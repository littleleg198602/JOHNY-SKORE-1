from __future__ import annotations

import datetime as dt
from typing import Any


class MT5Client:
    def __init__(self) -> None:
        self.mt5 = None

    def connect(self) -> None:
        import MetaTrader5 as mt5

        if not mt5.initialize():
            raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
        self.mt5 = mt5

    def close(self) -> None:
        if self.mt5:
            self.mt5.shutdown()

    def visible_symbols(self) -> list[str]:
        if not self.mt5:
            raise RuntimeError("MT5 not connected")
        return sorted({s.name for s in self.mt5.symbols_get() if getattr(s, "visible", False)})

    def d1_closes(self, symbol: str, count: int = 250) -> list[float]:
        if not self.mt5:
            return []
        rates = self.mt5.copy_rates_from_pos(symbol, self.mt5.TIMEFRAME_D1, 0, count)
        if rates is None:
            return []
        return [float(r["close"]) for r in rates]

    def copy_rates_range(self, symbol: str, start_date: dt.date, end_date: dt.date) -> list[tuple[dt.date, float, float]]:
        if not self.mt5:
            return []
        dt_from = dt.datetime.combine(start_date, dt.time.min)
        dt_to = dt.datetime.combine(end_date + dt.timedelta(days=1), dt.time.min)
        rates = self.mt5.copy_rates_range(symbol, self.mt5.TIMEFRAME_D1, dt_from, dt_to)
        if rates is None:
            return []
        out: list[tuple[dt.date, float, float]] = []
        for r in rates:
            d = dt.datetime.fromtimestamp(int(r["time"])).date()
            if start_date <= d <= end_date:
                out.append((d, float(r["open"]), float(r["close"])))
        return out
