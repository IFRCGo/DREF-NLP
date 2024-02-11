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

        lessons_learned : list (required)
            List of indexes, where each index represents the position of a lessons learned section.

        sectors : pandas DataFrame (required)
            Pandas DataFrame of sectors.
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
        self.lines.combine_spans_same_style()

        # Add text_base
        self.lines['text_base'] = self.lines['text']\
            .str.replace(r'[^A-Za-z0-9 ]+', ' ', regex=True)\
            .str.replace(' +', ' ', regex=True)\
            .str.lower()\
            .str.strip()

        # Remove photo blocks, page numbers, references
        self.remove_photo_blocks()
        self.drop_repeating_headers_footers()
        self.remove_headers_page_labels_references()
        self.remove_footers_page_labels_references()

        # Have to run again in case repeating headers or footers were below or above the page labels or references
        self.drop_repeating_headers_footers()


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
                if block_lines.starts_with_page_label() or block_lines.starts_with_reference():
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
                if block_lines.starts_with_page_label() or block_lines.starts_with_reference():
                    self.lines.drop(labels=block_lines.index, inplace=True)
                else:
                    break
    

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

        lessons_learned_title_texts = LessonsLearnedExtractor().lessons_learned_title_texts

        for page_blocks in [top_page_blocks, bottom_page_blocks]:

            # Get repeating texts
            elements = lines.loc[lines['page_block'].isin(page_blocks['page_block'].unique())]
            repeating_texts = elements\
                .reset_index()\
                .groupby(['page_number'])\
                .agg({'text_base': lambda x: ' '.join(x), 'index': tuple})\
                .groupby(['text_base'])\
                .filter(lambda x: len(x)>2)

            # Remove titles
            repeating_texts = repeating_texts.loc[~(
                repeating_texts['text_base'].isin(lessons_learned_title_texts)
            )]

            # Remove indexes - check exists in case page top block overlaps bottom block
            remove_indexes = [idx for idx in repeating_texts['index'].explode() if idx in self.lines.index]
            self.lines = self.lines.drop(remove_indexes)


    @cached_property
    def titles(self):
        return self.lines.titles


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


    @cached_property
    def lessons_learned(self):
        """
        """
        lessons_learned_extractor = LessonsLearnedExtractor()
        lessons_learned = lessons_learned_extractor.get_lessons_learned(
            document=self
        )
        
        return lessons_learned