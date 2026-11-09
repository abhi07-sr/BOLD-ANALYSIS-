"""Screen 1: Home / Macro Overview - Nifty 100 Financial Analytics Dashboard."""

import os
import sys
from typing import Any

# Ensure workspace root is in sys.path
_WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

import pandas as pd
import plotly.express as px
import streamlit as st

from src.dashboard.utils.db import clean_company_name, get_all_screener_data, get_home_kpis, get_sectors


def render() -> None:
    """Render the Home / Macro Overview screen."""
    try:
        st.set_page_config(layout="wide", page_title="Nifty 100 - Macro Overview", page_icon="🏠")
    except Exception:
        pass

    st.title("🏛️ Nifty 100 — Macro Financial Overview")
    st.markdown("Comprehensive executive macro summary of India's premier 92 non-financial & financial leaders.")

    # Year selector
    col_hdr, col_year = st.columns([3, 1])
    with col_year:
        year = st.selectbox(
            "📅 Analysis Fiscal Year",
            options=["2024", "2023", "2022", "2021", "2020", "2019"],
            index=0,
            help="Select fiscal year to dynamically update macro aggregates and sector statistics.",
        )

    # 6 Summary KPI tiles
    kpis = get_home_kpis(str(year))

    st.markdown("---")
    st.subheader(f"📊 Market Aggregates & Quality Health (FY {year})")

    kpi_col1, kpi_col2, kpi_col3, kpi_col4, kpi_col5, kpi_col6 = st.columns(6)

    with kpi_col1:
        st.metric(
            label="Average ROE",
            value=f"{kpis['avg_roe']}%",
            help="Average Return on Equity across all active non-financial and financial constituents.",
        )
    with kpi_col2:
        st.metric(
            label="Median P/E",
            value=f"{kpis['median_pe']}x",
            help="Median Price-to-Earnings multiple (trailing valuation multiple).",
        )
    with kpi_col3:
        st.metric(
            label="Median D/E",
            value=f"{kpis['median_de']}",
            help="Median Debt-to-Equity ratio (excludes Financials sector).",
        )
    with kpi_col4:
        st.metric(
            label="Total Companies",
            value=f"{kpis['total_companies']}",
            help="Total monitored Nifty 100 constituent enterprises in database.",
        )
    with kpi_col5:
        st.metric(
            label="Median 5Y Rev CAGR",
            value=f"{kpis['median_rev_cagr_5yr']}%",
            help="Median 5-Year compound annual revenue growth rate.",
        )
    with kpi_col6:
        st.metric(
            label="Debt-Free Companies",
            value=f"{kpis['debt_free_count']}",
            help="Count of non-financial companies with D/E <= 0.05.",
        )

    st.markdown("---")

    # Layout: Sector Distribution Donut + Top 5 Quality Table
    chart_col, table_col = st.columns([1, 1], gap="large")

    with chart_col:
        st.subheader("🍩 Sector Composition")
        sectors_df = get_sectors()
        if not sectors_df.empty:
            fig = px.pie(
                sectors_df,
                values="company_count",
                names="broad_sector",
                hole=0.45,
                color_discrete_sequence=px.colors.qualitative.Prism,
                custom_data=["total_weight"],
            )
            fig.update_traces(
                textposition="inside",
                textinfo="percent+label",
                hovertemplate="<b>%{label}</b><br>Count: %{value} companies<br>Index Weight: %{customdata[0]}%<extra></extra>",
            )
            fig.update_layout(
                showlegend=True,
                margin=dict(t=20, b=20, l=10, r=10),
                legend=dict(orientation="h", yanchor="top", y=-0.1, xanchor="center", x=0.5),
                height=420,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No sector data available.")

    with table_col:
        st.subheader("⭐ Top 5 Quality Compounders")
        screener_df = get_all_screener_data()
        if not screener_df.empty:
            sorted_df = screener_df.sort_values(by="composite_quality_score", ascending=False).head(5).copy()
            sorted_df["clean_name"] = sorted_df["company_name"].apply(clean_company_name)

            display_df = pd.DataFrame(
                {
                    "Rank": range(1, len(sorted_df) + 1),
                    "Company": sorted_df["clean_name"],
                    "Sector": sorted_df["broad_sector"],
                    "Quality Score": sorted_df["composite_quality_score"].apply(lambda x: f"{x:.1f} / 100"),
                    "ROE (%)": sorted_df["return_on_equity_pct"].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "N/A"),
                    "P/E (x)": sorted_df["pe_ratio"].apply(lambda x: f"{x:.1f}x" if pd.notna(x) and x > 0 else "N/A"),
                }
            )
            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Rank": st.column_config.NumberColumn(width="small"),
                    "Company": st.column_config.TextColumn(width="medium"),
                    "Sector": st.column_config.TextColumn(width="medium"),
                    "Quality Score": st.column_config.TextColumn(width="small"),
                    "ROE (%)": st.column_config.TextColumn(width="small"),
                    "P/E (x)": st.column_config.TextColumn(width="small"),
                },
            )
            st.caption("Composite Quality Score combines 6 factors: ROE, OPM, Rev CAGR, PAT CAGR, D/E, and FCF.")
        else:
            st.info("No quality ranking data available.")


if __name__ == "__main__":
    render()

