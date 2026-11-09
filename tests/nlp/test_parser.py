import csv
import sqlite3

from openpyxl import Workbook

from src.nlp.parser import parse_analysis


def test_parse_analysis_and_flag_five_year_cagr_divergence(tmp_path):
    workbook_path = tmp_path / "analysis.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Source workbook"])
    sheet.append([
        "id", "company_id", "compounded_sales_growth", "compounded_profit_growth",
        "stock_price_cagr", "roe",
    ])
    sheet.append(["1", "ABC", "5 Years: 21%", "5 Years: 10%", "3 Years: 8%", "10 Years: 17%"])
    sheet.append(["2", "ABC", "TTM: 18%", None, "1 Year: -2%", "Last Year: 12%"])
    workbook.save(workbook_path)

    db_path = tmp_path / "analytics.db"
    connection = sqlite3.connect(db_path)
    connection.execute(
        "CREATE TABLE financial_ratios (id INTEGER, company_id TEXT, year TEXT, "
        "revenue_cagr_5yr REAL, pat_cagr_5yr REAL)"
    )
    connection.execute(
        "INSERT INTO financial_ratios VALUES (1, 'ABC', '2024', 14.0, 12.0)"
    )
    connection.commit()
    connection.close()

    parsed_count, failure_count, divergence_count = parse_analysis(
        str(workbook_path), str(db_path), str(tmp_path / "output")
    )

    assert parsed_count == 4
    assert failure_count == 4
    assert divergence_count == 1
    with open(tmp_path / "output" / "analysis_parsed.csv", newline="", encoding="utf-8") as stream:
        parsed = list(csv.DictReader(stream))
    assert parsed[0] == {
        "company_id": "ABC",
        "metric_type": "compounded_sales_growth",
        "period_years": "5",
        "value_pct": "21.0",
    }
    with open(tmp_path / "output" / "cagr_divergences.csv", newline="", encoding="utf-8") as stream:
        divergences = list(csv.DictReader(stream))
    assert divergences[0]["divergence_pct_points"] == "7.0"
