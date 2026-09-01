from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Any

import pandas as pd


UNIVERSE_COLUMNS = [
    "ticker",
    "as_of_date",
    "benchmark",
    "sector",
    "source",
    "observed_at",
]


def _column_name(column: Any) -> str:
    return str(column).strip().lower().replace("_", " ")


def _find_column(columns: Iterable[Any], aliases: set[str]) -> Any | None:
    for column in columns:
        if _column_name(column) in aliases:
            return column
    return None


def _utc_day(value: str | pd.Timestamp | datetime) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")
    return timestamp.normalize()


def normalize_universe_snapshot(
    frame: pd.DataFrame,
    *,
    as_of_date: str | pd.Timestamp | datetime,
    source: str,
    default_benchmark: str = "SPY",
    observed_at: datetime | None = None,
) -> pd.DataFrame:
    """Normalize one explicitly dated universe snapshot.

    A snapshot is intentionally immutable in meaning: it says which symbols
    were available as of one date. The function never fills membership from a
    current universe and rejects duplicate ticker rows.
    """

    if frame.empty:
        raise ValueError("Universe snapshot is empty")
    source_value = str(source).strip()
    if not source_value:
        raise ValueError("Universe snapshot source must not be empty")
    benchmark_value = str(default_benchmark).strip().upper()
    if not benchmark_value:
        raise ValueError("Default benchmark must not be empty")

    ticker_column = _find_column(
        frame.columns,
        {"ticker", "yahoo ticker", "symbol", "symbols"},
    )
    if ticker_column is None:
        raise ValueError("Universe snapshot must contain a ticker or symbol column")
    benchmark_column = _find_column(
        frame.columns,
        {"benchmark", "benchmark ticker", "benchmark symbol", "index"},
    )
    sector_column = _find_column(
        frame.columns,
        {"sector", "gics sector", "industry", "industry group"},
    )

    result = pd.DataFrame({"ticker": frame[ticker_column].astype("string").str.strip().str.upper()})
    result["as_of_date"] = _utc_day(as_of_date)
    result["benchmark"] = (
        frame[benchmark_column].astype("string").str.strip().str.upper()
        if benchmark_column is not None
        else benchmark_value
    )
    result["benchmark"] = result["benchmark"].fillna(benchmark_value).replace("", benchmark_value)
    result["sector"] = (
        frame[sector_column].astype("string").str.strip()
        if sector_column is not None
        else pd.Series(pd.NA, index=frame.index, dtype="string")
    )
    observed = observed_at or datetime.now(timezone.utc)
    result["source"] = source_value
    result["observed_at"] = pd.Timestamp(observed).tz_convert("UTC").isoformat()
    result = result.dropna(subset=["ticker"])
    result = result[result["ticker"].ne("")]
    result = result[UNIVERSE_COLUMNS].sort_values("ticker").reset_index(drop=True)
    if result.empty:
        raise ValueError("Universe snapshot contains no usable tickers")
    if result.duplicated(["ticker", "as_of_date"]).any():
        raise ValueError("Universe snapshot contains duplicate ticker rows")
    return result


def read_universe_snapshot(
    path: Path,
    *,
    as_of_date: str | pd.Timestamp | datetime,
    source: str | None = None,
    default_benchmark: str = "SPY",
) -> pd.DataFrame:
    """Read a universe snapshot from CSV/TSV or Excel."""

    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix.lower() in {".xlsx", ".xls"}:
        frame = pd.read_excel(path)
    else:
        frame = pd.read_csv(path, sep=None, engine="python")
    return normalize_universe_snapshot(
        frame,
        as_of_date=as_of_date,
        source=source or path.name,
        default_benchmark=default_benchmark,
    )


class SQLiteUniverseStore:
    """SQLite storage for dated universe membership snapshots."""

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
                CREATE TABLE IF NOT EXISTS universe_membership (
                    ticker TEXT NOT NULL,
                    as_of_date TEXT NOT NULL,
                    benchmark TEXT NOT NULL,
                    sector TEXT,
                    source TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    PRIMARY KEY (ticker, as_of_date)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_universe_as_of ON universe_membership(as_of_date)"
            )

    def upsert(self, frame: pd.DataFrame) -> int:
        if not set(UNIVERSE_COLUMNS).issubset(frame.columns):
            missing = sorted(set(UNIVERSE_COLUMNS).difference(frame.columns))
            raise ValueError(f"Universe frame is missing: {', '.join(missing)}")
        if frame.duplicated(["ticker", "as_of_date"]).any():
            raise ValueError("Cannot upsert duplicate ticker/as_of_date rows")

        rows = []
        for row in frame[UNIVERSE_COLUMNS].itertuples(index=False, name=None):
            ticker, as_of_date, benchmark, sector, source, observed_at = row
            rows.append(
                (
                    str(ticker).strip().upper(),
                    _utc_day(as_of_date).isoformat(),
                    str(benchmark).strip().upper(),
                    None if pd.isna(sector) else str(sector).strip(),
                    str(source),
                    str(observed_at),
                )
            )
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO universe_membership
                    (ticker, as_of_date, benchmark, sector, source, observed_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker, as_of_date) DO UPDATE SET
                    benchmark=excluded.benchmark,
                    sector=excluded.sector,
                    source=excluded.source,
                    observed_at=excluded.observed_at
                """,
                rows,
            )
        return len(rows)

    def load(
        self,
        *,
        as_of_date: str | pd.Timestamp | datetime | None = None,
        tickers: Iterable[str] | None = None,
    ) -> pd.DataFrame:
        clauses: list[str] = []
        parameters: list[Any] = []
        if as_of_date is not None:
            clauses.append(
                "as_of_date = (SELECT MAX(as_of_date) FROM universe_membership WHERE as_of_date <= ?)"
            )
            parameters.append(_utc_day(as_of_date).isoformat())
        if tickers is not None:
            normalized = sorted({str(ticker).strip().upper() for ticker in tickers if str(ticker).strip()})
            if not normalized:
                return pd.DataFrame(columns=UNIVERSE_COLUMNS)
            placeholders = ", ".join("?" for _ in normalized)
            clauses.append(f"ticker IN ({placeholders})")
            parameters.extend(normalized)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"SELECT {', '.join(UNIVERSE_COLUMNS)} FROM universe_membership{where} ORDER BY as_of_date, ticker"
        with self._connect() as connection:
            return pd.read_sql_query(query, connection, params=parameters, parse_dates=["as_of_date", "observed_at"])
