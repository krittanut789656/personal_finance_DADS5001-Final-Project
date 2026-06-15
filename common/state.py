"""
Session State Layer
====================
Centralized `st.session_state` defaults for the AI Personal Finance
Intelligence Platform. Every page calls `init_session_state()` once near
the top (after `configure_page`) so all session keys exist before any page
reads or writes them.

Session state groups (per project brief):
  - Filters              -> filter_start_ym, filter_end_ym, filter_accounts, filter_categories
  - Selected Period       -> selected_period
  - AI History            -> ai_history
  - FIRE Inputs           -> fire_inputs
  - What-if Inputs        -> whatif_inputs
"""

from __future__ import annotations

import streamlit as st

DEFAULTS: dict = {
    # --- Filters (shared sidebar, applied to DuckDB queries on every page) ---
    "filter_start_ym": None,
    "filter_end_ym": None,
    "filter_accounts": [],
    "filter_categories": [],

    # --- Selected Period (drill-down month, e.g. Expense Analytics) ---
    "selected_period": None,

    # --- AI Financial Intelligence (Phase 4) ---
    "ai_history": [],
    "ai_insights_report": None,

    # --- AI What-if Simulator inputs (named scenarios, Phase 4) ---
    "whatif_inputs": {
        "scenario": "Reduce Food Spending",
        "scenario_params": {},
        "months_forward": 12,
    },
    "whatif_results": None,
    "whatif_explanation": None,

    # --- FIRE Planner inputs ---
    "fire_inputs": {
        "current_savings": 0.0,
        "monthly_income": 0.0,
        "monthly_expense": 0.0,
        "annual_return_pct": 7.0,
        "withdrawal_rate_pct": 4.0,
        "current_age": 30,
        "target_age": 50,
    },
    "fire_results": None,
    "fire_explanation": None,
}


def init_session_state() -> None:
    """Populate any missing `st.session_state` keys with their defaults."""
    for key, value in DEFAULTS.items():
        if key not in st.session_state:
            # Use a fresh copy for mutable defaults (dict/list)
            st.session_state[key] = value.copy() if isinstance(value, (dict, list)) else value


def get_active_filters() -> dict:
    """Build a DuckDB `filters` dict (see `DuckDBAnalytics._build_where`) from session_state."""
    return {
        "start_ym": st.session_state.get("filter_start_ym") or None,
        "end_ym": st.session_state.get("filter_end_ym") or None,
        "accounts": st.session_state.get("filter_accounts") or None,
        "categories": st.session_state.get("filter_categories") or None,
    }


def has_active_filters() -> bool:
    f = get_active_filters()
    return any(v for v in f.values())
