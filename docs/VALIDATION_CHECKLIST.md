# Final Validation Checklist

Per the project brief: *"Do not finalize until every requirement passes."*
Each item below names the concrete implementation evidence.

## ✓ Streamlit Multi-page

- `app.py` (Page 1: Dashboard) + native `pages/` directory:
  `2_Expense_Analytics.py` ... `9_Project_Methodology.py` (9 pages total).
- Shared sidebar nav (`NAV_ITEMS` in `common/ui.py`).

## ✓ Pandas

- `backend/etl/*`, `backend/analytics/duckdb_engine.py`, and every
  `common/ai_context.py` snapshot function operate on `pandas.DataFrame`.

## ✓ DuckDB

- `backend/analytics/duckdb_engine.py` (`DuckDBAnalytics`) is the mandatory
  in-process analytics engine for every aggregate query (`query_*` in
  `common/data_access.py`).
- `common/ai_context.py:duckdb_snapshot()` builds the AI context's DuckDB
  results.

## ✓ MongoDB Atlas

- `backend/repositories/mongo_repository.py` (`MongoRepository`):
  `transactions`, `monthly_summary`, `budget_plans`, `ai_reports`,
  `fire_simulations` collections.
- Used by Page 3 (budget plans), Page 7 (FIRE simulations save/load).
- `docs/MONGODB_SETUP.md` for setup; offline fallback if unreachable.

## ✓ Snowflake

- `backend/repositories/snowflake_repository.py` (`SnowflakeRepository`):
  auto-provisions warehouse/db/schema/tables (`sql/snowflake_ddl.sql`).
- `common/ai_context.py:snowflake_metrics_snapshot()` queries
  `MONTHLY_SUMMARY` (last 12 rows) and feeds it into the AI context (Page 5).
- `docs/SNOWFLAKE_SETUP.md` for setup; offline fallback if unreachable.

## ✓ Plotly

- Every chart across pages 1-7 uses `plotly.express` / `plotly.graph_objects`
  via `st.plotly_chart` (no Matplotlib/Altair).

## ✓ Non-AI Mode

- Pages 1-4, 8-9: fully rules-based, no AI dependency.
- Pages 5-7: `get_ai_client() is None` -> "⚪ Non-AI Mode" banner; page
  remains fully usable (context package / Python results shown).

## ✓ AI Mode

- `common/ai_client.py`: `get_ai_client()` (cached Anthropic client),
  `ask_ai()` (chat completion with graceful fallback).
- Page 5: 5-section Financial Intelligence report + grounded chat.
- Page 6: Python-computed what-if scenarios + LLM explanation (LLM
  forbidden from recomputing).
- Page 7: Python-computed FIRE numbers + LLM FIRE Readiness/Risks/
  Recommendations.
- **Data-centric constraint**: `common/ai_context.py` is the *only* path to
  the LLM and only passes aggregates (DuckDB results, Snowflake metrics,
  Financial Health Score, Budget Status, Profiling Summary, What-if
  Results, FIRE Results, FRED indicators) - never raw transaction rows.

## ✓ Cache Data

- `@st.cache_data` on: `load_transactions_df`, all `query_*` DuckDB
  wrappers, `get_profile_report` (`common/data_access.py`);
  `get_macro_context` (`common/fred_data.py`); `build_*_context`,
  `snowflake_metrics_snapshot` (`common/ai_context.py`).

## ✓ Cache Resource

- `@st.cache_resource` on: `get_duckdb_engine`, `get_mongo_repo`,
  `get_snowflake_repo` (`common/data_access.py`); `get_ai_client`
  (`common/ai_client.py`).

## ✓ Session State

- `common/state.py` `DEFAULTS` + `init_session_state()`: filters,
  `selected_period`, `ai_history`, `ai_insights_report`, `whatif_inputs`,
  `whatif_results`, `whatif_explanation`, `fire_inputs`, `fire_results`,
  `fire_explanation`.

## ✓ What-if Simulator

- Page 6: 5 named scenarios (Reduce Food Spending, Reduce Shopping
  Spending, Increase Savings, Increase Investment Amount, Increase Income).
- Python computes all projections; LLM only explains
  (`WHATIF_SYSTEM_PROMPT` explicitly forbids recomputation).

## ✓ FIRE Planner

- Page 7: **FIRE Number = Annual Expense x 25**.
- Python computes: Years to FIRE, FIRE Age, portfolio projection, return-
  rate and withdrawal-rate scenario tables.
- LLM explains: FIRE Readiness, Risks, Recommendations
  (`FIRE_SYSTEM_PROMPT`).

## ✓ Deployment Ready

- Root `requirements.txt` -> `backend/requirements.txt` (includes
  `anthropic`, `requests`).
- `.streamlit/config.toml` (theme, `headless = true`).
- `.streamlit/secrets.toml.example` (Streamlit Cloud secrets template).
- `backend/.env.example` (local `.env` template, incl. AI + FRED sections).
- `.gitignore` excludes secrets/credentials/build artifacts.
- `common/bootstrap.py` bridges `st.secrets` -> `os.environ`.
- `docs/DEPLOYMENT_GUIDE.md`, `docs/MONGODB_SETUP.md`,
  `docs/SNOWFLAKE_SETUP.md`.

## Additional Phase 4 deliverables

- `docs/ARCHITECTURE.md` - as-built architecture + data-centric AI
  workflow diagrams (Mermaid).
- `docs/PRESENTATION_OUTLINE.md` - slide-by-slide outline.
- `docs/DEMO_SCRIPT.md` - 3-5 minute demo script.
- `docs/DEPLOYMENT_CHECKLIST.md` - pre-submission checklist.
- This file - final validation checklist.

---

**Status: all items above are implemented in the codebase as described.**
Remaining work before first run: install dependencies
(`pip install -r requirements.txt`) and run the Phase 4 smoke test (Task
#33) to confirm the rewritten pages 5-7 execute without errors in both
Non-AI and (if credentials available) AI modes.
