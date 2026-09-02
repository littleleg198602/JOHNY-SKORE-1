from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from market_checker_app.model_v3.import_prices import (
    normalize_tickers,
    persist_universe_snapshot,
    read_tickers,
)
from market_checker_app.model_v3.universe import SQLiteUniverseStore


class ImportPricesTests(unittest.TestCase):
    def test_normalize_tickers_is_stable_and_deduplicates(self) -> None:
        self.assertEqual(
            normalize_tickers([" aapl ", "MSFT", "AAPL", "", None, "ticker"]),
            ["AAPL", "MSFT"],
        )

    def test_read_tickers_from_text_supports_comments_and_separators(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tickers.txt"
            path.write_text("AAPL, MSFT # USA\n\nTSLA;NVDA\n", encoding="utf-8")
            self.assertEqual(read_tickers(path), ["AAPL", "MSFT", "TSLA", "NVDA"])

    def test_read_tickers_from_text_supports_whitespace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tickers.txt"
            path.write_text("AAPL MSFT\nTSLA\tNVDA\n", encoding="utf-8")
            self.assertEqual(read_tickers(path), ["AAPL", "MSFT", "TSLA", "NVDA"])

    def test_read_tickers_from_csv_prefers_named_column(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tickers.csv"
            path.write_text("Name,Yahoo ticker\nApple,AAPL\nMicrosoft,MSFT\n", encoding="utf-8")
            self.assertEqual(read_tickers(path), ["AAPL", "MSFT"])

    def test_persist_universe_snapshot_uses_the_complete_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "model.db"
            rows = persist_universe_snapshot(
                ["AAPL", "MSFT"],
                db_path=db_path,
                as_of_date="2026-09-02",
                source="test",
            )
            self.assertEqual(rows, 2)
            loaded = SQLiteUniverseStore(db_path).load(as_of_date="2026-09-02")
            self.assertEqual(loaded["ticker"].tolist(), ["AAPL", "MSFT"])
            self.assertEqual(loaded["benchmark"].unique().tolist(), ["SPY"])


if __name__ == "__main__":
    unittest.main()
