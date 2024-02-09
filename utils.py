import re
import io
from math import sqrt
from statistics import mean
import requests
from collections import Counter
import fitz

def extract_text_and_fontsizes(document_path):
    data = []
    total_y = 0

    # Loop through pages and paragraphs
    for page_number, page_layout in enumerate(fitz.open(document_path)):

        # Get drawings to get text highlights
        coloured_drawings = [drawing for drawing in page_layout.get_drawings() if (drawing['fill'] != (0.0, 0.0, 0.0))]

        # Loop through blocks
        blocks = page_layout.get_text("dict", flags=11)["blocks"]
        for block_number, block in enumerate(blocks):
            for line_number, line in enumerate(block["lines"]):
                spans = [span for span in line['spans'] if span['text'].strip()]
                for span_number, span in enumerate(spans):
                        
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
                    span['text'] = span['text'].strip().replace('\r', '\n')
                    span['bold'] = is_bold(span["font"])
                    span['highlight_color'] = highlight_color_hex
                    span['page_number'] = page_number
                    span['block_number'] = block_number
                    span['line_number'] = line_number
                    span['span_number'] = span_number
                    span['origin_x'] = span['origin'][0]
                    span['origin_y'] = span['origin'][1]
                    span['total_y'] = span['origin'][1]+total_y
                    data.append(span)

        total_y += page_layout.rect.height

    return data


def phrase_in_sentence(phrase, sentence):
    if re.search(r"\b{}\b".format(phrase), sentence.lower().strip()):
        return True
    return False


def replace_phrases_in_sentence(phrases, repl, sentence):
    replaced = sentence.lower().strip()
    if isinstance(phrases, str):
        phrases = [phrases]
    for phrase in phrases:
        replaced = re.sub(r"\b{}\b".format(phrase), repl, replaced)
    return replaced


def is_bold(text):
    if ("black" in text.lower()) or ("bold" in text.lower()):
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


def strip_non_alphanumeric(text):
    text = re.sub(r'[^A-Za-z0-9 ]+', ' ', text)
    text = re.sub(' +', ' ', text)
    return text.strip()


def strip_filler_words(text):
    filler_words = ['and', 'the']
    words = text.split(' ')
    text_without_fillers = [word for word in words if word not in filler_words]
    return ' '.join(text_without_fillers)


def colour_diff(colour1, colour2):
    """
    Find the difference between two colours
    """
    # If both nan, return True
    if (colour1!=colour1) and (colour2!=colour2):
        return 0

    # Calculate distance if both not nan
    elif (colour1==colour1) and (colour2==colour2):

        # If the same, return
        if colour1==colour2:
            return 0
        
        # Convert to RGB
        if isinstance(colour1, str):
            colour1 = tuple(int(colour1.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
        if isinstance(colour2, str):
            colour2 = tuple(int(colour2.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))

        # Calculate distance, and normalize to 1
        distance = sqrt((colour1[0] - colour2[0])**2 + (colour1[1] - colour2[1])**2 + (colour1[2] - colour2[2])**2)/sqrt(3*(255**2))
        
        return distance
    
    # If one is nan and the other is not nan, return max distance 1
    else:
        return 1


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
    if len(final_reports)==0:
        raise RuntimeError(f'No final report appeal documents found for {mdr_code}')
    
    if len(final_reports)>1:
        final_reports = [document for document in final_reports if ('prelim' not in document['name'].lower())]
    if len(final_reports)>1:
        final_reports = sorted(final_reports, key=lambda d: d['created_at'], reverse=True)

    # Download the report
    document_url = final_reports[0]['document_url']
    pdf = requests.get(document_url)
    with open(save_path, 'wb') as f:
        f.write(pdf.content)