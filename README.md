# AI Personal Finance Intelligence Platform

A multi-page Streamlit application for personal finance analytics, budgeting,
financial health scoring, AI-powered insights, what-if simulation, and FIRE
planning - built on a DuckDB + MongoDB Atlas + Snowflake backend, with an
optional Anthropic Claude AI layer and FRED macroeconomic context.

DADS5001 Final Project. See `Architecture_Analysis_AI_Personal_Finance_Platform.md`
for the Phase 1 architecture analysis, `docs/ARCHITECTURE.md` for the
as-built (Phase 4) architecture diagrams, and `backend/README.md` for the
Phase 2 backend layer documentation.

## Documentation index

| Doc | Purpose |
|---|---|
| `docs/ARCHITECTURE.md` | As-built architecture + data-centric AI workflow diagrams |
| `docs/MONGODB_SETUP.md` | MongoDB Atlas setup (optional) |
| `docs/SNOWFLAKE_SETUP.md` | Snowflake setup (optional) |
| `docs/DEPLOYMENT_GUIDE.md` | Streamlit Community Cloud deployment |
| `docs/PRESENTATION_OUTLINE.md` | Slide-by-slide presentation outline |
| `docs/DEMO_SCRIPT.md` | 3-5 minute demo script |
| `docs/DEPLOYMENT_CHECKLIST.md` | Pre-submission deployment checklist |
| `docs/VALIDATION_CHECKLIST.md` | Final requirement validation checklist |

## Project structure

```
.
├── app.py                          # Page 1: Dashboard (Streamlit entry point)
├── pages/
│   ├── 2_Expense_Analytics.py
│   ├── 3_Budget_Planner.py
│   ├── 4_Financial_Health_Score.py
│   ├── 5_AI_Financial_Intelligence.py   # AI Mode: LLM insight report + chat
│   ├── 6_AI_What_if_Simulator.py        # Python computes, LLM explains
│   ├── 7_FIRE_Planner.py                # FIRE Number = Annual Expense x 25
│   ├── 8_Dataset_Profiling.py
│   └── 9_Project_Methodology.py
├── common/                          # Shared Streamlit layer
│   ├── bootstrap.py                  # sys.path + Streamlit secrets -> os.environ
│   ├── data_access.py                 # @st.cache_resource / @st.cache_data wrappers
│   ├── state.py                       # st.session_state defaults
│   ├── ui.py                          # Theme, KPI cards, sidebar filters
│   ├── ai_client.py                   # get_ai_client() / ask_ai() (Anthropic Claude)
│   ├── ai_context.py                  # Data-centric AI Context Package builder
│   └── fred_data.py                   # FRED macroeconomic indicators
├── backend/                          # Phase 2 backend (config, ETL, DuckDB, Mongo, Snowflake, profiling)
├── docs/                             # Phase 4 deployment & presentation docs
├── .streamlit/
│   ├── config.toml                   # Theme
│   └── secrets.toml.example          # Streamlit Cloud secrets template
├── .gitignore
└── requirements.txt                  # -> backend/requirements.txt (streamlit + plotly + anthropic + requests)
```

## Setup & run

```bash
pip install -r requirements.txt

# Optional: configure MongoDB Atlas / Snowflake / AI / FRED
# (the app is fully functional with none of these set)
cp backend/.env.example backend/.env
# edit backend/.env with real credentials

streamlit run app.py
```

If `backend/.env` is missing or MongoDB/Snowflake are unreachable, the app
automatically falls back to loading `Expenses_clean.csv` via the Phase 2 ETL
pipeline and runs entirely on the mandatory in-memory DuckDB engine
("offline mode" - shown via the data-source badge on every page).

## AI layer (Phase 4)

**Data-centric AI workflow** (hard requirement - enforced in
`common/ai_context.py`):

```
Data -> Metadata -> Statistical Summary -> Context Package -> LLM -> Insight Generation
```

The AI **never** receives raw transaction rows or full DataFrames. Only
aggregated objects are sent: DuckDB results, Snowflake metrics, Financial
Health Score, Budget Status, Profiling Summary, What-if Results, FIRE
Results, and FRED macro indicators.

| Page | What Python does | What the LLM does |
|---|---|---|
| 5. AI Financial Intelligence | Builds the context package from DuckDB/Mongo/Snowflake/profiling/FRED | Writes Spending Insights, Financial Risks, Budget Problems, Savings Opportunities, Recommended Actions + answers chat questions |
| 6. AI What-if Simulator | Computes the 5 named scenarios (Reduce Food Spending, Reduce Shopping Spending, Increase Savings, Increase Investment Amount, Increase Income) | Explains the Python-computed results only - never recomputes |
| 7. FIRE Planner | Computes FIRE Number (Annual Expense x 25), Years to FIRE, FIRE Age, return/withdrawal-rate scenarios | Explains FIRE Readiness, Risks, Recommendations |

With `ANTHROPIC_API_KEY` unset, all three pages run in **Non-AI Mode**:
fully functional, deterministic, and showing exactly the context package
that *would* be sent to the LLM.

FRED indicators (`CPIAUCSL`, `FEDFUNDS`, `UNRATE`) are fetched via
`common/fred_data.py` and included in the context package as macroeconomic
context; if `FRED_API_KEY` is unset, this is simply omitted.

## Streamlit feature compliance

| Feature | Implementation |
|---|---|
| Multi-page | `app.py` + `pages/2-9_*.py` (native Streamlit `pages/` directory) |
| Pandas | DataFrame wrangling throughout `backend/` and `common/` |
| DuckDB | `analytics/duckdb_engine.py` (`DuckDBAnalytics`) - mandatory analytics engine |
| MongoDB Atlas | `backend/repositories/mongo_repository.py` - budget plans, AI reports, FIRE simulations |
| Snowflake | `backend/repositories/snowflake_repository.py` - `MONTHLY_SUMMARY` feeds AI context |
| `@st.cache_data` | `load_transactions_df`, all `query_*` DuckDB wrappers, `get_profile_report`, `get_macro_context`, `build_*_context` (`common/data_access.py`, `common/ai_context.py`, `common/fred_data.py`) |
| `@st.cache_resource` | `get_mongo_repo`, `get_snowflake_repo`, `get_duckdb_engine`, `get_ai_client` (`common/data_access.py`, `common/ai_client.py`) |
| `st.session_state` | filters, `selected_period`, `ai_history`, `ai_insights_report`, `whatif_inputs`/`whatif_results`/`whatif_explanation`, `fire_inputs`/`fire_results`/`fire_explanation` (`common/state.py`) |
| Plotly only | every chart uses `plotly.express` / `plotly.graph_objects` |
| Non-AI / AI mode | pages 1-4, 8-9 are rules-based; pages 5-7 add an optional AI layer with full Non-AI Mode fallback |
| What-if Simulator | Page 6 - 5 named scenarios, Python-computed |
| FIRE Planner | Page 7 - FIRE Number = Annual Expense x 25 |
| Deployment | `docs/DEPLOYMENT_GUIDE.md` - Streamlit Community Cloud, secrets via `st.secrets` |

## Notes

- All analytics aggregation runs through `analytics/duckdb_engine.py`
  (`DuckDBAnalytics`), per the mandatory-DuckDB requirement.
- `common/bootstrap.py` is imported first by every page/module that touches
  the backend - it wires `sys.path` to `backend/` and copies any matching
  Streamlit secrets into `os.environ` so `backend/config/settings.py` works
  identically locally and on Streamlit Community Cloud.
