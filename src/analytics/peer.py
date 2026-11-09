"""Peer Engine: Group percentile rankings, radar charts, and Excel peer reports.

Implements:
- 10-metric peer percentile ranking with inverted D/E ranking
- SQLite peer_percentiles table population
- Unassigned company handling ("No peer group assigned")
- 8-axis PNG radar charts with peer/universe overlay in reports/radar_charts/
- 11-sheet formatted Excel workbook in output/peer_comparison.xlsx
"""

import os
import sqlite3
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

# Ensure workspace root is in sys.path for direct script execution
_WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
import pandas as pd

from src.screener.engine import build_screener_dataset, compute_composite_quality_score

# 10 core metrics for peer comparison
PEER_METRICS = [
    ("return_on_equity_pct", "ROE (%)", False),
    ("return_on_capital_employed_pct", "ROCE (%)", False),
    ("net_profit_margin_pct", "NPM (%)", False),
    ("debt_to_equity", "D/E", True),  # Inverted: lower D/E -> higher percentile
    ("free_cash_flow_cr", "FCF (Cr)", False),
    ("pat_cagr_5yr", "PAT CAGR 5Y (%)", False),
    ("revenue_cagr_5yr", "Rev CAGR 5Y (%)", False),
    ("eps_cagr_5yr", "EPS CAGR 5Y (%)", False),
    ("interest_coverage", "ICR", False),
    ("asset_turnover", "Asset Turnover", False),
]

# 8 axes for radar charts
RADAR_AXES = [
    ("return_on_equity_pct", "ROE", False),
    ("return_on_capital_employed_pct", "ROCE", False),
    ("net_profit_margin_pct", "NPM", False),
    ("debt_to_equity", "Low D/E", True),  # Inverted
    ("fcf_margin", "FCF Score", False),
    ("pat_cagr_5yr", "PAT CAGR 5Y", False),
    ("revenue_cagr_5yr", "Rev CAGR 5Y", False),
    ("composite_quality_score", "Quality Score", False),
]


def calc_percent_rank(series: pd.Series, invert: bool = False) -> pd.Series:
    """Compute PERCENT_RANK = (rank - 1) / (N - 1).

    If invert is True, returns 1.0 - PERCENT_RANK.
    """
    valid = series.dropna()
    n = len(valid)
    if n <= 1:
        return series.apply(lambda x: 1.0 if pd.notna(x) else np.nan)

    ranks = series.rank(ascending=True, method="min")
    pct_rank = (ranks - 1.0) / (n - 1.0)

    if invert:
        pct_rank = 1.0 - pct_rank

    return pct_rank.round(4)


def compute_peer_percentiles(
    conn: sqlite3.Connection, year: Optional[str] = None
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Compute percentile ranks for all 10 metrics across all 11 peer groups.

    Populates the `peer_percentiles` SQLite table.

    Returns:
        Tuple[pd.DataFrame, pd.DataFrame]:
            - Master scored DataFrame with peer percentiles added
            - Long-form DataFrame inserted into peer_percentiles SQLite table
    """
    # 1. Master dataset with composite scores
    master = build_screener_dataset(conn, year=year)
    scored = compute_composite_quality_score(master)

    # 2. Peer groups mapping
    df_pg = pd.read_sql("SELECT peer_group_name, company_id, is_benchmark FROM peer_groups", conn)
    scored = scored.merge(df_pg, on="company_id", how="left")

    records_to_insert: List[Dict[str, Any]] = []

    # Get distinct peer groups
    peer_groups = [g for g in scored["peer_group_name"].dropna().unique()]

    # Add percentile columns to master dataframe
    for col_key, _, invert in PEER_METRICS:
        scored[f"{col_key}_rank"] = np.nan

    for group_name in peer_groups:
        grp_idx = scored[scored["peer_group_name"] == group_name].index
        grp_df = scored.loc[grp_idx]

        for col_key, _, invert in PEER_METRICS:
            pct_ranks = calc_percent_rank(grp_df[col_key], invert=invert)
            scored.loc[grp_idx, f"{col_key}_rank"] = pct_ranks

            for idx, r in grp_df.iterrows():
                cid = r["company_id"]
                val = r[col_key]
                p_rank = pct_ranks.loc[idx]
                r_year = str(r["year"])

                records_to_insert.append(
                    {
                        "company_id": cid,
                        "peer_group_name": group_name,
                        "metric": col_key,
                        "value": None if pd.isna(val) else float(val),
                        "percentile_rank": None if pd.isna(p_rank) else float(p_rank),
                        "year": r_year,
                    }
                )

    # 3. Populate SQLite peer_percentiles table
    cursor = conn.cursor()
    cursor.execute("DELETE FROM peer_percentiles")
    insert_sql = """
        INSERT INTO peer_percentiles (company_id, peer_group_name, metric, value, percentile_rank, year)
        VALUES (:company_id, :peer_group_name, :metric, :value, :percentile_rank, :year)
    """
    cursor.executemany(insert_sql, records_to_insert)
    conn.commit()

    long_df = pd.DataFrame(records_to_insert)
    return scored, long_df


def get_company_peer_group(company_id: str, conn: sqlite3.Connection) -> Union[str, Dict[str, Any]]:
    """Retrieve peer group and rankings for a company.

    If company is not assigned to any peer group, returns message "No peer group assigned".
    """
    query = """
        SELECT peer_group_name, is_benchmark
        FROM peer_groups
        WHERE company_id = ?
    """
    res = conn.execute(query, (company_id,)).fetchone()
    if not res:
        return "No peer group assigned"

    pg_name, is_bm = res
    ranks_query = """
        SELECT metric, value, percentile_rank
        FROM peer_percentiles
        WHERE company_id = ?
    """
    ranks = pd.read_sql(ranks_query, conn, params=(company_id,))
    return {
        "company_id": company_id,
        "peer_group_name": pg_name,
        "is_benchmark": bool(is_bm),
        "rankings": ranks.to_dict(orient="records"),
    }


def generate_radar_charts(
    scored_df: pd.DataFrame,
    output_dir: str = "reports/radar_charts",
) -> List[str]:
    """Generate 8-axis radar charts for all 92 companies into output_dir.

    - Peer-grouped companies: filled polygon for company + dashed outline for peer group average.
    - Unassigned companies: filled polygon for company + dashed outline for Nifty 100 universe average.

    Returns:
        List of generated image filepaths.
    """
    os.makedirs(output_dir, exist_ok=True)
    generated_files: List[str] = []

    # Prepare normalized values (0 to 100) for all 8 radar axes
    df_plot = scored_df.copy()

    # Pre-scale each radar metric to 0-100 across universe for consistent axis radii
    scaled_cols: Dict[str, str] = {}
    for col_key, label, invert in RADAR_AXES:
        norm_col = f"norm_{col_key}"
        clean_s = df_plot[col_key].dropna()
        q10 = clean_s.quantile(0.10)
        q90 = clean_s.quantile(0.90)
        if q90 > q10:
            clipped = df_plot[col_key].clip(lower=q10, upper=q90)
            scaled = (clipped - q10) / (q90 - q10) * 100.0
            if invert:
                scaled = 100.0 - scaled
            df_plot[norm_col] = scaled.fillna(50.0)
        else:
            df_plot[norm_col] = 50.0
        scaled_cols[col_key] = norm_col

    # Precompute universe average vector
    univ_avg_vector = [df_plot[scaled_cols[k]].mean() for k, _, _ in RADAR_AXES]

    # Precompute peer group average vectors
    peer_avg_vectors: Dict[str, List[float]] = {}
    for pg, grp in df_plot.groupby("peer_group_name"):
        if pd.notna(pg):
            peer_avg_vectors[str(pg)] = [grp[scaled_cols[k]].mean() for k, _, _ in RADAR_AXES]

    categories = [label for _, label, _ in RADAR_AXES]
    num_vars = len(categories)
    angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
    # Complete loop
    angles += angles[:1]

    for _, row in df_plot.iterrows():
        cid = str(row["company_id"])
        cname = str(row.get("company_name", cid)).split("\n")[0]
        pg_name = row.get("peer_group_name")
        has_pg = pd.notna(pg_name) and str(pg_name).strip() != ""

        comp_vals = [float(row[scaled_cols[k]]) for k, _, _ in RADAR_AXES]
        comp_vals += comp_vals[:1]

        if has_pg:
            ref_vals = peer_avg_vectors.get(str(pg_name), univ_avg_vector).copy()
            ref_label = f"{pg_name} Peer Avg"
            subtitle = f"Peer Group: {pg_name}"
        else:
            ref_vals = univ_avg_vector.copy()
            ref_label = "Nifty 100 Universe Avg"
            subtitle = "Standalone (No Peer Group Assigned)"
        ref_vals += ref_vals[:1]

        # Plot
        fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))
        fig.patch.set_facecolor("#FFFFFF")
        ax.set_facecolor("#F9FBFD")

        # Company polygon
        ax.plot(angles, comp_vals, color="#1F497D", linewidth=2.5, label=cid)
        ax.fill(angles, comp_vals, color="#1F497D", alpha=0.3)

        # Benchmark / Overlay
        ax.plot(angles, ref_vals, color="#E31837", linewidth=2.0, linestyle="--", label=ref_label)

        # Axis ticks & styling
        ax.set_theta_offset(np.pi / 2)
        ax.set_theta_direction(-1)
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories, fontsize=10, fontweight="bold", color="#262626")
        ax.set_ylim(0, 105)
        ax.set_yticks([25, 50, 75, 100])
        ax.set_yticklabels(["25", "50", "75", "100"], fontsize=8, color="#7F7F7F")
        ax.grid(color="#D9D9D9", linestyle=":", linewidth=1)

        # Title & legend
        plt.title(f"{cname} ({cid})\n{subtitle}", size=12, fontweight="bold", color="#1F497D", pad=25)
        ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1.15), frameon=True, fontsize=9)

        filename = f"{cid}_radar.png"
        filepath = os.path.join(output_dir, filename)
        plt.tight_layout()
        plt.savefig(filepath, dpi=200, bbox_inches="tight")
        plt.close(fig)

        generated_files.append(filepath)

    return generated_files


def export_peer_comparison_excel(
    scored_df: pd.DataFrame,
    output_path: str = "output/peer_comparison.xlsx",
) -> str:
    """Generate output/peer_comparison.xlsx with 11 sheets, one per peer group.

    Columns: company_id, company_name, + 10 metric columns, + percentile rank for each metric.
    Percentile color-coding:
        - Green fill (>= 0.75)
        - Yellow fill (0.25 to 0.75)
        - Red fill (<= 0.25)
    Benchmark row highlighted in gold/amber.
    Summary row at bottom showing Peer Group Median.
    """
    wb: Any = openpyxl.Workbook()
    wb.remove(wb.active)

    # Styles
    font_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    fill_header = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")

    font_title = Font(name="Calibri", size=14, bold=True, color="1F497D")
    font_meta = Font(name="Calibri", size=10, italic=True, color="595959")

    fill_gold = PatternFill(start_color="FFE699", end_color="FFE699", fill_type="solid")  # Gold Benchmark
    fill_median = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
    font_median = Font(name="Calibri", size=10, bold=True, color="000000")

    fill_green = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    font_green = Font(name="Calibri", size=10, color="006100")

    fill_yellow = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
    font_yellow = Font(name="Calibri", size=10, color="9C6500")

    fill_red = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
    font_red = Font(name="Calibri", size=10, color="9C0006")

    font_regular = Font(name="Calibri", size=10)
    border_thin = Border(
        left=Side(style="thin", color="D9D9D9"),
        right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"),
        bottom=Side(style="thin", color="D9D9D9"),
    )

    # Define peer groups to export (strictly all 11 groups)
    peer_groups = sorted([str(g) for g in scored_df["peer_group_name"].dropna().unique()])

    for pg in peer_groups:
        ws: Any = wb.create_sheet(title=pg[:31])  # Excel 31 char max
        grp_df = scored_df[scored_df["peer_group_name"] == pg].sort_values("company_id")

        # Row 1: Title
        ws.cell(row=1, column=1, value=f"{pg} — Peer Comparison Analysis").font = font_title
        # Row 2: Subtitle
        ws.cell(
            row=2,
            column=1,
            value=f"Coverage: {len(grp_df)} Companies | Gold highlight = Benchmark Company",
        ).font = font_meta

        # Headers: Company Info + (Value & Rank for 10 metrics) + Composite Score
        headers = ["Company ID", "Company Name", "Benchmark?"]
        for col_key, header_title, _ in PEER_METRICS:
            headers.append(header_title)
            headers.append(f"{header_title} Rank")
        headers.append("Composite Score")

        start_row = 4
        for c_idx, h_text in enumerate(headers, start=1):
            cell = ws.cell(row=start_row, column=c_idx, value=h_text)
            cell.font = font_header
            cell.fill = fill_header
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        # Data Rows
        current_row = start_row + 1
        for _, row in grp_df.iterrows():
            is_bm = bool(row.get("is_benchmark", 0))
            cid = row["company_id"]
            cname = str(row.get("company_name", cid)).split("\n")[0]

            col_pos = 1
            # 1. ID
            cell_id = ws.cell(row=current_row, column=col_pos, value=cid)
            col_pos += 1
            # 2. Name
            cell_name = ws.cell(row=current_row, column=col_pos, value=cname)
            col_pos += 1
            # 3. Benchmark
            bm_str = "Yes (Benchmark)" if is_bm else "No"
            cell_bm = ws.cell(row=current_row, column=col_pos, value=bm_str)
            col_pos += 1

            for c in [cell_id, cell_name, cell_bm]:
                c.font = font_regular
                c.border = border_thin
                if is_bm:
                    c.fill = fill_gold

            # 10 Metric value + rank pairs
            for col_key, _, _ in PEER_METRICS:
                val = row.get(col_key)
                rank_val = row.get(f"{col_key}_rank")

                # Metric Value Cell
                cell_v = ws.cell(row=current_row, column=col_pos)
                if pd.isna(val) or val is None:
                    cell_v.value = "-"
                    cell_v.alignment = Alignment(horizontal="center")
                elif isinstance(val, (int, np.integer)):
                    cell_v.value = int(val)
                    cell_v.alignment = Alignment(horizontal="right")
                elif isinstance(val, (float, np.floating)):
                    cell_v.value = round(float(val), 2)
                    cell_v.alignment = Alignment(horizontal="right")
                else:
                    cell_v.value = str(val)
                    cell_v.alignment = Alignment(horizontal="left")

                cell_v.font = font_regular
                cell_v.border = border_thin
                if is_bm:
                    cell_v.fill = fill_gold
                col_pos += 1

                # Percentile Rank Cell
                cell_r = ws.cell(row=current_row, column=col_pos)
                if pd.isna(rank_val) or rank_val is None:
                    cell_r.value = "-"
                    cell_r.alignment = Alignment(horizontal="center")
                    cell_r.font = font_regular
                    if is_bm:
                        cell_r.fill = fill_gold
                else:
                    r_pct = float(rank_val)
                    cell_r.value = f"{round(r_pct * 100, 1)}%"
                    cell_r.alignment = Alignment(horizontal="center")

                    # Colour-code percentile rank
                    if r_pct >= 0.75:
                        cell_r.fill = fill_green
                        cell_r.font = font_green
                    elif r_pct <= 0.25:
                        cell_r.fill = fill_red
                        cell_r.font = font_red
                    else:
                        cell_r.fill = fill_yellow
                        cell_r.font = font_yellow

                cell_r.border = border_thin
                col_pos += 1

            # Composite Score
            c_score = row.get("composite_quality_score")
            cell_s = ws.cell(row=current_row, column=col_pos)
            cell_s.value = round(float(c_score), 2) if pd.notna(c_score) else "-"
            cell_s.font = font_regular
            cell_s.alignment = Alignment(horizontal="right")
            cell_s.border = border_thin
            if is_bm:
                cell_s.fill = fill_gold

            current_row += 1

        # Summary Row: Peer Group Median
        median_row = current_row
        cell_m_lbl = ws.cell(row=median_row, column=1, value="PEER MEDIAN")
        cell_m_lbl.font = font_median
        cell_m_lbl.fill = fill_median
        cell_m_lbl.border = border_thin

        ws.cell(row=median_row, column=2, value="Group Summary").font = font_median
        ws.cell(row=median_row, column=2).fill = fill_median
        ws.cell(row=median_row, column=2).border = border_thin

        ws.cell(row=median_row, column=3, value="-").font = font_median
        ws.cell(row=median_row, column=3).fill = fill_median
        ws.cell(row=median_row, column=3).border = border_thin
        ws.cell(row=median_row, column=3).alignment = Alignment(horizontal="center")

        col_pos = 4
        for col_key, _, _ in PEER_METRICS:
            med_val = grp_df[col_key].median()
            cell_mv = ws.cell(row=median_row, column=col_pos)
            cell_mv.value = round(float(med_val), 2) if pd.notna(med_val) else "-"
            cell_mv.font = font_median
            cell_mv.fill = fill_median
            cell_mv.border = border_thin
            cell_mv.alignment = Alignment(horizontal="right")
            col_pos += 1

            # Rank median is 50%
            cell_mr = ws.cell(row=median_row, column=col_pos, value="50.0%")
            cell_mr.font = font_median
            cell_mr.fill = fill_median
            cell_mr.border = border_thin
            cell_mr.alignment = Alignment(horizontal="center")
            col_pos += 1

        # Composite score median
        med_score = grp_df["composite_quality_score"].median()
        cell_ms = ws.cell(row=median_row, column=col_pos)
        cell_ms.value = round(float(med_score), 2) if pd.notna(med_score) else "-"
        cell_ms.font = font_median
        cell_ms.fill = fill_median
        cell_ms.border = border_thin
        cell_ms.alignment = Alignment(horizontal="right")

        # Column widths & freeze pane
        ws.row_dimensions[start_row].height = 28
        for col in ws.columns:
            col_letter = get_column_letter(col[0].column)
            max_len = 0
            for cell in col:
                val_str = str(cell.value or "")
                if cell.row > start_row - 1:
                    max_len = max(max_len, len(val_str))
            ws.column_dimensions[col_letter].width = max(max_len + 3, 11)

        ws.freeze_panes = ws.cell(row=start_row + 1, column=4)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    wb.save(output_path)
    return os.path.abspath(output_path)


if __name__ == "__main__":
    db_path = "nifty100.db"
    if not os.path.exists(db_path):
        db_path = os.path.join("..", "..", "nifty100.db")

    conn = sqlite3.connect(db_path)
    print("Computing peer percentiles and populating SQLite table...")
    scored_df, long_df = compute_peer_percentiles(conn)
    print(f"Computed {len(long_df)} peer percentile records across 11 groups.")

    print("Generating radar charts for all 92 companies...")
    radar_files = generate_radar_charts(scored_df, "reports/radar_charts")
    print(f"Generated {len(radar_files)} radar charts in reports/radar_charts/.")

    print("Exporting peer comparison Excel report...")
    excel_path = export_peer_comparison_excel(scored_df, "output/peer_comparison.xlsx")
    print(f"Exported peer comparison workbook to: {excel_path}")

    conn.close()
