"""Unit tests for Cash Flow KPIs and 8-Pattern Capital Allocation (Day 11)."""

import pytest
from src.analytics.cashflow_kpis import (
    classify_capital_allocation,
    compute_capex_intensity,
    compute_cfo_quality_score,
    compute_fcf_conversion,
    compute_free_cash_flow,
)


def test_free_cash_flow_calculation():
    # Operating = 500, Investing = -200 -> FCF = 300
    assert compute_free_cash_flow(500.0, -200.0) == 300.0
    # Negative FCF is valid: Operating = 100, Investing = -300 -> FCF = -200
    assert compute_free_cash_flow(100.0, -300.0) == -200.0
    assert compute_free_cash_flow(None, -200.0) is None


def test_cfo_quality_score_tiers():
    # CFO > PAT: High Quality
    score_high, label_high = compute_cfo_quality_score([120.0, 150.0], [100.0, 100.0])
    assert score_high == 1.35
    assert label_high == "High Quality"

    # Moderate: 0.5 <= CFO/PAT <= 1.0
    score_mod, label_mod = compute_cfo_quality_score([70.0, 80.0], [100.0, 100.0])
    assert score_mod == 0.75
    assert label_mod == "Moderate"

    # Accrual Risk: CFO/PAT < 0.5
    score_risk, label_risk = compute_cfo_quality_score([30.0, 40.0], [100.0, 100.0])
    assert score_risk == 0.35
    assert label_risk == "Accrual Risk"


def test_capex_intensity_tiers():
    # < 3%: Asset Light
    pct_light, label_light = compute_capex_intensity(-20.0, 1000.0)
    assert pct_light == 2.0
    assert label_light == "Asset Light"

    # 3-8%: Moderate
    pct_mod, label_mod = compute_capex_intensity(-50.0, 1000.0)
    assert pct_mod == 5.0
    assert label_mod == "Moderate"

    # > 8%: Capital Intensive
    pct_heavy, label_heavy = compute_capex_intensity(-150.0, 1000.0)
    assert pct_heavy == 15.0
    assert label_heavy == "Capital Intensive"


def test_fcf_conversion_rate():
    # FCF = 200, Operating Profit = 500 -> 40.0%
    assert compute_fcf_conversion(200.0, 500.0) == 40.0
    # Operating profit <= 0 -> None
    assert compute_fcf_conversion(200.0, 0.0) is None
    assert compute_fcf_conversion(200.0, -50.0) is None


def test_capital_allocation_patterns():
    # (+, -, -) with moderate CFO/PAT -> Reinvestor
    assert classify_capital_allocation(500, -200, -100, cfo_pat_ratio=1.0) == ("+", "-", "-", "Reinvestor")
    # (+, -, -) with high CFO/PAT (>1.2) -> Shareholder Returns
    assert classify_capital_allocation(500, -200, -100, cfo_pat_ratio=1.5) == ("+", "-", "-", "Shareholder Returns")
    # (+, +, -) -> Liquidating Assets
    assert classify_capital_allocation(300, 100, -100) == ("+", "+", "-", "Liquidating Assets")
    # (-, +, +) -> Distress Signal
    assert classify_capital_allocation(-100, 200, 100) == ("-", "+", "+", "Distress Signal")
    # (-, -, +) -> Growth Funded by Debt
    assert classify_capital_allocation(-100, -200, 400) == ("-", "-", "+", "Growth Funded by Debt")
    # (+, +, +) -> Cash Accumulator
    assert classify_capital_allocation(100, 200, 300) == ("+", "+", "+", "Cash Accumulator")
    # (-, -, -) -> Pre-Revenue
    assert classify_capital_allocation(-50, -50, -50) == ("-", "-", "-", "Pre-Revenue")
    # (+, -, +) -> Mixed
    assert classify_capital_allocation(200, -100, 50) == ("+", "-", "+", "Mixed")

