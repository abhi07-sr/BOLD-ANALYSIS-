"""Cash Flow KPIs and Capital Allocation 8-Pattern Classifier (Day 11)."""

import csv
import logging
import os
import re
import sqlite3
import sys
from typing import Dict, List, Optional, Tuple

import pandas as pd

_WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

from src.analytics.cagr import compute_cagr

logger = logging.getLogger(__name__)
DB_PATH = os.getenv("DB_PATH", os.path.join(_WORKSPACE_ROOT, "nifty100.db"))


def compute_free_cash_flow(
    operating_activity: Optional[float], investing_activity: Optional[float]
) -> Optional[float]:
    """Free Cash Flow: operating_activity + investing_activity.

    Note: In Indian accounting format, investing_activity is usually negative (cash outflow for CapEx).
    Negative FCF values are valid and returned as calculated.
    """
    if operating_activity is None or investing_activity is None:
        return None
    return round(float(operating_activity) + float(investing_activity), 2)


def compute_cfo_quality_score(
    cfo_history: List[float], pat_history: List[float]
) -> Tuple[Optional[float], str]:
    """CFO Quality Score: CFO / PAT ratio averaged over available years (up to 5 years).

    Quality Tiers:
    - > 1.0: "High Quality" (Strong cash conversion, conservative accounting)
    - 0.5 - 1.0: "Moderate"
    - < 0.5: "Accrual Risk" (Earnings not translating into cash flow)

    Returns:
        Tuple[Optional[float], str]: (avg_ratio, quality_label)
    """
    if not cfo_history or not pat_history:
        return None, "Insufficient Data"

    valid_pairs = [
        (c, p) for c, p in zip(cfo_history, pat_history) if p is not None and p > 0 and c is not None
    ]
    if not valid_pairs:
        return None, "Undefined"

    ratios = [c / p for c, p in valid_pairs]
    avg_ratio = round(sum(ratios) / len(ratios), 2)

    if avg_ratio > 1.0:
        label = "High Quality"
    elif avg_ratio >= 0.5:
        label = "Moderate"
    else:
        label = "Accrual Risk"

    return avg_ratio, label


def compute_capex_intensity(
    investing_activity: Optional[float], sales: Optional[float]
) -> Tuple[Optional[float], str]:
    """CapEx Intensity: abs(investing_activity) / sales * 100.

    Classification:
    - < 3%: "Asset Light" (e.g. IT services, consulting)
    - 3% - 8%: "Moderate"
    - > 8%: "Capital Intensive" (e.g. Manufacturing, Utilities, Telecom)

    Returns:
        Tuple[Optional[float], str]: (intensity_pct, intensity_label)
    """
    if investing_activity is None or sales is None or sales <= 0:
        return None, "Unknown"

    capex = abs(float(investing_activity))
    intensity = round((capex / sales) * 100.0, 2)

    if intensity < 3.0:
        label = "Asset Light"
    elif intensity <= 8.0:
        label = "Moderate"
    else:
        label = "Capital Intensive"

    return intensity, label


def compute_fcf_conversion(
    free_cash_flow: Optional[float], operating_profit: Optional[float]
) -> Optional[float]:
    """FCF Conversion Rate: (FCF / operating_profit) * 100.

    Returns None if operating_profit <= 0 or inputs are missing.
    """
    if free_cash_flow is None or operating_profit is None or operating_profit <= 0:
        return None
    return round((free_cash_flow / operating_profit) * 100.0, 2)


def classify_capital_allocation(
    cfo: Optional[float],
    cfi: Optional[float],
    cff: Optional[float],
    cfo_pat_ratio: Optional[float] = None,
) -> Tuple[str, str, str, str]:
    """Classify company-year into 1 of 8 Capital Allocation patterns based on sign of (CFO, CFI, CFF).

    Pattern Mapping:
    - (+, -, -): "Reinvestor" (or "Shareholder Returns" if cfo_pat_ratio > 1.2)
    - (+, +, -): "Liquidating Assets"
    - (-, +, +): "Distress Signal"
    - (-, -, +): "Growth Funded by Debt"
    - (+, +, +): "Cash Accumulator"
    - (-, -, -): "Pre-Revenue"
    - (+, -, +): "Mixed"
    - (-, +, -): "Restructuring"

    Returns:
        Tuple[str, str, str, str]: (cfo_sign, cfi_sign, cff_sign, pattern_label)
    """
    if cfo is None or cfi is None or cff is None:
        return "N/A", "N/A", "N/A", "Undefined"

    s_cfo = "+" if cfo >= 0 else "-"
    s_cfi = "+" if cfi >= 0 else "-"
    s_cff = "+" if cff >= 0 else "-"
    pattern = (s_cfo, s_cfi, s_cff)

    if pattern == ("+", "-", "-"):
        label = "Shareholder Returns" if (cfo_pat_ratio is not None and cfo_pat_ratio > 1.2) else "Reinvestor"
    elif pattern == ("+", "+", "-"):
        label = "Liquidating Assets"
    elif pattern == ("-", "+", "+"):
        label = "Distress Signal"
    elif pattern == ("-", "-", "+"):
        label = "Growth Funded by Debt"
    elif pattern == ("+", "+", "+"):
        label = "Cash Accumulator"
    elif pattern == ("-", "-", "-"):
        label = "Pre-Revenue"
    elif pattern == ("+", "-", "+"):
        label = "Mixed"
    else:
        label = "Restructuring"

    return s_cfo, s_cfi, s_cff, label


def generate_capital_allocation_report(
    db_path: str = "nifty100.db", output_path: str = "output/capital_allocation.csv"
):
    """Generate capital allocation 8-pattern classification CSV for all company-years."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    query = """
        SELECT cf.company_id, cf.year, cf.operating_activity, cf.investing_activity, cf.financing_activity,
               p.net_profit
        FROM cashflow cf
        LEFT JOIN profitandloss p ON cf.company_id = p.company_id AND cf.year = p.year
        ORDER BY cf.company_id, cf.year;
    """
    rows = cursor.execute(query).fetchall()
    conn.close()

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["company_id", "year", "cfo_sign", "cfi_sign", "cff_sign", "pattern_label"])

        for cid, yr, cfo, cfi, cff, pat in rows:
            cfo_pat = (cfo / pat) if (cfo is not None and pat is not None and pat > 0) else None
            s_cfo, s_cfi, s_cff, label = classify_capital_allocation(cfo, cfi, cff, cfo_pat)
            writer.writerow([cid, yr, s_cfo, s_cfi, s_cff, label])

    print(f"Capital allocation report generated: {output_path} ({len(rows)} records)")


def _year_number(value: str) -> int:
    match = re.search(r"(\d{4})", value or "")
    return int(match.group(1)) if match else -1


def _latest_fcf_cagr(rows: List[Dict[str, object]]) -> Optional[float]:
    valid = [row for row in rows if row["fcf"] is not None and _year_number(str(row["year"])) >= 0]
    valid = valid[-6:]
    if len(valid) != 6:
        return None
    years = [_year_number(str(row["year"])) for row in valid]
    if any(years[index] - years[index - 1] != 1 for index in range(1, len(years))):
        return None
    cagr, _ = compute_cagr(float(valid[0]["fcf"]), float(valid[-1]["fcf"]), 5)
    return cagr


def generate_cashflow_intelligence(
    db_path: Optional[str] = None, output_dir: Optional[str] = None
) -> Tuple[int, int, int]:
    """Generate company-level cash-flow classifications, alerts, and pattern summaries."""
    db_path = db_path or DB_PATH
    output_dir = output_dir or os.path.join(_WORKSPACE_ROOT, "output")
    os.makedirs(output_dir, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        companies = conn.execute(
            """
            SELECT c.id AS company_id, COALESCE(s.broad_sector, 'Unclassified') AS sector
            FROM companies c LEFT JOIN sectors s ON s.company_id = c.id
            ORDER BY c.id
            """
        ).fetchall()
        statement_rows = conn.execute(
            """
            SELECT cf.company_id, cf.year, cf.operating_activity AS cfo,
                   cf.investing_activity AS cfi, cf.financing_activity AS cff,
                   p.sales, p.net_profit, p.operating_profit,
                   b.borrowings,
                   (b.equity_capital + b.reserves) AS shareholders_equity,
                   (b.equity_capital + b.reserves + b.borrowings) AS total_capital,
                   b.other_liabilities, b.investments,
                   fr.debt_to_equity AS debt_to_equity
            FROM cashflow cf
            LEFT JOIN profitandloss p ON p.company_id = cf.company_id AND p.year = cf.year
            LEFT JOIN balancesheet b ON b.company_id = cf.company_id AND b.year = cf.year
            LEFT JOIN financial_ratios fr ON fr.company_id = cf.company_id AND fr.year = cf.year
            WHERE cf.year != 'TTM'
            ORDER BY cf.company_id, cf.id
            """
        ).fetchall()
        expected_keys = {
            (row[0], row[1]) for row in conn.execute("SELECT company_id, year FROM cashflow WHERE year != 'TTM'")
        }
        allocation_keys = set()
        allocation_path = os.path.join(output_dir, "capital_allocation.csv")
        if os.path.isfile(allocation_path):
            with open(allocation_path, newline="", encoding="utf-8") as stream:
                allocation_keys = {
                    (record.get("company_id"), record.get("year"))
                    for record in csv.DictReader(stream)
                }
        else:
            logger.warning("capital_allocation.csv is missing; writing a complete replacement")
        if allocation_keys != expected_keys:
            logger.warning(
                "capital allocation coverage differs from cashflow history: %d missing, %d unexpected",
                len(expected_keys - allocation_keys), len(allocation_keys - expected_keys),
            )
    finally:
        conn.close()

    histories: Dict[str, List[Dict[str, object]]] = {}
    for row in statement_rows:
        histories.setdefault(str(row["company_id"]), []).append(dict(row))

    pattern_names = (
        "Shareholder Returns", "Reinvestor", "Growth Funded by Debt", "Mixed",
        "Liquidating Assets", "Restructuring", "Distress Signal", "Pre-Revenue",
    )
    intelligence_rows: List[Dict[str, object]] = []
    distress_rows: List[Dict[str, object]] = []
    pattern_changes: List[Tuple[str, str, str, str, str]] = []

    for company in companies:
        cid = str(company["company_id"])
        history = histories.get(cid, [])
        if not history:
            continue
        latest = history[-1]
        pat_values = [
            row["net_profit"] for row in history[-5:]
        ]
        cfo_values = [row["cfo"] for row in history[-5:]]
        cfo_score, cfo_label = compute_cfo_quality_score(cfo_values, pat_values)
        capex_pct, capex_label = compute_capex_intensity(latest["cfi"], latest["sales"])
        latest_fcf = compute_free_cash_flow(latest["cfo"], latest["cfi"])
        fcf_conversion = compute_fcf_conversion(latest_fcf, latest["operating_profit"])
        fcf_values = [
            {**row, "fcf": compute_free_cash_flow(row["cfo"], row["cfi"])}
            for row in history
        ]
        fcf_cagr = _latest_fcf_cagr(fcf_values)

        latest_pat = latest["net_profit"]
        cfo_pat_ratio = (
            float(latest["cfo"]) / float(latest_pat)
            if latest["cfo"] is not None and latest_pat is not None and float(latest_pat) > 0
            else None
        )
        latest_pattern = classify_capital_allocation(
            latest["cfo"], latest["cfi"], latest["cff"], cfo_pat_ratio
        )[3]
        chronological = sorted(history, key=lambda row: (_year_number(str(row["year"])), str(row["year"])))
        prior_pattern = None
        prior_row = None
        for row in chronological:
            pat = row["net_profit"]
            row_cfo_pat = (
                float(row["cfo"]) / float(pat)
                if row["cfo"] is not None and pat is not None and float(pat) > 0
                else None
            )
            pattern = classify_capital_allocation(
                row["cfo"], row["cfi"], row["cff"], row_cfo_pat
            )[3]
            if prior_row and _year_number(str(row["year"])) - _year_number(str(prior_row["year"])) == 1:
                if pattern != prior_pattern:
                    pattern_changes.append((cid, str(prior_row["year"]), str(row["year"]), str(prior_pattern), pattern))
            prior_row, prior_pattern = row, pattern

        prior_borrowings = None
        if len(history) > 1:
            prior_borrowings = history[-2]["borrowings"]
        deleveraging = (
            latest["cff"] is not None and float(latest["cff"]) < 0
            and latest["borrowings"] is not None and prior_borrowings is not None
            and float(latest["borrowings"]) < float(prior_borrowings)
        )
        distress = (
            latest["cfo"] is not None and float(latest["cfo"]) < 0
            and latest["cff"] is not None and float(latest["cff"]) > 0
        )
        if distress:
            distress_rows.append({
                "company_id": cid, "cfo": latest["cfo"], "cff": latest["cff"],
                "latest_net_profit": latest["net_profit"],
            })
        intelligence_rows.append({
            "company_id": cid,
            "sector": company["sector"],
            "cfo_quality_score": cfo_score,
            "cfo_quality_label": cfo_label,
            "capex_intensity_pct": capex_pct,
            "capex_label": capex_label,
            "fcf_cagr_5yr": fcf_cagr,
            "fcf_conversion_pct": fcf_conversion,
            "distress_flag": distress,
            "deleveraging_flag": bool(deleveraging),
            "capital_allocation_label": latest_pattern,
        })

    columns = [
        "company_id", "sector", "cfo_quality_score", "cfo_quality_label",
        "capex_intensity_pct", "capex_label", "fcf_cagr_5yr", "fcf_conversion_pct",
        "distress_flag", "deleveraging_flag", "capital_allocation_label",
    ]
    pd.DataFrame(intelligence_rows, columns=columns).to_excel(
        os.path.join(output_dir, "cashflow_intelligence.xlsx"), index=False
    )
    with open(os.path.join(output_dir, "distress_alerts.csv"), "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["company_id", "cfo", "cff", "latest_net_profit"])
        writer.writeheader()
        writer.writerows(distress_rows)
    distribution = {name: 0 for name in pattern_names}
    for row in intelligence_rows:
        distribution[row["capital_allocation_label"]] = distribution.get(row["capital_allocation_label"], 0) + 1
    with open(os.path.join(output_dir, "capital_allocation_distribution.csv"), "w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["pattern_label", "company_count"])
        writer.writerows(distribution.items())
    with open(os.path.join(output_dir, "pattern_changes.csv"), "w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["company_id", "from_year", "to_year", "previous_pattern", "current_pattern"])
        writer.writerows(pattern_changes)
    if len(intelligence_rows) != len(companies):
        logger.warning(
            "Cashflow intelligence covers %d of %d companies; companies without cashflow data are omitted",
            len(intelligence_rows), len(companies),
        )
    return len(intelligence_rows), len(distress_rows), len(pattern_changes)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    generate_cashflow_intelligence()
