from __future__ import annotations

import datetime as dt
import time
import urllib.request

import feedparser

from market_checker_app.analysis.scoring import source_weight
from market_checker_app.config import RSS_DISABLE_AFTER_CONSECUTIVE_FAILURES, RSS_FETCH_TIMEOUT_S, RSS_NEVER_DISABLE_SOURCES, RSS_TICKER_BUDGET_S
from market_checker_app.models import NewsItem
from market_checker_app.utils.text import ticker_candidates


def _fetch_url_bytes(url: str, timeout_s: int = RSS_FETCH_TIMEOUT_S) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "JOHNY-MarketChecker/1.0 (+rss-fetch)"})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return resp.read()


def _entry_mentions_ticker(entry, ticker: str) -> bool:
    text = f" {str(getattr(entry, 'title', ''))} {str(getattr(entry, 'summary', ''))} {str(getattr(entry, 'link', ''))} ".upper()
    for c in ticker_candidates(ticker):
        t = c.upper()
        if f" {t} " in text or f"({t})" in text or f":{t}" in text or f"/{t}" in text:
            return True
    return False


def _parse_published(entry) -> dt.datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, key, None)
        if parsed:
            return dt.datetime.fromtimestamp(time.mktime(parsed), tz=dt.timezone.utc)
    return None


def fetch_rss_items_for_ticker(ticker: str, sources: list[dict], max_per_source: int, source_health: dict | None = None, shared_feed_cache: dict | None = None) -> list[NewsItem]:
    items: list[NewsItem] = []
    t0 = time.time()
    for src in sources:
        if time.time() - t0 >= RSS_TICKER_BUDGET_S:
            break
        source_name = str(src.get("source") or "unknown")
        template = (src.get("template") or "").strip()
        if not template:
            continue
        state = (source_health or {}).setdefault(source_name, {"failures": 0, "disabled": False}) if source_health is not None else None
        if state and state["disabled"]:
            continue

        urls = [template.format(ticker=c) for c in ticker_candidates(ticker)] if "{ticker}" in template else [template]
        seen_links: set[str] = set()
        for url in urls:
            feed = None
            cache_key = f"{source_name}|{url}" if shared_feed_cache is not None and "{ticker}" not in template else None
            if cache_key:
                feed = shared_feed_cache.get(cache_key)
            if feed is None:
                try:
                    feed = feedparser.parse(_fetch_url_bytes(url))
                    if cache_key:
                        shared_feed_cache[cache_key] = feed
                except Exception:
                    if state:
                        state["failures"] += 1
                        if source_name not in RSS_NEVER_DISABLE_SOURCES and state["failures"] >= RSS_DISABLE_AFTER_CONSECUTIVE_FAILURES:
                            state["disabled"] = True
                    continue
            w = source_weight(int(src.get("info_level") or 3))
            taken = 0
            for entry in getattr(feed, "entries", []) or []:
                if taken >= max_per_source:
                    break
                if "{ticker}" not in template and not _entry_mentions_ticker(entry, ticker):
                    continue
                link = str(getattr(entry, "link", "") or "")
                if link and link in seen_links:
                    continue
                seen_links.add(link)
                items.append(NewsItem(ticker=ticker, source=source_name, title=str(getattr(entry, "title", "") or ""), link=link, published_utc=_parse_published(entry), weight=w))
                taken += 1
    return items
