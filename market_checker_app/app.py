from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# Umozni spusteni jak z rootu repo, tak z adresare market_checker_app/
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from market_checker_app.collectors.mt5_client import MT5Client
from market_checker_app.config import APP_DESCRIPTION, APP_TITLE, DEFAULT_MARKETCAP_PATH, DEFAULT_MAX_RSS_ITEMS_PER_SOURCE, DEFAULT_OUTDIR
from market_checker_app.exporters.dashboard_builder import build_dashboard_tables
from market_checker_app.exporters.excel_exporter import export_run
from market_checker_app.services.comparison_service import compare_with_previous
from market_checker_app.services.pipeline_service import run_analysis, signals_to_df

st.set_page_config(page_title=APP_TITLE, layout="wide")
st.title(APP_TITLE)
st.caption(APP_DESCRIPTION)

if "watchlist" not in st.session_state:
    st.session_state.watchlist = []
if "result" not in st.session_state:
    st.session_state.result = None
if "signals_df" not in st.session_state:
    st.session_state.signals_df = pd.DataFrame()
if "articles_df" not in st.session_state:
    st.session_state.articles_df = pd.DataFrame()
if "delta_df" not in st.session_state:
    st.session_state.delta_df = pd.DataFrame()

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
            st.success(f"Načteno {len(st.session_state.watchlist)} symbolů.")
        except Exception as exc:
            st.error(f"MT5 není dostupné: {exc}")

    if st.button("Spustit analýzu"):
        if not st.session_state.watchlist:
            st.warning("Nejdřív načti watchlist z MT5.")
        else:
            with st.spinner("Probíhá analýza..."):
                result = run_analysis(st.session_state.watchlist, marketcap_path or None, int(max_rss))
                signals_df = signals_to_df(result.signals)
                articles_df = pd.DataFrame([a.__dict__ for a in result.articles])
                sources_df = pd.DataFrame(result.sources)
                dashboard = build_dashboard_tables(signals_df)
                delta_df = compare_with_previous(signals_df, outdir) if compare_prev else None

                if export_excel:
                    path = export_run(outdir, signals_df, sources_df, articles_df, dashboard, delta_df)
                    st.success(f"Export hotov: {path}")

                st.session_state.result = result
                st.session_state.signals_df = signals_df
                st.session_state.articles_df = articles_df
                st.session_state.delta_df = delta_df if delta_df is not None else pd.DataFrame()
                st.session_state.dashboard = dashboard

signals_tab, dashboard_tab, articles_tab, sources_tab, delta_tab = st.tabs(["Signals", "Dashboard", "Articles", "Sources", "Delta"])

with signals_tab:
    st.dataframe(st.session_state.signals_df, use_container_width=True)

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
    if not adf.empty:
        ticker = st.selectbox("Vyber ticker", sorted(adf["ticker"].dropna().unique().tolist()))
        st.dataframe(adf[adf["ticker"] == ticker], use_container_width=True)

with sources_tab:
    if st.session_state.result is not None:
        st.dataframe(pd.DataFrame(st.session_state.result.sources), use_container_width=True)

with delta_tab:
    st.dataframe(st.session_state.delta_df, use_container_width=True)
