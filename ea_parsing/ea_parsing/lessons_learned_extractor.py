"""
"""
from functools import cached_property
import numpy as np
import pandas as pd
import ea_parsing.definitions


class LessonsLearnedExtractor:
    def __init__(self):

        self.lessons_learned_title_texts = ea_parsing.definitions.LESSONS_LEARNED_TITLES


    @cached_property
    def lessons_learned_titles(self):
        """
        Get lessons learned titles
        """
        lessons_learned_titles = self.document.titles.loc[
            self.document.titles['text_base'].isin(self.lessons_learned_title_texts)
        ]
        return lessons_learned_titles


    @property
    def number_of_lessons_learned_sections(self):
        """
        Total number of lessons learned sections in the document.
        """
        return int(len(self.lessons_learned_titles))


    def get_lessons_learned(self, document):
        """
        Get lessons learned
        """
        self.document = document
        self.sectors_lessons_learned_map = None

        # Get a map between the document sectors and the lessons learned sections
        sectors_lessons_learned_map = self.get_lessons_learned_sectors(
            sectors=self.document.sector_titles
        )
        lessons_learned_sector_map = {}
        if sectors_lessons_learned_map:
            lessons_learned_sector_map = {v['idx']:k for k,v in sectors_lessons_learned_map.items()}
        
        # Get the span of each lessons learned section
        lessons_learned = []
        sector_titles_dict = self.document.sector_titles['Sector title'].to_dict()
        sector_similarity_scores_dict = self.document.sector_titles['Sector similarity score'].to_dict()
        for idx, row in self.lessons_learned_titles.iterrows():

            # Get lessons learned section title and details
            select_columns = ['text', 'text_base', 'style', 'page_number', 'block_number', 'line_number', 'span_number', 'total_y']
            lessons_learned_section_title = self.lessons_learned_titles.loc[idx]
            title_details = lessons_learned_section_title[select_columns].to_dict()
            title_details['idx'] = idx

            # Get lessons learned section content, check if empty
            section_content = self.get_lessons_learned_section_lines(
                title=lessons_learned_section_title
            )
            if section_content.is_nothing:
                section_content = pd.DataFrame()
            
            # Add title, content, and sector details to lessons_learned
            sector_idx = lessons_learned_sector_map.get(idx)
            lessons_learned_details = {
                'title': title_details,
                'sector_title': sector_titles_dict.get(sector_idx),
                'sector_idx': None if sector_idx is None else int(sector_idx),
                'sector_similarity_score': sector_similarity_scores_dict.get(sector_idx),
                'content': section_content[[col for col in select_columns if col in section_content.columns]].reset_index().to_dict('records')
            }            
            lessons_learned.append(lessons_learned_details)

        return lessons_learned

    
    def get_lessons_learned_sectors(self, sectors):
        """
        Get a map between sector title IDs and lessons learned title IDs.
        """
        if sectors.empty:
            return

        # Get the most likely font style of the sector titles
        primary_sector_style = self.get_primary_sector_style(
            sectors=sectors
        )
        self.sectors_lessons_learned_map = primary_sector_style['Lessons learned covered']
        if self.unmatched_lessons_learned:

            # Match lessons learned to sectors for sectors of a similar style
            similar_sector_styles = sectors.loc[
                (sectors['style']!=primary_sector_style.name) & 
                sectors.apply(
                    lambda row: row.is_similar_style(primary_sector_style), 
                    axis=1
                )
            ]
            self.match_sectors_by_distance(
                sectors=similar_sector_styles
            )
            
        return self.sectors_lessons_learned_map


    @property
    def unmatched_lessons_learned(self):
        if self.sectors_lessons_learned_map is None:
            return self.lessons_learned_titles.index.tolist()
        else:
            matched_lessons_learned = [x['idx'] for x in self.sectors_lessons_learned_map.values()]
            return [
                idx for idx in self.lessons_learned_titles.index.tolist()
                if idx not in matched_lessons_learned
            ]


    def get_primary_sector_style(self, sectors):
        """
        Match lessons learned to sectors by getting the style which matches most sectors.
        """
        if sectors.empty:
            return
        
        # Group the sector estimates into styles
        sector_title_styles = sectors\
            .reset_index()\
            .rename(columns={'index': 'Sector title indexes'})\
            .groupby(['style', 'font', 'double_fontsize_int', 'color', 'highlight_color', 'bold'], dropna=False)\
            .agg({'text': tuple, 'Sector title': tuple, 'Sector title indexes': tuple, 'Sector similarity score': 'mean'})\
            .reset_index()\
            .set_index('style')

        # Get which sector idxs correspond to lessons learned
        sector_title_styles['Lessons learned covered'] = sector_title_styles['Sector title indexes'].apply(
            lambda sector_idxs: {
                sector_idx: self.get_lessons_learned_covered(sector_idx, sector_idxs)
                for sector_idx in sector_idxs
                if self.get_lessons_learned_covered(sector_idx, sector_idxs)
            }
        )
        sector_title_styles['Number lessons learned covered'] = sector_title_styles['Lessons learned covered'].apply(lambda x: x if x is None else len(x))

        # Get distance from lessons learned
        sector_title_styles['Distance from lessons learned'] = sector_title_styles['Lessons learned covered'].apply(lambda x: float(np.mean([v['distance'] for k,v in x.items()]) if x else float('nan')))
        
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
                    lambda sector_idx: self.get_lessons_learned_covered(
                        sector_idx, 
                        self.sectors_lessons_learned_map
                    )
                )
            sectors.dropna(subset=['Lessons learned covered'], inplace=True)

            if not sectors.empty:

                # Get distance between sector title and lessons learned section
                sectors['Distance from lessons learned'] = sectors['Lessons learned covered'].apply(lambda x: x.get('distance'))

                # Get the titles which are closest to the lessons learned
                best_sectors = sectors\
                    .sort_values(
                        by=['Sector similarity score', 'Distance from lessons learned'], 
                        ascending=[False, True]
                    )\
                    .drop_duplicates(subset=['Sector title'])
                if not best_sectors.empty:
                    
                    best_sector = best_sectors.iloc[0]
                    self.sectors_lessons_learned_map[best_sector.name] = best_sector['Lessons learned covered']
                    sectors.drop(best_sector.name, inplace=True)


    def get_lessons_learned_covered(self, sector_idx, sector_idxs):
        """
        Get lessons learned covered by the sector at sector_idx, given the other sectors at sector_idxs.
        """
        # Get the lessons learned after the sector_idx
        next_lessons_learned_idxs = self.get_idxs_after_idx(
            idx=sector_idx,
            idxs=self.unmatched_lessons_learned
        )
        if not next_lessons_learned_idxs.empty:
            next_lessons_learned = next_lessons_learned_idxs.iloc[0]

            sector_title_line = self.document.lines.loc[sector_idx]
            next_lessons_learned_distance = {
                "idx": next_lessons_learned.name,
                "distance": next_lessons_learned['total_y'] - sector_title_line['total_y']
            }

            # Lessons learned must be before the end of the sector section
            # If only one lessons learned, impose stricter rule: sector section ends at next titley title
            sector_bounds = self.document.lines.loc[sector_idx:]
            if self.number_of_lessons_learned_sections <= 1:
                sector_bounds = sector_bounds.cut_at_more_titley_title(sector_title_line)
            if next_lessons_learned['total_y'] < sector_bounds['total_y'].max():
                
                # Get the sectors after the given sector_idx
                next_sector_idxs = self.get_idxs_after_idx(
                    idx=sector_idx,
                    idxs=sector_idxs
                )

                # If no sectors, return the lessons learned section
                if next_sector_idxs.empty:
                    return next_lessons_learned_distance
                
                # If lessons learned section is nearer than the section, return it
                else:
                    next_sector = next_sector_idxs.iloc[0]
                    if next_lessons_learned['total_y'] < next_sector['total_y']:
                        return next_lessons_learned_distance


    def get_idxs_after_idx(self, idx, idxs):
        """
        Get idxs after a given idx, comparing by total_y.

        Parameters
        ----------
        idx : int (required)
            Index to get the next lessons learned section after.
        """
        # Get y position of idx and idxs
        idx_position = self.document.lines.loc[idx]
        idxs_positions = self.document.lines.loc[list(idxs)]
        
        # Get the lessons learned which are after the idx - compare vertical position
        idxs_after = idxs_positions.loc[
            idxs_positions['total_y'] > idx_position['total_y']
        ].sort_values(by=['total_y'], ascending=True)

        return idxs_after


    def get_lessons_learned_section_lines(self, title):
        """
        Get the lines of a lessons learned section given the index of the title.
        """
        # Lessons learned section should only contain text lower than the title
        section_lines = self.document.lines.loc[
            self.document.lines['total_y'] > title['total_y']
        ]

        # Lessons learned section must end before the next lessons learned section
        next_lessons_learned = self.lessons_learned_titles.loc[
            self.lessons_learned_titles['total_y'] > title['total_y']
        ]
        if not next_lessons_learned.empty:
            next_lessons_learned_y = next_lessons_learned.sort_values(by=['total_y'], ascending=True).iloc[0]['total_y']
            section_lines = section_lines.loc[section_lines['total_y'] < next_lessons_learned_y]

        # Lessons learned section must end before the next sector_title
        if self.sectors_lessons_learned_map:
            next_sector_titles = self.document.sector_titles.loc[self.sectors_lessons_learned_map.keys()]
            next_sector_titles = next_sector_titles.loc[
                next_sector_titles['total_y'] > title['total_y']
            ]
            if not next_sector_titles.empty:
                next_sector_title_y = next_sector_titles.sort_values(by=['total_y'], ascending=True).iloc[0]['total_y']
                section_lines = section_lines.loc[section_lines['total_y'] < next_sector_title_y]

        # Cut the lessons learned section at the next title
        section_lines = section_lines.cut_at_more_titley_title(
            title=title
        )

        return section_lines