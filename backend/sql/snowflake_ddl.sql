-- =====================================================================
-- Snowflake DDL - AI Personal Finance Intelligence Platform
-- =====================================================================
-- These CREATE TABLE statements are executed automatically by
-- repositories.snowflake_repository.SnowflakeRepository.ensure_objects().
--
-- Warehouse / Database / Schema creation is handled separately in Python
-- (it needs account-level identifiers from config/settings.py), but for
-- manual reference the equivalent statements are:
--
--   CREATE WAREHOUSE IF NOT EXISTS COMPUTE_WH
--       WAREHOUSE_SIZE = 'XSMALL'
--       AUTO_SUSPEND = 60
--       AUTO_RESUME = TRUE
--       INITIALLY_SUSPENDED = TRUE;
--
--   CREATE DATABASE IF NOT EXISTS PERSONAL_FINANCE_DB;
--
--   CREATE SCHEMA IF NOT EXISTS PERSONAL_FINANCE_DB.PUBLIC;
--
-- Each statement below MUST be terminated with a semicolon - the
-- repository splits this file on ";" and runs each statement.
-- =====================================================================

-- ---------------------------------------------------------------------
-- TRANSACTIONS: canonical transaction-level fact table (ETL output)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS TRANSACTIONS (
    transaction_id        VARCHAR(32)     PRIMARY KEY,
    transaction_date      DATE            NOT NULL,
    transaction_datetime  TIMESTAMP_NTZ   NOT NULL,
    year                  INTEGER         NOT NULL,
    month                 INTEGER         NOT NULL,
    year_month            VARCHAR(7)      NOT NULL,
    category              VARCHAR(100)    NOT NULL,
    type                  VARCHAR(10)     NOT NULL,
    account               VARCHAR(50)     NOT NULL,
    amount                FLOAT           NOT NULL,
    currency              VARCHAR(10)     NOT NULL,
    tags                  VARCHAR(200),
    source                VARCHAR(50),
    ingested_at           TIMESTAMP_NTZ
);

-- ---------------------------------------------------------------------
-- MONTHLY_SUMMARY: one row per calendar month, derived from DuckDB
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS MONTHLY_SUMMARY (
    year_month            VARCHAR(7)      PRIMARY KEY,
    total_income          FLOAT           NOT NULL,
    total_expense         FLOAT           NOT NULL,
    net                    FLOAT           NOT NULL,
    savings_rate_pct       FLOAT,
    transaction_count      INTEGER         NOT NULL,
    generated_at           TIMESTAMP_NTZ
);

-- ---------------------------------------------------------------------
-- BUDGET_PLANS: user-defined per-category monthly budgets
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS BUDGET_PLANS (
    budget_id              VARCHAR(36)     PRIMARY KEY,
    category               VARCHAR(100)    NOT NULL,
    monthly_limit          FLOAT           NOT NULL,
    period                 VARCHAR(7),
    currency               VARCHAR(10)     DEFAULT 'BYN',
    created_at             TIMESTAMP_NTZ,
    updated_at             TIMESTAMP_NTZ
);

-- ---------------------------------------------------------------------
-- AI_REPORTS: cached LLM insight reports (AI Mode)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS AI_REPORTS (
    report_id              VARCHAR(36)     PRIMARY KEY,
    report_type            VARCHAR(50),
    query_hash             VARCHAR(64),
    metadata_snapshot      VARIANT,
    prompt                 TEXT,
    response               TEXT,
    model                  VARCHAR(100),
    created_at             TIMESTAMP_NTZ
);

-- ---------------------------------------------------------------------
-- FIRE_SIMULATIONS: saved FIRE Planner scenarios
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS FIRE_SIMULATIONS (
    simulation_id          VARCHAR(36)     PRIMARY KEY,
    params                 VARIANT,
    results                VARIANT,
    created_at             TIMESTAMP_NTZ
);
