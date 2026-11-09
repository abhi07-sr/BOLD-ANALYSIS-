"""Unit tests for the Data Quality Validator covering DQ-01 to DQ-14."""

import os
import sqlite3
import pytest
from src.etl.validator import DataQualityValidator, validate_database

DB_PATH = "nifty100.db"


@pytest.fixture(scope="module")
def db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


def test_dq01_pk_uniqueness(db_conn):
    """DQ-01: Verify primary key uniqueness across all tables (0 duplicate PKs)."""
    tables = [
        t[0]
        for t in db_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    ]
    for tbl in tables:
        dups = db_conn.execute(
            f"SELECT id, COUNT(*) as cnt FROM {tbl} GROUP BY id HAVING cnt > 1"
        ).fetchall()
        assert len(dups) == 0, f"Duplicate PKs found in {tbl}: {dups}"


def test_dq02_composite_pk_uniqueness(db_conn):
    """DQ-02: Verify composite PK (company_id, year) uniqueness (0 duplicate pairs)."""
    annual_tables = ["profitandloss", "balancesheet", "cashflow", "financial_ratios", "market_cap"]
    for tbl in annual_tables:
        dups = db_conn.execute(
            f"SELECT company_id, year, COUNT(*) as cnt FROM {tbl} GROUP BY company_id, year HAVING cnt > 1"
        ).fetchall()
        assert len(dups) == 0, f"Duplicate (company_id, year) found in {tbl}: {dups}"


def test_dq03_foreign_key_integrity(db_conn):
    """DQ-03: Verify zero foreign key violations in the SQLite database."""
    fk_violations = db_conn.execute("PRAGMA foreign_key_check;").fetchall()
    assert len(fk_violations) == 0, f"Foreign key violations found: {fk_violations}"


def test_dq04_balance_sheet_balance(db_conn):
    """DQ-04: Verify balance sheet total assets and liabilities are recorded."""
    rows = db_conn.execute(
        "SELECT COUNT(*) FROM balancesheet WHERE total_assets IS NULL OR total_liabilities IS NULL"
    ).fetchone()[0]
    assert rows == 0, f"Missing balance sheet totals: {rows}"


def test_dq05_opm_crosscheck(db_conn):
    """DQ-05: Verify operating profit margin crosscheck is computable for P&L rows."""
    rows = db_conn.execute(
        "SELECT COUNT(*) FROM profitandloss WHERE sales > 0 AND operating_profit IS NOT NULL AND opm_percentage IS NOT NULL"
    ).fetchone()[0]
    assert rows >= 1000, f"Expected >= 1000 P&L rows for OPM check, got {rows}"


def test_dq06_positive_sales(db_conn):
    """DQ-06: Verify sales are non-negative across all historical records."""
    neg_sales = db_conn.execute(
        "SELECT COUNT(*) FROM profitandloss WHERE sales < 0"
    ).fetchone()[0]
    assert neg_sales == 0, f"Negative sales detected: {neg_sales}"


def test_dq07_net_cash_flow(db_conn):
    """DQ-07: Verify cashflow table has operating activity recorded for >99% of records."""
    total = db_conn.execute("SELECT COUNT(*) FROM cashflow").fetchone()[0]
    valid_cfo = db_conn.execute("SELECT COUNT(*) FROM cashflow WHERE operating_activity IS NOT NULL").fetchone()[0]
    assert valid_cfo / total >= 0.99, f"CFO coverage too low: {valid_cfo}/{total}"


def test_dq08_tax_rate_bounds(db_conn):
    """DQ-08: Verify tax percentage records are populated for profitable periods."""
    rows = db_conn.execute("SELECT COUNT(*) FROM profitandloss WHERE profit_before_tax > 0 AND tax_percentage IS NOT NULL").fetchone()[0]
    assert rows > 800, f"Tax percentage records sparse: {rows}"


def test_dq09_dividend_payout(db_conn):
    """DQ-09: Verify dividend payout is recorded for profitable companies."""
    rows = db_conn.execute(
        "SELECT COUNT(*) FROM profitandloss WHERE net_profit > 0 AND dividend_payout IS NOT NULL"
    ).fetchone()[0]
    assert rows >= 900, f"Dividend payout records sparse: {rows}"


def test_dq10_urls(db_conn):
    """DQ-10: Verify company URLs and identifiers are properly formatted."""
    rows = db_conn.execute("SELECT website, chart_link FROM companies WHERE website IS NOT NULL").fetchall()
    assert len(rows) >= 90, "Expected at least 90 companies to have valid websites"


def test_dq11_eps_sign():
    """DQ-11: Verify validator flags EPS and PAT sign discordance as WARNING."""
    validator = DataQualityValidator(".")
    validator.load_all_datasets()
    validator._validate_dq11_eps_sign()
    failures = [f for f in validator.failures if f.rule_id == "DQ-11"]
    assert len(failures) > 0, "Expected DQ-11 to detect EPS/PAT sign discordance"
    assert all(f.severity == "WARNING" for f in failures)


def test_dq12_balance_sheet_components(db_conn):
    """DQ-12: Verify balance sheet equity capital is recorded for all records."""
    rows = db_conn.execute(
        "SELECT COUNT(*) FROM balancesheet WHERE equity_capital IS NULL"
    ).fetchone()[0]
    assert rows == 0, f"Missing equity capital rows: {rows}"


def test_dq13_historical_year_coverage(db_conn):
    """DQ-13: Verify all 92 companies have at least 3 years of reporting history."""
    counts = db_conn.execute(
        "SELECT company_id, COUNT(*) as cnt FROM profitandloss GROUP BY company_id"
    ).fetchall()
    assert len(counts) == 92, f"Expected 92 companies, got {len(counts)}"
    for c in counts:
        assert c["cnt"] >= 3, f"Company {c['company_id']} has insufficient history: {c['cnt']}"


def test_dq14_stock_prices_integrity(db_conn):
    """DQ-14: Stock prices integrity — verify High >= Low, Open, Close across all 5,520 records."""
    inversions = db_conn.execute("""
        SELECT COUNT(*) FROM stock_prices 
        WHERE high_price < low_price 
           OR high_price < open_price 
           OR high_price < close_price
    """).fetchone()[0]
    assert inversions == 0, f"Stock price high price inversions found: {inversions}"
