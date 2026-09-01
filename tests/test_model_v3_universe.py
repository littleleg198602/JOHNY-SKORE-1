from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from market_checker_app.model_v3.universe import (
    SQLiteUniverseStore,
    normalize_universe_snapshot,
)


class UniverseTests(unittest.TestCase):
    def test_snapshot_requires_explicit_date_and_fills_default_benchmark(self) -> None:
        frame = pd.DataFrame(
            {
                "Yahoo ticker": ["MSFT", "AAPL"],
                "Sector": ["Technology", "Technology"],
            }
        )
        normalized = normalize_universe_snapshot(
            frame,
            as_of_date="2025-01-03",
            source="watchlist.xlsx",
            observed_at=datetime(2025, 1, 4, tzinfo=timezone.utc),
        )
        self.assertEqual(normalized["ticker"].tolist(), ["AAPL", "MSFT"])
        self.assertEqual(normalized["benchmark"].unique().tolist(), ["SPY"])
        self.assertEqual(normalized["as_of_date"].iloc[0], pd.Timestamp("2025-01-03", tz="UTC"))

    def test_duplicate_membership_is_rejected(self) -> None:
        frame = pd.DataFrame({"ticker": ["AAPL", "AAPL"]})
        with self.assertRaisesRegex(ValueError, "duplicate"):
            normalize_universe_snapshot(
                frame,
                as_of_date="2025-01-03",
                source="test",
            )

    def test_load_uses_latest_complete_snapshot_not_current_rows(self) -> None:
        first = normalize_universe_snapshot(
            pd.DataFrame({"ticker": ["AAPL", "MSFT"]}),
            as_of_date="2025-01-01",
            source="snapshot-1",
        )
        second = normalize_universe_snapshot(
            pd.DataFrame({"ticker": ["AAPL", "NVDA"]}),
            as_of_date="2025-02-01",
            source="snapshot-2",
        )
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteUniverseStore(Path(directory) / "universe.db")
            store.upsert(first)
            store.upsert(second)
            loaded = store.load(as_of_date="2025-01-15")
            self.assertEqual(loaded["ticker"].tolist(), ["AAPL", "MSFT"])
            self.assertEqual(loaded["source"].unique().tolist(), ["snapshot-1"])


if __name__ == "__main__":
    unittest.main()
