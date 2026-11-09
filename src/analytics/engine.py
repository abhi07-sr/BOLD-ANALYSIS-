"""Financial Ratio Engine: Computes 50+ KPIs across all 92 companies and populates financial_ratios."""

import csv
import logging
import os
import sqlite3
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

# Ensure workspace root is in sys.path for direct script execution
_WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

from src.analytics.cagr import compute_cagr, compute_historical_cagr
from src.analytics.cashflow_kpis import (
    classify_capital_allocation,
    compute_capex_intensity,
    compute_cfo_quality_score,
    compute_fcf_conversion,
    compute_free_cash_flow,
    generate_capital_allocation_report,
)
from src.analytics.ratios import (
    compute_asset_turnover,
    compute_debt_to_equity,
    compute_interest_coverage,
    compute_net_debt,
    compute_npm,
    compute_opm,
    compute_roa,
    compute_roce,
    compute_roe,
)
from src.etl.normaliser import normalize_year

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = os.getenv("DB_PATH", "nifty100.db")


def parse_numeric_year(yr_str: str) -> Optional[int]:
    """Extract 4-digit calendar/fiscal year as integer."""
    if not yr_str or yr_str.upper() == "TTM":
        return None
    norm = normalize_year(yr_str)
    if norm and norm.isdigit():
        return int(norm)
    return None


def calculate_composite_quality_score(
    roe: Optional[float],
    de: Optional[float],
    icr: Optional[float],
    npm: Optional[float],
    cfo_quality: Optional[float],
    sales_cagr: Optional[float],
    is_financial: bool = False,
) -> float:
    """Compute a composite quality score (0 to 100) based on financial health."""
    score = 0.0

    # 1. ROE (up to 25 points)
    if roe is not None:
        if roe >= 20.0:
            score += 25.0
        elif roe >= 15.0:
            score += 20.0
        elif roe >= 10.0:
            score += 10.0
        elif roe > 0:
            score += 5.0

    # 2. Leverage D/E (up to 20 points)
    if is_financial:
        score += 20.0  # Leverage is operating model for banks
    elif de is not None:
        if de <= 0.3:
            score += 20.0
        elif de <= 0.7:
            score += 15.0
        elif de <= 1.5:
            score += 10.0
        elif de <= 3.0:
            score += 5.0

    # 3. Interest Coverage (up to 15 points)
    if is_financial or icr is None:
        score += 15.0  # Debt-free or financial carveout
    else:
        if icr >= 5.0:
            score += 15.0
        elif icr >= 3.0:
            score += 10.0
        elif icr >= 1.5:
            score += 5.0

    # 4. Net Profit Margin (up to 15 points)
    if npm is not None:
        if npm >= 20.0:
            score += 15.0
        elif npm >= 12.0:
            score += 10.0
        elif npm >= 5.0:
            score += 5.0

    # 5. Cash Flow Quality (up to 15 points)
    if cfo_quality is not None:
        if cfo_quality >= 1.0:
            score += 15.0
        elif cfo_quality >= 0.7:
            score += 10.0
        elif cfo_quality >= 0.5:
            score += 5.0

    # 6. Revenue Growth CAGR (up to 10 points)
    if sales_cagr is not None:
        if sales_cagr >= 15.0:
            score += 10.0
        elif sales_cagr >= 8.0:
            score += 7.0
        elif sales_cagr > 0:
            score += 4.0

    return round(score, 1)


class RatioEngine:
    """Calculates all KPIs and populates financial_ratios table in SQLite."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.financial_tickers = self._get_financial_tickers()

    def _get_financial_tickers(self) -> Set[str]:
        cursor = self.conn.cursor()
        rows = cursor.execute(
            "SELECT company_id FROM sectors WHERE broad_sector = 'Financials'"
        ).fetchall()
        return {r["company_id"] for r in rows}

    def run(self) -> int:
        """Run full KPI computation for all 92 companies across all available years."""
        cursor = self.conn.cursor()

        # Gather company metadata
        companies_meta = {}
        for row in cursor.execute("SELECT id, face_value, book_value, roce_percentage, roe_percentage FROM companies"):
            companies_meta[row["id"]] = dict(row)

        # Gather all P&L records
        pnl_records = {}
        for row in cursor.execute("SELECT * FROM profitandloss ORDER BY company_id, year"):
            pnl_records.setdefault(row["company_id"], []).append(dict(row))

        # Gather all Balance Sheet records
        bs_records = {}
        for row in cursor.execute("SELECT * FROM balancesheet ORDER BY company_id, year"):
            bs_records.setdefault(row["company_id"], []).append(dict(row))

        # Gather all Cash Flow records
        cf_records = {}
        for row in cursor.execute("SELECT * FROM cashflow ORDER BY company_id, year"):
            cf_records.setdefault(row["company_id"], []).append(dict(row))

        # Prepare lookup maps by (company_id, year)
        bs_lookup = {(r["company_id"], r["year"]): r for rows in bs_records.values() for r in rows}
        cf_lookup = {(r["company_id"], r["year"]): r for rows in cf_records.values() for r in rows}

        # Build historical series dictionaries for CAGR: company_id -> int_year -> value
        sales_hist: Dict[str, Dict[int, float]] = {}
        pat_hist: Dict[str, Dict[int, float]] = {}
        eps_hist: Dict[str, Dict[int, float]] = {}
        cfo_hist: Dict[str, List[float]] = {}
        pat_list_hist: Dict[str, List[float]] = {}

        for cid, rows in pnl_records.items():
            sales_hist[cid] = {}
            pat_hist[cid] = {}
            eps_hist[cid] = {}
            pat_list_hist[cid] = []
            for r in rows:
                yr_num = parse_numeric_year(r["year"])
                if yr_num is not None:
                    if r.get("sales") is not None:
                        sales_hist[cid][yr_num] = float(r["sales"])
                    if r.get("net_profit") is not None:
                        pat_hist[cid][yr_num] = float(r["net_profit"])
                        pat_list_hist[cid].append(float(r["net_profit"]))
                    if r.get("eps") is not None:
                        eps_hist[cid][yr_num] = float(r["eps"])

        for cid, rows in cf_records.items():
            cfo_hist[cid] = []
            for r in rows:
                if r.get("operating_activity") is not None:
                    cfo_hist[cid].append(float(r["operating_activity"]))

        # Compute ratios for every distinct (company_id, year) across P&L and Balance Sheet
        all_keys = set(pnl_records.keys())
        computed_rows = []
        anomalies = []

        for cid in sorted(all_keys):
            is_fin = cid in self.financial_tickers
            meta = companies_meta.get(cid, {})
            c_pnl = pnl_records.get(cid, [])

            # Compute company-wide 5Y CFO Quality score
            cfo_q_score, cfo_q_label = compute_cfo_quality_score(
                cfo_hist.get(cid, []), pat_list_hist.get(cid, [])
            )

            for pnl in c_pnl:
                yr = pnl["year"]
                yr_num = parse_numeric_year(yr)
                bs = bs_lookup.get((cid, yr), {})
                cf = cf_lookup.get((cid, yr), {})

                # Financial values
                sales = pnl.get("sales")
                op = pnl.get("operating_profit")
                net_profit = pnl.get("net_profit")
                pbt = pnl.get("profit_before_tax")
                interest = pnl.get("interest")
                eps = pnl.get("eps")
                div_payout = pnl.get("dividend_payout")
                opm_rep = pnl.get("opm_percentage")

                eq_cap = bs.get("equity_capital")
                reserves = bs.get("reserves")
                borrowings = bs.get("borrowings")
                tot_assets = bs.get("total_assets")

                cfo = cf.get("operating_activity")
                cfi = cf.get("investing_activity")

                # 1. Profitability KPIs
                npm = compute_npm(net_profit, sales)
                opm, opm_mismatch = compute_opm(op, sales, opm_rep)
                roe = compute_roe(net_profit, eq_cap, reserves)
                roa = compute_roa(net_profit, tot_assets)
                roce = compute_roce(pbt, interest, eq_cap, reserves, borrowings, is_financial=is_fin)

                # 2. Leverage & Efficiency KPIs
                de, high_leverage_flag = compute_debt_to_equity(
                    borrowings, eq_cap, reserves, is_financial=is_fin
                )
                icr, icr_label, icr_warning = compute_interest_coverage(
                    op, pnl.get("other_income"), interest
                )
                asset_turnover = compute_asset_turnover(sales, tot_assets)

                # 3. Cash Flow KPIs
                fcf = compute_free_cash_flow(cfo, cfi)
                capex_cr = abs(float(cfi)) if cfi is not None else None
                capex_pct, capex_label = compute_capex_intensity(cfi, sales)

                # 4. Book Value Per Share
                face_val = meta.get("face_value")
                bvps = None
                if eq_cap is not None and reserves is not None:
                    tot_eq = eq_cap + reserves
                    if face_val and float(face_val) > 0 and eq_cap > 0:
                        num_shares = eq_cap / float(face_val)
                        bvps = round(tot_eq / num_shares, 2)
                    elif meta.get("book_value"):
                        bvps = float(meta["book_value"])

                # 5. CAGR Metrics (5-Year Lookback)
                rev_cagr_5, rev_flag = (
                    compute_historical_cagr(sales_hist[cid], yr_num, 5)
                    if yr_num
                    else (None, "INSUFFICIENT")
                )
                pat_cagr_5, pat_flag = (
                    compute_historical_cagr(pat_hist[cid], yr_num, 5)
                    if yr_num
                    else (None, "INSUFFICIENT")
                )
                eps_cagr_5, eps_flag = (
                    compute_historical_cagr(eps_hist[cid], yr_num, 5)
                    if yr_num
                    else (None, "INSUFFICIENT")
                )

                # 6. Composite Quality Score
                comp_quality = calculate_composite_quality_score(
                    roe, de, icr, npm, cfo_q_score, rev_cagr_5, is_financial=is_fin
                )

                # Track Day 13 Anomaly Checks (on latest year e.g. 2024)
                if yr_num == 2024:
                    # ROCE anomaly check vs companies.roce_percentage
                    src_roce = meta.get("roce_percentage")
                    if roce is not None and src_roce is not None:
                        diff_roce = abs(roce - float(src_roce))
                        if diff_roce > 5.0:
                            category = "FORMULA_DISCREPANCY" if is_fin else "DATA_SOURCE_ISSUE"
                            anomalies.append(
                                f"ROCE Anomaly [{category}]: {cid} (2024) Computed={roce}%, Source={src_roce}%, Diff={diff_roce:.2f}%"
                            )

                    # ROE anomaly check vs companies.roe_percentage
                    src_roe = meta.get("roe_percentage")
                    if roe is not None and src_roe is not None:
                        src_roe_f = float(src_roe)
                        # Detect decimal fractions (e.g. TCS 0.52 vs 52%)
                        if 0 < src_roe_f < 1.0 and roe > 10.0:
                            anomalies.append(
                                f"ROE Anomaly [DATA_SOURCE_ISSUE]: {cid} (2024) Computed={roe}%, Source={src_roe_f} (Raw source stored as decimal ratio instead of percentage)"
                            )
                        elif abs(roe - src_roe_f) > 5.0:
                            anomalies.append(
                                f"ROE Anomaly [VERSION_DIFFERENCE]: {cid} (2024) Computed={roe}%, Source={src_roe_f}%, Diff={abs(roe - src_roe_f):.2f}%"
                            )

                computed_rows.append(
                    (
                        cid,
                        yr,
                        npm,
                        opm,
                        roe,
                        roa,
                        roce,
                        de,
                        1 if high_leverage_flag else 0,
                        icr,
                        icr_label,
                        asset_turnover,
                        fcf,
                        capex_cr,
                        eps,
                        bvps,
                        div_payout,
                        borrowings,
                        cfo,
                        rev_cagr_5,
                        rev_flag,
                        pat_cagr_5,
                        pat_flag,
                        eps_cagr_5,
                        eps_flag,
                        cfo_q_score,
                        capex_label,
                        comp_quality,
                    )
                )

        # Recreate financial_ratios table with all KPI columns
        cursor.execute("DROP TABLE IF EXISTS financial_ratios;")
        cursor.execute("""
            CREATE TABLE financial_ratios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                year TEXT NOT NULL,
                net_profit_margin_pct REAL,
                operating_profit_margin_pct REAL,
                return_on_equity_pct REAL,
                return_on_assets_pct REAL,
                return_on_capital_employed_pct REAL,
                debt_to_equity REAL,
                high_leverage_flag INTEGER DEFAULT 0,
                interest_coverage REAL,
                icr_label TEXT,
                asset_turnover REAL,
                free_cash_flow_cr REAL,
                capex_cr REAL,
                earnings_per_share REAL,
                book_value_per_share REAL,
                dividend_payout_ratio_pct REAL,
                total_debt_cr REAL,
                cash_from_operations_cr REAL,
                revenue_cagr_5yr REAL,
                revenue_cagr_5yr_flag TEXT,
                pat_cagr_5yr REAL,
                pat_cagr_5yr_flag TEXT,
                eps_cagr_5yr REAL,
                eps_cagr_5yr_flag TEXT,
                cfo_quality_score REAL,
                capex_intensity_label TEXT,
                composite_quality_score REAL,
                UNIQUE(company_id, year)
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ratios_comp_yr ON financial_ratios(company_id, year);")

        cursor.executemany(
            """
            INSERT INTO financial_ratios (
                company_id, year, net_profit_margin_pct, operating_profit_margin_pct,
                return_on_equity_pct, return_on_assets_pct, return_on_capital_employed_pct,
                debt_to_equity, high_leverage_flag, interest_coverage, icr_label,
                asset_turnover, free_cash_flow_cr, capex_cr, earnings_per_share,
                book_value_per_share, dividend_payout_ratio_pct, total_debt_cr,
                cash_from_operations_cr, revenue_cagr_5yr, revenue_cagr_5yr_flag,
                pat_cagr_5yr, pat_cagr_5yr_flag, eps_cagr_5yr, eps_cagr_5yr_flag,
                cfo_quality_score, capex_intensity_label, composite_quality_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            computed_rows,
        )
        self.conn.commit()

        # Write output/ratio_edge_cases.log
        self._write_edge_cases_log(anomalies)

        # Generate output/capital_allocation.csv
        generate_capital_allocation_report(self.db_path, "output/capital_allocation.csv")

        total_loaded = len(computed_rows)
        print(f"Successfully populated financial_ratios table: {total_loaded} rows inserted.")
        return total_loaded

    def _write_edge_cases_log(self, anomalies: List[str], output_path: str = "output/ratio_edge_cases.log"):
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("# Ratio Engine Edge Cases and Anomaly Cross-Check Log\n")
            f.write("# Categories: DATA_SOURCE_ISSUE, VERSION_DIFFERENCE, FORMULA_DISCREPANCY\n\n")
            for a in anomalies:
                f.write(f"{a}\n")
        print(f"Edge cases log generated: {output_path} ({len(anomalies)} anomalies logged)")

    def close(self):
        self.conn.close()


if __name__ == "__main__":
    engine = RatioEngine()
    count = engine.run()
    engine.close()
