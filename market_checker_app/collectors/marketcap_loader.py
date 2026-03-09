from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_marketcap_map(path: str | None) -> dict[str, tuple[float | None, int | None]]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}

    try:
        df = pd.read_excel(p) if p.suffix.lower() == ".xlsx" else pd.read_csv(p)
    except Exception:
        return {}

    cols = {c.lower(): c for c in df.columns}
    symbol_col = cols.get("symbol") or cols.get("yahoo_symbol") or cols.get("ticker")
    cap_col = cols.get("marketcap_usd") or cols.get("marketcap") or cols.get("market_cap")
    rank_col = cols.get("pořadí") or cols.get("poradi") or cols.get("rank") or cols.get("rankmarketcap")
    if not symbol_col:
        return {}

    out: dict[str, tuple[float | None, int | None]] = {}
    for _, row in df.iterrows():
        sym = str(row.get(symbol_col) or "").strip()
        if not sym:
            continue
        cap = pd.to_numeric(row.get(cap_col), errors="coerce") if cap_col else None
        rank = pd.to_numeric(row.get(rank_col), errors="coerce") if rank_col else None
        out[sym] = (float(cap) if pd.notna(cap) else None, int(rank) if pd.notna(rank) else None)
    return out
