"""Screen 5: Trend Analysis - 10-year historical trajectory across financial metrics with YoY change hover."""

import os
import sys
from typing import Any, Dict, List

# Ensure workspace root is in sys.path
_WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from src.dashboard.utils.db import clean_company_name, get_companies, get_pl, get_ratios

METRIC_MAP: Dict[str, Dict[str, Any]] = {
    "Revenue": {"col": "sales", "unit": "₹ Cr", "fmt": "₹{:,.1f} Cr", "color": "#2563eb"},
    "PAT": {"col": "net_profit", "unit": "₹ Cr", "fmt": "₹{:,.1f} Cr", "color": "#10b981"},
    "EPS": {"col": "eps", "unit": "₹/share", "fmt": "₹{:.2f}", "color": "#8b5cf6"},
    "ROE": {"col": "return_on_equity_pct", "unit": "%", "fmt": "{:.1f}%", "color": "#f59e0b"},
    "ROCE": {"col": "return_on_capital_employed_pct", "unit": "%", "fmt": "{:.1f}%", "color": "#ec4899"},
    "OPM": {"col": "operating_profit_margin_pct", "unit": "%", "fmt": "{:.1f}%", "color": "#06b6d4"},
    "D/E": {"col": "debt_to_equity", "unit": "x", "fmt": "{:.2f}x", "color": "#ef4444"},
    "FCF": {"col": "free_cash_flow_cr", "unit": "₹ Cr", "fmt": "₹{:,.0f} Cr", "color": "#14b8a6"},
}


def render() -> None:
    """Render the Trend Analysis screen."""
    try:
        st.set_page_config(layout="wide", page_title="Nifty 100 - Trend Analysis", page_icon="📈")
    except Exception:
        pass

    st.title("📈 10-Year Historical Financial Trend Analysis")
    st.markdown("Inspect multi-year trajectories, YoY growth momentum, and operating inflection points.")

    # 1. Company Selection
    companies_df = get_companies()
    if companies_df.empty:
        st.error("No companies found in database.")
        return

    company_options = {f"{r['id']} — {clean_company_name(r['company_name'])}": r["id"] for _, r in companies_df.iterrows()}
    option_list = list(company_options.keys())

    # Check default from session state
    default_idx = 0
    if "selected_ticker" in st.session_state and st.session_state.selected_ticker:
        cur_t = st.session_state.selected_ticker
        matches = [i for i, opt in enumerate(option_list) if company_options[opt] == cur_t]
        if matches:
            default_idx = matches[0]

    col_comp, col_metrics = st.columns([1, 1])
    with col_comp:
        selected_display = st.selectbox(
            "🏢 Select Company",
            options=option_list,
            index=default_idx,
            help="Choose company to load 10-year operating history.",
        )
    ticker = company_options[selected_display]
    st.session_state.selected_ticker = ticker

    # 2. Metric Multi-Selector (Choose up to 3 metrics)
    with col_metrics:
        selected_metrics = st.multiselect(
            "📊 Select Financial Metrics (up to 3)",
            options=list(METRIC_MAP.keys()),
            default=["Revenue", "PAT", "ROE"],
            max_selections=3,
            help="Select up to 3 metrics from Revenue, PAT, EPS, ROE, ROCE, OPM, D/E, FCF.",
        )

    if not selected_metrics:
        st.info("Please select at least 1 metric above to render trend charts.")
        return

    # 3. Load & Merge Data
    pl_df = get_pl(ticker)
    ratios_df = get_ratios(ticker)

    if pl_df.empty and ratios_df.empty:
        st.warning(f"No historical records found for {ticker}.")
        return

    # Merge by year
    if not pl_df.empty and not ratios_df.empty:
        merged = pd.merge(pl_df, ratios_df, on="year", how="outer", suffixes=("_pl", "_fr"))
    elif not pl_df.empty:
        merged = pl_df
    else:
        merged = ratios_df

    # Standardize column names if needed
    if "operating_profit_margin_pct" not in merged.columns and "opm_percentage" in merged.columns:
        merged["operating_profit_margin_pct"] = merged["opm_percentage"]

    # Filter out TTM and sort chronologically
    merged = merged[merged["year"] != "TTM"].copy()
    merged = merged.sort_values(by="year")

    st.markdown("---")

    # 4. Interactive Plotly Trend Charts with YoY % Change on Hover
    st.subheader(f"📊 Multi-Year Trajectory: {selected_display}")

    # Create subplots (one for each selected metric to keep scale clean and clear)
    num_metrics = len(selected_metrics)
    fig = make_subplots(
        rows=num_metrics,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.1,
        subplot_titles=[f"{m} ({METRIC_MAP[m]['unit']})" for m in selected_metrics],
    )

    summary_tables: Dict[str, pd.DataFrame] = {}

    for idx, metric_name in enumerate(selected_metrics, start=1):
        info = METRIC_MAP[metric_name]
        col_name = info["col"]

        if col_name not in merged.columns:
            continue

        series = merged[col_name].astype(float)
        years = merged["year"].tolist()

        # Compute YoY % changes
        yoy_pcts = series.pct_change() * 100.0
        yoy_labels = []
        for v in yoy_pcts:
            if pd.isna(v) or np.isinf(v):
                yoy_labels.append("N/A (base year)")
            elif v > 0:
                yoy_labels.append(f"+{v:.1f}%")
            else:
                yoy_labels.append(f"{v:.1f}%")

        customdata = list(zip(yoy_labels, [info["unit"]] * len(series)))

        fig.add_trace(
            go.Scatter(
                x=years,
                y=series,
                mode="lines+markers",
                name=metric_name,
                line=dict(color=info["color"], width=3),
                marker=dict(size=8),
                customdata=customdata,
                hovertemplate=(
                    f"<b>%{{x}}</b><br>"
                    f"{metric_name}: %{{y:,.2f}} %{{customdata[1]}}<br>"
                    f"<b>YoY Growth: %{{customdata[0]}}</b><extra></extra>"
                ),
            ),
            row=idx,
            col=1,
        )

        fig.update_yaxes(title_text=info["unit"], row=idx, col=1)

        # Store for data table
        summary_tables[metric_name] = pd.DataFrame(
            {
                "Year": years,
                f"{metric_name} ({info['unit']})": series,
                "YoY Growth": yoy_labels,
            }
        )

    fig.update_layout(
        height=260 * num_metrics,
        showlegend=False,
        margin=dict(t=40, b=20, l=10, r=10),
    )
    st.plotly_chart(fig, use_container_width=True)

    # 5. Tabular Data View
    st.markdown("---")
    with st.expander("📋 Detailed Year-by-Year YoY Growth Table"):
        tab_cols = st.columns(len(selected_metrics))
        for i, m_name in enumerate(selected_metrics):
            with tab_cols[i]:
                st.markdown(f"**{m_name}**")
                if m_name in summary_tables:
                    st.dataframe(summary_tables[m_name], use_container_width=True, hide_index=True)


if __name__ == "__main__":
    render()

