from __future__ import annotations

from pathlib import Path

import pandas as pd

from market_checker_app.config import EXCEL_FILENAME_PREFIX
from market_checker_app.utils.dates import now_local_naive


def export_run(outdir: str, signals_df: pd.DataFrame, sources_df: pd.DataFrame, articles_df: pd.DataFrame, dashboard_tables: dict[str, pd.DataFrame], delta_df: pd.DataFrame | None = None) -> str:
    Path(outdir).mkdir(parents=True, exist_ok=True)
    ts = now_local_naive().strftime("%Y%m%d_%H%M%S")
    outpath = str(Path(outdir) / f"{EXCEL_FILENAME_PREFIX}_{ts}.xlsx")
    with pd.ExcelWriter(outpath, engine="openpyxl") as writer:
        signals_df.to_excel(writer, sheet_name="Signals", index=False)
        sources_df.to_excel(writer, sheet_name="Sources", index=False)
        articles_df.to_excel(writer, sheet_name="Articles", index=False)
        dash = pd.concat({k: v for k, v in dashboard_tables.items()}, names=["Section"])
        dash.to_excel(writer, sheet_name="Dashboard")
        if delta_df is not None:
            delta_df.to_excel(writer, sheet_name="DeltaVsPrev", index=False)
    return outpath
