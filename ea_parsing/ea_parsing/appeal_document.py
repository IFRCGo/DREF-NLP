import requests
from functools import cached_property
import fitz
import pandas as pd
from ea_parsing import utils
from ea_parsing.sectors import Sectors
from ea_parsing.lines import Lines
from ea_parsing.lessons_learned_extractor import LessonsLearnedExtractor


class GOAPI:
    def __init__(self):
        """
        Class to interact with the IFRC GO API.
        """
        pass


    def get_appeal_data(self, mdr_code):
        """
        Get appeal details for an appeal specified by the MDR code.
        """
        # Get the results
        results = self._get_results(
            url=f'https://goadmin.ifrc.org/api/v2/appeal/',
            params={
                'format': 'json', 
                'code': mdr_code
            }
        )
        # Check only one appeal
        if len(results)==0:
            raise RuntimeError(f'No results found for MDR code {mdr_code}')
        if len(results) > 1:
            raise RuntimeError(f'Multiple results found for MDR code {mdr_code}:\n{results}')
        
        return results[0]


    def get_appeal_document_data(self, id):
        """
        Get appeal documents for an appeal specified by the appeal ID.
        """
        documents = self._get_results(
            url='https://goadmin.ifrc.org/api/v2/appeal_document/', 
            params={
                'format': 'json', 
                'appeal': id
            }
        )
        return documents

    
    def _get_results(self, url, params):
        """
        Get results for the URL, looping through pages.
        """
        # Loop through pages until there are no pages left
        results = []
        while url:
            response = requests.get(
                url=url, 
                params=params
            )
            response.raise_for_status()
            json = response.json()
            results += json['results']
            url = json['next']

        return results



class Appeal:
    def __init__(self, mdr_code):
        """
        Parameters
        ----------
        mdr_code : string (required)
            MDR code of the appeal.
        """
        self.mdr_code = mdr_code
        
        # Set appeal details
        appeal_data = GOAPI().get_appeal_data(mdr_code=self.mdr_code)
        for k, v in appeal_data.items():
            setattr(self, k, v)

        # Check that appeal is an emergency appeal
        if self.atype != 1:
            raise RuntimeError(f'Appeal with MDR code {mdr_code} is a {self.atype_display}, not an Emergency Appeal')

    
    @cached_property
    def documents(self):
        """
        Get all documents for the appeal from the IFRC GO API.
        """
        # Get appeal document data and convert to AppealDocument
        documents_data = GOAPI().get_appeal_document_data(id=self.id)
        documents = [
            AppealDocument(
                document_url=data['document_url'], 
                name=data['name']
            )
            for data in documents_data
        ]
        return documents


    @cached_property
    def final_report(self):
        """
        Get the final report for the appeal.
        """
        # Get final reports
        final_reports = [
            document 
            for document in self.documents 
            if ('final' in document.name.lower())
        ]
        
        if len(final_reports)==0:
            return None
        
        if len(final_reports) > 1:
            final_reports = [document for document in final_reports if ('prelim' not in document['name'].lower())]

        if len(final_reports) > 1:
            final_reports = sorted(final_reports, key=lambda d: d['created_at'], reverse=True)

        return final_reports[0]



class AppealDocument:
    def __init__(self, name, document_url):
        """
        """
        self.name = name
        self.document_url = document_url


    @cached_property
    def raw_lines(self):
        """
        Extract lines from the appeal document.
        """
        data = []
        total_y = 0

        # Get the document content and open with fitz
        document_url = self.document_url
        document = requests.get(document_url)
        doc = fitz.open(stream=document.content, filetype='pdf')

        # Loop through pages and paragraphs
        for page_number, page_layout in enumerate(doc):

            # Get drawings to get text highlights
            coloured_drawings = [drawing for drawing in page_layout.get_drawings() if (drawing['fill'] != (0.0, 0.0, 0.0))]
            page_images = page_layout.get_image_info()

            # Loop through blocks
            blocks = page_layout.get_text("dict", flags=11)["blocks"]
            for block_number, block in enumerate(blocks):
                for line_number, line in enumerate(block["lines"]):
                    spans = [span for span in line['spans'] if span['text'].strip()]
                    for span_number, span in enumerate(spans):
                            
                        # Check if the text block is contained in a drawing
                        highlights = []
                        for drawing in coloured_drawings:
                            if utils.get_overlap(span['bbox'], drawing['rect']):
                                drawing['overlap'] = utils.get_overlap(span['bbox'], drawing['rect'])
                                highlights.append(drawing)

                        # Get largest overlap
                        highlight_color_hex = None
                        if highlights:
                            largest_highlight = max(highlights, key=lambda x: x['overlap'])
                            highlight_color = largest_highlight['fill']
                            if highlight_color:
                                highlight_color_hex = '#%02x%02x%02x' % (int(255*highlight_color[0]), int(255*highlight_color[1]), int(255*highlight_color[2]))

                        # Check if the span overlaps with an image
                        max_overlap = None
                        overlapping_images = [utils.get_overlap(span['bbox'], img['bbox'])/utils.get_area(span['bbox']) for img in page_images if utils.get_overlap(span['bbox'], img['bbox'])]
                        if overlapping_images:
                            max_overlap = max(overlapping_images)

                        contains_images = [img for img in page_images if utils.contains(img['bbox'], span['bbox'])]
                        
                        # Append results
                        span['text'] = span['text'].replace('\r', '\n')
                        span['bold'] = utils.is_bold(span["font"])
                        span['highlight_color'] = highlight_color_hex
                        span['page_number'] = page_number
                        span['block_number'] = block_number
                        span['line_number'] = line_number
                        span['span_number'] = span_number
                        span['origin_x'] = span['origin'][0]
                        span['origin_y'] = span['origin'][1]
                        span['total_y'] = span['origin'][1]+total_y
                        span['img'] = bool(contains_images)
                        data.append(span)

            total_y += page_layout.rect.height

        return Lines(pd.DataFrame(data))


    @cached_property
    def lines(self):
        """
        Process the raw lines to get the document content.
        """
        lines = self.raw_lines.copy()

        # Sort lines by y of blocks
        lines = lines.sort_blocks_by_y()

        # Combine spans on same line with same styles
        lines = lines.combine_spans_same_style()

        # Add text_base
        lines['text_base'] = lines['text']\
            .str.replace(r'[^A-Za-z0-9 ]+', ' ', regex=True)\
            .str.replace(' +', ' ', regex=True)\
            .str.lower()\
            .str.strip()

        # Remove photo blocks, page numbers, references
        lines = self.remove_photo_blocks(lines=lines)
        lines = self.drop_all_repeating_headers_footers(lines=lines)
        lines = self.remove_page_labels_references(lines=lines)

        # Have to run again in case repeating headers or footers were below or above the page labels or references
        lines = self.drop_all_repeating_headers_footers(lines=lines)
        lines = self.remove_page_labels_references(lines=lines)

        return lines


    def remove_photo_blocks(self, lines):
        """
        Remove blocks which look like photos from the document lines.
        """
        lines['block_page'] = lines['block_number'].astype(str)+'_'+lines['page_number'].astype(str)
        photo_blocks = lines.loc[lines['text'].astype(str).str.contains('Photo: '), 'block_page'].unique()
        lines = lines.loc[~lines['block_page'].isin(photo_blocks)].drop(columns=['block_page'])

        return lines


    def remove_page_labels_references(self, lines):
        """
        Remove page numbers from page headers and footers.
        Assumes headers and footers are the vertically highest and lowest elements on the page.
        """
        for option in ['headers', 'footers']:
        
            # Loop through pages
            for page_number in lines['page_number'].unique():

                # Get document vertically highest and lowest spans
                page_lines = lines\
                    .loc[lines['page_number']==page_number]\
                    .sort_values(by=['origin_y'], ascending=True)
                block_numbers = page_lines['block_number'].drop_duplicates().tolist()

                # Loop through blocks and remove page labels and references
                if option=='footers':
                    block_numbers = block_numbers[::-1]
                for block_number in block_numbers:

                    block = page_lines.loc[page_lines['block_number']==block_number]
                    page_labels_references_idxs = []

                    # Check if the whole block is a page label or reference
                    if block.is_page_label() or block.is_reference():
                        lines.drop(labels=block.index, inplace=True)
                        continue

                    # Loop through lines and remove page numbers and references
                    for line in block['line_number'].unique():
                        line_lines = block.loc[block['line_number']==line]
                        if line_lines.is_page_label() or line_lines.is_reference():
                            block = block.drop(labels=line_lines.index)
                            lines.drop(labels=line_lines.index, inplace=True)
                    if block.empty:
                        continue

                    break

        return lines


    def drop_all_repeating_headers_footers(self, lines):
        """
        Drop all repeating headers and footers.
        Run until there are no more repeating headers or footers.
        """
        # Drop headers
        while True:
            repeating_texts = self.get_repeating(which='top', lines=lines)
            if repeating_texts.empty:
                break
            lines = lines.drop(repeating_texts['index'].explode())

        # Drop footers
        while True:
            repeating_texts = self.get_repeating(which='bottom', lines=lines)
            if repeating_texts.empty:
                break
            lines = lines.drop(repeating_texts['index'].explode())

        return lines
    

    def get_repeating(self, which, lines):
        """
        Drop any repeating elements at the top or bottom of pages.
        """
        # Get spans in blocks at top of each page
        lines['page_block'] = lines['page_number'].astype(str)+'_'+lines['block_number'].astype(str)
        
        # Get the top and bottom blocks on each page
        if which=='top':
            page_blocks = lines.loc[lines.groupby(['page_number'])['origin_y'].idxmax()]
        elif which=='bottom':
            page_blocks = lines.loc[lines.groupby(['page_number'])['origin_y'].idxmin()]
        else:
            raise RuntimeError('Unrecognised value for "which", should be "top" or "bottom"')
        page_lines = lines.loc[lines['page_block'].isin(page_blocks['page_block'].unique())]

        # Get repeating texts
        elements = lines.loc[lines['page_block'].isin(page_blocks['page_block'].unique())]
        repeating_texts = elements\
            .reset_index()\
            .groupby(['page_number'])\
            .agg({'text_base': lambda x: ' '.join(x), 'index': tuple})\
            .groupby(['text_base'])\
            .filter(lambda x: len(x)>2)

        # Don't remove lessons learned titles
        lessons_learned_title_texts = LessonsLearnedExtractor().lessons_learned_title_texts
        repeating_texts = repeating_texts.loc[~(
            repeating_texts['text_base'].isin(lessons_learned_title_texts)
        )]

        # Remove indexes
        return repeating_texts


    @cached_property
    def titles(self):
        return self.lines.titles


    @cached_property
    def sector_titles(self):
        """
        """
        sector_titles = self.titles.copy()

        # Get only sector titles in the "Detailed operational plan" section, if it exists
        detailed_operational_plan_titles = sector_titles.loc[sector_titles['text_base']=='c detailed operational plan']
        if not detailed_operational_plan_titles.empty:
            sector_titles = sector_titles.loc[sector_titles['total_y'] > detailed_operational_plan_titles['total_y'].min()]

        # Get a score representing how "sector titley" it is
        sectors = Sectors()
        sector_titles[['Sector title', 'Sector similarity score']] = sector_titles.apply(
            lambda row: 
                None if row['text']!=row['text'] else \
                pd.Series(
                    sectors.get_similar_sector(
                        row['text']
                    )
                ), axis=1
            )

        # Filter to only where the score is >= 0.5
        sector_titles = sector_titles.loc[sector_titles['Sector similarity score'] >= 0.5]
        
        return sector_titles


    @cached_property
    def lessons_learned(self):
        """
        Extract lessons learned from the document.
        """
        lessons_learned_extractor = LessonsLearnedExtractor()
        lessons_learned = lessons_learned_extractor.get_lessons_learned(
            document=self
        )
        
        return lessons_learned