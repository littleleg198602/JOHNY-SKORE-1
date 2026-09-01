from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from market_checker_app.model_v3.import_prices import normalize_tickers, read_tickers


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

    def test_read_tickers_from_csv_prefers_named_column(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tickers.csv"
            path.write_text("Name,Yahoo ticker\nApple,AAPL\nMicrosoft,MSFT\n", encoding="utf-8")
            self.assertEqual(read_tickers(path), ["AAPL", "MSFT"])


if __name__ == "__main__":
    unittest.main()
