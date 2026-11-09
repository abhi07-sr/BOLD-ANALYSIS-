"""Screen 4: Peer Comparison - Industry group rankings, radar charts, and gold benchmark table."""

import os
import sys
from typing import Any, List

# Ensure workspace root is in sys.path
_WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.utils.db import clean_company_name, get_peer_percentiles, get_peers


def render() -> None:
    """Render the Peer Comparison screen."""
    try:
        st.set_page_config(layout="wide", page_title="Nifty 100 - Peer Comparison", page_icon="👥")
    except Exception:
        pass

    st.title("👥 Peer Comparison & Sector Benchmarking")
    st.markdown("Analyze relative operational quality, profitability, and balance sheet strength within 11 industry peer groups.")

    # 1. Select Peer Group
    group_df = get_peers()
    if group_df.empty or "peer_group_name" not in group_df.columns:
        st.error("No peer groups found.")
        return

    available_groups = group_df["peer_group_name"].dropna().unique().tolist()
    default_group = "Automobiles" if "Automobiles" in available_groups else available_groups[0]

    col_g, col_c = st.columns([1, 1])
    with col_g:
        selected_group = st.selectbox(
            "🏢 Select Peer Group (11 Groups)",
            options=available_groups,
            index=available_groups.index(default_group),
        )

    # 2. Get Peers in Selected Group
    peers_df = get_peers(selected_group)
    if peers_df.empty:
        st.warning(f"No company records found for {selected_group}.")
        return

    peers_df["clean_name"] = peers_df["company_name"].apply(clean_company_name)

    # Select company to inspect in radar chart
    company_options = {f"{r['company_id']} — {r['clean_name']}": r["company_id"] for _, r in peers_df.iterrows()}
    with col_c:
        selected_label = st.selectbox(
            "🎯 Select Company to Compare",
            options=list(company_options.keys()),
            index=0,
        )
    selected_ticker = company_options[selected_label]

    st.markdown("---")

    # 3. Radar Chart (Comparing Selected Company vs Peer Group Percentiles / Averages)
    radar_col, summary_col = st.columns([3, 2], gap="large")

    radar_metrics = [
        ("return_on_equity_pct", "ROE"),
        ("return_on_capital_employed_pct", "ROCE"),
        ("net_profit_margin_pct", "Net Margin"),
        ("debt_to_equity", "Leverage (D/E)"),
        ("free_cash_flow_cr", "Free Cash Flow"),
        ("revenue_cagr_5yr", "5Y Rev CAGR"),
        ("pat_cagr_5yr", "5Y PAT CAGR"),
        ("asset_turnover", "Asset Turnover"),
    ]

    pp_df = get_peer_percentiles(selected_group)
    comp_pp = pp_df[pp_df["company_id"] == selected_ticker]

    categories: List[str] = []
    comp_values: List[float] = []
    peer_avg_values: List[float] = []

    for col_key, label in radar_metrics:
        categories.append(label)
        # Percentile rank (0 to 100)
        match_row = comp_pp[comp_pp["metric"] == col_key]
        if not match_row.empty and pd.notna(match_row["percentile_rank"].iloc[0]):
            val = float(match_row["percentile_rank"].iloc[0]) * 100.0
        else:
            # Fallback to normalized min-max if not in percentiles table
            if col_key in peers_df.columns:
                series = peers_df[col_key].dropna()
                if not series.empty and series.max() > series.min():
                    raw_val = peers_df[peers_df["company_id"] == selected_ticker][col_key].values
                    v = raw_val[0] if len(raw_val) > 0 and pd.notna(raw_val[0]) else series.min()
                    val = float((v - series.min()) / (series.max() - series.min()) * 100.0)
                else:
                    val = 50.0
            else:
                val = 50.0

        comp_values.append(round(val, 1))
        peer_avg_values.append(50.0)  # Peer group median benchmark is 50th percentile

    # Close radar loop
    radar_categories = categories + [categories[0]]
    radar_comp_vals = comp_values + [comp_values[0]]
    radar_peer_vals = peer_avg_values + [peer_avg_values[0]]

    with radar_col:
        st.subheader(f"🕸️ Percentile Radar Chart: `{selected_ticker}` vs Peer Median")
        fig_radar = go.Figure()

        # Peer Median Reference
        fig_radar.add_trace(
            go.Scatterpolar(
                r=radar_peer_vals,
                theta=radar_categories,
                fill=None,
                name="Peer Group Median (50th %ile)",
                line=dict(color="#94a3b8", width=2, dash="dash"),
                hoverinfo="theta+r",
            )
        )

        # Selected Company
        fig_radar.add_trace(
            go.Scatterpolar(
                r=radar_comp_vals,
                theta=radar_categories,
                fill="toself",
                fillcolor="rgba(37, 99, 235, 0.25)",
                name=f"{selected_ticker} (%ile Rank)",
                line=dict(color="#2563eb", width=3),
                hoverinfo="theta+r",
            )
        )

        fig_radar.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 100],
                    tickvals=[25, 50, 75, 100],
                    ticksuffix="%",
                )
            ),
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
            margin=dict(t=20, b=30, l=40, r=40),
            height=440,
        )
        st.plotly_chart(fig_radar, use_container_width=True)

    with summary_col:
        st.subheader("📌 Peer Group Overview")
        benchmark_row = peers_df[peers_df["is_benchmark"] == 1]
        benchmark_name = clean_company_name(benchmark_row["company_name"].iloc[0]) if not benchmark_row.empty else "N/A"
        benchmark_ticker = benchmark_row["company_id"].iloc[0] if not benchmark_row.empty else "N/A"

        st.info(
            f"**Peer Group:** {selected_group}\n\n"
            f"**Total Constituents:** {len(peers_df)}\n\n"
            f"**Group Benchmark Leader:** 🏆 `{benchmark_ticker}` ({benchmark_name})\n\n"
            f"The radar chart displays relative percentile performance (0–100%) against industry peers."
        )

        # Quick stats for selected company
        sel_row = peers_df[peers_df["company_id"] == selected_ticker].iloc[0]
        st.markdown(f"#### `{selected_ticker}` Snapshot")
        s_c1, s_c2 = st.columns(2)
        with s_c1:
            st.metric("ROE", f"{sel_row['return_on_equity_pct']:.1f}%" if pd.notna(sel_row['return_on_equity_pct']) else "N/A")
            st.metric("ROCE", f"{sel_row['return_on_capital_employed_pct']:.1f}%" if pd.notna(sel_row['return_on_capital_employed_pct']) else "N/A")
        with s_c2:
            st.metric("D/E", f"{sel_row['debt_to_equity']:.2f}" if pd.notna(sel_row['debt_to_equity']) else "N/A")
            fcf_val = sel_row['free_cash_flow_cr']
            st.metric("FCF", f"₹{fcf_val:,.0f} Cr" if pd.notna(fcf_val) else "N/A")

    st.markdown("---")

    # 4. Side-by-side KPI Comparison Table (with Gold Benchmark Highlight)
    st.subheader(f"📋 Side-by-Side KPI Comparison ({selected_group})")
    st.caption("🏆 The benchmark constituent designated by industry authority is highlighted in gold.")

    table_data = []
    for _, row in peers_df.iterrows():
        is_bm = row.get("is_benchmark", 0) == 1
        table_data.append(
            {
                "Benchmark": "🏆 Benchmark" if is_bm else "",
                "Ticker": row["company_id"],
                "Company": clean_company_name(row["company_name"]),
                "ROE (%)": row.get("return_on_equity_pct"),
                "ROCE (%)": row.get("return_on_capital_employed_pct"),
                "Net Margin (%)": row.get("net_profit_margin_pct"),
                "Debt/Equity": row.get("debt_to_equity"),
                "FCF (₹ Cr)": row.get("free_cash_flow_cr"),
                "5Y Rev CAGR (%)": row.get("revenue_cagr_5yr"),
                "5Y PAT CAGR (%)": row.get("pat_cagr_5yr"),
                "Asset Turnover": row.get("asset_turnover"),
            }
        )

    kpi_df = pd.DataFrame(table_data)

    def _highlight_benchmark(s: pd.Series) -> List[str]:
        is_benchmark = s["Benchmark"] == "🏆 Benchmark"
        return ["background-color: #fef3c7; color: #92400e; font-weight: bold;" if is_benchmark else "" for _ in s]

    styled_df = (
        kpi_df.style.apply(_highlight_benchmark, axis=1)
        .format(
            {
                "ROE (%)": "{:.1f}%",
                "ROCE (%)": "{:.1f}%",
                "Net Margin (%)": "{:.1f}%",
                "Debt/Equity": "{:.2f}",
                "FCF (₹ Cr)": "₹{:,.0f}",
                "5Y Rev CAGR (%)": "{:.1f}%",
                "5Y PAT CAGR (%)": "{:.1f}%",
                "Asset Turnover": "{:.2f}x",
            },
            na_rep="N/A",
        )
    )

    st.dataframe(
        styled_df,
        use_container_width=True,
        hide_index=True,
        height=320,
    )


if __name__ == "__main__":
    render()

