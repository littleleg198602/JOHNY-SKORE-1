from __future__ import annotations

import datetime as dt
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class NewsItem:
    ticker: str
    source: str
    title: str
    link: str
    published_utc: dt.datetime | None
    weight: float


@dataclass
class TechSnapshot:
    score: float
    status: str
    close: float | None = None
    ma20: float | None = None
    ma50: float | None = None
    rsi14: float | None = None


@dataclass
class YahooSnapshot:
    score: float
    status: str
    price: float | None = None
    target: float | None = None
    upside_pct: float | None = None
    rating_key: str | None = None
    rating_mean: float | None = None


@dataclass
class PerformanceSnapshot:
    last_week_change_pct: float | None
    last_week_status: str
    last_1m_change_pct: float | None
    last_1m_status: str
    last_3m_change_pct: float | None
    last_3m_status: str


@dataclass
class SignalRow:
    ticker: str
    mt5_symbol: str
    updated_at: str
    market_cap_usd: float | None
    rank_market_cap: int | None
    news_weighted_48h: float
    news_volume_48h: int
    news_score: float
    tech: TechSnapshot
    yahoo: YahooSnapshot
    total_score: float
    signal: str
    performance: PerformanceSnapshot

    def to_record(self) -> dict[str, Any]:
        rec = asdict(self)
        rec.update(
            {
                "TechScore(0-50)": self.tech.score,
                "TechStatus": self.tech.status,
                "Close": self.tech.close,
                "MA20": self.tech.ma20,
                "MA50": self.tech.ma50,
                "RSI14": self.tech.rsi14,
                "YahooScore(-20..20)": self.yahoo.score,
                "YahooStatus": self.yahoo.status,
                "YahooPrice": self.yahoo.price,
                "YahooTarget": self.yahoo.target,
                "YahooUpsidePct": self.yahoo.upside_pct,
                "YahooRatingKey": self.yahoo.rating_key,
                "YahooRatingMean": self.yahoo.rating_mean,
                "LastWeekMonFriChangePct": self.performance.last_week_change_pct,
                "LastWeekMonFriStatus": self.performance.last_week_status,
                "Last1MChangePct": self.performance.last_1m_change_pct,
                "Last1MStatus": self.performance.last_1m_status,
                "Last3MChangePct": self.performance.last_3m_change_pct,
                "Last3MStatus": self.performance.last_3m_status,
            }
        )
        return rec


@dataclass
class RunResult:
    signals: list[SignalRow] = field(default_factory=list)
    articles: list[NewsItem] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)
    delta: list[dict[str, Any]] = field(default_factory=list)
    output_path: str | None = None
