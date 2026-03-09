# Market Checker App (Streamlit)

Interní modulární analytická aplikace postavená nad původním skriptem `refresh_news_auto.py`.

## Co umí
- načtení watchlistu z MT5 (MarketWatch visible symbols)
- scoring: News + Tech + Yahoo + Total + Signal
- fallback Tech: MT5 -> yfinance
- Yahoo detail scoring (price/target/reco)
- performance: minulý týden, 1M, 3M
- dashboard přehledy (top/bottom)
- články podle tickeru
- export do Excelu (`Signals`, `Sources`, `Articles`, `Dashboard`, volitelně `DeltaVsPrev`)
- porovnání s předchozím během

## Spuštění
```bash
cd market_checker_app
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Poznámky
- Pokud MT5 není dostupné, aplikace pokračuje s omezenými daty (tech fallback přes yfinance, performance může být missing).
- Pokud RSS/Yahoo selže, běh pokračuje a pouze chybějící data mají `missing` status.
- Pokud marketcap soubor neexistuje, aplikace funguje bez něj.
