"""Screen 6: Sector Deep-Dive - Multi-sector analysis, bubble map, and median KPI benchmarking."""

import os
import sys
from typing import Any, List

# Ensure workspace root is in sys.path
_WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.utils.db import clean_company_name, get_all_screener_data, get_sectors


def render() -> None:
    """Render the Sector Deep-Dive screen."""
    try:
        st.set_page_config(layout="wide", page_title="Nifty 100 - Sector Deep-Dive", page_icon="🏭")
    except Exception:
        pass

    st.title("🏭 Sector Deep-Dive & Multi-Company Distribution")
    st.markdown("Examine sector concentration, valuation, growth positioning, and performance vs Nifty 100 benchmark medians.")

    master_df = get_all_screener_data()
    if master_df.empty:
        st.error("No company records available.")
        return

    master_df["clean_name"] = master_df["company_name"].apply(clean_company_name)

    # 1. Sector Selection Dropdown
    sectors_series = master_df["broad_sector"].dropna().unique().tolist()
    sectors_series.sort()
    sector_options = ["All Sectors"] + sectors_series

    col_sec, col_kpis = st.columns([1, 2])
    with col_sec:
        selected_sector = st.selectbox(
            "🏢 Select Broad Sector",
            options=sector_options,
            index=0,
            help="Filter by broad industry sector or view full market distribution.",
        )

    # Filter data
    if selected_sector == "All Sectors":
        sector_df = master_df.copy()
    else:
        sector_df = master_df[master_df["broad_sector"] == selected_sector].copy()

    # Sector summary metrics
    with col_kpis:
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("Companies", f"{len(sector_df)}")
        with m2:
            med_roe = sector_df["return_on_equity_pct"].median()
            st.metric("Sector Median ROE", f"{med_roe:.1f}%" if pd.notna(med_roe) else "N/A")
        with m3:
            med_pe = sector_df[sector_df["pe_ratio"] > 0]["pe_ratio"].median()
            st.metric("Sector Median P/E", f"{med_pe:.1f}x" if pd.notna(med_pe) else "N/A")
        with m4:
            tot_mcap = sector_df["market_cap_crore"].sum()
            st.metric("Total Market Cap", f"₹{tot_mcap / 1e5:.1f} Lakh Cr" if pd.notna(tot_mcap) else "N/A")

    st.markdown("---")

    # 2. Bubble Chart: X = Revenue, Y = ROE, Size = Market Cap, Color = Sub-Sector
    st.subheader(f"🫧 Valuation & Scale Positioning ({selected_sector})")
    st.caption("X-axis: Revenue (Sales ₹ Cr) | Y-axis: Return on Equity (ROE %) | Bubble Size: Market Cap (₹ Cr) | Color: Sub-sector")

    # Clean data for plotting
    plot_df = sector_df.dropna(subset=["sales", "return_on_equity_pct"]).copy()
    # Replace any zero or negative market cap with small positive for bubble size
    plot_df["bubble_size"] = plot_df["market_cap_crore"].apply(lambda x: max(float(x), 100.0) if pd.notna(x) else 100.0)
    plot_df["sub_sector_clean"] = plot_df["sub_sector"].fillna("General")

    if not plot_df.empty:
        fig_bubble = px.scatter(
            plot_df,
            x="sales",
            y="return_on_equity_pct",
            size="bubble_size",
            color="sub_sector_clean",
            hover_name="clean_name",
            hover_data={
                "sales": ":,.1f",
                "return_on_equity_pct": ":.1f",
                "market_cap_crore": ":,.0f",
                "bubble_size": False,
                "sub_sector_clean": True,
            },
            labels={
                "sales": "Annual Revenue (₹ Cr)",
                "return_on_equity_pct": "Return on Equity (ROE %)",
                "sub_sector_clean": "Sub-sector",
                "market_cap_crore": "Market Cap (₹ Cr)",
            },
            size_max=50,
            color_discrete_sequence=px.colors.qualitative.Safe,
        )
        fig_bubble.update_layout(
            height=500,
            margin=dict(t=30, b=20, l=10, r=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig_bubble, use_container_width=True)
    else:
        st.info("Insufficient financial metrics to generate bubble chart.")

    st.markdown("---")

    # 3. Sector Median KPI Bar Chart (Sector Median vs Nifty 100 Overall Benchmark)
    st.subheader(f"📊 Sector Median Benchmarking vs Overall Nifty 100")

    bench_metrics = [
        ("ROE (%)", "return_on_equity_pct"),
        ("ROCE (%)", "return_on_capital_employed_pct"),
        ("OPM (%)", "operating_profit_margin_pct"),
        ("P/E (x)", "pe_ratio"),
        ("5Y Rev CAGR (%)", "revenue_cagr_5yr"),
    ]

    metric_names = []
    sector_medians = []
    overall_medians = []

    for label, col_key in bench_metrics:
        if col_key in master_df.columns and col_key in sector_df.columns:
            metric_names.append(label)
            # Sector median
            s_val = sector_df[col_key].dropna()
            if col_key == "pe_ratio":
                s_val = s_val[s_val > 0]
            sec_med = s_val.median() if not s_val.empty else 0.0
            sector_medians.append(round(float(sec_med), 1))

            # Overall median
            o_val = master_df[col_key].dropna()
            if col_key == "pe_ratio":
                o_val = o_val[o_val > 0]
            ov_med = o_val.median() if not o_val.empty else 0.0
            overall_medians.append(round(float(ov_med), 1))

    fig_bar = go.Figure()
    fig_bar.add_trace(
        go.Bar(
            x=metric_names,
            y=sector_medians,
            name=f"{selected_sector} Median",
            marker_color="#2563eb",
            text=[f"{v:.1f}" for v in sector_medians],
            textposition="auto",
        )
    )
    fig_bar.add_trace(
        go.Bar(
            x=metric_names,
            y=overall_medians,
            name="Nifty 100 Benchmark Median",
            marker_color="#94a3b8",
            text=[f"{v:.1f}" for v in overall_medians],
            textposition="auto",
        )
    )

    fig_bar.update_layout(
        barmode="group",
        height=380,
        margin=dict(t=20, b=20, l=10, r=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        yaxis_title="Median Metric Value",
    )
    st.plotly_chart(fig_bar, use_container_width=True)

    # 4. Sector Constituents Breakdown
    with st.expander(f"📋 View All {len(sector_df)} Constituents in {selected_sector}"):
        disp_cols = {
            "clean_name": "Company Name",
            "company_id": "Ticker",
            "sub_sector": "Sub-Sector",
            "sales": "Revenue (₹ Cr)",
            "return_on_equity_pct": "ROE (%)",
            "operating_profit_margin_pct": "OPM (%)",
            "pe_ratio": "P/E",
            "market_cap_crore": "Market Cap (₹ Cr)",
        }
        avail = [c for c in disp_cols.keys() if c in sector_df.columns]
        sub_df = sector_df[avail].rename(columns=disp_cols)
        st.dataframe(
            sub_df.style.format(
                {
                    "Revenue (₹ Cr)": "₹{:,.0f}",
                    "ROE (%)": "{:.1f}%",
                    "OPM (%)": "{:.1f}%",
                    "P/E": "{:.1f}x",
                    "Market Cap (₹ Cr)": "₹{:,.0f}",
                },
                na_rep="N/A",
            ),
            use_container_width=True,
            hide_index=True,
        )


if __name__ == "__main__":
    render()

