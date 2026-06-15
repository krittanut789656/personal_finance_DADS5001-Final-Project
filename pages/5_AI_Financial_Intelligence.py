"""
Page 5 - AI Financial Intelligence
====================================
Data-centric AI workflow:

    Data -> Metadata -> Statistical Summary -> Context Package -> LLM -> Insight

The LLM NEVER sees raw transaction rows. `common.ai_context` assembles a
compact JSON "context package" from DuckDB aggregates, the Financial Health
Score, Budget Status, Profiling Summary, Snowflake metrics (if connected),
and FRED macroeconomic indicators. That package - and ONLY that package - is
sent to the model.

AI Mode vs. Non-AI Mode:
  - If `ANTHROPIC_API_KEY` is configured, `get_ai_client()` returns a real
    client and this page generates an LLM-written insights report + answers
    follow-up questions in the chat.
  - If not, the page still shows the full context package (everything the
    LLM *would* see) and explains how to enable AI Mode.
"""

from __future__ import annotations

import datetime as dt
import json

import common.bootstrap  # noqa: F401

import streamlit as st

from common.ai_client import ask_ai, get_ai_client
from common.ai_context import build_financial_intelligence_context
from common.data_access import ensure_duckdb_loaded
from common.ui import configure_page, data_source_badge, page_header, render_global_filters, render_sidebar_header

configure_page("AI Financial Intelligence")
render_sidebar_header()

engine = ensure_duckdb_loaded()
filters = render_global_filters()

page_header(
    "AI Financial Intelligence",
    subtitle="LLM-generated insights from a compact, aggregated context package - never raw transactions.",
    icon="🤖",
)
data_source_badge()
st.write("")

ai_client = get_ai_client()
ai_mode = ai_client is not None

if ai_mode:
    st.success("🟢 **AI Mode** - connected to the configured Anthropic model. Insights below are LLM-generated.")
else:
    st.warning(
        "⚪ **Non-AI Mode** - `ANTHROPIC_API_KEY` is not configured, so no LLM calls are made. "
        "The context package below shows exactly what *would* be sent to the AI. "
        "Add your key to `.env` (see `.env.example`) to enable AI Mode."
    )

# ----------------------------------------------------------------------
# Context package - what gets sent to the LLM (aggregates only)
# ----------------------------------------------------------------------
context = build_financial_intelligence_context(engine, filters)

with st.expander("📦 AI context package (sent to the LLM - aggregates only, never raw transactions)", expanded=False):
    st.json(context)
    st.caption(
        "Data -> Metadata -> Statistical Summary -> Context Package -> LLM -> Insight. "
        "This object contains DuckDB results, the Financial Health Score, Budget Status, "
        "a Profiling Summary, Snowflake metrics (if connected), and FRED macro indicators - "
        "no transaction-level rows."
    )

st.divider()

# ----------------------------------------------------------------------
# AI Financial Intelligence report
# ----------------------------------------------------------------------
st.markdown("#### 🧠 Financial Intelligence Report")
st.caption(
    "Generates: Spending Insights, Financial Risks, Budget Problems, Savings Opportunities, "
    "and Recommended Actions - based entirely on the context package above."
)

REPORT_SYSTEM_PROMPT = (
    "You are a careful, data-grounded personal finance analyst embedded in a dashboard. "
    "You receive ONLY a JSON context package of pre-aggregated statistics - never raw "
    "transaction rows. Base every statement strictly on the numbers in the context. "
    "If the context is insufficient for a section, say so explicitly rather than guessing. "
    "Amounts are in BYN. Keep recommendations general and educational, not individualized "
    "financial/legal/tax advice. Use the FRED macro context to add brief situational color "
    "(e.g. inflation, interest rates) where relevant, but do not overstate its importance."
)

REPORT_USER_PROMPT_TEMPLATE = (
    "Here is the current AI context package (JSON):\n\n{context_json}\n\n"
    "Write a financial intelligence report with EXACTLY these five sections, as markdown "
    "headings, in this order:\n"
    "## Spending Insights\n"
    "## Financial Risks\n"
    "## Budget Problems\n"
    "## Savings Opportunities\n"
    "## Recommended Actions\n\n"
    "Each section should be 2-4 concise bullet points, referencing specific numbers from "
    "the context where possible. If 'budget_status' is unavailable, say so under "
    "'Budget Problems' and suggest creating a budget plan."
)

col_gen, col_clear = st.columns([1, 1])
with col_gen:
    generate_clicked = st.button("✨ Generate Financial Intelligence Report", use_container_width=True)
with col_clear:
    if st.button("Clear report", use_container_width=True):
        st.session_state.pop("ai_insights_report", None)
        st.rerun()

if generate_clicked:
    context_json = json.dumps(context, default=str, indent=2)
    user_prompt = REPORT_USER_PROMPT_TEMPLATE.format(context_json=context_json)
    with st.spinner("Asking the AI to analyze your finances..."):
        report_text = ask_ai(ai_client, REPORT_SYSTEM_PROMPT, user_prompt, max_tokens=1400)
    st.session_state["ai_insights_report"] = report_text

if st.session_state.get("ai_insights_report"):
    st.markdown(st.session_state["ai_insights_report"])
elif not ai_mode:
    st.info("Click **Generate Financial Intelligence Report** to see what the AI would receive (Non-AI Mode message).")

st.divider()

# ----------------------------------------------------------------------
# Chat-style follow-up Q&A (session_state["ai_history"])
# ----------------------------------------------------------------------
st.markdown("#### 💬 Ask a follow-up question")
st.caption("Answers are grounded in the same context package shown above.")

for msg in st.session_state["ai_history"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        st.caption(msg["timestamp"])

prompt = st.chat_input("e.g. Why did my expenses increase last month? What should I prioritize?")

if prompt:
    st.session_state["ai_history"].append(
        {"role": "user", "content": prompt, "timestamp": dt.datetime.now().strftime("%Y-%m-%d %H:%M")}
    )

    chat_system_prompt = REPORT_SYSTEM_PROMPT + (
        " You are now answering a specific follow-up question from the user. "
        "Be concise (a short paragraph or a few bullets)."
    )
    chat_user_prompt = (
        f"AI context package (JSON):\n{json.dumps(context, default=str, indent=2)}\n\n"
        f"User question: {prompt}\n\n"
        "Answer using only the context above. If the context doesn't contain the answer, "
        "say what additional data would be needed."
    )
    with st.spinner("Thinking..."):
        reply = ask_ai(ai_client, chat_system_prompt, chat_user_prompt, max_tokens=800)

    st.session_state["ai_history"].append(
        {"role": "assistant", "content": reply, "timestamp": dt.datetime.now().strftime("%Y-%m-%d %H:%M")}
    )
    st.rerun()

if st.session_state["ai_history"]:
    if st.button("Clear conversation"):
        st.session_state["ai_history"] = []
        st.rerun()
