from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from market_checker_app.collectors.mt5_client import MT5Client
from market_checker_app.config import APP_DESCRIPTION, APP_TITLE, DEFAULT_MARKETCAP_PATH, DEFAULT_MAX_RSS_ITEMS_PER_SOURCE, DEFAULT_OUTDIR
from market_checker_app.exporters.dashboard_builder import build_dashboard_tables
from market_checker_app.exporters.excel_exporter import export_run
from market_checker_app.services.comparison_service import compare_with_previous
from market_checker_app.services.pipeline_service import run_analysis, signals_to_df


@st.cache_data(show_spinner=False)
def get_dashboard_tables(signals_df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return build_dashboard_tables(signals_df)


@st.cache_data(show_spinner=False)
def get_delta(signals_df: pd.DataFrame, outdir: str, enabled: bool) -> pd.DataFrame:
    if not enabled:
        return pd.DataFrame()
    delta = compare_with_previous(signals_df, outdir)
    return delta if delta is not None else pd.DataFrame()


st.set_page_config(page_title=APP_TITLE, layout="wide")
st.title(APP_TITLE)
st.caption(APP_DESCRIPTION)

for key, default in {
    "watchlist": [],
    "result": None,
    "signals_df": pd.DataFrame(),
    "articles_df": pd.DataFrame(),
    "delta_df": pd.DataFrame(),
    "dashboard": {},
    "selected_ticker": None,
    "excel_bytes": None,
    "excel_name": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

with st.sidebar:
    outdir = st.text_input("Output directory", str(DEFAULT_OUTDIR))
    marketcap_path = st.text_input("MarketCap file (.xlsx/.csv)", DEFAULT_MARKETCAP_PATH)
    export_excel = st.checkbox("Export do Excelu", value=True)
    compare_prev = st.checkbox("Porovnat s předchozím během", value=True)
    max_rss = st.number_input("Max RSS items per source", min_value=1, max_value=50, value=DEFAULT_MAX_RSS_ITEMS_PER_SOURCE)

    if st.button("Načíst watchlist z MT5"):
        try:
            mt5 = MT5Client()
            mt5.connect()
            st.session_state.watchlist = mt5.visible_symbols()
            mt5.close()
            st.success(f"Načteno {len(st.session_state.watchlist)} symbolů z MT5 MarketWatch.")
        except Exception as exc:
            st.error(f"MT5 není dostupné. Zkontroluj spuštěný terminál + přihlášení. Detail: {exc}")

    st.caption(f"Watchlist size: {len(st.session_state.watchlist)}")

    if st.button("Spustit analýzu"):
        if not st.session_state.watchlist:
            st.warning("Nejdřív načti watchlist z MT5.")
        else:
            progress = st.progress(0.0, text="Inicializace analýzy...")
            status = st.empty()

            def on_progress(done: int, total: int, ticker: str) -> None:
                pct = (done / total) if total else 1.0
                progress.progress(min(max(pct, 0.0), 1.0), text=f"Analýza {done}/{total} | {ticker}")

            warning_bucket: list[str] = []

            def on_warning(message: str) -> None:
                warning_bucket.append(message)
                status.caption(f"⚠️ {message}")

            result = run_analysis(
                st.session_state.watchlist,
                marketcap_path or None,
                int(max_rss),
                progress_callback=on_progress,
                warning_callback=on_warning,
            )
            signals_df = signals_to_df(result.signals)
            articles_df = pd.DataFrame([a.__dict__ for a in result.articles])
            sources_df = pd.DataFrame(result.sources)
            dashboard = get_dashboard_tables(signals_df)
            delta_df = get_delta(signals_df, outdir, compare_prev)

            if export_excel:
                path = export_run(outdir, signals_df, sources_df, articles_df, dashboard, delta_df if not delta_df.empty else None)
                st.success(f"Export hotov: {path}")
                with open(path, "rb") as f:
                    st.session_state.excel_bytes = f.read()
                st.session_state.excel_name = Path(path).name

            st.session_state.result = result
            st.session_state.signals_df = signals_df
            st.session_state.articles_df = articles_df
            st.session_state.delta_df = delta_df
            st.session_state.dashboard = dashboard
            if not signals_df.empty:
                st.session_state.selected_ticker = str(signals_df.iloc[0]["Ticker"])

            progress.progress(1.0, text="Analýza dokončena")

    if st.session_state.excel_bytes:
        st.download_button(
            "Stáhnout poslední Excel",
            data=st.session_state.excel_bytes,
            file_name=st.session_state.excel_name or "market_checker_export.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

signals_tab, dashboard_tab, articles_tab, sources_tab, delta_tab = st.tabs(["Signals", "Dashboard", "Articles", "Sources", "Delta"])

with signals_tab:
    base = st.session_state.signals_df
    if base.empty:
        st.info("Zatím nejsou data. Spusť analýzu.")
    else:
        c1, c2 = st.columns([1, 1])
        with c1:
            signal_values = ["ALL"] + sorted(base["Signal"].dropna().unique().tolist())
            signal_filter = st.selectbox("Filter Signal", signal_values)
        with c2:
            ticker_filter = st.text_input("Filter ticker contains", "").strip().upper()

        filtered = base.copy()
        if signal_filter != "ALL":
            filtered = filtered[filtered["Signal"] == signal_filter]
        if ticker_filter:
            filtered = filtered[filtered["Ticker"].str.upper().str.contains(ticker_filter, na=False)]

        st.caption(f"Zobrazeno {len(filtered)} / {len(base)} řádků")

        try:
            selection = st.dataframe(
                filtered,
                use_container_width=True,
                on_select="rerun",
                selection_mode="single-row",
                hide_index=True,
            )
            if selection and selection.selection.rows:
                row_idx = selection.selection.rows[0]
                st.session_state.selected_ticker = str(filtered.iloc[row_idx]["Ticker"])
        except TypeError:
            st.dataframe(filtered, use_container_width=True, hide_index=True)

        pick = st.selectbox("Ticker detail (manual)", filtered["Ticker"].dropna().astype(str).tolist(), index=0)
        if st.button("Zobrazit články pro ticker", key="show_articles_from_signals"):
            st.session_state.selected_ticker = pick

with dashboard_tab:
    dashboard = st.session_state.get("dashboard", {})
    if dashboard:
        st.subheader("Top 20 by TotalScore")
        st.dataframe(dashboard["top_total"], use_container_width=True)
        st.subheader("Top 20 weekly drops")
        st.dataframe(dashboard["weekly_drops"], use_container_width=True)
        st.subheader("Top 20 1M drops")
        st.dataframe(dashboard["m1_drops"], use_container_width=True)
        st.subheader("Top 20 3M drops")
        st.dataframe(dashboard["m3_drops"], use_container_width=True)
        st.subheader("Top 20 by MarketCap")
        st.dataframe(dashboard["top_mcap"], use_container_width=True)
        st.subheader("Bottom 20 by MarketCap")
        st.dataframe(dashboard["bottom_mcap"], use_container_width=True)

with articles_tab:
    adf = st.session_state.articles_df
    if adf.empty:
        st.info("Žádné články k zobrazení.")
    else:
        tickers = sorted(adf["ticker"].dropna().astype(str).unique().tolist())
        default_ix = tickers.index(st.session_state.selected_ticker) if st.session_state.selected_ticker in tickers else 0
        ticker = st.selectbox("Vyber ticker", tickers, index=default_ix)
        st.session_state.selected_ticker = ticker
        st.dataframe(adf[adf["ticker"] == ticker], use_container_width=True, hide_index=True)

with sources_tab:
    if st.session_state.result is not None:
        st.dataframe(pd.DataFrame(st.session_state.result.sources), use_container_width=True, hide_index=True)
        if st.session_state.result.warnings:
            with st.expander(f"Warnings ({len(st.session_state.result.warnings)})", expanded=False):
                for msg in st.session_state.result.warnings[:200]:
                    st.write(f"- {msg}")

with delta_tab:
    if st.session_state.delta_df.empty:
        st.info("Delta není k dispozici (nebo nebyl nalezen předchozí workbook).")
    else:
        st.dataframe(st.session_state.delta_df, use_container_width=True, hide_index=True)
