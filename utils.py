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
        blocks = page_layout.get_text("dict", flags=11)["blocks"]
        for b in blocks:
            for l in b["lines"]:
                for s in l["spans"]:
                    if s['text'].strip():
                        data.append({
                            'text': s["text"],
                            'fontsizes': [s["size"]],
                            'fontnames': [s["font"]],
                            'bold': [(True if 'bold' in s["font"] else False)],
                            'page': page_number
                        })
    return data


def is_lessons_learned_section_title(text):
    if text != text:
        return False

    if strip_non_alpha(text).lower() in ['lessons learned', 'lessons learnt']:
        return True

    return False


def strip_non_alpha(text):
    text = re.sub(r'[^A-Za-z ]+', ' ', text)
    text = re.sub(' +', ' ', text)
    return text.strip()


def get_lessons_learned_section_end(lines, size_threshold=0.2):

    # Get lessons learned title information
    title = lines.iloc[0]
    title_size = mean(title['fontsizes'])
    title_bold = any(title['bold'])

    # Get first line information
    first_line = lines.iloc[1]
    first_line_size = mean(first_line['fontsizes'])
    first_line_bold = any(first_line['bold'])

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

        if line['fontsizes']:
            average_line_size = mean(line['fontsizes'])
            if average_line_size >= (title_size - size_threshold):
                size_condition_met = True

        if line['bold']:
            line_bold = any(line['bold'])
            if line_bold:
                bold_condition_met = True

        if require_large_size and require_bold:
            if size_condition_met and bold_condition_met:
                return previous_index
        elif require_large_size and size_condition_met:
            return previous_index
        elif require_bold and bold_condition_met:
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
        raise RuntimeError(f'More than one appeal document found for {mdr_code}\n\n{final_reports}')
    elif len(final_reports)==0:
        raise RuntimeError(f'No appeal documents found for {mdr_code}')
    document_url = final_reports[0]['document_url']

    # Download the report
    pdf = requests.get(document_url)
    with open(save_path, 'wb') as f:
        f.write(pdf.content)