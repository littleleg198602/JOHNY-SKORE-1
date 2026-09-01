from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Any, Protocol

import pandas as pd


PANEL_COLUMNS = [
    "ticker",
    "date",
    "open",
    "high",
    "low",
    "close",
    "adj_close",
    "volume",
    "source",
    "observed_at",
]


class HistoricalPriceLoader(Protocol):
    def fetch(self, ticker: str) -> pd.DataFrame:
        """Return a normalized daily price frame for one ticker."""


def _flat_column_name(column: Any) -> str:
    if isinstance(column, tuple):
        parts = [str(part) for part in column if str(part).strip()]
        return " ".join(parts).strip().lower().replace("_", " ")
    return str(column).strip().lower().replace("_", " ")


def _find_column(columns: Iterable[Any], aliases: set[str]) -> Any | None:
    for column in columns:
        normalized = _flat_column_name(column)
        if normalized in aliases:
            return column
        if any(normalized.endswith(f" {alias}") for alias in aliases):
            return column
    return None


def normalize_price_frame(
    frame: pd.DataFrame,
    *,
    ticker: str,
    source: str,
    observed_at: datetime | None = None,
) -> pd.DataFrame:
    """Normalize one provider response into the immutable price-panel schema.

    The function preserves the provider's observed dates and never forward
    fills missing sessions. Duplicate ticker/date rows are rejected instead of
    silently overwriting history.
    """

    if frame.empty:
        raise ValueError(f"Historical price response is empty for {ticker}")
    ticker_value = str(ticker).strip().upper()
    if not ticker_value:
        raise ValueError("Ticker must not be empty")

    working = frame.copy()
    date_column = _find_column(
        working.columns,
        {"date", "datetime", "timestamp", "time"},
    )
    if date_column is None:
        date_values = working.index
    else:
        date_values = working.pop(date_column)

    aliases = {
        "open": {"open"},
        "high": {"high"},
        "low": {"low"},
        "close": {"close"},
        "adj_close": {"adj close", "adjusted close", "adjclose"},
        "volume": {"volume", "tick volume", "real volume"},
    }
    selected: dict[str, Any] = {}
    for target, names in aliases.items():
        column = _find_column(working.columns, names)
        if column is not None:
            selected[target] = working[column]

    if "close" not in selected and "adj_close" not in selected:
        raise ValueError(f"Historical price response has no close price for {ticker_value}")
    if "close" not in selected:
        selected["close"] = selected["adj_close"]
    if "adj_close" not in selected:
        selected["adj_close"] = selected["close"]

    result = pd.DataFrame(selected)
    result.insert(0, "ticker", ticker_value)
    result.insert(1, "date", pd.to_datetime(date_values, utc=True, errors="coerce"))
    result["source"] = str(source)
    observed = observed_at or datetime.now(timezone.utc)
    result["observed_at"] = pd.Timestamp(observed).tz_convert("UTC").isoformat()

    for column in ["open", "high", "low", "close", "adj_close", "volume"]:
        if column not in result.columns:
            result[column] = pd.NA
        result[column] = pd.to_numeric(result[column], errors="coerce")

    result = result.dropna(subset=["date", "close", "adj_close"])
    result = result[result["close"] > 0]
    result = result[result["adj_close"] > 0]
    result = result[PANEL_COLUMNS].sort_values("date").reset_index(drop=True)
    if result.empty:
        raise ValueError(f"Historical price response has no valid prices for {ticker_value}")
    if result.duplicated(["ticker", "date"]).any():
        raise ValueError(f"Historical price response has duplicate dates for {ticker_value}")
    return result


class YahooHistoricalLoader:
    """Small adapter for Yahoo daily history.

    Yahoo is suitable for the first prototype price panel, but it is not a
    survivorship-free or point-in-time fundamentals source. The source name is
    stored with every row so it can be audited and replaced later.
    """

    def __init__(self, *, period: str = "max") -> None:
        self.period = period

    def fetch(self, ticker: str) -> pd.DataFrame:
        try:
            import yfinance as yf
        except Exception as exc:  # pragma: no cover - environment-specific
            raise RuntimeError("yfinance is required for Yahoo historical ingestion") from exc
        raw = yf.Ticker(str(ticker).strip().upper()).history(
            period=self.period,
            interval="1d",
            auto_adjust=False,
            actions=True,
        )
        return normalize_price_frame(
            raw,
            ticker=ticker,
            source="yfinance",
        )


class SQLitePricePanelStore:
    """Persistent local store for normalized historical daily prices."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS price_panel (
                    ticker TEXT NOT NULL,
                    date TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL NOT NULL,
                    adj_close REAL NOT NULL,
                    volume REAL,
                    source TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    PRIMARY KEY (ticker, date)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_price_panel_date ON price_panel(date)"
            )

    def upsert(self, frame: pd.DataFrame) -> int:
        required = set(PANEL_COLUMNS)
        if not required.issubset(frame.columns):
            missing = sorted(required.difference(frame.columns))
            raise ValueError(f"Normalized price frame is missing: {', '.join(missing)}")
        if frame.duplicated(["ticker", "date"]).any():
            raise ValueError("Cannot upsert duplicate ticker/date observations")

        rows = []
        for row in frame[PANEL_COLUMNS].itertuples(index=False, name=None):
            ticker, date, open_, high, low, close, adj_close, volume, source, observed_at = row
            timestamp = pd.Timestamp(date)
            if timestamp.tzinfo is None:
                timestamp = timestamp.tz_localize("UTC")
            else:
                timestamp = timestamp.tz_convert("UTC")
            rows.append(
                (
                    str(ticker).strip().upper(),
                    timestamp.isoformat(),
                    None if pd.isna(open_) else float(open_),
                    None if pd.isna(high) else float(high),
                    None if pd.isna(low) else float(low),
                    float(close),
                    float(adj_close),
                    None if pd.isna(volume) else float(volume),
                    str(source),
                    str(observed_at),
                )
            )
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO price_panel
                    (ticker, date, open, high, low, close, adj_close, volume, source, observed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker, date) DO UPDATE SET
                    open=excluded.open,
                    high=excluded.high,
                    low=excluded.low,
                    close=excluded.close,
                    adj_close=excluded.adj_close,
                    volume=excluded.volume,
                    source=excluded.source,
                    observed_at=excluded.observed_at
                """,
                rows,
            )
        return len(rows)

    def load(
        self,
        *,
        tickers: Iterable[str] | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        clauses: list[str] = []
        parameters: list[Any] = []
        if tickers is not None:
            normalized = sorted({str(ticker).strip().upper() for ticker in tickers if str(ticker).strip()})
            if not normalized:
                return pd.DataFrame(columns=PANEL_COLUMNS)
            placeholders = ", ".join("?" for _ in normalized)
            clauses.append(f"ticker IN ({placeholders})")
            parameters.extend(normalized)
        if start is not None:
            clauses.append("date >= ?")
            parameters.append(pd.Timestamp(start, tz="UTC").isoformat())
        if end is not None:
            clauses.append("date <= ?")
            parameters.append(pd.Timestamp(end, tz="UTC").isoformat())
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"SELECT {', '.join(PANEL_COLUMNS)} FROM price_panel{where} ORDER BY ticker, date"
        with self._connect() as connection:
            return pd.read_sql_query(query, connection, params=parameters, parse_dates=["date", "observed_at"])


def ingest_tickers(
    tickers: Iterable[str],
    *,
    loader: HistoricalPriceLoader,
    store: SQLitePricePanelStore,
) -> dict[str, str]:
    """Ingest a ticker collection and return only failures by ticker."""

    failures: dict[str, str] = {}
    for raw_ticker in tickers:
        ticker = str(raw_ticker).strip().upper()
        if not ticker:
            continue
        try:
            frame = loader.fetch(ticker)
            store.upsert(frame)
        except Exception as exc:
            failures[ticker] = str(exc)
    return failures
