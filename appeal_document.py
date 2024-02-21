from functools import cached_property
import yaml
import pandas as pd
from sectors import Sectors
from lines import Lines
from lessons_learned_extractor import LessonsLearnedExtractor


class AppealDocument:
    def __init__(self, lines):
        """
        Parameters
        ----------
        lines : pandas DataFrame (required)
            Pandas DataFrame, where each row is an element in the document.
        """
        # Add style columns
        lines['double_fontsize_int'] = (lines['size'].astype(float)*2).round(0).astype('Int64')
        lines['style'] = lines['font'].astype(str)+', '+lines['double_fontsize_int'].astype(str)+', '+lines['color'].astype(str)+', '+lines['highlight_color'].astype(str)

        # Process the lines: remove headers footers, etc.
        self.lines = Lines(lines)
        self.process_lines()


    def process_lines(self):
        """
        Add some more information.
        """
        # Sort lines by y of blocks
        self.lines = self.lines.sort_blocks_by_y()

        # Combine spans on same line with same styles
        self.lines = self.lines.combine_spans_same_style()

        # Add text_base
        self.lines['text_base'] = self.lines['text']\
            .str.replace(r'[^A-Za-z0-9 ]+', ' ', regex=True)\
            .str.replace(' +', ' ', regex=True)\
            .str.lower()\
            .str.strip()

        # Remove photo blocks, page numbers, references
        self.remove_photo_blocks()
        self.drop_all_repeating_headers_footers()
        self.remove_page_labels_references()

        # Have to run again in case repeating headers or footers were below or above the page labels or references
        self.drop_all_repeating_headers_footers()


    def remove_photo_blocks(self):
        """
        Remove blocks which look like photos from the document lines.
        """
        self.lines['block_page'] = self.lines['block_number'].astype(str)+'_'+self.lines['page_number'].astype(str)
        photo_blocks = self.lines.loc[self.lines['text'].astype(str).str.contains('Photo: '), 'block_page'].unique()
        self.lines = self.lines.loc[~self.lines['block_page'].isin(photo_blocks)].drop(columns=['block_page'])


    def remove_page_labels_references(self):
        """
        Remove page numbers from page headers and footers.
        Assumes headers and footers are the vertically highest and lowest elements on the page.
        """
        for option in ['headers', 'footers']:
        
            # Loop through pages
            for page_number in self.lines['page_number'].unique():

                # Get document vertically highest and lowest spans
                page_lines = self.lines\
                    .loc[self.lines['page_number']==page_number]\
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
                        page_labels_references_idxs += block.index.tolist()

                    # Check if individual lines are page numbers
                    block_lines = block.copy()
                    if option=='footers':
                        block_lines = block_lines[::-1]
                    for idx, line in block_lines.iterrows():
                        if line.is_page_label():
                            page_labels_references_idxs.append(idx)

                    # Drop. If non page labels or references, break.
                    page_labels_references_idxs = list(set(page_labels_references_idxs))
                    self.lines.drop(labels=page_labels_references_idxs, inplace=True)
                    if sorted(page_labels_references_idxs)==block.index.tolist():
                        break


    def drop_all_repeating_headers_footers(self):
        """
        Drop all repeating headers and footers.
        Run until there are no more repeating headers or footers.
        """
        # Drop headers
        while True:
            repeating_texts = self.get_repeating(which='top')
            if repeating_texts.empty:
                break
            self.lines = self.lines.drop(repeating_texts['index'].explode())

        # Drop footers
        while True:
            repeating_texts = self.get_repeating(which='bottom')
            if repeating_texts.empty:
                break
            self.lines = self.lines.drop(repeating_texts['index'].explode())
    

    def get_repeating(self, which):
        """
        Drop any repeating elements at the top or bottom of pages.
        """
        # Get spans in blocks at top of each page
        lines = self.lines.copy()
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