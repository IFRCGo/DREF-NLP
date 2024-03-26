"""
"""
import re
from functools import cached_property
import pandas as pd
import ea_parsing.definitions
from ea_parsing import utils


class Line(pd.Series):
    @property
    def _constructor(self):
        return Line

    @property
    def _constructor_expanddim(self):
        return Lines

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

    def is_sentence_end(self):
        """
        Consider sentence end if ends with full stop, question mark, or exclamation mark.
        """
        sentence_enders = ['.', '?', '!']
        exceptions = ['e.g.', 'i.e.']

        text = str(self['text']).strip().lower()
        if text:

            # Check that the text does not end with an exception
            for exception in exceptions:
                if text[-len(exception):] == exception:
                    return False

            # If ends with sentence ender, consider sentence ended
            if text[-1] in sentence_enders:
                return True

        return False

    def is_sentence_start(self):
        """
        Consider sentence start if the first letter is uppercase.
        Account for letters as bullet items, e.g. a), b., etc.
        """
        text = utils.remove_bullet(self.copy()['text'])
        alphanumeric = re.sub(r'[^A-Za-z0-9 ]+', ' ', text).strip()
        if alphanumeric:
            first_char = alphanumeric[0]
            if first_char.isalpha():
                if first_char.isupper():
                    return True
                else:
                    return False
            else:
                return

        return False


class Lines(pd.DataFrame):
    def __init__(self, *args, **kwargs):
        super(Lines,  self).__init__(*args, **kwargs)

        if 'size' in self.columns:
            if 'double_fontsize_int' not in self.columns:
                self['double_fontsize_int'] = (self['size'].astype(float)*2).round(0).astype('Int64')
        if (
            ('font' in self.columns) and
            ('double_fontsize_int' in self.columns) and
            ('color' in self.columns) and
            ('highlight_color' in self.columns)
        ):
            self['style'] = self['font'].str.lower().str.split(pat='-', n=1).str[-1].replace({'boldmt': 'bold'})+', ' +\
                            self['double_fontsize_int'].astype(str)+', ' +\
                            self['color'].astype(str)+', ' +\
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

    def merge_inline_text(self, exclude_texts=None):
        """
        Sometimes there is text of a different style, e.g. bold, that is inline in a paragraph.
        Merge this text with the other lines.
        """
        lines = self.copy()

        # Don't merge rows which have text in exclude_texts (ignoring case etc)
        lines['ignore'] = False
        if exclude_texts is not None:
            exclude_texts = [utils.remove_filler_words(utils.strip_non_alphanumeric(item)) for item in exclude_texts]
            lines['text_base'] = lines['text']\
                .str.replace(r'[^A-Za-z0-9 ]+', ' ', regex=True)\
                .str.replace(' +', ' ', regex=True)\
                .str.lower()\
                .str.strip()
            exclude_indexes = lines.loc[
                lines['text_base']
                .str.replace(r'[^A-Za-z ]+', ' ', regex=True)
                .str.strip()
                .apply(utils.remove_filler_words)
                .isin(exclude_texts)
            ].index
            lines.loc[exclude_indexes, 'ignore'] = True
            lines.loc[
                pd.Series(lines.index).shift(1).isin(exclude_indexes),
                'ignore'
            ] = True

        # To be considered joined to the previous item, the item must be
        # to the right (because of reading left to right), and must be close horizontally
        lines['h_gap'] = lines['bbox_x1'] - lines['bbox_x2'].shift(1).fillna(0)
        lines['h_group'] = True
        lines.loc[
            (lines['page_number'] == lines['page_number'].shift(1).fillna(0)) &
            (lines['block_number'] == lines['block_number'].shift(1).fillna(0)) &
            (lines['line_number'] == lines['line_number'].shift(1).fillna(0)) &
            ((lines['total_y'] - lines['total_y'].shift(1).fillna(0)).abs() < 2) &
            (lines['double_fontsize_int'] == lines['double_fontsize_int'].shift(1).fillna(0)) &
            (lines['span_number'] != 0) &
            (lines['h_gap'] < 10) & (lines['h_gap'] > 0) &
            ~lines['ignore'],
            'h_group'
        ] = False
        lines['h_group'] = lines['h_group'].cumsum()

        # Combine row texts and keep the first element from other columns
        lines['text'] = lines['text'].fillna('')
        agg_funcs = {
            'index': 'min',
            'text': lambda x: ' '.join(x.astype(str)),
            'span_number': 'min',
            'origin_x': 'min',
            'bbox_x1': 'min',
            'bbox_y1': 'min',
            'bbox_x2': 'max',
            'bbox_y2': 'max'
        }
        agg_funcs = {
            **agg_funcs,
            **{col: 'first' for col in lines if col not in agg_funcs}
        }
        lines = lines\
            .reset_index()\
            .groupby('h_group')\
            .agg(agg_funcs)\
            .drop(columns=['h_gap', 'h_group'])\
            .set_index('index')

        return lines

    def combine_spans_same_style(self):
        """
        """
        lines = self.copy()
        lines['text'] = lines\
            .groupby(['page_number', 'block_number', 'line_number', 'style'])['text']\
            .transform(lambda x: ' '.join([txt for txt in x if txt == txt]))
        lines = lines.drop_duplicates(subset=['page_number', 'block_number', 'line_number', 'style', 'text'])

        return lines

    def combine_bullet_spans(self):
        """
        Sometimes, bullet points are listed as separate lines than the text which follows them.
        Combine these onto the same line, with different span numbers.
        """
        lines = self.copy()

        # Get bullets: span zero, bullet character
        bullets = lines.loc[
            (lines['text'].str.strip().isin(ea_parsing.definitions.BULLETS)) &
            (lines['span_number'] == 0)
        ]

        # Loop through bullets and put bullet item text on the same line_number
        for i, bullet in bullets.iterrows():
            bullet_block = lines.loc[
                (lines['page_number'] == bullet['page_number']) &
                (lines['block_number'] == bullet['block_number'])
            ]
            bullet_line = bullet_block.loc[
                (lines['line_number'] == bullet['line_number'])
            ]
            text_at_bullet_level = bullet_block.loc[
                (lines['line_number'] != bullet['line_number']) &
                (lines['span_number'] == 0) &
                (lines['total_y'] == bullet['total_y'])
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
        if len(lines) == 1 and lines.iloc[0]['text_base'].isdigit():
            return True

        # If only contains "page" and number, assume page label
        combined_text_chars = ' '.join(lines_with_chars['text_base'].dropna().to_list())
        combined_text_chars_no_numbers = re.sub(r'[0-9]', '', combined_text_chars)
        if not combined_text_chars_no_numbers.replace('page', '').strip():
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
        if len(self) == 1:
            if first_span['text_base'].isdigit():
                return True
        elif len(self) > 1:
            if first_span['text_base'].isdigit():
                if (self.iloc[1]['size'] - first_span['size']) >= 1:
                    return True

        return False

    @cached_property
    def is_nothing(self):
        """
        Check if the lines only contain placeholders for nothing.
        """
        nothing_texts = [
            'nothing to report',
            'none was reported',
            'none reported',
            'na',
            'n a',
            'none',
            'not applicable',
            'no significant details to report'
        ]
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
                         (self['span_number'] == 0) &
                         (self['text'].apply(utils.is_text_title))
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
        headings = self.titles.loc[self.titles['style'] != self.body_style]

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
            (self['page_number'] == more_titley['page_number']) &
            (self['block_number'] == more_titley['block_number']) &
            (self['line_number'] == more_titley['line_number'])
        ]

        return self.loc[self['total_y'] < more_titley_line['total_y'].min()]

    def to_items(self):
        """
        Convert the Lines object to a list or dict of text.
        """
        lines = self.copy()
        if len(lines) > 1:

            # Get which lines start with a bullet
            lines['bullet_start'] = False
            lines.loc[lines.is_bullet_start(), 'bullet_start'] = True

            # Remove bullet points from the text
            lines = lines.loc[~(
                lines['text'].str.strip().apply(utils.is_bullet) &
                (lines['span_number'] == 0)
            )]

            # Get the approximate size of the first word
            lines['end_gap'] = lines['bbox_x2'].max() - lines['bbox_x2']
            lines['first_word_size'] = lines.apply(
                lambda row:
                    (row['bbox_x2'] - row['bbox_x1']) *
                    len(row['text'].split(' ')[0]) / len(row['text']),
                axis=1
            )

            # Get sentence end and sentence start
            lines['sentence_start'] = lines.apply(lambda row: row.is_sentence_start(), axis=1)
            lines['sentence_end'] = lines.apply(lambda row: row.is_sentence_end(), axis=1)

            # Get whether or not the sentence is the start of a new "item"
            # # 1. line starts with a bullet point
            lines['sentence_start_with_bullet'] = False
            lines.loc[
                lines['sentence_start'].fillna(True) & lines['bullet_start'],
                'sentence_start_with_bullet'
            ] = True

            # # 2. previous line is short
            line_enders = [':']
            lines['previous_line_ends_short'] = False
            lines.loc[
                lines['sentence_start'].fillna(True) & (
                    (
                        lines['sentence_end'].shift(1).fillna(True) |
                        lines['text'].shift(1).str.strip().str[-1].isin(line_enders)
                    ) &
                    ((lines['total_y'] - lines['total_y'].shift(1).fillna(-1)) >= lines['size']*0.1) &
                    (lines['end_gap'].shift(1).fillna(-1) >= lines['first_word_size']*1.2)
                ),
                'previous_line_ends_short'
            ] = True

            # # 3. significant vertical gap
            line_spacing_min = (lines['total_y'] - lines['total_y'].shift(1)).min()
            lines['vertical_gap'] = False
            lines.loc[
                lines['sentence_start'].fillna(True) & (
                    (lines['page_number'] == lines['page_number'].shift(1).fillna(0)) &
                    ((lines['total_y'] - lines['total_y'].shift(1).fillna(-1)) > lines['size'].apply(
                        lambda size: max(size*1.5, line_spacing_min*1.5)
                    ))
                ),
                'vertical_gap'
            ] = True

            # New group is when the item starts and the previous item ends
            lines['item_start'] = lines[[
                'sentence_start_with_bullet', 'previous_line_ends_short', 'vertical_gap'
            ]].any(axis=1)
            lines['item_no'] = lines['item_start'].cumsum()

            # Group into items and combine the text
            lines = lines.groupby(['item_no'])[['text', 'bullet_start']].agg({
                'text': lambda x: ' '.join(x.str.strip()),
                'bullet_start': 'first'
            })
            lines = lines.dropna(subset=['text'])

            # Remove bullets for cases where all items are bullets
            lines['text'] = lines['text'].astype(str).apply(utils.remove_bullet)
            if not lines['bullet_start'].all():
                lines.loc[lines['bullet_start'], 'text'] = '• ' + lines['text']

        # Convert to list
        items = lines['text'].dropna().astype(str).str.strip().tolist()

        # Tidy sentences, and remove items with no characters
        items = [
            utils.tidy_sentence(txt)
            for txt in items
            if re.search('[a-zA-Z]', txt)
        ]

        return items

    def is_bullet_start(self):
        """
        Check whether each row in a dataframe is the start of a bullet point.
        I.e. it is a bullet point itself, or is following a bullet point on the same level.
        """
        lines = self.copy()
        lines['bullet_start'] = False

        # The row is a bullet start if it meets a bullet format (i.e. bullet point character, "a)", "a.", etc.)
        lines.loc[
            lines['text'].str.strip().apply(utils.is_bulleted) &
            (lines['span_number'] == 0),
            'bullet_start'
        ] = True

        # The row is a bullet start if the previous row is a bullet, and is on the same level
        lines['bullet'] = lines['text'].str.strip().apply(utils.is_bullet)
        lines.loc[
            (lines['total_y'] == lines['total_y'].shift(1).fillna(-1)) &
            lines['bullet'].shift(1).fillna(False),
            'bullet_start'
        ] = True

        return lines['bullet_start']
