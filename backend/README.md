# Backend Layer — AI Personal Finance Intelligence Platform

Phase 2 deliverable: complete backend layer, following the architecture
approved in Phase 1 (`../Architecture_Analysis_AI_Personal_Finance_Platform.md`).

The Phase 3 Streamlit application (`../app.py` + `../pages/`) is built on top
of this backend - see the root `../README.md` for how to run it. The DuckDB
analytics layer additionally exposes filter-aware query variants
(`monthly_summary_filtered`, `category_breakdown_filtered`, etc.) used by the
Streamlit sidebar filters.

## Layers

| Layer | Module | Purpose |
|---|---|---|
| Configuration | `config/settings.py`, `config/category_mapping.json` | Loads all env vars + category→type mapping |
| Logging | `core/logger.py` | Console + rotating file logs for every layer |
| ETL Pipeline | `etl/extract.py`, `etl/transform.py`, `etl/load.py`, `etl/pipeline.py` | CSV → clean canonical schema → DuckDB → Mongo/Snowflake |
| Data Profiling | `profiling/profiler.py` | Schema/quality checks + DuckDB-based distribution stats → JSON report |
| MongoDB Repository | `repositories/mongo_repository.py` | CRUD for all 5 `personal_finance_db` collections |
| Snowflake Repository | `repositories/snowflake_repository.py` | Auto-creates warehouse/db/schema/tables + CRUD |
| DuckDB Analytics (mandatory) | `analytics/duckdb_engine.py` | All analytics SQL (monthly summary, trends, anomalies, etc.) |

## Setup

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # optional
pip install -r requirements.txt
cp .env.example .env
# edit .env with real MongoDB Atlas + Snowflake credentials
```

## Initialize cloud objects

```bash
python scripts/init_db.py                # MongoDB indexes + Snowflake warehouse/db/schema/tables
python scripts/init_db.py --mongo-only
python scripts/init_db.py --snowflake-only
```

## Run the ETL pipeline

```bash
python scripts/run_etl.py                       # full run (Mongo + Snowflake)
python scripts/run_etl.py --no-mongo --no-snowflake   # offline/dev: DuckDB only
```

## Run data profiling

```bash
python scripts/run_profiling.py
```
Writes a timestamped JSON report to `reports/`.

## Canonical transaction schema

| Field | Type | Notes |
|---|---|---|
| transaction_id | str | stable hash, unique key |
| transaction_date | date | YYYY-MM-DD |
| transaction_datetime | datetime | ISO 8601 |
| year, month, year_month | int/str | derived |
| category | str | from dataset |
| type | str | "Income" or "Expense" (see `config/category_mapping.json`) |
| account | str | acct_1 / acct_2 / acct_3 |
| amount | float | always >= 0 |
| currency | str | BYN |
| tags | str | |
| source | str | provenance, e.g. "csv_seed" |
| ingested_at | str | ETL run timestamp (UTC) |

## MongoDB collections (`personal_finance_db`)

- `transactions` — canonical rows (unique index on `transaction_id`)
- `monthly_summary` — DuckDB-derived monthly aggregates (unique index on `year_month`)
- `budget_plans` — user-defined budgets (app feature, empty until used)
- `ai_reports` — cached LLM insight reports (AI mode, empty until used)
- `fire_simulations` — saved FIRE Planner scenarios (empty until used)

## Snowflake objects (`PERSONAL_FINANCE_DB.PUBLIC`)

Auto-created by `SnowflakeRepository.ensure_objects()` from `sql/snowflake_ddl.sql`:
`TRANSACTIONS`, `MONTHLY_SUMMARY`, `BUDGET_PLANS`, `AI_REPORTS`, `FIRE_SIMULATIONS`.

## Notes on the dataset

`data/raw/Expenses_clean.csv` has no explicit Income/Expense column. The ETL
transform step derives `type` via `config/category_mapping.json`
(currently only `"Job"` is mapped to `"Income"`; everything else defaults to
`"Expense"`). Adjust this mapping file as the dataset/requirements evolve —
no code changes needed.
