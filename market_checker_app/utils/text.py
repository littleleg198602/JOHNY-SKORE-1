from __future__ import annotations

import re


def ticker_candidates(ticker: str) -> list[str]:
    t = (ticker or "").strip().upper()
    c = {t}
    if "." in t:
        c.add(t.replace(".", "-"))
        c.add(t.replace(".", ""))
    if "-" in t:
        c.add(t.replace("-", "."))
        c.add(t.replace("-", ""))
    return sorted(c)


def slugify_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_")
