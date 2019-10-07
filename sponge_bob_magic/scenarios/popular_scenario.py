import logging
import os
from datetime import datetime
from typing import Dict, Tuple, TypeVar, Any

import joblib
import optuna
from pyspark.sql import SparkSession, DataFrame

from sponge_bob_magic.metrics.metrics import Metrics
from sponge_bob_magic.models.popular_recomennder import PopularRecommender
from sponge_bob_magic.validation_schemes import ValidationSchemes

TNum = TypeVar('TNum', int, float)


class PopularScenario:
    study: optuna.Study or None

    def __init__(self, spark: SparkSession):
        self.model = None
        self.spark = spark
        self.study = None

        self.seed = 1234

    def research(self,
                 params_grid: Dict[str, Tuple[TNum, TNum]],
                 log: DataFrame,
                 users: DataFrame or None,
                 items: DataFrame or None,
                 user_features: DataFrame or None = None,
                 item_features: DataFrame or None = None,
                 test_start: datetime or None = None,
                 test_size: float = None,
                 k: int = 10,
                 context: str or None = 'no_context',
                 to_filter_seen_items: bool = True,
                 n_trials: int = 10,
                 n_jobs: int = 1,
                 how_to_split: str = 'by_date',
                 path: str or None = None
                 ) -> Dict[str, Any]:
        splitter = ValidationSchemes(self.spark)

        logging.debug("Деление на трейн и тест")
        if how_to_split == 'by_date':
            train, test_input, test = splitter.log_split_by_date(
                log, test_start=test_start,
                drop_cold_users=False, drop_cold_items=True
            )
        elif how_to_split == 'randomly':
            train, test_input, test = splitter.log_split_randomly(
                log,
                drop_cold_users=False, drop_cold_items=True,
                seed=self.seed, test_size=test_size
            )
        else:
            raise ValueError(
                f"Значение how_to_split неверное ({how_to_split}), "
                "допустимые варианты: 'by_date' или 'randomly'")

        # рассчитываем все выборки перед подбором параметров
        train.checkpoint()
        test_input.checkpoint()
        test.checkpoint()
        logging.debug(f"Размер трейна:      {train.count()}")
        logging.debug(f"Размер теста_инпут: {test_input.count()}")
        logging.debug(f"Размер теста:       {test.count()}")

        self.model = PopularRecommender(self.spark)

        # если юзеров или айтемов нет, возьмем всех из лога,
        # чтобы не делать на каждый trial их заново
        if users is None:
            users = log.select('user_id').distinct()

        if items is None:
            items = log.select('item_id').distinct()

        users.checkpoint()
        items.checkpoint()

        # обучаем модель заранее, чтобы сохранить каунты
        # здесь происходит сохранение популярности items в checkpoint
        self.model.fit(log=train,
                       user_features=user_features,
                       item_features=item_features,
                       path=None)

        def objective(trial: optuna.Trial):
            if path is not None:
                joblib.dump(self.study,
                            os.path.join(path, "optuna_study.joblib"))

            alpha = trial.suggest_int(
                'alpha', params_grid['alpha'][0], params_grid['alpha'][1])
            beta = trial.suggest_int(
                'beta', params_grid['beta'][0], params_grid['beta'][1])

            params = {'alpha': alpha,
                      'beta': beta}
            self.model.set_params(**params)

            logging.debug("Предикт модели в оптимизации")
            # здесь как в фите делается checkpoint
            recs = self.model.predict(
                k=k,
                users=users, items=items,
                user_features=user_features,
                item_features=item_features,
                context=context,
                log=test,
                to_filter_seen_items=to_filter_seen_items
            )

            logging.debug("Подсчет метрики в оптимизации")
            metric_result = Metrics.hit_rate_at_k(recs, test, k=k)

            # вот так можно положить в trial еще метрики
            trial.set_user_attr('some_metric', 1.0)

            logging.debug(f"Метрика и параметры: {metric_result, params}")

            return metric_result

        logging.debug("Начало оптимизации параметров")
        sampler = optuna.samplers.RandomSampler()
        self.study = optuna.create_study(direction='maximize', sampler=sampler)
        self.study.optimize(objective, n_trials=n_trials, n_jobs=n_jobs)

        logging.debug(f"Лучшие значения метрики: {self.study.best_value}")
        logging.debug(f"Лучшие параметры: {self.study.best_params}")
        return self.study.best_params

    def production(self, params,
                   log: DataFrame,
                   users: DataFrame or None,
                   items: DataFrame or None,
                   user_features: DataFrame or None,
                   item_features: DataFrame or None,
                   k: int,
                   context: str or None,
                   to_filter_seen_items: bool
                   ) -> DataFrame:
        self.model = PopularRecommender(self.spark)
        self.model.set_params(**params)

        return self.model.fit_predict(k, users, items, context, log,
                                      user_features, item_features,
                                      to_filter_seen_items)


if __name__ == '__main__':
    spark_ = (SparkSession
              .builder
              .master('local[4]')
              .config('spark.driver.memory', '2g')
              .config("spark.sql.shuffle.partitions", "1")
              .appName('testing-pyspark')
              .enableHiveSupport()
              .getOrCreate())

    spark_.sparkContext.setCheckpointDir(os.environ['SPONGE_BOB_CHECKPOINTS'])

    data = [
        ["user1", "item1", 1.0, 'no_context', datetime(2019, 10, 8)],
        ["user2", "item2", 2.0, 'no_context', datetime(2019, 10, 9)],
        ["user1", "item3", 1.0, 'no_context', datetime(2019, 10, 10)],
        ["user1", "item1", 1.0, 'no_context', datetime(2019, 10, 11)],
        ["user1", "item2", 1.0, 'no_context', datetime(2019, 10, 12)],
        ["user3", "item3", 2.0, 'no_context', datetime(2019, 10, 13)],
    ]
    schema = ['user_id', 'item_id', 'relevance', 'context', 'timestamp']
    log_ = spark_.createDataFrame(data=data,
                                  schema=schema)

    popular_scenario = PopularScenario(spark_)
    popular_params_grid = {'alpha': (0, 100), 'beta': (0, 100)}

    best_params = popular_scenario.research(
        popular_params_grid,
        log_,
        users=None, items=None,
        user_features=None,
        item_features=None,
        test_start=datetime(2019, 10, 11),
        k=3, context='no_context',
        to_filter_seen_items=True,
        n_trials=4, n_jobs=4
    )

    print(best_params)

    recs_ = popular_scenario.production(
        best_params,
        log_,
        users=None,
        items=None,
        user_features=None,
        item_features=None,
        k=3,
        context='no_context',
        to_filter_seen_items=True
    )

    recs_.show()

    best_params = popular_scenario.research(
        popular_params_grid,
        log_,
        users=None, items=None,
        user_features=None,
        item_features=None,
        test_start=None,
        test_size=0.4,
        k=3, context='no_context',
        to_filter_seen_items=True,
        n_trials=4, n_jobs=1,
        how_to_split='randomly'
    )

    print(best_params)

    recs_ = popular_scenario.production(
        best_params,
        log_,
        users=None,
        items=None,
        user_features=None,
        item_features=None,
        k=3,
        context='no_context',
        to_filter_seen_items=True
    )

    recs_.show()