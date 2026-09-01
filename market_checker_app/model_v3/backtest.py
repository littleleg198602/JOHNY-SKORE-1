from __future__ import annotations

import math

import pandas as pd


def _spearman_by_date(frame: pd.DataFrame, date_col: str, prediction_col: str, target_col: str) -> float | None:
    values: list[float] = []
    for _, group in frame.groupby(date_col, sort=True):
        usable = group[[prediction_col, target_col]].dropna()
        if len(usable) < 2 or usable[prediction_col].nunique() < 2 or usable[target_col].nunique() < 2:
            continue
        correlation = usable[prediction_col].corr(usable[target_col], method="spearman")
        if pd.notna(correlation):
            values.append(float(correlation))
    return float(sum(values) / len(values)) if values else None


def evaluate_cross_section(
    frame: pd.DataFrame,
    *,
    date_col: str = "date",
    prediction_col: str = "prediction",
    target_col: str = "excess_return_5d",
    outperform_col: str = "outperform_5d",
    top_fraction: float = 0.10,
    bottom_fraction: float = 0.10,
) -> dict[str, float | int | None]:
    """Evaluate ranking quality before portfolio construction.

    This is deliberately a small, deterministic metric layer. It does not
    assume that every prediction becomes a trade and does not hide missing
    future labels.
    """

    required = {date_col, prediction_col, target_col}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"Missing backtest columns: {', '.join(missing)}")
    if not 0 < top_fraction <= 0.5 or not 0 < bottom_fraction <= 0.5:
        raise ValueError("Top and bottom fractions must be in (0, 0.5]")

    usable = frame[list(required.union({outperform_col}).intersection(frame.columns))].copy()
    usable[prediction_col] = pd.to_numeric(usable[prediction_col], errors="coerce")
    usable[target_col] = pd.to_numeric(usable[target_col], errors="coerce")
    usable = usable.dropna(subset=[date_col, prediction_col, target_col])
    if usable.empty:
        return {
            "observations": 0,
            "dates": 0,
            "rank_ic": None,
            "top_bottom_spread": None,
            "top_fraction_mean_return": None,
            "top_fraction_outperform_rate": None,
        }

    spreads: list[float] = []
    top_returns: list[float] = []
    top_hit_rates: list[float] = []
    for _, group in usable.groupby(date_col, sort=True):
        group = group.sort_values(prediction_col, ascending=False)
        top_n = max(1, math.ceil(len(group) * top_fraction))
        bottom_n = max(1, math.ceil(len(group) * bottom_fraction))
        top = group.head(top_n)
        bottom = group.tail(bottom_n)
        spreads.append(float(top[target_col].mean() - bottom[target_col].mean()))
        top_returns.append(float(top[target_col].mean()))
        if outperform_col in top.columns:
            hit = pd.to_numeric(top[outperform_col], errors="coerce").dropna()
            if not hit.empty:
                top_hit_rates.append(float(hit.mean()))

    return {
        "observations": int(len(usable)),
        "dates": int(usable[date_col].nunique()),
        "rank_ic": _spearman_by_date(usable, date_col, prediction_col, target_col),
        "top_bottom_spread": float(sum(spreads) / len(spreads)) if spreads else None,
        "top_fraction_mean_return": float(sum(top_returns) / len(top_returns)) if top_returns else None,
        "top_fraction_outperform_rate": float(sum(top_hit_rates) / len(top_hit_rates)) if top_hit_rates else None,
    }
