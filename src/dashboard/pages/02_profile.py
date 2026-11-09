"""Screen 2: Company Profile - Detailed fundamentals, KPIs, 10Y trends, and Pros/Cons."""

import os
import sys
from typing import Any, Optional

# Ensure workspace root is in sys.path
_WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.utils.db import (
    clean_company_name,
    get_bs,
    get_cf,
    get_companies,
    get_pl,
    get_prosandcons,
    get_ratios,
    get_stock_price_summary,
)


def _fmt_val(val: Any, unit: str = "", decimals: int = 2) -> str:
    """Safely format a metric value, returning 'N/A' if None, NaN, or infinite."""
    if val is None or pd.isna(val) or np.isinf(val):
        return "N/A"
    try:
        fval = float(val)
        return f"{fval:.{decimals}f}{unit}"
    except (ValueError, TypeError):
        return str(val)


def render() -> None:
    """Render the Company Profile screen."""
    try:
        st.set_page_config(layout="wide", page_title="Nifty 100 - Company Profile", page_icon="🏢")
    except Exception:
        pass

    st.title("🏢 Company Deep-Dive Profile")
    st.markdown("Comprehensive fundamental snapshot, multi-year operating trends, and investment highlights.")

    # 1. Company Search & Autocomplete
    companies_df = get_companies()
    if companies_df.empty:
        st.error("No company records found in database.")
        return

    company_options = {}
    for _, row in companies_df.iterrows():
        display_label = f"{row['id']} — {clean_company_name(row['company_name'])}"
        company_options[display_label] = row["id"]

    # Check for query param or session state default
    default_idx = 0
    query_ticker = st.query_params.get("ticker", None)
    if "selected_ticker" in st.session_state and st.session_state.selected_ticker:
        query_ticker = st.session_state.selected_ticker

    option_list = list(company_options.keys())
    if query_ticker:
        matching = [i for i, opt in enumerate(option_list) if company_options[opt].upper() == query_ticker.upper()]
        if matching:
            default_idx = matching[0]

    col_select, col_info = st.columns([2, 1])
    with col_select:
        selected_display = st.selectbox(
            "🔍 Search & Select Company (92 Nifty 100 Constituents)",
            options=option_list,
            index=default_idx,
            help="Type to search by Ticker or Company Name.",
        )

    ticker = company_options.get(selected_display, None)

    # Verification of ticker
    if not ticker:
        st.error("Ticker not found — please try another.")
        return

    company_row = companies_df[companies_df["id"] == ticker]
    if company_row.empty:
        st.error("Ticker not found — please try another.")
        return

    c_info = company_row.iloc[0]
    st.session_state.selected_ticker = ticker

    # 2. Company Header Card
    price_stats = get_stock_price_summary(ticker)
    curr_price = price_stats.get("current_price")
    h52 = price_stats.get("high_52w")
    l52 = price_stats.get("low_52w")
    mcap = price_stats.get("market_cap_crore")

    st.markdown("---")
    hdr_left, hdr_right = st.columns([3, 2])
    with hdr_left:
        st.subheader(f"{clean_company_name(c_info['company_name'])} (`{ticker}`)")
        sector_badge = c_info.get("broad_sector") or "Unclassified"
        sub_sector_badge = c_info.get("sub_sector") or "General"
        mcap_cat = c_info.get("market_cap_category") or "Large Cap"
        st.markdown(f"**Sector:** `{sector_badge}` | **Sub-sector:** `{sub_sector_badge}` | **Category:** `{mcap_cat}`")
        if pd.notna(c_info.get("about_company")) and str(c_info["about_company"]).strip():
            about_txt = str(c_info["about_company"]).split("\n")[0][:250]
            st.caption(f"{about_txt}...")

    with hdr_right:
        p_c1, p_c2, p_c3 = st.columns(3)
        with p_c1:
            st.metric("Price (₹)", _fmt_val(curr_price, decimals=1))
        with p_c2:
            st.metric("52W High / Low", f"{_fmt_val(h52, decimals=0)} / {_fmt_val(l52, decimals=0)}")
        with p_c3:
            st.metric("Market Cap", f"₹{_fmt_val(mcap, decimals=0)} Cr" if mcap else "N/A")

    # 3. 6 Core KPI Tiles (Latest Year)
    ratios_df = get_ratios(ticker)
    latest_ratio = ratios_df.iloc[-1] if not ratios_df.empty else pd.Series(dtype=object)

    st.markdown("---")
    st.subheader("⚡ Core Performance Metrics (Latest FY)")
    k1, k2, k3, k4, k5, k6 = st.columns(6)

    with k1:
        roe = latest_ratio.get("return_on_equity_pct")
        st.metric("ROE", _fmt_val(roe, "%", 1), help="Return on Equity: Net Profit / Shareholders' Equity")
    with k2:
        roce = latest_ratio.get("return_on_capital_employed_pct")
        st.metric("ROCE", _fmt_val(roce, "%", 1), help="Return on Capital Employed: EBIT / Total Capital")
    with k3:
        pe = price_stats.get("pe_ratio")
        st.metric("P/E Ratio", _fmt_val(pe, "x", 1), help="Price-to-Earnings Multiple")
    with k4:
        de = latest_ratio.get("debt_to_equity")
        st.metric("Debt / Equity", _fmt_val(de, "x", 2), help="Total Borrowings / Shareholders' Equity")
    with k5:
        opm = latest_ratio.get("operating_profit_margin_pct")
        st.metric("Operating Margin", _fmt_val(opm, "%", 1), help="Operating Profit Margin (OPM)")
    with k6:
        fcf = latest_ratio.get("free_cash_flow_cr")
        st.metric("Free Cash Flow", f"₹{_fmt_val(fcf, decimals=0)} Cr" if fcf is not None and pd.notna(fcf) else "N/A", help="Operating Cash Flow - Capex")

    st.markdown("---")

    # 4. Interactive Trend Charts (10-Year Revenue & PAT + 10-Year ROE & ROCE)
    chart1_col, chart2_col = st.columns(2, gap="medium")

    # Chart 1: Revenue & PAT Trend
    pl_df = get_pl(ticker)
    with chart1_col:
        st.subheader("📊 10-Year Revenue & PAT Trend")
        if not pl_df.empty and "sales" in pl_df.columns and "net_profit" in pl_df.columns:
            fig_pl = go.Figure()
            fig_pl.add_trace(
                go.Bar(
                    x=pl_df["year"],
                    y=pl_df["sales"],
                    name="Revenue / Sales (₹ Cr)",
                    marker_color="#2563eb",
                    hovertemplate="<b>%{x}</b><br>Revenue: ₹%{y:,.1f} Cr<extra></extra>",
                )
            )
            fig_pl.add_trace(
                go.Bar(
                    x=pl_df["year"],
                    y=pl_df["net_profit"],
                    name="Net Profit / PAT (₹ Cr)",
                    marker_color="#10b981",
                    hovertemplate="<b>%{x}</b><br>Net Profit: ₹%{y:,.1f} Cr<extra></extra>",
                )
            )
            fig_pl.update_layout(
                barmode="group",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(t=30, b=20, l=10, r=10),
                height=380,
                xaxis_title="Fiscal Year",
                yaxis_title="Amount (₹ Cr)",
            )
            st.plotly_chart(fig_pl, use_container_width=True)
        else:
            st.info("No P&L historical trend data available.")

    # Chart 2: 10-Year ROE vs ROCE Dual Line Chart
    with chart2_col:
        st.subheader("📈 10-Year ROE vs ROCE Trend")
        if not ratios_df.empty and "return_on_equity_pct" in ratios_df.columns and "return_on_capital_employed_pct" in ratios_df.columns:
            fig_ratios = go.Figure()
            fig_ratios.add_trace(
                go.Scatter(
                    x=ratios_df["year"],
                    y=ratios_df["return_on_equity_pct"],
                    mode="lines+markers",
                    name="ROE (%)",
                    line=dict(color="#8b5cf6", width=2.5),
                    marker=dict(size=7),
                    hovertemplate="<b>%{x}</b><br>ROE: %{y:.1f}%<extra></extra>",
                )
            )
            fig_ratios.add_trace(
                go.Scatter(
                    x=ratios_df["year"],
                    y=ratios_df["return_on_capital_employed_pct"],
                    mode="lines+markers",
                    name="ROCE (%)",
                    line=dict(color="#f59e0b", width=2.5, dash="dash"),
                    marker=dict(size=7),
                    hovertemplate="<b>%{x}</b><br>ROCE: %{y:.1f}%<extra></extra>",
                )
            )
            fig_ratios.update_layout(
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(t=30, b=20, l=10, r=10),
                height=380,
                xaxis_title="Fiscal Year",
                yaxis_title="Return (%)",
            )
            st.plotly_chart(fig_ratios, use_container_width=True)
        else:
            st.info("No ROE/ROCE historical trend data available.")

    st.markdown("---")

    # 5. Pros and Cons Display
    st.subheader("📋 Qualitative Pros & Cons Analysis")
    pc_data = get_prosandcons(ticker)
    pros = pc_data.get("pros", [])
    cons = pc_data.get("cons", [])

    pro_col, con_col = st.columns(2, gap="large")
    with pro_col:
        st.markdown("#### 🟢 Key Strengths (Pros)")
        if pros:
            for p in pros:
                st.markdown(f"- ✅ **{p}**")
        else:
            st.write("• No major positive flags recorded.")

    with con_col:
        st.markdown("#### 🔴 Key Risks & Concerns (Cons)")
        if cons:
            for c in cons:
                st.markdown(f"- ❌ **{c}**")
        else:
            st.write("• No major negative concerns recorded.")

    # 6. Financial Statements Collapsible View
    with st.expander("📑 View Complete 10-Year Financial Statements History"):
        tab_pl, tab_bs, tab_cf = st.tabs(["Profit & Loss", "Balance Sheet", "Cash Flow"])
        with tab_pl:
            if not pl_df.empty:
                st.dataframe(pl_df, use_container_width=True, hide_index=True)
            else:
                st.write("P&L data unavailable.")
        with tab_bs:
            bs_df = get_bs(ticker)
            if not bs_df.empty:
                st.dataframe(bs_df, use_container_width=True, hide_index=True)
            else:
                st.write("Balance Sheet data unavailable.")
        with tab_cf:
            cf_df = get_cf(ticker)
            if not cf_df.empty:
                st.dataframe(cf_df, use_container_width=True, hide_index=True)
            else:
                st.write("Cash Flow data unavailable.")


if __name__ == "__main__":
    render()

