from __future__ import annotations

from pathlib import Path

import pandas as pd
from pandas.api.types import is_datetime64tz_dtype

from market_checker_app.config import EXCEL_FILENAME_PREFIX
from market_checker_app.utils.dates import now_local_naive


def _strip_timezones(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy where timezone-aware datetime columns are timezone-naive."""
    cleaned = df.copy()
    for col in cleaned.columns:
        if is_datetime64tz_dtype(cleaned[col]):
            cleaned[col] = cleaned[col].dt.tz_localize(None)
    if is_datetime64tz_dtype(cleaned.index):
        cleaned.index = cleaned.index.tz_localize(None)
    return cleaned


def export_run(outdir: str, signals_df: pd.DataFrame, sources_df: pd.DataFrame, articles_df: pd.DataFrame, dashboard_tables: dict[str, pd.DataFrame], delta_df: pd.DataFrame | None = None) -> str:
    Path(outdir).mkdir(parents=True, exist_ok=True)
    ts = now_local_naive().strftime("%Y%m%d_%H%M%S")
    outpath = str(Path(outdir) / f"{EXCEL_FILENAME_PREFIX}_{ts}.xlsx")
    with pd.ExcelWriter(outpath, engine="openpyxl") as writer:
        signals_df = _strip_timezones(signals_df)
        sources_df = _strip_timezones(sources_df)
        articles_df = _strip_timezones(articles_df)
        dashboard_tables = {name: _strip_timezones(df) for name, df in dashboard_tables.items()}

        signals_df.to_excel(writer, sheet_name="Signals", index=False)
        sources_df.to_excel(writer, sheet_name="Sources", index=False)
        articles_df.to_excel(writer, sheet_name="Articles", index=False)
        dash = pd.concat({k: v for k, v in dashboard_tables.items()}, names=["Section"])
        dash = _strip_timezones(dash)
        dash.to_excel(writer, sheet_name="Dashboard")
        if delta_df is not None:
            delta_df = _strip_timezones(delta_df)
            delta_df.to_excel(writer, sheet_name="DeltaVsPrev", index=False)
    return outpath
