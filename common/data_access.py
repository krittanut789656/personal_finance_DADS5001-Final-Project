"""
Data Access Layer (Streamlit caching)
======================================
This module is the ONLY place the Streamlit app talks to the Phase 2
backend (config, core, etl, analytics, repositories, profiling). It wires
the backend into Streamlit's caching model:

    @st.cache_resource  -> MongoDB connection, Snowflake connection, AI client
    @st.cache_data      -> Dataset loading, DuckDB queries, profiling results

All analytics aggregation is delegated to `DuckDBAnalytics` (mandatory
analytics engine). MongoDB/Snowflake are optional - if credentials are not
configured, the app falls back to the local CSV via the Phase 2 ETL
extract/transform pipeline and runs in "offline mode".
"""

from __future__ import annotations

from typing import Optional

import pandas as pd
import streamlit as st

import common.bootstrap  # noqa: F401  -- must run before backend imports

from core.logger import get_logger  # noqa: E402
from analytics.duckdb_engine import DuckDBAnalytics  # noqa: E402

logger = get_logger("streamlit_app")


# ======================================================================
# @st.cache_resource - connections & clients (created once per session)
# ======================================================================
@st.cache_resource(show_spinner="Connecting to MongoDB Atlas...")
def get_mongo_repo():
    """
    Return a connected `MongoRepository`, or `None` if MongoDB Atlas is not
    configured / unreachable. The app degrades gracefully to CSV + DuckDB
    only ("offline mode") when this returns None.
    """
    try:
        from repositories.mongo_repository import MongoRepository

        repo = MongoRepository()
        repo.get_client()  # forces connection + ping
        logger.info("MongoDB Atlas connection established")
        return repo
    except Exception as exc:  # noqa: BLE001
        logger.warning("MongoDB unavailable, running without it: %s", exc)
        return None


@st.cache_resource(show_spinner="Connecting to Snowflake...")
def get_snowflake_repo():
    """
    Return a connected `SnowflakeRepository`, or `None` if Snowflake is not
    configured / unreachable.
    """
    try:
        from repositories.snowflake_repository import SnowflakeRepository

        repo = SnowflakeRepository()
        repo.get_connection()
        logger.info("Snowflake connection established")
        return repo
    except Exception as exc:  # noqa: BLE001
        logger.warning("Snowflake unavailable, running without it: %s", exc)
        return None


@st.cache_resource(show_spinner="Starting DuckDB analytics engine...")
def get_duckdb_engine() -> DuckDBAnalytics:
    """
    Singleton in-memory DuckDB connection for this Streamlit session.

    DuckDB is the MANDATORY analytics engine: every aggregation/query on
    every page is executed through this connection via
    `analytics.duckdb_engine.DuckDBAnalytics`.
    """
    return DuckDBAnalytics(db_path=":memory:")


# `get_ai_client()` lives in `common/ai_client.py` (Phase 4) and is
# re-exported here so existing page imports (`from common.data_access import
# get_ai_client`) keep working unchanged. It is an `@st.cache_resource`
# target that returns a real Anthropic client when `ANTHROPIC_API_KEY` is
# configured, or `None` (Non-AI Mode) otherwise.
from common.ai_client import get_ai_client  # noqa: E402,F401


# ======================================================================
# @st.cache_data - dataset loading
# ======================================================================
@st.cache_data(show_spinner="Loading transaction data...")
def load_transactions_df() -> pd.DataFrame:
    """
    Load the canonical transactions dataset.

    Preference order:
      1. MongoDB Atlas `transactions` collection (operational store)
      2. Local CSV via the Phase 2 ETL extract -> transform pipeline
         (offline fallback, always available)
    """
    mongo = get_mongo_repo()
    if mongo is not None:
        try:
            df = mongo.find_transactions()
            if not df.empty:
                logger.info("Loaded %d transactions from MongoDB Atlas", len(df))
                return df
        except Exception as exc:  # noqa: BLE001
            logger.warning("MongoDB read failed, falling back to CSV: %s", exc)

    from etl.extract import extract_transactions
    from etl.transform import transform_transactions

    raw = extract_transactions()
    df = transform_transactions(raw)
    logger.info("Loaded %d transactions from local CSV (offline mode)", len(df))
    return df


@st.cache_data(show_spinner=False)
def get_data_source_label() -> str:
    """Human-readable label for the active data source (used in UI badges)."""
    mongo = get_mongo_repo()
    if mongo is not None:
        try:
            df = mongo.find_transactions(limit=1)
            if not df.empty:
                return "MongoDB Atlas"
        except Exception:  # noqa: BLE001
            pass
    return "Local CSV (offline mode)"


def ensure_duckdb_loaded() -> DuckDBAnalytics:
    """
    Make sure the shared DuckDB engine has the `transactions` table loaded.

    Safe to call on every page render: the underlying table-existence check
    is cheap, and the (cached) DataFrame load + DuckDB load only happen
    once per session.
    """
    engine = get_duckdb_engine()
    try:
        engine.con.execute("SELECT 1 FROM transactions LIMIT 1")
    except Exception:  # noqa: BLE001 - table doesn't exist yet
        df = load_transactions_df()
        engine.load_transactions(df, mode="replace")
        logger.info("DuckDB: loaded %d transactions into in-memory engine", len(df))
    return engine


# ======================================================================
# @st.cache_data - DuckDB query wrappers
#
# Every aggregation goes through DuckDBAnalytics. The leading underscore on
# `_engine` tells st.cache_data to skip hashing that argument (DuckDB
# connections are not hashable); `filters` and other plain args ARE hashed,
# so results are correctly re-computed when filters change.
# ======================================================================
@st.cache_data(show_spinner=False)
def query_monthly_summary(_engine: DuckDBAnalytics, filters: Optional[dict] = None) -> pd.DataFrame:
    return _engine.monthly_summary_filtered(filters)


@st.cache_data(show_spinner=False)
def query_category_breakdown(_engine: DuckDBAnalytics, filters: Optional[dict] = None) -> pd.DataFrame:
    return _engine.category_breakdown_filtered(filters)


@st.cache_data(show_spinner=False)
def query_top_categories(
    _engine: DuckDBAnalytics, filters: Optional[dict] = None, n: int = 5, type_filter: str = "Expense"
) -> pd.DataFrame:
    return _engine.top_categories_filtered(filters, n=n, type_filter=type_filter)


@st.cache_data(show_spinner=False)
def query_monthly_trends(_engine: DuckDBAnalytics, filters: Optional[dict] = None) -> pd.DataFrame:
    return _engine.monthly_trends_filtered(filters)


@st.cache_data(show_spinner=False)
def query_account_breakdown(_engine: DuckDBAnalytics, filters: Optional[dict] = None) -> pd.DataFrame:
    return _engine.account_breakdown_filtered(filters)


@st.cache_data(show_spinner=False)
def query_anomalies(_engine: DuckDBAnalytics, z_threshold: float = 2.0) -> pd.DataFrame:
    return _engine.detect_anomalies(z_threshold)


@st.cache_data(show_spinner=False)
def query_date_range(_engine: DuckDBAnalytics) -> dict:
    return _engine.date_range()


@st.cache_data(show_spinner=False)
def query_available_filters(_engine: DuckDBAnalytics) -> dict:
    return {
        "year_months": _engine.available_year_months(),
        "accounts": _engine.available_accounts(),
        "categories": _engine.available_categories(),
    }


@st.cache_data(show_spinner=False)
def query_filtered_transactions(
    _engine: DuckDBAnalytics, filters: Optional[dict] = None, limit: int = 500
) -> pd.DataFrame:
    return _engine.filtered_transactions(filters, limit=limit)


# ======================================================================
# @st.cache_data - profiling results
# ======================================================================
@st.cache_data(show_spinner="Running dataset profiling...")
def get_profile_report() -> dict:
    """Run (and cache) the Phase 2 structural + statistical profiling report."""
    from profiling.profiler import run_profiling

    return run_profiling(save_report=False)


# ======================================================================
# Mongo-backed write helpers (budget plans / AI reports / FIRE simulations)
#
# These are best-effort: if MongoDB is not connected, they no-op and the
# UI shows a notice instead of raising.
# ======================================================================
def save_budget_plan(plan: dict) -> Optional[str]:
    mongo = get_mongo_repo()
    if mongo is None:
        return None
    try:
        return mongo.create_budget_plan(plan)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to save budget plan: %s", exc)
        return None


def load_budget_plans() -> pd.DataFrame:
    mongo = get_mongo_repo()
    if mongo is None:
        return pd.DataFrame()
    try:
        return mongo.list_budget_plans()
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load budget plans: %s", exc)
        return pd.DataFrame()


def save_fire_simulation(simulation: dict) -> Optional[str]:
    mongo = get_mongo_repo()
    if mongo is None:
        return None
    try:
        return mongo.insert_fire_simulation(simulation)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to save FIRE simulation: %s", exc)
        return None


def load_fire_simulations() -> pd.DataFrame:
    mongo = get_mongo_repo()
    if mongo is None:
        return pd.DataFrame()
    try:
        return mongo.list_fire_simulations()
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load FIRE simulations: %s", exc)
        return pd.DataFrame()
