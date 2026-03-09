from __future__ import annotations

from pathlib import Path

import pandas as pd

from market_checker_app.config import EXCEL_FILENAME_PREFIX
from market_checker_app.exporters.delta_builder import build_delta_df


def find_previous_workbook(outdir: str) -> str | None:
    files = sorted(Path(outdir).glob(f"{EXCEL_FILENAME_PREFIX}_*.xlsx"), key=lambda p: p.stat().st_mtime, reverse=True)
    return str(files[0]) if files else None


def compare_with_previous(current_df: pd.DataFrame, outdir: str) -> pd.DataFrame | None:
    prev = find_previous_workbook(outdir)
    if not prev:
        return None
    try:
        prev_df = pd.read_excel(prev, sheet_name="Signals")
    except Exception:
        return None
    if "Ticker" not in prev_df.columns:
        return None
    return build_delta_df(current_df, prev_df)
