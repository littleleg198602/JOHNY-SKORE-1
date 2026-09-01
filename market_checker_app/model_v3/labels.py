from __future__ import annotations

from collections.abc import Iterable

import pandas as pd


def build_forward_labels(
    frame: pd.DataFrame,
    *,
    horizons: Iterable[int] = (5, 20, 60),
    ticker_col: str = "ticker",
    date_col: str = "date",
    price_col: str = "adj_close",
    benchmark_col: str = "benchmark_adj_close",
    minimum_edge_bps: float = 0.0,
) -> pd.DataFrame:
    """Append fixed-horizon future-return labels.

    The labels are intentionally created in a separate step from features.
    A row is usable for horizon ``h`` only when a price exactly ``h`` panel
    observations later exists.  The benchmark is expected to be repeated for
    every ticker/date row, which keeps the function compatible with a normal
    long panel.
    """

    required = {ticker_col, date_col, price_col, benchmark_col}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"Missing required label columns: {', '.join(missing)}")
    if frame.duplicated([ticker_col, date_col]).any():
        raise ValueError("Label panel contains duplicate ticker/date observations")

    result = frame.copy()
    result[date_col] = pd.to_datetime(result[date_col], utc=True, errors="raise")
    result[price_col] = pd.to_numeric(result[price_col], errors="coerce")
    result[benchmark_col] = pd.to_numeric(result[benchmark_col], errors="coerce")
    result = result.sort_values([ticker_col, date_col]).reset_index(drop=True)
    grouped_price = result.groupby(ticker_col, sort=False)[price_col]
    grouped_benchmark = result.groupby(ticker_col, sort=False)[benchmark_col]
    edge = float(minimum_edge_bps) / 10_000.0

    normalized_horizons = sorted({int(value) for value in horizons})
    if not normalized_horizons or any(value <= 0 for value in normalized_horizons):
        raise ValueError("Horizons must contain positive integers")

    for horizon in normalized_horizons:
        future_price = grouped_price.shift(-horizon)
        future_benchmark = grouped_benchmark.shift(-horizon)
        current_price = result[price_col]
        current_benchmark = result[benchmark_col]
        stock_return = future_price / current_price - 1.0
        benchmark_return = future_benchmark / current_benchmark - 1.0
        excess_return = stock_return - benchmark_return
        result[f"future_return_{horizon}d"] = stock_return
        result[f"benchmark_return_{horizon}d"] = benchmark_return
        result[f"excess_return_{horizon}d"] = excess_return
        outperform = pd.Series(pd.NA, index=result.index, dtype="Int64")
        valid = excess_return.notna()
        outperform.loc[valid] = (excess_return.loc[valid] > edge).astype("int64")
        result[f"outperform_{horizon}d"] = outperform

    return result
