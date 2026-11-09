-- SQLite Database Schema for Nifty 100 Financial Data (nifty100.db)
-- Enforce Foreign Key Constraints
PRAGMA foreign_keys = ON;

-- 1. Companies Table (Parent Table)
DROP TABLE IF EXISTS companies;
CREATE TABLE companies (
    id TEXT PRIMARY KEY,
    company_logo TEXT,
    company_name TEXT NOT NULL,
    chart_link TEXT,
    about_company TEXT,
    website TEXT,
    nse_profile TEXT,
    bse_profile TEXT,
    face_value REAL,
    book_value REAL,
    roce_percentage REAL,
    roe_percentage REAL
);

-- 2. Profit & Loss Table
DROP TABLE IF EXISTS profitandloss;
CREATE TABLE profitandloss (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    year TEXT NOT NULL,
    sales REAL,
    expenses REAL,
    operating_profit REAL,
    opm_percentage REAL,
    other_income REAL,
    interest REAL,
    depreciation REAL,
    profit_before_tax REAL,
    tax_percentage REAL,
    net_profit REAL,
    eps REAL,
    dividend_payout REAL,
    UNIQUE(company_id, year)
);

-- 3. Balance Sheet Table
DROP TABLE IF EXISTS balancesheet;
CREATE TABLE balancesheet (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    year TEXT NOT NULL,
    equity_capital REAL,
    reserves REAL,
    borrowings REAL,
    other_liabilities REAL,
    total_liabilities REAL,
    fixed_assets REAL,
    cwip REAL,
    investments REAL,
    other_asset REAL,
    total_assets REAL,
    UNIQUE(company_id, year)
);

-- 4. Cash Flow Table
DROP TABLE IF EXISTS cashflow;
CREATE TABLE cashflow (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    year TEXT NOT NULL,
    operating_activity REAL,
    investing_activity REAL,
    financing_activity REAL,
    net_cash_flow REAL,
    UNIQUE(company_id, year)
);

-- 5. Financial Ratios Table
DROP TABLE IF EXISTS financial_ratios;
CREATE TABLE financial_ratios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    year TEXT NOT NULL,
    net_profit_margin_pct REAL,
    operating_profit_margin_pct REAL,
    return_on_equity_pct REAL,
    return_on_assets_pct REAL,
    return_on_capital_employed_pct REAL,
    debt_to_equity REAL,
    high_leverage_flag INTEGER DEFAULT 0,
    interest_coverage REAL,
    icr_label TEXT,
    asset_turnover REAL,
    free_cash_flow_cr REAL,
    capex_cr REAL,
    earnings_per_share REAL,
    book_value_per_share REAL,
    dividend_payout_ratio_pct REAL,
    total_debt_cr REAL,
    cash_from_operations_cr REAL,
    revenue_cagr_5yr REAL,
    revenue_cagr_5yr_flag TEXT,
    pat_cagr_5yr REAL,
    pat_cagr_5yr_flag TEXT,
    eps_cagr_5yr REAL,
    eps_cagr_5yr_flag TEXT,
    cfo_quality_score REAL,
    capex_intensity_label TEXT,
    composite_quality_score REAL,
    UNIQUE(company_id, year)
);

-- 6. Stock Prices Table
DROP TABLE IF EXISTS stock_prices;
CREATE TABLE stock_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    date TEXT NOT NULL,
    open_price REAL,
    high_price REAL,
    low_price REAL,
    close_price REAL,
    volume INTEGER,
    adjusted_close REAL,
    UNIQUE(company_id, date)
);

-- 7. Documents Table (Annual Reports)
DROP TABLE IF EXISTS documents;
CREATE TABLE documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    year TEXT NOT NULL,
    annual_report TEXT,
    UNIQUE(company_id, year)
);

-- 8. Sectors Table
DROP TABLE IF EXISTS sectors;
CREATE TABLE sectors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    broad_sector TEXT,
    sub_sector TEXT,
    index_weight_pct REAL,
    market_cap_category TEXT,
    UNIQUE(company_id)
);

-- 9. Peer Groups Table
DROP TABLE IF EXISTS peer_groups;
CREATE TABLE peer_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    peer_group_name TEXT NOT NULL,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    is_benchmark INTEGER DEFAULT 0,
    UNIQUE(peer_group_name, company_id)
);

-- 10. Market Capitalization Table
DROP TABLE IF EXISTS market_cap;
CREATE TABLE market_cap (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    year TEXT NOT NULL,
    market_cap_crore REAL,
    enterprise_value_crore REAL,
    pe_ratio REAL,
    pb_ratio REAL,
    ev_ebitda REAL,
    dividend_yield_pct REAL,
    UNIQUE(company_id, year)
);

-- 11. Analysis Table
DROP TABLE IF EXISTS analysis;
CREATE TABLE analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    compounded_sales_growth TEXT,
    compounded_profit_growth TEXT,
    stock_price_cagr TEXT,
    roe TEXT
);

-- 12. Pros & Cons Table
DROP TABLE IF EXISTS prosandcons;
CREATE TABLE prosandcons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    pros TEXT,
    cons TEXT
);

-- 13. Peer Percentiles Table
DROP TABLE IF EXISTS peer_percentiles;
CREATE TABLE peer_percentiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    peer_group_name TEXT NOT NULL,
    metric TEXT NOT NULL,
    value REAL,
    percentile_rank REAL,
    year TEXT NOT NULL,
    UNIQUE(company_id, peer_group_name, metric, year)
);

-- Performance Indexes
CREATE INDEX IF NOT EXISTS idx_pnl_comp_yr ON profitandloss(company_id, year);
CREATE INDEX IF NOT EXISTS idx_bs_comp_yr ON balancesheet(company_id, year);
CREATE INDEX IF NOT EXISTS idx_cf_comp_yr ON cashflow(company_id, year);
CREATE INDEX IF NOT EXISTS idx_prices_comp_dt ON stock_prices(company_id, date);
CREATE INDEX IF NOT EXISTS idx_ratios_comp_yr ON financial_ratios(company_id, year);
CREATE INDEX IF NOT EXISTS idx_peer_perc_comp ON peer_percentiles(company_id, peer_group_name, metric);
