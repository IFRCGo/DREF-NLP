"""
"""
import numpy as np
from functools import cached_property
import yaml


class LessonsLearnedExtractor:
    def __init__(self):

        self.lessons_learned_title_texts = yaml.safe_load(open('lessons_learned_titles.yml'))


    def get_lessons_learned(self, document):
        """
        Get lessons learned
        """
        self.document = document
        self.sectors_lessons_learned_map = None

        # Match the lessons learned to the sector indexes
        lessons_learned_sector_map = None
        if len(self.lessons_learned_titles) > 1:

            # Get the document sector titles
            sectors_lessons_learned_map = self.get_lessons_learned_sectors(
                sectors=self.document.sector_titles
            )
            lessons_learned_sector_map = {v['idx']:k for k,v in sectors_lessons_learned_map.items()}
        
        # Get the span of each lessons learned section
        lessons_learned = []
        sector_titles_dict = self.document.sector_titles['Sector title'].to_dict()
        sector_similarity_scores_dict = self.document.sector_titles['Sector similarity score'].to_dict()
        for idx, row in self.lessons_learned_titles.iterrows():

            # Get lessons learned section lines, remove title
            section_lines = self.get_lessons_learned_section_lines(idx=idx)

            lessons_learned_details = {
                "title_text": section_lines.iloc[0],
                "title_idx": idx,
                "section_lines": section_lines.iloc[1:],
            }
            # Add section index to lessons learned
            if lessons_learned_sector_map:
                sector_idx = lessons_learned_sector_map.get(idx)                
                lessons_learned_details['sector_idx'] = sector_idx
                lessons_learned_details['sector_title'] = sector_titles_dict.get(sector_idx)
                lessons_learned_details['sector_similarity_score'] = sector_similarity_scores_dict.get(sector_idx)
            
            lessons_learned.append(lessons_learned_details)

        # Remove empty lessons learned sections
        lessons_learned = self.remove_empty_lessons_learned(lessons_learned)

        return lessons_learned


    @cached_property
    def lessons_learned_titles(self):
        """
        Get lessons learned titles
        """
        lessons_learned_titles = self.document.titles.loc[
            self.document.titles['text_base'].isin(self.lessons_learned_title_texts)
        ]
        return lessons_learned_titles


    def remove_empty_lessons_learned(self, lessons_learned):
        """
        Filter the lessons learned sections to remove blank ones.
        """
        empty_texts = ['nothing to report', 'none was reported']

        filtered_lessons_learned = []
        for details in lessons_learned:
            text_content = ' '.join(details['section_lines']['text_base'].tolist())
            if text_content not in empty_texts:
                filtered_lessons_learned.append(details)

        return filtered_lessons_learned

    
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
        # Group the sector estimates into styles
        sector_title_styles = sectors\
            .reset_index()\
            .rename(columns={'index': 'Sector title indexes'})\
            .groupby(['style', 'font', 'double_fontsize_int', 'color', 'highlight_color', 'bold'], dropna=False)\
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
                sectors['Distance from lessons learned'] = sectors['Lessons learned covered'].apply(lambda x: x.get('distance'))

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
                sectors.drop(best_sector.name, inplace=True)


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
        sector_section = self.document.lines.loc[sector_idx:].cut_at_first_title()

        # Get y position of sectors and lessons learned
        sector_idx_position = self.document.lines.loc[sector_idx, ['page_number', 'total_y']]
        sector_idxs_positions = self.document.lines.loc[list(sector_idxs), ['page_number', 'total_y']]
        unmatched_lessons_learned_positions = self.document.lines.loc[self.unmatched_lessons_learned, ['page_number', 'total_y']]
        
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


    def get_lessons_learned_section_lines(self, idx):
        """
        Get the lines of a lessons learned section given the index of the title.
        """
        lessons_learned_title = self.lessons_learned_titles.loc[idx]

        # Lessons learned section should only contain text lower than the title
        section_lines = self.document.lines.loc[
            self.document.lines['total_y'] >= lessons_learned_title['total_y']
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
            next_sector_titles = self.document.sector_titles.loc[self.sectors_lessons_learned_map.keys()]
            next_sector_titles = next_sector_titles.loc[
                next_sector_titles['total_y'] > lessons_learned_title['total_y']
            ]
            if not next_sector_titles.empty:
                next_sector_title_y = next_sector_titles.sort_values(by=['total_y'], ascending=True).iloc[0]['total_y']
                section_lines = section_lines.loc[section_lines['total_y'] < next_sector_title_y]

        # Cut the lessons learned section at the next title
        section_lines = section_lines.cut_at_first_title()

        return section_lines