"""
Page 7 - FIRE Planner
=======================
Financial Independence, Retire Early (FIRE) calculator.

Formula (per project spec):
    FIRE Number = Annual Expense x 25   (equivalent to a 4% safe withdrawal rate)

Python calculates:
  - FIRE Number
  - Monthly contribution, portfolio projection
  - Years to FIRE / FIRE Age
  - Scenario Analysis (alternate return rates and withdrawal rates)

The LLM only EXPLAINS these Python-computed results - FIRE Readiness,
Risks, and Recommendations - via a small context package
(`common.ai_context.build_fire_context`) that also includes FRED
macroeconomic indicators (inflation, rates, unemployment).

Fully deterministic (Non-AI Mode) without an AI client. Scenarios can be
saved to MongoDB (`fire_simulations`).
"""

from __future__ import annotations

import json

import common.bootstrap  # noqa: F401

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from common.ai_client import ask_ai, get_ai_client
from common.ai_context import build_fire_context
from common.data_access import ensure_duckdb_loaded, get_mongo_repo, load_fire_simulations, query_monthly_summary, save_fire_simulation
from common.ui import configure_page, data_source_badge, format_currency, page_header, render_global_filters, render_sidebar_header

configure_page("FIRE Planner")
render_sidebar_header()

engine = ensure_duckdb_loaded()
filters = render_global_filters()

page_header(
    "FIRE Planner",
    subtitle="FIRE Number = Annual Expense x 25 (4% rule). Python computes the numbers; AI explains them.",
    icon="🔥",
)
data_source_badge()
st.write("")

monthly = query_monthly_summary(engine, filters)
n_months = max(len(monthly), 1)
default_income = float(monthly["total_income"].sum()) / n_months if not monthly.empty else 0.0
default_expense = float(monthly["total_expense"].sum()) / n_months if not monthly.empty else 0.0

fi = st.session_state["fire_inputs"]
if not fi.get("monthly_income"):
    fi["monthly_income"] = round(default_income, 2)
if not fi.get("monthly_expense"):
    fi["monthly_expense"] = round(default_expense, 2)

# ----------------------------------------------------------------------
# Inputs (bound to st.session_state["fire_inputs"])
# ----------------------------------------------------------------------
st.markdown("#### Your numbers")
c1, c2, c3 = st.columns(3)

with c1:
    fi["current_savings"] = st.number_input("Current savings / investments (BYN)", min_value=0.0, step=100.0, value=float(fi["current_savings"]))
    fi["monthly_income"] = st.number_input("Average monthly income (BYN)", min_value=0.0, step=10.0, value=float(fi["monthly_income"]))
    fi["monthly_expense"] = st.number_input("Average monthly expense (BYN)", min_value=0.0, step=10.0, value=float(fi["monthly_expense"]))

with c2:
    fi["annual_return_pct"] = st.slider("Expected annual return (%)", min_value=0.0, max_value=15.0, value=float(fi["annual_return_pct"]), step=0.5)
    st.metric("FIRE withdrawal rate (fixed)", "4.0%", help="FIRE Number = Annual Expense x 25, equivalent to a 4% safe withdrawal rate.")

with c3:
    fi["current_age"] = st.number_input("Current age", min_value=16, max_value=80, step=1, value=int(fi["current_age"]))
    fi["target_age"] = st.number_input("Plan until age", min_value=int(fi["current_age"]) + 1, max_value=100, step=1, value=max(int(fi["target_age"]), int(fi["current_age"]) + 1))

st.session_state["fire_inputs"] = fi

# ----------------------------------------------------------------------
# FIRE calculations (deterministic - Python only)
# ----------------------------------------------------------------------
def project_fire_age(
    monthly_expense: float,
    monthly_income: float,
    current_savings: float,
    annual_return_pct: float,
    current_age: int,
    target_age: int,
    fire_number: float,
) -> tuple[float | None, pd.DataFrame]:
    monthly_contribution = max(monthly_income - monthly_expense, 0.0)
    monthly_return = (1 + annual_return_pct / 100.0) ** (1 / 12) - 1
    total_months = (int(target_age) - int(current_age)) * 12

    ages, balances = [], []
    balance = current_savings
    fire_age = None
    for m in range(total_months + 1):
        age = current_age + m / 12
        ages.append(age)
        balances.append(balance)
        if fire_age is None and fire_number > 0 and balance >= fire_number:
            fire_age = age
        balance = balance * (1 + monthly_return) + monthly_contribution

    return fire_age, pd.DataFrame({"age": ages, "portfolio_value": balances})


annual_expenses = fi["monthly_expense"] * 12
fire_number = annual_expenses * 25  # FIRE Number = Annual Expense x 25 (4% rule)
monthly_contribution = max(fi["monthly_income"] - fi["monthly_expense"], 0.0)

fire_age, projection_df = project_fire_age(
    fi["monthly_expense"], fi["monthly_income"], fi["current_savings"],
    fi["annual_return_pct"], fi["current_age"], fi["target_age"], fire_number,
)
years_to_fire = round(fire_age - fi["current_age"], 1) if fire_age else None

st.divider()
st.markdown("#### Results")

m1, m2, m3, m4 = st.columns(4)
m1.metric("FIRE number (25x annual expense)", format_currency(fire_number))
m2.metric("Monthly contribution", format_currency(monthly_contribution))
m3.metric("Age at FIRE", f"{fire_age:.1f}" if fire_age else f"Not within {fi['target_age']}")
m4.metric("Years to FIRE", f"{years_to_fire:.1f}" if years_to_fire is not None else "—")

fig = go.Figure()
fig.add_trace(go.Scatter(x=projection_df["age"], y=projection_df["portfolio_value"], name="Projected portfolio", mode="lines", line=dict(color="#2E5BFF")))
fig.add_hline(y=fire_number, line_dash="dash", line_color="#DC2626", annotation_text="FIRE number", annotation_position="top left")
if fire_age:
    fig.add_vline(x=fire_age, line_dash="dot", line_color="#16A34A", annotation_text=f"FIRE at age {fire_age:.1f}")
fig.update_layout(
    height=440,
    margin=dict(l=10, r=10, t=30, b=10),
    xaxis_title="Age",
    yaxis_title="Portfolio Value (BYN)",
)
st.plotly_chart(fig, use_container_width=True)

if monthly_contribution <= 0:
    st.warning(
        "Your average monthly expenses meet or exceed your average monthly income for the "
        "selected period, so the projection assumes zero new contributions - the portfolio will "
        "only grow from investment returns on existing savings."
    )

st.caption(
    f"Default income/expense values are pre-filled from your DuckDB-derived average for the "
    f"selected period ({format_currency(default_income)} income, {format_currency(default_expense)} expense per month) - adjust them above to explore scenarios."
)

# ----------------------------------------------------------------------
# Scenario Analysis (Python computed)
# ----------------------------------------------------------------------
st.divider()
st.markdown("#### Scenario Analysis")

st.markdown("##### If your investment return differs")
return_scenarios = []
for label, delta in [("Conservative (-2pp)", -2.0), ("Base case", 0.0), ("Aggressive (+2pp)", 2.0)]:
    rr = max(0.0, fi["annual_return_pct"] + delta)
    f_age, _ = project_fire_age(fi["monthly_expense"], fi["monthly_income"], fi["current_savings"], rr, fi["current_age"], fi["target_age"], fire_number)
    return_scenarios.append({
        "scenario": label,
        "annual_return_pct": round(rr, 2),
        "fire_age": round(f_age, 1) if f_age else None,
        "years_to_fire": round(f_age - fi["current_age"], 1) if f_age else None,
    })
return_scenarios_df = pd.DataFrame(return_scenarios)
st.dataframe(return_scenarios_df, use_container_width=True, hide_index=True)

st.markdown("##### If your target safe withdrawal rate differs")
withdrawal_scenarios = []
for wr in (3.0, 4.0, 5.0):
    fn = annual_expenses / (wr / 100.0)
    f_age, _ = project_fire_age(fi["monthly_expense"], fi["monthly_income"], fi["current_savings"], fi["annual_return_pct"], fi["current_age"], fi["target_age"], fn)
    withdrawal_scenarios.append({
        "withdrawal_rate_pct": wr,
        "fire_number": round(fn, 2),
        "fire_age": round(f_age, 1) if f_age else None,
        "years_to_fire": round(f_age - fi["current_age"], 1) if f_age else None,
        "is_default_25x": wr == 4.0,
    })
withdrawal_scenarios_df = pd.DataFrame(withdrawal_scenarios)
st.dataframe(
    withdrawal_scenarios_df.style.format({"fire_number": "{:,.2f}"}),
    use_container_width=True,
    hide_index=True,
)
st.caption("The 4% row (FIRE Number = Annual Expense x 25) is the primary number used above.")

fire_results = {
    "fire_number": round(fire_number, 2),
    "annual_expenses": round(annual_expenses, 2),
    "monthly_contribution": round(monthly_contribution, 2),
    "fire_age": round(fire_age, 1) if fire_age else None,
    "years_to_fire": years_to_fire,
    "current_age": fi["current_age"],
    "target_age": fi["target_age"],
    "return_rate_scenarios": return_scenarios,
    "withdrawal_rate_scenarios": withdrawal_scenarios,
}
st.session_state["fire_results"] = fire_results

with st.expander("📦 FIRE results (sent to the AI for explanation)", expanded=False):
    st.json(fire_results)

st.divider()

# ----------------------------------------------------------------------
# AI explanation (LLM explains Python results - never recomputes)
# ----------------------------------------------------------------------
st.markdown("#### 🤖 AI Explanation")

ai_client = get_ai_client()
if ai_client is None:
    st.warning(
        "⚪ **Non-AI Mode** - `ANTHROPIC_API_KEY` is not configured. The Python results above "
        "are the full output of this page; configure AI for FIRE Readiness / Risks / Recommendations."
    )

FIRE_SYSTEM_PROMPT = (
    "You are a personal finance explainer. Python has ALREADY computed all FIRE (Financial "
    "Independence, Retire Early) numbers - you must NOT recompute or contradict any number. "
    "Using ONLY the provided JSON context (FIRE results + FRED macro context), write a short "
    "report with EXACTLY these three sections as markdown headings:\n"
    "## FIRE Readiness\n"
    "## Risks\n"
    "## Recommendations\n"
    "Amounts are in BYN. Reference the macro context (inflation, rates) briefly where relevant "
    "(e.g. inflation eroding a fixed FIRE number over time). Keep each section to 2-4 bullet "
    "points. Do not give individualized investment/legal/tax advice."
)

if st.button("🤖 Generate AI explanation (FIRE Readiness, Risks, Recommendations)"):
    context = build_fire_context(fi, fire_results)
    user_prompt = f"FIRE context package (JSON):\n{json.dumps(context, default=str, indent=2)}\n\nExplain these results."
    with st.spinner("Asking the AI to assess your FIRE plan..."):
        explanation = ask_ai(ai_client, FIRE_SYSTEM_PROMPT, user_prompt, max_tokens=900)
    st.session_state["fire_explanation"] = explanation

if st.session_state.get("fire_explanation"):
    st.markdown(st.session_state["fire_explanation"])

st.divider()

# ----------------------------------------------------------------------
# Save scenario
# ----------------------------------------------------------------------
st.markdown("#### Save this scenario")
if st.button("💾 Save FIRE scenario", use_container_width=False):
    simulation = {
        "inputs": dict(fi),
        "results": {**fire_results, "filters": filters},
    }
    sim_id = save_fire_simulation(simulation)
    if sim_id:
        st.success(f"Scenario saved (id={sim_id}).")
        load_fire_simulations.clear()
    else:
        st.warning("MongoDB is not connected, so this scenario could not be persisted.")

saved = load_fire_simulations()
if saved.empty:
    mongo = get_mongo_repo()
    if mongo is None:
        st.info("MongoDB is not connected - saved scenarios are not available in offline mode.")
else:
    st.markdown("##### Saved scenarios")
    st.dataframe(saved, use_container_width=True, hide_index=True)
