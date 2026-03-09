from __future__ import annotations

import datetime as dt

from market_checker_app.utils.dates import now_local_naive, previous_week_monday_friday


def _calc_change(bars: list[tuple[dt.date, float, float]]) -> float | None:
    if not bars:
        return None
    bars.sort(key=lambda x: x[0])
    first_open = bars[0][1]
    last_close = bars[-1][2]
    if not first_open:
        return None
    return (last_close / first_open - 1.0) * 100.0


def _change_between(mt5_client, yahoo_client, symbol: str, start_date: dt.date, end_date: dt.date, yf_period: str) -> tuple[float | None, str]:
    bars = mt5_client.copy_rates_range(symbol, start_date, end_date)
    change = _calc_change(bars)
    if change is not None:
        return change, "ok_mt"
    ybars = yahoo_client.history_open_close(symbol, start_date, end_date, yf_period)
    ychange = _calc_change(ybars)
    if ychange is not None:
        return ychange, "ok_yf"
    return None, "missing"


def last_week_change_pct(mt5_client, yahoo_client, symbol: str) -> tuple[float | None, str]:
    mon, fri = previous_week_monday_friday(now_local_naive().date())
    return _change_between(mt5_client, yahoo_client, symbol, mon, fri, "1mo")


def last_1m_change_pct(mt5_client, yahoo_client, symbol: str) -> tuple[float | None, str]:
    end_date = now_local_naive().date()
    return _change_between(mt5_client, yahoo_client, symbol, end_date - dt.timedelta(days=30), end_date, "6mo")


def last_3m_change_pct(mt5_client, yahoo_client, symbol: str) -> tuple[float | None, str]:
    end_date = now_local_naive().date()
    return _change_between(mt5_client, yahoo_client, symbol, end_date - dt.timedelta(days=90), end_date, "1y")
