"""Compound Annual Growth Rate (CAGR) Engine with comprehensive edge-case handling."""

from typing import Dict, Optional, Tuple

# 6 Canonical CAGR Flag Constants
FLAG_NORMAL = "NORMAL"
FLAG_DECLINE_TO_LOSS = "DECLINE_TO_LOSS"
FLAG_TURNAROUND = "TURNAROUND"
FLAG_BOTH_NEGATIVE = "BOTH_NEGATIVE"
FLAG_ZERO_BASE = "ZERO_BASE"
FLAG_INSUFFICIENT = "INSUFFICIENT"


def compute_cagr(
    start_value: Optional[float], end_value: Optional[float], n_years: int
) -> Tuple[Optional[float], str]:
    """Compute CAGR over an n-year window with edge-case classification.

    Formula:
        CAGR = ((end_value / start_value) ** (1 / n_years) - 1) * 100

    Edge Cases Handled:
        1. Both positive: Computed normally, flag = "NORMAL"
        2. Positive to Loss (start > 0, end <= 0): None, flag = "DECLINE_TO_LOSS"
        3. Loss to Profit (start <= 0, end > 0): None, flag = "TURNAROUND"
        4. Both negative (start <= 0, end <= 0): None, flag = "BOTH_NEGATIVE"
        5. Zero base (start == 0): None, flag = "ZERO_BASE"
        6. Insufficient years (n_years <= 0 or missing values): None, flag = "INSUFFICIENT"

    Args:
        start_value: Value at the beginning of the period.
        end_value: Value at the end of the period.
        n_years: Number of years in the period.

    Returns:
        Tuple[Optional[float], str]: (cagr_percentage, edge_case_flag)
    """
    if n_years <= 0 or start_value is None or end_value is None:
        return None, FLAG_INSUFFICIENT

    s = float(start_value)
    e = float(end_value)

    if s == 0.0:
        return None, FLAG_ZERO_BASE

    if s > 0 and e <= 0:
        return None, FLAG_DECLINE_TO_LOSS

    if s < 0 and e > 0:
        return None, FLAG_TURNAROUND

    if s < 0 and e <= 0:
        return None, FLAG_BOTH_NEGATIVE

    # Both positive: standard CAGR
    try:
        ratio = e / s
        cagr = (pow(ratio, 1.0 / n_years) - 1.0) * 100.0
        return round(cagr, 2), FLAG_NORMAL
    except (ValueError, OverflowError, ZeroDivisionError):
        return None, FLAG_INSUFFICIENT


def compute_historical_cagr(
    annual_data: Dict[int, float], target_year: int, n_years: int
) -> Tuple[Optional[float], str]:
    """Compute CAGR for an n-year lookback from target_year using an annual dictionary.

    Args:
        annual_data: Dictionary mapping integer calendar/reporting years to values.
        target_year: Ending year.
        n_years: Lookback window (e.g. 3, 5, 10).

    Returns:
        Tuple[Optional[float], str]: (cagr_percentage, flag)
    """
    start_year = target_year - n_years
    if start_year not in annual_data or target_year not in annual_data:
        return None, FLAG_INSUFFICIENT

    start_val = annual_data.get(start_year)
    end_val = annual_data.get(target_year)

    return compute_cagr(start_val, end_val, n_years)

