"""Generate one sector PDF with medians and all constituent company KPIs."""

import logging
import os
import re
import sqlite3
import sys
from typing import Dict, List, Optional, Tuple

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle,
)

_WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

logger = logging.getLogger(__name__)
DB_PATH = os.getenv("DB_PATH", os.path.join(_WORKSPACE_ROOT, "nifty100.db"))
METRICS = (
    ("ROE (%)", "return_on_equity_pct"),
    ("ROCE (%)", "return_on_capital_employed_pct"),
    ("OPM (%)", "operating_profit_margin_pct"),
    ("D/E", "debt_to_equity"),
    ("Revenue CAGR (%)", "revenue_cagr_5yr"),
    ("PAT CAGR (%)", "pat_cagr_5yr"),
    ("FCF (Cr)", "free_cash_flow_cr"),
    ("CFO quality", "cfo_quality_score"),
)


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower() or "sector"


def _load_sector_data(db_path: str) -> Dict[str, List[Dict[str, object]]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT c.id AS company_id, c.company_name, COALESCE(s.broad_sector, 'Unclassified') AS sector,
                   fr.return_on_equity_pct, fr.return_on_capital_employed_pct,
                   fr.operating_profit_margin_pct, fr.debt_to_equity,
                   fr.revenue_cagr_5yr, fr.pat_cagr_5yr,
                   fr.free_cash_flow_cr, fr.cfo_quality_score
            FROM companies c
            LEFT JOIN sectors s ON s.company_id = c.id
            LEFT JOIN financial_ratios fr ON fr.id = (
                SELECT MAX(fr2.id) FROM financial_ratios fr2
                WHERE fr2.company_id = c.id AND fr2.year != 'TTM'
            )
            ORDER BY sector, c.id
            """
        ).fetchall()
    finally:
        conn.close()
    grouped: Dict[str, List[Dict[str, object]]] = {}
    for row in rows:
        grouped.setdefault(str(row["sector"]), []).append(dict(row))
    return grouped


def _format(value: object) -> str:
    if value is None:
        return "N/A"
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return "N/A"


def _build_sector_pdf(sector: str, rows: List[Dict[str, object]], output_path: str) -> None:
    page = landscape(letter)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="SectorCell", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=7, leading=8, alignment=TA_LEFT, wordWrap="CJK",
    ))
    styles.add(ParagraphStyle(
        name="SectorHeader", parent=styles["BodyText"], fontName="Helvetica-Bold",
        fontSize=7, leading=8, textColor=colors.white, wordWrap="CJK",
    ))
    doc = BaseDocTemplate(
        output_path, pagesize=page, leftMargin=0.35 * inch,
        rightMargin=0.35 * inch, topMargin=0.45 * inch, bottomMargin=0.4 * inch,
        title=f"{sector} Sector Report",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="sector")

    def page_header(pdf, document):
        pdf.saveState()
        pdf.setFillColor(colors.HexColor("#10243A"))
        pdf.rect(0, page[1] - 0.34 * inch, page[0], 0.34 * inch, fill=1, stroke=0)
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(doc.leftMargin, page[1] - 0.23 * inch, f"{sector} | Nifty 100")
        pdf.setFillColor(colors.HexColor("#627184"))
        pdf.setFont("Helvetica", 7)
        pdf.drawRightString(page[0] - doc.rightMargin, 0.2 * inch, f"Page {document.page}")
        pdf.restoreState()

    doc.addPageTemplates([PageTemplate(id="sector", frames=[frame], onPage=page_header)])
    story = [Spacer(1, 0.12 * inch), Paragraph(f"<b>{sector} Sector Snapshot</b>", styles["Title"])]
    story.append(Paragraph(f"{len(rows)} companies | Latest available financial ratios", styles["BodyText"]))
    summary_data = [[Paragraph("<b>Median KPI</b>", styles["SectorCell"]), Paragraph("<b>Value</b>", styles["SectorCell"])]]
    for label, key in METRICS:
        values = [float(row[key]) for row in rows if row[key] is not None]
        if values:
            values.sort()
            middle = len(values) // 2
            median = values[middle] if len(values) % 2 else (values[middle - 1] + values[middle]) / 2
            formatted = f"{median:,.2f}"
        else:
            formatted = "N/A"
        summary_data.append([Paragraph(label, styles["SectorCell"]), Paragraph(formatted, styles["SectorCell"])])
    summary = Table(summary_data, colWidths=[2.1 * inch, 1.35 * inch], hAlign="LEFT")
    summary.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#10243A")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F6F9")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("WORDWRAP", (0, 0), (-1, -1), "CJK"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.extend([Spacer(1, 0.12 * inch), summary, PageBreak(),
                  Paragraph(f"<b>{sector} Companies and Financial Metrics</b>", styles["Heading1"]),
                  Spacer(1, 0.08 * inch)])
    headers = ["Ticker", "Company"] + [label for label, _ in METRICS]
    table_data = [[Paragraph(value, styles["SectorHeader"]) for value in headers]]
    for row in rows:
        values = [row["company_id"], row["company_name"]] + [_format(row[key]) for _, key in METRICS]
        table_data.append([Paragraph(str(value), styles["SectorCell"]) for value in values])
    widths = [0.82 * inch, 2.45 * inch] + [0.78 * inch] * len(METRICS)
    table = Table(table_data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#10243A")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F6F9")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("WORDWRAP", (0, 0), (-1, -1), "CJK"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(table)
    doc.build(story)


def generate_sector_reports(
    db_path: Optional[str] = None, output_dir: Optional[str] = None
) -> Tuple[int, List[str]]:
    """Build reports for sectors present in the source company table."""
    db_path = db_path or DB_PATH
    output_dir = output_dir or os.path.join(_WORKSPACE_ROOT, "reports", "sector")
    os.makedirs(output_dir, exist_ok=True)
    sectors = _load_sector_data(db_path)
    for sector, rows in sectors.items():
        _build_sector_pdf(sector, rows, os.path.join(output_dir, f"{_safe_name(sector)}_report.pdf"))
    logger.info("Generated %d sector reports from available sector classifications", len(sectors))
    return len(sectors), sorted(sectors)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    generate_sector_reports()
