from __future__ import annotations

import unittest

import pandas as pd

from market_checker_app.model_v3.baseline import (
    BaselineConfig,
    ElasticNetBaseline,
    add_momentum_baseline,
    run_walk_forward_baseline,
)
from market_checker_app.model_v3.walk_forward import make_walk_forward_windows


def _training_frame() -> pd.DataFrame:
    rows = []
    for date_number in range(1, 21):
        for ticker_number, ticker in enumerate(["AAA", "BBB", "CCC"]):
            feature = float(date_number + ticker_number)
            rows.append(
                {
                    "date": pd.Timestamp("2020-01-01", tz="UTC") + pd.Timedelta(days=date_number),
                    "ticker": ticker,
                    "signal_feature": feature,
                    "secondary_feature": float(ticker_number),
                    "target": feature * 0.02 + ticker_number * 0.01,
                    "label": int(ticker_number > 0),
                    "momentum_12_1": feature,
                }
            )
    return pd.DataFrame(rows)


class BaselineTests(unittest.TestCase):
    def test_elastic_net_outputs_return_and_probability(self) -> None:
        frame = _training_frame()
        model = ElasticNetBaseline(
            BaselineConfig(
                feature_columns=("signal_feature", "secondary_feature"),
                target_column="target",
                label_column="label",
            )
        ).fit(frame)
        predicted = model.predict(frame.iloc[-3:])
        self.assertIn("prediction", predicted.columns)
        self.assertIn("probability_outperform", predicted.columns)
        self.assertTrue(predicted["probability_outperform"].between(0, 1).all())

    def test_momentum_benchmark_is_transparent(self) -> None:
        frame = _training_frame()
        result = add_momentum_baseline(frame)
        self.assertEqual(result["momentum_prediction"].tolist(), result["momentum_12_1"].tolist())

    def test_missing_classification_labels_use_a_safe_prior(self) -> None:
        frame = _training_frame()
        frame["label"] = pd.NA
        model = ElasticNetBaseline(
            BaselineConfig(
                feature_columns=("signal_feature", "secondary_feature"),
                target_column="target",
                label_column="label",
            )
        ).fit(frame)
        predicted = model.predict(frame.iloc[:2])
        self.assertEqual(predicted["probability_outperform"].tolist(), [0.0, 0.0])

    def test_walk_forward_refits_and_marks_test_windows(self) -> None:
        frame = _training_frame()
        windows = make_walk_forward_windows(
            frame["date"].drop_duplicates(),
            train_periods=8,
            validation_periods=2,
            test_periods=2,
            step_periods=2,
            embargo_periods=1,
        )
        result = run_walk_forward_baseline(
            frame,
            windows,
            config=BaselineConfig(
                feature_columns=("signal_feature", "secondary_feature"),
                target_column="target",
                label_column="label",
            ),
        )
        self.assertFalse(result.empty)
        self.assertTrue((result["test_start"] <= result["date"]).all())
        self.assertEqual(result["walk_forward_window"].nunique(), len(windows))


if __name__ == "__main__":
    unittest.main()
