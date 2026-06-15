# Snowflake Setup Guide

The app runs fully without Snowflake (offline mode, DuckDB + local CSV /
MongoDB). This guide enables the Snowflake-backed `MONTHLY_SUMMARY` table,
which feeds `snowflake_metrics_snapshot()` into the AI context package
(Page 5).

## 1. Create a free trial account

1. Go to https://signup.snowflake.com/ and sign up for a free trial
   (30 days / $400 credit).
2. Choose any cloud provider/region. After verifying your email and setting
   a password, note your **account identifier** (shown in the URL, e.g.
   `https://<account_identifier>.snowflakecomputing.com` -> the part before
   `.snowflakecomputing.com`, e.g. `ab12345.us-east-1` or an org-style
   identifier like `myorg-myaccount`).

## 2. Nothing else to create manually

Unlike a typical setup, **this project auto-provisions everything** the
first time it connects. `SnowflakeRepository.ensure_objects()`
(`backend/repositories/snowflake_repository.py`, DDL in
`backend/sql/snowflake_ddl.sql`) creates, if missing:

- Warehouse: `SNOWFLAKE_WAREHOUSE` (default `COMPUTE_WH`)
- Database: `SNOWFLAKE_DATABASE` (default `PERSONAL_FINANCE_DB`)
- Schema: `SNOWFLAKE_SCHEMA` (default `PUBLIC`)
- Tables: `TRANSACTIONS`, `MONTHLY_SUMMARY`, `BUDGET_PLANS`, `AI_REPORTS`,
  `FIRE_SIMULATIONS`

Your Snowflake user just needs a role with `CREATEWAREHOUSE`/`CREATEDATABASE`
privileges - on a fresh trial account, the default `ACCOUNTADMIN` role
(assigned to your user automatically) has these.

## 3. Configure the app

Set the following in `backend/.env` (local) or Streamlit secrets (Cloud -
see `.streamlit/secrets.toml.example`):

```ini
SNOWFLAKE_ACCOUNT=<your_account_identifier>
SNOWFLAKE_USER=<your_username>
SNOWFLAKE_PASSWORD=<your_password>
SNOWFLAKE_ROLE=ACCOUNTADMIN
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
SNOWFLAKE_DATABASE=PERSONAL_FINANCE_DB
SNOWFLAKE_SCHEMA=PUBLIC
```

> The committed `.env.example` ships with a placeholder
> `SNOWFLAKE_ACCOUNT=mj18661` from development - replace it with your own
> account identifier.

## 4. Initialize objects

```bash
cd backend
python scripts/init_db.py --snowflake-only
```

This connects, runs `sql/snowflake_ddl.sql` (idempotent `CREATE ... IF NOT
EXISTS`), and logs success/failure.

## 5. Load data

```bash
python scripts/run_etl.py                       # DuckDB + MongoDB + Snowflake
python scripts/run_etl.py --no-mongo            # DuckDB + Snowflake only
```

This populates `TRANSACTIONS` and `MONTHLY_SUMMARY`. Page 5's
`snowflake_metrics_snapshot()` reads the last 12 rows of `MONTHLY_SUMMARY`.

## 6. Verify

Run the app (`streamlit run app.py`) and open **Page 5 - AI Financial
Intelligence**. Expand **"AI context package"** - if connected, you should
see a `snowflake_metrics` key with `"available": true` and a list of monthly
rows (`YEAR_MONTH`, `TOTAL_INCOME`, `TOTAL_EXPENSE`, `NET`,
`SAVINGS_RATE_PCT`, ...).

## Troubleshooting

- **`SnowflakeConnectionError` / import error**: confirm
  `snowflake-connector-python>=3.6.0` is installed (`pip install -r
  backend/requirements.txt`).
- **Authentication / account identifier errors**: the account identifier
  must NOT include `https://` or `.snowflakecomputing.com` - just the
  identifier portion.
- **Insufficient privileges creating warehouse/database**: use the
  `ACCOUNTADMIN` role (default for trial accounts), or have an admin
  pre-create the warehouse/database/schema and grant your role `USAGE` +
  `CREATE TABLE` on them.
- App still works with `"snowflake_metrics": {"available": false, ...}`:
  this is by design - any Snowflake error is caught and the rest of the
  context package (DuckDB, Financial Health Score, Budget Status, FRED) is
  still sent to the AI.
- Trial credits/warehouse auto-suspend: the default warehouse auto-suspends
  after inactivity and resumes on the next query - first query after a
  pause may take a few extra seconds.
