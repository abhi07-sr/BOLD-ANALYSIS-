"""Database utilities and cached query functions for the Streamlit dashboard."""

import os
import sqlite3
import sys
from typing import Any, Dict, List, Optional

# Ensure workspace root is in sys.path
_WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

import pandas as pd
import streamlit as st

from src.screener.engine import build_screener_dataset, compute_composite_quality_score

DB_PATH = os.getenv("DB_PATH", "nifty100.db")


def clean_company_name(name: Optional[str]) -> str:
    """Clean company name by stripping multiline descriptions or extra whitespace."""
    if not name or pd.isna(name):
        return "Unknown"
    return str(name).split("\n")[0].strip()


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Create a thread-safe connection to the SQLite database."""
    if not os.path.isabs(db_path):
        db_path = os.path.join(_WORKSPACE_ROOT, db_path)
    return sqlite3.connect(db_path, check_same_thread=False)


@st.cache_data(ttl=600)
def get_companies() -> pd.DataFrame:
    """Retrieve all 92 companies with sector metadata, profiles, and face/book value."""
    conn = get_connection()
    query = """
        SELECT c.*, s.broad_sector, s.sub_sector, s.index_weight_pct, s.market_cap_category
        FROM companies c
        LEFT JOIN sectors s ON c.id = s.company_id
        ORDER BY c.id ASC
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_ratios(ticker: Optional[str] = None, year: Optional[str] = None) -> pd.DataFrame:
    """Retrieve financial ratios history for a specific company or all companies.

    Excludes TTM rows by default unless specifically requested.
    """
    conn = get_connection()
    clauses = ["fr.year != 'TTM'"]
    params = []

    if ticker:
        clauses.append("fr.company_id = ?")
        params.append(ticker)
    if year:
        clauses.append("fr.year = ?")
        params.append(year)

    where_sql = " AND ".join(clauses)
    query = f"""
        SELECT fr.*, c.company_name, s.broad_sector
        FROM financial_ratios fr
        JOIN companies c ON fr.company_id = c.id
        LEFT JOIN sectors s ON c.id = s.company_id
        WHERE {where_sql}
        ORDER BY fr.company_id, fr.id ASC
    """
    df = pd.read_sql(query, conn, params=params)
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_pl(ticker: str) -> pd.DataFrame:
    """Retrieve 10-year Profit & Loss statement history for a company."""
    conn = get_connection()
    query = """
        SELECT *
        FROM profitandloss
        WHERE company_id = ? AND year != 'TTM'
        ORDER BY id ASC
    """
    df = pd.read_sql(query, conn, params=(ticker,))
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_bs(ticker: str) -> pd.DataFrame:
    """Retrieve Balance Sheet statement history for a company."""
    conn = get_connection()
    query = """
        SELECT *
        FROM balancesheet
        WHERE company_id = ? AND year != 'TTM'
        ORDER BY id ASC
    """
    df = pd.read_sql(query, conn, params=(ticker,))
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_cf(ticker: str) -> pd.DataFrame:
    """Retrieve Cash Flow statement history for a company."""
    conn = get_connection()
    query = """
        SELECT *
        FROM cashflow
        WHERE company_id = ? AND year != 'TTM'
        ORDER BY id ASC
    """
    df = pd.read_sql(query, conn, params=(ticker,))
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_sectors() -> pd.DataFrame:
    """Retrieve all sectors with company count and cumulative index weight."""
    conn = get_connection()
    query = """
        SELECT 
            COALESCE(broad_sector, 'Unclassified') as broad_sector,
            COUNT(company_id) as company_count,
            ROUND(SUM(COALESCE(index_weight_pct, 0)), 2) as total_weight
        FROM sectors
        GROUP BY broad_sector
        ORDER BY company_count DESC, total_weight DESC
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_peers(group_name: Optional[str] = None) -> pd.DataFrame:
    """Retrieve peer group members and rankings for an industry group."""
    conn = get_connection()
    if group_name:
        query = """
            SELECT pg.peer_group_name, pg.company_id, pg.is_benchmark, c.company_name,
                   fr.return_on_equity_pct, fr.return_on_capital_employed_pct,
                   fr.net_profit_margin_pct, fr.debt_to_equity, fr.free_cash_flow_cr,
                   fr.revenue_cagr_5yr, fr.pat_cagr_5yr, fr.eps_cagr_5yr,
                   fr.interest_coverage, fr.asset_turnover
            FROM peer_groups pg
            JOIN companies c ON pg.company_id = c.id
            LEFT JOIN (
                SELECT * FROM financial_ratios 
                WHERE year != 'TTM'
                GROUP BY company_id
                HAVING id = MAX(id)
            ) fr ON pg.company_id = fr.company_id
            WHERE pg.peer_group_name = ?
            ORDER BY pg.is_benchmark DESC, fr.return_on_equity_pct DESC
        """
        df = pd.read_sql(query, conn, params=(group_name,))
    else:
        query = "SELECT DISTINCT peer_group_name FROM peer_groups ORDER BY peer_group_name ASC"
        df = pd.read_sql(query, conn)
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_valuation(ticker: Optional[str] = None) -> pd.DataFrame:
    """Retrieve valuation metrics, multiples, and overvaluation flags."""
    excel_path = os.path.join(_WORKSPACE_ROOT, "output", "valuation_summary.xlsx")
    if os.path.exists(excel_path):
        df = pd.read_excel(excel_path)
    else:
        # Fallback to computing on the fly
        conn = get_connection()
        from src.analytics.valuation import compute_valuation_metrics
        df = compute_valuation_metrics(conn, "2024")
        conn.close()

    if ticker:
        df = df[df["company_id"] == ticker].copy()
    return df


@st.cache_data(ttl=600)
def get_prosandcons(ticker: str) -> Dict[str, List[str]]:
    """Retrieve pros and cons for a specific company."""
    conn = get_connection()
    query = "SELECT pros, cons FROM prosandcons WHERE company_id = ?"
    rows = conn.execute(query, (ticker,)).fetchall()
    conn.close()

    pros_list: List[str] = []
    cons_list: List[str] = []

    for r in rows:
        p, c = r[0], r[1]
        if p and p.strip():
            # May be newline or comma separated
            pros_list.extend([line.strip() for line in p.split("\n") if line.strip()])
        if c and c.strip():
            cons_list.extend([line.strip() for line in c.split("\n") if line.strip()])

    return {"pros": pros_list, "cons": cons_list}


@st.cache_data(ttl=600)
def get_annual_reports(ticker: str) -> pd.DataFrame:
    """Retrieve list of available annual reports and links for a company."""
    conn = get_connection()
    query = """
        SELECT year, annual_report as url
        FROM documents
        WHERE company_id = ?
        ORDER BY year DESC
    """
    df = pd.read_sql(query, conn, params=(ticker,))
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_capital_allocation(ticker: Optional[str] = None) -> pd.DataFrame:
    """Retrieve capital allocation patterns from CSV or database."""
    csv_path = os.path.join(_WORKSPACE_ROOT, "output", "capital_allocation.csv")
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
        # Join company name and sector
        df_comp = get_companies()[["id", "company_name", "broad_sector"]]
        df = df.merge(df_comp, left_on="company_id", right_on="id", how="left")
    else:
        df = pd.DataFrame()

    if ticker and not df.empty:
        df = df[df["company_id"] == ticker].copy()
    return df


@st.cache_data(ttl=600)
def get_all_screener_data() -> pd.DataFrame:
    """Retrieve full master screener dataset with composite quality scores."""
    conn = get_connection()
    master = build_screener_dataset(conn)
    scored = compute_composite_quality_score(master)
    conn.close()
    return scored


@st.cache_data(ttl=600)
def get_home_kpis(year: str = "2024") -> Dict[str, Any]:
    """Compute 6 summary KPI metrics for the Home Screen.

    KPIs:
        1. Average ROE
        2. Median P/E
        3. Median D/E
        4. Total Companies (92)
        5. Median Revenue CAGR 5yr
        6. Debt-Free Companies Count (D/E <= 0.05)
    """
    conn = get_connection()

    # Ratios for latest year (or year specified)
    query_fr = """
        SELECT fr.company_id, fr.return_on_equity_pct, fr.debt_to_equity,
               fr.revenue_cagr_5yr, s.broad_sector
        FROM financial_ratios fr
        LEFT JOIN sectors s ON fr.company_id = s.company_id
        WHERE fr.year != 'TTM'
        ORDER BY fr.company_id, fr.id ASC
    """
    df_fr = pd.read_sql(query_fr, conn)
    latest_fr = df_fr.groupby("company_id").last().reset_index()

    # Market cap P/E for the year
    query_mc = f"SELECT company_id, pe_ratio FROM market_cap WHERE year = '{year}'"
    df_mc = pd.read_sql(query_mc, conn)
    if df_mc.empty:
        query_mc = "SELECT company_id, pe_ratio FROM market_cap GROUP BY company_id HAVING id = MAX(id)"
        df_mc = pd.read_sql(query_mc, conn)

    merged = latest_fr.merge(df_mc, on="company_id", how="left")
    conn.close()

    # 1. Average ROE
    valid_roe = merged["return_on_equity_pct"].dropna()
    # Filter out extreme outliers (e.g. >500% from exceptional items) for cleaner display
    avg_roe = valid_roe[valid_roe < 200].mean() if not valid_roe.empty else 0.0

    # 2. Median P/E
    pos_pe = merged["pe_ratio"].dropna()
    pos_pe = pos_pe[pos_pe > 0]
    med_pe = pos_pe.median() if not pos_pe.empty else 0.0

    # 3. Median D/E (excluding Financials)
    non_fin_de = merged[merged["broad_sector"] != "Financials"]["debt_to_equity"].dropna()
    med_de = non_fin_de.median() if not non_fin_de.empty else 0.0

    # 4. Total Companies
    total_companies = len(merged)

    # 5. Median Revenue CAGR 5yr
    valid_cagr = merged["revenue_cagr_5yr"].dropna()
    med_rev_cagr = valid_cagr.median() if not valid_cagr.empty else 0.0

    # 6. Debt-Free Companies Count (D/E <= 0.05, excluding Financials)
    debt_free_count = (non_fin_de <= 0.05).sum()

    return {
        "avg_roe": round(float(avg_roe), 1),
        "median_pe": round(float(med_pe), 1),
        "median_de": round(float(med_de), 2),
        "total_companies": int(total_companies),
        "median_rev_cagr_5yr": round(float(med_rev_cagr), 1),
        "debt_free_count": int(debt_free_count),
    }


@st.cache_data(ttl=600)
def get_stock_price_summary(ticker: str) -> Dict[str, Any]:
    """Retrieve current close price, 52W high, 52W low, and market cap for a company."""
    conn = get_connection()
    query_prices = """
        SELECT close_price, high_price, low_price, date
        FROM stock_prices
        WHERE company_id = ?
        ORDER BY date DESC
        LIMIT 12
    """
    rows = conn.execute(query_prices, (ticker,)).fetchall()

    current_price = rows[0][0] if rows else None
    high_52w = max(r[1] for r in rows) if rows else None
    low_52w = min(r[2] for r in rows) if rows else None

    query_mc = """
        SELECT market_cap_crore, pe_ratio, pb_ratio
        FROM market_cap
        WHERE company_id = ?
        ORDER BY year DESC
        LIMIT 1
    """
    mc_row = conn.execute(query_mc, (ticker,)).fetchone()
    market_cap_crore = mc_row[0] if mc_row else None
    pe_ratio = mc_row[1] if mc_row else None
    pb_ratio = mc_row[2] if mc_row else None

    conn.close()
    return {
        "current_price": current_price,
        "high_52w": high_52w,
        "low_52w": low_52w,
        "market_cap_crore": market_cap_crore,
        "pe_ratio": pe_ratio,
        "pb_ratio": pb_ratio,
    }


@st.cache_data(ttl=600)
def get_peer_percentiles(group_name: Optional[str] = None) -> pd.DataFrame:
    """Retrieve percentile rankings for peer groups."""
    conn = get_connection()
    if group_name:
        query = """
            SELECT pp.*, c.company_name
            FROM peer_percentiles pp
            JOIN companies c ON pp.company_id = c.id
            WHERE pp.peer_group_name = ?
            ORDER BY pp.metric, pp.percentile_rank DESC
        """
        df = pd.read_sql(query, conn, params=(group_name,))
    else:
        query = """
            SELECT pp.*, c.company_name
            FROM peer_percentiles pp
            JOIN companies c ON pp.company_id = c.id
            ORDER BY pp.peer_group_name, pp.metric
        """
        df = pd.read_sql(query, conn)
    conn.close()
    return df
