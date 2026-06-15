"""
Page 3 - Budget Planner
========================
Create per-category monthly budget limits, store them in MongoDB Atlas
(`budget_plans` collection), and compare actual spend (via DuckDB) against
the plan for the selected period.
"""

from __future__ import annotations

import common.bootstrap  # noqa: F401

import plotly.graph_objects as go
import streamlit as st

from common.data_access import (
    ensure_duckdb_loaded,
    get_mongo_repo,
    load_budget_plans,
    query_available_filters,
    query_category_breakdown,
    save_budget_plan,
)
from common.ui import configure_page, data_source_badge, page_header, render_global_filters, render_sidebar_header

configure_page("Budget Planner")
render_sidebar_header()

engine = ensure_duckdb_loaded()
filters = render_global_filters()

page_header(
    "Budget Planner",
    subtitle="Set monthly spending limits per category and track actual vs. planned spend.",
    icon="🎯",
)
data_source_badge()
st.write("")

options = query_available_filters(engine)
categories = sorted(options["categories"])

# ----------------------------------------------------------------------
# Create / edit a budget plan
# ----------------------------------------------------------------------
with st.expander("➕ Create a new budget plan", expanded=False):
    with st.form("budget_plan_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            plan_category = st.selectbox("Category", options=categories)
        with c2:
            monthly_limit = st.number_input("Monthly limit (BYN)", min_value=0.0, step=10.0, value=100.0)
        with c3:
            applies_from = st.text_input("Applies from (YYYY-MM)", value=filters.get("start_ym") or "")

        notes = st.text_area("Notes (optional)", placeholder="e.g. tighten food spending after Q3")
        submitted = st.form_submit_button("Save budget plan", use_container_width=True)

        if submitted:
            plan = {
                "category": plan_category,
                "monthly_limit": float(monthly_limit),
                "applies_from": applies_from or None,
                "notes": notes or None,
            }
            plan_id = save_budget_plan(plan)
            if plan_id:
                st.success(f"Budget plan saved (id={plan_id}).")
                load_budget_plans.clear()
            else:
                st.warning(
                    "MongoDB is not connected, so this plan could not be persisted. "
                    "Connect MONGODB_URI to enable saving budget plans."
                )

st.divider()

# ----------------------------------------------------------------------
# Existing plans
# ----------------------------------------------------------------------
st.markdown("#### Saved Budget Plans")
plans_df = load_budget_plans()

if plans_df.empty:
    mongo = get_mongo_repo()
    if mongo is None:
        st.info("MongoDB is not connected - budget plans are not available in offline mode.")
    else:
        st.info("No budget plans saved yet. Use the form above to create one.")
else:
    st.dataframe(plans_df, use_container_width=True, hide_index=True)

st.divider()

# ----------------------------------------------------------------------
# Actual vs. budget for the selected period
# ----------------------------------------------------------------------
st.markdown("#### Actual Spend vs. Budget (selected period)")

actual = query_category_breakdown(engine, filters)
actual_expense = actual[actual["type"] == "Expense"][["category", "total_amount"]].rename(
    columns={"total_amount": "actual"}
)

if plans_df.empty or "category" not in plans_df.columns:
    st.info("Add at least one budget plan above to see the actual-vs-budget comparison.")
else:
    budget_df = plans_df.groupby("category", as_index=False)["monthly_limit"].max()
    compare = budget_df.merge(actual_expense, on="category", how="left").fillna({"actual": 0.0})
    compare["over_under"] = compare["actual"] - compare["monthly_limit"]

    fig = go.Figure()
    fig.add_bar(x=compare["category"], y=compare["monthly_limit"], name="Budget", marker_color="#94A3B8")
    fig.add_bar(
        x=compare["category"],
        y=compare["actual"],
        name="Actual",
        marker_color=["#DC2626" if v > 0 else "#16A34A" for v in compare["over_under"]],
    )
    fig.update_layout(
        barmode="group",
        height=420,
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        yaxis_title="Amount (BYN)",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        compare.style.format({"monthly_limit": "{:,.2f}", "actual": "{:,.2f}", "over_under": "{:+,.2f}"}),
        use_container_width=True,
        hide_index=True,
    )
