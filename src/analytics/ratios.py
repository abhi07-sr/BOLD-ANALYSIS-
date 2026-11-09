"""Financial Ratio calculations: Profitability, Leverage, and Efficiency KPIs."""

import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================================
# Day 08 — Profitability Ratios
# ============================================================================

def compute_npm(net_profit: Optional[float], sales: Optional[float]) -> Optional[float]:
    """Net Profit Margin: (net_profit / sales) * 100.

    Returns:
        float: Net profit margin percentage, rounded to 2 decimal places.
        None: If sales is None, zero, or negative.
    """
    if net_profit is None or sales is None or sales <= 0:
        return None
    return round((net_profit / sales) * 100.0, 2)


def compute_opm(
    operating_profit: Optional[float],
    sales: Optional[float],
    reported_opm: Optional[float] = None,
) -> Tuple[Optional[float], bool]:
    """Operating Profit Margin: (operating_profit / sales) * 100.

    Cross-checks against reported OPM percentage if provided.

    Returns:
        Tuple[Optional[float], bool]: (calculated_opm, has_mismatch)
        has_mismatch is True if difference between calculated and reported > 1.0%.
    """
    if operating_profit is None or sales is None or sales <= 0:
        return None, False

    calc_opm = round((operating_profit / sales) * 100.0, 2)
    has_mismatch = False

    if reported_opm is not None:
        diff = abs(calc_opm - reported_opm)
        if diff > 1.0:
            has_mismatch = True
            logger.info(
                f"OPM mismatch > 1%: calc={calc_opm}%, reported={reported_opm}% (diff={diff:.2f}%)"
            )

    return calc_opm, has_mismatch


def compute_roe(
    net_profit: Optional[float],
    equity_capital: Optional[float],
    reserves: Optional[float],
) -> Optional[float]:
    """Return on Equity: net_profit / (equity_capital + reserves) * 100.

    Returns:
        float: ROE percentage, rounded to 2 decimal places.
        None: If total equity (capital + reserves) <= 0 or inputs are missing.
    """
    if net_profit is None or equity_capital is None or reserves is None:
        return None

    total_equity = equity_capital + reserves
    if total_equity <= 0:
        return None

    return round((net_profit / total_equity) * 100.0, 2)


def compute_roce(
    pbt: Optional[float],
    interest: Optional[float],
    equity_capital: Optional[float],
    reserves: Optional[float],
    borrowings: Optional[float],
    is_financial: bool = False,
) -> Optional[float]:
    """Return on Capital Employed: EBIT / (equity + reserves + borrowings) * 100.

    For financial institutions (banks/NBFCs), interest is an operating cost,
    so EBIT is represented by PBT alone or sector-relative benchmark.

    Returns:
        float: ROCE percentage, rounded to 2 decimal places.
        None: If capital employed <= 0 or inputs are missing.
    """
    if (
        pbt is None
        or equity_capital is None
        or reserves is None
        or borrowings is None
    ):
        return None

    ebit = pbt if is_financial else (pbt + (interest or 0.0))
    capital_employed = equity_capital + reserves + borrowings

    if capital_employed <= 0:
        return None

    return round((ebit / capital_employed) * 100.0, 2)


def compute_roa(
    net_profit: Optional[float], total_assets: Optional[float]
) -> Optional[float]:
    """Return on Assets: (net_profit / total_assets) * 100.

    Returns:
        float: ROA percentage, rounded to 2 decimal places.
        None: If total_assets <= 0 or inputs are missing.
    """
    if net_profit is None or total_assets is None or total_assets <= 0:
        return None
    return round((net_profit / total_assets) * 100.0, 2)


# ============================================================================
# Day 09 — Leverage & Efficiency Ratios
# ============================================================================

def compute_debt_to_equity(
    borrowings: Optional[float],
    equity_capital: Optional[float],
    reserves: Optional[float],
    is_financial: bool = False,
) -> Tuple[Optional[float], bool]:
    """Debt-to-Equity ratio: borrowings / (equity_capital + reserves).

    - If borrowings == 0, returns 0.0 (not None).
    - If total equity <= 0, returns (None, False).
    - If D/E > 5.0 and NOT in Financials, sets high_leverage_flag = True.

    Returns:
        Tuple[Optional[float], bool]: (debt_to_equity, high_leverage_flag)
    """
    if equity_capital is None or reserves is None:
        return None, False

    total_equity = equity_capital + reserves
    if total_equity <= 0:
        return None, False

    actual_borrowings = 0.0 if (borrowings is None or borrowings == 0) else float(borrowings)
    de_ratio = round(actual_borrowings / total_equity, 4)

    # Flag high leverage (> 5.0) only for non-financial companies
    high_leverage_flag = bool(de_ratio > 5.0 and not is_financial)

    return de_ratio, high_leverage_flag


def compute_interest_coverage(
    operating_profit: Optional[float],
    other_income: Optional[float],
    interest: Optional[float],
) -> Tuple[Optional[float], str, bool]:
    """Interest Coverage Ratio: (operating_profit + other_income) / interest.

    - If interest == 0 (debt-free), returns (None, "Debt Free", False).
    - If ICR < 1.5, sets icr_warning_flag = True ("At Risk").

    Returns:
        Tuple[Optional[float], str, bool]: (icr_value, icr_label, icr_warning_flag)
    """
    if interest is None or interest == 0:
        return None, "Debt Free", False

    ebit = (operating_profit or 0.0) + (other_income or 0.0)
    icr_value = round(ebit / interest, 2)
    warning_flag = bool(icr_value < 1.5)
    label = "At Risk" if warning_flag else "Adequate"

    return icr_value, label, warning_flag


def compute_net_debt(
    borrowings: Optional[float], investments: Optional[float]
) -> float:
    """Net Debt: borrowings - investments (using investments as liquid asset proxy)."""
    b = float(borrowings or 0.0)
    inv = float(investments or 0.0)
    return round(b - inv, 2)


def compute_asset_turnover(
    sales: Optional[float], total_assets: Optional[float]
) -> Optional[float]:
    """Asset Turnover: sales / total_assets.

    Returns:
        float: Asset turnover multiple, rounded to 4 decimal places.
        None: If total_assets <= 0 or inputs are missing.
    """
    if sales is None or total_assets is None or total_assets <= 0:
        return None
    return round(sales / total_assets, 4)

