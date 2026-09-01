from __future__ import annotations

import argparse
from pathlib import Path
import re
from typing import Iterable

import pandas as pd

from .price_panel import SQLitePricePanelStore, YahooHistoricalLoader, ingest_tickers


TICKER_COLUMN_NAMES = {
    "ticker",
    "yahoo ticker",
    "yahoo_ticker",
    "symbol",
    "symbols",
}


def normalize_tickers(values: Iterable[object]) -> list[str]:
    """Return a stable, de-duplicated list of usable ticker symbols."""

    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        ticker = str(value).strip().upper()
        if not ticker or ticker in {"NAN", "NONE", "TICKER", "SYMBOL"}:
            continue
        if ticker not in seen:
            seen.add(ticker)
            result.append(ticker)
    return result


def read_tickers(path: Path) -> list[str]:
    """Read tickers from TXT, CSV/TSV, or Excel files.

    Tabular files use a column named ticker, Yahoo ticker, symbol, or the first
    column as a fallback. Text files may contain one ticker per line or use
    commas/semicolons as separators. Lines beginning with ``#`` are ignored.
    """

    if not path.exists():
        raise FileNotFoundError(path)
    suffix = path.suffix.lower()
    if suffix in {".txt", ".list"}:
        values: list[str] = []
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            line = line.split("#", 1)[0].strip()
            if line:
                values.extend(part for part in re.split(r"[,;\\s]+", line) if part)
        return normalize_tickers(values)

    if suffix in {".xlsx", ".xls"}:
        frame = pd.read_excel(path)
    else:
        frame = pd.read_csv(path, sep=None, engine="python")
    if frame.empty:
        return []

    normalized_columns = {
        str(column).strip().lower().replace("_", " "): column
        for column in frame.columns
    }
    ticker_column = next(
        (column for name, column in normalized_columns.items() if name in TICKER_COLUMN_NAMES),
        frame.columns[0],
    )
    return normalize_tickers(frame[ticker_column].tolist())


def import_yahoo_prices(
    tickers: Iterable[str],
    *,
    db_path: Path | str,
    period: str = "max",
) -> dict[str, object]:
    """Download and persist Yahoo daily history for a ticker collection."""

    ticker_list = normalize_tickers(tickers)
    store = SQLitePricePanelStore(db_path)
    failures = ingest_tickers(
        ticker_list,
        loader=YahooHistoricalLoader(period=period),
        store=store,
    )
    loaded = store.load(tickers=ticker_list)
    return {
        "requested": len(ticker_list),
        "succeeded": len(ticker_list) - len(failures),
        "failed": len(failures),
        "rows": len(loaded),
        "failures": failures,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Importuj historická denní data do model v3 SQLite panelu."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--ticker", action="append", help="Ticker; lze zadat vícekrát.")
    source.add_argument("--tickers-file", type=Path, help="TXT, CSV, TSV nebo XLSX se seznamem tickerů.")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("data/model_v3_prices.db"),
        help="Cesta k SQLite databázi (výchozí: data/model_v3_prices.db).",
    )
    parser.add_argument(
        "--period",
        default="max",
        help="Yahoo period, např. max, 10y nebo 2y (výchozí: max).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    tickers = args.ticker if args.ticker else read_tickers(args.tickers_file)
    if not tickers:
        print("Nebyl nalezen žádný ticker.")
        return 2

    try:
        result = import_yahoo_prices(tickers, db_path=args.db, period=args.period)
    except Exception as exc:
        print(f"Import selhal: {exc}")
        return 1

    print(
        f"Hotovo: {result['succeeded']}/{result['requested']} tickerů, "
        f"{result['rows']} řádků v {args.db}."
    )
    failures = result["failures"]
    if failures:
        print("Neúspěšné tickery:")
        for ticker, reason in failures.items():
            print(f"- {ticker}: {reason}")
    return 0 if not failures else 3


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
