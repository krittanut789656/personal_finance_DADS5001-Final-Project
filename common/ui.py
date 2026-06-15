"""
UI Helpers
==========
Shared page configuration, theming (CSS), KPI cards, page headers, the
global sidebar filter widgets, and small formatting utilities used across
all 9 pages.
"""

from __future__ import annotations

from typing import Optional

import streamlit as st

from common.data_access import (
    ensure_duckdb_loaded,
    get_data_source_label,
    query_available_filters,
    query_date_range,
)
from common.state import init_session_state

APP_NAME = "AI Personal Finance Intelligence Platform"
APP_ICON = "💰"

NAV_ITEMS = [
    ("app.py", "📊", "Dashboard"),
    ("pages/2_Expense_Analytics.py", "🧾", "Expense Analytics"),
    ("pages/3_Budget_Planner.py", "🎯", "Budget Planner"),
    ("pages/4_Financial_Health_Score.py", "❤️", "Financial Health Score"),
    ("pages/5_AI_Financial_Intelligence.py", "🤖", "AI Financial Intelligence"),
    ("pages/6_AI_What_if_Simulator.py", "🔮", "AI What-if Simulator"),
    ("pages/7_FIRE_Planner.py", "🔥", "FIRE Planner"),
    ("pages/8_Dataset_Profiling.py", "🔍", "Dataset Profiling"),
    ("pages/9_Project_Methodology.py", "📐", "Project Methodology"),
]


# ----------------------------------------------------------------------
# Page setup
# ----------------------------------------------------------------------
def configure_page(page_title: str, page_icon: str = APP_ICON) -> None:
    """Set page config + inject shared CSS. Call FIRST, before any other st.* call."""
    st.set_page_config(
        page_title=f"{page_title} | Personal Finance Intelligence",
        page_icon=page_icon,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _inject_css()
    init_session_state()


def _inject_css() -> None:
    st.markdown(
        """
        <style>
        /* Tighten default top padding */
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2rem;
            max-width: 1300px;
        }

        /* KPI metric cards */
        div[data-testid="stMetric"] {
            background-color: rgba(46, 91, 255, 0.06);
            border: 1px solid rgba(46, 91, 255, 0.15);
            border-radius: 10px;
            padding: 0.9rem 1rem;
        }
        div[data-testid="stMetricLabel"] {
            font-weight: 600;
            opacity: 0.8;
        }

        /* Sidebar branding */
        section[data-testid="stSidebar"] .block-container {
            padding-top: 1rem;
        }

        /* Section headers */
        h2, h3 {
            font-weight: 700;
        }

        /* Data-source badge */
        .data-source-badge {
            display: inline-block;
            padding: 0.15rem 0.6rem;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
        }
        .badge-online {
            background-color: rgba(22, 163, 74, 0.12);
            color: #16A34A;
            border: 1px solid rgba(22, 163, 74, 0.3);
        }
        .badge-offline {
            background-color: rgba(100, 116, 139, 0.12);
            color: #64748B;
            border: 1px solid rgba(100, 116, 139, 0.3);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: Optional[str] = None, icon: str = "") -> None:
    label = f"{icon}  {title}" if icon else title
    st.markdown(f"## {label}")
    if subtitle:
        st.caption(subtitle)


def data_source_badge() -> None:
    label = get_data_source_label()
    css_class = "badge-online" if "MongoDB" in label or "Snowflake" in label else "badge-offline"
    dot = "🟢" if css_class == "badge-online" else "⚪"
    st.markdown(
        f'<span class="data-source-badge {css_class}">{dot} Data source: {label}</span>',
        unsafe_allow_html=True,
    )


# ----------------------------------------------------------------------
# Sidebar: branding + global filters
# ----------------------------------------------------------------------
def render_sidebar_header() -> None:
    st.sidebar.markdown(f"### {APP_ICON} {APP_NAME}")
    st.sidebar.caption("DADS5001 Final Project — Multi-page Streamlit App")
    st.sidebar.divider()


def render_global_filters() -> dict:
    """
    Render the shared sidebar filter widgets (bound to `st.session_state`)
    and return the active filters dict for use in DuckDB queries.

    Widgets use `key=` so Streamlit automatically syncs their values into
    `st.session_state["filter_*"]` - no manual callbacks needed.
    """
    engine = ensure_duckdb_loaded()
    options = query_available_filters(engine)
    year_months = options["year_months"]
    accounts = options["accounts"]
    categories = options["categories"]

    with st.sidebar:
        st.markdown("#### 🔎 Filters")

        if year_months:
            start_default = st.session_state.get("filter_start_ym") or year_months[0]
            end_default = st.session_state.get("filter_end_ym") or year_months[-1]
            if start_default not in year_months:
                start_default = year_months[0]
            if end_default not in year_months:
                end_default = year_months[-1]

            start_ym, end_ym = st.select_slider(
                "Period (year-month)",
                options=year_months,
                value=(start_default, end_default),
                key="filter_period_slider",
            )
            st.session_state["filter_start_ym"] = start_ym
            st.session_state["filter_end_ym"] = end_ym

        st.multiselect(
            "Accounts",
            options=accounts,
            key="filter_accounts",
            placeholder="All accounts",
        )
        st.multiselect(
            "Categories",
            options=categories,
            key="filter_categories",
            placeholder="All categories",
        )

        if st.button("Reset filters", use_container_width=True):
            st.session_state["filter_start_ym"] = year_months[0] if year_months else None
            st.session_state["filter_end_ym"] = year_months[-1] if year_months else None
            st.session_state["filter_accounts"] = []
            st.session_state["filter_categories"] = []
            st.rerun()

        st.divider()
        date_range = query_date_range(engine)
        st.caption(
            f"📅 Dataset: {date_range['min_date']} → {date_range['max_date']}  \n"
            f"📄 {date_range['row_count']:,} transactions"
        )

    return {
        "start_ym": st.session_state.get("filter_start_ym"),
        "end_ym": st.session_state.get("filter_end_ym"),
        "accounts": st.session_state.get("filter_accounts") or None,
        "categories": st.session_state.get("filter_categories") or None,
    }


# ----------------------------------------------------------------------
# KPI cards
# ----------------------------------------------------------------------
def kpi_row(items: list[dict]) -> None:
    """
    Render a responsive row of `st.metric` KPI cards.

    Each item: {"label": str, "value": str, "delta": Optional[str],
                 "delta_color": "normal"|"inverse"|"off", "help": Optional[str]}
    """
    cols = st.columns(len(items))
    for col, item in zip(cols, items):
        with col:
            st.metric(
                label=item.get("label", ""),
                value=item.get("value", "—"),
                delta=item.get("delta"),
                delta_color=item.get("delta_color", "normal"),
                help=item.get("help"),
            )


def format_currency(value: float, currency: str = "BYN") -> str:
    try:
        return f"{value:,.2f} {currency}"
    except (TypeError, ValueError):
        return "—"


def format_pct(value: Optional[float]) -> str:
    if value is None:
        return "—"
    try:
        return f"{value:+.2f}%"
    except (TypeError, ValueError):
        return "—"
