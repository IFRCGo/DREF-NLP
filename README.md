Installation of all packages needed to run both apps

```
conda create --name dref python=3.8
conda activate dref
python -m pip install -r requirements.txt
python -m spacy download en_core_web_md
python -m pip install -e ./dref_tagging
python -m pip install -e ./dref_parsing
```

Running apps

```
uvicorn dref_tagging.main:app --reload
uvicorn dref_parsing.main:app --reload
```

To run the dref_tagging app you must download the file DREF_docBERT.pt and add it to the dref_tagging/dref_tagging/config file.
Currently to download this file you must contact the team at Nextbridge. 