"""Evidence-based pros and cons generated from annual company fundamentals."""

import csv
import logging
import os
import re
import sqlite3
import sys
from typing import Dict, List, Optional, Sequence, Tuple

_WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

logger = logging.getLogger(__name__)
OUTPUT_DIR = os.path.join(_WORKSPACE_ROOT, "output")

PRO_TEXT = {
    1: "Consistently high return on equity above 20% demonstrates exceptional capital efficiency",
    2: "Strong free cash flow generation over 5 years signals healthy business fundamentals",
    3: "Debt-free balance sheet provides financial flexibility and eliminates interest burden",
    4: "Revenue growing at above 15% CAGR over 5 years reflects strong business momentum",
    5: "Operating profit margin above 25% indicates strong pricing power and cost discipline",
    6: "Net profit compounding at above 20% over 5 years creates significant shareholder value",
    7: "Very high interest coverage ratio reflects negligible financial stress from debt servicing",
    8: "Consistent dividend yield above 2% backed by positive free cash flow",
    9: "Earnings per share growing above 15% CAGR indicates strong earnings quality and compounding",
    10: "Return on equity improving for 3 consecutive years shows strengthening business quality",
    11: "Revenue growing slower than profits shows improving operating leverage and scale benefits",
    12: "Growing asset base funded by internal accruals reflects self-sustaining growth",
}
CON_TEXT = {
    1: "Debt-to-equity ratio of {value:.2f} is elevated for a non-financial company and warrants monitoring",
    2: "Free cash flow negative for 3 consecutive years raises concern about cash generation quality",
    3: "Operating margins declining for 3 consecutive years suggest pricing or cost pressure",
    4: "Company reported a net loss in the most recent financial year",
    5: "Revenue contraction over 2 consecutive years indicates demand weakness or market share loss",
    6: "Interest coverage ratio below 1.5x indicates the company is at risk of not meeting its debt obligations",
    7: "Dividend payout ratio above 100% means the company is paying dividends from reserves, which is unsustainable",
    8: "Rising debt-to-equity ratio over 3 years suggests increasing financial leverage risk",
    9: "Earnings per share declining for 3 consecutive years reflects deteriorating profitability",
    10: "Return on capital employed below 10% suggests the business is not generating sufficient returns on invested capital",
    11: "Net debt exceeding 3 times EBITDA is a high leverage ratio and limits financial flexibility",
    12: "Revenue growing at below 5% over 5 years lags inflation and suggests limited business momentum",
}
YEAR_RE = re.compile(r"(\d{4})")


def _year_number(value: str) -> int:
    match = YEAR_RE.search(value or "")
    return int(match.group(1)) if match else -1


def _confidence(margin: float = 0.0, base: float = 68.0, scale: float = 1.0) -> int:
    """Map distance from a rule threshold to a bounded 0-100 confidence score."""
    return max(0, min(99, round(base + max(0.0, margin) * scale)))


def _consecutive(rows: Sequence[Dict[str, object]], length: int) -> bool:
    if len(rows) < length:
        return False
    years = [_year_number(str(row["year"])) for row in rows[-length:]]
    return all(year >= 0 for year in years) and all(
        years[index] - years[index - 1] == 1 for index in range(1, len(years))
    )


def _present(value: object) -> bool:
    return value is not None


def _evaluate(company: Dict[str, object], rows: List[Dict[str, object]]) -> List[Tuple[str, int, str, int]]:
    if not rows:
        return []
    latest = rows[-1]
    pros: List[Tuple[str, int, str, int]] = []
    cons: List[Tuple[str, int, str, int]] = []

    def pro(rule: int, condition: bool, confidence: int) -> None:
        if condition and confidence > 60:
            pros.append(("pro", rule, PRO_TEXT[rule], confidence))

    def con(rule: int, condition: bool, confidence: int, value: Optional[float] = None) -> None:
        if condition and confidence > 60:
            text = CON_TEXT[rule].format(value=value) if rule == 1 and value is not None else CON_TEXT[rule]
            cons.append(("con", rule, text, confidence))

    recent3 = rows[-3:]
    recent4 = rows[-4:]
    recent5 = rows[-5:]
    roe_values = [row["roe"] for row in recent3]
    roe_streak = _consecutive(rows, 3) and all(_present(value) and float(value) > 20 for value in roe_values)
    roe_avg = sum(float(value) for value in roe_values if _present(value)) / 3 if all(_present(v) for v in roe_values) else 20
    pro(1, roe_streak, _confidence(roe_avg - 20, 72, 1.3))

    fcf_streak = _consecutive(rows, 5) and all(_present(row["fcf"]) and float(row["fcf"]) > 0 for row in recent5)
    pro(2, fcf_streak, _confidence(max(0, sum(float(row["fcf"] or 0) for row in recent5) / 5), 75, 0.001))

    de = latest["de"]
    borrowings = latest["borrowings"]
    debt_free = (de is not None and float(de) == 0.0) or (borrowings is not None and float(borrowings) == 0.0)
    pro(3, debt_free, 94)

    rev_cagr = latest["rev_cagr"]
    pro(4, rev_cagr is not None and float(rev_cagr) > 15, _confidence(float(rev_cagr or 15) - 15, 70, 1.0))
    opm = latest["opm"]
    pro(5, opm is not None and float(opm) > 25, _confidence(float(opm or 25) - 25, 70, 0.8))
    pat_cagr = latest["pat_cagr"]
    pro(6, pat_cagr is not None and float(pat_cagr) > 20, _confidence(float(pat_cagr or 20) - 20, 70, 0.8))
    icr = latest["icr"]
    pro(7, debt_free or (icr is not None and float(icr) > 10), 92 if debt_free else _confidence(float(icr or 10) - 10, 70, 0.8))

    dividend_yield = latest["dividend_yield"]
    pro(8, dividend_yield is not None and float(dividend_yield) > 2 and latest["fcf"] is not None and float(latest["fcf"]) > 0,
        _confidence(float(dividend_yield or 2) - 2, 70, 2.0))
    eps_cagr = latest["eps_cagr"]
    pro(9, eps_cagr is not None and float(eps_cagr) > 15, _confidence(float(eps_cagr or 15) - 15, 70, 1.0))

    rising_roe = _consecutive(rows, 4) and all(
        _present(recent4[index]["roe"]) and _present(recent4[index + 1]["roe"])
        and float(recent4[index + 1]["roe"]) > float(recent4[index]["roe"])
        for index in range(3)
    )
    pro(10, rising_roe, 78)

    pro(11, rev_cagr is not None and pat_cagr is not None and float(pat_cagr) > float(rev_cagr),
        _confidence(float(pat_cagr or 0) - float(rev_cagr or 0), 68, 0.8))

    asset_rows = [row for row in rows if _present(row["assets"]) and _present(row["borrowings"])]
    asset_trend = asset_rows[-3:]
    assets_with_deleveraging = _consecutive(asset_trend, 3) and all(
        float(asset_trend[index + 1]["assets"]) > float(asset_trend[index]["assets"])
        and float(asset_trend[index + 1]["borrowings"]) < float(asset_trend[index]["borrowings"])
        for index in range(2)
    )
    pro(12, assets_with_deleveraging, 78)

    financial = company["sector"] == "Financials"
    con(1, not financial and de is not None and float(de) > 2,
        _confidence(float(de or 2) - 2, 70, 4.0), float(de) if de is not None else None)
    negative_fcf = _consecutive(rows, 3) and all(
        _present(row["fcf"]) and float(row["fcf"]) < 0 for row in rows[-3:]
    )
    con(2, negative_fcf, 82)
    declining_opm = _consecutive(rows, 4) and all(
        _present(recent4[index]["opm"]) and _present(recent4[index + 1]["opm"])
        and float(recent4[index + 1]["opm"]) < float(recent4[index]["opm"])
        for index in range(3)
    )
    con(3, declining_opm, 80)
    net_profit = latest["net_profit"]
    con(4, net_profit is not None and float(net_profit) < 0, _confidence(abs(float(net_profit or 0)), 75, 0.001))

    sales = [row["sales"] for row in recent3]
    revenue_falling = _consecutive(rows, 3) and all(_present(value) for value in sales) and (
        float(sales[0]) > float(sales[1]) > float(sales[2])
    )
    con(5, revenue_falling, 78)
    con(6, icr is not None and float(icr) < 1.5, _confidence(1.5 - float(icr or 1.5), 70, 8.0))
    payout = latest["payout"]
    con(7, payout is not None and float(payout) > 100, _confidence(float(payout or 100) - 100, 70, 0.5))

    rising_de = _consecutive(rows, 4) and all(
        _present(recent4[index]["de"]) and _present(recent4[index + 1]["de"])
        and float(recent4[index + 1]["de"]) > float(recent4[index]["de"])
        for index in range(3)
    )
    con(8, rising_de, 78)
    declining_eps = _consecutive(rows, 4) and all(
        _present(recent4[index]["eps"]) and _present(recent4[index + 1]["eps"])
        and float(recent4[index + 1]["eps"]) < float(recent4[index]["eps"])
        for index in range(3)
    )
    con(9, declining_eps, 78)
    roce = latest["roce"]
    con(10, roce is not None and float(roce) < 10, _confidence(10 - float(roce or 10), 70, 1.5))

    net_debt = None
    if latest["borrowings"] is not None:
        net_debt = float(latest["borrowings"]) - float(latest["investments"] or 0)
    ebitda = None
    if latest["operating_profit"] is not None:
        ebitda = float(latest["operating_profit"]) + float(latest["depreciation"] or 0)
    leverage = net_debt / ebitda if ebitda is not None and ebitda > 0 else None
    con(11, leverage is not None and leverage > 3, _confidence(float(leverage or 3) - 3, 70, 5.0))
    con(12, rev_cagr is not None and float(rev_cagr) < 5, _confidence(5 - float(rev_cagr or 5), 70, 1.2))
    return pros + cons


def generate_pros_cons(
    db_path: Optional[str] = None, output_dir: Optional[str] = None
) -> Tuple[int, int, int]:
    """Evaluate all configured rules and write CSV outputs and coverage exceptions."""
    db_path = db_path or os.getenv("DB_PATH", os.path.join(_WORKSPACE_ROOT, "nifty100.db"))
    output_dir = output_dir or OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        company_rows = connection.execute(
            """SELECT c.id, c.company_name, COALESCE(s.broad_sector, '') AS sector
               FROM companies c LEFT JOIN sectors s ON s.company_id = c.id ORDER BY c.id"""
        ).fetchall()
        data_rows = connection.execute(
            """
            SELECT p.company_id, p.year, p.sales, p.net_profit, p.operating_profit,
                   p.depreciation, p.eps, p.dividend_payout, b.borrowings,
                   b.equity_capital, b.reserves, b.total_assets,
                   b.investments, fr.return_on_equity_pct AS roe,
                   fr.return_on_capital_employed_pct AS roce,
                   fr.debt_to_equity AS de, fr.interest_coverage AS icr,
                   fr.free_cash_flow_cr AS fcf, fr.revenue_cagr_5yr AS rev_cagr,
                   fr.pat_cagr_5yr AS pat_cagr, fr.eps_cagr_5yr AS eps_cagr,
                   fr.operating_profit_margin_pct AS opm,
                   fr.dividend_payout_ratio_pct AS payout,
                   mc.dividend_yield_pct AS dividend_yield
            FROM profitandloss p
            LEFT JOIN balancesheet b ON b.company_id = p.company_id AND b.year = p.year
            LEFT JOIN financial_ratios fr ON fr.company_id = p.company_id AND fr.year = p.year
            LEFT JOIN market_cap mc ON mc.company_id = p.company_id AND mc.year = p.year
            WHERE p.year != 'TTM'
            ORDER BY p.company_id, p.id
            """
        ).fetchall()
    finally:
        connection.close()

    histories: Dict[str, List[Dict[str, object]]] = {}
    for row in data_rows:
        history_row = dict(row)
        history_row["assets"] = history_row.pop("total_assets")
        history_row["borrowings"] = history_row["borrowings"]
        histories.setdefault(str(row["company_id"]), []).append(history_row)

    results: List[Tuple[str, str, int, str, int]] = []
    uncovered: List[Tuple[str, str, int, int]] = []
    for company in company_rows:
        cid = str(company["id"])
        signals = _evaluate(dict(company), histories.get(cid, []))
        pro_count = sum(signal[0] == "pro" for signal in signals)
        con_count = sum(signal[0] == "con" for signal in signals)
        if not pro_count or not con_count:
            uncovered.append((cid, str(company["company_name"]), pro_count, con_count))
        for signal_type, rule_id, text, confidence in signals:
            if confidence > 60:
                results.append((cid, signal_type, rule_id, text, confidence))

    with open(os.path.join(output_dir, "pros_cons_generated.csv"), "w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["company_id", "type", "rule_id", "text", "confidence_pct"])
        writer.writerows(results)
    with open(os.path.join(output_dir, "pros_cons_coverage.csv"), "w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["company_id", "company_name", "pro_count", "con_count"])
        writer.writerows(uncovered)
    if uncovered:
        logger.warning(
            "%d of %d companies do not have at least one generated pro and one con; see pros_cons_coverage.csv",
            len(uncovered), len(company_rows),
        )
    return len(company_rows), len(results), len(uncovered)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    generate_pros_cons()
