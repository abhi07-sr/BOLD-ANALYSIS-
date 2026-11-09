"""Screen 7: Capital Allocation - 8-Pattern Treemap and 10-Year Cash Flow Sequence Analysis."""

import os
import sys
from typing import Any, Dict

# Ensure workspace root is in sys.path
_WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from src.dashboard.utils.db import clean_company_name, get_capital_allocation, get_cf, get_connection

PATTERN_COLORS = {
    "Shareholder Returns": "#10b981",       # Green
    "Reinvestor": "#2563eb",                # Blue
    "Growth Funded by Debt": "#f59e0b",     # Amber
    "Mixed": "#8b5cf6",                     # Purple
    "Liquidating Assets": "#06b6d4",        # Cyan
    "Restructuring": "#ec4899",             # Pink
    "Distress Signal": "#ef4444",           # Red
    "Pre-Revenue": "#64748b",               # Slate
}

PATTERN_EXPLANATIONS = {
    "Shareholder Returns": "CFO (+), CFI (-), CFF (-): Healthy organic cash generation funding capex while returning excess cash via dividends/buybacks/debt reduction.",
    "Reinvestor": "CFO (+), CFI (-), CFF (-): Business generates strong operating cash and reinvests substantially into core capital expenditures and capacity expansion.",
    "Growth Funded by Debt": "CFO (+ or -), CFI (-), CFF (+): Aggressive growth phase where heavy capex exceeds operating cash and is supported by external debt or equity financing.",
    "Mixed": "Transitional capital cycle with shifting operating or financing cash signs across fiscal years.",
    "Liquidating Assets": "CFO (+ or -), CFI (+), CFF (-): Generating liquidity by divesting non-core assets or investments to settle borrowings.",
    "Restructuring": "Undergoing operational realignment with debt rationalization and selective portfolio resizing.",
    "Distress Signal": "CFO (-), CFI (+ or -), CFF (+): Negative operating cash flows necessitating emergency external borrowing to sustain day-to-day operations.",
    "Pre-Revenue": "Nascent developmental phase with zero or negative operating cash prior to commercial scale.",
}


def render() -> None:
    """Render the Capital Allocation screen."""
    try:
        st.set_page_config(layout="wide", page_title="Nifty 100 - Capital Allocation", page_icon="💰")
    except Exception:
        pass

    st.title("💰 Capital Allocation & Cash Flow Lifecycle Patterns")
    st.markdown("Analyze how Nifty 100 corporate boards allocate operational capital across growth capex, debt repayment, and shareholder distributions.")

    # 1. Load Capital Allocation Data
    df_cap = get_capital_allocation()
    if df_cap.empty:
        st.error("No capital allocation data available.")
        return

    # Get latest year for each company
    latest_cap = df_cap.groupby("company_id").last().reset_index()
    latest_cap["clean_name"] = latest_cap["company_name"].apply(clean_company_name)

    # Fetch latest CFO, CFI, CFF values from cashflow table for hover details
    conn = get_connection()
    cf_query = """
        SELECT company_id, operating_activity as cfo, investing_activity as cfi, financing_activity as cff
        FROM cashflow
        WHERE year != 'TTM'
        GROUP BY company_id
        HAVING id = MAX(id)
    """
    cf_latest = pd.read_sql(cf_query, conn)
    conn.close()

    treemap_df = latest_cap.merge(cf_latest, on="company_id", how="left")
    treemap_df["cfo"] = treemap_df["cfo"].fillna(0.0)
    treemap_df["cfi"] = treemap_df["cfi"].fillna(0.0)
    treemap_df["cff"] = treemap_df["cff"].fillna(0.0)
    treemap_df["tile_size"] = 1  # Equal area per company for clean visual comparison

    # 2. Pattern Summary Counts
    st.subheader("📊 Distribution across the 8 Capital Allocation Archetypes")
    pattern_counts = latest_cap["pattern_label"].value_counts()

    cols = st.columns(4)
    patterns_list = list(PATTERN_COLORS.keys())
    for i, p_name in enumerate(patterns_list):
        cnt = pattern_counts.get(p_name, 0)
        col_idx = i % 4
        with cols[col_idx]:
            color_hex = PATTERN_COLORS[p_name]
            st.markdown(
                f"<div style='border-left: 4px solid {color_hex}; padding-left: 8px; margin-bottom: 8px;'>"
                f"<span style='font-size: 0.9em; font-weight: 600;'>{p_name}</span><br>"
                f"<span style='font-size: 1.2em; font-weight: 700;'>{cnt} Companies</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # 3. Treemap Visualization
    st.subheader("🗺️ Constituent Treemap Grouped by Capital Pattern")
    st.caption("Click into any pattern block to drill down into constituent corporations. Hover to inspect CFO/CFI/CFF figures.")

    fig_treemap = px.treemap(
        treemap_df,
        path=[px.Constant("All 92 Nifty 100 Companies"), "pattern_label", "clean_name"],
        values="tile_size",
        color="pattern_label",
        color_discrete_map=PATTERN_COLORS,
        custom_data=["company_id", "cfo_sign", "cfi_sign", "cff_sign", "cfo", "cfi", "cff", "broad_sector"],
    )

    fig_treemap.update_traces(
        hovertemplate=(
            "<b>%{label}</b><br>"
            "Pattern: %{parent}<br>"
            "Ticker: %{customdata[0]}<br>"
            "Sector: %{customdata[7]}<br>"
            "Cash Flow Signs: [%{customdata[1]} , %{customdata[2]} , %{customdata[3]}]<br>"
            "CFO (Ops): ₹%{customdata[4]:,.1f} Cr<br>"
            "CFI (Capex/Inv): ₹%{customdata[5]:,.1f} Cr<br>"
            "CFF (Financing): ₹%{customdata[6]:,.1f} Cr<extra></extra>"
        ),
        textinfo="label",
    )

    fig_treemap.update_layout(
        height=540,
        margin=dict(t=20, b=10, l=10, r=10),
    )
    st.plotly_chart(fig_treemap, use_container_width=True)

    st.markdown("---")

    # 4. Interactive 10-Year Cash Flow Sign Sequence Deep-Dive
    st.subheader("🔍 Interactive 10-Year Cash Flow Sign Sequence Analysis")
    st.markdown("Select any company to inspect its longitudinal lifecycle evolution from FY2013 to FY2024.")

    comp_options = {f"{r['company_id']} — {r['clean_name']}": r["company_id"] for _, r in latest_cap.iterrows()}
    opt_keys = list(comp_options.keys())

    default_idx = 0
    if "selected_ticker" in st.session_state and st.session_state.selected_ticker:
        cur_t = st.session_state.selected_ticker
        matches = [i for i, k in enumerate(opt_keys) if comp_options[k] == cur_t]
        if matches:
            default_idx = matches[0]

    col_sel, col_pat_desc = st.columns([1, 2])
    with col_sel:
        selected_display = st.selectbox(
            "🏢 Select Company for Sequence History",
            options=opt_keys,
            index=default_idx,
        )
    chosen_ticker = comp_options[selected_display]
    st.session_state.selected_ticker = chosen_ticker

    # Load 10Y history for chosen company
    company_history = df_cap[df_cap["company_id"] == chosen_ticker].copy()
    comp_cf = get_cf(chosen_ticker)

    with col_pat_desc:
        latest_pat = company_history.iloc[-1]["pattern_label"] if not company_history.empty else "N/A"
        st.info(f"**Latest Classification:** `{latest_pat}`\n\n{PATTERN_EXPLANATIONS.get(latest_pat, '')}")

    if not company_history.empty:
        # Merge with cashflow amounts
        if not comp_cf.empty:
            merged_hist = pd.merge(company_history, comp_cf, on="year", how="left")
        else:
            merged_hist = company_history

        display_history = pd.DataFrame(
            {
                "Fiscal Year": merged_hist["year"],
                "CFO Sign": merged_hist["cfo_sign"],
                "CFI Sign": merged_hist["cfi_sign"],
                "CFF Sign": merged_hist["cff_sign"],
                "Capital Allocation Pattern": merged_hist["pattern_label"],
                "CFO (₹ Cr)": merged_hist.get("operating_activity", 0.0),
                "CFI (₹ Cr)": merged_hist.get("investing_activity", 0.0),
                "CFF (₹ Cr)": merged_hist.get("financing_activity", 0.0),
            }
        )

        st.dataframe(
            display_history.style.format(
                {
                    "CFO (₹ Cr)": "₹{:,.1f}",
                    "CFI (₹ Cr)": "₹{:,.1f}",
                    "CFF (₹ Cr)": "₹{:,.1f}",
                },
                na_rep="N/A",
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.warning(f"No capital allocation sequence records found for {chosen_ticker}.")


if __name__ == "__main__":
    render()

