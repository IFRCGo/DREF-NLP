"""
Appeal Document class
"""
from ast import literal_eval
from functools import cached_property
import pandas as pd
from utils import is_text_title, get_similar_sector, get_lessons_learned_section_end
from document_processor import LessonsLearnedProcessor

class AppealDocument:
    def __init__(self, lines):
        self.lines = self.process_lines(lines)


    def process_lines(self, lines):
        lines = self.remove_photo_blocks(lines)
        lines['double_fontsize_int'] = (lines['size']*2).round(0).astype('Int64')
        lines['style'] = lines['font'].astype(str)+', '+lines['double_fontsize_int'].astype(str)+', '+lines['color'].astype(str)+', '+lines['highlight_color'].astype(str)

        return lines
    

    def remove_photo_blocks(self, lines):
        """
        Remove blocks which look like photos from the document lines.
        """
        lines['block_page'] = lines['block_number'].astype(str)+'_'+lines['page_number'].astype(str)
        photo_blocks = lines.loc[lines['text'].astype(str).str.contains('Photo: '), 'block_page'].unique()
        lines = lines.loc[~lines['block_page'].isin(photo_blocks)].drop(columns=['block_page'])

        return lines


    def get_lessons_learned(self, lessons_learned_title_texts: list[str], sector_title_texts: list[str]):
        """
        Get lessons learned
        """
        # Get lessons learned titles
        lessons_learned_titles = self.get_lessons_learned_titles(
            lessons_learned_title_texts=lessons_learned_title_texts
        )
        lessons_learned_titles_idxs = lessons_learned_titles.index.tolist()

        # Match the lessons learned to the sector indexes
        sector_titles = None
        lessons_learned_sector_map = None
        if len(lessons_learned_titles) > 1:
            lessons_learned_processor = LessonsLearnedProcessor(
                lessons_learned=lessons_learned_titles_idxs
            )
            sector_titles = self.get_sector_titles(sector_title_texts)
            sectors_lessons_learned_map = lessons_learned_processor.get_lessons_learned_sectors(
                sectors=sector_titles
            )
            lessons_learned_sector_map = {v:k for k,v in sectors_lessons_learned_map.items()}
        
        # Get the span of each lessons learned section
        lessons_learned = self.lines.copy()
        for idx, row in lessons_learned_titles.iterrows():

            section_lines = lessons_learned.loc[idx:]

            # Lessons learned section should only contain text lower than the title
            section_lines = section_lines.loc[~(
                (section_lines["page_number"]==row["page_number"]) & \
                (section_lines["origin"].apply(literal_eval).str[1] < literal_eval(row["origin"])[1])
            )]

            # Lessons learned section must end before the next lessons learned section
            following_lessons_learned_titles = [i for i in lessons_learned_titles_idxs if i > idx]
            if following_lessons_learned_titles:
                section_lines = section_lines.loc[:min(following_lessons_learned_titles)-1]

            # Lessons learned section must end before the next sector title
            following_sector_titles = [sector_idx for sector_idx in sectors_lessons_learned_map if sector_idx > idx]
            if following_sector_titles:
                section_lines = section_lines.loc[:min(following_sector_titles)-1]

            # Get end of lessons learned section based on font styles
            lessons_learned_text_end = get_lessons_learned_section_end(section_lines)
            section_lines = section_lines.loc[:lessons_learned_text_end]

            # Add section index to lessons learned
            lessons_learned.loc[section_lines.index, 'Section index'] = idx
            if lessons_learned_sector_map:
                if idx in lessons_learned_sector_map:
                    lessons_learned.loc[section_lines.index, 'Sector index'] = lessons_learned_sector_map[idx]

        # Filter for only lessons learned
        if sector_titles is not None:
            sector_names_map = sector_titles['Sector title'].to_dict()
            lessons_learned['Sector title'] = lessons_learned['Sector index'].map(sector_names_map)
        lessons_learned = lessons_learned.loc[lessons_learned['Section index'].notnull()]

        return lessons_learned
        

    def get_titles(self):
        """
        Get all titles in the documents
        """
        titles = self.lines.dropna(subset=['text'])\
                            .loc[
                                (self.lines['span_number']==0) & 
                                (self.lines['text'].apply(is_text_title))
                            ]
        return titles


    def get_lessons_learned_titles(self, lessons_learned_title_texts: list[str]):
        """
        """
        titles = self.get_titles()
        lessons_learned_titles = titles.loc[
            titles['text'].str.replace(r'[^A-Za-z ]+', ' ', regex=True)\
                        .str.replace(' +', ' ', regex=True)\
                        .str.lower()\
                        .str.strip()\
                        .isin(lessons_learned_title_texts)
        ]
        return lessons_learned_titles


    def get_sector_titles(self, sector_title_texts: list[str], threshold=0.5):
        """
        """
        sector_estimates = self.get_titles()
        sector_estimates[['Sector title', 'Sector similarity score']] = sector_estimates.apply(
            lambda row: 
                None if row['text']!=row['text'] else \
                pd.Series(
                    get_similar_sector(
                        row['text'], 
                        sector_title_texts=sector_title_texts
                    )
                ), axis=1
            )
        
        return sector_estimates.loc[sector_estimates['Sector similarity score'] >= threshold]