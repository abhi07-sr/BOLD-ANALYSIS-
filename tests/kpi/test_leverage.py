"""Unit tests for Leverage and Efficiency Ratios (Day 09)."""

import pytest
from src.analytics.ratios import (
    compute_asset_turnover,
    compute_debt_to_equity,
    compute_interest_coverage,
    compute_net_debt,
)


def test_de_debt_free_returns_zero():
    # When company has no borrowings, D/E must return 0.0 (not None)
    de, flag = compute_debt_to_equity(0.0, 100.0, 400.0)
    assert de == 0.0
    assert not flag

    de_none, flag_none = compute_debt_to_equity(None, 100.0, 400.0)
    assert de_none == 0.0
    assert not flag_none


def test_de_normal_calculation():
    # borrowings=500, total equity=1000 -> D/E = 0.5
    de, flag = compute_debt_to_equity(500.0, 100.0, 900.0)
    assert de == 0.5
    assert not flag


def test_de_high_leverage_flag_non_financial():
    # borrowings=6000, total equity=1000 -> D/E = 6.0 (> 5.0) -> Flag True
    de, flag = compute_debt_to_equity(6000.0, 100.0, 900.0, is_financial=False)
    assert de == 6.0
    assert flag


def test_de_high_leverage_suppression_financials():
    # For banks/NBFCs, high leverage (> 5.0) is structurally normal -> Flag suppressed (False)
    de, flag = compute_debt_to_equity(6000.0, 100.0, 900.0, is_financial=True)
    assert de == 6.0
    assert not flag


def test_icr_interest_zero_debt_free_label():
    # Interest == 0 -> returns (None, "Debt Free", False)
    val, label, warning = compute_interest_coverage(500.0, 50.0, 0.0)
    assert val is None
    assert label == "Debt Free"
    assert not warning


def test_icr_warning_flag_below_threshold():
    # EBIT = 120, interest = 100 -> ICR = 1.2 (< 1.5) -> At Risk
    val, label, warning = compute_interest_coverage(100.0, 20.0, 100.0)
    assert val == 1.2
    assert label == "At Risk"
    assert warning


def test_icr_adequate():
    # EBIT = 500, interest = 100 -> ICR = 5.0 (>= 1.5) -> Adequate
    val, label, warning = compute_interest_coverage(450.0, 50.0, 100.0)
    assert val == 5.0
    assert label == "Adequate"
    assert not warning


def test_net_debt_and_asset_turnover():
    # Net Debt = borrowings - investments
    assert compute_net_debt(1000.0, 300.0) == 700.0
    assert compute_net_debt(200.0, 500.0) == -300.0  # Net cash positive

    # Asset Turnover = sales / total_assets
    assert compute_asset_turnover(1500.0, 1000.0) == 1.5
    assert compute_asset_turnover(1500.0, 0.0) is None

