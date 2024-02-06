import re
import io
from statistics import mean
import requests
from collections import Counter
import fitz

def extract_text_and_fontsizes(document_path):
    data = []

    # Loop through pages and paragraphs
    for page_number, page_layout in enumerate(fitz.open(document_path)):

        # Get drawings to get text highlights
        coloured_drawings = [drawing for drawing in page_layout.get_drawings() if (drawing['fill'] != (0.0, 0.0, 0.0))]

        # Loop through blocks
        blocks = page_layout.get_text("dict", flags=11)["blocks"]
        for block_number, block in enumerate(blocks):
            for line_number, line in enumerate(block["lines"]):
                for span_number, span in enumerate(line["spans"]):
                    if span['text'].strip():
                        
                        # Check if the text block is contained in a drawing
                        highlights = []
                        for drawing in coloured_drawings:
                            if get_overlap(span['bbox'], drawing['rect']):
                                drawing['overlap'] = get_overlap(span['bbox'], drawing['rect'])
                                highlights.append(drawing)

                        # Get largest overlap
                        highlight_color_hex = None
                        if highlights:
                            largest_highlight = max(highlights, key=lambda x: x['overlap'])
                            highlight_color = largest_highlight['fill']
                            if highlight_color:
                                highlight_color_hex = '#%02x%02x%02x' % (int(255*highlight_color[0]), int(255*highlight_color[1]), int(255*highlight_color[2]))
                        
                        # Append results
                        span['bold'] = (True if 'bold' in span["font"].lower() else False)
                        span['highlight_color'] = highlight_color_hex
                        span['page_number'] = page_number
                        span['block_number'] = block_number
                        span['line_number'] = line_number
                        span['span_number'] = span_number
                        data.append(span)

    return data


def box_inside_box(bbox1, bbox2, tolerance=0.05):
    # bbox = (x0, y0, x1, y1)
    # Check if bbox1 in bbox2
    if (
            (bbox2[0]-bbox1[0]) <= (tolerance*bbox1[0]) and 
            (bbox2[1]-bbox1[1]) <= (tolerance*bbox1[1]) and 
            (bbox1[2]-bbox2[2]) <= (tolerance*bbox1[2]) and 
            (bbox1[3]-bbox2[3]) <= (tolerance*bbox1[3])
        ):
        return True
    return False


def get_overlap(bbox1, bbox2):
    # Get overlap area between boxes
    dx = min(bbox1[2], bbox2[2]) - max(bbox1[0], bbox2[0])
    dy = min(bbox1[3], bbox2[3]) - max(bbox1[1], bbox2[1])
    if (dx >= 0) and (dy >= 0):
        return dx*dy


def is_text_title(text):
    if text!=text: 
        return False
    # Check first letter is uppercase
    letters = [char for char in text if char.isalpha()]
    if letters:
        if letters[0].isupper():
            return True
        else:
            return False
    return False


def strip_non_alpha(text):
    text = re.sub(r'[^A-Za-z ]+', ' ', text)
    text = re.sub(' +', ' ', text)
    return text.strip()


def get_lessons_learned_section_end(lines):

    # Get lessons learned title information
    title = lines.iloc[0]
    first_line_chars = lines.loc[lines['text'].astype(str).str.contains('[a-zA-Z]')].iloc[1]

    # Round sizes
    title_size = 2*round(title['size'])
    first_line_size = 2*round(first_line_chars['size'])

    # Loop through lines
    # Returns index of last element in the lessons learned section
    previous_idx = 0
    for idx, line in lines.iloc[1:].iterrows():

        line_size = 2*round(line['size'])

        # If line is a page number, continue
        any_letters = [char for char in line['text'].strip() if char.isalpha()]
        if not any_letters:
            continue

        # Next title if text is bigger than the lessons learned title, or bold
        if line_size > title_size:
            return previous_idx
        elif line_size == title_size:
            if first_line_size < title_size:
                return previous_idx
            if (title['bold'] and line['bold']) and not first_line_chars['bold']:
                return previous_idx

        previous_idx = idx
                
    return lines.index[-1]


def remove_dict_values(dct, remove_values):
    # Dict in form: {66: [], 68: [], 71: [], 72: [497, 911, 1016, ...
    # Remove values, and remove dict items if values is empty list
    dct = {
        k: [v for v in vals if v not in remove_values] 
        for k, vals in dct.items()
    }
    return dct


def remove_empty_dict_values(dct):
    # Remove empty or None or False dict values
    dct = {
        k: v 
        for k, v in dct.items()
        if v
    }
    return dct


def is_bold(text):
    if ("black" in text.lower()) or ("bold" in text.lower()):
        return True


def styles_are_similar(style1, style2):
    # Check if two styles are similar
    if abs(style1["double_fontsize_int"] - style2["double_fontsize_int"]) <= 4:
        if style1["highlight_color"] and style2["highlight_color"]:
            if is_bold(style1['font']) == is_bold(style2['font']):
                return True
    return False


def get_similar_sector(text, sector_title_texts):
    text_base = strip_non_alpha(text).lower()

    # First, check if there is an exact match with the titles
    for sector_name, details in sector_title_texts.items():
        if details is None:
            titles = [sector_name]
        else:
            titles = (details['titles'] if 'titles' in details else [])+[sector_name]
        for title in titles:
            if text_base == strip_non_alpha(title).lower():
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
        filler_words = ['and']
        text_base_without_keywords_words = [word for word in text_base_without_keywords_words if (word and (word not in filler_words))]
        text_base_without_filler_worlds = [word for word in text_base_words if (word and (word not in filler_words))]
        number_words_covered = len(text_base_without_filler_worlds) - len(text_base_without_keywords_words)
        proportion_text_covered_by_sector[sector_name] = number_words_covered/len(text_base_without_filler_worlds)

    max_sector = max(proportion_text_covered_by_sector, key=proportion_text_covered_by_sector.get)
    max_proportion = proportion_text_covered_by_sector[max_sector]

    if max_proportion > 0:
        return max_sector, max_proportion


def get_ifrc_go_final_report(mdr_code, save_path):
    # Get Appeal ID
    appeals = requests.get(f'https://goadmin.ifrc.org/api/v2/appeal/?format=json&code={mdr_code}')
    appeals.raise_for_status()
    appeal_id = appeals.json()['results'][0]['id']

    # Get appeal documents
    appeal_documents = requests.get(f'https://goadmin.ifrc.org/api/v2/appeal_document/?format=json&appeal={appeal_id}')
    appeal_documents.raise_for_status()

    # Get final reports
    final_reports = [document for document in appeal_documents.json()['results'] if ('final' in document['name'].lower())]
    if len(final_reports)>1:
        final_reports = [document for document in final_reports if ('prelim' not in document['name'].lower())]
    if len(final_reports)>1:
        raise RuntimeError(f'More than one appeal document found for {mdr_code}\n\n{final_reports}')
    elif len(final_reports)==0:
        raise RuntimeError(f'No appeal documents found for {mdr_code}')
    document_url = final_reports[0]['document_url']

    # Download the report
    pdf = requests.get(document_url)
    with open(save_path, 'wb') as f:
        f.write(pdf.content)