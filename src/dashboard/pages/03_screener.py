"""Screen 3: Financial Screener - Custom metric filters, 6 presets, and CSV export."""

import os
import sys
from typing import Any, Dict

# Ensure workspace root is in sys.path
_WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

import numpy as np
import pandas as pd
import streamlit as st

from src.dashboard.utils.db import clean_company_name, get_all_screener_data

# Presets mapping to slider values
PRESET_CONFIGS: Dict[str, Dict[str, float]] = {
    "Quality Compounders": {
        "roe_min": 15.0,
        "de_max": 1.0,
        "fcf_min": 0.0,
        "rev_cagr_min": 10.0,
        "pat_cagr_min": 10.0,
        "opm_min": 15.0,
        "pe_max": 80.0,
        "pb_max": 20.0,
        "div_yield_min": 0.0,
        "icr_min": 3.0,
    },
    "High Growth": {
        "roe_min": 12.0,
        "de_max": 2.0,
        "fcf_min": -500.0,
        "rev_cagr_min": 15.0,
        "pat_cagr_min": 20.0,
        "opm_min": 12.0,
        "pe_max": 90.0,
        "pb_max": 25.0,
        "div_yield_min": 0.0,
        "icr_min": 2.0,
    },
    "Value Picks": {
        "roe_min": 10.0,
        "de_max": 2.0,
        "fcf_min": 0.0,
        "rev_cagr_min": 5.0,
        "pat_cagr_min": 5.0,
        "opm_min": 10.0,
        "pe_max": 25.0,
        "pb_max": 5.0,
        "div_yield_min": 1.0,
        "icr_min": 2.0,
    },
    "Cash Flow Kings": {
        "roe_min": 12.0,
        "de_max": 1.5,
        "fcf_min": 1000.0,
        "rev_cagr_min": 5.0,
        "pat_cagr_min": 5.0,
        "opm_min": 15.0,
        "pe_max": 80.0,
        "pb_max": 20.0,
        "div_yield_min": 0.5,
        "icr_min": 3.0,
    },
    "Low Leverage": {
        "roe_min": 12.0,
        "de_max": 0.05,
        "fcf_min": 0.0,
        "rev_cagr_min": 5.0,
        "pat_cagr_min": 5.0,
        "opm_min": 10.0,
        "pe_max": 80.0,
        "pb_max": 20.0,
        "div_yield_min": 0.0,
        "icr_min": 5.0,
    },
    "Turnaround Candidates": {
        "roe_min": 5.0,
        "de_max": 2.5,
        "fcf_min": 0.0,
        "rev_cagr_min": 8.0,
        "pat_cagr_min": 10.0,
        "opm_min": 8.0,
        "pe_max": 70.0,
        "pb_max": 15.0,
        "div_yield_min": 0.0,
        "icr_min": 1.5,
    },
}

DEFAULT_SLIDERS = {
    "roe_min": 0.0,
    "de_max": 5.0,
    "fcf_min": -2000.0,
    "rev_cagr_min": -20.0,
    "pat_cagr_min": -20.0,
    "opm_min": 0.0,
    "pe_max": 120.0,
    "pb_max": 35.0,
    "div_yield_min": 0.0,
    "icr_min": 0.0,
}


def _apply_preset(preset_name: str) -> None:
    """Update session state sliders with preset threshold configuration."""
    cfg = PRESET_CONFIGS.get(preset_name, DEFAULT_SLIDERS)
    for k, v in cfg.items():
        st.session_state[f"slider_{k}"] = float(v)


def _reset_filters() -> None:
    """Reset all sliders to inclusive defaults."""
    for k, v in DEFAULT_SLIDERS.items():
        st.session_state[f"slider_{k}"] = float(v)


def render() -> None:
    """Render the Financial Screener screen."""
    try:
        st.set_page_config(layout="wide", page_title="Nifty 100 - Screener", page_icon="🔍")
    except Exception:
        pass

    st.title("🔍 Nifty 100 — Financial Screener Engine")
    st.markdown("Filter all 92 constituents across profitability, leverage, cash flow quality, growth, and valuation multiples.")

    # Initialize session state keys for sliders if not set
    for k, v in DEFAULT_SLIDERS.items():
        if f"slider_{k}" not in st.session_state:
            st.session_state[f"slider_{k}"] = float(v)

    # 1. Preset Quick Buttons
    st.subheader("⚡ Preset Screeners")
    p_cols = st.columns(7)
    with p_cols[0]:
        if st.button("🌟 Quality Compounders", use_container_width=True):
            _apply_preset("Quality Compounders")
            st.rerun()
    with p_cols[1]:
        if st.button("🚀 High Growth", use_container_width=True):
            _apply_preset("High Growth")
            st.rerun()
    with p_cols[2]:
        if st.button("💎 Value Picks", use_container_width=True):
            _apply_preset("Value Picks")
            st.rerun()
    with p_cols[3]:
        if st.button("👑 Cash Flow Kings", use_container_width=True):
            _apply_preset("Cash Flow Kings")
            st.rerun()
    with p_cols[4]:
        if st.button("🛡️ Low Leverage", use_container_width=True):
            _apply_preset("Low Leverage")
            st.rerun()
    with p_cols[5]:
        if st.button("🔄 Turnarounds", use_container_width=True):
            _apply_preset("Turnaround Candidates")
            st.rerun()
    with p_cols[6]:
        if st.button("♻️ Reset All", use_container_width=True):
            _reset_filters()
            st.rerun()

    st.markdown("---")

    # 2. Filter Controls (Sidebar)
    st.sidebar.header("🎛️ Screener Threshold Filters")

    roe_min = st.sidebar.slider("Min ROE (%)", min_value=-10.0, max_value=50.0, step=1.0, key="slider_roe_min")
    de_max = st.sidebar.slider("Max Debt-to-Equity", min_value=0.0, max_value=5.0, step=0.05, key="slider_de_max")
    fcf_min = st.sidebar.slider("Min Free Cash Flow (₹ Cr)", min_value=-2000.0, max_value=10000.0, step=250.0, key="slider_fcf_min")
    rev_cagr_min = st.sidebar.slider("Min 5Y Rev CAGR (%)", min_value=-20.0, max_value=40.0, step=1.0, key="slider_rev_cagr_min")
    pat_cagr_min = st.sidebar.slider("Min 5Y PAT CAGR (%)", min_value=-20.0, max_value=50.0, step=1.0, key="slider_pat_cagr_min")
    opm_min = st.sidebar.slider("Min OPM (%)", min_value=0.0, max_value=60.0, step=1.0, key="slider_opm_min")
    pe_max = st.sidebar.slider("Max P/E Multiple", min_value=5.0, max_value=120.0, step=1.0, key="slider_pe_max")
    pb_max = st.sidebar.slider("Max P/B Multiple", min_value=0.5, max_value=35.0, step=0.5, key="slider_pb_max")
    div_yield_min = st.sidebar.slider("Min Dividend Yield (%)", min_value=0.0, max_value=10.0, step=0.1, key="slider_div_yield_min")
    icr_min = st.sidebar.slider("Min Interest Coverage (ICR)", min_value=0.0, max_value=30.0, step=0.5, key="slider_icr_min")

    # 3. Filter Dataset
    master_df = get_all_screener_data()
    if master_df.empty:
        st.warning("No screener data found.")
        return

    df = master_df.copy()

    # Apply filters
    # ROE filter
    if "return_on_equity_pct" in df.columns:
        df = df[df["return_on_equity_pct"].isna() | (df["return_on_equity_pct"] >= roe_min)]

    # D/E filter: exclude Financials from D/E restriction
    if "debt_to_equity" in df.columns and "broad_sector" in df.columns:
        is_fin = df["broad_sector"] == "Financials"
        de_pass = df["debt_to_equity"].isna() | (df["debt_to_equity"] <= de_max)
        df = df[is_fin | de_pass]

    # FCF filter
    if "free_cash_flow_cr" in df.columns:
        df = df[df["free_cash_flow_cr"].isna() | (df["free_cash_flow_cr"] >= fcf_min)]

    # Rev CAGR 5yr
    if "revenue_cagr_5yr" in df.columns:
        df = df[df["revenue_cagr_5yr"].isna() | (df["revenue_cagr_5yr"] >= rev_cagr_min)]

    # PAT CAGR 5yr
    if "pat_cagr_5yr" in df.columns:
        df = df[df["pat_cagr_5yr"].isna() | (df["pat_cagr_5yr"] >= pat_cagr_min)]

    # OPM
    if "operating_profit_margin_pct" in df.columns:
        df = df[df["operating_profit_margin_pct"].isna() | (df["operating_profit_margin_pct"] >= opm_min)]

    # P/E filter (only apply to positive P/E)
    if "pe_ratio" in df.columns:
        df = df[df["pe_ratio"].isna() | (df["pe_ratio"] <= 0) | (df["pe_ratio"] <= pe_max)]

    # P/B filter
    if "pb_ratio" in df.columns:
        df = df[df["pb_ratio"].isna() | (df["pb_ratio"] <= pb_max)]

    # Dividend yield
    if "dividend_yield_pct" in df.columns:
        df = df[df["dividend_yield_pct"].isna() | (df["dividend_yield_pct"] >= div_yield_min)]

    # ICR: treat Debt Free / high coverage as passing
    if "interest_coverage" in df.columns:
        icr_pass = df["interest_coverage"].isna() | (df["interest_coverage"] >= icr_min)
        if "icr_label" in df.columns:
            icr_pass = icr_pass | (df["icr_label"] == "Debt Free")
        df = df[icr_pass]

    # Clean display columns
    df["clean_name"] = df["company_name"].apply(clean_company_name)

    # 4. Results Header and Counter
    hdr_c1, hdr_c2 = st.columns([3, 1])
    with hdr_c1:
        st.subheader(f"🎯 Filter Results: {len(df)} companies match your filters")
    with hdr_c2:
        # CSV Export Button
        csv_data = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Export Results as CSV",
            data=csv_data,
            file_name="nifty100_filtered_screener.csv",
            mime="text/csv",
            use_container_width=True,
        )

    # Format table for presentation
    display_cols = {
        "clean_name": "Company",
        "company_id": "Ticker",
        "broad_sector": "Sector",
        "composite_quality_score": "Score",
        "return_on_equity_pct": "ROE (%)",
        "return_on_capital_employed_pct": "ROCE (%)",
        "operating_profit_margin_pct": "OPM (%)",
        "debt_to_equity": "D/E",
        "free_cash_flow_cr": "FCF (₹ Cr)",
        "revenue_cagr_5yr": "Rev CAGR 5Y (%)",
        "pat_cagr_5yr": "PAT CAGR 5Y (%)",
        "pe_ratio": "P/E",
        "pb_ratio": "P/B",
        "dividend_yield_pct": "Div Yield (%)",
    }

    available_cols = [c for c in display_cols.keys() if c in df.columns]
    table_df = df[available_cols].copy().rename(columns=display_cols)

    # Sort by composite score if available
    if "Score" in table_df.columns:
        table_df = table_df.sort_values(by="Score", ascending=False)

    st.dataframe(
        table_df.style.format(
            {
                "Score": "{:.1f}",
                "ROE (%)": "{:.1f}%",
                "ROCE (%)": "{:.1f}%",
                "OPM (%)": "{:.1f}%",
                "D/E": "{:.2f}",
                "FCF (₹ Cr)": "₹{:,.0f}",
                "Rev CAGR 5Y (%)": "{:.1f}%",
                "PAT CAGR 5Y (%)": "{:.1f}%",
                "P/E": "{:.1f}x",
                "P/B": "{:.1f}x",
                "Div Yield (%)": "{:.2f}%",
            },
            na_rep="N/A",
        ),
        use_container_width=True,
        hide_index=True,
        height=520,
    )


if __name__ == "__main__":
    render()

