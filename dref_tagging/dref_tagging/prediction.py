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

import pathlib
from importlib import resources
import random

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, SequentialSampler, TensorDataset
from transformers import BertTokenizer
from typing import List, Sequence, Tuple, Union

from dref_tagging.tag_utils import split_into_chunks, merge_predicted_tags

# **************************************************************************
# SETUP / PREPARATIONS
# **************************************************************************

# Set default configuration in args.py
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
n_gpu = torch.cuda.device_count()

# print('Device:', str(device).upper())
# print('Number of GPUs:', n_gpu)

# Set random seed for reproducibility
seed = 3435
random.seed(seed)
np.random.seed(seed)
torch.manual_seed(seed)

# BASE_DIRECTORY = pathlib.Path(__file__).parent.parent

model = "bert-base-uncased"
# trained_model = BASE_DIRECTORY / "DREF_docBERT.pt"

if n_gpu > 0:
    torch.cuda.manual_seed_all(seed)

args = dict()
args["num_labels"] = 46
args["max_seq_length"] = 400
args["batch_size"] = 2
args["device"] = device

tokenizer = BertTokenizer.from_pretrained(model)

with resources.path("dref_tagging.config", "DREF_docBERT.pt") as trained_model:
    model = torch.load(trained_model, map_location=device)

if n_gpu > 1:
    model = torch.nn.DataParallel(model)

model = model.to(device)
model.eval()

with resources.path("dref_tagging.config", "tags_dict.csv") as tags_file:
    tags_dict = pd.read_csv(tags_file, index_col=0).loc[:, "Category"]


# **************************************************************************
# Predict tags for longer texts:
# Splits them into chuncks, does tagging and merges the tags
# **************************************************************************
def predict_tags_any_length(
    eval_texts: Union[str, Sequence[str]]
) -> Tuple[List[str], List[List[str]]]:

    if isinstance(eval_texts, str):
        eval_texts = [eval_texts]

    # split long text into suitable text chunks
    max_len = int(args["max_seq_length"] * 0.8)
    divided_text, text_indicies = split_into_chunks(eval_texts, max_len = max_len, verbose=1) 

    # make predictions on the chunks
    returned_texts, predictions = predict_tags(divided_text)

    # merge the predictions
    merged_predictions = merge_predicted_tags(predictions, text_indicies) 

    assert len(eval_texts) == len(merged_predictions)
    return merged_predictions


# **************************************************************************
# Predict tags (for shorter chunks of text)
# **************************************************************************
def predict_tags(
    eval_texts: Union[str, Sequence[str]]
) -> Tuple[List[str], List[List[str]]]:
    """

    predict tags for given texts using the IFRC DREF framework
    
    Given a text or sequence of texts this function automatically
    tags them using the DREF framework. The 
    function uses a trained deep-learning model called docBERT to make 
    the predictions.

    Parameters
    ----------
        eval_texts: The text(s) to be evaluated

    Returns
    -------
        eval_texts: A list of the text(s) that were given as input
        predicted_tags: A list of lists of tags such that the i-th
            element is a list of tags for the text in element i of
            'eval_texts' 

    """

    if isinstance(eval_texts, str):
        eval_texts = [eval_texts]

    try:
        eval_texts = [str(text) for text in eval_texts]
    except TypeError:
        error_msg = "Unable to transform input to a list of strings"
        raise TypeError(error_msg)

    features = _get_features(eval_texts, args["max_seq_length"])
    unpadded_input_ids, unpadded_input_mask, unpadded_segment_ids = features

    padded_input_ids = torch.tensor(unpadded_input_ids, dtype=torch.long)
    padded_input_mask = torch.tensor(unpadded_input_mask, dtype=torch.long)
    padded_segment_ids = torch.tensor(unpadded_segment_ids, dtype=torch.long)

    eval_data = TensorDataset(padded_input_ids, padded_input_mask, padded_segment_ids)
    eval_sampler = SequentialSampler(eval_data)
    eval_dataloader = DataLoader(
        eval_data, sampler=eval_sampler, batch_size=args["batch_size"]
    )

    predicted_tags = []

    for input_ids, input_mask, segment_ids in eval_dataloader:
        input_ids = input_ids.to(args["device"])
        input_mask = input_mask.to(args["device"])
        segment_ids = segment_ids.to(args["device"])

        with torch.no_grad():
            logits = model(input_ids, input_mask, segment_ids)[0]
            predicted_tags.extend(
                torch.sigmoid(logits*5).round().long().cpu().detach().numpy()
            )

    for i, prediction in enumerate(predicted_tags):
        prediction = [bool(d) for d in prediction]
        predicted_tags[i] = tags_dict.loc[prediction].to_list()

    return (eval_texts, predicted_tags)


# **************************************************************************
# **************************************************************************
def _get_features(texts: Sequence[str], max_seq_length: int):
    """
    generate input features to the BERT model from texts

    This helper function for the 'predict_tags' function takes in a list
    of texts and transforms each of them to the set of input features
    required by the BERT model that makes the tag predictions.

    Parameters
    ----------
        texts: the texts that the Bert model should make predictions 
            for
        max_seq_length: the maximum sequence length that the model 
            can handle

    Returns
    -------
        input_idss: a list of length equal to the number of texts. 
            Element i is a list of length 'max_seq_len' with the 
            (zero padded) integer ids for the tokenized input text for 
            element i of 'texts'. 
        input_masks: a list of length equal to the number of texts. 
            Element i is a list of length 'max_seq_len' with the input 
            mask for element i of 'input_idss'. The input mask has value 
            1 if the corresponding input id is not padding, and 0 
            otherwise.
        segment_ids: a list of length equal to the number of texts. 
            Element i is a list of length 'max_seq_len' with the segment 
            ids for element i of 'input_idss'. These may be used to 
            distinguish between sequences in a sequence pair. However 
            here each text is treated as a single sequence, so the 
            seqment ids are all 0.
    """
    input_idss = []
    input_masks = []
    segment_idss = []
    for text in texts:
        tokens_a = tokenizer.tokenize(text)
        if len(tokens_a) > max_seq_length - 2:
            tokens_a = tokens_a[: (max_seq_length - 2)]

        tokens = ["[CLS]"] + tokens_a + ["[SEP]"]

        input_ids = tokenizer.convert_tokens_to_ids(tokens)

        # The mask has 1 for real tokens and 0 for padding tokens. Only real
        # tokens are attended to.
        input_mask = [1] * len(input_ids)

        # Zero-pad up to the sequence length.
        padding = [0] * (max_seq_length - len(input_ids))
        input_ids += padding
        input_mask += padding
        segment_ids = [0] * max_seq_length

        assert len(input_ids) == max_seq_length
        assert len(input_mask) == max_seq_length
        assert len(segment_ids) == max_seq_length

        input_idss.append(input_ids)
        input_masks.append(input_mask)
        segment_idss.append(segment_ids)

    return (input_idss, input_masks, segment_idss)



