# Model V3 – learned cross-sectional prediction

This branch starts a separate prediction foundation. The existing heuristic
engine remains unchanged until the learned pipeline proves that it adds value
out of sample.

## Definition of the first model

Every prediction date produces a ranking of the complete available universe.
The first target is the stock's future total return relative to a benchmark or
sector over 5 trading observations. The same feature panel will later support
20-observation and 60-observation targets.

The model must output both:

- a continuous expected excess return used for ranking;
- a calibrated probability of outperforming after a configurable cost buffer.

`BUY`/`NO_TRADE` is a downstream decision. It is not the training label.

## Current branch contents

- `market_checker_app/model_v3/price_features.py` builds lagged price,
  momentum, volatility, drawdown, liquidity and same-date percentile features.
- `market_checker_app/model_v3/price_panel.py` normalizes provider responses
  and stores the daily price panel in SQLite without filling missing sessions.
- `market_checker_app/model_v3/import_prices.py` provides a repeatable CLI
  importer for ticker lists from TXT, CSV/TSV and Excel files.
- `market_checker_app/model_v3/universe.py` stores dated universe snapshots
  with explicit benchmark and sector mappings and selects the latest snapshot
  available at a prediction date.
- `market_checker_app/model_v3/labels.py` builds fixed-horizon forward stock,
  benchmark and excess-return labels.
- `market_checker_app/model_v3/walk_forward.py` creates chronological
  train/validation/test windows with an embargo gap.
- `market_checker_app/model_v3/backtest.py` evaluates rank IC and top/bottom
  cross-sectional spread without silently converting every row into a trade.
- `tests/test_model_v3_foundation.py` covers the deterministic foundation.

## Implementation order

1. Add a persistent historical daily-price panel with adjusted prices,
   corporate actions and source timestamps. The prototype storage and Yahoo
   importer are now in place; the point-in-time data-source audit remains.
2. Add point-in-time universe membership and benchmark/sector mappings. The
   snapshot store is now in place; historical membership still depends on
   importing dated source snapshots rather than assuming today's universe.
3. Build a baseline model: momentum-only, then Elastic Net and gradient
   boosted trees.
4. Add cost-aware portfolio construction and risk/exposure constraints.
5. Add point-in-time SEC fundamentals and earnings-event features.
6. Add historical news storage, entity resolution and financial NLP.
7. Integrate the winning out-of-sample model into the Streamlit pipeline.

## Non-negotiable validation rules

- Never random-shuffle observations.
- Never use a current Yahoo fundamental value in a historical row.
- Fit transformations only on the training portion of each window.
- Keep test predictions immutable and record model/config hashes.
- Compare every model with a naive benchmark and the existing heuristic score.
- Report rank quality, calibrated probabilities, net returns, turnover and
  drawdown together.
