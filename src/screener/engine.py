"""Financial Screener Engine.

Implements threshold filtering for 15 metrics, 6 preset screeners,
P10/P90 winsorized sector-relative composite quality scoring,
and formatted Excel export to output/screener_output.xlsx.
"""

import os
import sqlite3
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

# Ensure workspace root is in sys.path for direct script execution
_WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

import numpy as np
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
import pandas as pd
import yaml

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "config", "screener_config.yaml")


def load_screener_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load and parse the screener YAML configuration.

    Args:
        config_path: Path to screener_config.yaml. Defaults to DEFAULT_CONFIG_PATH.

    Returns:
        Dict containing configuration sections.
    """
    path = config_path or DEFAULT_CONFIG_PATH
    if not os.path.isabs(path):
        path = os.path.abspath(path)

    if not os.path.exists(path):
        raise FileNotFoundError(f"Screener config not found at: {path}")

    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if isinstance(config, dict):
        return config
    return {}


def build_screener_dataset(conn: sqlite3.Connection, year: Optional[str] = None) -> pd.DataFrame:
    """Build the master dataset joining financial_ratios, companies, sectors, market_cap, and profitandloss.

    Selects the latest reporting period for each company (excluding 'TTM').

    Args:
        conn: SQLite database connection.
        year: Optional specific year to filter by.

    Returns:
        pd.DataFrame containing all 92 companies with merged KPI metrics.
    """
    # 1. Fetch non-TTM financial ratios
    year_clause = f"AND fr.year = '{year}'" if year else "AND fr.year != 'TTM'"
    query_fr = f"""
        SELECT fr.*, c.company_name, s.broad_sector, s.sub_sector
        FROM financial_ratios fr
        JOIN companies c ON fr.company_id = c.id
        LEFT JOIN sectors s ON c.id = s.company_id
        WHERE 1=1 {year_clause}
        ORDER BY fr.company_id, fr.id ASC
    """
    df_fr = pd.read_sql(query_fr, conn)

    if df_fr.empty:
        return pd.DataFrame()

    # Get latest row per company
    latest_fr = df_fr.groupby("company_id").last().reset_index()

    # Get prior row per company for YoY calculations (e.g. D/E decline)
    prior_fr = df_fr.groupby("company_id").nth(-2).reset_index()
    prior_de_map = prior_fr.set_index("company_id")["debt_to_equity"].to_dict()
    latest_fr["prior_de"] = latest_fr["company_id"].map(prior_de_map)

    # 2. Join latest market_cap (2024 or latest available)
    df_mc = pd.read_sql(
        """
        SELECT company_id, market_cap_crore, enterprise_value_crore, pe_ratio, pb_ratio, ev_ebitda, dividend_yield_pct
        FROM market_cap
        WHERE year = '2024'
        """,
        conn,
    )
    if df_mc.empty:
        # Fallback to latest available year in market_cap
        df_mc = pd.read_sql(
            """
            SELECT company_id, market_cap_crore, enterprise_value_crore, pe_ratio, pb_ratio, ev_ebitda, dividend_yield_pct
            FROM market_cap
            GROUP BY company_id
            HAVING id = MAX(id)
            """,
            conn,
        )

    # 3. Join latest profitandloss metrics (sales, net_profit, dividend_payout)
    df_pnl = pd.read_sql(
        """
        SELECT id, company_id, year, sales, net_profit, dividend_payout
        FROM profitandloss
        WHERE year != 'TTM'
        ORDER BY company_id, id ASC
        """,
        conn,
    )
    latest_pnl = df_pnl.groupby("company_id").last().reset_index()
    latest_pnl = latest_pnl.rename(columns={"year": "pnl_year"})

    # Compute 3-year revenue CAGR from profitandloss
    rev_3yr_map: Dict[str, float] = {}
    for cid, group in df_pnl.groupby("company_id"):
        group_sorted = group.sort_values("id")
        if len(group_sorted) >= 4:
            s_end = group_sorted.iloc[-1]["sales"]
            s_start = group_sorted.iloc[-4]["sales"]
            if s_start and s_end and s_start > 0 and s_end > 0:
                cagr_val = ((s_end / s_start) ** (1.0 / 3.0) - 1.0) * 100.0
                rev_3yr_map[str(cid)] = round(cagr_val, 2)
    latest_fr["revenue_cagr_3yr"] = latest_fr["company_id"].map(rev_3yr_map)

    # 4. Join latest CFO from cashflow
    df_cf = pd.read_sql(
        """
        SELECT id, company_id, operating_activity as cfo
        FROM cashflow
        WHERE year != 'TTM'
        ORDER BY company_id, id ASC
        """,
        conn,
    )
    latest_cf = df_cf.groupby("company_id").last().reset_index()

    # Merge all
    merged = latest_fr.merge(df_mc, on="company_id", how="left")
    merged = merged.merge(latest_pnl[["company_id", "sales", "net_profit", "dividend_payout"]], on="company_id", how="left")
    merged = merged.merge(latest_cf, on="company_id", how="left")

    return merged


def winsorize_and_scale(
    series: pd.Series, p_low: float = 0.10, p_high: float = 0.90, invert: bool = False
) -> pd.Series:
    """Winsorize extreme values at p_low and p_high percentiles, then min-max scale to 0-100.

    Args:
        series: Numeric pandas Series.
        p_low: Lower percentile (e.g. 0.10 for P10).
        p_high: Upper percentile (e.g. 0.90 for P90).
        invert: If True, inverts the score (lower is higher score).

    Returns:
        Scaled pandas Series with values in [0, 100].
    """
    clean = series.dropna()
    if len(clean) == 0:
        return pd.Series(50.0, index=series.index)

    q_low = clean.quantile(p_low)
    q_high = clean.quantile(p_high)

    if q_high == q_low:
        # No variance
        scaled = pd.Series(50.0, index=series.index)
        return scaled

    clipped = series.clip(lower=q_low, upper=q_high)
    scaled = (clipped - q_low) / (q_high - q_low) * 100.0

    if invert:
        scaled = 100.0 - scaled

    # Fill NaNs with median score (50.0)
    return scaled.fillna(50.0)


def compute_composite_quality_score(
    df: pd.DataFrame, config: Optional[Dict[str, Any]] = None
) -> pd.DataFrame:
    """Compute the 0-100 sector-relative composite quality score.

    Weights:
        - 35% Profitability: ROE (15%), ROCE (10%), NPM (10%)
        - 30% Cash Quality: FCF growth (15%), CFO/PAT (10%), FCF > 0 flag (5%)
        - 20% Growth: Revenue CAGR 5yr (10%), PAT CAGR 5yr (10%)
        - 15% Leverage: D/E inverted (10%), ICR (5%)

    Each metric is winsorized at P10/P90 within each broad_sector,
    falling back to full universe percentiles if sector has < 3 companies.

    Args:
        df: Master screener DataFrame.
        config: Configuration dictionary.

    Returns:
        DataFrame with 'composite_quality_score' column added.
    """
    df_out = df.copy()

    # Derived components
    # CFO / PAT ratio
    pat = df_out["net_profit"].replace(0, np.nan)
    df_out["cfo_pat_ratio"] = df_out["cfo"] / pat
    # Cap extreme negative or positive ratios to [-2, 5] before winsorization
    df_out["cfo_pat_ratio"] = df_out["cfo_pat_ratio"].clip(lower=-2.0, upper=5.0)

    # FCF growth proxy: ratio of FCF to total assets or sales
    sales_safe = df_out["sales"].replace(0, np.nan)
    df_out["fcf_margin"] = df_out["free_cash_flow_cr"] / sales_safe

    # FCF Positive Flag (100 if > 0, else 0)
    df_out["fcf_positive_score"] = np.where(df_out["free_cash_flow_cr"] > 0, 100.0, 0.0)

    # ICR score handling: If ICR label is "Debt Free" or interest == 0, ICR score = 100.0
    df_out["effective_icr"] = df_out["interest_coverage"].copy()
    debt_free_mask = (df_out["icr_label"] == "Debt Free") | (df_out["debt_to_equity"] <= 0.01)
    df_out.loc[debt_free_mask, "effective_icr"] = 100.0

    # Sector-relative winsorized scoring
    metric_configs = [
        ("return_on_equity_pct", False, 0.15),
        ("return_on_capital_employed_pct", False, 0.10),
        ("net_profit_margin_pct", False, 0.10),
        ("fcf_margin", False, 0.15),
        ("cfo_pat_ratio", False, 0.10),
        ("revenue_cagr_5yr", False, 0.10),
        ("pat_cagr_5yr", False, 0.10),
        ("debt_to_equity", True, 0.10),  # Inverted
        ("effective_icr", False, 0.05),
    ]

    total_score = pd.Series(0.0, index=df_out.index)
    total_score += df_out["fcf_positive_score"] * 0.05  # 5% fixed weight

    # Group by broad sector
    sectors = df_out["broad_sector"].unique()
    for col, invert, weight in metric_configs:
        col_score = pd.Series(index=df_out.index, dtype=float)
        # Compute within sector
        for sec in sectors:
            sec_idx = df_out[df_out["broad_sector"] == sec].index
            sec_vals = pd.Series(df_out.loc[sec_idx, col])
            if len(sec_vals.dropna()) >= 3:
                col_score.loc[sec_idx] = winsorize_and_scale(sec_vals, 0.10, 0.90, invert=invert)
            else:
                # Fallback to universe level
                universe_scaled = winsorize_and_scale(pd.Series(df_out[col]), 0.10, 0.90, invert=invert)
                col_score.loc[sec_idx] = universe_scaled.loc[sec_idx]

        # For Financials sector on D/E: neutralize debt penalty by setting to sector median (75.0)
        if col == "debt_to_equity":
            fin_idx = df_out[df_out["broad_sector"] == "Financials"].index
            col_score.loc[fin_idx] = 75.0

        total_score += col_score.fillna(50.0) * weight

    df_out["composite_quality_score"] = total_score.clip(0.0, 100.0).round(2)
    return df_out


def passes_single_filter(
    val: Any,
    rule: Dict[str, Any],
    is_financial: bool = False,
    is_debt_free: bool = False,
    metric_name: str = "",
) -> bool:
    """Check whether a single value satisfies a min/max rule.

    Handles special rules:
        - Financials broad sector exempt from D/E max filter.
        - Debt Free label exempt from ICR min filter.
    """
    if metric_name == "debt_to_equity" and is_financial:
        return True

    if metric_name in ("interest_coverage", "icr") and is_debt_free:
        return True

    if pd.isna(val) or val is None:
        return False

    val_num = float(val)

    if "min" in rule and val_num < rule["min"]:
        return False

    if "max" in rule and val_num > rule["max"]:
        return False

    return True


def apply_threshold_filters(
    df: pd.DataFrame,
    filters: Dict[str, Any],
    is_turnaround: bool = False,
) -> pd.DataFrame:
    """Apply arbitrary threshold filters to the master dataset.

    Args:
        df: Master screener DataFrame.
        filters: Dictionary mapping column names to {'min': val, 'max': val}.
        is_turnaround: Special flag for Turnaround Watch (declining D/E).

    Returns:
        Filtered DataFrame meeting all criteria.
    """
    if df.empty:
        return df

    mask = pd.Series(True, index=df.index)

    for metric, rule in filters.items():
        if metric == "de_declining":
            continue

        if metric not in df.columns:
            continue

        col_mask = []
        for _, row in df.iterrows():
            is_fin = row.get("broad_sector") == "Financials"
            is_df = (row.get("icr_label") == "Debt Free") or (row.get("debt_to_equity", 1) <= 0.01)
            val = row.get(metric)
            passed = passes_single_filter(val, rule, is_financial=is_fin, is_debt_free=is_df, metric_name=metric)
            col_mask.append(passed)

        mask = mask & pd.Series(col_mask, index=df.index)

    if is_turnaround:
        # D/E declining YoY: latest D/E <= prior D/E (or debt free or Financials)
        de_cond = []
        for _, row in df.iterrows():
            is_fin = row.get("broad_sector") == "Financials"
            cur_de = row.get("debt_to_equity")
            prior_de = row.get("prior_de")
            if is_fin:
                de_cond.append(True)
            elif pd.isna(cur_de) or pd.isna(prior_de):
                de_cond.append(False)
            elif cur_de <= 0.05:  # Already debt-free
                de_cond.append(True)
            else:
                de_cond.append(cur_de <= prior_de)

        mask = mask & pd.Series(de_cond, index=df.index)

    return df[mask].copy()


def run_preset(
    master_df: pd.DataFrame, preset_key: str, config: Optional[Dict[str, Any]] = None
) -> pd.DataFrame:
    """Execute one of the 6 preset screeners and return results sorted by composite score.

    Presets:
        1. quality_compounder
        2. value_pick
        3. growth_accelerator
        4. dividend_champion
        5. debt_free_blue_chip
        6. turnaround_watch
    """
    cfg = config or load_screener_config()
    presets_cfg = cfg.get("presets", {})

    if preset_key not in presets_cfg:
        raise ValueError(f"Unknown preset: {preset_key}. Available: {list(presets_cfg.keys())}")

    preset_info = presets_cfg[preset_key]
    filters = preset_info.get("filters", {})
    is_turnaround = preset_key == "turnaround_watch" or filters.get("de_declining", False)

    # Filter
    filtered = apply_threshold_filters(master_df, filters, is_turnaround=is_turnaround)

    # Sort descending by composite_quality_score
    if "composite_quality_score" in filtered.columns:
        filtered = filtered.sort_values("composite_quality_score", ascending=False)

    return filtered


def run_all_presets(
    conn: sqlite3.Connection, config_path: Optional[str] = None
) -> Dict[str, pd.DataFrame]:
    """Build master dataset, compute composite scores, and execute all 6 presets.

    Returns:
        Dict mapping preset_key to result DataFrame.
    """
    cfg = load_screener_config(config_path)
    master = build_screener_dataset(conn)
    scored = compute_composite_quality_score(master, cfg)

    results: Dict[str, pd.DataFrame] = {}
    preset_keys = [
        "quality_compounder",
        "value_pick",
        "growth_accelerator",
        "dividend_champion",
        "debt_free_blue_chip",
        "turnaround_watch",
    ]

    for pkey in preset_keys:
        results[pkey] = run_preset(scored, pkey, cfg)

    return results


# 20 Standard KPI Columns for Excel Export
EXPORT_KPI_COLUMNS = [
    ("company_id", "Company ID"),
    ("company_name", "Company Name"),
    ("broad_sector", "Sector"),
    ("composite_quality_score", "Composite Score"),
    ("return_on_equity_pct", "ROE (%)"),
    ("return_on_capital_employed_pct", "ROCE (%)"),
    ("net_profit_margin_pct", "NPM (%)"),
    ("operating_profit_margin_pct", "OPM (%)"),
    ("debt_to_equity", "D/E"),
    ("interest_coverage", "ICR"),
    ("free_cash_flow_cr", "FCF (Cr)"),
    ("capex_cr", "CapEx (Cr)"),
    ("sales", "Sales (Cr)"),
    ("net_profit", "PAT (Cr)"),
    ("revenue_cagr_5yr", "Rev CAGR 5Y (%)"),
    ("pat_cagr_5yr", "PAT CAGR 5Y (%)"),
    ("eps_cagr_5yr", "EPS CAGR 5Y (%)"),
    ("pe_ratio", "P/E"),
    ("pb_ratio", "P/B"),
    ("dividend_yield_pct", "Div Yield (%)"),
    ("dividend_payout", "Div Payout (%)"),
]


def export_screener_excel(
    results_dict: Dict[str, pd.DataFrame],
    output_path: str = "output/screener_output.xlsx",
    config: Optional[Dict[str, Any]] = None,
) -> str:
    """Generate output/screener_output.xlsx with 6 sheets, one per preset.

    Each sheet contains 20 KPI columns, sorted by composite_quality_score.
    Cells are colour-coded:
        - Green fill (#C6EFCE, dark green text #006100) for meeting preset threshold
        - Red fill (#FFC7CE, dark red text #9C0006) for failing preset threshold

    Args:
        results_dict: Dictionary of preset_key -> DataFrame.
        output_path: Destination path for the Excel file.
        config: Optional configuration dictionary.

    Returns:
        Absolute path to the created Excel workbook.
    """
    cfg = config or load_screener_config()
    presets_cfg = cfg.get("presets", {})

    wb: Any = openpyxl.Workbook()
    # Remove default sheet
    wb.remove(wb.active)

    # Styles
    font_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    fill_header = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")  # Navy

    font_title = Font(name="Calibri", size=14, bold=True, color="1F497D")
    font_meta = Font(name="Calibri", size=10, italic=True, color="595959")

    fill_green = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    font_green = Font(name="Calibri", size=10, color="006100")

    fill_red = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
    font_red = Font(name="Calibri", size=10, color="9C0006")

    font_regular = Font(name="Calibri", size=10)
    border_thin = Border(
        left=Side(style="thin", color="D9D9D9"),
        right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"),
        bottom=Side(style="thin", color="D9D9D9"),
    )

    preset_display_names = {
        "quality_compounder": "Quality Compounder",
        "value_pick": "Value Pick",
        "growth_accelerator": "Growth Accelerator",
        "dividend_champion": "Dividend Champion",
        "debt_free_blue_chip": "Debt-Free Blue Chip",
        "turnaround_watch": "Turnaround Watch",
    }

    for pkey, sheet_title in preset_display_names.items():
        ws: Any = wb.create_sheet(title=sheet_title)
        df_preset = results_dict.get(pkey, pd.DataFrame())
        preset_info = presets_cfg.get(pkey, {})
        filters = preset_info.get("filters", {})
        desc = preset_info.get("description", "")

        # Row 1: Title
        ws.cell(row=1, column=1, value=f"{sheet_title} Screener").font = font_title
        # Row 2: Description & Count
        count_str = f"Found {len(df_preset)} matching companies out of 92"
        ws.cell(row=2, column=1, value=f"{desc} — ({count_str})").font = font_meta

        # Row 4: Table Headers
        start_row = 4
        for col_idx, (col_key, col_header) in enumerate(EXPORT_KPI_COLUMNS, start=1):
            cell = ws.cell(row=start_row, column=col_idx, value=col_header)
            cell.font = font_header
            cell.fill = fill_header
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        # Populate Data Rows
        current_row = start_row + 1
        for _, row in df_preset.iterrows():
            is_fin = row.get("broad_sector") == "Financials"
            is_df = (row.get("icr_label") == "Debt Free") or (row.get("debt_to_equity", 1) <= 0.01)

            for col_idx, (col_key, _) in enumerate(EXPORT_KPI_COLUMNS, start=1):
                val = row.get(col_key)
                cell = ws.cell(row=current_row, column=col_idx)

                # Format value
                if pd.isna(val) or val is None:
                    cell.value = "-"
                    cell.alignment = Alignment(horizontal="center")
                elif isinstance(val, (int, np.integer)):
                    cell.value = int(val)
                    cell.alignment = Alignment(horizontal="right")
                elif isinstance(val, (float, np.floating)):
                    cell.value = round(float(val), 2)
                    cell.alignment = Alignment(horizontal="right")
                else:
                    cell.value = str(val)
                    cell.alignment = Alignment(horizontal="left")

                cell.font = font_regular
                cell.border = border_thin

                # Colour-code if metric is part of preset threshold filters
                if col_key in filters:
                    rule = filters[col_key]
                    if isinstance(rule, dict):
                        passed = passes_single_filter(
                            val, rule, is_financial=is_fin, is_debt_free=is_df, metric_name=col_key
                        )
                        if passed:
                            cell.fill = fill_green
                            cell.font = font_green
                        else:
                            cell.fill = fill_red
                            cell.font = font_red

            current_row += 1

        # Adjust column widths
        ws.row_dimensions[start_row].height = 28
        for col in ws.columns:
            col_letter = get_column_letter(col[0].column)
            max_len = 0
            for cell in col:
                val_str = str(cell.value or "")
                if cell.row > start_row - 1:
                    max_len = max(max_len, len(val_str))
            ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

        # Freeze panes below header
        ws.freeze_panes = ws.cell(row=start_row + 1, column=3)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    wb.save(output_path)
    return os.path.abspath(output_path)


if __name__ == "__main__":
    db_path = "nifty100.db"
    if not os.path.exists(db_path):
        db_path = os.path.join("..", "..", "nifty100.db")

    conn = sqlite3.connect(db_path)
    print("Running screener pipeline...")
    results = run_all_presets(conn)
    for k, v in results.items():
        print(f"Preset [{k}]: {len(v)} companies returned.")

    excel_out = export_screener_excel(results, "output/screener_output.xlsx")
    print(f"Exported screener results to: {excel_out}")
    conn.close()
