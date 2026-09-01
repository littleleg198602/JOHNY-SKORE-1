"""First-generation learned prediction foundation.

The modules in this package are deliberately independent of the existing
heuristic scoring engine.  They build a point-in-time feature/label panel and
provide deterministic evaluation primitives before a trained model is added.
"""

from .backtest import evaluate_cross_section
from .baseline import (
    BaselineConfig,
    ElasticNetBaseline,
    add_momentum_baseline,
    run_walk_forward_baseline,
)
from .labels import build_forward_labels
from .price_panel import (
    SQLitePricePanelStore,
    YahooHistoricalLoader,
    ingest_tickers,
    normalize_price_frame,
)
from .price_features import build_price_features, cross_sectional_rank
from .universe import (
    SQLiteUniverseStore,
    normalize_universe_snapshot,
    read_universe_snapshot,
)
from .walk_forward import WalkForwardWindow, make_walk_forward_windows, select_window

__all__ = [
    "WalkForwardWindow",
    "BaselineConfig",
    "ElasticNetBaseline",
    "add_momentum_baseline",
    "build_forward_labels",
    "build_price_features",
    "cross_sectional_rank",
    "evaluate_cross_section",
    "ingest_tickers",
    "make_walk_forward_windows",
    "normalize_price_frame",
    "select_window",
    "run_walk_forward_baseline",
    "SQLitePricePanelStore",
    "YahooHistoricalLoader",
    "SQLiteUniverseStore",
    "normalize_universe_snapshot",
    "read_universe_snapshot",
]
