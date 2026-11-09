"""Valuation Engine: Computes FCF yield, sector median P/E benchmarks, and overvaluation flags.

Produces:
- output/valuation_summary.xlsx (92 companies with valuation multiples, FCF yield, and flags)
- output/valuation_flags.csv (Companies flagged as Caution or Discount)
"""

import os
import sqlite3
import sys
from typing import Any, Dict, Optional, Tuple

# Ensure workspace root is in sys.path
_WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
import pandas as pd

DB_PATH = os.getenv("DB_PATH", "nifty100.db")


def compute_fcf_yield(fcf: Optional[float], mcap: Optional[float]) -> Optional[float]:
    """Compute Free Cash Flow yield as (FCF / Market Cap) * 100."""
    if fcf is None or pd.isna(fcf) or mcap is None or pd.isna(mcap) or mcap <= 0:
        return None
    return round((float(fcf) / float(mcap)) * 100.0, 2)


def compute_relative_pe(pe: Optional[float], sector_median: Optional[float]) -> Optional[float]:
    """Compute relative P/E vs sector median percentage: ((PE - median) / median) * 100."""
    if pe is None or pd.isna(pe) or sector_median is None or pd.isna(sector_median):
        return None
    if pe <= 0 or sector_median <= 0:
        return None
    return round(((float(pe) - float(sector_median)) / float(sector_median)) * 100.0, 2)


def assign_valuation_flag(pe: Optional[float], sector_median: Optional[float]) -> Optional[str]:
    """Assign valuation flag based on sector median multiple:
    - Caution: P/E > 1.5x sector median
    - Discount: P/E < 0.7x sector median
    - Fair: Otherwise
    """
    if pe is None or pd.isna(pe) or sector_median is None or pd.isna(sector_median):
        return None
    if pe <= 0 or sector_median <= 0:
        return None
    pe_val = float(pe)
    med_val = float(sector_median)
    if pe_val > med_val * 1.5:
        return "Caution"
    elif pe_val < med_val * 0.7:
        return "Discount"
    else:
        return "Fair"


def compute_valuation_metrics(
    conn: sqlite3.Connection,
    target_year: str = "2024",
    year: Optional[str] = None,
) -> pd.DataFrame:
    """Compute valuation metrics, FCF yield, and overvaluation flags for all 92 companies.

    Args:
        conn: SQLite database connection.
        target_year: Valuation year (defaults to '2024').
        year: Optional alias for target_year.

    Returns:
        pd.DataFrame containing all 92 companies with complete valuation metrics.
    """
    if year is not None:
        target_year = year
    # 1. Fetch market_cap for target year joined with companies and sectors
    query = """
        SELECT m.company_id, c.company_name, COALESCE(s.broad_sector, 'Other') as sector,
               m.market_cap_crore, m.pe_ratio, m.pb_ratio, m.ev_ebitda, m.dividend_yield_pct
        FROM market_cap m
        JOIN companies c ON m.company_id = c.id
        LEFT JOIN sectors s ON m.company_id = s.company_id
        WHERE m.year = ?
        ORDER BY m.company_id
    """
    df = pd.read_sql(query, conn, params=(target_year,))

    if df.empty:
        # Fallback to latest year
        query_fallback = """
            SELECT m.company_id, c.company_name, COALESCE(s.broad_sector, 'Other') as sector,
                   m.market_cap_crore, m.pe_ratio, m.pb_ratio, m.ev_ebitda, m.dividend_yield_pct
            FROM market_cap m
            JOIN companies c ON m.company_id = c.id
            LEFT JOIN sectors s ON m.company_id = s.company_id
            GROUP BY m.company_id
            HAVING m.id = MAX(m.id)
            ORDER BY m.company_id
        """
        df = pd.read_sql(query_fallback, conn)

    # 2. Compute 5-year historical median PE per company (2020-2024)
    pe_hist_query = """
        SELECT company_id, pe_ratio
        FROM market_cap
        WHERE pe_ratio IS NOT NULL AND pe_ratio > 0
    """
    df_pe_hist = pd.read_sql(pe_hist_query, conn)
    median_5yr_pe = df_pe_hist.groupby("company_id")["pe_ratio"].median().round(2).to_dict()
    df["5yr_median_PE"] = df["company_id"].map(median_5yr_pe)

    # 3. Fetch latest Free Cash Flow (FCF) from financial_ratios
    fcf_query = """
        SELECT company_id, free_cash_flow_cr
        FROM financial_ratios
        WHERE year != 'TTM'
        ORDER BY company_id, id ASC
    """
    df_fcf = pd.read_sql(fcf_query, conn)
    latest_fcf = df_fcf.groupby("company_id").last().reset_index()
    fcf_map = latest_fcf.set_index("company_id")["free_cash_flow_cr"].to_dict()
    df["free_cash_flow_cr"] = df["company_id"].map(fcf_map)

    # 4. Compute FCF Yield: (FCF / Market Cap) * 100
    df["FCF_yield_pct"] = df.apply(
        lambda r: compute_fcf_yield(r.get("free_cash_flow_cr"), r.get("market_cap_crore")),
        axis=1,
    )

    # 5. Compute Sector Median P/E for latest year
    sector_pos_pe = df[df["pe_ratio"] > 0]
    sector_median_pe = sector_pos_pe.groupby("sector")["pe_ratio"].median().round(2).to_dict()
    df["sector_median_PE"] = df["sector"].map(sector_median_pe)

    # 6. Compute PE vs Sector Median Percentage: ((P/E - sector_median) / sector_median) * 100
    df["PE_vs_sector_median_pct"] = df.apply(
        lambda r: compute_relative_pe(r.get("pe_ratio"), r.get("sector_median_PE")),
        axis=1,
    )

    # 7. Apply Overvaluation Flags
    df["flag"] = df.apply(
        lambda r: assign_valuation_flag(r.get("pe_ratio"), r.get("sector_median_PE")) or "Fair",
        axis=1,
    )

    # Standardize column naming for requested report columns
    df = df.rename(
        columns={
            "pe_ratio": "P/E",
            "pb_ratio": "P/B",
            "ev_ebitda": "EV/EBITDA",
        }
    )

    return df


def export_valuation_reports(
    df: pd.DataFrame,
    excel_path: str = "output/valuation_summary.xlsx",
    csv_path: str = "output/valuation_flags.csv",
) -> Tuple[str, str]:
    """Export valuation summary workbook and caution/discount flags CSV.

    Args:
        df: Valuation DataFrame with 92 rows.
        excel_path: Destination for valuation_summary.xlsx.
        csv_path: Destination for valuation_flags.csv.

    Returns:
        Tuple of (excel_path, csv_path).
    """
    os.makedirs(os.path.dirname(os.path.abspath(excel_path)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(csv_path)), exist_ok=True)

    # Columns for Excel export
    export_cols = [
        "company_id",
        "company_name",
        "sector",
        "P/E",
        "P/B",
        "EV/EBITDA",
        "FCF_yield_pct",
        "5yr_median_PE",
        "PE_vs_sector_median_pct",
        "flag",
    ]
    df_export = df[export_cols].copy()

    # 1. Export Excel using openpyxl with clean styling
    wb: Any = openpyxl.Workbook()
    ws: Any = wb.active
    ws.title = "Valuation Summary"

    # Styles
    font_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    fill_header = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")

    font_title = Font(name="Calibri", size=14, bold=True, color="1F497D")
    font_meta = Font(name="Calibri", size=10, italic=True, color="595959")

    fill_caution = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")  # Red
    font_caution = Font(name="Calibri", size=10, color="9C0006", bold=True)

    fill_discount = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")  # Green
    font_discount = Font(name="Calibri", size=10, color="006100", bold=True)

    fill_fair = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")  # Yellow
    font_fair = Font(name="Calibri", size=10, color="9C6500")

    font_regular = Font(name="Calibri", size=10)
    border_thin = Border(
        left=Side(style="thin", color="D9D9D9"),
        right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"),
        bottom=Side(style="thin", color="D9D9D9"),
    )

    start_row = 1
    for c_idx, col_name in enumerate(export_cols, start=1):
        cell = ws.cell(row=start_row, column=c_idx, value=col_name)
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = Alignment(horizontal="center", vertical="center")

    current_row = start_row + 1
    for _, row in df_export.iterrows():
        flag_val = str(row.get("flag", "Fair"))
        for c_idx, col_name in enumerate(export_cols, start=1):
            val = row.get(col_name)
            cell = ws.cell(row=current_row, column=c_idx)

            if pd.isna(val) or val is None:
                cell.value = "-"
                cell.alignment = Alignment(horizontal="center")
            elif isinstance(val, (int, float)):
                cell.value = round(float(val), 2)
                cell.alignment = Alignment(horizontal="right")
            else:
                cell.value = str(val)
                cell.alignment = Alignment(horizontal="left")

            cell.font = font_regular
            cell.border = border_thin

            # Flag color coding
            if col_name == "flag":
                cell.alignment = Alignment(horizontal="center")
                if flag_val == "Caution":
                    cell.fill = fill_caution
                    cell.font = font_caution
                elif flag_val == "Discount":
                    cell.fill = fill_discount
                    cell.font = font_discount
                else:
                    cell.fill = fill_fair
                    cell.font = font_fair

        current_row += 1

    # Auto-adjust column widths
    ws.row_dimensions[start_row].height = 25
    for col in ws.columns:
        col_letter = get_column_letter(col[0].column)
        max_len = max(len(str(cell.value or "")) for cell in col if cell.row >= start_row)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

    ws.freeze_panes = ws.cell(row=start_row + 1, column=3)
    wb.save(excel_path)

    # 2. Export valuation_flags.csv containing only Caution or Discount
    df_flags = df_export[df_export["flag"].isin(["Caution", "Discount"])].copy()
    df_flags.to_csv(csv_path, index=False, encoding="utf-8")

    return os.path.abspath(excel_path), os.path.abspath(csv_path)


def run_valuation_pipeline(
    conn: Optional[sqlite3.Connection] = None,
    target_year: str = "2024",
) -> Tuple[pd.DataFrame, str, str]:
    """Execute valuation calculation and generate output files."""
    close_conn = False
    if conn is None:
        conn = sqlite3.connect(DB_PATH)
        close_conn = True

    try:
        df = compute_valuation_metrics(conn, target_year=target_year)
        excel_path, csv_path = export_valuation_reports(df)
        return df, excel_path, csv_path
    finally:
        if close_conn:
            conn.close()


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    print("Running Valuation Engine...")
    df, x_path, c_path = run_valuation_pipeline(conn)
    print(f"Computed valuation for {len(df)} companies.")
    print(f"Exported Excel: {x_path}")
    print(f"Exported Flags CSV: {c_path}")
    conn.close()
