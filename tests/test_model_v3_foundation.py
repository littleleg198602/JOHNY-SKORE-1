from __future__ import annotations

import unittest

import pandas as pd

from market_checker_app.model_v3 import (
    build_forward_labels,
    build_price_features,
    cross_sectional_rank,
    evaluate_cross_section,
    make_walk_forward_windows,
    select_window,
)


def _panel() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=12, freq="D", tz="UTC")
    rows: list[dict[str, object]] = []
    for ticker, start in (("AAA", 100.0), ("BBB", 90.0)):
        for index, date in enumerate(dates):
            rows.append(
                {
                    "ticker": ticker,
                    "date": date,
                    "adj_close": start + index * (2.0 if ticker == "AAA" else 0.5),
                    "benchmark_adj_close": 100.0 + index,
                    "volume": 1_000_000 + index * 10_000,
                }
            )
    return pd.DataFrame(rows)


class ModelV3FoundationTests(unittest.TestCase):
    def test_price_features_are_lagged_and_cross_sectional_ranks_work(self) -> None:
        source = _panel()
        features = build_price_features(source)
        early = features[features["date"] == pd.Timestamp("2024-01-02", tz="UTC")]
        self.assertTrue(early["ret_1d"].notna().all())
        self.assertTrue(early["ret_5d"].isna().all())
        ranked = cross_sectional_rank(features, columns=["ret_1d"])
        self.assertTrue(ranked["ret_1d_rank"].dropna().between(0, 1).all())

    def test_future_labels_use_fixed_forward_observation(self) -> None:
        labels = build_forward_labels(_panel(), horizons=[1, 5], minimum_edge_bps=0)
        aaa = labels[labels["ticker"] == "AAA"].sort_values("date").reset_index(drop=True)
        expected = (aaa.loc[1, "adj_close"] / aaa.loc[0, "adj_close"]) - 1
        self.assertAlmostEqual(float(aaa.loc[0, "future_return_1d"]), expected)
        self.assertTrue(pd.isna(aaa.loc[len(aaa) - 1, "future_return_1d"]))
        self.assertEqual(int(aaa.loc[0, "outperform_1d"]), 1)

    def test_walk_forward_has_chronological_gaps(self) -> None:
        dates = pd.date_range("2024-01-01", periods=20, freq="D", tz="UTC")
        windows = make_walk_forward_windows(
            list(dates),
            train_periods=8,
            validation_periods=3,
            test_periods=3,
            step_periods=3,
            embargo_periods=1,
        )
        self.assertEqual(len(windows), 2)
        first = windows[0]
        self.assertLess(first.train_end, first.validation_start)
        self.assertLess(first.validation_end, first.test_start)
        self.assertEqual(len(select_window(pd.DataFrame({"date": dates}), first, "test")), 3)

    def test_cross_section_evaluation_rewards_correct_ranking(self) -> None:
        frame = pd.DataFrame(
            {
                "date": ["2024-01-01"] * 4,
                "prediction": [4.0, 3.0, 2.0, 1.0],
                "excess_return_5d": [0.04, 0.03, -0.01, -0.02],
                "outperform_5d": [1, 1, 0, 0],
            }
        )
        metrics = evaluate_cross_section(frame, top_fraction=0.25, bottom_fraction=0.25)
        self.assertEqual(metrics["observations"], 4)
        self.assertEqual(metrics["dates"], 1)
        self.assertGreater(float(metrics["rank_ic"]), 0.9)
        self.assertAlmostEqual(float(metrics["top_bottom_spread"]), 0.06)


if __name__ == "__main__":
    unittest.main()
