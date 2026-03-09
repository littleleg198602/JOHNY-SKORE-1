from __future__ import annotations

from pathlib import Path

APP_TITLE = "Market Checker (interní analytika)"
APP_DESCRIPTION = "Modulární Streamlit aplikace pro news/tech/yahoo scoring z MT5 watchlistu."

DEFAULT_OUTDIR = Path("./outputs")
DEFAULT_MARKETCAP_PATH = "market_watch_symbols_enriched_yahoo.xlsx"
DEFAULT_MAX_RSS_ITEMS_PER_SOURCE = 10

RSS_FETCH_TIMEOUT_S = 4
RSS_TICKER_BUDGET_S = 15
RSS_DISABLE_AFTER_CONSECUTIVE_FAILURES = 10
RSS_NEVER_DISABLE_SOURCES = {"Yahoo Finance", "Seeking Alpha"}

EXCEL_FILENAME_PREFIX = "market_checker_watchlist"

SOURCES = [
    {"source": "Yahoo Finance", "type": "aggregator", "paywall": "limited", "info_level": 3, "template": "https://finance.yahoo.com/rss/headline?s={ticker}", "notes": "RSS supported"},
    {"source": "Seeking Alpha", "type": "analysis", "paywall": "limited", "info_level": 3, "template": "https://seekingalpha.com/api/sa/combined/{ticker}.xml", "notes": "RSS supported"},
    {"source": "Benzinga", "type": "news", "paywall": "limited", "info_level": 2, "template": "https://www.benzinga.com/markets/feed", "notes": "RSS supported"},
    {"source": "GlobeNewswire", "type": "press releases", "paywall": "free", "info_level": 3, "template": "https://www.globenewswire.com/RssFeed/orgclass/1/feedTitle/GlobeNewswire%20-%20News%20about%20Public%20Companies", "notes": "RSS supported"},
    {"source": "PR Newswire", "type": "press releases", "paywall": "free", "info_level": 3, "template": "https://www.prnewswire.com/rss/news-releases-list.rss", "notes": "RSS supported"},
    {"source": "ECB (RSS + MID)", "type": "macro", "paywall": "free", "info_level": 4, "template": "https://www.ecb.europa.eu/press/rss/press.xml", "notes": "RSS supported"},
]

RSS_ENABLED_SOURCES = {s["source"] for s in SOURCES}
