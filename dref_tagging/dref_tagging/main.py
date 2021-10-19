"""
Implement an API for automatic tagging of text using FastAPI

Classes
-------
    Prediction: Return class for the prediction from the API

Functions
---------
    classify: implement the FastAPI endpoint for automatic tagging
    translate: translate text to English
"""

from fastapi import Body, FastAPI
from dref_tagging.prediction import args
from dref_tagging.prediction import predict_tags
from typing import Union, List
from pydantic import BaseModel
import re
import spacy
import numpy as np
from langdetect import detect
from googletrans import Translator
import time

nlp_spacy = spacy.load("en_core_web_md")
"""
Module for automatically generating tags for texts using the DREF framework

Functions
---------
    predict_tags: predict IFRC tags for given texts
    _get_features: extracts features from given texts, to be used by predict_tags

Notes
-----
    This file and the docBERT model used for the predictions is based 
    on the docBERT implementation from Hedwig 
    , https://github.com/castorini/hedwig, which is licensed under 
    Apache License 2.0. See the included LICENSE.txt for licensing details.
"""

import random

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, SequentialSampler, TensorDataset
from transformers import BertTokenizer
from typing import List, Sequence, Tuple, Union
# Set default configuration in args.py
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
n_gpu = torch.cuda.device_count()

# Set random seed for reproducibility
seed = 3435
random.seed(seed)
np.random.seed(seed)
torch.manual_seed(seed)


args = dict()
args["num_labels"] = 46
args["max_seq_length"] = 400
args["batch_size"] = 2
args["device"] = device


app = FastAPI()
translator = Translator()

example_text = (
"A  pre hurricane season meeting will be held in June. Discussion will be held to improve the coordination in the use of shelter kits in the future."
)


class Prediction(BaseModel):
    """
    The return class model for the response from the API
    """

    text: str
    tags: List[str]

    class Config:
        schema_extra = {
            "example": [
                {
                    "text": example_text,
                    "tags": ["Pre-disaster Meetings and Agreements"],
                }
            ]
        }


@app.post("/classify", response_model=List[Prediction], status_code=201)
async def classify(
    texts: Union[str, List[str]] = Body(..., example=f'"{example_text}"',)
):
    """
    predict tags for text(s) sent to the API endpoint as a POST request

    This function implements an API POST endpoint using FastAPI. The
    endpoint expects a string (text - please remember to include quotation marks) or an array of strings encoded as 
    json. It returns the texts as well as their predicted list of tags 
    for the analytical framework of DREF 

    To test out the model, you can enter some text below. Please remember to include quotation marks.

    Parameters
    ----------
        texts: The text(s) to translate
    
    Returns
    -------
        result: the texts as well as their predicted tags, given as a list
            of instances of the class 'Prediction'.
    """

    # logic to split long text into suitable text chunks
    max_len = int(args["max_seq_length"] * 0.8)
    if isinstance(texts, str):
        texts = [texts]

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

    # make predictions on the chunks
    returned_texts, predictions = predict_tags(divided_text)

    # merge split text chunks back into the original text and union the predictions
    merged_predictions = []
    for j, _ in enumerate(text_indicies[:-1]):
        current_prediction = []
        for prediction in predictions[text_indicies[j] : text_indicies[j + 1]]:
            current_prediction.extend(prediction)
        current_prediction = list(set(current_prediction))
        merged_predictions.append(current_prediction)
    assert len(texts) == len(merged_predictions)

    final_predictions = [
        Prediction(text=t, tags=p) for (t, p) in zip(texts, merged_predictions)
    ]

    return final_predictions


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
    except RuntimeError:
        pass
    return text
