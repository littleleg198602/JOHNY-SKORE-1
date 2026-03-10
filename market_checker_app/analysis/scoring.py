from __future__ import annotations

import datetime as dt
import math

from market_checker_app.models import NewsItem


def source_weight(info_level: int) -> float:
    return {1: 0.6, 2: 0.8, 3: 1.0, 4: 1.2, 5: 1.4}.get(int(info_level), 1.0)


def tech_score(close: float, ma20: float | None, ma50: float | None, rsi14: float | None) -> float:
    score = 0.0
    if ma20 is not None and ma50 is not None:
        score += 12 if ma20 > ma50 else 4
        score += 8 if close > ma20 else 2
    if rsi14 is not None:
        if 45 <= rsi14 <= 65:
            score += 15
        elif 35 <= rsi14 < 45 or 65 < rsi14 <= 75:
            score += 10
        elif 25 <= rsi14 < 35 or 75 < rsi14 <= 85:
            score += 6
        else:
            score += 3
    if ma20 is not None:
        dist = (close - ma20) / ma20 * 100.0
        if dist >= 8:
            score += 2
        elif dist >= 3:
            score += 6
        elif dist >= -3:
            score += 10
        elif dist >= -8:
            score += 6
        else:
            score += 2
    return max(0.0, min(50.0, score))


def news_metrics_48h(items: list[NewsItem], now_utc: dt.datetime) -> tuple[float, int]:
    cutoff = now_utc - dt.timedelta(hours=48)
    wsum = 0.0
    cnt = 0
    for it in items:
        if not it.published_utc or it.published_utc < cutoff:
            continue
        cnt += 1
        age_h = (now_utc - it.published_utc).total_seconds() / 3600.0
        recency = max(0.05, 1.0 - age_h / 48.0)
        wsum += it.weight * recency
    return wsum, cnt


def news_metrics_48h_with_latest_fallback(items: list[NewsItem], now_utc: dt.datetime) -> tuple[float, int, bool]:
    wsum, cnt = news_metrics_48h(items, now_utc)
    if cnt > 0:
        return wsum, cnt, False

    # Pokud neni zadna zprava v poslednich 48h, zohledni alespon nejnovejsi dostupnou.
    dated_items = [it for it in items if it.published_utc is not None]
    if not dated_items:
        return wsum, cnt, False

    latest = max(dated_items, key=lambda it: it.published_utc)
    age_h = max(0.0, (now_utc - latest.published_utc).total_seconds() / 3600.0)
    # Pro starsi zpravy zachovame nizkou, ale nenulovou vahu.
    recency = max(0.05, 1.0 / (1.0 + age_h / (24.0 * 7.0)))
    return latest.weight * recency, 1, True


def news_score_0_50(news_weighted_48h: float, news_volume_48h: int) -> float:
    return max(0.0, min(50.0, min(30.0, news_weighted_48h * 4.0) + min(20.0, math.log1p(news_volume_48h) * 5.0)))


def total_score(news_0_50: float, tech_0_50: float, yahoo_m20_p20: float) -> float:
    return max(0.0, min(100.0, news_0_50 + tech_0_50 + (yahoo_m20_p20 + 20.0) * 0.5))


def signal(total_0_100: float) -> str:
    if total_0_100 >= 85:
        return "STRONG BUY"
    if total_0_100 >= 70:
        return "BUY"
    if total_0_100 >= 55:
        return "HOLD"
    if total_0_100 >= 40:
        return "SELL"
    return "STRONG SELL"
