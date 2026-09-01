from __future__ import annotations

from pathlib import Path
import unittest

import pandas as pd

from market_checker_app.model_v3.dataset import build_model_panel
from market_checker_app.model_v3.universe import normalize_universe_snapshot


def _prices() -> pd.DataFrame:
    rows = []
    dates = pd.date_range("2025-01-01", periods=12, freq="D", tz="UTC")
    for ticker, base in [("AAA", 100.0), ("BBB", 80.0), ("SPY", 400.0)]:
        for index, date in enumerate(dates):
            close = base + index * (2.0 if ticker == "AAA" else 1.0)
            rows.append(
                {
                    "ticker": ticker,
                    "date": date,
                    "open": close,
                    "high": close + 1,
                    "low": close - 1,
                    "close": close,
                    "adj_close": close,
                    "volume": 1000,
                    "source": "test",
                    "observed_at": date,
                }
            )
    return pd.DataFrame(rows)


class DatasetTests(unittest.TestCase):
    def test_model_panel_uses_latest_membership_snapshot_and_benchmark(self) -> None:
        first = normalize_universe_snapshot(
            pd.DataFrame({"ticker": ["AAA", "BBB"], "sector": ["Tech", "Finance"]}),
            as_of_date="2025-01-01",
            source="snapshot-1",
        )
        second = normalize_universe_snapshot(
            pd.DataFrame({"ticker": ["AAA"], "sector": ["Tech"]}),
            as_of_date="2025-01-07",
            source="snapshot-2",
        )
        universe = pd.concat([first, second], ignore_index=True)
        result = build_model_panel(_prices(), universe, horizons=(5,))

        before_change = result[result["date"] < pd.Timestamp("2025-01-07", tz="UTC")]
        after_change = result[result["date"] >= pd.Timestamp("2025-01-07", tz="UTC")]
        self.assertEqual(set(before_change["ticker"]), {"AAA", "BBB"})
        self.assertEqual(set(after_change["ticker"]), {"AAA"})
        self.assertTrue(result["benchmark_adj_close"].notna().all())
        self.assertIn("excess_return_5d", result.columns)
        self.assertIn("ret_5d_rank", result.columns)


if __name__ == "__main__":
    unittest.main()
