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
from dref_tagging.prediction import predict_tags_any_length

from typing import Union, List
from pydantic import BaseModel
import numpy as np
from langdetect import detect

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


import numpy as np
import pandas as pd

from typing import List, Sequence, Tuple, Union

app = FastAPI()

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

    # make sure 'texts' is a list
    if isinstance(texts, str): texts = [texts]

    merged_predictions = predict_tags_any_length(texts)

    #texts[0] = '22 ' + texts[0] # for debugging

    final_predictions = [
        Prediction(text=t, tags=p) for (t, p) in zip(texts, merged_predictions)
    ]

    return final_predictions
    
