# Architecture Diagram (As-Built, Phase 4)

This reflects the implemented system (Phases 1-4), superseding the Phase 1
design diagram in `Architecture_Analysis_AI_Personal_Finance_Platform.md`.

## System overview

```mermaid
flowchart TB
    subgraph USER["User (Browser)"]
        BROWSER[Streamlit UI]
    end

    subgraph APP["Streamlit Multi-Page App"]
        P1[1. Dashboard]
        P2[2. Expense Analytics]
        P3[3. Budget Planner]
        P4[4. Financial Health Score]
        P5[5. AI Financial Intelligence]
        P6[6. AI What-if Simulator]
        P7[7. FIRE Planner]
        P8[8. Dataset Profiling]
        P9[9. Project Methodology]
        SS[(st.session_state\nfilters, ai_history,\nwhatif_inputs, fire_inputs)]
    end

    subgraph COMMON["common/ shared layer"]
        BOOT[bootstrap.py\nsys.path + secrets->env]
        DA[data_access.py\ncache_data / cache_resource]
        UI[ui.py\ntheme, filters, KPIs]
        AICTX[ai_context.py\nContext Package Builder]
        AICLIENT[ai_client.py\nget_ai_client / ask_ai]
        FRED[fred_data.py\nget_macro_context]
    end

    subgraph BACKEND["backend/ (Phase 2)"]
        ETL[ETL pipeline\nextract/transform/load]
        DDB[(DuckDB\nanalytics engine\nmandatory)]
        PROFILE[profiling/profiler.py]
        MONGOREPO[MongoRepository]
        SNOWREPO[SnowflakeRepository]
        CFG[config/settings.py\nenv-based config]
    end

    subgraph CLOUD["External Cloud Storage"]
        CSV[Expenses_clean.csv]
        MONGO[(MongoDB Atlas)]
        SNOW[(Snowflake)]
    end

    subgraph AILAYER["AI Layer (AI Mode only)"]
        CLAUDE[Anthropic Claude\nclaude-sonnet-4-6]
        FREDAPI[FRED API\nCPIAUCSL, FEDFUNDS, UNRATE]
    end

    BROWSER --> P1 & P2 & P3 & P4 & P5 & P6 & P7 & P8 & P9
    P1 & P2 & P3 & P4 & P5 & P6 & P7 & P8 & P9 --> SS
    P1 & P2 & P3 & P4 & P5 & P6 & P7 & P8 & P9 --> UI
    P1 & P2 & P3 & P4 & P5 & P6 & P7 & P8 & P9 --> DA
    P5 & P6 & P7 --> AICTX
    P5 & P6 & P7 --> AICLIENT

    DA --> BOOT
    AICTX --> BOOT
    AICLIENT --> BOOT
    FRED --> BOOT

    DA --> ETL
    DA --> DDB
    DA --> PROFILE
    DA --> MONGOREPO
    DA --> SNOWREPO
    BOOT -.injects secrets.-> CFG

    ETL --> CSV
    ETL --> DDB
    ETL --> MONGOREPO
    ETL --> SNOWREPO
    MONGOREPO --> MONGO
    SNOWREPO --> SNOW

    AICTX -- "aggregates only\n(no raw rows)" --> AICLIENT
    AICLIENT --> CLAUDE
    FRED --> FREDAPI
    AICTX --> FRED
```

## Data-centric AI workflow (Phase 4 - hard constraint)

**The AI never receives raw transaction datasets.** Every value sent to the
LLM passes through `common/ai_context.py`, which only assembles already
aggregated/summary objects.

```mermaid
flowchart LR
    DATA[Raw Data\nExpenses_clean.csv] --> META[Metadata\nETL canonical schema]
    META --> STAT[Statistical Summary\nDuckDB aggregates,\nFinancial Health Score,\nBudget Status,\nProfiling Summary,\nSnowflake metrics,\nFRED indicators]
    STAT --> CTX[Context Package\nJSON dict, common/ai_context.py]
    CTX --> LLM[LLM\nAnthropic Claude]
    LLM --> INSIGHT[Insight Generation\nSpending Insights, Risks,\nBudget Problems, Savings\nOpportunities, Recommended Actions]
```

Allowed AI context (per page):

| Page | Context builder | Contents |
|---|---|---|
| 5. AI Financial Intelligence | `build_financial_intelligence_context()` | DuckDB results, Financial Health Score, Budget Status, Profiling Summary, Snowflake metrics, FRED macro |
| 6. AI What-if Simulator | `build_whatif_context()` | Scenario name + params, Python-computed What-if Results, FRED macro |
| 7. FIRE Planner | `build_fire_context()` | FIRE inputs, Python-computed FIRE Results, FRED macro |

In every case: **Python performs the calculations. The LLM only explains
the results** (Pages 6-7 system prompts explicitly forbid recomputation).

## Non-AI Mode vs AI Mode

| | Non-AI Mode (default / offline) | AI Mode |
|---|---|---|
| Trigger | `ANTHROPIC_API_KEY` not set -> `get_ai_client()` returns `None` | `ANTHROPIC_API_KEY` set -> real `anthropic.Anthropic` client |
| Pages 1-4, 8-9 | Fully functional (rules-based KPIs, charts, profiling) | Identical - no AI dependency |
| Page 5 | Shows the context package (`st.json`) that *would* be sent | Generates the 5-section Financial Intelligence report + chat |
| Page 6 | Shows Python-computed scenario projection | Adds an LLM explanation of the projection |
| Page 7 | Shows Python-computed FIRE number / age / scenarios | Adds an LLM FIRE Readiness/Risks/Recommendations explanation |
| FRED macro | `get_macro_context()` returns `{"available": False}` if `FRED_API_KEY` unset | Macro context included in the package above |

## Caching & state map

| Mechanism | Used for |
|---|---|
| `@st.cache_resource` | `get_duckdb_engine`, `get_mongo_repo`, `get_snowflake_repo`, `get_ai_client` |
| `@st.cache_data` | `load_transactions_df`, all `query_*` DuckDB wrappers, `get_profile_report`, `get_macro_context`, `build_*_context`, `snowflake_metrics_snapshot` |
| `st.session_state` | filters, `selected_period`, `ai_history`, `ai_insights_report`, `whatif_inputs`/`whatif_results`/`whatif_explanation`, `fire_inputs`/`fire_results`/`fire_explanation` |
