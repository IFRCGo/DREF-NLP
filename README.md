## Installation of all packages needed to run both apps

```
conda create --name dref python=3.8
conda activate dref
python -m pip install -r requirements.txt
python -m spacy download en_core_web_md
python -m pip install -e ./dref_tagging
python -m pip install -e ./dref_parsing
```

## Requirements

To run the dref_tagging app you must download the file DREF_docBERT.pt and add it to the dref_tagging/dref_tagging/config file.
Currently to download this file you must contact the team at Nextbridge. 

## Running apps

The apps are made using fastapi and can be started by commands
```
uvicorn dref_tagging.main:app --reload
uvicorn dref_parsing.main:app --reload
```
and then opening in a browser the indicated web-page,
usually http://127.0.0.1:8000/docs 

## Azure / Docker

The current versions of the apps are available at:

https://dref-pdf-parsing.azurewebsites.net/docs  
https://dreftagging.azurewebsites.net/docs

The docker images uploaded to Azure were created 
by running the following build command from the folders 
```dref_tagging``` and ```dref_parsing```:

```docker build -t myimage . ```

To run the docker locally, use

```docker run -p 8000:8000 myimage```

and open ```http://localhost:8000/docs```


