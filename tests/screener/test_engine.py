"""Unit tests for the Screener Engine and all 6 preset screeners."""

import os
import sqlite3
import openpyxl
import pandas as pd
import pytest

from src.screener.engine import (
    apply_threshold_filters,
    build_screener_dataset,
    compute_composite_quality_score,
    export_screener_excel,
    load_screener_config,
    passes_single_filter,
    run_all_presets,
    run_preset,
)

DB_PATH = "nifty100.db"


@pytest.fixture(scope="module")
def db_conn():
    conn = sqlite3.connect(DB_PATH)
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def screener_data(db_conn):
    master = build_screener_dataset(db_conn)
    scored = compute_composite_quality_score(master)
    return scored


def test_load_screener_config():
    """Verify screener_config.yaml loads properly and contains all presets and metric thresholds."""
    cfg = load_screener_config()
    assert "presets" in cfg
    assert "metric_thresholds" in cfg
    assert "composite_score_weights" in cfg

    presets = cfg["presets"]
    expected_presets = [
        "quality_compounder",
        "value_pick",
        "growth_accelerator",
        "dividend_champion",
        "debt_free_blue_chip",
        "turnaround_watch",
    ]
    for p in expected_presets:
        assert p in presets, f"Missing preset: {p}"


def test_build_screener_dataset(db_conn):
    """Verify master screener dataset contains all 92 companies and expected columns."""
    df = build_screener_dataset(db_conn)
    assert len(df) == 92, f"Expected 92 companies, got {len(df)}"

    required_cols = [
        "company_id",
        "company_name",
        "broad_sector",
        "return_on_equity_pct",
        "debt_to_equity",
        "interest_coverage",
        "free_cash_flow_cr",
        "revenue_cagr_5yr",
        "pat_cagr_5yr",
        "sales",
        "net_profit",
        "pe_ratio",
        "pb_ratio",
        "dividend_yield_pct",
        "revenue_cagr_3yr",
        "prior_de",
    ]
    for c in required_cols:
        assert c in df.columns, f"Missing column in screener dataset: {c}"


def test_filter_financials_de_exemption():
    """Verify that Financials broad sector is exempted from D/E max threshold."""
    # Financials bank with high D/E
    passed_fin = passes_single_filter(
        val=8.5,
        rule={"max": 1.0},
        is_financial=True,
        is_debt_free=False,
        metric_name="debt_to_equity",
    )
    assert passed_fin is True, "Financials company should pass D/E max filter"

    # Non-financial company with high D/E
    passed_non_fin = passes_single_filter(
        val=8.5,
        rule={"max": 1.0},
        is_financial=False,
        is_debt_free=False,
        metric_name="debt_to_equity",
    )
    assert passed_non_fin is False, "Non-financial company with high D/E should fail D/E max filter"


def test_filter_debt_free_icr_bypass():
    """Verify that Debt Free companies pass any ICR minimum threshold."""
    # Debt-free company with None ICR
    passed = passes_single_filter(
        val=None,
        rule={"min": 5.0},
        is_financial=False,
        is_debt_free=True,
        metric_name="interest_coverage",
    )
    assert passed is True, "Debt-free company should pass ICR min filter"


def test_all_15_metrics_filtering(screener_data):
    """Test filtering across all 15 supported metrics."""
    metrics_to_test = [
        ("return_on_equity_pct", {"min": 10.0}),
        ("debt_to_equity", {"max": 1.5}),
        ("free_cash_flow_cr", {"min": 100.0}),
        ("revenue_cagr_5yr", {"min": 5.0}),
        ("pat_cagr_5yr", {"min": 5.0}),
        ("operating_profit_margin_pct", {"min": 10.0}),
        ("pe_ratio", {"max": 50.0}),
        ("pb_ratio", {"max": 10.0}),
        ("dividend_yield_pct", {"min": 0.5}),
        ("interest_coverage", {"min": 2.0}),
        ("market_cap_crore", {"min": 10000.0}),
        ("net_profit", {"min": 500.0}),
        ("eps_cagr_5yr", {"min": 5.0}),
        ("asset_turnover", {"min": 0.5}),
        ("sales", {"min": 2000.0}),
    ]
    for metric, rule in metrics_to_test:
        filtered = apply_threshold_filters(screener_data, {metric: rule})
        assert len(filtered) > 0, f"Filter on {metric} returned 0 results"
        assert len(filtered) <= len(screener_data)


def test_composite_quality_score_bounds(screener_data):
    """Verify composite quality scores are bounded within [0, 100]."""
    scores = screener_data["composite_quality_score"]
    assert scores.notna().all(), "Composite score contains NaNs"
    assert (scores >= 0.0).all(), "Found composite score < 0"
    assert (scores <= 100.0).all(), "Found composite score > 100"
    assert scores.max() > scores.min(), "Composite scores have no variance"


def test_preset_quality_compounder(screener_data):
    """Verify Quality Compounder preset returns between 5 and 50 companies."""
    res = run_preset(screener_data, "quality_compounder")
    count = len(res)
    assert 5 <= count <= 50, f"Quality Compounder returned {count} companies, expected between 5 and 50"
    # Spot-check top company criteria
    top = res.iloc[0]
    assert top["return_on_equity_pct"] > 15.0
    assert top["free_cash_flow_cr"] > 0.0
    assert top["revenue_cagr_5yr"] > 10.0


def test_preset_value_pick(screener_data):
    """Verify Value Pick preset returns between 5 and 50 companies."""
    res = run_preset(screener_data, "value_pick")
    count = len(res)
    assert 5 <= count <= 50, f"Value Pick returned {count} companies, expected between 5 and 50"


def test_preset_growth_accelerator(screener_data):
    """Verify Growth Accelerator preset returns between 5 and 50 companies."""
    res = run_preset(screener_data, "growth_accelerator")
    count = len(res)
    assert 5 <= count <= 50, f"Growth Accelerator returned {count} companies, expected between 5 and 50"


def test_preset_dividend_champion(screener_data):
    """Verify Dividend Champion preset returns between 5 and 50 companies."""
    res = run_preset(screener_data, "dividend_champion")
    count = len(res)
    assert 5 <= count <= 50, f"Dividend Champion returned {count} companies, expected between 5 and 50"


def test_preset_debt_free_blue_chip(screener_data):
    """Verify Debt-Free Blue Chip preset returns between 5 and 50 companies."""
    res = run_preset(screener_data, "debt_free_blue_chip")
    count = len(res)
    assert 5 <= count <= 50, f"Debt-Free Blue Chip returned {count} companies, expected between 5 and 50"


def test_preset_turnaround_watch(screener_data):
    """Verify Turnaround Watch preset returns between 5 and 50 companies."""
    res = run_preset(screener_data, "turnaround_watch")
    count = len(res)
    assert 5 <= count <= 50, f"Turnaround Watch returned {count} companies, expected between 5 and 50"


def test_run_all_presets(db_conn):
    """Verify run_all_presets returns all 6 presets and each has 5-50 companies."""
    all_res = run_all_presets(db_conn)
    assert len(all_res) == 6
    for pkey, df_res in all_res.items():
        assert 5 <= len(df_res) <= 50, f"Preset {pkey} returned {len(df_res)} companies"


def test_screener_excel_export(screener_data):
    """Verify export_screener_excel creates a workbook with 6 sheets and proper column count."""
    presets = {
        "quality_compounder": run_preset(screener_data, "quality_compounder"),
        "value_pick": run_preset(screener_data, "value_pick"),
        "growth_accelerator": run_preset(screener_data, "growth_accelerator"),
        "dividend_champion": run_preset(screener_data, "dividend_champion"),
        "debt_free_blue_chip": run_preset(screener_data, "debt_free_blue_chip"),
        "turnaround_watch": run_preset(screener_data, "turnaround_watch"),
    }
    out_file = "output/test_screener_export.xlsx"
    path = export_screener_excel(presets, out_file)
    assert os.path.exists(path)

    wb = openpyxl.load_workbook(path)
    assert len(wb.sheetnames) == 6
    for sname in wb.sheetnames:
        sheet = wb[sname]
        assert sheet.max_row >= 5
        assert sheet.max_column == 21
    if os.path.exists(out_file):
        os.remove(out_file)

