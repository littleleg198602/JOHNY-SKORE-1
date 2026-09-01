from __future__ import annotations

from datetime import datetime, timezone
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from market_checker_app.model_v3 import SQLitePricePanelStore, normalize_price_frame


class ModelV3PricePanelTests(unittest.TestCase):
    def _provider_frame(self) -> pd.DataFrame:
        index = pd.to_datetime(["2024-01-02", "2024-01-04"])
        return pd.DataFrame(
            {
                "Open": [100.0, 102.0],
                "High": [101.0, 103.0],
                "Low": [99.0, 101.0],
                "Close": [100.5, 102.5],
                "Adj Close": [100.5, 102.0],
                "Volume": [1000, 1200],
            },
            index=index,
        )

    def test_normalization_preserves_gaps_and_uses_utc(self) -> None:
        normalized = normalize_price_frame(
            self._provider_frame(),
            ticker="aaa",
            source="fixture",
            observed_at=datetime(2024, 1, 5, tzinfo=timezone.utc),
        )
        self.assertEqual(list(normalized["ticker"].unique()), ["AAA"])
        self.assertEqual(len(normalized), 2)
        self.assertEqual(str(normalized.loc[0, "date"].tz), "UTC")
        self.assertEqual(normalized["date"].iloc[1] - normalized["date"].iloc[0], pd.Timedelta(days=2))
        self.assertEqual(normalized.loc[1, "adj_close"], 102.0)

    def test_duplicate_provider_dates_are_rejected(self) -> None:
        duplicate = pd.concat([self._provider_frame(), self._provider_frame().iloc[[0]]])
        with self.assertRaisesRegex(ValueError, "duplicate dates"):
            normalize_price_frame(duplicate, ticker="AAA", source="fixture")

    def test_sqlite_round_trip_and_upsert(self) -> None:
        normalized = normalize_price_frame(self._provider_frame(), ticker="AAA", source="fixture")
        with tempfile.TemporaryDirectory() as directory:
            store = SQLitePricePanelStore(Path(directory) / "panel.db")
            self.assertEqual(store.upsert(normalized), 2)
            self.assertEqual(store.upsert(normalized), 2)
            loaded = store.load(tickers=["aaa"])
            self.assertEqual(len(loaded), 2)
            self.assertEqual(loaded["ticker"].tolist(), ["AAA", "AAA"])
            self.assertEqual(loaded["adj_close"].tolist(), [100.5, 102.0])


if __name__ == "__main__":
    unittest.main()
