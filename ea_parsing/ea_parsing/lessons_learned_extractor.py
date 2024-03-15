"""
"""
from functools import cached_property
import numpy as np
import pandas as pd
import ea_parsing.definitions
from ea_parsing.utils import generate_sentence_variations


class ChallengesLessonsLearnedExtractor:
    def __init__(self, section_type):
        """
        Extract sections in the Emergency Appeal document based on title texts, and associate with a sector.
        Only works for "Challenges" or "Lessons Learned".
        """
        # Check that section_type is "challenges" or "lessons_learned"
        self.section_type = str(section_type).lower().strip()
        if section_type not in ['challenges', 'lessons_learned']:
            raise ValueError("'section_type' must be 'challenges' or 'lessons_learned'")

    @cached_property
    def title_texts(self):
        """
        Get the title texts, including abbreviations.
        """
        # Get title definitions and abbreviations
        section_titles_details = ea_parsing.definitions.LESSONS_LEARNED_TITLES

        # Get all possible title variations, considering abbreviations
        title_texts = {'lessons_learned': [], 'challenges': []}
        for section_type in title_texts:
            section_titles = section_titles_details.get(f'{section_type}_titles')
            for title in section_titles:
                title_texts[section_type] += generate_sentence_variations(
                    sentence=title,
                    abbreviations=section_titles_details['abbreviations']
                )

        return title_texts

    @cached_property
    def section_titles(self):
        """
        Get section titles
        """
        section_titles = self.document.titles.loc[
            self.document.titles['text_base']
                .str.replace(r'[^A-Za-z ]+', ' ', regex=True)
                .str.strip()
                .isin(self.title_texts[self.section_type])
        ]
        return section_titles

    @property
    def number_of_sections(self):
        """
        Total number of sections in the document.
        """
        return int(len(self.section_titles))

    def get_sections(self, document):
        """
        Get sections
        """
        self.document = document
        self.sectors_sections_map = None

        # Get a map between the document sectors and the sections
        sectors_sections_map = self.get_section_sectors(
            sectors=self.document.sector_titles
        )

        # Reverse the map
        section_sector_map = {}
        if sectors_sections_map:
            section_sector_map = {
                section_idx: sector_idx
                for sector_idx, section_idxs
                in sectors_sections_map.items()
                for section_idx in section_idxs
            }

        # Get the span of each section
        sections = []
        sector_titles_dict = self.document.sector_titles['Sector title'].to_dict()
        sector_similarity_scores_dict = self.document.sector_titles['Sector similarity score'].to_dict()
        for idx, row in self.section_titles.iterrows():

            # Get section title and details
            select_columns = [
                'text',
                'text_base',
                'style',
                'size',
                'page_number',
                'block_number',
                'line_number',
                'span_number',
                'total_y',
                'origin_x'
            ]
            section_title = self.section_titles.loc[idx]
            title_details = section_title[select_columns].to_dict()
            title_details['idx'] = idx

            # Get section content, check if empty
            section_content = self.get_section_lines(
                title=section_title
            )
            if section_content.is_nothing:
                section_content = pd.DataFrame()

            # Add title, content, and sector details to sections
            sector_idx = section_sector_map.get(idx)
            section_details = {
                'title': title_details,
                'sector_title': sector_titles_dict.get(sector_idx),
                'sector_idx': None if sector_idx is None else int(sector_idx),
                'sector_similarity_score': sector_similarity_scores_dict.get(sector_idx),
                'content': section_content[[
                    col for col in select_columns
                    if col in section_content.columns
                    ]].reset_index().to_dict('records')
            }
            sections.append(section_details)

        return sections

    def get_section_sectors(self, sectors):
        """
        Get a map between sector title IDs and section title IDs.
        """
        if sectors.empty:
            return

        # Get the most likely font style of the sector titles
        primary_sector_style = self.get_primary_sector_style(
            sectors=sectors
        )
        self.sectors_sections_map = {
            sector_idx: [section_details['idx']]
            for sector_idx, section_details
            in primary_sector_style['Sections covered'].items()
        }

        # If only one section, and after all sectors, set to no sector
        sector_titles_primary_style = sectors.loc[sectors['style'] == primary_sector_style.name]
        if (
            (self.number_of_sections <= 1) and
            (self.section_titles['total_y'].max() >= sector_titles_primary_style['total_y'].max())
        ):
            self.sectors_sections_map = {}
            return self.sectors_sections_map

        # Get closest sectors to match unmatched sections
        if self.unmatched_sections:
            self.match_sectors_by_distance(
                sectors=sectors.loc[sectors['style'] != primary_sector_style.name]
            )

        # If there are still unmatched sections, match to the closest sector
        for section_idx in self.unmatched_sections:
            sectors_before_section = self.get_idxs_before_idx(
                idx=section_idx,
                idxs=self.sectors_sections_map.keys()
            )
            if not sectors_before_section.empty:
                closest_sector_before_section = sectors_before_section.iloc[-1]
                sector_idx = closest_sector_before_section.name
                if sector_idx in self.sectors_sections_map:
                    self.sectors_sections_map[sector_idx].append(section_idx)
                else:
                    self.sectors_sections_map[sector_idx] = [section_idx]

        return self.sectors_sections_map

    @property
    def unmatched_sections(self):
        if self.sectors_sections_map is None:
            return self.section_titles.index.tolist()
        else:
            matched_sections = [idx for idxs in self.sectors_sections_map.values() for idx in idxs]
            return [
                idx for idx in self.section_titles.index.tolist()
                if idx not in matched_sections
            ]

    def get_primary_sector_style(self, sectors):
        """
        Match sections to sectors by getting the style which matches most sectors.
        """
        if sectors.empty:
            return

        # Group the sector estimates into styles
        sector_title_styles = sectors\
            .reset_index()\
            .rename(columns={'index': 'Sector title indexes'})\
            .groupby(['style', 'double_fontsize_int'], dropna=False)\
            .agg({
                'text': tuple,
                'Sector title': tuple,
                'Sector title indexes': tuple,
                'Sector similarity score': 'mean'
            })\
            .reset_index()\
            .set_index('style')

        # Get which sector idxs correspond to sections
        sector_title_styles['Sections covered'] = sector_title_styles['Sector title indexes'].apply(
            lambda sector_idxs: {
                sector_idx: self.get_sections_covered_by_sector(sector_idx, sector_idxs)
                for sector_idx in sector_idxs
                if self.get_sections_covered_by_sector(sector_idx, sector_idxs)
            }
        )

        # Drop repeat sections, keep sector title which is closest
        sector_title_styles['Sections covered'] = sector_title_styles['Sections covered'].apply(
            lambda results:
                pd.DataFrame(index=results.keys(), data=results.values())
                .sort_values(by='distance', ascending=True)
                .drop_duplicates(subset='idx', keep='first')
                .to_dict('index')
                if results
                else results
        )

        # Get total and distance from section
        sector_title_styles['Number sections covered'] = sector_title_styles['Sections covered'].apply(
            lambda x: x if x is None else len(x)
        )
        sector_title_styles['Distance from section'] = sector_title_styles['Sections covered'].apply(
            lambda x: float(
                np.mean([v['distance'] for k, v in x.items()])
                if x
                else float('nan')
            )
        )

        # Select the largest style that covers most sections
        primary_sector_style = sector_title_styles\
            .sort_values(
                by=['Number sections covered', 'double_fontsize_int', 'Distance from section'],
                ascending=[False, False, True]
            )\
            .iloc[0]

        return primary_sector_style

    def match_sectors_by_distance(self, sectors):
        """
        Match sections to given sectors by distance between section and sectors.
        """
        # Get other possible sector titles: texts with similar style, that are not the selected style
        while self.unmatched_sections and not sectors.empty:

            sectors = sectors.copy()
            sectors['Sections covered'] = sectors\
                .index\
                .to_series()\
                .apply(
                    lambda sector_idx: self.get_sections_covered_by_sector(
                        sector_idx,
                        self.sectors_sections_map.keys()
                    )
                )
            sectors.dropna(subset=['Sections covered'], inplace=True)

            if not sectors.empty:

                # Get distance between sector title and section
                sectors['Distance from section'] = sectors['Sections covered'].apply(lambda x: x.get('distance'))

                # Get the titles which are closest to the section
                best_sectors = sectors\
                    .sort_values(
                        by=['Sector similarity score', 'Distance from section'],
                        ascending=[False, True]
                    )\
                    .drop_duplicates(subset=['Sector title'])
                if not best_sectors.empty:
                    best_sector = best_sectors.iloc[0]
                    self.sectors_sections_map[best_sector.name] = [best_sector['Sections covered']['idx']]
                    sectors.drop(best_sector.name, inplace=True)

    def get_sections_covered_by_sector(self, sector_idx, sector_idxs):
        """
        Get sections covered by the sector at sector_idx, given the other sectors at sector_idxs.
        """
        # Get the section after the sector_idx
        next_section_idxs = self.get_idxs_after_idx(
            idx=sector_idx,
            idxs=self.unmatched_sections
        )
        if next_section_idxs.empty:
            return

        # Get distance between the sector title and the next section
        sector_title_line = self.document.lines.loc[sector_idx]
        next_section = next_section_idxs.iloc[0]
        next_section_distance = {
            "idx": next_section.name,
            "distance": next_section['total_y'] - sector_title_line['total_y']
        }

        # Section must be before the end of the sector section
        # If only one section, impose stricter rule: sector section ends at next titley title
        sector_bounds = self.document.lines.loc[sector_idx:]
        if self.number_of_sections <= 1:
            sector_bounds = sector_bounds.iloc[1:].cut_at_more_titley_title(sector_title_line)

        if next_section['total_y'] < sector_bounds['total_y'].max():

            # Get the sectors after the given sector_idx
            next_sector_idxs = self.get_idxs_after_idx(
                idx=sector_idx,
                idxs=sector_idxs
            )

            # If no sectors after the section, return the section
            if next_sector_idxs.empty:
                return next_section_distance

            # If section is nearer than the next sector, return it
            else:
                next_sector = next_sector_idxs.iloc[0]
                if next_section['total_y'] < next_sector['total_y']:
                    return next_section_distance

    def get_idxs_after_idx(self, idx, idxs):
        """
        Get idxs after a given idx, comparing by total_y.

        Parameters
        ----------
        idx : int (required)
            Index to get the next section after.
        """
        # Get y position of idx and idxs
        idx_position = self.document.lines.loc[idx]
        idxs_positions = self.document.lines.loc[list(idxs)]

        # Get the sections which are after the idx - compare vertical position
        idxs_after = idxs_positions.loc[
            idxs_positions['total_y'] > idx_position['total_y']
        ].sort_values(by=['total_y'], ascending=True)

        return idxs_after

    def get_idxs_before_idx(self, idx, idxs):
        """
        Get idxs before a given idx, comparing by total_y.

        Parameters
        ----------
        idx : int (required)
            Index to get the next section after.
        """
        # Get y position of idx and idxs
        idx_position = self.document.lines.loc[idx]
        idxs_positions = self.document.lines.loc[list(idxs)]

        # Get the sections which are after the idx - compare vertical position
        idxs_before = idxs_positions.loc[
            idxs_positions['total_y'] < idx_position['total_y']
        ].sort_values(by=['total_y'], ascending=True)

        return idxs_before

    def get_section_lines(self, title):
        """
        Get the lines of a section given the index of the title.
        """
        # Section should only contain text lower than the title
        section_lines = self.document.lines.loc[
            self.document.lines['total_y'] >= title['total_y']
        ]
        section_lines = section_lines.drop(title.name)

        # Section must end before the next section
        next_section = self.section_titles.loc[
            self.section_titles['total_y'] > title['total_y']
        ]
        if not next_section.empty:
            next_section_y = next_section.sort_values(by=['total_y'], ascending=True).iloc[0]['total_y']
            section_lines = section_lines.loc[section_lines['total_y'] < next_section_y]

        # Section must end before the next "Lessons Learned" or "Challenges" section
        lessons_learned_challenges_titles = self.document.titles.loc[
            self.document.titles['text_base']
                .str.replace(r'[^A-Za-z ]+', ' ', regex=True)
                .str.strip()
                .isin(
                    self.title_texts['lessons_learned'] +
                    self.title_texts['challenges']
                )
        ]
        lessons_learned_challenges_titles_after_section = lessons_learned_challenges_titles.drop(title.name).loc[
            lessons_learned_challenges_titles['total_y'] > title['total_y']
        ]
        if not lessons_learned_challenges_titles_after_section.empty:
            section_lines = section_lines.loc[
                section_lines['total_y'] < lessons_learned_challenges_titles_after_section['total_y'].min()
            ]

        # Section must end before the next sector_title
        if self.sectors_sections_map:

            # Get all sector titles with the same styles as the section sector titles
            section_sector_styles = self.document.lines.loc[
                self.sectors_sections_map.keys(), 'style'
            ].unique()
            all_sector_titles = self.document.sector_titles.loc[
                self.document.sector_titles['style'].isin(
                    [
                        style
                        for style in section_sector_styles
                        if style != self.document.lines.body_style
                    ]
                )
            ]

            # End section before next sector title
            next_sector_titles = all_sector_titles.loc[
                all_sector_titles['total_y'] > title['total_y']
            ]
            if not next_sector_titles.empty:
                next_sector_title_y = next_sector_titles.sort_values(by=['total_y'], ascending=True).iloc[0]['total_y']
                section_lines = section_lines.loc[section_lines['total_y'] < next_sector_title_y]

        # Cut the section at the next title
        section_lines = section_lines.cut_at_more_titley_title(
            title=title
        )

        return section_lines
