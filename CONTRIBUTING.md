# Contribution guide[WIP]

## Before submitting PR

Check codestyle
```bash
pycodestyle --ignore=E203,E231,E501,W503,W605 --max-doc-length=160 replay tests
```

Check linting
```bash
pylint --rcfile=.pylintrc replay
```

Run tests
```bash
pytest tests
```

## Good PR examples[WIP]

#### Bug:

- todo

#### New feature:

- todo



## Adding new model[WIP]

Typically for new model you need to update inner methods for `train`, `predict` and `predict_pairs`.

For details check

TODO: [predict structure for RePlay models](https://miro.com/app/board/uXjVOlaS1B4=/?share_link_id=536004808955)
 
