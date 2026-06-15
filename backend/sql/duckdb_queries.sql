-- =====================================================================
-- DuckDB Analytics Layer - Reference Queries
-- =====================================================================
-- These mirror the SQL executed by analytics/duckdb_engine.py.
-- Provided for documentation / manual exploration via the DuckDB CLI:
--
--   duckdb data/duckdb/personal_finance.duckdb
--
-- Assumes the `transactions` table has already been populated by the
-- ETL pipeline (scripts/run_etl.py).
-- =====================================================================

-- 1. Monthly summary: income, expense, net, savings rate, tx count
SELECT
    year_month,
    SUM(CASE WHEN type = 'Income'  THEN amount ELSE 0 END) AS total_income,
    SUM(CASE WHEN type = 'Expense' THEN amount ELSE 0 END) AS total_expense,
    SUM(CASE WHEN type = 'Income'  THEN amount ELSE -amount END) AS net,
    COUNT(*) AS transaction_count
FROM transactions
GROUP BY year_month
ORDER BY year_month;

-- 2. Category breakdown (overall)
SELECT
    category,
    type,
    SUM(amount) AS total_amount,
    COUNT(*) AS transaction_count,
    AVG(amount) AS avg_amount
FROM transactions
GROUP BY category, type
ORDER BY total_amount DESC;

-- 3. Top 5 expense categories
SELECT category, SUM(amount) AS total_amount, COUNT(*) AS transaction_count
FROM transactions
WHERE type = 'Expense'
GROUP BY category
ORDER BY total_amount DESC
LIMIT 5;

-- 4. Month-over-month trend with 3-month rolling average expense
WITH monthly AS (
    SELECT
        year_month,
        SUM(CASE WHEN type = 'Income'  THEN amount ELSE 0 END) AS total_income,
        SUM(CASE WHEN type = 'Expense' THEN amount ELSE 0 END) AS total_expense
    FROM transactions
    GROUP BY year_month
)
SELECT
    year_month,
    total_income,
    total_expense,
    total_income - total_expense AS net,
    ROUND(100.0 * (total_expense - LAG(total_expense) OVER (ORDER BY year_month))
        / NULLIF(LAG(total_expense) OVER (ORDER BY year_month), 0), 2) AS expense_mom_change_pct,
    ROUND(AVG(total_expense) OVER (
        ORDER BY year_month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    ), 2) AS expense_3mo_avg
FROM monthly
ORDER BY year_month;

-- 5. Account breakdown
SELECT
    account,
    SUM(CASE WHEN type = 'Expense' THEN amount ELSE 0 END) AS total_expense,
    SUM(CASE WHEN type = 'Income'  THEN amount ELSE 0 END) AS total_income,
    COUNT(*) AS transaction_count
FROM transactions
GROUP BY account
ORDER BY total_expense DESC;

-- 6. Anomaly detection: category-months with |z-score| >= 2
WITH cat_month AS (
    SELECT category, year_month, SUM(amount) AS month_total
    FROM transactions
    WHERE type = 'Expense'
    GROUP BY category, year_month
),
cat_stats AS (
    SELECT category, AVG(month_total) AS mean_total, STDDEV_SAMP(month_total) AS std_total
    FROM cat_month
    GROUP BY category
)
SELECT
    cm.category,
    cm.year_month,
    ROUND(cm.month_total, 2) AS month_total,
    ROUND(cs.mean_total, 2) AS category_mean,
    ROUND((cm.month_total - cs.mean_total) / NULLIF(cs.std_total, 0), 2) AS z_score
FROM cat_month cm
JOIN cat_stats cs USING (category)
WHERE cs.std_total > 0
  AND ABS((cm.month_total - cs.mean_total) / cs.std_total) >= 2
ORDER BY ABS((cm.month_total - cs.mean_total) / cs.std_total) DESC;
