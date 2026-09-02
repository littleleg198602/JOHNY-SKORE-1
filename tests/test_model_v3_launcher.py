from __future__ import annotations

from pathlib import Path
import unittest


class LauncherTests(unittest.TestCase):
    def test_windows_launcher_runs_full_universe_import(self) -> None:
        launcher = Path(__file__).parents[1] / "Spustit_Model_V3_Import.bat"
        content = launcher.read_text(encoding="utf-8")
        self.assertIn("--mt5-watchlist", content)
        self.assertIn("--snapshot-date", content)
        self.assertIn("--db", content)
        self.assertIn("model_v3_prices.db", content)
        self.assertIn("pause", content.lower())


if __name__ == "__main__":
    unittest.main()
