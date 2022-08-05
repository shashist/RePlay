# RePlay

RePlay is a library providing tools for all stages of creating a recommendation system, from data preprocessing to model evaluation and comparison.

## Quickstart
```bash
pip install replay-rec
```


```python
from rs_datasets import MovieLens

from replay.data_preparator import DataPreparator, Indexer
from replay.metrics import HitRate, NDCG
from replay.models import KNN
from replay.session_handler import State
from replay.splitters import UserSplitter

spark = State().session

ml_1m = MovieLens("1m")

# data preprocessing
preparator = DataPreparator()
log = preparator.transform(
    columns_mapping={'relevance': 'rating'}, data=ml_1m.ratings
)
indexer = Indexer(user_col='user_id', item_col='item_id')
indexer.fit(users=log.select('user_id'))
log_replay = indexer.transform(df=log)

# data splitting
user_splitter = UserSplitter(
    item_test_size=10,
    user_test_size=500,
    drop_cold_items=True,
    drop_cold_users=True,
    shuffle=True,
    seed=42,
)
train, test = user_splitter.split(log_replay)

# model training
model = KNN()
model.fit(train)

# model inference
recs = model.predict(
    log=train,
    k=K,
    users=test.select('user_idx').distinct(),
    filter_seen_items=True,
)

# model evaluation
metrics = Experiment(test,  {NDCG(): K, HitRate(): K})
metrics.add_result("knn", recs)
```

## Overview

RePlay uses PySpark to handle big data.

[Framework architecture](https://miro.com/app/board/uXjVOhTSHK0=/?share_link_id=748466292621)

You can

- [Filter and split data, train models, optimize hyperparameters, evaluate predictions with metrics](experiments/01_replay_basics.ipynb)
- [Create reproducible model comparison](experiments/02_models_comparison.ipynb)
- [Use pyspark for feature preprocessing](experiments/03_features_preprocessing_and_lightFM.ipynb)
- Combine predictions from different models
- Create a two-level model


## Docs

[Documentation](https://sb-ai-lab.github.io/RePlay/)


### Installation

Use Linux machine with Python 3.7+, Java 8+ and C++ compiler. 

```bash
pip install replay-rec
```

It is preferable to use a virtual environment for your installation.

If you encounter an error during RePlay installation, check the [troubleshooting](https://sb-ai-lab.github.io/RePlay/pages/installation.html#troubleshooting) guide.
