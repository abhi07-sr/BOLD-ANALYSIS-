"""Unit tests for valuation module: FCF yield, multiples, relative P/E, and flags."""

import os
import sqlite3
import pandas as pd
import pytest

from src.analytics.valuation import (
    assign_valuation_flag,
    compute_fcf_yield,
    compute_relative_pe,
    compute_valuation_metrics,
    export_valuation_reports,
)


@pytest.fixture
def db_connection():
    """Fixture providing database connection to nifty100.db."""
    db_path = os.getenv("DB_PATH", "nifty100.db")
    conn = sqlite3.connect(db_path)
    yield conn
    conn.close()


class TestValuationCalculations:
    """Tests for core valuation mathematical formulas."""

    def test_compute_fcf_yield_positive(self):
        # FCF 5,000 Cr on Market Cap 100,000 Cr -> 5.0%
        res = compute_fcf_yield(5000.0, 100000.0)
        assert res == 5.0

    def test_compute_fcf_yield_negative_fcf(self):
        # Negative FCF -> -2.5%
        res = compute_fcf_yield(-2500.0, 100000.0)
        assert res == -2.5

    def test_compute_fcf_yield_zero_or_none_mcap(self):
        assert compute_fcf_yield(1000.0, 0.0) is None
        assert compute_fcf_yield(1000.0, -500.0) is None
        assert compute_fcf_yield(1000.0, None) is None
        assert compute_fcf_yield(None, 100000.0) is None

    def test_compute_relative_pe(self):
        # Company PE 30, Sector Median 20 -> ((30-20)/20)*100 = +50.0%
        res = compute_relative_pe(30.0, 20.0)
        assert res == 50.0

        # Company PE 14, Sector Median 20 -> ((14-20)/20)*100 = -30.0%
        res2 = compute_relative_pe(14.0, 20.0)
        assert res2 == -30.0

    def test_compute_relative_pe_invalid(self):
        assert compute_relative_pe(None, 20.0) is None
        assert compute_relative_pe(25.0, None) is None
        assert compute_relative_pe(-10.0, 20.0) is None
        assert compute_relative_pe(25.0, 0.0) is None

    def test_assign_valuation_flag_caution(self):
        # Caution if PE > 1.5x sector median
        # Sector median 20 -> threshold 30 -> PE 31 is Caution
        flag = assign_valuation_flag(31.0, 20.0)
        assert flag == "Caution"

    def test_assign_valuation_flag_discount(self):
        # Discount if PE < 0.7x sector median
        # Sector median 20 -> threshold 14 -> PE 13 is Discount
        flag = assign_valuation_flag(13.0, 20.0)
        assert flag == "Discount"

    def test_assign_valuation_flag_fair(self):
        # Fair if between 0.7x and 1.5x
        # Sector median 20 -> PE 20 is Fair
        flag = assign_valuation_flag(20.0, 20.0)
        assert flag == "Fair"

    def test_assign_valuation_flag_invalid(self):
        assert assign_valuation_flag(None, 20.0) is None
        assert assign_valuation_flag(25.0, None) is None
        assert assign_valuation_flag(-5.0, 20.0) is None


class TestValuationOutputs:
    """Tests for generated valuation summary excel and flags csv files."""

    def test_compute_valuation_metrics_all_92_companies(self, db_connection):
        df = compute_valuation_metrics(db_connection, year="2024")
        assert len(df) == 92
        assert "company_id" in df.columns
        assert "flag" in df.columns
        assert "FCF_yield_pct" in df.columns
        assert "5yr_median_PE" in df.columns

    def test_valuation_summary_excel_exists_and_valid(self):
        excel_path = os.path.join("output", "valuation_summary.xlsx")
        assert os.path.exists(excel_path), "output/valuation_summary.xlsx does not exist"

        df = pd.read_excel(excel_path)
        assert len(df) == 92, f"Expected 92 rows in valuation summary, got {len(df)}"

        required_cols = [
            "company_id",
            "company_name",
            "sector",
            "P/E",
            "P/B",
            "EV/EBITDA",
            "FCF_yield_pct",
            "5yr_median_PE",
            "PE_vs_sector_median_pct",
            "flag",
        ]
        for col in required_cols:
            assert col in df.columns, f"Missing required column: {col}"

    def test_valuation_flags_csv_exists_and_filtered(self):
        csv_path = os.path.join("output", "valuation_flags.csv")
        assert os.path.exists(csv_path), "output/valuation_flags.csv does not exist"

        df = pd.read_csv(csv_path)
        assert not df.empty, "valuation_flags.csv is empty"
        assert set(df["flag"].unique()).issubset({"Caution", "Discount"}), (
            f"valuation_flags.csv should only contain Caution and Discount flags, got: {df['flag'].unique()}"
        )
        assert "Fair" not in df["flag"].values
