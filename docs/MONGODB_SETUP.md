# MongoDB Atlas Setup Guide

The app runs fully without MongoDB (offline mode, DuckDB + local CSV). This
guide is only needed to enable the "online" data source and the
budget-plan / AI-report / FIRE-simulation persistence features.

## 1. Create a free Atlas cluster

1. Go to https://www.mongodb.com/cloud/atlas/register and create a free account.
2. Create a new **Project** (e.g. "AI Personal Finance Platform").
3. Click **Build a Database** -> choose the **M0 Free** shared tier.
4. Pick any cloud provider/region close to you, name the cluster (e.g.
   `personal-finance-cluster`), and click **Create**.

## 2. Create a database user

1. In **Database Access** (left sidebar), click **Add New Database User**.
2. Authentication method: **Password**.
3. Set a username and a strong password (save it - you'll need it for the
   connection string).
4. Built-in role: **Read and write to any database** (or restrict to
   `personal_finance_db` for least-privilege).

## 3. Allow network access

1. In **Network Access**, click **Add IP Address**.
2. For local development, add your current IP, or `0.0.0.0/0` (allow from
   anywhere) if deploying to Streamlit Community Cloud (which uses dynamic
   egress IPs). `0.0.0.0/0` is convenient for this project but is a
   weaker security posture - tighten it if you handle real financial data.

## 4. Get the connection string

1. Go to **Database** -> **Connect** on your cluster.
2. Choose **Drivers** -> **Python** -> version **3.6 or later**.
3. Copy the connection string, which looks like:
   ```
   mongodb+srv://<username>:<password>@<cluster-host>/?retryWrites=true&w=majority
   ```
4. Replace `<username>` and `<password>` with the database user created in
   step 2 (URL-encode any special characters in the password).

## 5. Configure the app

Set the following in `backend/.env` (local) or Streamlit secrets (Cloud -
see `.streamlit/secrets.toml.example`):

```ini
MONGODB_URI=mongodb+srv://<username>:<password>@<cluster-host>/?retryWrites=true&w=majority
MONGODB_DATABASE=personal_finance_db
```

## 6. Initialize collections + indexes

```bash
cd backend
python scripts/init_db.py --mongo-only
```

This creates (implicitly, on first write) and indexes the 5 collections in
`personal_finance_db`:

| Collection | Purpose | Index |
|---|---|---|
| `transactions` | canonical transaction rows | unique on `transaction_id` |
| `monthly_summary` | DuckDB-derived monthly aggregates | unique on `year_month` |
| `budget_plans` | user-defined budgets (Page 3) | - |
| `ai_reports` | cached LLM insight reports (Page 5) | - |
| `fire_simulations` | saved FIRE Planner scenarios (Page 7) | - |

## 7. Load data (optional)

```bash
python scripts/run_etl.py            # full run: DuckDB + MongoDB + Snowflake
python scripts/run_etl.py --no-snowflake   # DuckDB + MongoDB only
```

## 8. Verify

Run the app (`streamlit run app.py`). The sidebar/header **data-source
badge** should show **"🟢 MongoDB"** instead of **"⚪ Local CSV (offline)"**
once `MONGODB_URI` is reachable.

## Troubleshooting

- **`ServerSelectionTimeoutError`**: usually a Network Access (IP allowlist)
  issue - re-check step 3.
- **Auth failed**: re-check the username/password in step 2, and make sure
  special characters in the password are percent-encoded in the URI.
- App still shows offline mode with no error: this is by design - any
  MongoDB connection failure is caught and the app falls back to the local
  CSV + in-memory DuckDB so the app is always demoable without cloud creds.
