"""Unit tests for CAGR Engine and its 6 edge cases (Day 10)."""

import pytest
from src.analytics.cagr import (
    FLAG_BOTH_NEGATIVE,
    FLAG_DECLINE_TO_LOSS,
    FLAG_INSUFFICIENT,
    FLAG_NORMAL,
    FLAG_TURNAROUND,
    FLAG_ZERO_BASE,
    compute_cagr,
    compute_historical_cagr,
)


def test_cagr_normal_positive_growth():
    # 100 growing to 200 over 5 years is ~14.87%
    cagr, flag = compute_cagr(100.0, 200.0, 5)
    assert cagr == 14.87
    assert flag == FLAG_NORMAL


def test_cagr_normal_positive_decay():
    # 100 dropping to 50 over 5 years is ~ -12.94%
    cagr, flag = compute_cagr(100.0, 50.0, 5)
    assert cagr == -12.94
    assert flag == FLAG_NORMAL


def test_cagr_decline_to_loss_negative_end():
    cagr, flag = compute_cagr(150.0, -25.0, 3)
    assert cagr is None
    assert flag == FLAG_DECLINE_TO_LOSS


def test_cagr_decline_to_loss_zero_end():
    cagr, flag = compute_cagr(150.0, 0.0, 3)
    assert cagr is None
    assert flag == FLAG_DECLINE_TO_LOSS


def test_cagr_turnaround_from_loss():
    cagr, flag = compute_cagr(-50.0, 100.0, 5)
    assert cagr is None
    assert flag == FLAG_TURNAROUND


def test_cagr_both_negative():
    cagr, flag = compute_cagr(-100.0, -20.0, 3)
    assert cagr is None
    assert flag == FLAG_BOTH_NEGATIVE


def test_cagr_zero_base():
    cagr, flag = compute_cagr(0.0, 500.0, 5)
    assert cagr is None
    assert flag == FLAG_ZERO_BASE


def test_cagr_insufficient_zero_or_negative_n():
    cagr, flag = compute_cagr(100.0, 200.0, 0)
    assert cagr is None
    assert flag == FLAG_INSUFFICIENT


def test_cagr_none_inputs():
    cagr, flag = compute_cagr(None, 200.0, 5)
    assert cagr is None
    assert flag == FLAG_INSUFFICIENT


def test_historical_series_lookback():
    history = {2019: 100.0, 2020: 120.0, 2021: 150.0, 2024: 200.0}
    # 5-year lookback from 2024 (needs 2019): 100 -> 200
    cagr, flag = compute_historical_cagr(history, target_year=2024, n_years=5)
    assert cagr == 14.87
    assert flag == FLAG_NORMAL

    # Missing start year (e.g. 3-year lookback needs 2021, present; 4-year needs 2020, present; 2-year needs 2022, missing!)
    cagr_miss, flag_miss = compute_historical_cagr(history, target_year=2024, n_years=2)
    assert cagr_miss is None
    assert flag_miss == FLAG_INSUFFICIENT

