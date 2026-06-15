"""
AI Context Package Builder (Phase 4)
=======================================
This module is the SINGLE place that assembles data to send to the LLM.

DATA-CENTRIC AI WORKFLOW (mandatory):

    Data -> Metadata -> Statistical Summary -> Context Package -> LLM -> Insight

ALLOWED CONTEXT (aggregated/derived only):
  - DuckDB results        (monthly summary, category breakdown, trends, accounts)
  - Snowflake metrics      (monthly_summary table, if Snowflake is connected)
  - Financial Health Score (sub-scores + composite, from Page 4's formula)
  - Budget Status          (plan vs. actual, from Page 3's formula)
  - Profiling Summary      (column-level stats, NOT row-level data)
  - What-if Results        (Python-computed projections)
  - FIRE Results           (Python-computed FIRE numbers / projections)
  - FRED macro indicators  (CPI, Fed Funds rate, unemployment)

NEVER INCLUDED: raw transaction rows, full DataFrames, or anything from
`query_filtered_transactions` / `filtered_transactions`. Every function in
this module returns small Python dicts/lists built from aggregates only.
"""

from __future__ import annotations

import common.bootstrap  # noqa: F401  -- must run before backend imports

import numpy as np
import pandas as pd
import streamlit as st

from analytics.duckdb_engine import DuckDBAnalytics
from common.data_access import (
    get_profile_report,
    get_snowflake_repo,
    load_budget_plans,
    query_account_breakdown,
    query_category_breakdown,
    query_monthly_summary,
    query_monthly_trends,
    query_top_categories,
)
from common.fred_data import get_macro_context

# ----------------------------------------------------------------------
# Financial Health Score (mirrors pages/4_Financial_Health_Score.py)
# ----------------------------------------------------------------------
HEALTH_WEIGHTS = {
    "Savings Rate": 0.40,
    "Expense Stability": 0.25,
    "Income Stability": 0.15,
    "Spending Diversification": 0.20,
}


def score_band(score: float) -> tuple[str, str]:
    if score >= 75:
        return "Healthy", "#16A34A"
    if score >= 50:
        return "Fair", "#EAB308"
    return "At Risk", "#DC2626"


def financial_health_snapshot(monthly: pd.DataFrame, cat: pd.DataFrame) -> dict:
    """Recompute the Page 4 Financial Health Score from DuckDB aggregates."""
    if monthly.empty:
        return {"available": False}

    total_income = float(monthly["total_income"].sum())
    total_expense = float(monthly["total_expense"].sum())
    net = float(monthly["net"].sum())
    overall_savings_rate = (net / total_income * 100) if total_income > 0 else 0.0

    savings_score = float(np.clip(overall_savings_rate / 50.0 * 100, 0, 100))

    expense_mean = monthly["total_expense"].mean()
    expense_std = monthly["total_expense"].std(ddof=0) if len(monthly) > 1 else 0.0
    expense_cv = (expense_std / expense_mean) if expense_mean else 0.0
    expense_stability_score = float(np.clip(100 - expense_cv * 100, 0, 100))

    income_mean = monthly["total_income"].mean()
    income_std = monthly["total_income"].std(ddof=0) if len(monthly) > 1 else 0.0
    income_cv = (income_std / income_mean) if income_mean else 0.0
    income_stability_score = float(np.clip(100 - income_cv * 100, 0, 100))

    expense_cats = cat[cat["type"] == "Expense"]
    if not expense_cats.empty and expense_cats["total_amount"].sum() > 0:
        shares = expense_cats["total_amount"] / expense_cats["total_amount"].sum()
        hhi = float((shares ** 2).sum())
        diversification_score = float(np.clip((1 - hhi) * 100, 0, 100))
    else:
        hhi = None
        diversification_score = 0.0

    sub_scores = {
        "Savings Rate": round(savings_score, 1),
        "Expense Stability": round(expense_stability_score, 1),
        "Income Stability": round(income_stability_score, 1),
        "Spending Diversification": round(diversification_score, 1),
    }
    composite = sum(sub_scores[k] * HEALTH_WEIGHTS[k] for k in HEALTH_WEIGHTS)
    band, _ = score_band(composite)

    return {
        "available": True,
        "composite_score": round(composite, 1),
        "band": band,
        "sub_scores": sub_scores,
        "weights": HEALTH_WEIGHTS,
        "overall_savings_rate_pct": round(overall_savings_rate, 2),
        "category_hhi": round(hhi, 3) if hhi is not None else None,
    }


# ----------------------------------------------------------------------
# Budget Status (mirrors pages/3_Budget_Planner.py)
# ----------------------------------------------------------------------
def budget_status_snapshot(cat: pd.DataFrame) -> dict:
    """Recompute the Page 3 plan-vs-actual comparison from DuckDB + MongoDB."""
    plans_df = load_budget_plans()
    if plans_df.empty or "category" not in plans_df.columns:
        return {"available": False, "reason": "No budget plans saved yet."}

    actual_expense = cat[cat["type"] == "Expense"][["category", "total_amount"]].rename(
        columns={"total_amount": "actual"}
    )
    budget_df = plans_df.groupby("category", as_index=False)["monthly_limit"].max()
    compare = budget_df.merge(actual_expense, on="category", how="left").fillna({"actual": 0.0})
    compare["over_under"] = compare["actual"] - compare["monthly_limit"]

    over_budget = compare[compare["over_under"] > 0].sort_values("over_under", ascending=False)

    return {
        "available": True,
        "categories": compare.round(2).to_dict("records"),
        "over_budget_categories": over_budget["category"].tolist(),
        "total_over_budget_amount": round(float(compare.loc[compare["over_under"] > 0, "over_under"].sum()), 2),
    }


# ----------------------------------------------------------------------
# Profiling Summary (mirrors pages/8_Dataset_Profiling.py - column stats only)
# ----------------------------------------------------------------------
def profiling_summary_snapshot() -> dict:
    """Condensed dataset-quality summary - column-level stats only, no row data."""
    try:
        report = get_profile_report()
    except Exception:  # noqa: BLE001
        return {"available": False}

    structural = report.get("structural", {})
    statistical = report.get("statistical", {})

    columns_summary = {
        col: {
            "dtype": info.get("dtype"),
            "null_pct": info.get("null_pct"),
            "unique_count": info.get("unique_count"),
        }
        for col, info in structural.get("columns", {}).items()
    }

    return {
        "available": True,
        "source_rows": report.get("source_rows"),
        "clean_rows": report.get("clean_rows"),
        "rows_dropped_in_transform": report.get("rows_dropped_in_transform"),
        "duplicate_rows": structural.get("duplicate_rows"),
        "columns": columns_summary,
        "date_range": statistical.get("date_range"),
        "amount_stats": statistical.get("amount_stats"),
    }


# ----------------------------------------------------------------------
# DuckDB Results snapshot (aggregates only)
# ----------------------------------------------------------------------
def duckdb_snapshot(engine: DuckDBAnalytics, filters: dict | None) -> dict:
    monthly = query_monthly_summary(engine, filters)
    cat = query_category_breakdown(engine, filters)
    top_expense = query_top_categories(engine, filters, n=5, type_filter="Expense")
    top_income = query_top_categories(engine, filters, n=3, type_filter="Income")
    trends = query_monthly_trends(engine, filters)
    accounts = query_account_breakdown(engine, filters)

    return {
        "period": {"start": filters.get("start_ym") if filters else None, "end": filters.get("end_ym") if filters else None},
        "filters": {
            "accounts": filters.get("accounts") if filters else None,
            "categories": filters.get("categories") if filters else None,
        },
        "months_covered": int(len(monthly)),
        "totals": {
            "total_income": float(monthly["total_income"].sum()) if not monthly.empty else 0.0,
            "total_expense": float(monthly["total_expense"].sum()) if not monthly.empty else 0.0,
            "net": float(monthly["net"].sum()) if not monthly.empty else 0.0,
        },
        "monthly_summary": monthly.round(2).to_dict("records") if not monthly.empty else [],
        "top_expense_categories": top_expense.round(2).to_dict("records") if not top_expense.empty else [],
        "top_income_categories": top_income.round(2).to_dict("records") if not top_income.empty else [],
        "monthly_trends": trends.round(2).to_dict("records") if not trends.empty else [],
        "account_breakdown": accounts.round(2).to_dict("records") if not accounts.empty else [],
    }, monthly, cat


# ----------------------------------------------------------------------
# Snowflake Metrics snapshot (aggregates only, if connected)
# ----------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def snowflake_metrics_snapshot() -> dict:
    repo = get_snowflake_repo()
    if repo is None:
        return {"available": False, "reason": "Snowflake is not connected."}
    try:
        df = repo.run_query(
            "SELECT YEAR_MONTH, TOTAL_INCOME, TOTAL_EXPENSE, NET, SAVINGS_RATE_PCT, TRANSACTION_COUNT "
            "FROM MONTHLY_SUMMARY ORDER BY YEAR_MONTH DESC LIMIT 12"
        )
        if df.empty:
            return {"available": False, "reason": "MONTHLY_SUMMARY table is empty."}
        df.columns = [c.lower() for c in df.columns]
        return {"available": True, "monthly_summary_recent": df.round(2).to_dict("records")}
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "reason": f"Snowflake query failed: {exc}"}


# ----------------------------------------------------------------------
# Macro context (FRED)
# ----------------------------------------------------------------------
def macro_snapshot() -> dict:
    return get_macro_context()


# ----------------------------------------------------------------------
# Top-level context packages (one per AI page)
# ----------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def build_financial_intelligence_context(_engine: DuckDBAnalytics, filters: dict | None) -> dict:
    """Full context package for Page 5 - AI Financial Intelligence."""
    duck, monthly, cat = duckdb_snapshot(_engine, filters)
    return {
        "duckdb_results": duck,
        "financial_health_score": financial_health_snapshot(monthly, cat),
        "budget_status": budget_status_snapshot(cat),
        "profiling_summary": profiling_summary_snapshot(),
        "snowflake_metrics": snowflake_metrics_snapshot(),
        "macro_context": macro_snapshot(),
    }


def build_whatif_context(
    engine: DuckDBAnalytics,
    filters: dict | None,
    scenario_name: str,
    scenario_params: dict,
    whatif_results: dict,
) -> dict:
    """Context package for Page 6 - AI What-if Simulator (results, not raw data)."""
    duck, monthly, cat = duckdb_snapshot(engine, filters)
    return {
        "scenario": {"name": scenario_name, "parameters": scenario_params},
        "whatif_results": whatif_results,
        "baseline_duckdb_summary": {
            "totals": duck["totals"],
            "months_covered": duck["months_covered"],
            "top_expense_categories": duck["top_expense_categories"],
        },
        "financial_health_score": financial_health_snapshot(monthly, cat),
        "macro_context": macro_snapshot(),
    }


def build_fire_context(fire_inputs: dict, fire_results: dict, macro: dict | None = None) -> dict:
    """Context package for Page 7 - FIRE Planner (Python-computed FIRE results)."""
    return {
        "fire_inputs": fire_inputs,
        "fire_results": fire_results,
        "macro_context": macro if macro is not None else macro_snapshot(),
    }


__all__ = [
    "financial_health_snapshot",
    "budget_status_snapshot",
    "profiling_summary_snapshot",
    "duckdb_snapshot",
    "snowflake_metrics_snapshot",
    "macro_snapshot",
    "build_financial_intelligence_context",
    "build_whatif_context",
    "build_fire_context",
    "format_currency",
]
