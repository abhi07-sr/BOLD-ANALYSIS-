"""Unit tests for ETL normaliser functions (35+ tests: 20 year, 15 ticker)."""

import pytest
from src.etl.normaliser import normalize_ticker, normalize_year


# ============================================================================
# 20 Unit Tests for normalize_year()
# ============================================================================

def test_year_01_standard_string_4digit():
    assert normalize_year("2021") == "2021"


def test_year_02_integer_input():
    assert normalize_year(2023) == "2023"


def test_year_03_float_integer_equivalent():
    assert normalize_year(2019.0) == "2019"


def test_year_04_float_with_decimal():
    assert normalize_year("2024.5") == "2024"


def test_year_05_month_year_mar():
    assert normalize_year("Mar 2024") == "2024"


def test_year_06_month_year_dec():
    assert normalize_year("Dec 2012") == "2012"


def test_year_07_month_year_jun():
    assert normalize_year("Jun 2015") == "2015"


def test_year_08_month_year_sep():
    assert normalize_year("Sep 2011") == "2011"


def test_year_09_month_dash_2digit_20s():
    assert normalize_year("Mar-22") == "2022"


def test_year_10_month_dash_2digit_10s():
    assert normalize_year("Mar-13") == "2013"


def test_year_11_annotated_month_year_9m():
    assert normalize_year("Mar 2016 9m") == "2016"


def test_year_12_annotated_month_year_15m():
    assert normalize_year("Mar 2023 15") == "2023"


def test_year_13_trailing_twelve_months_ttm():
    assert normalize_year("TTM") == "TTM"


def test_year_14_fiscal_year_prefix_fy4digit():
    assert normalize_year("FY2022") == "2022"


def test_year_15_fiscal_year_prefix_fy2digit():
    assert normalize_year("FY24") == "2024"


def test_year_16_fiscal_year_range_hyphenated():
    assert normalize_year("2020-21") == "2021"


def test_year_17_full_date_dmy():
    assert normalize_year("31-03-2023") == "2023"


def test_year_18_leading_trailing_whitespace():
    assert normalize_year("   2018   ") == "2018"


def test_year_19_none_handling():
    assert normalize_year(None) is None
    with pytest.raises(ValueError):
        normalize_year(None, strict=True)


def test_year_20_invalid_and_empty_string():
    assert normalize_year("") is None
    assert normalize_year("   ") is None
    with pytest.raises(ValueError):
        normalize_year("", strict=True)


# ============================================================================
# 15 Unit Tests for normalize_ticker()
# ============================================================================

def test_ticker_01_standard_uppercase():
    assert normalize_ticker("ABB") == "ABB"


def test_ticker_02_lowercase_to_uppercase():
    assert normalize_ticker("infy") == "INFY"


def test_ticker_03_mixed_case():
    assert normalize_ticker("Tcs") == "TCS"


def test_ticker_04_leading_trailing_whitespace():
    assert normalize_ticker("  RELIANCE  ") == "RELIANCE"


def test_ticker_05_nse_prefix_stripping():
    assert normalize_ticker("NSE:HDFCBANK") == "HDFCBANK"


def test_ticker_06_bse_prefix_stripping():
    assert normalize_ticker("BSE:ITC") == "ITC"


def test_ticker_07_ns_suffix_stripping():
    assert normalize_ticker("SBIN.NS") == "SBIN"


def test_ticker_08_bo_suffix_stripping():
    assert normalize_ticker("WIPRO.BO") == "WIPRO"


def test_ticker_09_preserve_hyphen():
    assert normalize_ticker("BAJAJ-AUTO") == "BAJAJ-AUTO"


def test_ticker_10_preserve_ampersand():
    assert normalize_ticker("M&M") == "M&M"


def test_ticker_11_preserve_ampersand_financial():
    assert normalize_ticker("L&TFH") == "L&TFH"


def test_ticker_12_typo_correction_agtl_to_atgl():
    assert normalize_ticker("AGTL") == "ATGL"


def test_ticker_13_alphanumeric_ticker():
    assert normalize_ticker("3MINDIA") == "3MINDIA"


def test_ticker_14_none_handling():
    assert normalize_ticker(None) is None
    with pytest.raises(ValueError):
        normalize_ticker(None, strict=True)


def test_ticker_15_empty_and_invalid_ticker():
    assert normalize_ticker("") is None
    assert normalize_ticker("   ") is None
    with pytest.raises(ValueError):
        normalize_ticker("", strict=True)
    with pytest.raises(ValueError):
        normalize_ticker("BAD TICKER!", strict=True)

