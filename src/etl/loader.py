"""ETL Data Loader: Ingests, normalizes, validates, and loads Nifty 100 data into SQLite."""

import csv
import os
import sqlite3
import sys
from typing import Any, Dict, List, Set, Tuple

# Ensure workspace root is in sys.path for direct script execution
_WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

from src.etl.normaliser import normalize_ticker, normalize_year
from src.etl.validator import find_source_files, load_raw_sheet_data

DB_PATH = os.getenv("DB_PATH", "nifty100.db")
SCHEMA_PATH = "db/schema.sql"
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "output")


def init_database(db_path: str = DB_PATH, schema_path: str = SCHEMA_PATH) -> sqlite3.Connection:
    """Initialize SQLite database with schema and enforce foreign keys."""
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")

    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    conn.executescript(schema_sql)
    conn.commit()
    return conn


def clean_val(val: Any) -> Any:
    """Clean empty strings, newlines, and invalid representations to None or trimmed value."""
    if val is None:
        return None
    s = str(val).strip()
    if s == "" or s.lower() == "nan" or s.lower() == "none" or s.lower() == "null":
        return None
    if isinstance(val, str):
        return s
    return val


class DataLoader:
    """ETL Pipeline orchestrator loading all 12 files into SQLite database."""

    def __init__(self, db_path: str = DB_PATH, raw_dir: str = "."):
        self.db_path = db_path
        self.raw_dir = raw_dir
        self.files = find_source_files(raw_dir)
        self.conn = init_database(db_path)
        self.valid_company_ids: Set[str] = set()
        self.audit_records: List[Dict[str, Any]] = []

    def run_pipeline(self):
        """Execute full load in strict dependency order."""
        # 1. Parent Table: Companies
        self._load_companies()

        # 2. Core Financial Statements & Market Data
        self._load_profitandloss()
        self._load_balancesheet()
        self._load_cashflow()
        self._load_financial_ratios()
        self._load_stock_prices()
        self._load_market_cap()

        # 3. Supplementary Data
        self._load_documents()
        self._load_sectors()
        self._load_peer_groups()
        self._load_analysis()
        self._load_prosandcons()

        # Verify Foreign Keys
        self._verify_foreign_keys()

        # Write Load Audit
        self._write_load_audit()

    def _load_companies(self):
        """Load companies table (Parent table)."""
        rows = load_raw_sheet_data(self.files["companies"])
        raw_count = len(rows)
        loaded = 0
        deduped = 0
        orphans = 0
        critical_rejections = 0

        cursor = self.conn.cursor()
        seen_pks = set()

        for r in rows:
            cid = normalize_ticker(r.get("id"))
            if not cid or cid in seen_pks:
                deduped += 1
                continue
            seen_pks.add(cid)

            try:
                cursor.execute(
                    """
                    INSERT INTO companies (
                        id, company_logo, company_name, chart_link, about_company,
                        website, nse_profile, bse_profile, face_value, book_value,
                        roce_percentage, roe_percentage
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        cid,
                        clean_val(r.get("company_logo")),
                        clean_val(r.get("company_name")),
                        clean_val(r.get("chart_link")),
                        clean_val(r.get("about_company")),
                        clean_val(r.get("website")),
                        clean_val(r.get("nse_profile")),
                        clean_val(r.get("bse_profile")),
                        clean_val(r.get("face_value")),
                        clean_val(r.get("book_value")),
                        clean_val(r.get("roce_percentage")),
                        clean_val(r.get("roe_percentage")),
                    ),
                )
                self.valid_company_ids.add(cid)
                loaded += 1
            except Exception as e:
                critical_rejections += 1

        self.conn.commit()
        self.audit_records.append(
            {
                "table_name": "companies",
                "raw_file_records": raw_count,
                "valid_records_loaded": loaded,
                "orphan_records_filtered": orphans,
                "duplicate_records_deduped": deduped,
                "critical_rejections_during_load": critical_rejections,
                "status": "SUCCESS" if critical_rejections == 0 else "FAILED",
            }
        )
        print(f"Loaded companies: {loaded}/{raw_count} (FK pool size: {len(self.valid_company_ids)})")

    def _load_profitandloss(self):
        """Load profitandloss table."""
        rows = load_raw_sheet_data(self.files["profitandloss"])
        raw_count = len(rows)
        loaded = 0
        deduped = 0
        orphans = 0
        critical_rejections = 0

        cursor = self.conn.cursor()
        seen_keys = set()

        for r in rows:
            cid = normalize_ticker(r.get("company_id"))
            yr = clean_val(r.get("year"))

            if not cid or not yr:
                continue

            # Resolve DQ-03 FK Integrity: Filter orphan records referencing companies not in master
            if cid not in self.valid_company_ids:
                orphans += 1
                continue

            # Resolve DQ-02: Deduplicate composite key (company_id, year)
            key = (cid, yr)
            if key in seen_keys:
                deduped += 1
                continue
            seen_keys.add(key)

            try:
                cursor.execute(
                    """
                    INSERT INTO profitandloss (
                        company_id, year, sales, expenses, operating_profit,
                        opm_percentage, other_income, interest, depreciation,
                        profit_before_tax, tax_percentage, net_profit, eps, dividend_payout
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        cid,
                        yr,
                        clean_val(r.get("sales")),
                        clean_val(r.get("expenses")),
                        clean_val(r.get("operating_profit")),
                        clean_val(r.get("opm_percentage")),
                        clean_val(r.get("other_income")),
                        clean_val(r.get("interest")),
                        clean_val(r.get("depreciation")),
                        clean_val(r.get("profit_before_tax")),
                        clean_val(r.get("tax_percentage")),
                        clean_val(r.get("net_profit")),
                        clean_val(r.get("eps")),
                        clean_val(r.get("dividend_payout")),
                    ),
                )
                loaded += 1
            except Exception as e:
                critical_rejections += 1

        self.conn.commit()
        self.audit_records.append(
            {
                "table_name": "profitandloss",
                "raw_file_records": raw_count,
                "valid_records_loaded": loaded,
                "orphan_records_filtered": orphans,
                "duplicate_records_deduped": deduped,
                "critical_rejections_during_load": critical_rejections,
                "status": "SUCCESS" if critical_rejections == 0 else "FAILED",
            }
        )
        print(f"Loaded profitandloss: {loaded}/{raw_count} (orphans: {orphans}, dups: {deduped})")

    def _load_balancesheet(self):
        """Load balancesheet table."""
        rows = load_raw_sheet_data(self.files["balancesheet"])
        raw_count = len(rows)
        loaded = 0
        deduped = 0
        orphans = 0
        critical_rejections = 0

        cursor = self.conn.cursor()
        seen_keys = set()

        for r in rows:
            cid = normalize_ticker(r.get("company_id"))
            yr = clean_val(r.get("year"))

            if not cid or not yr:
                continue

            if cid not in self.valid_company_ids:
                orphans += 1
                continue

            key = (cid, yr)
            if key in seen_keys:
                deduped += 1
                continue
            seen_keys.add(key)

            try:
                cursor.execute(
                    """
                    INSERT INTO balancesheet (
                        company_id, year, equity_capital, reserves, borrowings,
                        other_liabilities, total_liabilities, fixed_assets, cwip,
                        investments, other_asset, total_assets
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        cid,
                        yr,
                        clean_val(r.get("equity_capital")),
                        clean_val(r.get("reserves")),
                        clean_val(r.get("borrowings")),
                        clean_val(r.get("other_liabilities")),
                        clean_val(r.get("total_liabilities")),
                        clean_val(r.get("fixed_assets")),
                        clean_val(r.get("cwip")),
                        clean_val(r.get("investments")),
                        clean_val(r.get("other_asset")),
                        clean_val(r.get("total_assets")),
                    ),
                )
                loaded += 1
            except Exception as e:
                critical_rejections += 1

        self.conn.commit()
        self.audit_records.append(
            {
                "table_name": "balancesheet",
                "raw_file_records": raw_count,
                "valid_records_loaded": loaded,
                "orphan_records_filtered": orphans,
                "duplicate_records_deduped": deduped,
                "critical_rejections_during_load": critical_rejections,
                "status": "SUCCESS" if critical_rejections == 0 else "FAILED",
            }
        )
        print(f"Loaded balancesheet: {loaded}/{raw_count} (orphans: {orphans}, dups: {deduped})")

    def _load_cashflow(self):
        """Load cashflow table."""
        rows = load_raw_sheet_data(self.files["cashflow"])
        raw_count = len(rows)
        loaded = 0
        deduped = 0
        orphans = 0
        critical_rejections = 0

        cursor = self.conn.cursor()
        seen_keys = set()

        for r in rows:
            # normalize_ticker fixes AGTL -> ATGL
            cid = normalize_ticker(r.get("company_id"))
            yr = clean_val(r.get("year"))

            if not cid or not yr:
                continue

            if cid not in self.valid_company_ids:
                orphans += 1
                continue

            key = (cid, yr)
            if key in seen_keys:
                deduped += 1
                continue
            seen_keys.add(key)

            try:
                cursor.execute(
                    """
                    INSERT INTO cashflow (
                        company_id, year, operating_activity, investing_activity,
                        financing_activity, net_cash_flow
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        cid,
                        yr,
                        clean_val(r.get("operating_activity")),
                        clean_val(r.get("investing_activity")),
                        clean_val(r.get("financing_activity")),
                        clean_val(r.get("net_cash_flow")),
                    ),
                )
                loaded += 1
            except Exception as e:
                critical_rejections += 1

        self.conn.commit()
        self.audit_records.append(
            {
                "table_name": "cashflow",
                "raw_file_records": raw_count,
                "valid_records_loaded": loaded,
                "orphan_records_filtered": orphans,
                "duplicate_records_deduped": deduped,
                "critical_rejections_during_load": critical_rejections,
                "status": "SUCCESS" if critical_rejections == 0 else "FAILED",
            }
        )
        print(f"Loaded cashflow: {loaded}/{raw_count} (orphans: {orphans}, dups: {deduped})")

    def _load_financial_ratios(self):
        """Load financial_ratios table."""
        rows = load_raw_sheet_data(self.files["financial_ratios"])
        raw_count = len(rows)
        loaded = 0
        deduped = 0
        orphans = 0
        critical_rejections = 0

        cursor = self.conn.cursor()
        seen_keys = set()

        for r in rows:
            cid = normalize_ticker(r.get("company_id"))
            yr = clean_val(r.get("year"))

            if not cid or not yr:
                continue

            if cid not in self.valid_company_ids:
                orphans += 1
                continue

            key = (cid, yr)
            if key in seen_keys:
                deduped += 1
                continue
            seen_keys.add(key)

            try:
                cursor.execute(
                    """
                    INSERT INTO financial_ratios (
                        company_id, year, net_profit_margin_pct, operating_profit_margin_pct,
                        return_on_equity_pct, debt_to_equity, interest_coverage, asset_turnover,
                        free_cash_flow_cr, capex_cr, earnings_per_share, book_value_per_share,
                        dividend_payout_ratio_pct, total_debt_cr, cash_from_operations_cr
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        cid,
                        yr,
                        clean_val(r.get("net_profit_margin_pct")),
                        clean_val(r.get("operating_profit_margin_pct")),
                        clean_val(r.get("return_on_equity_pct")),
                        clean_val(r.get("debt_to_equity")),
                        clean_val(r.get("interest_coverage")),
                        clean_val(r.get("asset_turnover")),
                        clean_val(r.get("free_cash_flow_cr")),
                        clean_val(r.get("capex_cr")),
                        clean_val(r.get("earnings_per_share")),
                        clean_val(r.get("book_value_per_share")),
                        clean_val(r.get("dividend_payout_ratio_pct")),
                        clean_val(r.get("total_debt_cr")),
                        clean_val(r.get("cash_from_operations_cr")),
                    ),
                )
                loaded += 1
            except Exception as e:
                critical_rejections += 1

        self.conn.commit()
        self.audit_records.append(
            {
                "table_name": "financial_ratios",
                "raw_file_records": raw_count,
                "valid_records_loaded": loaded,
                "orphan_records_filtered": orphans,
                "duplicate_records_deduped": deduped,
                "critical_rejections_during_load": critical_rejections,
                "status": "SUCCESS" if critical_rejections == 0 else "FAILED",
            }
        )
        print(f"Loaded financial_ratios: {loaded}/{raw_count} (orphans: {orphans}, dups: {deduped})")

    def _load_stock_prices(self):
        """Load stock_prices table."""
        rows = load_raw_sheet_data(self.files["stock_prices"])
        raw_count = len(rows)
        loaded = 0
        deduped = 0
        orphans = 0
        critical_rejections = 0

        cursor = self.conn.cursor()
        seen_keys = set()

        for r in rows:
            cid = normalize_ticker(r.get("company_id"))
            dt = clean_val(r.get("date"))

            if not cid or not dt:
                continue

            if cid not in self.valid_company_ids:
                orphans += 1
                continue

            key = (cid, dt)
            if key in seen_keys:
                deduped += 1
                continue
            seen_keys.add(key)

            op = clean_val(r.get("open_price"))
            hp = clean_val(r.get("high_price"))
            lp = clean_val(r.get("low_price"))
            cp = clean_val(r.get("close_price"))
            vol = clean_val(r.get("volume"))
            adj_close = clean_val(r.get("adjusted_close"))

            if op is not None and hp is not None and lp is not None and cp is not None:
                try:
                    op = float(op)
                    hp = float(hp)
                    lp = float(lp)
                    cp = float(cp)
                    hp = max(hp, op, cp)
                    lp = min(lp, op, cp)
                except (ValueError, TypeError):
                    pass

            try:
                cursor.execute(
                    """
                    INSERT INTO stock_prices (
                        company_id, date, open_price, high_price, low_price,
                        close_price, volume, adjusted_close
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (cid, dt, op, hp, lp, cp, vol, adj_close),
                )
                loaded += 1
            except Exception as e:
                critical_rejections += 1

        self.conn.commit()
        self.audit_records.append(
            {
                "table_name": "stock_prices",
                "raw_file_records": raw_count,
                "valid_records_loaded": loaded,
                "orphan_records_filtered": orphans,
                "duplicate_records_deduped": deduped,
                "critical_rejections_during_load": critical_rejections,
                "status": "SUCCESS" if critical_rejections == 0 else "FAILED",
            }
        )
        print(f"Loaded stock_prices: {loaded}/{raw_count}")

    def _load_market_cap(self):
        """Load market_cap table."""
        rows = load_raw_sheet_data(self.files["market_cap"])
        raw_count = len(rows)
        loaded = 0
        deduped = 0
        orphans = 0
        critical_rejections = 0

        cursor = self.conn.cursor()
        seen_keys = set()

        for r in rows:
            cid = normalize_ticker(r.get("company_id"))
            yr = clean_val(r.get("year"))

            if not cid or not yr:
                continue

            if cid not in self.valid_company_ids:
                orphans += 1
                continue

            key = (cid, yr)
            if key in seen_keys:
                deduped += 1
                continue
            seen_keys.add(key)

            try:
                cursor.execute(
                    """
                    INSERT INTO market_cap (
                        company_id, year, market_cap_crore, enterprise_value_crore,
                        pe_ratio, pb_ratio, ev_ebitda, dividend_yield_pct
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        cid,
                        yr,
                        clean_val(r.get("market_cap_crore")),
                        clean_val(r.get("enterprise_value_crore")),
                        clean_val(r.get("pe_ratio")),
                        clean_val(r.get("pb_ratio")),
                        clean_val(r.get("ev_ebitda")),
                        clean_val(r.get("dividend_yield_pct")),
                    ),
                )
                loaded += 1
            except Exception as e:
                critical_rejections += 1

        self.conn.commit()
        self.audit_records.append(
            {
                "table_name": "market_cap",
                "raw_file_records": raw_count,
                "valid_records_loaded": loaded,
                "orphan_records_filtered": orphans,
                "duplicate_records_deduped": deduped,
                "critical_rejections_during_load": critical_rejections,
                "status": "SUCCESS" if critical_rejections == 0 else "FAILED",
            }
        )
        print(f"Loaded market_cap: {loaded}/{raw_count}")

    def _load_documents(self):
        """Load documents table."""
        rows = load_raw_sheet_data(self.files["documents"])
        raw_count = len(rows)
        loaded = 0
        deduped = 0
        orphans = 0
        critical_rejections = 0

        cursor = self.conn.cursor()
        seen_keys = set()

        for r in rows:
            cid = normalize_ticker(r.get("company_id"))
            yr = clean_val(r.get("year"))

            if not cid or not yr:
                continue

            if cid not in self.valid_company_ids:
                orphans += 1
                continue

            key = (cid, yr)
            if key in seen_keys:
                deduped += 1
                continue
            seen_keys.add(key)

            try:
                cursor.execute(
                    """
                    INSERT INTO documents (company_id, year, annual_report)
                    VALUES (?, ?, ?)
                """,
                    (cid, yr, clean_val(r.get("annual_report"))),
                )
                loaded += 1
            except Exception as e:
                critical_rejections += 1

        self.conn.commit()
        self.audit_records.append(
            {
                "table_name": "documents",
                "raw_file_records": raw_count,
                "valid_records_loaded": loaded,
                "orphan_records_filtered": orphans,
                "duplicate_records_deduped": deduped,
                "critical_rejections_during_load": critical_rejections,
                "status": "SUCCESS" if critical_rejections == 0 else "FAILED",
            }
        )
        print(f"Loaded documents: {loaded}/{raw_count}")

    def _load_sectors(self):
        """Load sectors table."""
        rows = load_raw_sheet_data(self.files["sectors"])
        raw_count = len(rows)
        loaded = 0
        deduped = 0
        orphans = 0
        critical_rejections = 0

        cursor = self.conn.cursor()
        seen_keys = set()

        for r in rows:
            cid = normalize_ticker(r.get("company_id"))
            if not cid or cid in seen_keys:
                deduped += 1
                continue

            if cid not in self.valid_company_ids:
                orphans += 1
                continue
            seen_keys.add(cid)

            try:
                cursor.execute(
                    """
                    INSERT INTO sectors (
                        company_id, broad_sector, sub_sector, index_weight_pct, market_cap_category
                    ) VALUES (?, ?, ?, ?, ?)
                """,
                    (
                        cid,
                        clean_val(r.get("broad_sector")),
                        clean_val(r.get("sub_sector")),
                        clean_val(r.get("index_weight_pct")),
                        clean_val(r.get("market_cap_category")),
                    ),
                )
                loaded += 1
            except Exception as e:
                critical_rejections += 1

        self.conn.commit()
        self.audit_records.append(
            {
                "table_name": "sectors",
                "raw_file_records": raw_count,
                "valid_records_loaded": loaded,
                "orphan_records_filtered": orphans,
                "duplicate_records_deduped": deduped,
                "critical_rejections_during_load": critical_rejections,
                "status": "SUCCESS" if critical_rejections == 0 else "FAILED",
            }
        )
        print(f"Loaded sectors: {loaded}/{raw_count}")

    def _load_peer_groups(self):
        """Load peer_groups table."""
        rows = load_raw_sheet_data(self.files["peer_groups"])
        raw_count = len(rows)
        loaded = 0
        deduped = 0
        orphans = 0
        critical_rejections = 0

        cursor = self.conn.cursor()
        seen_keys = set()

        for r in rows:
            cid = normalize_ticker(r.get("company_id"))
            pg_name = clean_val(r.get("peer_group_name"))

            if not cid or not pg_name:
                continue

            if cid not in self.valid_company_ids:
                orphans += 1
                continue

            key = (pg_name, cid)
            if key in seen_keys:
                deduped += 1
                continue
            seen_keys.add(key)

            try:
                cursor.execute(
                    """
                    INSERT INTO peer_groups (peer_group_name, company_id, is_benchmark)
                    VALUES (?, ?, ?)
                """,
                    (pg_name, cid, clean_val(r.get("is_benchmark"))),
                )
                loaded += 1
            except Exception as e:
                critical_rejections += 1

        self.conn.commit()
        self.audit_records.append(
            {
                "table_name": "peer_groups",
                "raw_file_records": raw_count,
                "valid_records_loaded": loaded,
                "orphan_records_filtered": orphans,
                "duplicate_records_deduped": deduped,
                "critical_rejections_during_load": critical_rejections,
                "status": "SUCCESS" if critical_rejections == 0 else "FAILED",
            }
        )
        print(f"Loaded peer_groups: {loaded}/{raw_count}")

    def _load_analysis(self):
        """Load analysis table."""
        rows = load_raw_sheet_data(self.files["analysis"])
        raw_count = len(rows)
        loaded = 0
        deduped = 0
        orphans = 0
        critical_rejections = 0

        cursor = self.conn.cursor()

        for r in rows:
            cid = normalize_ticker(r.get("company_id"))
            if not cid:
                continue

            if cid not in self.valid_company_ids:
                orphans += 1
                continue

            try:
                cursor.execute(
                    """
                    INSERT INTO analysis (
                        company_id, compounded_sales_growth, compounded_profit_growth,
                        stock_price_cagr, roe
                    ) VALUES (?, ?, ?, ?, ?)
                """,
                    (
                        cid,
                        clean_val(r.get("compounded_sales_growth")),
                        clean_val(r.get("compounded_profit_growth")),
                        clean_val(r.get("stock_price_cagr")),
                        clean_val(r.get("roe")),
                    ),
                )
                loaded += 1
            except Exception as e:
                critical_rejections += 1

        self.conn.commit()
        self.audit_records.append(
            {
                "table_name": "analysis",
                "raw_file_records": raw_count,
                "valid_records_loaded": loaded,
                "orphan_records_filtered": orphans,
                "duplicate_records_deduped": deduped,
                "critical_rejections_during_load": critical_rejections,
                "status": "SUCCESS" if critical_rejections == 0 else "FAILED",
            }
        )
        print(f"Loaded analysis: {loaded}/{raw_count}")

    def _load_prosandcons(self):
        """Load prosandcons table."""
        rows = load_raw_sheet_data(self.files["prosandcons"])
        raw_count = len(rows)
        loaded = 0
        deduped = 0
        orphans = 0
        critical_rejections = 0

        cursor = self.conn.cursor()

        for r in rows:
            cid = normalize_ticker(r.get("company_id"))
            if not cid:
                continue

            if cid not in self.valid_company_ids:
                orphans += 1
                continue

            try:
                cursor.execute(
                    """
                    INSERT INTO prosandcons (company_id, pros, cons)
                    VALUES (?, ?, ?)
                """,
                    (cid, clean_val(r.get("pros")), clean_val(r.get("cons"))),
                )
                loaded += 1
            except Exception as e:
                critical_rejections += 1

        self.conn.commit()
        self.audit_records.append(
            {
                "table_name": "prosandcons",
                "raw_file_records": raw_count,
                "valid_records_loaded": loaded,
                "orphan_records_filtered": orphans,
                "duplicate_records_deduped": deduped,
                "critical_rejections_during_load": critical_rejections,
                "status": "SUCCESS" if critical_rejections == 0 else "FAILED",
            }
        )
        print(f"Loaded prosandcons: {loaded}/{raw_count}")

    def _verify_foreign_keys(self):
        """Execute PRAGMA foreign_key_check to ensure zero FK violations."""
        cursor = self.conn.cursor()
        fk_violations = cursor.execute("PRAGMA foreign_key_check;").fetchall()
        if fk_violations:
            print(f"WARNING: Foreign key violations found: {len(fk_violations)}")
            for v in fk_violations:
                print(" ", v)
        else:
            print("PRAGMA foreign_key_check PASSED: 0 violations found.")

    def _write_load_audit(self, output_path: str = "output/load_audit.csv"):
        """Write load audit CSV report."""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "table_name",
                    "raw_file_records",
                    "valid_records_loaded",
                    "orphan_records_filtered",
                    "duplicate_records_deduped",
                    "critical_rejections_during_load",
                    "status",
                ],
            )
            writer.writeheader()
            for rec in self.audit_records:
                writer.writerow(rec)
        print(f"Load audit report generated: {output_path}")

    def close(self):
        self.conn.close()


if __name__ == "__main__":
    loader = DataLoader(DB_PATH, ".")
    loader.run_pipeline()
    loader.close()
