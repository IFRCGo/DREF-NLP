"""
"""
from functools import cached_property
import pandas as pd
from ea_parsing.utils import colour_diff, is_text_title


class Line(pd.Series):
    @property
    def _constructor(self):
        return Line

    @property
    def _constructor_expanddim(self):
        return Lines


    def is_similar_style(self, line2):
        # Size tolerance greater if highlight_colour
        size_tolerance = 6 if not self['highlight_color'] else 100

        # Check if sizes are similar
        if abs(self["double_fontsize_int"] - line2["double_fontsize_int"]) <= size_tolerance:

            # Check if fonts are similar
            font = self['font'].split('-')[0].lower()
            other_font = line2['font'].split('-')[0].lower()
            similar_fonts = [['arial', 'calibri', 'opensans', 'montserrat']]
            common_fonts = [fonts for fonts in similar_fonts if ((font in fonts) and (other_font in fonts))]
            if (font == other_font) or common_fonts:

                # Check if colours and bold are similar
                highlight_color1 = self['highlight_color'] if self['highlight_color'] is not None else "#ffffff"
                highlight_color2 = line2['highlight_color'] if line2['highlight_color'] is not None else "#ffffff"
                if colour_diff(highlight_color1, highlight_color2) < 0.2:

                    color1 = self['color'] if self['color'] is not None else "#000000"
                    color2 = line2['color'] if line2['color'] is not None else "#000000"
                    if colour_diff(color1, color2) < 0.2:
                        
                        if self['bold'] == line2['bold']:
                            return True
        
        return False


    def more_titley(self, title, nontitle):
        """
        Check if line is more titley, or just as titley, as title.
        Use nontitle to check what a title looks like.
        Don't consider titles in images as titles.
        """
        # Don't consider titles in images as titles
        if self['img']:
            return False

        # If line is larger, it is more titley
        if self['double_fontsize_int'] > max(title['double_fontsize_int'], nontitle['double_fontsize_int']):
            return True

        if self['double_fontsize_int'] == title['double_fontsize_int']:

            # Bolder = more titley
            if title['bold'] and not self['bold']:
                return False
            if not title['bold'] and self['bold']:
                return True
            
            # Same boldness, uppercase = more titley
            if title['text'].isupper() and not self['text'].isupper():
                return False
            if self['text'].isupper() and not title['text'].isupper():
                return True

            # Same boldness and case, compare with nontitle
            if title['double_fontsize_int'] > nontitle['double_fontsize_int']:
                return True
            if title['bold'] and not nontitle['bold']:
                return True

        return False


class Lines(pd.DataFrame):
    def __init__(self, *args, **kwargs):
        super(Lines,  self).__init__(*args, **kwargs)
        
        if 'size' in self.columns:
            self['double_fontsize_int'] = (self['size'].astype(float)*2).round(0).astype('Int64')
        if ('font' in self.columns) and ('double_fontsize_int' in self.columns) and ('color' in self.columns) and ('highlight_color' in self.columns):
            self['style'] = self['font'].str.lower().str.split(pat='-', n=1).str[-1].replace({'boldmt': 'bold'})+', '+\
                            self['double_fontsize_int'].astype(str)+', '+\
                            self['color'].astype(str)+', '+\
                            self['highlight_color'].astype(str)


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
        lines = lines.sort_values(by=['order', 'total_y']).drop(columns=['page_block', 'order'])

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


    def combine_bullet_spans(self):
        """
        Sometimes, bullet points are listed as separate lines than the text which follows them.
        Combine these onto the same line, with different span numbers.
        """
        lines = self.copy()

        # Get bullets: span zero, bullet character
        bullet_chars = ['•']
        bullets = lines.loc[
            (lines['text'].str.strip().isin(bullet_chars)) &
            (lines['span_number']==0)
        ]
        
        # Loop through bullets and put bullet item text on the same line_number
        for i, bullet in bullets.iterrows():
            bullet_block = lines.loc[
                (lines['page_number']==bullet['page_number']) &
                (lines['block_number']==bullet['block_number'])
            ]
            bullet_line = bullet_block.loc[
                (lines['line_number']==bullet['line_number'])
            ]
            text_at_bullet_level = bullet_block.loc[
                (lines['line_number']!=bullet['line_number']) &
                (lines['span_number']==0) &
                (lines['total_y']==bullet['total_y'])
            ]
            if not text_at_bullet_level.empty:
                first_text_at_bullet_level = text_at_bullet_level.index[0]
                lines.loc[first_text_at_bullet_level, 'line_number'] = bullet['line_number']
                lines.loc[first_text_at_bullet_level, 'span_number'] = bullet_line['span_number'].max() + 1

        return lines


    def is_page_label(self):
        """
        Check if a block of lines are a page label.
        """
        # Return if no alphanumeric characters in text block
        lines = self.dropna(subset=['text_base']).sort_values(by=['line_number', 'span_number'])
        if lines.empty:
            return False

        # If the the first word is page, assume page label
        lines_with_chars = lines.loc[lines['text_base'].astype(str).str.contains('[a-z]')]
        if not lines_with_chars.empty:
            if lines_with_chars.iloc[0]['text_base'].startswith('page'):
                return True
        
        # If only a single number, assume page label
        if len(lines)==1 and lines.iloc[0]['text_base'].isdigit():
            return True

        return False


    def is_reference(self):
        """
        Remove references denoted by a superscript number in document headers and footers.
        """
        # Get the first text containing alphanumeric characters
        self = self.dropna(subset=['text_base']).sort_values(by=['line_number', 'span_number'])
        if self.empty:
            return False

        # If the first span is small and a number
        first_span = self.iloc[0]
        if len(self)==1:
            if first_span['text_base'].isdigit():
                return True
        elif len(self)>1:
            if first_span['text_base'].isdigit():
                if (self.iloc[1]['size'] - first_span['size']) >= 1:
                    return True

        return False


    @cached_property
    def is_nothing(self):
        """
        Check if the lines only contain placeholders for nothing.
        """
        nothing_texts = ['nothing to report', 'none was reported', 'none reported', 'na', 'n a', 'none', 'not applicable']
        text_content = ' '.join(self['text_base'].astype(str).tolist()).strip()
        if (not text_content) or (text_content in nothing_texts):
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

        return titles


    @cached_property
    def body_style(self):
        return self['style'].value_counts().idxmax()
        

    @cached_property
    def headings(self):
        """
        Filter titles to greater than body text.
        """
        # Assume that the body text is most common, and drop titles not bigger than this
        headings = self.titles.loc[self.titles['style']!=self.body_style]
        
        return headings


    def cut_at_more_titley_title(self, title):
        """
        Cut the section lines at the first title that is more titley, or just as titley, as title.
        Assume that the first line is the title of the section.
        """
        # Get title information
        lines_with_chars = self.loc[self['text'].astype(str).str.contains('[a-zA-Z]')]
        if lines_with_chars.empty:
            return self
        first_section_line_with_chars = lines_with_chars.iloc[0]

        # Filter to only consider titles in section
        section_titles = self.loc[self.index.isin(
            [idx for idx in self.index if idx in self.titles.index]
        )].sort_values(by=['total_y'])
        
        # Get the next title which is more titley than the title
        more_titley = None
        for idx, line in section_titles.iterrows():
            if line.more_titley(title, first_section_line_with_chars):
                more_titley = line
                break

        # Cut the section at the minimum y position of the more_titley line
        if more_titley is None:
            return self

        more_titley_line = self.loc[
            (self['page_number']==more_titley['page_number']) & 
            (self['block_number']==more_titley['block_number']) & 
            (self['line_number']==more_titley['line_number'])
        ]

        return self.loc[self['total_y'] < more_titley_line['total_y'].min()]