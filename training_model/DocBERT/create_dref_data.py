import pandas as pd
from pathlib import Path


def main():
    bert_dir = Path().parent.resolve()
    write_dir = bert_dir / "hedwig-data" / "datasets" / "DREF"
    write_dir.mkdir(parents=True, exist_ok=True)
    training_dir = bert_dir.parents[1] / "data" / "training"

    data = pd.read_csv(training_dir / "training_data_dref.csv",sep="\t")

    cols = ["Categories","Excerpt"]
    training = data.loc[data["Set"] == "training",cols]   
    development = data.loc[data["Set"] == "validation",cols]   
    test = data.loc[data["Set"] == "test",cols]

    training.to_csv(write_dir / "train.tsv", sep="\t", header=False, index=False)
    development.to_csv(write_dir / "dev.tsv", sep="\t", header=False, index=False)
    test.to_csv(write_dir / "test.tsv", sep="\t", header=False, index=False)

if __name__ == "__main__":
    main()