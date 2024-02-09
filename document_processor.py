from functools import cached_property
import yaml
import numpy as np
import pandas as pd
from utils import is_text_title, strip_non_alpha, strip_non_alphanumeric, colour_diff
from sectors import Sectors


class LessonsLearnedProcessor:
    def __init__(self, lines):
        """
        Parameters
        ----------
        lines : pandas DataFrame (required)
            Pandas DataFrame, where each row is an element in the document.

        lessons_learned : list (required)
            List of indexes, where each index represents the position of a lessons learned section.

        sectors : pandas DataFrame (required)
            Pandas DataFrame of sectors.
        """
        self.style_columns = ['font', 'double_fontsize_int', 'color', 'highlight_color', 'bold']
        self.lines = lines
        self.process_lines()
        self.sectors_lessons_learned_map = None


    def process_lines(self):
        """
        Add some more information.
        """
        # Remove photo blocks, page numbers, references
        self.remove_photo_blocks()
        self.drop_repeating_headers_footers()
        self.remove_headers_page_labels_references()
        self.remove_footers_page_labels_references()

        # Have to run again in case repeating headers or footers were below or above the page labels or references
        self.drop_repeating_headers_footers()

        # Add more info
        self.lines['double_fontsize_int'] = (self.lines['size'].astype(float)*2).round(0).astype('Int64')
        self.lines['style'] = self.lines['font'].astype(str)+', '+self.lines['double_fontsize_int'].astype(str)+', '+self.lines['color'].astype(str)+', '+self.lines['highlight_color'].astype(str)


    def remove_photo_blocks(self):
        """
        Remove blocks which look like photos from the document lines.
        """
        self.lines['block_page'] = self.lines['block_number'].astype(str)+'_'+self.lines['page_number'].astype(str)
        photo_blocks = self.lines.loc[self.lines['text'].astype(str).str.contains('Photo: '), 'block_page'].unique()
        self.lines = self.lines.loc[~self.lines['block_page'].isin(photo_blocks)].drop(columns=['block_page'])


    def remove_headers_page_labels_references(self):
        """
        Remove page numbers from page headers and footers.
        Assumes headers and footers are the vertically highest and lowest elementes on the page.
        """        
        # Loop through pages
        for page_number in self.lines['page_number'].unique():

            # Get document vertically highest and lowest spans
            page_lines = self.lines\
                .loc[self.lines['page_number']==page_number]\
                .sort_values(by=['origin_y'], ascending=True)
            block_numbers = page_lines['block_number'].drop_duplicates().tolist()

            # Headers: Loop through blocks and remove header page labels and references
            for block_number in block_numbers:
                block_lines = page_lines.loc[page_lines['block_number']==block_number]
                if self.is_page_label(block_lines) or self.is_reference(block_lines):
                    self.lines.drop(labels=block_lines.index, inplace=True)
                else:
                    break


    def remove_footers_page_labels_references(self):
        """
        Remove page numbers from page headers and footers.
        Assumes headers and footers are the vertically highest and lowest elementes on the page.
        """        
        # Loop through pages
        for page_number in self.lines['page_number'].unique():

            # Get document vertically highest and lowest spans
            page_lines = self.lines\
                .loc[self.lines['page_number']==page_number]\
                .sort_values(by=['origin_y'], ascending=True)
            block_numbers = page_lines['block_number'].drop_duplicates().tolist()

            # Footers: Loop through blocks and remove footer page labels and references
            for block_number in block_numbers[::-1]:
                block_lines = page_lines.loc[page_lines['block_number']==block_number]
                if self.is_page_label(block_lines) or self.is_reference(block_lines):
                    self.lines.drop(labels=block_lines.index, inplace=True)
                else:
                    break


    def is_page_label(self, block):
        """
        """
        # Get the first text containing alphanumeric characters
        block = block.copy()
        block.loc[:, 'text'] = block.loc[:, 'text'].apply(strip_non_alphanumeric).str.lower()
        block = block.dropna(subset=['text']).sort_values(by=['line_number', 'span_number'])
        first_span = block.iloc[0]

        # If the the first word is page, assume page label
        if first_span['text'].startswith('page'):
            return True
        
        # If only a single number, assume page label
        if len(block)==1 and first_span['text'].isdigit():
            return True

        return False


    def is_reference(self, block):
        """
        Remove references denoted by a superscript number in document headers and footers.
        """
        # Get the first text containing alphanumeric characters
        block = block.copy()
        block.loc[:, 'text'] = block.loc[:, 'text'].apply(strip_non_alphanumeric).str.lower()
        block = block.dropna(subset=['text']).sort_values(by=['line_number', 'span_number'])
        first_span = block.iloc[0]

        # If the first span is small and a number
        if len(block)==1:
            if first_span['text'].isdigit():
                return True
        elif len(block)>1:
            if first_span['text'].isdigit():
                if (block.iloc[1]['size'] - first_span['size']) >= 1:
                    return True

        return False


    def drop_repeating_headers_footers(self):
        """
        Drop any repeating elements at the top or bottom of pages.
        """
        # Get spans in blocks at top of each page
        lines = self.lines.copy()
        lines['page_block'] = lines['page_number'].astype(str)+'_'+lines['block_number'].astype(str)
        
        # Get top and bottom page blocks
        top_page_blocks = lines.loc[lines.groupby(['page_number'])['origin_y'].idxmax()]
        bottom_page_blocks = lines.loc[lines.groupby(['page_number'])['origin_y'].idxmin()]

        for page_blocks in [top_page_blocks, bottom_page_blocks]:

            # Get repeating texts
            elements = lines.loc[lines['page_block'].isin(page_blocks['page_block'].unique())]
            elements.loc[:, 'text'] = elements.loc[:, 'text'].apply(strip_non_alphanumeric).str.lower()
            repeating_texts = elements\
                .reset_index()\
                .groupby(['page_number'])\
                .agg({'text': lambda x: ' '.join(x), 'index': tuple})\
                .groupby(['text'])\
                .filter(lambda x: len(x)>1)

            # Remove indexes - check exists in case page top block overlaps bottom block
            remove_indexes = [idx for idx in repeating_texts['index'].explode() if idx in self.lines.index]
            self.lines = self.lines.drop(remove_indexes)


    @cached_property
    def lessons_learned_titles(self):
        """
        Get lessons learned titles
        """
        lessons_learned_title_texts = yaml.safe_load(open('lessons_learned_titles.yml'))
        lessons_learned_titles = self.titles.loc[
            self.titles['text']\
                .str.replace(r'[^A-Za-z ]+', ' ', regex=True)\
                .str.replace(' +', ' ', regex=True)\
                .str.lower()\
                .str.strip()\
                .isin(lessons_learned_title_texts)
        ]
        return lessons_learned_titles
        

    @cached_property
    def titles(self):
        """
        Get all titles in the documents
        """
        # Get all lines starting with capital letter
        titles = self.lines.dropna(subset=['text'])\
                            .loc[
                                (self.lines['span_number']==0) & 
                                (self.lines['text'].apply(is_text_title))
                            ]
        
        # Assume that the body text is most common, and drop titles not bigger than this
        body_style = self.lines['style'].value_counts().idxmax()
        titles = titles.loc[titles['style']!=body_style]
        
        return titles


    @cached_property
    def sector_titles(self):
        """
        """
        sector_titles = self.titles.copy()

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


    def get_lessons_learned(self):
        """
        Get lessons learned
        """
        # Match the lessons learned to the sector indexes
        lessons_learned_sector_map = None
        if len(self.lessons_learned_titles) > 1:

            # Get the document sector titles
            sectors_lessons_learned_map = self.get_lessons_learned_sectors(
                sectors=self.sector_titles
            )
            lessons_learned_sector_map = {v['idx']:k for k,v in sectors_lessons_learned_map.items()}
        
        # Get the span of each lessons learned section
        lessons_learned = self.lines.copy()
        for idx, row in self.lessons_learned_titles.iterrows():

            # Get lessons learned section lines
            section_lines = self.get_lessons_learned_section_lines(idx=idx)

            # Add section index to lessons learned
            lessons_learned.loc[section_lines.index, 'Section index'] = idx
            if lessons_learned_sector_map:
                if idx in lessons_learned_sector_map:
                    lessons_learned.loc[section_lines.index, 'Sector index'] = lessons_learned_sector_map[idx]

        # Add sector title
        if lessons_learned_sector_map:
            lessons_learned['Sector title'] = lessons_learned['Sector index'].map(self.sector_titles['Sector title'].to_dict())
            lessons_learned['Sector similarity score'] = lessons_learned['Sector index'].map(self.sector_titles['Sector similarity score'].to_dict())

        # Filter for only lessons learned
        if not self.lessons_learned_titles.empty:
            lessons_learned = lessons_learned.loc[lessons_learned['Section index'].notnull()]

        return lessons_learned

    
    def get_lessons_learned_sectors(self, sectors):
        """
        Get a map between sector title IDs and lessons learned title IDs.
        """
        # Get the most likely font style of the sector titles
        primary_sector_style = self.get_primary_sector_style(
            sectors=sectors
        )
        self.sectors_lessons_learned_map = primary_sector_style['Lessons learned covered']
        if self.unmatched_lessons_learned:

            # Match lessons learned to sectors for sectors of a similar style
            similar_sector_styles = self.get_sectors_similar_styles(
                style=primary_sector_style,
                sectors=sectors
            )
            self.match_sectors_by_distance(
                sectors=similar_sector_styles
            )
            
        return self.sectors_lessons_learned_map


    @property
    def unmatched_lessons_learned(self):
        if self.sectors_lessons_learned_map is None:
            return self.lessons_learned_titles.index.tolist()
        else:
            return [
                idx for idx in self.lessons_learned_titles.index.tolist()
                if idx not in self.sectors_lessons_learned_map.values()
            ]


    def get_primary_sector_style(self, sectors):
        """
        Match lessons learned to sectors by getting the style which matches most sectors.
        """
        # Group the sector estimates into styles
        sector_title_styles = sectors\
            .reset_index()\
            .rename(columns={'index': 'Sector title indexes'})\
            .groupby(['style']+self.style_columns, dropna=False)\
            .agg({'text': tuple, 'Sector title': tuple, 'Sector title indexes': tuple, 'Sector similarity score': 'mean'})\
            .reset_index()\
            .set_index('style')

        # Get which sector idxs correspond to lessons learned
        sector_title_styles['Lessons learned covered'] = sector_title_styles['Sector title indexes']\
            .apply(
                lambda sector_idxs: {
                    sector_idx: self.get_next_lessons_learned(sector_idx, sector_idxs) 
                    for sector_idx in sector_idxs 
                    if self.get_next_lessons_learned(sector_idx, sector_idxs)
                }
            )
        sector_title_styles['Number lessons learned covered'] = sector_title_styles['Lessons learned covered'].apply(lambda x: x if x is None else len(x))

        # Get distance from lessons learned
        sector_title_styles['Distance from lessons learned'] = sector_title_styles['Lessons learned covered'].apply(lambda x: np.mean([v['distance'] for k,v in x.items()]) if x else float('nan'))
        
        # Select the largest style that covers most lessons learned sections
        primary_sector_style = sector_title_styles\
            .sort_values(
                by=['Number lessons learned covered', 'double_fontsize_int', 'Distance from lessons learned'],
                ascending=[False, False, True]
            )\
            .iloc[0]
            
        return primary_sector_style


    def match_sectors_by_distance(self, sectors):
        """
        Match lessons learned to given sectors by distance between lessons learned and sectors.
        """    
        # Get other possible sector titles: texts with similar style, that are not the selected style
        while self.unmatched_lessons_learned and not sectors.empty:

            sectors = sectors.copy()
            sectors['Lessons learned covered'] = sectors\
                .index\
                .to_series()\
                .apply(
                    lambda sector_idx: self.get_next_lessons_learned(
                        sector_idx, 
                        self.sectors_lessons_learned_map
                    )
                )
            sectors.dropna(subset=['Lessons learned covered'], inplace=True)

            if not sectors.empty:

                # Get distance between sector title and lessons learned section
                sectors['Distance from lessons learned'] = sectors['Lessons learned covered'].apply(lambda x: np.mean([v['distance'] for k,v in x.items()]) if x else float('nan'))

                # Get the titles which are closest to the lessons learned
                best_sector = sectors\
                    .sort_values(
                        by=['Sector similarity score', 'Distance from lessons learned'], 
                        ascending=[False, True]
                    )\
                    .drop_duplicates(subset=['Lessons learned covered'])\
                    .drop_duplicates(subset=['Sector title'])\
                    .iloc[0]

                self.sectors_lessons_learned_map[best_sector.name] = best_sector['Lessons learned covered']


    def get_next_lessons_learned(self, sector_idx, sector_idxs):
        """
        Get the next unmatched lessons learned index in the document after the sector position at sector_idx, unless there is a sector index first (in sector_idxs). Compare by vertical position in the whole document.

        Parameters
        ----------
        sector_idx : int (required)
            Index of the sector title to get the next lessons learned section for.

        sector_idxs : list of ints (required)
            List of indexes of known sector titles.
        """
        # The lessons learned must be in the sector section
        # Define the sector section as before the next "more titley" title
        sector_section = self.cut_at_first_title(self.lines.loc[sector_idx:])

        # Get y position of sectors and lessons learned
        sector_idx_position = self.lines.loc[sector_idx, ['page_number', 'total_y']]
        sector_idxs_positions = self.lines.loc[list(sector_idxs), ['page_number', 'total_y']]
        unmatched_lessons_learned_positions = self.lines.loc[self.unmatched_lessons_learned, ['page_number', 'total_y']]
        
        # Get the sectors and lessons learned which are after the sector - compare vertical position
        next_sector_idxs = sector_idxs_positions.loc[
            sector_idxs_positions['total_y'] > sector_idx_position['total_y']
        ].sort_values(by=['total_y'], ascending=True)
        next_lessons_learned_idxs = unmatched_lessons_learned_positions.loc[
            unmatched_lessons_learned_positions['total_y'] > sector_idx_position['total_y']
        ].sort_values(by=['total_y'], ascending=True)

        # Loop through next lessons learned section indexes, and return if before the nearest sector index
        if not next_lessons_learned_idxs.empty:
            next_lessons_learned = next_lessons_learned_idxs.iloc[0]
            next_lessons_learned_distance = {
                "idx": next_lessons_learned.name,
                "distance": next_lessons_learned['total_y'] - sector_idx_position['total_y']
            }

            # If lessons learned is before the end of the sector section
            if next_lessons_learned['total_y'] < sector_section['total_y'].max():

                # If no sectors, return the nearest lessons learned section
                if next_sector_idxs.empty:
                    return next_lessons_learned_distance
                
                # If lessons learned section is nearer than the section, return it
                next_sector = next_sector_idxs.iloc[0]
                if next_lessons_learned['total_y'] < next_sector['total_y']:
                    return next_lessons_learned_distance


    def styles_are_similar(self, style1, style2):
        # Check if two styles are similar
        if abs(style1["double_fontsize_int"] - style2["double_fontsize_int"]) <= 4:
            if colour_diff(style1["highlight_color"], style2["highlight_color"]) < 0.1:
                if colour_diff(style1['color'], style2['color']) < 0.1:
                    if style1['bold'] == style2['bold']:
                        return True
        return False


    def get_sectors_similar_styles(self, style, sectors):
        return sectors.loc[
            (sectors['style']!=style.name) & 
            sectors.apply(
                lambda row: self.styles_are_similar(row, style), 
                axis=1
            )
        ]


    def get_lessons_learned_section_lines(self, idx):
        """
        Get the lines of a lessons learned section given the index of the title.
        """
        lessons_learned_title = self.lessons_learned_titles.loc[idx]

        # Lessons learned section should only contain text lower than the title
        section_lines = self.lines.loc[
            self.lines['total_y'] >= lessons_learned_title['total_y']
        ]

        # Lessons learned section must end before the next lessons learned section
        next_lessons_learned = self.lessons_learned_titles.loc[
            self.lessons_learned_titles['total_y'] > lessons_learned_title['total_y']
        ]
        if not next_lessons_learned.empty:
            next_lessons_learned_y = next_lessons_learned.sort_values(by=['total_y'], ascending=True).iloc[0]['total_y']
            section_lines = section_lines.loc[section_lines['total_y'] < next_lessons_learned_y]

        # Lessons learned section must end before the next sector_title
        if self.sectors_lessons_learned_map:
            next_sector_titles = self.sector_titles.loc[self.sectors_lessons_learned_map.keys()]
            next_sector_titles = next_sector_titles.loc[
                next_sector_titles['total_y'] > lessons_learned_title['total_y']
            ]
            if not next_sector_titles.empty:
                next_sector_title_y = next_sector_titles.sort_values(by=['total_y'], ascending=True).iloc[0]['total_y']
                section_lines = section_lines.loc[section_lines['total_y'] < next_sector_title_y]

        # Cut the lessons learned section at the next title
        section_lines = self.cut_at_first_title(
            section=section_lines
        )

        return section_lines


    def cut_at_first_title(self, section):
        """
        Cut the section lines at the first title.
        Assume that the first line is the title of the section.
        """
        # Assume that the title is the first line of the section
        title = section.iloc[0]
        section_content = section.iloc[1:]

        # Get title information
        first_section_line_with_chars = section_content.loc[section_content['text'].astype(str).str.contains('[a-zA-Z]')].iloc[0]

        # Filter to only consider titles in section
        section_titles = section_content.loc[
            [idx for idx in section_content.index if idx in self.titles.index]
        ].sort_values(by=['total_y'])
        
        # Get the next title which is more titley than the title
        more_titley_y = None
        for idx, line in section_titles.iterrows():
            if self.more_titley(title, first_section_line_with_chars, line):
                more_titley_y = line['total_y']
                break

        # Cut the section at the title index found
        if more_titley_y is None:
            return section

        return section.loc[section['total_y'] < more_titley_y]


    def more_titley(self, title, nontitle, line):
        """
        Check if line is more titley than title.
        Use nontitle to check what a title looks like.
        """
        # If line is larger, it is more titley
        if line['double_fontsize_int'] > title['double_fontsize_int']:
            return True

        if line['double_fontsize_int'] == title['double_fontsize_int']:
            
            # If same size but nontitle is smaller, it is more titley
            if nontitle['double_fontsize_int'] < title['double_fontsize_int']:
                return True

            # If same size but nontitle is not bold
            if line['bold'] and not nontitle['bold']:
                return True

        return False