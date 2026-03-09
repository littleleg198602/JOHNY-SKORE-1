from __future__ import annotations

import pandas as pd


def build_delta_df(current_df: pd.DataFrame, previous_df: pd.DataFrame) -> pd.DataFrame:
    merge = current_df.merge(previous_df, on="Ticker", suffixes=("_curr", "_prev"))
    for field in ["TotalScore(0-100)", "NewsScore(0-50)", "TechScore(0-50)", "YahooScore(-20..20)"]:
        merge[f"Delta_{field}"] = merge[f"{field}_curr"] - merge[f"{field}_prev"]
    merge["SignalChanged"] = merge["Signal_curr"] != merge["Signal_prev"]
    cols = [
        "Ticker",
        "TotalScore(0-100)_prev",
        "TotalScore(0-100)_curr",
        "Delta_TotalScore(0-100)",
        "Delta_NewsScore(0-50)",
        "Delta_TechScore(0-50)",
        "Delta_YahooScore(-20..20)",
        "Signal_prev",
        "Signal_curr",
        "SignalChanged",
    ]
    return merge[cols].sort_values("Delta_TotalScore(0-100)", key=lambda s: s.abs(), ascending=False)
