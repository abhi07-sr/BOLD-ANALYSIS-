"""Unit and performance tests for Streamlit dashboard database loader utility."""

import time
import pandas as pd
import pytest

from src.dashboard.utils.db import (
    clean_company_name,
    get_all_screener_data,
    get_annual_reports,
    get_bs,
    get_capital_allocation,
    get_cf,
    get_companies,
    get_home_kpis,
    get_peer_percentiles,
    get_peers,
    get_pl,
    get_prosandcons,
    get_ratios,
    get_sectors,
    get_stock_price_summary,
    get_valuation,
)


class TestDashboardDBLoader:
    """Validate query functions return expected DataFrames and dictionary structures."""

    def test_get_companies(self):
        df = get_companies()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 92
        assert "id" in df.columns
        assert "company_name" in df.columns
        assert "broad_sector" in df.columns

    def test_get_ratios_single_company(self):
        df = get_ratios(ticker="ABB")
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert "return_on_equity_pct" in df.columns
        assert "operating_profit_margin_pct" in df.columns
        # TTM rows excluded by default
        assert "TTM" not in df["year"].values

    def test_get_financial_statements(self):
        pl = get_pl("TCS")
        bs = get_bs("TCS")
        cf = get_cf("TCS")

        assert isinstance(pl, pd.DataFrame) and not pl.empty
        assert isinstance(bs, pd.DataFrame) and not bs.empty
        assert isinstance(cf, pd.DataFrame) and not cf.empty

        assert "sales" in pl.columns
        assert "net_profit" in pl.columns
        assert "total_assets" in bs.columns or "equity_capital" in bs.columns
        assert "operating_activity" in cf.columns

    def test_get_sectors(self):
        df = get_sectors()
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert "broad_sector" in df.columns
        assert "company_count" in df.columns
        assert "total_weight" in df.columns
        assert df["company_count"].sum() == 92

    def test_get_peers(self):
        groups = get_peers()
        assert isinstance(groups, pd.DataFrame)
        assert "peer_group_name" in groups.columns

        auto_peers = get_peers("Automobiles")
        assert isinstance(auto_peers, pd.DataFrame)
        assert not auto_peers.empty
        assert "is_benchmark" in auto_peers.columns
        assert auto_peers["is_benchmark"].sum() >= 1

    def test_get_valuation(self):
        df = get_valuation()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 92
        assert "company_id" in df.columns
        assert "flag" in df.columns
        assert "P/E" in df.columns

    def test_get_prosandcons(self):
        pc = get_prosandcons("TCS")
        assert isinstance(pc, dict)
        assert "pros" in pc and "cons" in pc
        assert isinstance(pc["pros"], list)
        assert isinstance(pc["cons"], list)

    def test_get_annual_reports(self):
        docs = get_annual_reports("ABB")
        assert isinstance(docs, pd.DataFrame)
        assert not docs.empty
        assert "year" in docs.columns
        assert "url" in docs.columns

    def test_get_capital_allocation(self):
        df = get_capital_allocation()
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert "pattern_label" in df.columns
        assert "cfo_sign" in df.columns

    def test_get_home_kpis(self):
        kpis = get_home_kpis("2024")
        assert isinstance(kpis, dict)
        required_keys = ["avg_roe", "median_pe", "median_de", "total_companies", "median_rev_cagr_5yr", "debt_free_count"]
        for k in required_keys:
            assert k in kpis, f"Missing key {k} in home KPIs"
        assert kpis["total_companies"] == 92

    def test_get_stock_price_summary(self):
        summary = get_stock_price_summary("ABB")
        assert isinstance(summary, dict)
        assert "current_price" in summary
        assert "high_52w" in summary
        assert "low_52w" in summary
        assert "market_cap_crore" in summary

    def test_clean_company_name(self):
        raw = "Asian Paints\nIndian Multi-National Paint and Coatings Company"
        clean = clean_company_name(raw)
        assert clean == "Asian Paints"


class TestPerformanceConstraints:
    """Verify performance requirements for dashboard loading."""

    def test_company_profile_load_time_under_3_seconds(self):
        # Time the data retrieval sequence required to render Company Profile
        t0 = time.time()
        _comps = get_companies()
        _ratios = get_ratios("TCS")
        _pl = get_pl("TCS")
        _bs = get_bs("TCS")
        _cf = get_cf("TCS")
        _prices = get_stock_price_summary("TCS")
        _pc = get_prosandcons("TCS")
        load_time = time.time() - t0

        assert load_time < 3.0, f"Company Profile data loading took {load_time:.3f}s, exceeding 3.0s limit"
