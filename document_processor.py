from ast import literal_eval
from functools import cached_property
import yaml
import numpy as np
import pandas as pd
from utils import is_text_title, strip_non_alpha, strip_filler_words


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
        # Remove photo blocks
        self.remove_photo_blocks()

        # Remove page numbers
        self.remove_page_numbers()

        # Add more info
        self.lines['double_fontsize_int'] = (self.lines['size'].astype(float)*2).round(0).astype('Int64')
        self.lines['style'] = self.lines['font'].astype(str)+', '+self.lines['double_fontsize_int'].astype(str)+', '+lines['color'].astype(str)+', '+self.lines['highlight_color'].astype(str)


    def remove_photo_blocks(self):
        """
        Remove blocks which look like photos from the document lines.
        """
        self.lines['block_page'] = self.lines['block_number'].astype(str)+'_'+self.lines['page_number'].astype(str)
        photo_blocks = self.lines.loc[self.lines['text'].astype(str).str.contains('Photo: '), 'block_page'].unique()
        self.lines = self.lines.loc[~self.lines['block_page'].isin(photo_blocks)].drop(columns=['block_page'])


    def remove_page_numbers(self):
        """
        Remove page numbers from page headers and footers.
        """
        # Loop through pages
        for page in self.lines['page_number'].unique():
            page = self.lines.loc[self.lines['page_number']==page]

            # Get document first and last lines
            first_block = page.loc[page['block_number']==page['block_number'].min()]
            first_line = first_block.loc[first_block['line_number']==first_block['line_number'].min()]
            last_block = page.loc[page['block_number']==page['block_number'].max()]
            last_line = last_block.loc[last_block['line_number']==last_block['line_number'].max()]

            # Assume that if the line starts with "page", it is page number
            check_lines = ([first_line, last_line] if first_line.equals(last_line) else [first_line])
            for line_spans in check_lines:
                line_spans['text'] = line_spans['text'].apply(strip_non_alpha).str.lower()
                line_spans = line_spans.loc[line_spans['text'].notnull()]
                first_text = line_spans.loc[line_spans['span_number'].idxmin(), 'text']
                if strip_non_alpha(first_text).lower().startswith('page'):
                    self.lines.drop(labels=line_spans.index, inplace=True)

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
    def sector_titles(self):
        """
        """
        sector_titles = self.titles.copy()

        # Get a score representing how "sector titley" it is
        sector_titles[['Sector title', 'Sector similarity score']] = sector_titles.apply(
            lambda row: 
                None if row['text']!=row['text'] else \
                pd.Series(
                    self.get_similar_sector(
                        row['text']
                    )
                ), axis=1
            )

        # Filter to only where the score is >= 0.5
        sector_titles = sector_titles.loc[sector_titles['Sector similarity score'] >= 0.5]
        
        return sector_titles


    def get_similar_sector(self, text):
        text_base = strip_non_alpha(text).lower()
        sector_title_texts = yaml.safe_load(open('sectors.yml'))

        # First, check if there is an exact match with the titles
        for sector_name, details in sector_title_texts.items():
            if details is None:
                titles = [sector_name]
            else:
                titles = (details['titles'] if 'titles' in details else [])+[sector_name]
            for title in titles:
                if text_base == strip_non_alpha(title).lower():
                    return sector_name, 1

        # Next, check if the title is any title plus filler words 
        for sector_name, details in sector_title_texts.items():
            if details is None:
                titles = [sector_name]
            else:
                titles = (details['titles'] if 'titles' in details else [])+[sector_name]
            for title in titles:
                if strip_filler_words(text_base) == strip_filler_words(strip_non_alpha(title).lower()):
                    return sector_name, 1

        # Next, check if there is an exact match with any keywords
        for sector_name, details in sector_title_texts.items():
            if details is None:
                keywords = []
            else:
                keywords = (details['keywords'] if 'keywords' in details else [])
            for keyword in keywords:
                if text_base == strip_non_alpha(keyword).lower():
                    return sector_name, 0.9

        # Next, check how many words in the text are covered by each sector and sector keywords
        text_base_words = text_base.split(' ')
        proportion_text_covered_by_sector = {}
        for sector_name, details in sector_title_texts.items():
            if details is None:
                keywords = []
            else:
                keywords = (details['keywords'] if 'keywords' in details else [])
            
            # Extract keywords from string to get overlap proportion
            text_base_without_keywords = text_base
            for keyword in keywords:
                text_base_without_keywords = text_base_without_keywords.replace(keyword, '')
            text_base_without_keywords_words = text_base_without_keywords.split(' ')

            # Remove filler words
            filler_words = ['and', 'the']
            text_base_without_keywords_words = [word for word in text_base_without_keywords_words if (word and (word not in filler_words))]
            text_base_without_filler_worlds = [word for word in text_base_words if (word and (word not in filler_words))]
            number_words_covered = len(text_base_without_filler_worlds) - len(text_base_without_keywords_words)
            if len(text_base_without_filler_worlds) > 0:
                proportion_text_covered_by_sector[sector_name] = number_words_covered/len(text_base_without_filler_worlds)
            else:
                return float('nan')

        max_sector = max(proportion_text_covered_by_sector, key=proportion_text_covered_by_sector.get)
        max_proportion = proportion_text_covered_by_sector[max_sector]

        if max_proportion > 0:
            return max_sector, max_proportion
        

    @cached_property
    def titles(self):
        """
        Get all titles in the documents
        """
        titles = self.lines.dropna(subset=['text'])\
                            .loc[
                                (self.lines['span_number']==0) & 
                                (self.lines['text'].apply(is_text_title))
                            ]
        return titles

    
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
        sector_title_styles['Distance from lessons learned'] = sector_title_styles['Lessons learned covered'].apply(lambda x: np.mean([v-k for k,v in x.items()]) if x else float('nan'))
        
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
                sectors['Distance from lessons learned'] = sectors.apply(lambda row: abs(row['Lessons learned covered'] - row.name), axis=1)

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
        Get the next unmatched lessons learned index after the sector position at sector_idx, unless there is a sector index first (in sector_idxs).
        """
        # Loop through next lessons learned section indexes, and return if before the nearest sector index
        lessons_learned_covered = []
        next_sector_idxs = [i for i in sector_idxs if i > sector_idx]
        next_lessons_learned_idxs = [i for i in self.unmatched_lessons_learned if i > sector_idx]
        if next_lessons_learned_idxs:
            next_lessons_learned_idx = min(next_lessons_learned_idxs)
            if not next_sector_idxs:
                return next_lessons_learned_idx
            elif next_lessons_learned_idx < min(next_sector_idxs):
                return next_lessons_learned_idx


    def styles_are_similar(self, style1, style2):
        # Check if two styles are similar
        if abs(style1["double_fontsize_int"] - style2["double_fontsize_int"]) <= 4:
            if style1["highlight_color"] and style2["highlight_color"]:
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
            lessons_learned_sector_map = {v:k for k,v in sectors_lessons_learned_map.items()}
        
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


    def get_lessons_learned_section_lines(self, idx):
        """
        Get the lines of a lessons learned section given the index of the title.
        """
        section_lines = self.lines.loc[idx:]
        lessons_learned_title = self.lessons_learned_titles.loc[idx]

        # Lessons learned section should only contain text lower than the title
        section_lines = section_lines.loc[~(
            (section_lines["page_number"]==lessons_learned_title["page_number"]) & \
            (section_lines["origin"].apply(literal_eval).str[1] < literal_eval(lessons_learned_title["origin"])[1])
        )]

        # Lessons learned section must end before the next lessons learned section
        following_lessons_learned_titles = [i for i in self.lessons_learned_titles.index if i > idx]
        if following_lessons_learned_titles:
            section_lines = section_lines.loc[:min(following_lessons_learned_titles)-1]

        # Lessons learned section must end before the next sector title
        if self.sectors_lessons_learned_map:
            following_sector_titles = [sector_idx for sector_idx in self.sectors_lessons_learned_map if sector_idx > idx]
            if following_sector_titles:
                section_lines = section_lines.loc[:min(following_sector_titles)-1]

        # Get end of lessons learned section based on font styles
        lessons_learned_text_end = self.get_section_end(
            title=section_lines.iloc[0],
            lines=section_lines.iloc[1:]
        )
        section_lines = section_lines.loc[:lessons_learned_text_end]

        return section_lines


    def get_section_end(self, title, lines):
        """
        Get the end of a section by comparing font properties of the section title to font properties of the section contents.
        """
        # Get title information
        first_line_chars = lines.loc[lines['text'].astype(str).str.contains('[a-zA-Z]')].iloc[0]

        # Round sizes
        title_size = title['double_fontsize_int']
        first_line_size = first_line_chars['double_fontsize_int']

        # Loop through lines
        # Returns index of last element in the section
        previous_idx = 0
        for idx, line in lines.iterrows():

            line_size = line['double_fontsize_int']

            # If line is a page number, continue
            any_letters = [char for char in line['text'].strip() if char.isalpha()]
            if not any_letters:
                continue

            # Next title if text is bigger than the title, or bold
            if line_size > title_size:
                return previous_idx
            elif line_size == title_size:
                if first_line_size < title_size:
                    return previous_idx
                if (title['bold'] and line['bold']) and not first_line_chars['bold']:
                    return previous_idx

            previous_idx = idx
                    
        return lines.index[-1]