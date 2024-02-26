import re
import itertools
import io
from math import sqrt
from statistics import mean
import requests
from collections import Counter
import fitz


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
    Given a sentence, sentence, and possible abbreviations, abbreviations, generate all possible sentences with different abbreviation options.
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
    filler_words = ['and', 'the', 'to', 'for', 'in', 'a', 'in']
    text_without_fillers = replace_phrases_in_sentence(filler_words, '', text).strip()
    return text_without_fillers


def colour_diff(colour1, colour2):
    """
    Find the difference between two colours.
    Both colours must be in hex format.
    """
    # If both nan, return True
    if (colour1!=colour1) and (colour2!=colour2):
        return 0

    # Calculate distance if both not nan
    elif (colour1==colour1) and (colour2==colour2):

        # If the same, return
        if colour1==colour2:
            return 0
        
        # Convert hex to RGB
        colour1 = tuple(int(str(colour1).lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
        colour2 = tuple(int(str(colour2).lstrip("#")[i:i+2], 16) for i in (0, 2, 4))

        # Calculate distance, and normalize to 1
        distance = sqrt(
            (colour1[0] - colour2[0])**2 + 
            (colour1[1] - colour2[1])**2 + 
            (colour1[2] - colour2[2])**2
        )/sqrt(3*(255**2))
        
        return distance
    
    # If one is nan and the other is not nan, return max distance 1
    else:
        return 1