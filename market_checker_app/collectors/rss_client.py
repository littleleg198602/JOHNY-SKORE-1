from __future__ import annotations

import datetime as dt
import time
import urllib.error
import urllib.request
from collections.abc import Callable

from market_checker_app.analysis.scoring import source_weight
from market_checker_app.config import (
    RSS_DISABLE_AFTER_CONSECUTIVE_FAILURES,
    RSS_FETCH_TIMEOUT_S,
    RSS_NEVER_DISABLE_SOURCES,
    RSS_TICKER_BUDGET_S,
)
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


def fetch_rss_items_for_ticker(
    ticker: str,
    sources: list[dict],
    max_per_source: int,
    source_health: dict | None = None,
    shared_feed_cache: dict | None = None,
    on_warning: Callable[[str], None] | None = None,
) -> list[NewsItem]:
    try:
        import feedparser
    except Exception as exc:
        if on_warning:
            on_warning(f"RSS parser unavailable: {exc}")
        return []

    items: list[NewsItem] = []
    t0 = time.time()

    for src in sources:
        if time.time() - t0 >= RSS_TICKER_BUDGET_S:
            break

        source_name = str(src.get("source") or "unknown")
        template = (src.get("template") or "").strip()
        if not template:
            continue

        if source_health is not None:
            state = source_health.setdefault(source_name, {"failures": 0, "disabled": False, "warned_keys": set()})
        else:
            state = None

        if state and state["disabled"]:
            continue

        has_ticker = "{ticker}" in template
        urls = [template.format(ticker=c) for c in ticker_candidates(ticker)] if has_ticker else [template]
        seen_links: set[str] = set()

        for url in urls:
            feed = None
            cache_key = f"{source_name}|{url}" if shared_feed_cache is not None and not has_ticker else None

            if cache_key and cache_key in shared_feed_cache:
                cached = shared_feed_cache[cache_key]
                if isinstance(cached, dict) and cached.get("error"):
                    continue
                feed = cached

            if feed is None:
                try:
                    feed = feedparser.parse(_fetch_url_bytes(url))
                    if cache_key:
                        shared_feed_cache[cache_key] = feed
                except Exception as exc:
                    err_key = f"{source_name}:{type(exc).__name__}:{str(exc)[:120]}"
                    if state:
                        state["failures"] += 1

                    if isinstance(exc, urllib.error.HTTPError) and exc.code == 404 and not has_ticker and state:
                        state["disabled"] = True
                        if cache_key:
                            shared_feed_cache[cache_key] = {"error": "404"}
                        if on_warning and "404_disabled" not in state["warned_keys"]:
                            on_warning(f"RSS source disabled (404 permanent): {source_name}")
                            state["warned_keys"].add("404_disabled")
                        continue

                    if cache_key:
                        shared_feed_cache[cache_key] = {"error": str(exc)}

                    if on_warning and state and err_key not in state["warned_keys"]:
                        on_warning(f"RSS fetch failed ({source_name}): {exc}")
                        state["warned_keys"].add(err_key)

                    if state and source_name not in RSS_NEVER_DISABLE_SOURCES and state["failures"] >= RSS_DISABLE_AFTER_CONSECUTIVE_FAILURES:
                        state["disabled"] = True
                        if on_warning and "disabled_retries" not in state["warned_keys"]:
                            on_warning(f"RSS source disabled after repeated failures: {source_name}")
                            state["warned_keys"].add("disabled_retries")
                    continue

            w = source_weight(int(src.get("info_level") or 3))
            taken = 0
            for entry in getattr(feed, "entries", []) or []:
                if taken >= max_per_source:
                    break
                if not has_ticker and not _entry_mentions_ticker(entry, ticker):
                    continue

                link = str(getattr(entry, "link", "") or "")
                if link and link in seen_links:
                    continue
                if link:
                    seen_links.add(link)

                items.append(
                    NewsItem(
                        ticker=ticker,
                        source=source_name,
                        title=str(getattr(entry, "title", "") or ""),
                        link=link,
                        published_utc=_parse_published(entry),
                        weight=w,
                    )
                )
                taken += 1

    return items
