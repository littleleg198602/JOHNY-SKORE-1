from __future__ import annotations

import datetime as dt
import json
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

from market_checker_app.analysis.indicators import rsi, sma
from market_checker_app.analysis.scoring import tech_score
from market_checker_app.models import NewsItem, TechSnapshot, YahooSnapshot


class YahooClient:
    def __init__(self, timeout_s: int = 4, on_warning: Callable[[str], None] | None = None) -> None:
        self.timeout_s = timeout_s
        self.on_warning = on_warning

    def _warn(self, message: str) -> None:
        if self.on_warning:
            self.on_warning(message)

    def _fetch_url_bytes(self, url: str) -> bytes:
        req = urllib.request.Request(url, headers={"User-Agent": "JOHNY-MarketChecker/1.0"})
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            return resp.read()

    def quote_overview(self, symbol: str) -> dict[str, Any]:
        import yfinance as yf

        out: dict[str, Any] = {
            "market_cap": None,
            "long_name": None,
            "short_name": None,
        }

        try:
            t = yf.Ticker(symbol)
            info = getattr(t, "info", {}) or {}

            market_cap = info.get("marketCap")
            if market_cap is None:
                fast_info = getattr(t, "fast_info", None)
                market_cap = getattr(fast_info, "market_cap", None) if fast_info is not None else None
            if market_cap is not None:
                out["market_cap"] = float(market_cap)

            long_name = info.get("longName")
            if long_name:
                out["long_name"] = str(long_name)

            short_name = info.get("shortName")
            if short_name:
                out["short_name"] = str(short_name)

            return out
        except Exception as exc:
            self._warn(f"Yahoo quote overview failed for {symbol}: {exc}")
            return out

    def history_closes(self, symbol: str, period: str = "12mo") -> list[float]:
        import yfinance as yf

        hist = yf.Ticker(symbol).history(period=period, interval="1d")
        closes: list[float] = []
        for _, row in hist.iterrows():
            c = row.get("Close")
            if c is not None:
                closes.append(float(c))
        return closes

    def history_open_close(self, symbol: str, start_date: dt.date, end_date: dt.date, yf_period: str) -> list[tuple[dt.date, float, float]]:
        import yfinance as yf

        hist = yf.Ticker(symbol).history(period=yf_period, interval="1d")
        out: list[tuple[dt.date, float, float]] = []
        for idx, row in hist.iterrows():
            d = idx.date()
            if not (start_date <= d <= end_date):
                continue
            o, c = row.get("Open"), row.get("Close")
            if o is not None and c is not None:
                out.append((d, float(o), float(c)))
        return out

    def price_change_pct_since(self, symbol: str, since_date: dt.date) -> float | None:
        import yfinance as yf

        try:
            hist = yf.Ticker(symbol).history(period="1y", interval="1d")
            if hist is None or hist.empty:
                return None

            baseline = None
            latest_close = None
            for idx, row in hist.iterrows():
                d = idx.date()
                c = row.get("Close")
                if c is None:
                    continue
                c = float(c)
                latest_close = c
                if baseline is None and d >= since_date:
                    baseline = c

            if baseline is None or latest_close is None or baseline <= 0:
                return None
            return (latest_close / baseline - 1.0) * 100.0
        except Exception as exc:
            self._warn(f"price change lookup failed for {symbol}: {exc}")
            return None

    def tech_snapshot(self, symbol: str) -> TechSnapshot:
        try:
            closes = self.history_closes(symbol)
            if len(closes) < 60:
                self._warn(f"yfinance tech data missing for {symbol} (insufficient history)")
                return TechSnapshot(score=0.0, status="missing_yf")
            close = closes[-1]
            ma20 = sma(closes, 20)
            ma50 = sma(closes, 50)
            rsi14 = rsi(closes, 14)
            return TechSnapshot(score=tech_score(close, ma20, ma50, rsi14), status="ok_yf_tech", close=close, ma20=ma20, ma50=ma50, rsi14=rsi14)
        except Exception as exc:
            self._warn(f"yfinance tech snapshot failed for {symbol}: {exc}")
            return TechSnapshot(score=0.0, status="missing_yf")

    def yahoo_snapshot(self, symbol: str) -> YahooSnapshot:
        import yfinance as yf

        try:
            info = getattr(yf.Ticker(symbol), "info", {}) or {}
            price = info.get("currentPrice") or info.get("regularMarketPrice")
            target = info.get("targetMeanPrice") or info.get("targetMedianPrice")
            reco = info.get("recommendationMean")
            key = info.get("recommendationKey")
            upside = (float(target) / float(price) - 1.0) * 100.0 if price and target else None
            score = 0.0
            if reco is not None:
                rm = float(reco)
                score += 8 if rm <= 1.6 else 5 if rm <= 2.2 else 2 if rm <= 2.8 else -2
            if upside is not None:
                score += 10 if upside >= 40 else 7 if upside >= 20 else 3 if upside >= 5 else 0 if upside >= -5 else -4 if upside >= -15 else -8
            return YahooSnapshot(
                score=max(-20.0, min(20.0, score)),
                status="ok_yf",
                price=float(price) if price is not None else None,
                target=float(target) if target is not None else None,
                upside_pct=float(upside) if upside is not None else None,
                rating_key=key,
                rating_mean=float(reco) if reco is not None else None,
            )
        except Exception as exc:
            self._warn(f"yfinance yahoo snapshot failed for {symbol}: {exc}")
            return YahooSnapshot(score=0.0, status="missing")

    def news_fallback(self, ticker: str, max_items: int = 12) -> list[NewsItem]:
        import yfinance as yf

        items: list[NewsItem] = []
        seen: set[str] = set()

        def parse(raw_news: list[dict[str, Any]], src: str) -> None:
            for n in raw_news:
                if len(items) >= max_items:
                    return
                link = str(n.get("link") or "")
                if link and link in seen:
                    continue
                ts = n.get("providerPublishTime")
                pub = dt.datetime.fromtimestamp(int(ts), tz=dt.timezone.utc) if ts else None
                if link:
                    seen.add(link)
                items.append(NewsItem(ticker=ticker, source=src, title=str(n.get("title") or ""), link=link, published_utc=pub, weight=1.0))

        try:
            parse(getattr(yf.Ticker(ticker), "news", []) or [], "Yahoo Finance API")
        except Exception as exc:
            self._warn(f"yfinance news failed for {ticker}: {exc}")

        def fetch_search_news(query: str) -> None:
            q = urllib.parse.quote(query)
            url = f"https://query1.finance.yahoo.com/v1/finance/search?q={q}&quotesCount=1&newsCount={max_items}"
            obj = json.loads(self._fetch_url_bytes(url).decode("utf-8", errors="ignore"))
            parse(obj.get("news") or [], "Yahoo Search API")

        try:
            fetch_search_news(ticker)
        except Exception as exc:
            self._warn(f"Yahoo Search API fallback failed for {ticker}: {exc}")

        # Kratke tickery (napr. "AA") vraci casto 0 news pri hledani jen podle symbolu.
        # Pokud stale nic nemame, zkusime vyhledat i podle nazvu firmy z quote endpointu.
        if not items:
            overview = self.quote_overview(ticker)
            for name_key in ("long_name", "short_name"):
                query = overview.get(name_key)
                if not query:
                    continue
                try:
                    fetch_search_news(str(query))
                except Exception as exc:
                    self._warn(f"Yahoo Search API name fallback failed for {ticker} ({name_key}): {exc}")
                if items:
                    break

        return items[:max_items]
