"""Create two-page financial tearsheets for Nifty 100 companies."""

import csv
import io
import logging
import os
import re
import sqlite3
import sys
from typing import Dict, List, Optional, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

_WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

logger = logging.getLogger(__name__)
logging.getLogger("matplotlib.category").setLevel(logging.WARNING)
DB_PATH = os.getenv("DB_PATH", os.path.join(_WORKSPACE_ROOT, "nifty100.db"))
PAGE_WIDTH, PAGE_HEIGHT = A4
NAVY = colors.HexColor("#10243A")
GREEN = colors.HexColor("#17834A")
RED = colors.HexColor("#B42318")
MUTED = colors.HexColor("#627184")


def _records(db_path: str) -> Dict[str, Dict[str, object]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        companies = conn.execute(
            """
            SELECT c.id, c.company_name, COALESCE(s.broad_sector, 'Unclassified') AS sector
            FROM companies c LEFT JOIN sectors s ON s.company_id = c.id ORDER BY c.id
            """
        ).fetchall()
        pnl = conn.execute("SELECT * FROM profitandloss WHERE year != 'TTM' ORDER BY company_id, id").fetchall()
        balances = conn.execute("SELECT * FROM balancesheet WHERE year != 'TTM' ORDER BY company_id, id").fetchall()
        cashflows = conn.execute("SELECT * FROM cashflow WHERE year != 'TTM' ORDER BY company_id, id").fetchall()
        ratios = conn.execute("SELECT * FROM financial_ratios WHERE year != 'TTM' ORDER BY company_id, id").fetchall()
    finally:
        conn.close()
    data: Dict[str, Dict[str, object]] = {}
    for company in companies:
        cid = str(company["id"])
        data[cid] = {
            "company_id": cid, "company_name": company["company_name"], "sector": company["sector"],
            "pnl": [], "balances": {}, "cashflows": {}, "ratios": {},
        }
    for row in pnl:
        data[str(row["company_id"])]["pnl"].append(dict(row))
    for rows, key in ((balances, "balances"), (cashflows, "cashflows"), (ratios, "ratios")):
        for row in rows:
            data[str(row["company_id"])][key][str(row["year"])] = dict(row)
    return data


def _year(value: str) -> int:
    match = re.search(r"(\d{4})", value or "")
    return int(match.group(1)) if match else -1


def _chart_bytes(draw) -> io.BytesIO:
    buffer = io.BytesIO()
    figure = plt.figure(figsize=(6.2, 3.4), dpi=120)
    draw(figure)
    figure.tight_layout()
    figure.savefig(buffer, format="png", dpi=120, facecolor="white")
    plt.close(figure)
    buffer.seek(0)
    return buffer


def _history(data: Dict[str, object]) -> List[Dict[str, object]]:
    records = []
    for pnl in data["pnl"]:
        year = str(pnl["year"])
        record = dict(pnl)
        record.update(data["balances"].get(year, {}))
        record.update(data["cashflows"].get(year, {}))
        record.update(data["ratios"].get(year, {}))
        records.append(record)
    return sorted(records, key=lambda row: (_year(str(row["year"])), str(row["year"])))


def _draw_revenue_profit(figure, rows: List[Dict[str, object]]) -> None:
    recent = rows[-10:]
    labels = [str(row["year"])[-4:] for row in recent]
    for index, (field, title, color) in enumerate(
        (("sales", "Revenue", "#1976D2"), ("net_profit", "Net Profit", "#26A269"))
    ):
        axis = figure.add_subplot(1, 2, index + 1)
        values = [float(row[field] or 0) for row in recent]
        axis.bar(range(len(values)), values, color=color, width=0.72)
        axis.set_title(title, fontsize=9, loc="left", color="#10243A")
        axis.set_xticks(range(len(labels)))
        axis.set_xticklabels(labels, rotation=45, fontsize=6)
        axis.tick_params(axis="y", labelsize=6)
        axis.grid(axis="y", alpha=0.2)
        axis.set_axisbelow(True)
        axis.yaxis.set_major_locator(MaxNLocator(4))


def _draw_roe_roce(figure, rows: List[Dict[str, object]]) -> None:
    recent = rows[-10:]
    labels = [str(row["year"])[-4:] for row in recent]
    axis = figure.add_subplot(1, 1, 1)
    years = range(len(labels))
    roe = [row.get("return_on_equity_pct") for row in recent]
    roce = [row.get("return_on_capital_employed_pct") for row in recent]
    axis.plot(years, [float(v) if v is not None else float("nan") for v in roe], marker="o", ms=3, color="#1976D2", label="ROE (%)")
    other = axis.twinx()
    other.plot(years, [float(v) if v is not None else float("nan") for v in roce], marker="s", ms=3, color="#E67E22", label="ROCE (%)")
    axis.set_xticks(list(years))
    axis.set_xticklabels(labels, rotation=45, fontsize=6)
    axis.tick_params(axis="y", labelsize=6)
    other.tick_params(axis="y", labelsize=6, colors="#E67E22")
    axis.grid(alpha=0.2)
    axis.set_title("ROE and ROCE trend", fontsize=9, loc="left", color="#10243A")
    lines, names = axis.get_legend_handles_labels()
    lines2, names2 = other.get_legend_handles_labels()
    axis.legend(lines + lines2, names + names2, fontsize=6, loc="upper left", frameon=False)


def _draw_balance_sheet(figure, rows: List[Dict[str, object]]) -> None:
    recent = [row for row in rows if row.get("total_liabilities") is not None][-10:]
    labels = [str(row["year"])[-4:] for row in recent]
    equity = [float(row.get("shareholders_equity") or ((row.get("equity_capital") or 0) + (row.get("reserves") or 0))) for row in recent]
    debt = [float(row.get("borrowings") or 0) for row in recent]
    liabilities = [float(row.get("other_liabilities") or 0) for row in recent]
    axis = figure.add_subplot(1, 1, 1)
    axis.bar(labels, equity, color="#1976D2", label="Equity")
    axis.bar(labels, debt, bottom=equity, color="#E67E22", label="Borrowings")
    bottoms = [equity[i] + debt[i] for i in range(len(recent))]
    axis.bar(labels, liabilities, bottom=bottoms, color="#9AA8B7", label="Other liabilities")
    axis.set_title("Balance sheet composition", fontsize=9, loc="left", color="#10243A")
    axis.tick_params(axis="x", labelsize=6, rotation=45)
    axis.tick_params(axis="y", labelsize=6)
    axis.legend(fontsize=6, frameon=False, ncol=3)
    axis.grid(axis="y", alpha=0.2)
    axis.set_axisbelow(True)


def _draw_cashflow(figure, latest: Dict[str, object]) -> None:
    fields = (("CFO", "operating_activity"), ("CFI", "investing_activity"), ("CFF", "financing_activity"))
    values = [float(latest.get(key) or 0) for _, key in fields]
    net_cash = float(latest.get("net_cash_flow") or sum(values))
    axis = figure.add_subplot(1, 1, 1)
    cumulative = 0.0
    for index, (name, value) in enumerate(zip((field[0] for field in fields), values)):
        bottom = cumulative if value >= 0 else cumulative + value
        axis.bar(index, abs(value), bottom=bottom,
                 color="#17834A" if value >= 0 else "#B42318", width=0.58)
        cumulative += value
        if index < len(values) - 1:
            axis.plot([index + 0.29, index + 0.71], [cumulative, cumulative],
                      color="#627184", linewidth=0.7, linestyle=":")
    axis.bar(3, net_cash, color="#1976D2" if net_cash >= 0 else "#B42318", width=0.58)
    axis.axhline(0, color="#627184", linewidth=0.8)
    axis.set_title(f"Cash flow — {latest.get('year', '')}", fontsize=9, loc="left", color="#10243A")
    axis.set_xticks(range(4))
    axis.set_xticklabels(["CFO", "CFI", "CFF", "Net Cash"], fontsize=7)
    axis.tick_params(axis="y", labelsize=6)
    axis.grid(axis="y", alpha=0.2)
    axis.set_axisbelow(True)


def _fmt(value: object, suffix: str = "") -> str:
    if value is None:
        return "N/A"
    try:
        return f"{float(value):,.2f}{suffix}"
    except (TypeError, ValueError):
        return "N/A"


def _draw_header(pdf: canvas.Canvas, name: str, ticker: str, sector: str, page: int) -> None:
    pdf.setFillColor(NAVY)
    pdf.rect(0, PAGE_HEIGHT - 77, PAGE_WIDTH, 77, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 17)
    pdf.drawString(38, PAGE_HEIGHT - 42, name[:55])
    pdf.setFont("Helvetica", 9)
    pdf.drawString(39, PAGE_HEIGHT - 60, f"{ticker}  |  {sector}")
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 8)
    pdf.drawRightString(PAGE_WIDTH - 38, 22, f"Financial tearsheet  |  {page}/2")


def _draw_bullets(pdf: canvas.Canvas, values: List[str], x: float, y: float, width: float, color, max_rows: int = 12) -> None:
    from reportlab.lib.utils import simpleSplit

    line_height = 10
    for text in values[:max_rows]:
        lines = simpleSplit(str(text), "Helvetica", 7.2, width - 14)
        needed = max(1, len(lines))
        if y - needed * line_height < 32:
            logger.warning("Pros/cons content exceeded its allocated tearsheet area")
            break
        pdf.setFillColor(color)
        pdf.circle(x + 3, y - 2, 2, fill=1, stroke=0)
        pdf.setFillColor(colors.HexColor("#25364A"))
        pdf.setFont("Helvetica", 7.2)
        for index, line in enumerate(lines):
            pdf.drawString(x + 11, y - index * line_height, line)
        y -= needed * line_height + 4


def generate_tearsheet(
    company_id: str, output_path: str, db_path: Optional[str] = None,
    pros_cons_path: Optional[str] = None,
) -> bool:
    """Generate one two-page PDF and return whether sufficient company history exists."""
    db_path = db_path or DB_PATH
    all_data = _records(db_path)
    data = all_data.get(company_id)
    if data is None:
        raise KeyError(f"Unknown company_id: {company_id}")
    rows = _history(data)
    if len(rows) < 3:
        return False
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    pros_cons_path = pros_cons_path or os.path.join(_WORKSPACE_ROOT, "output", "pros_cons_generated.csv")
    pros: List[str] = []
    cons: List[str] = []
    if pros_cons_path and os.path.isfile(pros_cons_path):
        with open(pros_cons_path, newline="", encoding="utf-8") as stream:
            for row in csv.DictReader(stream):
                if row["company_id"] == company_id:
                    (pros if row["type"] == "pro" else cons).append(row["text"])
    if not pros or not cons:
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute("SELECT pros, cons FROM prosandcons WHERE company_id = ?", (company_id,)).fetchone()
        finally:
            conn.close()
        if row:
            if not pros:
                pros = [line.strip() for line in str(row[0] or "").splitlines() if line.strip()]
            if not cons:
                cons = [line.strip() for line in str(row[1] or "").splitlines() if line.strip()]

    latest = rows[-1]
    metrics = [
        ("ROE", latest.get("return_on_equity_pct"), "%"),
        ("ROCE", latest.get("return_on_capital_employed_pct"), "%"),
        ("Revenue CAGR (5Y)", latest.get("revenue_cagr_5yr"), "%"),
        ("PAT CAGR (5Y)", latest.get("pat_cagr_5yr"), "%"),
        ("Debt / Equity", latest.get("debt_to_equity"), "x"),
        ("Free Cash Flow", latest.get("free_cash_flow_cr"), " Cr"),
    ]
    fig1 = _chart_bytes(lambda fig: _draw_revenue_profit(fig, rows))
    fig2 = _chart_bytes(lambda fig: _draw_roe_roce(fig, rows))
    fig3 = _chart_bytes(lambda fig: _draw_balance_sheet(fig, rows))
    fig4 = _chart_bytes(lambda fig: _draw_cashflow(fig, latest))
    pdf = canvas.Canvas(output_path, pagesize=A4, pageCompression=1)
    _draw_header(pdf, str(data["company_name"]), company_id, str(data["sector"]), 1)
    tile_width = (PAGE_WIDTH - 88) / 3
    tile_height = 61
    for index, (label, value, suffix) in enumerate(metrics):
        row, col = divmod(index, 3)
        x = 38 + col * (tile_width + 6)
        y = PAGE_HEIGHT - 161 - row * (tile_height + 8)
        pdf.setFillColor(colors.HexColor("#F1F5F9"))
        pdf.roundRect(x, y, tile_width, tile_height, 6, fill=1, stroke=0)
        pdf.setFillColor(MUTED)
        pdf.setFont("Helvetica", 8)
        pdf.drawString(x + 10, y + 40, label)
        pdf.setFillColor(NAVY)
        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawString(x + 10, y + 17, _fmt(value, suffix))
    graph_width = (PAGE_WIDTH - 88) / 2
    graph_height = 150
    y = PAGE_HEIGHT - 500
    for index, (title, image) in enumerate((("Revenue & net profit (10Y)", fig1), ("Returns (dual-axis)", fig2))):
        x = 38 + index * (graph_width + 12)
        pdf.setFillColor(NAVY)
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(x, y + graph_height + 8, title)
        pdf.drawImage(ImageReader(image), x, y, width=graph_width, height=graph_height, preserveAspectRatio=True, anchor="c")
    pdf.showPage()

    _draw_header(pdf, str(data["company_name"]), company_id, str(data["sector"]), 2)
    graph_y = PAGE_HEIGHT - 330
    for index, (title, image) in enumerate((("Balance sheet", fig3), ("Cash flow waterfall", fig4))):
        x = 38 + index * (graph_width + 12)
        pdf.setFillColor(NAVY)
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(x, graph_y + graph_height + 8, title)
        pdf.drawImage(ImageReader(image), x, graph_y, width=graph_width, height=graph_height, preserveAspectRatio=True, anchor="c")

    pdf.setFillColor(GREEN)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(38, 454, "PROS")
    pdf.setFillColor(RED)
    pdf.drawString(PAGE_WIDTH / 2 + 5, 454, "CONS")
    _draw_bullets(pdf, pros, 38, 437, PAGE_WIDTH / 2 - 50, GREEN)
    _draw_bullets(pdf, cons, PAGE_WIDTH / 2 + 5, 437, PAGE_WIDTH / 2 - 50, RED)
    allocation = latest.get("capital_allocation_label")
    if not allocation:
        from src.analytics.cashflow_kpis import classify_capital_allocation
        allocation = classify_capital_allocation(
            latest.get("operating_activity"), latest.get("investing_activity"),
            latest.get("financing_activity"),
        )[3]
    pdf.setFillColor(NAVY)
    pdf.roundRect(38, 38, PAGE_WIDTH - 76, 28, 8, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawCentredString(PAGE_WIDTH / 2, 48, f"Capital Allocation  |  {allocation}")
    pdf.showPage()
    pdf.save()
    for image in (fig1, fig2, fig3, fig4):
        image.close()
    return True


def generate_all_tearsheets(
    db_path: Optional[str] = None, output_dir: Optional[str] = None,
    pros_cons_path: Optional[str] = None,
) -> Tuple[int, int]:
    """Batch-generate tearsheets; record companies with fewer than three years."""
    db_path = db_path or DB_PATH
    output_dir = output_dir or os.path.join(_WORKSPACE_ROOT, "reports", "tearsheets")
    pros_cons_path = pros_cons_path or os.path.join(_WORKSPACE_ROOT, "output", "pros_cons_generated.csv")
    os.makedirs(output_dir, exist_ok=True)
    data = _records(db_path)
    generated = 0
    skipped: List[Tuple[str, int]] = []
    for ticker, company in data.items():
        if len(company["pnl"]) < 3:
            skipped.append((ticker, len(company["pnl"])))
            continue
        output_path = os.path.join(output_dir, f"{ticker}_tearsheet.pdf")
        if generate_tearsheet(ticker, output_path, db_path, pros_cons_path):
            generated += 1
    skip_path = os.path.join(_WORKSPACE_ROOT, "output", "skipped_tearsheets.csv")
    os.makedirs(os.path.dirname(skip_path), exist_ok=True)
    with open(skip_path, "w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["ticker", "available_years"])
        writer.writerows(skipped)
    return generated, len(skipped)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    count, skipped = generate_all_tearsheets()
    logger.info("Generated %d tearsheets; skipped %d companies", count, skipped)
