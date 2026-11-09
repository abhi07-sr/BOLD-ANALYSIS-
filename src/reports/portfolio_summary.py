"""Generate a one-page-per-company portfolio PDF with KPI trend arrows."""

import os
import re
import sqlite3
import sys
from typing import Dict, List, Optional, Tuple

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

_WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

DB_PATH = os.getenv("DB_PATH", os.path.join(_WORKSPACE_ROOT, "nifty100.db"))
PAGE_WIDTH, PAGE_HEIGHT = A4
NAVY = colors.HexColor("#10243A")
METRICS = (
    ("Revenue", "sales", False, " Cr"),
    ("Net Profit", "net_profit", False, " Cr"),
    ("EPS", "eps", False, ""),
    ("ROE", "return_on_equity_pct", False, "%"),
    ("ROCE", "return_on_capital_employed_pct", False, "%"),
    ("Debt / Equity", "debt_to_equity", True, "x"),
)


def _year(value: str) -> int:
    match = re.search(r"(\d{4})", value or "")
    return int(match.group(1)) if match else -1


def _direction(current: Optional[float], previous: Optional[float], lower_is_better: bool) -> str:
    if current is None or previous is None:
        return "flat"
    if previous == 0:
        delta = 0 if current == 0 else (1 if current > 0 else -1)
    else:
        delta = (current - previous) / abs(previous)
    if abs(delta) <= 0.02:
        return "flat"
    improved = delta < 0 if lower_is_better else delta > 0
    return "up" if improved else "down"


def _draw_arrow(pdf: canvas.Canvas, x: float, y: float, direction: str) -> None:
    color = colors.HexColor("#17834A") if direction == "up" else (
        colors.HexColor("#B42318") if direction == "down" else colors.HexColor("#627184")
    )
    pdf.setStrokeColor(color)
    pdf.setFillColor(color)
    pdf.setLineWidth(2)
    if direction == "up":
        pdf.line(x, y - 6, x, y + 6)
        pdf.line(x, y + 6, x - 4, y + 2)
        pdf.line(x, y + 6, x + 4, y + 2)
    elif direction == "down":
        pdf.line(x, y + 6, x, y - 6)
        pdf.line(x, y - 6, x - 4, y - 2)
        pdf.line(x, y - 6, x + 4, y - 2)
    else:
        pdf.line(x - 6, y, x + 6, y)
        pdf.line(x + 6, y, x + 2, y + 4)
        pdf.line(x + 6, y, x + 2, y - 4)


def _fmt(value: object, suffix: str) -> str:
    if value is None:
        return "N/A"
    try:
        return f"{float(value):,.2f}{suffix}"
    except (TypeError, ValueError):
        return "N/A"


def generate_portfolio_summary(
    db_path: Optional[str] = None, output_path: Optional[str] = None
) -> int:
    """Create a portfolio PDF with a page for each available company."""
    db_path = db_path or DB_PATH
    output_path = output_path or os.path.join(_WORKSPACE_ROOT, "reports", "portfolio", "portfolio_summary.pdf")
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        company_rows = conn.execute(
            """
            SELECT c.id, c.company_name, COALESCE(s.broad_sector, 'Unclassified') AS sector
            FROM companies c LEFT JOIN sectors s ON s.company_id = c.id ORDER BY c.id
            """
        ).fetchall()
        statements = conn.execute(
            """
            SELECT c.company_id, c.year, p.sales, p.net_profit, p.eps,
                   fr.return_on_equity_pct, fr.return_on_capital_employed_pct, fr.debt_to_equity
            FROM cashflow c
            LEFT JOIN profitandloss p ON p.company_id = c.company_id AND p.year = c.year
            LEFT JOIN financial_ratios fr ON fr.company_id = c.company_id AND fr.year = c.year
            WHERE c.year != 'TTM'
            ORDER BY c.company_id, c.id
            """
        ).fetchall()
    finally:
        conn.close()
    histories: Dict[str, List[Dict[str, object]]] = {}
    for row in statements:
        histories.setdefault(str(row["company_id"]), []).append(dict(row))

    pdf = canvas.Canvas(output_path, pagesize=A4, pageCompression=1)
    pdf.setTitle("Nifty 100 Portfolio Summary")
    for company in company_rows:
        ticker = str(company["id"])
        rows = sorted(histories.get(ticker, []), key=lambda row: (_year(str(row["year"])), str(row["year"])))
        latest = rows[-1] if rows else {}
        previous = rows[-2] if len(rows) > 1 else {}
        pdf.setFillColor(NAVY)
        pdf.rect(0, PAGE_HEIGHT - 112, PAGE_WIDTH, 112, fill=1, stroke=0)
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 18)
        pdf.drawString(42, PAGE_HEIGHT - 48, str(company["company_name"])[:60])
        pdf.setFont("Helvetica", 10)
        pdf.drawString(43, PAGE_HEIGHT - 70, f"{ticker}  |  {company['sector']}  |  {latest.get('year', 'No annual data')}")
        pdf.setFillColor(colors.HexColor("#CBD5E1"))
        pdf.setFont("Helvetica", 8)
        pdf.drawString(43, PAGE_HEIGHT - 91, "Latest available financial KPIs and year-over-year trend")

        for index, (label, key, lower_is_better, suffix) in enumerate(METRICS):
            row, col = divmod(index, 2)
            x = 42 + col * 258
            y = PAGE_HEIGHT - 200 - row * 102
            value = latest.get(key)
            previous_value = previous.get(key)
            pdf.setFillColor(colors.HexColor("#F1F5F9"))
            pdf.roundRect(x, y - 48, 238, 70, 8, fill=1, stroke=0)
            pdf.setFillColor(colors.HexColor("#627184"))
            pdf.setFont("Helvetica", 9)
            pdf.drawString(x + 14, y + 3, label)
            pdf.setFillColor(NAVY)
            pdf.setFont("Helvetica-Bold", 15)
            pdf.drawString(x + 14, y - 24, _fmt(value, suffix))
            _draw_arrow(pdf, x + 214, y - 10, _direction(
                float(value) if value is not None else None,
                float(previous_value) if previous_value is not None else None,
                lower_is_better,
            ))
            pdf.setFillColor(colors.HexColor("#627184"))
            pdf.setFont("Helvetica", 7)
            pdf.drawString(x + 14, y - 39, f"Previous year: {_fmt(previous_value, suffix)}")

        pdf.setFillColor(colors.HexColor("#627184"))
        pdf.setFont("Helvetica", 8)
        pdf.drawString(42, 45, "Trend arrows: green = improving, red = declining, grey = within 2% or unavailable")
        pdf.drawRightString(PAGE_WIDTH - 42, 45, f"{ticker}")
        pdf.showPage()
    pdf.save()
    return len(company_rows)


if __name__ == "__main__":
    generate_portfolio_summary()
