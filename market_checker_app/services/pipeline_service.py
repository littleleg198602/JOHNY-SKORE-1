from __future__ import annotations

import datetime as dt
import logging

import pandas as pd

from market_checker_app.analysis.indicators import rsi, sma
from market_checker_app.analysis.performance import last_1m_change_pct, last_3m_change_pct, last_week_change_pct
from market_checker_app.analysis.scoring import news_metrics_48h, news_score_0_50, signal, tech_score, total_score
from market_checker_app.collectors.marketcap_loader import load_marketcap_map
from market_checker_app.collectors.mt5_client import MT5Client
from market_checker_app.collectors.rss_client import fetch_rss_items_for_ticker
from market_checker_app.collectors.yahoo_client import YahooClient
from market_checker_app.config import SOURCES
from market_checker_app.models import PerformanceSnapshot, RunResult, SignalRow, TechSnapshot
from market_checker_app.utils.dates import now_local_naive

logger = logging.getLogger(__name__)


def run_analysis(symbols: list[str], marketcap_path: str | None, max_rss_items_per_source: int) -> RunResult:
    mt5 = MT5Client()
    yahoo = YahooClient()
    cap_map = load_marketcap_map(marketcap_path)
    source_health: dict = {}
    feed_cache: dict = {}

    now_utc = dt.datetime.now(dt.timezone.utc)
    rows: list[SignalRow] = []
    all_articles = []

    mt5_connected = False
    try:
        mt5.connect()
        mt5_connected = True
    except Exception as exc:
        logger.warning("MT5 unavailable, using yfinance fallback: %s", exc)

    for ticker in symbols:
        yf_news = yahoo.news_fallback(ticker, max_items=20)
        rss_news = fetch_rss_items_for_ticker(ticker, SOURCES, max_rss_items_per_source, source_health=source_health, shared_feed_cache=feed_cache)
        articles = yf_news + [a for a in rss_news if a.link not in {n.link for n in yf_news if n.link}]
        all_articles.extend(articles)

        n_w, n_v = news_metrics_48h(articles, now_utc)
        n_score = news_score_0_50(n_w, n_v)

        tech = TechSnapshot(score=0.0, status="missing")
        if mt5_connected:
            closes = mt5.d1_closes(ticker)
            if len(closes) >= 60:
                c = closes[-1]
                ma20, ma50, rsi14 = sma(closes, 20), sma(closes, 50), rsi(closes, 14)
                tech = TechSnapshot(score=tech_score(c, ma20, ma50, rsi14), status="ok_mt", close=c, ma20=ma20, ma50=ma50, rsi14=rsi14)
        if tech.status != "ok_mt":
            tech = yahoo.tech_snapshot(ticker)

        ysnap = yahoo.yahoo_snapshot(ticker)

        if mt5_connected:
            lw, lws = last_week_change_pct(mt5, yahoo, ticker)
            m1, m1s = last_1m_change_pct(mt5, yahoo, ticker)
            m3, m3s = last_3m_change_pct(mt5, yahoo, ticker)
        else:
            lw, lws = None, "missing"
            m1, m1s = None, "missing"
            m3, m3s = None, "missing"

        perf = PerformanceSnapshot(lw, lws, m1, m1s, m3, m3s)
        total = total_score(n_score, tech.score, ysnap.score)
        cap, rank = cap_map.get(ticker, (None, None))

        rows.append(
            SignalRow(
                ticker=ticker,
                mt5_symbol=ticker,
                updated_at=now_local_naive().strftime("%Y-%m-%d %H:%M"),
                market_cap_usd=cap,
                rank_market_cap=rank,
                news_weighted_48h=round(n_w, 3),
                news_volume_48h=n_v,
                news_score=round(n_score, 1),
                tech=tech,
                yahoo=ysnap,
                total_score=round(total, 1),
                signal=signal(total),
                performance=perf,
            )
        )

    if mt5_connected:
        mt5.close()

    return RunResult(signals=rows, articles=all_articles, sources=SOURCES)


def signals_to_df(rows: list[SignalRow]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Ticker": r.ticker,
                "MT5Symbol": r.mt5_symbol,
                "UpdatedAt": r.updated_at,
                "MarketCapUSD": r.market_cap_usd,
                "RankMarketCap": r.rank_market_cap,
                "NewsWeighted48h": r.news_weighted_48h,
                "NewsVolume48h": r.news_volume_48h,
                "NewsScore(0-50)": r.news_score,
                "TechScore(0-50)": r.tech.score,
                "YahooScore(-20..20)": r.yahoo.score,
                "TotalScore(0-100)": r.total_score,
                "Signal": r.signal,
                "TechStatus": r.tech.status,
                "YahooStatus": r.yahoo.status,
                "Close": r.tech.close,
                "MA20": r.tech.ma20,
                "MA50": r.tech.ma50,
                "RSI14": r.tech.rsi14,
                "YahooPrice": r.yahoo.price,
                "YahooTarget": r.yahoo.target,
                "YahooUpsidePct": r.yahoo.upside_pct,
                "YahooRatingKey": r.yahoo.rating_key,
                "YahooRatingMean": r.yahoo.rating_mean,
                "LastWeekMonFriChangePct": r.performance.last_week_change_pct,
                "Last1MChangePct": r.performance.last_1m_change_pct,
                "Last3MChangePct": r.performance.last_3m_change_pct,
            }
            for r in rows
        ]
    )
