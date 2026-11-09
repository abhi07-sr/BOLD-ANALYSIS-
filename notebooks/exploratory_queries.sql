-- ============================================================================
-- Sprint 01 Wrap-Up: 10 Exploratory & Verification SQL Queries (nifty100.db)
-- ============================================================================

-- Query 1: Total Companies and Sector Distribution
SELECT 
    COALESCE(s.broad_sector, 'Unclassified') AS sector,
    COUNT(c.id) AS company_count,
    ROUND(SUM(COALESCE(s.index_weight_pct, 0)), 2) AS total_index_weight
FROM companies c
LEFT JOIN sectors s ON c.id = s.company_id
GROUP BY s.broad_sector
ORDER BY total_index_weight DESC;

-- Query 2: Top 10 Companies by Sales (Latest Fiscal Year)
SELECT 
    c.id AS ticker,
    c.company_name,
    p.year,
    p.sales AS sales_in_crores,
    p.operating_profit,
    p.opm_percentage
FROM companies c
JOIN profitandloss p ON c.id = p.company_id
WHERE p.year != 'TTM'
ORDER BY p.sales DESC
LIMIT 10;

-- Query 3: Top 10 Companies by Net Profit (Latest Fiscal Year)
SELECT 
    c.id AS ticker,
    c.company_name,
    p.year,
    p.net_profit AS net_profit_crores,
    p.eps,
    p.tax_percentage
FROM companies c
JOIN profitandloss p ON c.id = p.company_id
WHERE p.year != 'TTM'
ORDER BY p.net_profit DESC
LIMIT 10;

-- Query 4: Top 10 Companies with Highest Operating Margin (OPM > 30%)
SELECT 
    c.id AS ticker,
    c.company_name,
    p.year,
    p.sales,
    p.operating_profit,
    p.opm_percentage
FROM companies c
JOIN profitandloss p ON c.id = p.company_id
WHERE p.sales > 5000 AND p.opm_percentage > 30 AND p.year != 'TTM'
ORDER BY p.opm_percentage DESC
LIMIT 10;

-- Query 5: Balance Sheet Verification: Assets vs Liabilities Check
SELECT 
    b.company_id,
    b.year,
    b.total_assets,
    b.total_liabilities,
    ROUND(ABS(b.total_assets - b.total_liabilities), 2) AS diff,
    ROUND(ABS(b.total_assets - b.total_liabilities) * 100.0 / NULLIF(b.total_assets, 0), 3) AS diff_pct
FROM balancesheet b
WHERE b.total_assets > 0
ORDER BY diff_pct DESC
LIMIT 10;

-- Query 6: Cash Flow Operations vs Net Profit (Quality of Earnings)
SELECT 
    c.id AS ticker,
    c.company_name,
    cf.year,
    p.net_profit,
    cf.operating_activity AS cash_from_operations,
    ROUND(cf.operating_activity - p.net_profit, 2) AS ocf_minus_pat
FROM companies c
JOIN profitandloss p ON c.id = p.company_id
JOIN cashflow cf ON c.id = cf.company_id AND p.year = cf.year
WHERE p.net_profit > 1000
ORDER BY ocf_minus_pat DESC
LIMIT 10;

-- Query 7: Valuation Multiples by Broad Sector (Market Cap & PE)
SELECT 
    s.broad_sector,
    COUNT(DISTINCT c.id) AS companies_count,
    ROUND(AVG(m.pe_ratio), 2) AS avg_pe_ratio,
    ROUND(AVG(m.pb_ratio), 2) AS avg_pb_ratio,
    ROUND(AVG(m.ev_ebitda), 2) AS avg_ev_ebitda,
    ROUND(SUM(m.market_cap_crore), 2) AS total_market_cap_cr
FROM companies c
JOIN sectors s ON c.id = s.company_id
JOIN market_cap m ON c.id = m.company_id
WHERE m.year = '2024'
GROUP BY s.broad_sector
ORDER BY total_market_cap_cr DESC;

-- Query 8: High Quality Companies: High ROE (>20%) & Low Debt-to-Equity (<0.5)
SELECT 
    c.id AS ticker,
    c.company_name,
    c.roce_percentage,
    c.roe_percentage,
    fr.debt_to_equity,
    fr.interest_coverage
FROM companies c
JOIN financial_ratios fr ON c.id = fr.company_id
WHERE c.roe_percentage > 20 AND fr.debt_to_equity < 0.5 AND fr.year = 'Mar 2024'
ORDER BY c.roe_percentage DESC
LIMIT 10;

-- Query 9: Stock Price Performance and Volatility Summary
SELECT 
    sp.company_id AS ticker,
    c.company_name,
    MIN(sp.low_price) AS lowest_price_5y,
    MAX(sp.high_price) AS highest_price_5y,
    ROUND(AVG(sp.close_price), 2) AS avg_close_price,
    ROUND(MAX(sp.high_price) / NULLIF(MIN(sp.low_price), 0), 2) AS price_multiple_5y
FROM stock_prices sp
JOIN companies c ON sp.company_id = c.id
GROUP BY sp.company_id, c.company_name
ORDER BY price_multiple_5y DESC
LIMIT 10;

-- Query 10: Historical Financial Statement Coverage & Completeness per Company
SELECT 
    c.id AS ticker,
    c.company_name,
    COUNT(DISTINCT p.year) AS pnl_years_count,
    COUNT(DISTINCT b.year) AS bs_years_count,
    COUNT(DISTINCT cf.year) AS cf_years_count,
    COUNT(sp.date) AS stock_price_days_count
FROM companies c
LEFT JOIN profitandloss p ON c.id = p.company_id
LEFT JOIN balancesheet b ON c.id = b.company_id
LEFT JOIN cashflow cf ON c.id = cf.company_id
LEFT JOIN stock_prices sp ON c.id = sp.company_id
GROUP BY c.id, c.company_name
ORDER BY pnl_years_count ASC
LIMIT 10;

