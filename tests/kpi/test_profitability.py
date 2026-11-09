"""Unit tests for Profitability Ratios (Day 08)."""

import pytest
from src.analytics.ratios import (
    compute_npm,
    compute_opm,
    compute_roa,
    compute_roce,
    compute_roe,
)


def test_npm_normal_calculation():
    assert compute_npm(150.0, 1000.0) == 15.0


def test_npm_zero_and_negative_sales():
    assert compute_npm(100.0, 0.0) is None
    assert compute_npm(100.0, -500.0) is None
    assert compute_npm(None, 1000.0) is None


def test_opm_normal_crosscheck_match():
    opm, has_mismatch = compute_opm(200.0, 1000.0, reported_opm=20.0)
    assert opm == 20.0
    assert not has_mismatch


def test_opm_mismatch_flag():
    opm, has_mismatch = compute_opm(250.0, 1000.0, reported_opm=20.0)
    assert opm == 25.0
    assert has_mismatch


def test_roe_normal_calculation():
    # equity_capital=100, reserves=900 -> total equity = 1000
    assert compute_roe(150.0, 100.0, 900.0) == 15.0


def test_roe_negative_and_zero_equity():
    # Negative net worth (reserves deeply negative)
    assert compute_roe(50.0, 100.0, -200.0) is None
    # Zero net worth
    assert compute_roe(50.0, 100.0, -100.0) is None


def test_roce_normal_and_financial_carveout():
    # PBT=300, interest=50 (EBIT=350), equity=100, reserves=400, borrowings=500 -> CE = 1000
    assert compute_roce(300.0, 50.0, 100.0, 400.0, 500.0, is_financial=False) == 35.0
    # Financial firm (EBIT = PBT alone) -> 300 / 1000 = 30.0%
    assert compute_roce(300.0, 50.0, 100.0, 400.0, 500.0, is_financial=True) == 30.0


def test_roa_normal_and_zero_assets():
    assert compute_roa(50.0, 500.0) == 10.0
    assert compute_roa(50.0, 0.0) is None
    assert compute_roa(50.0, -100.0) is None

