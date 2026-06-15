"""
Page 4 - Financial Health Score
=================================
A composite, rules-based "financial health score" (0-100) derived purely
from DuckDB aggregates - no AI involved. Combines savings rate, expense
stability, income stability, and spending diversification.
"""

from __future__ import annotations

import common.bootstrap  # noqa: F401

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from common.data_access import ensure_duckdb_loaded, query_category_breakdown, query_monthly_summary
from common.ui import configure_page, data_source_badge, format_currency, format_pct, page_header, render_global_filters, render_sidebar_header

configure_page("Financial Health Score")
render_sidebar_header()

engine = ensure_duckdb_loaded()
filters = render_global_filters()

page_header(
    "Financial Health Score",
    subtitle="A rules-based composite score (0-100) computed from your DuckDB aggregates - savings rate, spending stability, and diversification.",
    icon="❤️",
)
data_source_badge()
st.write("")

monthly = query_monthly_summary(engine, filters)
cat = query_category_breakdown(engine, filters)

if monthly.empty:
    st.warning("No transactions match the current filters.")
    st.stop()

# ----------------------------------------------------------------------
# Sub-score calculations
# ----------------------------------------------------------------------
total_income = float(monthly["total_income"].sum())
total_expense = float(monthly["total_expense"].sum())
net = float(monthly["net"].sum())
overall_savings_rate = (net / total_income * 100) if total_income > 0 else 0.0

# 1. Savings rate score: 0% -> 0, 50%+ -> 100
savings_score = float(np.clip(overall_savings_rate / 50.0 * 100, 0, 100))

# 2. Expense stability score: lower coefficient of variation -> higher score
expense_mean = monthly["total_expense"].mean()
expense_std = monthly["total_expense"].std(ddof=0) if len(monthly) > 1 else 0.0
expense_cv = (expense_std / expense_mean) if expense_mean else 0.0
expense_stability_score = float(np.clip(100 - expense_cv * 100, 0, 100))

# 3. Income stability score: lower coefficient of variation -> higher score
income_mean = monthly["total_income"].mean()
income_std = monthly["total_income"].std(ddof=0) if len(monthly) > 1 else 0.0
income_cv = (income_std / income_mean) if income_mean else 0.0
income_stability_score = float(np.clip(100 - income_cv * 100, 0, 100))

# 4. Spending diversification score: 1 - Herfindahl-Hirschman Index of expense categories
expense_cats = cat[cat["type"] == "Expense"]
if not expense_cats.empty and expense_cats["total_amount"].sum() > 0:
    shares = expense_cats["total_amount"] / expense_cats["total_amount"].sum()
    hhi = float((shares ** 2).sum())
    diversification_score = float(np.clip((1 - hhi) * 100, 0, 100))
else:
    diversification_score = 0.0

WEIGHTS = {
    "Savings Rate": 0.40,
    "Expense Stability": 0.25,
    "Income Stability": 0.15,
    "Spending Diversification": 0.20,
}
sub_scores = {
    "Savings Rate": savings_score,
    "Expense Stability": expense_stability_score,
    "Income Stability": income_stability_score,
    "Spending Diversification": diversification_score,
}
composite = sum(sub_scores[k] * WEIGHTS[k] for k in WEIGHTS)


def score_band(score: float) -> tuple[str, str]:
    if score >= 75:
        return "Healthy", "#16A34A"
    if score >= 50:
        return "Fair", "#EAB308"
    return "At Risk", "#DC2626"


band_label, band_color = score_band(composite)

# ----------------------------------------------------------------------
# Layout
# ----------------------------------------------------------------------
c1, c2 = st.columns([2, 3], gap="large")

with c1:
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=round(composite, 1),
            number={"suffix": " / 100"},
            title={"text": f"Overall Score - {band_label}"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": band_color},
                "steps": [
                    {"range": [0, 50], "color": "rgba(220,38,38,0.15)"},
                    {"range": [50, 75], "color": "rgba(234,179,8,0.15)"},
                    {"range": [75, 100], "color": "rgba(22,163,74,0.15)"},
                ],
            },
        )
    )
    fig.update_layout(height=380, margin=dict(l=20, r=20, t=60, b=10))
    st.plotly_chart(fig, use_container_width=True)

with c2:
    categories_list = list(sub_scores.keys())
    values = list(sub_scores.values())
    fig2 = go.Figure(
        go.Scatterpolar(
            r=values + [values[0]],
            theta=categories_list + [categories_list[0]],
            fill="toself",
            line_color="#2E5BFF",
        )
    )
    fig2.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        height=380,
        margin=dict(l=40, r=40, t=30, b=10),
        showlegend=False,
        title="Sub-score Breakdown",
    )
    st.plotly_chart(fig2, use_container_width=True)

st.divider()

st.markdown("#### Sub-score Details")
cols = st.columns(4)
details = [
    ("Savings Rate", savings_score, f"Overall savings rate: {format_pct(overall_savings_rate)}", WEIGHTS["Savings Rate"]),
    ("Expense Stability", expense_stability_score, f"Monthly expense CV: {expense_cv:.2f}", WEIGHTS["Expense Stability"]),
    ("Income Stability", income_stability_score, f"Monthly income CV: {income_cv:.2f}", WEIGHTS["Income Stability"]),
    ("Spending Diversification", diversification_score, f"Category HHI: {hhi:.3f}" if not expense_cats.empty else "No expense data", WEIGHTS["Spending Diversification"]),
]
for col, (name, score, detail, weight) in zip(cols, details):
    with col:
        st.metric(label=f"{name} ({weight:.0%} weight)", value=f"{score:.1f}")
        st.caption(detail)

st.divider()
st.markdown("#### How this score is calculated")
st.markdown(
    f"""
| Component | Weight | Logic |
|---|---|---|
| Savings Rate | 40% | `clip(savings_rate / 50%, 0, 1) * 100` — a 50%+ savings rate scores 100 |
| Expense Stability | 25% | `clip(100 - CV(monthly_expense) * 100, 0, 100)` — lower month-to-month volatility scores higher |
| Income Stability | 15% | `clip(100 - CV(monthly_income) * 100, 0, 100)` — steadier income scores higher |
| Spending Diversification | 20% | `clip((1 - HHI(category_shares)) * 100, 0, 100)` — spend spread across categories scores higher |

**Total income (period):** {format_currency(total_income)}  &nbsp;|&nbsp;
**Total expense (period):** {format_currency(total_expense)}  &nbsp;|&nbsp;
**Net:** {format_currency(net)}

*This score is fully rules-based (Non-AI Mode) and computed directly from DuckDB query results - no LLM involved.*
"""
)
