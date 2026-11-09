"""Parse CAGR and return metrics from the source analysis workbook."""

import csv
import glob
import logging
import os
import re
import sqlite3
import sys
from typing import Dict, Iterable, List, Optional, Tuple

from openpyxl import load_workbook

_WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

logger = logging.getLogger(__name__)
METRIC_FIELDS = (
    "compounded_sales_growth",
    "compounded_profit_growth",
    "stock_price_cagr",
    "roe",
)
VALUE_PATTERN = re.compile(r"(\d+)\s*Years?:?\s*([\d.]+)%", re.IGNORECASE)
OUTPUT_DIR = os.path.join(_WORKSPACE_ROOT, "output")


def _analysis_workbook(path: Optional[str] = None) -> str:
    if path:
        return path
    candidates = sorted(glob.glob(os.path.join(_WORKSPACE_ROOT, "*-analysis.xlsx")))
    if not candidates:
        raise FileNotFoundError("No *-analysis.xlsx source workbook found in the workspace")
    return candidates[-1]


def _read_analysis_rows(workbook_path: str) -> Iterable[Dict[str, object]]:
    workbook = load_workbook(workbook_path, read_only=True, data_only=True)
    worksheet = workbook[workbook.sheetnames[0]]
    all_rows = worksheet.iter_rows(values_only=True)
    headers = None
    rows = None
    for candidate in all_rows:
        if candidate and "company_id" in candidate:
            headers = candidate
            rows = all_rows
            break
    if headers is None or rows is None:
        workbook.close()
        raise ValueError(f"Analysis workbook has no company_id header: {workbook_path}")
    header_index = {str(value).strip(): index for index, value in enumerate(headers) if value}
    required = {"company_id", *METRIC_FIELDS}
    missing = required.difference(header_index)
    if missing:
        workbook.close()
        raise ValueError(f"Analysis workbook is missing columns: {', '.join(sorted(missing))}")
    result = []
    for row in rows:
        if not row or not row[header_index["company_id"]]:
            continue
        result.append({
            "company_id": str(row[header_index["company_id"]]).strip(),
            **{field: row[header_index[field]] for field in METRIC_FIELDS},
        })
    workbook.close()
    return result


def parse_analysis(
    workbook_path: Optional[str] = None,
    db_path: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> Tuple[int, int, int]:
    """Write parsed values, unmatched text, and material CAGR divergences.

    Ratio Engine cross-validation is available for 5-year sales and profit CAGR
    entries; other periods/metrics are retained without an unavailable comparison.
    """
    workbook_path = _analysis_workbook(workbook_path)
    output_dir = output_dir or OUTPUT_DIR
    db_path = db_path or os.getenv("DB_PATH", os.path.join(_WORKSPACE_ROOT, "nifty100.db"))
    os.makedirs(output_dir, exist_ok=True)

    parsed: List[Tuple[str, str, int, float]] = []
    failures: List[Tuple[str, str, str]] = []
    for row in _read_analysis_rows(workbook_path):
        for metric in METRIC_FIELDS:
            text = row.get(metric)
            match = VALUE_PATTERN.search(str(text)) if text is not None else None
            if match:
                parsed.append((row["company_id"], metric, int(match.group(1)), float(match.group(2))))
            else:
                failures.append((row["company_id"], metric, "" if text is None else str(text)))

    conn = sqlite3.connect(db_path)
    try:
        comparison_rows = conn.execute(
            """
            SELECT company_id, revenue_cagr_5yr, pat_cagr_5yr
            FROM financial_ratios
            WHERE year != 'TTM'
            ORDER BY company_id, id
            """
        ).fetchall()
    finally:
        conn.close()

    latest_ratios = {company_id: (revenue, profit) for company_id, revenue, profit in comparison_rows}
    divergences: List[Tuple[str, str, int, float, float, float]] = []
    ratio_metric = {
        "compounded_sales_growth": 0,
        "compounded_profit_growth": 1,
    }
    for company_id, metric, period, value in parsed:
        if period != 5 or metric not in ratio_metric:
            continue
        values = latest_ratios.get(company_id)
        computed = values[ratio_metric[metric]] if values else None
        if computed is not None and abs(value - float(computed)) > 5.0:
            divergences.append((
                company_id, metric, period, value, float(computed), round(abs(value - float(computed)), 2)
            ))

    with open(os.path.join(output_dir, "analysis_parsed.csv"), "w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["company_id", "metric_type", "period_years", "value_pct"])
        writer.writerows(parsed)
    with open(os.path.join(output_dir, "parse_failures.csv"), "w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["company_id", "metric_type", "source_text"])
        writer.writerows(failures)
    with open(os.path.join(output_dir, "cagr_divergences.csv"), "w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow([
            "company_id", "metric_type", "period_years", "parsed_value_pct",
            "ratio_engine_value_pct", "divergence_pct_points",
        ])
        writer.writerows(divergences)

    if failures:
        logger.warning("%d analysis entries did not match the required format", len(failures))
    if divergences:
        logger.warning("%d parsed 5-year CAGR values diverge by more than 5 points", len(divergences))
    return len(parsed), len(failures), len(divergences)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parse_analysis()
