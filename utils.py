import re
import io
import yaml
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
        for block in blocks:
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
                        highlight_colour_hex = None
                        if highlights:
                            largest_highlight = max(highlights, key=lambda x: x['overlap'])
                            highlight_colour = largest_highlight['fill']
                            if highlight_colour:
                                highlight_colour_hex = '#%02x%02x%02x' % (int(255*highlight_colour[0]), int(255*highlight_colour[1]), int(255*highlight_colour[2]))
                        
                        # Append results
                        data.append({
                            'text': span["text"].strip(),
                            'fontsize': span["size"],
                            'fontname': span["font"],
                            'colour': span["color"],
                            'bold': (True if 'bold' in span["font"].lower() else False),
                            'highlight_colour': highlight_colour_hex,
                            'page_number': page_number,
                            'line_number': line_number,
                            'span_number': span_number
                        })

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


def is_lessons_learned_section_title(row):
    if row['text'] != row['text']:
        return False

    # Check first letter is uppercase
    letters = [char for char in row['text'] if char.isalpha()]
    if letters:
        if not letters[0].isupper():
            return False

    # If not at front of line, return False
    if row['span_number'] > 0:
        return False

    # If lessons learned text
    if strip_non_alpha(row['text']).lower() in ['lessons learned', 'lessons learnt']:
        return True

    return False


def strip_non_alpha(text):
    text = re.sub(r'[^A-Za-z ]+', ' ', text)
    text = re.sub(' +', ' ', text)
    return text.strip()


def get_lessons_learned_section_end(lines, size_threshold=0.2):

    # Get lessons learned title information
    title = lines.iloc[0]
    title_size = title['fontsize']
    title_bold = title['bold']

    # Get first line information
    first_line = lines.iloc[1]
    first_line_size = first_line['fontsize']
    first_line_bold = first_line['bold']

    # If the title is larger than the first line, consider this font size to represent a new section
    # Could do this based on exact fontsizes - doubled and rounded to int (i.e. exact halves)
    require_large_size = False
    if (title_size - first_line_size) >= size_threshold:
        require_large_size = True

    # Else, if title is bold and the first line is not bold, consider boldness to represent the new section
    require_bold = False
    if title_bold and not first_line_bold:
        require_bold = True

    # Loop through lines until required conditions are met
    # Returns index of last element in the lessons learned section
    size_condition_met = False; bold_condition_met = False
    previous_index = None
    for i, line in lines.iloc[1:].iterrows():

        if line['fontsize']:
            if line['fontsize'] >= (title_size + size_threshold):
                size_condition_met = True

        if line['bold']:
            if line['bold']:
                bold_condition_met = True

        # If required conditions are met, return
        if require_large_size and require_bold:
            if size_condition_met and bold_condition_met:
                return previous_index
        elif require_large_size:
            if size_condition_met:
                return previous_index
        elif require_bold:
            if bold_condition_met:
                return previous_index
        else:
            if bold_condition_met or size_condition_met:
                return previous_index

        previous_index = i
                
    return lines.index[-1]


def get_similar_sector(text):
    # If the text is not capitalised, return
    for char in text:
        if char.isalpha():
            if not char.isupper():
                return None
            else:
                break

    # If no alphanumeric characters, return
    sectors = yaml.safe_load(open('sectors.yml'))
    text_base = strip_non_alpha(text).lower()
    if text_base != text_base:
        return

    # First, check if there is an exact match with the titles
    for sector_name, details in sectors.items():
        if details is None:
            titles = [sector_name]
        else:
            titles = (details['titles'] if 'titles' in details else [])+[sector_name]
        for title in titles:
            if text_base == strip_non_alpha(title).lower():
                return sector_name, 1

    # Next, check if there is an exact match with any keywords
    for sector_name, details in sectors.items():
        if details is None:
            keywords = []
        else:
            keywords = (details['keywords'] if 'keywords' in details else [])
        for keyword in keywords:
            if text_base == strip_non_alpha(keyword).lower():
                return sector_name, 0.9

    # Next, check how many words in the text are covered by each sector and sector keywords
    text_base_words = text_base.split(' ')
    filler_words = ['and']
    text_base_words = [word for word in text_base_words if word not in filler_words]
    proportion_text_covered_by_sector = {}
    for sector_name, details in sectors.items():
        if details is None:
            keywords = []
        else:
            keywords = (details['keywords'] if 'keywords' in details else [])
        overlap = [word for word in text_base_words if word in keywords]
        proportion_text_covered_by_sector[sector_name] = len(overlap)/len(text_base_words)

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