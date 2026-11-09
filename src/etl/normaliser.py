"""Data normalisation utilities for financial tickers and reporting years."""

import re
from typing import Optional, Union

# Known ticker corrections (e.g. typos in source data)
TICKER_CORRECTIONS = {
    "AGTL": "ATGL",
}

# 2-digit to 4-digit century cutoff
# E.g. '95' -> 1995, '24' -> 2024
TWO_DIGIT_YEAR_CUTOFF = 50


def normalize_year(val: Union[str, int, float, None], strict: bool = False) -> Optional[str]:
    """Normalize various year representations into a standard 4-digit string or 'TTM'.

    Supported formats:
    - 4-digit year: 2021, '2021', 2021.0 -> '2021'
    - Month Year: 'Mar 2021', 'Dec 2012', 'Jun 2013' -> '2021', '2012', '2013'
    - Month-2digit: 'Mar-22', 'Mar-13' -> '2022', '2013'
    - Annotated: 'Mar 2016 9m', 'Mar 2023 15' -> '2016', '2023'
    - Float year: '2024.5', 2024.5 -> '2024'
    - Fiscal year: 'FY2021' -> '2021', 'FY22' -> '2022', '2020-21' -> '2021'
    - Date strings: '31-03-2023', '2023-03-31' -> '2023'
    - Trailing Twelve Months: 'TTM' -> 'TTM'

    Args:
        val: Input year representation.
        strict: If True, raises ValueError on invalid input; otherwise returns None.

    Returns:
        Normalized string (e.g. '2021' or 'TTM'), or None if empty/invalid.
    """
    if val is None:
        if strict:
            raise ValueError("Year cannot be None")
        return None

    # If already an integer
    if isinstance(val, int):
        if 1900 <= val <= 2100:
            return str(val)
        if strict:
            raise ValueError(f"Integer year out of range: {val}")
        return None

    # If float
    if isinstance(val, float):
        if val != val:  # NaN
            if strict:
                raise ValueError("Year cannot be NaN")
            return None
        int_val = int(val)
        if 1900 <= int_val <= 2100:
            return str(int_val)
        if strict:
            raise ValueError(f"Float year out of range: {val}")
        return None

    s = str(val).strip()
    if not s:
        if strict:
            raise ValueError("Empty year string")
        return None

    # Check for TTM
    if s.upper() == "TTM":
        return "TTM"

    # Handle standard 4-digit year at start or end or alone
    # Check if string is a float like '2024.5'
    try:
        f_val = float(s)
        int_val = int(f_val)
        if 1900 <= int_val <= 2100:
            return str(int_val)
    except ValueError:
        pass

    # Check FY format: FY2021 or FY21
    fy_match = re.search(r"FY\s*(\d{2,4})", s, re.IGNORECASE)
    if fy_match:
        yr = fy_match.group(1)
        if len(yr) == 2:
            y_int = int(yr)
            century = 1900 if y_int >= TWO_DIGIT_YEAR_CUTOFF else 2000
            return str(century + y_int)
        return yr

    # Check hyphenated range: '2020-21' or '2020-2021' -> second year
    range_match = re.search(r"\b(19\d\d|20\d\d)[-/](\d{2,4})\b", s)
    if range_match:
        y2 = range_match.group(2)
        if len(y2) == 2:
            return str(int(range_match.group(1)[:2]) * 100 + int(y2))
        return y2

    # Check date formats: dd-mm-yyyy or yyyy-mm-dd
    date_match = re.search(r"\b(19\d\d|20\d\d)\b", s)
    if date_match:
        return date_match.group(1)

    # Check Month-2digit format: 'Mar-22', 'Dec-15'
    m_2digit = re.search(r"([A-Za-z]{3})[-/\s](\d{2})\b", s)
    if m_2digit:
        y_int = int(m_2digit.group(2))
        century = 1900 if y_int >= TWO_DIGIT_YEAR_CUTOFF else 2000
        return str(century + y_int)

    if strict:
        raise ValueError(f"Could not normalize year: {val}")
    return None


def normalize_ticker(val: Optional[str], strict: bool = False) -> Optional[str]:
    """Normalize stock ticker symbol.

    Performs:
    - Strips leading/trailing whitespace
    - Converts to uppercase
    - Strips exchange prefixes (e.g. 'NSE:', 'BSE:')
    - Strips exchange suffixes (e.g. '.NS', '.BO')
    - Corrects known dataset typos (e.g. 'AGTL' -> 'ATGL')
    - Preserves valid characters: letters, digits, '-', '&'

    Args:
        val: Input ticker string.
        strict: If True, raises ValueError on invalid input; otherwise returns None.

    Returns:
        Normalized ticker string or None.
    """
    if val is None:
        if strict:
            raise ValueError("Ticker cannot be None")
        return None

    s = str(val).strip().upper()
    if not s:
        if strict:
            raise ValueError("Ticker cannot be empty")
        return None

    # Remove prefixes like 'NSE:', 'BSE:'
    s = re.sub(r"^(NSE|BSE):", "", s)

    # Remove suffixes like '.NS', '.BO', '.BSE'
    s = re.sub(r"\.(NS|BO|BSE)$", "", s)

    # Clean stray spaces
    s = s.strip()

    # Apply typo dictionary
    if s in TICKER_CORRECTIONS:
        s = TICKER_CORRECTIONS[s]

    # Validate ticker structure (letters, digits, hyphen, ampersand)
    if not re.match(r"^[A-Z0-9&\-]+$", s):
        if strict:
            raise ValueError(f"Invalid ticker format: {val}")
        return None

    return s

