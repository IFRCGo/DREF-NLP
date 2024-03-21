import re
import itertools


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
    replaced = re.sub(' +', ' ', replaced)
    return replaced


def generate_sentence_variations(sentence, abbreviations):
    """
    Given a sentence and possible abbreviations, generate all possible sentences with different abbreviation options.
    """
    # Find which abbreviations are in sentence
    lsources = [phrase for phrase in abbreviations if phrase_in_sentence(phrase, sentence)]
    ldests = [[phrase]+abbreviations[phrase] for phrase in lsources]

    # Generate the various pairings
    sentence_options = []
    for lproduct in itertools.product(*ldests):
        output = sentence
        for src, dest in zip(lsources, lproduct):
            output = replace_phrases_in_sentence(src, dest, output)

        sentence_options.append(output)

    return sentence_options


def contains(bbox1, bbox2):
    # Check if bbox1 contains bbox2
    if (
        (bbox1[0] < bbox2[0]) and
        (bbox1[1] < bbox2[1]) and
        (bbox1[2] > bbox2[2]) and
        (bbox1[3] > bbox2[3])
    ):
        return True
    return False


def get_overlap(bbox1, bbox2):
    # Get overlap area between boxes
    dx = min(bbox1[2], bbox2[2]) - max(bbox1[0], bbox2[0])
    dy = min(bbox1[3], bbox2[3]) - max(bbox1[1], bbox2[1])
    if (dx >= 0) and (dy >= 0):
        return dx*dy


def get_area(bbox):
    return abs((bbox[2]-bbox[0])*(bbox[1]-bbox[3]))


def is_text_title(text):
    if text != text:
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
    filler_words = ['and', 'the', 'to', 'for', 'in', 'a', 'in']
    text_without_fillers = replace_phrases_in_sentence(filler_words, '', text).strip()
    return text_without_fillers