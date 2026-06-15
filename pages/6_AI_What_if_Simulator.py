"""
Page 6 - AI What-if Simulator
===============================
Named what-if scenarios over your DuckDB-derived monthly baseline:

  - Reduce Food Spending
  - Reduce Shopping Spending
  - Increase Savings
  - Increase Investment Amount
  - Increase Income

IMPORTANT (project rule): Python performs ALL numeric calculations.
The LLM only EXPLAINS the Python-computed results - it never recomputes
or overrides numbers. The "AI explanation" is generated from a small
context package (`common.ai_context.build_whatif_context`) containing only
the scenario parameters and the already-computed results.
"""

from __future__ import annotations

import json

import common.bootstrap  # noqa: F401

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from common.ai_client import ask_ai, get_ai_client
from common.ai_context import build_whatif_context
from common.data_access import ensure_duckdb_loaded, query_category_breakdown, query_monthly_summary
from common.ui import configure_page, data_source_badge, format_currency, page_header, render_global_filters, render_sidebar_header

configure_page("AI What-if Simulator")
render_sidebar_header()

engine = ensure_duckdb_loaded()
filters = render_global_filters()

page_header(
    "AI What-if Simulator",
    subtitle="Python computes the scenario math. The AI explains what it means for you.",
    icon="🔮",
)
data_source_badge()
st.write("")

monthly = query_monthly_summary(engine, filters)
cat = query_category_breakdown(engine, filters)
expense_cats = cat[cat["type"] == "Expense"].sort_values("total_amount", ascending=False)

if monthly.empty or expense_cats.empty:
    st.warning("No transactions match the current filters.")
    st.stop()

n_months = max(len(monthly), 1)
baseline_monthly_income = float(monthly["total_income"].sum()) / n_months
baseline_category_monthly = (expense_cats.set_index("category")["total_amount"] / n_months).to_dict()
baseline_monthly_expense = sum(baseline_category_monthly.values())
baseline_net_monthly = baseline_monthly_income - baseline_monthly_expense


def _find_category(categories, *keywords) -> str | None:
    for c in categories:
        for kw in keywords:
            if kw.lower() in str(c).lower():
                return c
    return None


food_category = _find_category(baseline_category_monthly.keys(), "food", "grocer")
shopping_category = _find_category(baseline_category_monthly.keys(), "shop", "retail")

# ----------------------------------------------------------------------
# Scenario selection (bound to st.session_state["whatif_inputs"])
# ----------------------------------------------------------------------
SCENARIOS = [
    "Reduce Food Spending",
    "Reduce Shopping Spending",
    "Increase Savings",
    "Increase Investment Amount",
    "Increase Income",
]

wi = st.session_state["whatif_inputs"]
wi.setdefault("scenario", SCENARIOS[0])
wi.setdefault("scenario_params", {})

st.markdown("#### 1. Choose a scenario")
scenario_name = st.selectbox("Scenario", SCENARIOS, index=SCENARIOS.index(wi["scenario"]) if wi["scenario"] in SCENARIOS else 0)
wi["scenario"] = scenario_name

st.markdown("#### 2. Set parameters")
c1, c2 = st.columns([1, 1], gap="large")

scenario_params: dict = {}
adjusted_category_monthly = dict(baseline_category_monthly)
adjusted_monthly_income = baseline_monthly_income
investment_projection = None

with c1:
    if scenario_name == "Reduce Food Spending":
        if food_category is None:
            st.warning("No 'Food'-like category found in this dataset/period - this scenario has no effect.")
            pct = 0
        else:
            pct = st.slider(f"Reduce '{food_category}' spending by (%)", 0, 100, value=int(wi["scenario_params"].get("pct", 10)), step=5)
            adjusted_category_monthly[food_category] = baseline_category_monthly[food_category] * (1 - pct / 100.0)
        scenario_params = {"category": food_category, "reduction_pct": pct}

    elif scenario_name == "Reduce Shopping Spending":
        if shopping_category is None:
            st.warning("No 'Shopping'-like category found in this dataset/period - this scenario has no effect.")
            pct = 0
        else:
            pct = st.slider(f"Reduce '{shopping_category}' spending by (%)", 0, 100, value=int(wi["scenario_params"].get("pct", 10)), step=5)
            adjusted_category_monthly[shopping_category] = baseline_category_monthly[shopping_category] * (1 - pct / 100.0)
        scenario_params = {"category": shopping_category, "reduction_pct": pct}

    elif scenario_name == "Increase Savings":
        max_amount = round(baseline_monthly_expense, 2)
        amount = st.number_input(
            "Additional monthly savings (BYN)",
            min_value=0.0,
            max_value=max(max_amount, 0.0),
            step=10.0,
            value=float(wi["scenario_params"].get("amount", 0.0)),
            help="Cuts total monthly expenses by this amount, spread proportionally across categories.",
        )
        if baseline_monthly_expense > 0:
            factor = max(0.0, (baseline_monthly_expense - amount) / baseline_monthly_expense)
            adjusted_category_monthly = {k: v * factor for k, v in adjusted_category_monthly.items()}
        scenario_params = {"additional_monthly_savings": amount}

    elif scenario_name == "Increase Investment Amount":
        amount = st.number_input(
            "Additional monthly investment contribution (BYN)",
            min_value=0.0,
            step=10.0,
            value=float(wi["scenario_params"].get("amount", 50.0)),
            help="Diverted from your monthly net savings into an investment account.",
        )
        return_pct = st.slider(
            "Assumed annual investment return (%)",
            min_value=0.0,
            max_value=15.0,
            value=float(wi["scenario_params"].get("return_pct", 7.0)),
            step=0.5,
        )
        scenario_params = {"additional_monthly_investment": amount, "annual_return_pct": return_pct}

    elif scenario_name == "Increase Income":
        pct = st.slider(
            "Increase income by (%)",
            min_value=0,
            max_value=100,
            value=int(wi["scenario_params"].get("pct", 5)),
            step=1,
        )
        adjusted_monthly_income = baseline_monthly_income * (1 + pct / 100.0)
        scenario_params = {"income_increase_pct": pct}

with c2:
    months_forward = st.slider("Project forward (months)", min_value=1, max_value=36, value=int(wi.get("months_forward", 12)), step=1)
    wi["months_forward"] = months_forward

wi["scenario_params"] = scenario_params
st.session_state["whatif_inputs"] = wi

# ----------------------------------------------------------------------
# Deterministic projection (Python performs the calculation)
# ----------------------------------------------------------------------
adjusted_monthly_expense = sum(adjusted_category_monthly.values())
adjusted_net_monthly = adjusted_monthly_income - adjusted_monthly_expense

if scenario_name == "Increase Investment Amount":
    amount = scenario_params["additional_monthly_investment"]
    return_pct = scenario_params["annual_return_pct"]
    adjusted_net_monthly = baseline_net_monthly - amount  # diverted into investment
    monthly_return = (1 + return_pct / 100.0) ** (1 / 12) - 1
    fv = 0.0
    investment_values = []
    for _ in range(months_forward):
        fv = fv * (1 + monthly_return) + amount
        investment_values.append(fv)
    investment_projection = {
        "monthly_contribution": amount,
        "annual_return_pct": return_pct,
        "future_value_after_months": round(fv, 2),
        "total_contributed": round(amount * months_forward, 2),
        "investment_growth": round(fv - amount * months_forward, 2),
    }

months = list(range(0, months_forward + 1))
baseline_cum = [baseline_net_monthly * m for m in months]
adjusted_cum = [adjusted_net_monthly * m for m in months]

whatif_results = {
    "baseline_monthly_income": round(baseline_monthly_income, 2),
    "baseline_monthly_expense": round(baseline_monthly_expense, 2),
    "adjusted_monthly_income": round(adjusted_monthly_income, 2),
    "adjusted_monthly_expense": round(adjusted_monthly_expense, 2),
    "baseline_net_monthly": round(baseline_net_monthly, 2),
    "adjusted_net_monthly": round(adjusted_net_monthly, 2),
    "net_monthly_change": round(adjusted_net_monthly - baseline_net_monthly, 2),
    "months_forward": months_forward,
    "baseline_cumulative_net": round(baseline_cum[-1], 2),
    "adjusted_cumulative_net": round(adjusted_cum[-1], 2),
}
if investment_projection:
    whatif_results["investment_projection"] = investment_projection

st.session_state["whatif_results"] = whatif_results

# ----------------------------------------------------------------------
# Results (Non-AI Mode - fully deterministic)
# ----------------------------------------------------------------------
st.divider()
st.markdown("#### 3. Projected impact (Python-computed)")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Baseline monthly net", format_currency(baseline_net_monthly))
m2.metric("Adjusted monthly net", format_currency(adjusted_net_monthly), delta=format_currency(adjusted_net_monthly - baseline_net_monthly))
m3.metric("Baseline monthly expense", format_currency(baseline_monthly_expense))
m4.metric("Adjusted monthly expense", format_currency(adjusted_monthly_expense), delta=format_currency(adjusted_monthly_expense - baseline_monthly_expense), delta_color="inverse")

fig = go.Figure()
fig.add_trace(go.Scatter(x=months, y=baseline_cum, name="Baseline (current trend)", mode="lines+markers", line=dict(color="#94A3B8")))
fig.add_trace(go.Scatter(x=months, y=adjusted_cum, name=f"What-if: {scenario_name}", mode="lines+markers", line=dict(color="#2E5BFF")))
if investment_projection:
    fig.add_trace(
        go.Scatter(
            x=list(range(1, months_forward + 1)),
            y=investment_values,
            name="Investment account value",
            mode="lines+markers",
            line=dict(color="#16A34A", dash="dot"),
        )
    )
fig.update_layout(
    height=420,
    margin=dict(l=10, r=10, t=30, b=10),
    xaxis_title="Months from now",
    yaxis_title="Cumulative Value (BYN)",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
st.plotly_chart(fig, use_container_width=True)

if investment_projection:
    st.caption(
        f"Investing {format_currency(investment_projection['monthly_contribution'])}/month at "
        f"{investment_projection['annual_return_pct']:.1f}% annual return for {months_forward} months "
        f"grows to {format_currency(investment_projection['future_value_after_months'])} "
        f"({format_currency(investment_projection['investment_growth'])} in growth on "
        f"{format_currency(investment_projection['total_contributed'])} contributed)."
    )

with st.expander("📦 What-if results (sent to the AI for explanation)", expanded=False):
    st.json(whatif_results)

st.divider()

# ----------------------------------------------------------------------
# AI explanation (LLM explains Python results - never recomputes)
# ----------------------------------------------------------------------
st.markdown("#### 🤖 AI Explanation")

ai_client = get_ai_client()
if ai_client is None:
    st.warning(
        "⚪ **Non-AI Mode** - `ANTHROPIC_API_KEY` is not configured. The Python results above "
        "are the full output of this page; configure AI to get a plain-language explanation."
    )

WHATIF_SYSTEM_PROMPT = (
    "You are a personal finance explainer. Python has ALREADY computed all numbers for a "
    "'what-if' scenario - you must NOT recompute, re-derive, or contradict any number. "
    "Your job is ONLY to explain what the given results mean in plain language: what changed, "
    "whether it's a meaningful improvement, and 1-2 practical considerations or caveats. "
    "Reference the FRED macro context briefly if relevant (e.g. inflation eroding savings). "
    "Amounts are in BYN. Keep it to 4-6 sentences or short bullet points. Do not give "
    "individualized investment/legal/tax advice."
)

if st.button("🤖 Generate AI explanation of this scenario", use_container_width=False):
    context = build_whatif_context(engine, filters, scenario_name, scenario_params, whatif_results)
    user_prompt = (
        f"What-if context package (JSON):\n{json.dumps(context, default=str, indent=2)}\n\n"
        "Explain these Python-computed results to the user."
    )
    with st.spinner("Asking the AI to explain these results..."):
        explanation = ask_ai(ai_client, WHATIF_SYSTEM_PROMPT, user_prompt, max_tokens=600)
    st.session_state["whatif_explanation"] = explanation

if st.session_state.get("whatif_explanation"):
    st.markdown(st.session_state["whatif_explanation"])

st.caption(
    "Projection assumes the adjusted monthly income/expense levels hold constant for every "
    "projected month (simple linear projection). All figures above are computed in Python; "
    "the AI only explains them."
)
