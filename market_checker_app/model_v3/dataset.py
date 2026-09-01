from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from .labels import build_forward_labels
from .price_features import build_price_features, cross_sectional_rank
from .universe import UNIVERSE_COLUMNS


def _require_columns(frame: pd.DataFrame, columns: Iterable[str], name: str) -> None:
    missing = sorted(set(columns).difference(frame.columns))
    if missing:
        raise ValueError(f"{name} is missing: {', '.join(missing)}")


def attach_point_in_time_universe(
    prices: pd.DataFrame,
    universe: pd.DataFrame,
    *,
    ticker_col: str = "ticker",
    date_col: str = "date",
) -> pd.DataFrame:
    """Attach the latest available membership snapshot to each price row."""

    _require_columns(prices, [ticker_col, date_col, "adj_close"], "Price panel")
    _require_columns(universe, UNIVERSE_COLUMNS, "Universe panel")
    if prices.duplicated([ticker_col, date_col]).any():
        raise ValueError("Price panel contains duplicate ticker/date observations")
    if universe.duplicated(["ticker", "as_of_date"]).any():
        raise ValueError("Universe panel contains duplicate ticker/as_of_date observations")

    left = prices.copy()
    left[date_col] = pd.to_datetime(left[date_col], utc=True, errors="raise").astype(
        "datetime64[ns, UTC]"
    )
    left[ticker_col] = left[ticker_col].astype(str).str.strip().str.upper()
    # merge_asof requires the ``on`` key to be globally sorted, even when a
    # ``by`` key is present. Sort by date first, then restore panel order below.
    left = left.sort_values([date_col, ticker_col]).reset_index(drop=True)

    right = universe.copy()
    right["as_of_date"] = pd.to_datetime(
        right["as_of_date"], utc=True, errors="raise"
    ).astype("datetime64[ns, UTC]")
    right["ticker"] = right["ticker"].astype(str).str.strip().str.upper()
    right = right.sort_values(["as_of_date", "ticker"]).reset_index(drop=True)

    # A snapshot represents a complete universe. First select one complete
    # snapshot date for every price date; otherwise a ticker omitted from a
    # newer snapshot would incorrectly survive from an older snapshot.
    snapshot_dates = right[["as_of_date"]].drop_duplicates().sort_values("as_of_date")
    date_map = pd.merge_asof(
        left[[date_col]].drop_duplicates().sort_values(date_col),
        snapshot_dates,
        left_on=date_col,
        right_on="as_of_date",
        direction="backward",
        allow_exact_matches=True,
    )
    left = left.merge(date_map, on=date_col, how="left", validate="many_to_one")
    result = left.merge(
        right,
        left_on=[ticker_col, "as_of_date"],
        right_on=["ticker", "as_of_date"],
        how="inner",
        validate="many_to_one",
        suffixes=("", "_membership"),
    )
    if ticker_col != "ticker":
        result = result.drop(columns=["ticker"])
    return result.sort_values([ticker_col, date_col]).reset_index(drop=True)


def attach_benchmark_prices(
    frame: pd.DataFrame,
    prices: pd.DataFrame,
    *,
    date_col: str = "date",
    benchmark_col: str = "benchmark",
    price_col: str = "adj_close",
    output_column: str = "benchmark_adj_close",
) -> pd.DataFrame:
    """Join benchmark prices by the explicit benchmark ticker and date."""

    _require_columns(frame, [date_col, benchmark_col], "Universe-enriched panel")
    _require_columns(prices, ["ticker", date_col, price_col], "Price panel")
    benchmark_prices = prices[["ticker", date_col, price_col]].copy()
    benchmark_prices["ticker"] = benchmark_prices["ticker"].astype(str).str.strip().str.upper()
    benchmark_prices[date_col] = pd.to_datetime(
        benchmark_prices[date_col], utc=True, errors="raise"
    ).astype("datetime64[ns, UTC]")
    benchmark_prices = benchmark_prices.rename(
        columns={"ticker": "benchmark_join_ticker", price_col: output_column}
    )

    result = frame.copy()
    result[date_col] = pd.to_datetime(result[date_col], utc=True, errors="raise").astype(
        "datetime64[ns, UTC]"
    )
    result[benchmark_col] = result[benchmark_col].astype(str).str.strip().str.upper()
    result = result.merge(
        benchmark_prices,
        left_on=[benchmark_col, date_col],
        right_on=["benchmark_join_ticker", date_col],
        how="left",
        validate="many_to_one",
    ).drop(columns=["benchmark_join_ticker"])
    return result


def build_model_panel(
    prices: pd.DataFrame,
    universe: pd.DataFrame,
    *,
    horizons: Iterable[int] = (5, 20, 60),
    rank_columns: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Build the chronological feature/label panel consumed by the model.

    Only rows covered by a dated universe snapshot are retained. Benchmark
    prices are joined before labels are created; features remain backward-only
    and labels are added as a separate forward-looking step.
    """

    enriched = attach_point_in_time_universe(prices, universe)
    enriched = attach_benchmark_prices(enriched, prices)
    enriched = build_price_features(enriched)
    enriched = cross_sectional_rank(enriched, columns=rank_columns or (
        "ret_5d",
        "ret_21d",
        "momentum_12_1",
        "volatility_20d",
        "volatility_60d",
        "dollar_volume_20d",
        "drawdown_252d",
    ))
    return build_forward_labels(enriched, horizons=horizons)
