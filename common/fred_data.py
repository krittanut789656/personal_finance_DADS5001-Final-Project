"""
FRED Macroeconomic Data Integration (Phase 4)
================================================
Fetches a small set of macroeconomic indicators from the Federal Reserve
Economic Data (FRED) API to use as *macroeconomic context* for the AI
layer (AI Financial Intelligence, What-if Simulator, FIRE Planner).

Indicators (per project spec):
  - CPIAUCSL : Consumer Price Index (used to derive YoY inflation %)
  - FEDFUNDS : Effective Federal Funds Rate
  - UNRATE   : Civilian Unemployment Rate

This module returns only small, aggregated/derived values (latest level +
YoY change for CPI) - never bulk time series - keeping AI prompts compact.

FRED is OPTIONAL. If `FRED_API_KEY` is not configured, or the request
fails (e.g. no network access), `get_macro_context()` returns
`{"available": False, ...}` and callers should treat macro context as
absent without raising.
"""

from __future__ import annotations

import common.bootstrap  # noqa: F401  -- must run before backend imports

import streamlit as st

from config.settings import settings
from core.logger import get_logger

logger = get_logger(__name__)

FRED_OBSERVATIONS_PATH = "/series/observations"


def _fetch_observations(series_id: str, api_key: str, limit: int = 13) -> list[dict]:
    """Return up to `limit` most recent non-missing observations for `series_id`."""
    import requests

    url = f"{settings.fred.base_url}{FRED_OBSERVATIONS_PATH}"
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "sort_order": "desc",
        "limit": limit,
    }
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return [obs for obs in data.get("observations", []) if obs.get("value") not in (None, ".")]


@st.cache_data(ttl=6 * 60 * 60, show_spinner="Fetching FRED macroeconomic indicators...")
def get_macro_context() -> dict:
    """
    Return a compact macroeconomic context package:

        {
            "available": True,
            "source": "FRED (Federal Reserve Economic Data)",
            "indicators": {
                "CPIAUCSL": {"label": ..., "latest_value": ..., "latest_date": ..., "yoy_change_pct": ...},
                "FEDFUNDS": {"label": ..., "latest_value": ..., "latest_date": ...},
                "UNRATE":   {"label": ..., "latest_value": ..., "latest_date": ...},
            },
        }

    or `{"available": False, "reason": "..."}` if FRED is not configured or
    the request fails. Cached for 6 hours so repeated page loads within a
    session don't re-hit the FRED API.
    """
    if not settings.fred.is_configured():
        return {
            "available": False,
            "reason": "FRED_API_KEY not configured - macroeconomic context is unavailable.",
            "indicators": {},
        }

    indicators: dict = {}
    try:
        for series_id, label in settings.fred.indicators.items():
            obs = _fetch_observations(series_id, settings.fred.api_key, limit=13)
            if not obs:
                continue
            latest = obs[0]
            entry = {
                "label": label,
                "latest_value": float(latest["value"]),
                "latest_date": latest["date"],
            }
            if series_id == "CPIAUCSL" and len(obs) >= 13:
                year_ago = obs[12]
                try:
                    yoy = (float(latest["value"]) - float(year_ago["value"])) / float(year_ago["value"]) * 100
                    entry["yoy_change_pct"] = round(yoy, 2)
                    entry["yoy_note"] = "Approximate headline CPI inflation, year-over-year"
                except ZeroDivisionError:
                    pass
            indicators[series_id] = entry

        if not indicators:
            return {"available": False, "reason": "FRED returned no usable observations.", "indicators": {}}

        return {
            "available": True,
            "source": "FRED (Federal Reserve Economic Data) - api.stlouisfed.org",
            "indicators": indicators,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("FRED request failed: %s", exc)
        return {"available": False, "reason": f"FRED request failed: {exc}", "indicators": {}}
