import numpy as np
import re
import spacy
from googletrans import Translator
from langdetect import detect
import time


nlp_spacy = spacy.load("en_core_web_md")
translator = Translator()


# ******************************************************************
# Splits long text into chunks based on max length and linebreaks.
# Does it for each text in the list 'texts'
# Also translates if text is not in English 
# ******************************************************************
def split_into_chunks(texts, max_len=320, verbose=0):

    # make sure 'texts' is a list
    if isinstance(texts, str): texts = [texts]
    
    newline_reg = re.compile(r"\n+")
    divided_text = []
    text_indicies = [0]
    text_ind = 0
    for text in texts:
        mod_text = newline_reg.sub(r"\n", text)
        mod_text = translate_text(mod_text)
        # check if we can do the full text
        if len(mod_text.split()) <= max_len:
            divided_text.append(mod_text)
            text_ind += 1
        else:
            # divide into paragrahps based on newline
            paragraphs = mod_text.split("\n")
            for paragraph in paragraphs:
                # check if we can do paragraph
                if len(paragraph.split()) <= max_len:
                    divided_text.append(paragraph)
                    text_ind += 1
                else:
                    # divide paragraph into approximately equal chunks
                    sentences = [
                        sentence.text for sentence in nlp_spacy(paragraph).sents
                    ]
                    sentence_lengths = np.cumsum(
                        [len(sentence.split()) for sentence in sentences]
                    )
                    rem_lengths = sentence_lengths.copy()

                    # find the minimal number of splits we need
                    n_splits = 1
                    while rem_lengths[-1] > max_len:
                        ind = np.searchsorted(rem_lengths, max_len)
                        rem_lengths -= rem_lengths[ind]
                        n_splits += 1
                    # determine which sentences go into which chunks
                    split_indicies = [0]
                    for i in range(1, n_splits):
                        len_target = int(i * sentence_lengths[-1] / n_splits)
                        ind = np.searchsorted(
                            sentence_lengths, len_target, side="right"
                        )
                        split_indicies.append(ind)
                    split_indicies.append(len(sentence_lengths))
                    if verbose>0:
                        print(split_indicies)
                        print(len(sentences))
                    text_ind += n_splits

                    # form the chunks
                    for j, _ in enumerate(split_indicies[:-1]):
                        par_sentences = sentences[
                            split_indicies[j] : split_indicies[j + 1]
                        ]
                        new_par = " ".join(par_sentences)
                        divided_text.append(new_par)
        text_indicies.append(text_ind)

    return divided_text, text_indicies


# ******************************************
# Merge predictions for individual chunks 
# ******************************************
def merge_predicted_tags(predictions, text_indicies):
    merged_predictions = []
    for j, _ in enumerate(text_indicies[:-1]):
        current_prediction = []
        for prediction in predictions[text_indicies[j] : text_indicies[j + 1]]:
            current_prediction.extend(prediction)
        current_prediction = list(set(current_prediction))
        merged_predictions.append(current_prediction)
    return merged_predictions


# ******************************************
# Translate if not English 
# ******************************************
def translate_text(text):
    """
    translate text to English if it is not already in English
    """
    if len(text.split()) < 5:
        return text

    text_language = detect(text)
    if text_language == "en":
        return text

    time.sleep(1)
    try:
        translation = translator.translate(text)

        text = translation.text  # Update the field to English!
    #except RuntimeError:
    except: # Some errors broke the code, but were not caught by RuntimeError:
        pass
    return text    