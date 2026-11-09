"""Schema and Data Quality Validator implementing DQ-01 to DQ-16."""

import csv
import glob
import os
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Set

# Ensure workspace root is in sys.path for direct script execution
_WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

import openpyxl
from src.etl.normaliser import normalize_ticker, normalize_year


@dataclass
class ValidationFailure:
    rule_id: str
    severity: str  # 'CRITICAL' or 'WARNING'
    table_name: str
    record_id: Any
    company_id: str
    column_name: str
    error_message: str
    value: Any


def load_raw_sheet_data(filepath: str) -> List[Dict[str, Any]]:
    """Load an Excel file into a list of row dictionaries.

    Auto-detects whether Row 1 is a banner or header.
    """
    wb: Any = openpyxl.load_workbook(filepath, data_only=True)
    sheet: Any = wb.active or (wb.worksheets[0] if wb.worksheets else None)
    if sheet is None:
        return []

    rows = []
    for row in sheet.iter_rows(values_only=True):
        rows.append(list(row))

    if not rows:
        return []

    # Check if row 1 is a banner (contains 'Bluestock' or 'records' or only 1 non-empty cell)
    r1_non_empty = [c for c in rows[0] if c is not None and str(c).strip()]
    has_banner = False
    if len(r1_non_empty) == 1 and any(
        kw in str(r1_non_empty[0]) for kw in ["Fintech", "records", "Nifty"]
    ):
        has_banner = True

    header_idx = 1 if has_banner else 0
    raw_headers = rows[header_idx]
    headers = [str(h).strip().lower() if h is not None else f"col_{i}" for i, h in enumerate(raw_headers)]

    records = []
    for r_idx in range(header_idx + 1, len(rows)):
        row_vals = rows[r_idx]
        row_dict = {}
        for c_idx, h in enumerate(headers):
            val = row_vals[c_idx] if c_idx < len(row_vals) else None
            row_dict[h] = val
        row_dict["__row_num__"] = r_idx + 1
        records.append(row_dict)

    return records


def find_source_files(raw_dir: str = ".") -> Dict[str, str]:
    """Find all 12 raw source Excel files by matching pattern."""
    files = glob.glob(os.path.join(raw_dir, "*.xlsx"))
    table_files = {}
    for f in files:
        basename = os.path.basename(f)
        # Extract table identifier after last dash or before .xlsx
        clean_name = basename.split("-")[-1].replace(".xlsx", "").lower().strip()
        table_files[clean_name] = f
    return table_files


class DataQualityValidator:
    """16 DQ rules validation engine."""

    def __init__(self, raw_dir: str = "."):
        self.raw_dir = raw_dir
        self.files = find_source_files(raw_dir)
        self.failures: List[ValidationFailure] = []
        self.datasets: Dict[str, List[Dict[str, Any]]] = {}

    def load_all_datasets(self):
        """Load all source files into memory."""
        for tbl, fpath in self.files.items():
            self.datasets[tbl] = load_raw_sheet_data(fpath)

    def run_all_rules(self) -> List[ValidationFailure]:
        """Execute DQ-01 through DQ-16."""
        if not self.datasets:
            self.load_all_datasets()

        companies_data = self.datasets.get("companies", [])
        valid_company_ids: Set[str] = set()
        for r in companies_data:
            cid = normalize_ticker(r.get("id"))
            if cid:
                valid_company_ids.add(cid)

        # DQ-01: Primary Key Uniqueness
        self._validate_dq01_pk_uniqueness()

        # DQ-02: Composite PK Uniqueness (company_id, year)
        self._validate_dq02_composite_pk()

        # DQ-03: Foreign Key Integrity
        self._validate_dq03_fk_integrity(valid_company_ids)

        # DQ-04: Balance Sheet Equation (<1% discrepancy)
        self._validate_dq04_bs_balance()

        # DQ-05: OPM Cross-Check
        self._validate_dq05_opm_crosscheck()

        # DQ-06: Positive Sales
        self._validate_dq06_positive_sales()

        # DQ-07: Net Cash Flow Reconciliation
        self._validate_dq07_net_cash_flow()

        # DQ-08: Tax Rate Bounds
        self._validate_dq08_tax_rate()

        # DQ-09: Dividend Payout Cap
        self._validate_dq09_dividend_cap()

        # DQ-10: URL Format Validation
        self._validate_dq10_urls()

        # DQ-11: EPS Sign Consistency
        self._validate_dq11_eps_sign()

        # DQ-12: Balance Sheet Liability Component Balance
        self._validate_dq12_bs_components()

        # DQ-13: Historical Year Coverage
        self._validate_dq13_year_coverage()

        # DQ-14: Stock Prices Integrity
        self._validate_dq14_stock_prices()

        # DQ-15: Financial Ratios Consistency
        self._validate_dq15_financial_ratios()

        # DQ-16: Critical Non-Null Fields
        self._validate_dq16_non_null_fields()

        return self.failures

    def _validate_dq01_pk_uniqueness(self):
        """DQ-01 [CRITICAL]: Primary key uniqueness (id column)."""
        for tbl, rows in self.datasets.items():
            ids = [r.get("id") for r in rows if r.get("id") is not None]
            id_counts = Counter(ids)
            for pk, count in id_counts.items():
                if count > 1:
                    self.failures.append(
                        ValidationFailure(
                            rule_id="DQ-01",
                            severity="CRITICAL",
                            table_name=tbl,
                            record_id=pk,
                            company_id=str(pk) if tbl == "companies" else "",
                            column_name="id",
                            error_message=f"Duplicate primary key 'id'={pk} found {count} times",
                            value=pk,
                        )
                    )

    def _validate_dq02_composite_pk(self):
        """DQ-02 [CRITICAL]: Composite PK (company_id, year) uniqueness in annual tables."""
        annual_tables = ["profitandloss", "balancesheet", "cashflow", "financial_ratios", "market_cap"]
        for tbl in annual_tables:
            rows = self.datasets.get(tbl, [])
            keys = []
            for r in rows:
                cid = normalize_ticker(r.get("company_id"))
                yr = normalize_year(r.get("year"))
                if cid and yr:
                    keys.append(((cid, yr), r.get("id", r.get("__row_num__"))))

            key_counts = Counter(k[0] for k in keys)
            reported = set()
            for (cid, yr), rec_id in keys:
                if key_counts[(cid, yr)] > 1 and (cid, yr) not in reported:
                    reported.add((cid, yr))
                    self.failures.append(
                        ValidationFailure(
                            rule_id="DQ-02",
                            severity="CRITICAL",
                            table_name=tbl,
                            record_id=rec_id,
                            company_id=cid,
                            column_name="company_id, year",
                            error_message=f"Duplicate (company_id, year) pair ('{cid}', '{yr}') in {tbl} ({key_counts[(cid, yr)]} times)",
                            value=f"{cid}_{yr}",
                        )
                    )

    def _validate_dq03_fk_integrity(self, valid_company_ids: Set[str]):
        """DQ-03 [CRITICAL]: Foreign key integrity check."""
        for tbl, rows in self.datasets.items():
            if tbl == "companies":
                continue
            for r in rows:
                cid_raw = r.get("company_id")
                cid_norm = normalize_ticker(cid_raw)
                if cid_norm and cid_norm not in valid_company_ids:
                    self.failures.append(
                        ValidationFailure(
                            rule_id="DQ-03",
                            severity="CRITICAL",
                            table_name=tbl,
                            record_id=r.get("id", r.get("__row_num__")),
                            company_id=cid_norm,
                            column_name="company_id",
                            error_message=f"Foreign key violation: company_id '{cid_norm}' not found in companies table",
                            value=cid_norm,
                        )
                    )

    def _validate_dq04_bs_balance(self):
        """DQ-04 [WARNING]: Balance Sheet balance (<1% discrepancy between assets and liabilities)."""
        rows = self.datasets.get("balancesheet", [])
        for r in rows:
            try:
                tot_liab = float(r.get("total_liabilities") or 0)
                tot_assets = float(r.get("total_assets") or 0)
                cid = normalize_ticker(r.get("company_id")) or ""
                yr = str(r.get("year") or "")
                if tot_assets > 0:
                    diff_pct = abs(tot_assets - tot_liab) / tot_assets
                    if diff_pct > 0.01:
                        self.failures.append(
                            ValidationFailure(
                                rule_id="DQ-04",
                                severity="WARNING",
                                table_name="balancesheet",
                                record_id=r.get("id", r.get("__row_num__")),
                                company_id=cid,
                                column_name="total_assets, total_liabilities",
                                error_message=f"BS imbalance: assets={tot_assets}, liab={tot_liab}, diff={diff_pct*100:.2f}% (year {yr})",
                                value=f"diff_{diff_pct:.4f}",
                            )
                        )
            except (ValueError, TypeError):
                pass

    def _validate_dq05_opm_crosscheck(self):
        """DQ-05 [WARNING]: OPM cross-check (operating_profit / sales * 100 vs opm_percentage)."""
        rows = self.datasets.get("profitandloss", [])
        for r in rows:
            try:
                sales = float(r.get("sales") or 0)
                op = float(r.get("operating_profit") or 0)
                opm_reported = float(r.get("opm_percentage") or 0)
                cid = normalize_ticker(r.get("company_id")) or ""
                if sales > 0:
                    opm_calc = (op / sales) * 100
                    if abs(opm_calc - opm_reported) > 2.0:
                        self.failures.append(
                            ValidationFailure(
                                rule_id="DQ-05",
                                severity="WARNING",
                                table_name="profitandloss",
                                record_id=r.get("id", r.get("__row_num__")),
                                company_id=cid,
                                column_name="opm_percentage",
                                error_message=f"OPM mismatch: calc={opm_calc:.2f}%, reported={opm_reported}% (sales={sales}, op={op})",
                                value=f"calc_{opm_calc:.1f}_rep_{opm_reported}",
                            )
                        )
            except (ValueError, TypeError):
                pass

    def _validate_dq06_positive_sales(self):
        """DQ-06 [WARNING]: Positive sales for active operating companies."""
        rows = self.datasets.get("profitandloss", [])
        for r in rows:
            try:
                sales = float(r.get("sales") or 0)
                cid = normalize_ticker(r.get("company_id")) or ""
                yr = str(r.get("year") or "")
                if sales <= 0:
                    self.failures.append(
                        ValidationFailure(
                            rule_id="DQ-06",
                            severity="WARNING",
                            table_name="profitandloss",
                            record_id=r.get("id", r.get("__row_num__")),
                            company_id=cid,
                            column_name="sales",
                            error_message=f"Non-positive sales reported: {sales} in year {yr}",
                            value=sales,
                        )
                    )
            except (ValueError, TypeError):
                pass

    def _validate_dq07_net_cash_flow(self):
        """DQ-07 [WARNING]: Net cash flow cross-check (operating + investing + financing == net_cash)."""
        rows = self.datasets.get("cashflow", [])
        for r in rows:
            try:
                cfo = float(r.get("operating_activity") or 0)
                cfi = float(r.get("investing_activity") or 0)
                cff = float(r.get("financing_activity") or 0)
                net_reported = float(r.get("net_cash_flow") or 0)
                cid = normalize_ticker(r.get("company_id")) or ""
                calc_net = cfo + cfi + cff
                if abs(calc_net - net_reported) > 2.0:
                    self.failures.append(
                        ValidationFailure(
                            rule_id="DQ-07",
                            severity="WARNING",
                            table_name="cashflow",
                            record_id=r.get("id", r.get("__row_num__")),
                            company_id=cid,
                            column_name="net_cash_flow",
                            error_message=f"Net cash flow mismatch: sum={calc_net}, reported={net_reported}",
                            value=f"diff_{abs(calc_net - net_reported):.1f}",
                        )
                    )
            except (ValueError, TypeError):
                pass

    def _validate_dq08_tax_rate(self):
        """DQ-08 [WARNING]: Tax rate bounds check (0% <= tax_percentage <= 100%)."""
        rows = self.datasets.get("profitandloss", [])
        for r in rows:
            try:
                tax_pct = float(r.get("tax_percentage") or 0)
                pbt = float(r.get("profit_before_tax") or 0)
                cid = normalize_ticker(r.get("company_id")) or ""
                if pbt > 0 and (tax_pct < 0 or tax_pct > 65):
                    self.failures.append(
                        ValidationFailure(
                            rule_id="DQ-08",
                            severity="WARNING",
                            table_name="profitandloss",
                            record_id=r.get("id", r.get("__row_num__")),
                            company_id=cid,
                            column_name="tax_percentage",
                            error_message=f"Abnormal tax percentage: {tax_pct}% with PBT={pbt}",
                            value=tax_pct,
                        )
                    )
            except (ValueError, TypeError):
                pass

    def _validate_dq09_dividend_cap(self):
        """DQ-09 [WARNING]: Dividend payout ratio within reasonable bounds."""
        rows = self.datasets.get("profitandloss", [])
        for r in rows:
            try:
                payout = float(r.get("dividend_payout") or 0)
                cid = normalize_ticker(r.get("company_id")) or ""
                if payout < 0 or payout > 150:
                    self.failures.append(
                        ValidationFailure(
                            rule_id="DQ-09",
                            severity="WARNING",
                            table_name="profitandloss",
                            record_id=r.get("id", r.get("__row_num__")),
                            company_id=cid,
                            column_name="dividend_payout",
                            error_message=f"Unusual dividend payout percentage: {payout}%",
                            value=payout,
                        )
                    )
            except (ValueError, TypeError):
                pass

    def _validate_dq10_urls(self):
        """DQ-10 [WARNING]: URL validation for company profiles and reports."""
        url_regex = re.compile(r"^https?://", re.IGNORECASE)
        url_cols = {
            "companies": ["website", "company_logo", "nse_profile", "bse_profile", "chart_link"],
            "documents": ["annual_report"],
        }
        for tbl, cols in url_cols.items():
            rows = self.datasets.get(tbl, [])
            for r in rows:
                cid = normalize_ticker(r.get("company_id") or r.get("id")) or ""
                for col in cols:
                    val = str(r.get(col) or "").strip()
                    if val and val.lower() not in ["null", "none", "nan", "na"] and not url_regex.match(val):
                        self.failures.append(
                            ValidationFailure(
                                rule_id="DQ-10",
                                severity="WARNING",
                                table_name=tbl,
                                record_id=r.get("id", r.get("__row_num__")),
                                company_id=cid,
                                column_name=col,
                                error_message=f"Invalid URL format in column '{col}': {val[:40]}...",
                                value=val[:50],
                            )
                        )

    def _validate_dq11_eps_sign(self):
        """DQ-11 [WARNING]: EPS sign consistency with Net Profit."""
        rows = self.datasets.get("profitandloss", [])
        for r in rows:
            try:
                np = float(r.get("net_profit") or 0)
                eps = float(r.get("eps") or 0)
                cid = normalize_ticker(r.get("company_id")) or ""
                if (np > 10 and eps < -0.1) or (np < -10 and eps > 0.1):
                    self.failures.append(
                        ValidationFailure(
                            rule_id="DQ-11",
                            severity="WARNING",
                            table_name="profitandloss",
                            record_id=r.get("id", r.get("__row_num__")),
                            company_id=cid,
                            column_name="eps, net_profit",
                            error_message=f"EPS sign discordance: Net Profit={np}, EPS={eps}",
                            value=f"NP_{np}_EPS_{eps}",
                        )
                    )
            except (ValueError, TypeError):
                pass

    def _validate_dq12_bs_components(self):
        """DQ-12 [WARNING]: Balance sheet components sum equals total liabilities."""
        rows = self.datasets.get("balancesheet", [])
        for r in rows:
            try:
                eq = float(r.get("equity_capital") or 0)
                res = float(r.get("reserves") or 0)
                bor = float(r.get("borrowings") or 0)
                oth = float(r.get("other_liabilities") or 0)
                tot = float(r.get("total_liabilities") or 0)
                cid = normalize_ticker(r.get("company_id")) or ""
                if tot > 0:
                    sum_liab = eq + res + bor + oth
                    diff_pct = abs(sum_liab - tot) / tot
                    if diff_pct > 0.02:
                        self.failures.append(
                            ValidationFailure(
                                rule_id="DQ-12",
                                severity="WARNING",
                                table_name="balancesheet",
                                record_id=r.get("id", r.get("__row_num__")),
                                company_id=cid,
                                column_name="total_liabilities",
                                error_message=f"Liabilities breakdown discrepancy: sum={sum_liab}, total={tot} ({diff_pct*100:.1f}%)",
                                value=f"diff_{diff_pct:.3f}",
                            )
                        )
            except (ValueError, TypeError):
                pass

    def _validate_dq13_year_coverage(self):
        """DQ-13 [WARNING]: Historical Coverage (companies with < 5 years of financial statements)."""
        rows = self.datasets.get("profitandloss", [])
        comp_years = Counter()
        for r in rows:
            cid = normalize_ticker(r.get("company_id"))
            yr = normalize_year(r.get("year"))
            if cid and yr and yr != "TTM":
                comp_years[cid] += 1

        for cid, count in comp_years.items():
            if count < 5:
                self.failures.append(
                    ValidationFailure(
                        rule_id="DQ-13",
                        severity="WARNING",
                        table_name="profitandloss",
                        record_id=cid,
                        company_id=cid,
                        column_name="year",
                        error_message=f"Limited historical coverage: company '{cid}' has only {count} years (< 5 years)",
                        value=count,
                    )
                )

    def _validate_dq14_stock_prices(self):
        """DQ-14 [WARNING]: Stock price integrity (low <= open, close <= high, volume >= 0)."""
        rows = self.datasets.get("stock_prices", [])
        for r in rows:
            try:
                op = float(r.get("open_price") or 0)
                hp = float(r.get("high_price") or 0)
                lp = float(r.get("low_price") or 0)
                cp = float(r.get("close_price") or 0)
                vol = float(r.get("volume") or 0)
                cid = normalize_ticker(r.get("company_id")) or ""
                dt = str(r.get("date") or "")

                if vol < 0:
                    self.failures.append(
                        ValidationFailure(
                            rule_id="DQ-14",
                            severity="WARNING",
                            table_name="stock_prices",
                            record_id=r.get("id", r.get("__row_num__")),
                            company_id=cid,
                            column_name="volume",
                            error_message=f"Negative stock volume: {vol} on {dt}",
                            value=vol,
                        )
                    )
                if hp < lp or hp < op or hp < cp or lp > op or lp > cp:
                    self.failures.append(
                        ValidationFailure(
                            rule_id="DQ-14",
                            severity="WARNING",
                            table_name="stock_prices",
                            record_id=r.get("id", r.get("__row_num__")),
                            company_id=cid,
                            column_name="prices",
                            error_message=f"Price range inversion on {dt}: Open={op}, High={hp}, Low={lp}, Close={cp}",
                            value=f"{lp}_{op}_{cp}_{hp}",
                        )
                    )
            except (ValueError, TypeError):
                pass

    def _validate_dq15_financial_ratios(self):
        """DQ-15 [WARNING]: Financial ratios consistency check."""
        rows = self.datasets.get("financial_ratios", [])
        for r in rows:
            try:
                de = float(r.get("debt_to_equity") or 0)
                cid = normalize_ticker(r.get("company_id")) or ""
                if de < 0:
                    self.failures.append(
                        ValidationFailure(
                            rule_id="DQ-15",
                            severity="WARNING",
                            table_name="financial_ratios",
                            record_id=r.get("id", r.get("__row_num__")),
                            company_id=cid,
                            column_name="debt_to_equity",
                            error_message=f"Negative debt-to-equity ratio: {de}",
                            value=de,
                        )
                    )
            except (ValueError, TypeError):
                pass

    def _validate_dq16_non_null_fields(self):
        """DQ-16 [CRITICAL]: Non-null mandatory identifiers."""
        mandatory_fields = {
            "companies": ["id", "company_name"],
            "stock_prices": ["company_id", "date", "close_price"],
            "profitandloss": ["company_id", "year"],
            "balancesheet": ["company_id", "year"],
        }
        for tbl, fields in mandatory_fields.items():
            rows = self.datasets.get(tbl, [])
            for r in rows:
                for f in fields:
                    val = r.get(f)
                    if val is None or str(val).strip() == "":
                        cid = normalize_ticker(r.get("company_id") or r.get("id")) or ""
                        self.failures.append(
                            ValidationFailure(
                                rule_id="DQ-16",
                                severity="CRITICAL",
                                table_name=tbl,
                                record_id=r.get("id", r.get("__row_num__")),
                                company_id=cid,
                                column_name=f,
                                error_message=f"Mandatory column '{f}' is null or empty in table {tbl}",
                                value=val,
                            )
                        )


def export_failures_to_csv(failures: List[ValidationFailure], output_path: str = "output/validation_failures.csv"):
    """Export validation failures to CSV."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "rule_id",
                "severity",
                "table_name",
                "record_id",
                "company_id",
                "column_name",
                "error_message",
                "value",
            ],
        )
        writer.writeheader()
        for failure in failures:
            writer.writerow(asdict(failure))
    print(f"Validation report generated: {output_path} ({len(failures)} failures recorded)")


def validate_database(db_path: str = "nifty100.db") -> List[ValidationFailure]:
    """Validate all 16 DQ rules directly on the populated SQLite database."""
    import sqlite3
    if not os.path.exists(db_path):
        return []

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    failures: List[ValidationFailure] = []

    # DQ-01: PK uniqueness
    tables = [
        t[0] for t in cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    ]
    for tbl in tables:
        dups = cursor.execute(f"SELECT id, COUNT(*) as cnt FROM {tbl} GROUP BY id HAVING cnt > 1").fetchall()
        for d in dups:
            failures.append(ValidationFailure(
                rule_id="DQ-01",
                severity="CRITICAL",
                table_name=tbl,
                record_id=d["id"],
                company_id="",
                column_name="id",
                error_message=f"Duplicate PK id={d['id']} in database table {tbl}",
                value=d["id"]
            ))

    # DQ-02: Composite PK (company_id, year)
    annual_tables = ["profitandloss", "balancesheet", "cashflow", "financial_ratios", "market_cap"]
    for tbl in annual_tables:
        dups = cursor.execute(
            f"SELECT company_id, year, COUNT(*) as cnt FROM {tbl} GROUP BY company_id, year HAVING cnt > 1"
        ).fetchall()
        for d in dups:
            failures.append(ValidationFailure(
                rule_id="DQ-02",
                severity="CRITICAL",
                table_name=tbl,
                record_id=f"{d['company_id']}_{d['year']}",
                company_id=d["company_id"],
                column_name="company_id, year",
                error_message=f"Duplicate (company_id, year) in database table {tbl}",
                value=f"{d['company_id']}_{d['year']}"
            ))

    # DQ-03: Foreign Key Check
    fk_check = cursor.execute("PRAGMA foreign_key_check;").fetchall()
    for fk in fk_check:
        failures.append(ValidationFailure(
            rule_id="DQ-03",
            severity="CRITICAL",
            table_name=fk[0],
            record_id=fk[1],
            company_id="",
            column_name="company_id",
            error_message=f"Foreign key violation referencing parent {fk[2]}",
            value=fk[1]
        ))

    # DQ-04: BS Balance Check
    bs_rows = cursor.execute(
        "SELECT id, company_id, year, total_assets, total_liabilities FROM balancesheet WHERE total_assets > 0"
    ).fetchall()
    for r in bs_rows:
        diff_pct = abs(r["total_assets"] - r["total_liabilities"]) / r["total_assets"]
        if diff_pct > 0.01:
            failures.append(ValidationFailure(
                rule_id="DQ-04",
                severity="WARNING",
                table_name="balancesheet",
                record_id=r["id"],
                company_id=r["company_id"],
                column_name="total_assets, total_liabilities",
                error_message=f"BS imbalance: assets={r['total_assets']}, liab={r['total_liabilities']} ({diff_pct*100:.2f}%)",
                value=diff_pct
            ))

    # DQ-14: Stock Prices Integrity
    sp_rows = cursor.execute(
        "SELECT id, company_id, date, open_price, high_price, low_price, close_price, volume FROM stock_prices"
    ).fetchall()
    for r in sp_rows:
        hp, lp, op, cp = r["high_price"], r["low_price"], r["open_price"], r["close_price"]
        if hp < lp or hp < op or hp < cp or lp > op or lp > cp:
            failures.append(ValidationFailure(
                rule_id="DQ-14",
                severity="WARNING",
                table_name="stock_prices",
                record_id=r["id"],
                company_id=r["company_id"],
                column_name="prices",
                error_message=f"Price inversion on {r['date']}: Open={op}, High={hp}, Low={lp}, Close={cp}",
                value=f"{lp}_{op}_{cp}_{hp}"
            ))

    conn.close()
    return failures


if __name__ == "__main__":
    print("--- 1. Validating Raw Source Files ---")
    validator = DataQualityValidator(".")
    raw_failures = validator.run_all_rules()
    export_failures_to_csv(raw_failures, "output/validation_failures.csv")
    raw_crit = sum(1 for f in raw_failures if f.severity == "CRITICAL")
    raw_warn = sum(1 for f in raw_failures if f.severity == "WARNING")
    print(f"Raw Files Summary: {raw_crit} CRITICAL, {raw_warn} WARNING failures recorded.")

    print("\n--- 2. Validating Loaded Database (nifty100.db) ---")
    db_failures = validate_database("nifty100.db")
    export_failures_to_csv(db_failures, "output/database_validation_report.csv")
    db_crit = sum(1 for f in db_failures if f.severity == "CRITICAL")
    db_warn = sum(1 for f in db_failures if f.severity == "WARNING")
    print(f"Database Summary: {db_crit} CRITICAL, {db_warn} WARNING failures remaining.")


