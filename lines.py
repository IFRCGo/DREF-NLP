"""
"""
from functools import cached_property
import pandas as pd
from utils import colour_diff, is_text_title


class Line(pd.Series):
    @property
    def _constructor(self):
        return Line

    @property
    def _constructor_expanddim(self):
        return Lines


    def is_similar_style(self, line2):
        # Check if two styles are similar
        if abs(self["double_fontsize_int"] - line2["double_fontsize_int"]) <= 6:

            # Check if fonts are similar
            font = self['font'].split('-')[0].lower()
            other_font = line2['font'].split('-')[0].lower()
            similar_fonts = [['arial', 'calibri']]
            common_fonts = [fonts for fonts in similar_fonts if ((font in fonts) and (other_font in fonts))]
            if (font == other_font) or common_fonts:

                # Check if colours and bold are similar
                if colour_diff(self["highlight_color"], line2["highlight_color"]) < 0.1:
                    if colour_diff(self['color'], line2['color']) < 0.1:
                        if self['bold'] == line2['bold']:
                            return True
        
        return False


    def more_titley(self, title, nontitle):
        """
        Check if line is more titley than title.
        Use nontitle to check what a title looks like.
        Don't consider titles in images as titles.
        """
        # Don't consider titles in images as titles
        if self['img']:
            return False

        # If line is larger, it is more titley
        if self['double_fontsize_int'] > title['double_fontsize_int']:
            return True

        if self['double_fontsize_int'] == title['double_fontsize_int']:
            
            # If same size but nontitle is smaller, it is more titley
            if nontitle['double_fontsize_int'] < title['double_fontsize_int']:
                return True

            # If same size but nontitle is not bold
            if self['bold'] and not nontitle['bold']:
                return True

        return False


class Lines(pd.DataFrame):

    @property
    def _constructor(self):
        return Lines

    @property
    def _constructor_sliced(self):
        return Line


    def sort_blocks_by_y(self):
        """
        Sort blocks in the lines by the y position in the document.
        """
        lines = self.copy()
        lines['page_block'] = lines['page_number'].astype(str)+'_'+lines['block_number'].astype(str)
        block_y = lines.groupby(['page_block'])['total_y'].min().to_dict()
        lines['order'] = lines['page_block'].map(block_y)
        lines = lines.sort_values(by=['order', 'line_number', 'span_number']).drop(columns=['page_block', 'order'])

        return lines


    def combine_spans_same_style(self):
        """
        """
        lines = self.copy()
        lines['text'] = lines\
            .groupby(['page_number', 'block_number', 'line_number', 'style'])['text']\
            .transform(lambda x: ' '.join([txt for txt in x if txt==txt]))
        lines = lines.drop_duplicates(subset=['page_number', 'block_number', 'line_number', 'style'])

        return lines


    def starts_with_page_label(self):
        """
        """
        # Get the first text containing alphanumeric characters
        self = self.dropna(subset=['text_base']).sort_values(by=['line_number', 'span_number'])
        first_span = self.iloc[0]

        # If the the first word is page, assume page label
        if first_span['text_base'].startswith('page'):
            return True
        
        # If only a single number, assume page label
        if len(self)==1 and first_span['text_base'].isdigit():
            return True

        return False


    def starts_with_reference(self):
        """
        Remove references denoted by a superscript number in document headers and footers.
        """
        # Get the first text containing alphanumeric characters
        self = self.dropna(subset=['text_base']).sort_values(by=['line_number', 'span_number'])
        first_span = self.iloc[0]

        # If the first span is small and a number
        if len(self)==1:
            if first_span['text_base'].isdigit():
                return True
        elif len(self)>1:
            if first_span['text_base'].isdigit():
                if (self.iloc[1]['size'] - first_span['size']) >= 1:
                    return True

        return False


    @cached_property
    def titles(self):
        """
        Get all titles in the documents
        """        
        # Get all lines starting with capital letter
        titles = self.dropna(subset=['text'])\
                     .loc[
                         (self['span_number']==0) & 
                         (self['text'].apply(is_text_title))
                     ]
        
        # Assume that the body text is most common, and drop titles not bigger than this
        body_style = self['style'].value_counts().idxmax()
        titles = titles.loc[titles['style']!=body_style]
        
        return titles


    def cut_at_first_title(self):
        """
        Cut the section lines at the first title.
        Assume that the first line is the title of the section.
        """
        # Assume that the title is the first line of the section
        title = self.iloc[0]
        section_content = self.iloc[1:]

        # Get title information
        first_section_line_with_chars = section_content.loc[section_content['text'].astype(str).str.contains('[a-zA-Z]')].iloc[0]

        # Filter to only consider titles in section
        section_titles = section_content.loc[section_content.index.isin(
            [idx for idx in section_content.index if idx in self.titles.index]
        )].sort_values(by=['total_y'])
        
        # Get the next title which is more titley than the title
        more_titley = None
        for idx, line in section_titles.iterrows():
            if line.more_titley(title, first_section_line_with_chars):
                more_titley = line
                break

        # Cut the section at the title index found
        if more_titley is None:
            return self

        more_titley_line = self.loc[
            (self['page_number']==more_titley['page_number']) & 
            (self['block_number']==more_titley['block_number']) & 
            (self['line_number']==more_titley['line_number'])
        ]

        return self.loc[self['total_y'] < more_titley_line['total_y'].min()]