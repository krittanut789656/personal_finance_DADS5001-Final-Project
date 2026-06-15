"""
Page 2 - Expense Analytics
===========================
Deeper dive into spending: category breakdown, month-over-month trends,
account-level analysis, and anomaly detection - all via DuckDB.
"""

from __future__ import annotations

import common.bootstrap  # noqa: F401

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from common.data_access import (
    ensure_duckdb_loaded,
    query_anomalies,
    query_category_breakdown,
    query_monthly_trends,
)
from common.ui import (
    configure_page,
    data_source_badge,
    format_pct,
    page_header,
    render_global_filters,
    render_sidebar_header,
)

configure_page("Expense Analytics")
render_sidebar_header()

engine = ensure_duckdb_loaded()
filters = render_global_filters()

page_header(
    "Expense Analytics",
    subtitle="Category breakdowns, month-over-month trends, and spending anomalies.",
    icon="🧾",
)
data_source_badge()
st.write("")

# ----------------------------------------------------------------------
# Category breakdown
# ----------------------------------------------------------------------
st.markdown("#### Spending by Category")
cat_df = query_category_breakdown(engine, filters)
expense_cats = cat_df[cat_df["type"] == "Expense"].copy()

if expense_cats.empty:
    st.info("No expense data for the current filters.")
else:
    c1, c2 = st.columns([3, 2], gap="large")
    with c1:
        fig = px.treemap(
            expense_cats,
            path=["category"],
            values="total_amount",
            color="total_amount",
            color_continuous_scale="Reds",
            title="Expense Breakdown (Treemap)",
        )
        fig.update_layout(height=420, margin=dict(l=10, r=10, t=50, b=10), coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.markdown("##### Category Detail")
        st.dataframe(
            expense_cats.sort_values("total_amount", ascending=False)[
                ["category", "total_amount", "transaction_count", "avg_amount"]
            ].style.format({"total_amount": "{:,.2f}", "avg_amount": "{:,.2f}", "transaction_count": "{:,}"}),
            use_container_width=True,
            hide_index=True,
            height=420,
        )

st.divider()

# ----------------------------------------------------------------------
# Monthly trends (MoM % change)
# ----------------------------------------------------------------------
st.markdown("#### Month-over-Month Trends")
trends = query_monthly_trends(engine, filters)

if trends.empty:
    st.info("No trend data for the current filters.")
else:
    c1, c2 = st.columns([3, 2], gap="large")
    with c1:
        fig2 = go.Figure()
        fig2.add_trace(
            go.Scatter(x=trends["year_month"], y=trends["total_expense"], name="Expense", mode="lines+markers", line=dict(color="#DC2626"))
        )
        fig2.add_trace(
            go.Scatter(
                x=trends["year_month"],
                y=trends["expense_3mo_avg"],
                name="Expense (3-mo avg)",
                mode="lines",
                line=dict(color="#DC2626", dash="dot"),
            )
        )
        fig2.add_trace(
            go.Scatter(x=trends["year_month"], y=trends["total_income"], name="Income", mode="lines+markers", line=dict(color="#16A34A"))
        )
        fig2.update_layout(
            height=400,
            margin=dict(l=10, r=10, t=30, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            yaxis_title="Amount (BYN)",
        )
        st.plotly_chart(fig2, use_container_width=True)

    with c2:
        st.markdown("##### MoM Change (%)")
        display_cols = trends[["year_month", "expense_mom_change_pct", "income_mom_change_pct"]].copy()
        display_cols.columns = ["Month", "Expense MoM %", "Income MoM %"]
        display_cols["Expense MoM %"] = display_cols["Expense MoM %"].apply(format_pct)
        display_cols["Income MoM %"] = display_cols["Income MoM %"].apply(format_pct)
        st.dataframe(display_cols, use_container_width=True, hide_index=True, height=400)

st.divider()

# ----------------------------------------------------------------------
# Anomaly detection
# ----------------------------------------------------------------------
st.markdown("#### Spending Anomalies")
st.caption("Category/month combinations whose total deviates from that category's historical average by 2+ standard deviations (z-score).")

z_threshold = st.slider("Sensitivity (z-score threshold)", min_value=1.0, max_value=3.5, value=2.0, step=0.25)
anomalies = query_anomalies(engine, z_threshold)

if anomalies.empty:
    st.success("No anomalies detected at this sensitivity level.")
else:
    fig3 = px.bar(
        anomalies.head(15),
        x="z_score",
        y="category",
        color="year_month",
        orientation="h",
        title="Top Anomalies by Z-score",
        hover_data=["month_total", "category_mean"],
    )
    fig3.update_layout(height=420, margin=dict(l=10, r=10, t=50, b=10), yaxis_title=None)
    st.plotly_chart(fig3, use_container_width=True)

    st.dataframe(
        anomalies.style.format(
            {"month_total": "{:,.2f}", "category_mean": "{:,.2f}", "category_std": "{:,.2f}", "z_score": "{:,.2f}"}
        ),
        use_container_width=True,
        hide_index=True,
    )
