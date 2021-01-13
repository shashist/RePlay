# pylint: disable-all
import logging
import multiprocessing
import unittest
import warnings
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from pyspark.ml.linalg import DenseVector
from pyspark.sql import DataFrame, SparkSession
from replay.session_handler import get_spark_session


def unify_dataframe(data_frame: DataFrame):
    pandas_df = data_frame.toPandas()
    columns_to_sort_by: List[str] = []

    if len(pandas_df) == 0:
        columns_to_sort_by = pandas_df.columns
    else:
        for column in pandas_df.columns:
            if not type(pandas_df[column][0]) in {
                DenseVector,
                list,
                np.ndarray,
            }:
                columns_to_sort_by.append(column)

    return (
        pandas_df[sorted(data_frame.columns)]
        .sort_values(by=sorted(columns_to_sort_by))
        .reset_index(drop=True)
    )


def sparkDataFrameEqual(df1: DataFrame, df2: DataFrame):
    return pd.testing.assert_frame_equal(
        unify_dataframe(df1), unify_dataframe(df2), check_like=True
    )


class PySparkTest(unittest.TestCase):
    spark: SparkSession

    def assertSparkDataFrameEqual(
        self, df1: DataFrame, df2: DataFrame, msg: Optional[str] = None
    ) -> None:
        try:
            sparkDataFrameEqual(df1, df2)
        except AssertionError as e:
            raise self.failureException(msg) from e

    def assertDictAlmostEqual(
        self, d1: Dict, d2: Dict, msg: Optional[str] = None
    ) -> None:
        try:
            self.assertSetEqual(set(d1.keys()), set(d2.keys()))
            for key in d1:
                self.assertAlmostEqual(d1[key], d2[key])
        except AssertionError as e:
            raise self.failureException(msg) from e

    @classmethod
    def setUpClass(cls):
        multiprocessing.set_start_method("spawn", force=True)
        logger = logging.getLogger("replay")
        logger.setLevel("WARN")
        warnings.filterwarnings(action="ignore", category=ResourceWarning)
        cls.spark = get_spark_session(1, 1)
