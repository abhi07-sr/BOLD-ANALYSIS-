"""Unit tests for the ETL Loader."""

import os
import sqlite3
import pytest
from src.etl.loader import DB_PATH, SCHEMA_PATH, clean_val, init_database


def test_clean_val():
    assert clean_val(None) is None
    assert clean_val("") is None
    assert clean_val("   ") is None
    assert clean_val("nan") is None
    assert clean_val("NaN") is None
    assert clean_val("null") is None
    assert clean_val("NULL") is None
    assert clean_val("TCS\n") == "TCS"
    assert clean_val("  Infosys  ") == "Infosys"
    assert clean_val(123.45) == 123.45


def test_schema_file_exists():
    assert os.path.exists(SCHEMA_PATH)


def test_database_companies_count():
    conn = sqlite3.connect("nifty100.db")
    cursor = conn.cursor()
    cnt = cursor.execute("SELECT COUNT(*) FROM companies;").fetchone()[0]
    conn.close()
    assert cnt == 92


def test_database_stock_prices_count():
    conn = sqlite3.connect("nifty100.db")
    cursor = conn.cursor()
    cnt = cursor.execute("SELECT COUNT(*) FROM stock_prices;").fetchone()[0]
    conn.close()
    assert cnt == 5520


def test_database_tables_exist():
    conn = sqlite3.connect("nifty100.db")
    cursor = conn.cursor()
    tables = [
        t[0] for t in cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
        ).fetchall()
    ]
    conn.close()
    expected = [
        "companies",
        "profitandloss",
        "balancesheet",
        "cashflow",
        "financial_ratios",
        "stock_prices",
        "documents",
        "sectors",
        "peer_groups",
        "market_cap",
        "analysis",
        "prosandcons",
    ]
    for exp in expected:
        assert exp in tables, f"Missing table: {exp}"

