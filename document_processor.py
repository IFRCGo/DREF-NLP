from utils import styles_are_similar


class LessonsLearnedProcessor:
    def __init__(self, lessons_learned):
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
        self.style_columns = ['font', 'double_fontsize_int', 'color', 'highlight_color']
        self.lessons_learned = lessons_learned
        self.sectors_lessons_learned_map = None

    
    def get_lessons_learned_sectors(self, sectors):
        """
        """
        # Get the most likely font style of the sector titles
        primary_sector_style = self.match_sectors_by_style(
            sectors=sectors
        )
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
            return self.lessons_learned
        else:
            return [
                idx for idx in self.lessons_learned 
                if idx not in self.sectors_lessons_learned_map.values()
            ]


    def match_sectors_by_style(self, sectors):
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
        
        # Select the largest style that covers most lessons learned sections
        primary_sector_style = sector_title_styles\
            .sort_values(
                by=['Number lessons learned covered', 'double_fontsize_int'],
                ascending=[False, False]
            )\
            .iloc[0]

        # Set the matched lessons learned
        self.sectors_lessons_learned_map = primary_sector_style['Lessons learned covered']
            
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
                        self.sectors_lessons_learned_map.values()
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
        Get the next unmatched lessons learned index after the sector position, unless there is a sector index first.
        """
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
                if is_bold(style1['font']) == is_bold(style2['font']):
                    return True
        return False


    def get_sectors_similar_styles(self, style, sectors):
        return sectors.loc[
            (sectors['style']!=style.name) & 
            sectors.apply(
                lambda row: styles_are_similar(row, style), 
                axis=1
            )
        ]