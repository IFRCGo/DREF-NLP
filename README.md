## Overview

Available apps:

- Parsing PDFs (dref_parsing)
- Tagging text (dref_tagging)
- Parsing + Tagging

## Installation of all packages needed to run all apps

```
conda create --name dref python=3.8
conda activate dref
python -m pip install -r requirements.txt
python -m spacy download en_core_web_md
python -m pip install -e ./dref_parsing
python -m pip install -e ./dref_tagging
```

## Requirements

To run the dref_tagging app (or the joint app) you must download the file DREF_docBERT.pt 
and add it to the dref_tagging/dref_tagging/config file.
Currently to download this file you must contact the [IM team at IFRC](&#105;&#109;&#64;&#105;&#102;&#114;&#99;&#46;&#111;&#114;&#103;)

## Running apps

The apps are made using fastapi and can be started by commands
```
uvicorn dref_parsing.main:app --reload
uvicorn dref_tagging.main:app --reload
uvicorn main:app --reload
```
and then opening in a browser the indicated web-page,
usually http://127.0.0.1:8000/docs 

## Azure / Docker

The current version of the apps is available at:
https://drefnlpdev.azurewebsites.net/docs

It contains the joint apps (for parsing the data and tagging it).

If the dref_tagging is needed (without parsing the data), it is available at:
https://dreftagging.azurewebsites.net/docs

The docker images uploaded to Azure were created 
by running the following build command from the folders 
```dref_tagging```, ```dref_parsing``` or the root folder:

```docker build -t myimage . ```

To run the docker locally, use

```docker run -p 8000:8000 myimage```

and open ```http://localhost:8000/docs```


