"""
Page 1 - Dashboard
==================
Landing page of the AI Personal Finance Intelligence Platform.

Shows headline KPIs for the selected period plus an income vs. expense
trend, top expense categories, and an account breakdown - all computed
through the mandatory DuckDB analytics engine.
"""


from __future__ import annotations

import common.bootstrap  # noqa: F401  -- must be first

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from common.data_access import (
    ensure_duckdb_loaded,
    query_account_breakdown,
    query_monthly_summary,
    query_top_categories,
)
from common.ui import (
    configure_page,
    data_source_badge,
    format_currency,
    format_pct,
    kpi_row,
    page_header,
    render_global_filters,
    render_sidebar_header,
)

configure_page("Dashboard")
render_sidebar_header()

engine = ensure_duckdb_loaded()
filters = render_global_filters()

page_header(
    "Dashboard",
    subtitle="Overview of your income, expenses, and savings for the selected period.",
    icon="📊",
)
data_source_badge()
st.write("")

# ----------------------------------------------------------------------
# KPI cards
# ----------------------------------------------------------------------
monthly = query_monthly_summary(engine, filters)

if monthly.empty:
    st.warning("No transactions match the current filters.")
else:
    total_income = float(monthly["total_income"].sum())
    total_expense = float(monthly["total_expense"].sum())
    net = float(monthly["net"].sum())
    savings_rate = round((net / total_income) * 100, 2) if total_income > 0 else None
    txn_count = int(monthly["transaction_count"].sum())
    months_covered = len(monthly)

    kpi_row(
        [
            {"label": "Total Income", "value": format_currency(total_income), "help": "Sum of all Income transactions in the selected period"},
            {"label": "Total Expense", "value": format_currency(total_expense), "help": "Sum of all Expense transactions in the selected period"},
            {
                "label": "Net Savings",
                "value": format_currency(net),
                "delta_color": "normal" if net >= 0 else "inverse",
                "help": "Total income minus total expense",
            },
            {
                "label": "Savings Rate",
                "value": format_pct(savings_rate) if savings_rate is not None else "—",
                "delta_color": "normal" if (savings_rate or 0) >= 0 else "inverse",
                "help": "Net savings as a % of income",
            },
            {"label": "Transactions", "value": f"{txn_count:,}", "help": f"Across {months_covered} month(s)"},
        ]
    )

st.write("")
st.divider()

# ----------------------------------------------------------------------
# Income vs Expense trend
# ----------------------------------------------------------------------
left, right = st.columns([3, 2], gap="large")

with left:
    st.markdown("#### Monthly Income vs. Expense")
    if monthly.empty:
        st.info("No data to display.")
    else:
        fig = go.Figure()
        fig.add_bar(x=monthly["year_month"], y=monthly["total_income"], name="Income", marker_color="#16A34A")
        fig.add_bar(x=monthly["year_month"], y=monthly["total_expense"], name="Expense", marker_color="#DC2626")
        fig.add_trace(
            go.Scatter(
                x=monthly["year_month"],
                y=monthly["net"],
                name="Net",
                mode="lines+markers",
                line=dict(color="#2E5BFF", width=3),
                yaxis="y1",
            )
        )
        fig.update_layout(
            barmode="group",
            height=420,
            margin=dict(l=10, r=10, t=30, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis_title=None,
            yaxis_title="Amount (BYN)",
        )
        st.plotly_chart(fig, use_container_width=True)

with right:
    st.markdown("#### Top Expense Categories")
    top_cats = query_top_categories(engine, filters, n=8, type_filter="Expense")
    if top_cats.empty:
        st.info("No expense data to display.")
    else:
        fig2 = px.bar(
            top_cats.sort_values("total_amount"),
            x="total_amount",
            y="category",
            orientation="h",
            text="total_amount",
            color="total_amount",
            color_continuous_scale="Blues",
        )
        fig2.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
        fig2.update_layout(
            height=420,
            margin=dict(l=10, r=10, t=30, b=10),
            xaxis_title="Total Amount (BYN)",
            yaxis_title=None,
            coloraxis_showscale=False,
        )
        st.plotly_chart(fig2, use_container_width=True)

st.divider()

# ----------------------------------------------------------------------
# Account breakdown
# ----------------------------------------------------------------------
st.markdown("#### Account Breakdown")
acct = query_account_breakdown(engine, filters)
if acct.empty:
    st.info("No account data to display.")
else:
    c1, c2 = st.columns([2, 3], gap="large")
    with c1:
        fig3 = px.pie(
            acct,
            names="account",
            values="total_expense",
            hole=0.45,
            title="Expense Share by Account",
        )
        fig3.update_layout(height=360, margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig3, use_container_width=True)
    with c2:
        st.dataframe(
            acct.style.format(
                {
                    "total_expense": "{:,.2f}",
                    "total_income": "{:,.2f}",
                    "transaction_count": "{:,}",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

st.caption(
    "💡 Use the sidebar filters to narrow the period, accounts, or categories - "
    "every chart and KPI on this page recomputes through DuckDB."
)
