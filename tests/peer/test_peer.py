"""Unit tests for the Peer Comparison Engine and Radar Charts."""

import os
import sqlite3
import openpyxl
import pandas as pd
import pytest

from src.analytics.peer import (
    calc_percent_rank,
    compute_peer_percentiles,
    export_peer_comparison_excel,
    get_company_peer_group,
)

DB_PATH = "nifty100.db"


@pytest.fixture(scope="module")
def db_conn():
    conn = sqlite3.connect(DB_PATH)
    yield conn
    conn.close()


def test_percent_rank_formula():
    """Verify PERCENT_RANK calculation: (rank - 1) / (N - 1)."""
    s = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])
    ranks = calc_percent_rank(s, invert=False)
    assert ranks.iloc[0] == 0.0
    assert ranks.iloc[-1] == 1.0
    assert ranks.iloc[2] == 0.5


def test_inverted_de_percent_rank():
    """Verify that inverted ranking gives lower D/E the highest percentile rank."""
    de_series = pd.Series([0.05, 0.50, 1.20, 2.50])
    ranks = calc_percent_rank(de_series, invert=True)
    # Lowest debt (0.05) must have rank 1.0 (100%)
    assert ranks.iloc[0] == 1.0
    # Highest debt (2.50) must have rank 0.0 (0%)
    assert ranks.iloc[-1] == 0.0


def test_peer_groups_coverage(db_conn):
    """Verify exactly 11 peer groups exist in peer_groups table."""
    groups = [
        r[0]
        for r in db_conn.execute("SELECT DISTINCT peer_group_name FROM peer_groups ORDER BY peer_group_name").fetchall()
    ]
    assert len(groups) == 11, f"Expected 11 peer groups, got {len(groups)}: {groups}"


def test_peer_percentiles_table_population(db_conn):
    """Verify peer_percentiles table is populated with 560 records."""
    count = db_conn.execute("SELECT COUNT(*) FROM peer_percentiles").fetchone()[0]
    assert count == 560, f"Expected 560 rows in peer_percentiles, got {count}"

    # Verify distinct metrics
    metrics = [r[0] for r in db_conn.execute("SELECT DISTINCT metric FROM peer_percentiles").fetchall()]
    assert len(metrics) == 10, f"Expected 10 metrics, got {len(metrics)}"


def test_spot_check_it_services_roe_rank(db_conn):
    """Spot-check IT Services: Company with highest ROE must have ROE percentile rank = 1.0."""
    query = """
        SELECT company_id, value, percentile_rank
        FROM peer_percentiles
        WHERE peer_group_name = 'IT Services' AND metric = 'return_on_equity_pct'
        ORDER BY value DESC
    """
    rows = db_conn.execute(query).fetchall()
    assert len(rows) == 5, f"Expected 5 IT Services companies, got {len(rows)}"
    highest = rows[0]
    # In IT Services, TCS has highest ROE (~50.94%)
    assert highest[0] == "TCS"
    assert highest[2] == 1.0, f"Expected TCS ROE rank to be 1.0, got {highest[2]}"


def test_spot_check_fmcg_benchmark(db_conn):
    """Spot-check FMCG: Benchmark company must be designated and identifiable."""
    query = """
        SELECT company_id, is_benchmark
        FROM peer_groups
        WHERE peer_group_name = 'FMCG' AND is_benchmark = 1
    """
    benchmarks = db_conn.execute(query).fetchall()
    assert len(benchmarks) == 1, f"Expected 1 FMCG benchmark, got {len(benchmarks)}"
    assert benchmarks[0][0] == "HINDUNILVR", f"Expected HINDUNILVR as FMCG benchmark, got {benchmarks[0][0]}"


def test_unassigned_company_message(db_conn):
    """Verify companies not in any peer group return 'No peer group assigned' without error."""
    # ABB has no peer group
    msg = get_company_peer_group("ABB", db_conn)
    assert msg == "No peer group assigned"

    # TCS has IT Services peer group
    tcs_res = get_company_peer_group("TCS", db_conn)
    assert isinstance(tcs_res, dict)
    assert tcs_res["peer_group_name"] == "IT Services"


def test_peer_comparison_excel_structure():
    """Verify peer_comparison.xlsx exists and has exactly 11 sheets covering all 11 peer groups."""
    excel_path = "output/peer_comparison.xlsx"
    assert os.path.exists(excel_path), f"File not found: {excel_path}"

    wb = openpyxl.load_workbook(excel_path)
    sheet_names = wb.sheetnames
    assert len(sheet_names) == 11, f"Expected 11 sheets, got {len(sheet_names)}: {sheet_names}"

    for sname in sheet_names:
        sheet = wb[sname]
        # Check title and header row
        assert sheet.cell(row=1, column=1).value is not None
        # Check summary row at bottom has 'PEER MEDIAN'
        last_row = sheet.max_row
        median_label = sheet.cell(row=last_row, column=1).value
        assert median_label == "PEER MEDIAN", f"Sheet {sname} missing PEER MEDIAN in row {last_row}"


def test_radar_charts_generated():
    """Verify 92 radar charts are generated in reports/radar_charts/."""
    radar_dir = "reports/radar_charts"
    assert os.path.isdir(radar_dir), f"Directory not found: {radar_dir}"
    files = [f for f in os.listdir(radar_dir) if f.endswith("_radar.png")]
    assert len(files) == 92, f"Expected 92 radar chart files, got {len(files)}"
