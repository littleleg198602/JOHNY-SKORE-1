# Spuštění Model V3 bez příkazové řádky

Ve Windows stačí dvakrát kliknout na:

`Spustit_Model_V3_Import.bat`

Spouštěč automaticky:

1. použije stejné Python prostředí jako současný Market Checker,
2. zkontroluje závislosti,
3. načte kompletní viditelný MT5 watchlist,
4. přidá `SPY` jako benchmark,
5. vytvoří snapshot univerza s dnešním UTC datem,
6. uloží historické ceny do `data/model_v3_prices.db`.

Případné chyby se zobrazí v okně a import pokračuje přes další tickery. Okno
zůstane po dokončení otevřené, aby byl vidět počet úspěšných a neúspěšných
importů.
