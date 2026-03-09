from __future__ import annotations

import pandas as pd


def build_dashboard_tables(signals_df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    df = signals_df.copy()
    return {
        "top_total": df.sort_values("TotalScore(0-100)", ascending=False).head(20),
        "weekly_drops": df[df["LastWeekMonFriChangePct"].fillna(0) < 0].sort_values("LastWeekMonFriChangePct", ascending=True).head(20),
        "m1_drops": df[df["Last1MChangePct"].fillna(0) < 0].sort_values("Last1MChangePct", ascending=True).head(20),
        "m3_drops": df[df["Last3MChangePct"].fillna(0) < 0].sort_values("Last3MChangePct", ascending=True).head(20),
        "top_mcap": df[df["MarketCapUSD"].notna()].sort_values("MarketCapUSD", ascending=False).head(20),
        "bottom_mcap": df[df["MarketCapUSD"].notna()].sort_values("MarketCapUSD", ascending=True).head(20),
    }
