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

## Spuštění (doporučeno)
```bash
cd /workspace/JOHNY-SKORE-1
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r market_checker_app/requirements.txt
streamlit run market_checker_app/app.py
```

## Alternativa
Můžeš spustit i z podadresáře `market_checker_app`:
```bash
cd /workspace/JOHNY-SKORE-1/market_checker_app
streamlit run app.py
```

## Poznámky
- Pokud MT5 není dostupné, aplikace pokračuje s omezenými daty (tech fallback přes yfinance, performance může být missing).
- Pokud RSS/Yahoo selže, běh pokračuje a pouze chybějící data mají `missing` status.
- Pokud marketcap soubor neexistuje, aplikace funguje bez něj.
- Textové řádky typu `APA, CF, ...` v Excel Dashboardu nejsou pád aplikace; jsou to agregované seznamy v reportu.
