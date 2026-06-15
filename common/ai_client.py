"""
AI Client Layer (Phase 4)
==========================
Thin wrapper around the Anthropic Claude API, exposed as an
`@st.cache_resource` resource so the client (and its connection pool) is
created once per Streamlit session.

DATA-CENTRIC AI CONSTRAINT
---------------------------
This module NEVER receives raw transaction rows or full DataFrames. Every
caller MUST build its prompt from a small "context package" assembled by
`common/ai_context.py`, which only contains:

  - DuckDB aggregate results (monthly summaries, category breakdowns, ...)
  - Snowflake metrics (if connected)
  - Financial Health Score (sub-scores + composite)
  - Budget Status (plan vs. actual, by category)
  - Profiling Summary (column-level stats, NOT row-level data)
  - What-if Results (Python-computed projections)
  - FIRE Results (Python-computed FIRE numbers / projections)
  - FRED macroeconomic indicators (CPI, Fed Funds rate, unemployment)

AI is OPTIONAL. If `ANTHROPIC_API_KEY` is not configured, `get_ai_client()`
returns `None` and every page falls back to "Non-AI Mode" - Python-only
calculations and rules-based summaries, with no LLM narrative.
"""

from __future__ import annotations

import common.bootstrap  # noqa: F401  -- must run before backend imports

import streamlit as st

from config.settings import settings
from core.logger import get_logger

logger = get_logger(__name__)


@st.cache_resource(show_spinner=False)
def get_ai_client():
    """
    Return a cached `anthropic.Anthropic` client, or `None` if AI is not
    configured / the SDK is unavailable.

    Every AI-powered page (5, 6, 7) calls this once and checks for `None`
    to decide whether to render "AI Mode" (LLM narrative) or "Non-AI Mode"
    (Python-only results).
    """
    if not settings.ai.is_configured():
        logger.info("AI client not configured (ANTHROPIC_API_KEY missing) - running in Non-AI Mode.")
        return None
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.ai.api_key)
        logger.info("AI client initialized (model=%s)", settings.ai.model)
        return client
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to initialize AI client, running in Non-AI Mode: %s", exc)
        return None


def ask_ai(client, system_prompt: str, user_prompt: str, max_tokens: int | None = None) -> str:
    """
    Send `system_prompt` + `user_prompt` to the LLM and return the text
    response. `user_prompt` must be built from an AI context package
    (`common/ai_context.py`) - never from raw transaction data.

    Returns a short, user-facing message (instead of raising) if the
    client is `None` or the request fails, so pages can render the
    returned string directly without extra error handling.
    """
    if client is None:
        return (
            "🤖 AI is not configured for this session. Set `ANTHROPIC_API_KEY` "
            "(see `.env.example`) to enable AI-generated insights and "
            "explanations. All calculations on this page are still computed "
            "in Python (Non-AI Mode)."
        )
    try:
        response = client.messages.create(
            model=settings.ai.model,
            max_tokens=max_tokens or settings.ai.max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        parts = [block.text for block in response.content if getattr(block, "type", None) == "text"]
        text = "\n".join(parts).strip()
        return text or "_(The AI returned an empty response.)_"
    except Exception as exc:  # noqa: BLE001
        logger.warning("AI request failed: %s", exc)
        return f"⚠️ AI request failed: `{exc}`. Showing Python-computed results only (Non-AI Mode)."
