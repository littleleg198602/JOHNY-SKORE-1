from __future__ import annotations

from collections.abc import Iterable

import pandas as pd


DEFAULT_RETURN_WINDOWS = (1, 5, 10, 21, 63, 126, 252)
DEFAULT_RANK_COLUMNS = (
    "ret_5d",
    "ret_21d",
    "momentum_12_1",
    "volatility_20d",
    "volatility_60d",
    "dollar_volume_20d",
    "drawdown_252d",
)


def _validate_panel(
    frame: pd.DataFrame,
    *,
    ticker_col: str,
    date_col: str,
    price_col: str,
) -> None:
    required = {ticker_col, date_col, price_col}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"Missing required price-panel columns: {', '.join(missing)}")
    if frame.empty:
        raise ValueError("Price panel is empty")
    if frame.duplicated([ticker_col, date_col]).any():
        raise ValueError("Price panel contains duplicate ticker/date observations")
    prices = pd.to_numeric(frame[price_col], errors="coerce")
    if prices.isna().any() or (prices <= 0).any():
        raise ValueError("Price panel contains missing or non-positive prices")


def build_price_features(
    frame: pd.DataFrame,
    *,
    ticker_col: str = "ticker",
    date_col: str = "date",
    price_col: str = "adj_close",
    volume_col: str = "volume",
    return_windows: Iterable[int] = DEFAULT_RETURN_WINDOWS,
) -> pd.DataFrame:
    """Build lagged daily price/liquidity features without future information.

    ``frame`` must contain one observation per ticker/date.  The function
    accepts adjusted close prices for total-return-like price features; raw
    OHLCV and corporate-action handling belong in the data-ingestion layer.
    All rolling windows are backward-looking and are calculated independently
    for each ticker.
    """

    _validate_panel(
        frame,
        ticker_col=ticker_col,
        date_col=date_col,
        price_col=price_col,
    )
    result = frame.copy()
    result[date_col] = pd.to_datetime(result[date_col], utc=True, errors="raise")
    result[price_col] = pd.to_numeric(result[price_col], errors="raise")
    result = result.sort_values([ticker_col, date_col]).reset_index(drop=True)

    grouped_price = result.groupby(ticker_col, sort=False)[price_col]
    for window in sorted({int(value) for value in return_windows}):
        if window <= 0:
            raise ValueError("Return windows must be positive")
        result[f"ret_{window}d"] = grouped_price.pct_change(window)

    # 12-1 month momentum deliberately skips the most recent month.
    result["momentum_12_1"] = (
        grouped_price.shift(21) / grouped_price.shift(252) - 1.0
    )
    result["reversal_5d"] = result["ret_5d"]

    daily_return = result["ret_1d"]
    result["volatility_20d"] = daily_return.groupby(result[ticker_col]).transform(
        lambda values: values.rolling(20, min_periods=10).std()
    )
    result["volatility_60d"] = daily_return.groupby(result[ticker_col]).transform(
        lambda values: values.rolling(60, min_periods=30).std()
    )
    result["drawdown_252d"] = result[price_col] / result.groupby(ticker_col)[
        price_col
    ].transform(lambda values: values.rolling(252, min_periods=20).max()) - 1.0

    if volume_col in result.columns:
        volume = pd.to_numeric(result[volume_col], errors="coerce")
        result["dollar_volume"] = result[price_col] * volume
        result["dollar_volume_20d"] = result.groupby(ticker_col)[
            "dollar_volume"
        ].transform(lambda values: values.rolling(20, min_periods=5).mean())
        result["volume_zscore_20d"] = result.groupby(ticker_col)[
            "dollar_volume"
        ].transform(
            lambda values: (
                (values - values.rolling(20, min_periods=10).mean())
                / values.rolling(20, min_periods=10).std().replace(0, pd.NA)
            )
        )
    else:
        result["dollar_volume"] = pd.NA
        result["dollar_volume_20d"] = pd.NA
        result["volume_zscore_20d"] = pd.NA

    return result


def cross_sectional_rank(
    frame: pd.DataFrame,
    *,
    date_col: str = "date",
    columns: Iterable[str] = DEFAULT_RANK_COLUMNS,
    suffix: str = "_rank",
) -> pd.DataFrame:
    """Add same-date percentile ranks for model features.

    Cross-sectional ranking is allowed at prediction time because it uses only
    the other securities observed on that same date.  It must still be applied
    separately inside each live/backtest universe.
    """

    if date_col not in frame.columns:
        raise ValueError(f"Missing date column: {date_col}")
    result = frame.copy()
    dates = pd.to_datetime(result[date_col], utc=True, errors="raise")
    for column in columns:
        if column not in result.columns:
            raise ValueError(f"Missing feature column: {column}")
        numeric = pd.to_numeric(result[column], errors="coerce")
        result[f"{column}{suffix}"] = numeric.groupby(dates, sort=False).rank(
            pct=True, method="average"
        )
    return result
