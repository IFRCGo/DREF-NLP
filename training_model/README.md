
# How to train DocBERT on IFRC DREF data

## Model information

+ [DocBERT](models/bert/) : DocBERT: BERT for Document Classification [(Adhikari et al., 2019)](https://arxiv.org/abs/1904.08398v1)

## Setup

### Prerequisites

It is assumed that the repository is structured like 

```
DREF_NLP
 ├── data
 |    └── training
 |           └── training_data.csv
 ├── training_model
      └──README
      └──DocBERT
           └── hedwig           
           └── hedwig-data
                  └── models
                  └── embeddings
                  └── datasets
                         └── DREF
                         └── .......                                           
                         └── .......                                           
 ```

where *training_data.csv* contains the pre-processed DREF IFRC training data.

### Environment

Install the envrionment from the requirements.txt file from the "training_model" folder

```
conda create --name dref_training python=3.8
conda activate dref_training
python -m pip install -r requirements.txt
python -m spacy download en_core_web_md
```

### Data

To download the "hedwig" folder, go to  https://github.com/castorini/hedwig and download

To download other datasets, along with required pretrained BERT-models:

1. Download the repository: [`hedwig-data`](https://git.uwaterloo.ca/jimmylin/hedwig-data). 

2. Place all its content into the *hedwig-data* folder inside the *DocBERT* folder. 
Hedwig-data should contain folders datasets, embeddings, and models.
The dataset folder should contain both DREF subfolder from this repository and a few downloaded subfolders. 

3. Run the below command from the *DocBERT* folder in order to add the IFRC dataset.
```
python create_dref_data.py
```

## Quick start

For fine-tuning the pre-trained BERT-base model on the IFRC dataset, just run the following from the *hedwig* folder

```
python -m models.bert --dataset DREF --model bert-base-uncased --max-seq-length 256 --batch-size 2 --lr 2e-5 --epochs 30
```

Depending on the memory of the GPU in your PC you may want to increase the batch-size to speed up training.  

The best model weights found during training will be saved in

```
/model_checkpoints/bert/DREF/[timestamp].pt
```
Where [timestamp] is the time training was initialized. 

To only test the model, using previously found weights, you can use the following command, again starting from from the *hedwig* folder

```
python -m models.bert --dataset DREF --model bert-base-uncased --max-seq-length 256 --batch-size 16 --lr 2e-5 --epochs 30 --trained-model [model weight path]
```
where [model weight path] is the path to your stored model weights, e.g. 
```
./model_checkpoints/bert/DREF/2021-01-01_23-45-25.pt
```
## Model Types 

The same types of BERT models as in [huggingface's implementation](https://github.com/huggingface/pytorch-pretrained-BERT.git) are available
- bert-base-uncased
- bert-large-uncased
- bert-base-cased
- bert-large-cased

## Settings

The finetuning procedure can be found in:
- [BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding](https://arxiv.org/abs/1810.04805)
- [DocBERT: BERT for Document Classification](https://arxiv.org/abs/1904.08398v1)
