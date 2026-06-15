"""
Page 9 - Project Methodology
==============================
Static reference page describing the project architecture, requirement
compliance, and the Non-AI / AI mode design.
"""

from __future__ import annotations

import common.bootstrap  # noqa: F401

import streamlit as st

from common.data_access import ensure_duckdb_loaded, query_date_range
from common.ui import configure_page, page_header, render_sidebar_header

configure_page("Project Methodology")
render_sidebar_header()

with st.sidebar:
    st.markdown("#### ℹ️ About")
    st.caption("This page documents how the platform is built and why - no filters apply here.")

page_header(
    "Project Methodology",
    subtitle="DADS5001 Final Project — AI Personal Finance Intelligence Platform",
    icon="📐",
)

engine = ensure_duckdb_loaded()
dr = query_date_range(engine)

st.markdown(
    f"""
### Project Overview

The **AI Personal Finance Intelligence Platform** is a multi-page Streamlit application
that turns a personal expenses/income transaction log
({dr['row_count']:,} transactions, {dr['min_date']} → {dr['max_date']}) into a full
analytics, planning, and (eventually) AI-assisted financial intelligence platform.

The project is built in phases:

| Phase | Scope | Status |
|---|---|---|
| 1 | Architecture & requirement analysis (no code) | ✅ Done |
| 2 | Backend layer: ETL, MongoDB, Snowflake, DuckDB, profiling, config, logging | ✅ Done |
| 3 | Streamlit multi-page UI (this app) | ✅ Done |
| 4 | AI prompts / metadata-to-LLM workflow | 🚧 Planned |

---

### Architecture at a Glance

```
CSV (Expenses_clean.csv)
   │
   ▼
ETL Pipeline (extract → transform)
   │
   ▼
DuckDB  ──────────────► (mandatory analytics engine for ALL pages)
   │
   ├──► MongoDB Atlas (operational store: transactions, monthly_summary,
   │        budget_plans, ai_reports, fire_simulations)
   │
   └──► Snowflake (cloud warehouse: TRANSACTIONS, MONTHLY_SUMMARY,
            BUDGET_PLANS, AI_REPORTS, FIRE_SIMULATIONS)

Streamlit App (9 pages)
   │
   ├── @st.cache_resource → Mongo / Snowflake / DuckDB connections, AI client
   ├── @st.cache_data      → dataset loading, DuckDB query results, profiling
   └── st.session_state    → filters, selected period, AI history,
                              FIRE inputs, What-if inputs
```

---

### Requirement Compliance

| Requirement | Where it's satisfied |
|---|---|
| **Streamlit Multi-page** | `app.py` (Dashboard) + `pages/2-9` (native Streamlit multi-page) |
| **Pandas** | Used throughout ETL, transform, profiling, and as the DataFrame interface to DuckDB |
| **DuckDB** | Mandatory analytics engine - `analytics/duckdb_engine.py`; every chart/KPI on every page is computed via `DuckDBAnalytics` |
| **MongoDB Atlas** | `repositories/mongo_repository.py` - 5 collections: `transactions`, `monthly_summary`, `budget_plans`, `ai_reports`, `fire_simulations` |
| **Snowflake** | `repositories/snowflake_repository.py` - auto-provisions warehouse/database/schema/tables |
| **Non-AI Mode** | Dashboard, Expense Analytics, Budget Planner, Financial Health Score, FIRE Planner, What-if projections - all rules-based / DuckDB SQL |
| **AI Mode** | AI Financial Intelligence + AI What-if Simulator pages - structure, caching, and session state are wired; LLM prompts are Phase 4 |
| **@st.cache_data** | Dataset loading (`load_transactions_df`), DuckDB query wrappers, profiling report (`get_profile_report`) |
| **@st.cache_resource** | MongoDB connection, Snowflake connection, DuckDB engine, AI client (`get_ai_client`) |
| **st.session_state** | Filters, selected period, `ai_history`, `fire_inputs`, `whatif_inputs` |
| **Plotly Visualization** | All charts use `plotly.express` / `plotly.graph_objects` exclusively |
| **GitHub Submission** | Project follows a clean `backend/` + `common/` + `pages/` structure suitable for version control |
| **Streamlit Deployment** | Single entry point (`app.py`), `requirements.txt`, `.streamlit/config.toml` theme |

---

### Page Map

1. **Dashboard** - headline KPIs, income vs. expense trend, top categories, account breakdown
2. **Expense Analytics** - category treemap, MoM trends, anomaly detection (z-score)
3. **Budget Planner** - create per-category budgets, compare actual vs. plan
4. **Financial Health Score** - composite 0-100 score (savings rate, stability, diversification)
5. **AI Financial Intelligence** - chat-style Q&A scaffold + metadata-to-LLM payload preview (Phase 4)
6. **AI What-if Simulator** - deterministic income/expense scenario projections + AI explanation placeholder (Phase 4)
7. **FIRE Planner** - FIRE number, contribution rate, portfolio projection, scenario saving
8. **Dataset Profiling** - structural (Pandas, raw) and statistical (DuckDB, cleaned) data profiles
9. **Project Methodology** - this page

---

### Non-AI vs. AI Mode

- **Non-AI Mode** (pages 1-4, 7-8): every number on screen is the direct output of a
  DuckDB SQL query or a transparent formula (shown on the Financial Health Score page).
  This mode works fully offline with just the local CSV.
- **AI Mode** (pages 5-6): structured around a *metadata-to-LLM* workflow - instead of
  sending raw transaction rows to an LLM, the app first computes a compact metadata
  summary (via DuckDB) and will pass that to the LLM in Phase 4. This keeps prompts
  small, cheap, and avoids exposing raw financial records.

### Offline / Degraded Mode

If `MONGODB_URI` / Snowflake credentials are not configured, the app automatically
falls back to loading transactions from the local CSV via the Phase 2 ETL pipeline,
and Budget Planner / FIRE Planner persistence features show a notice instead of
failing. DuckDB analytics work identically either way.
"""
)
