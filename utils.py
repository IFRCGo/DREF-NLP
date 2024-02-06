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