# Deployment Guide (Streamlit Community Cloud)

The app is designed to deploy with **zero required configuration** - every
external dependency (MongoDB, Snowflake, Anthropic, FRED) is optional and
degrades gracefully. This guide covers a minimal "offline demo" deploy and
the optional steps to enable each integration.

## 1. Push to GitHub

```bash
git init
git add .
git commit -m "AI Personal Finance Intelligence Platform - Phase 1-4"
git branch -M main
git remote add origin <your-repo-url>
git push -u origin main
```

`.gitignore` already excludes `backend/.env`, `.streamlit/secrets.toml`,
DuckDB files, logs, and `__pycache__`.

## 2. Create the Streamlit Community Cloud app

1. Go to https://share.streamlit.io/ and sign in with GitHub.
2. Click **Create app** -> **Yup, I have an app** (or "From existing repo").
3. Repository: select your pushed repo.
4. Branch: `main`.
5. Main file path: `app.py`.
6. Click **Deploy**.

The first deploy installs everything from the root `requirements.txt`
(which points at `backend/requirements.txt`).

## 3. (Optional) Configure secrets

With no secrets configured, the app runs in:
- Offline data mode (local CSV + in-memory DuckDB) - data-source badge
  shows "⚪ Local CSV (offline)"
- **Non-AI Mode** on Pages 5-7 (context packages shown, no LLM calls)
- FRED macro context unavailable (`"available": false`)

To enable any integration, go to **App settings -> Secrets** and paste keys
from `.streamlit/secrets.toml.example` (filled with real values). Only set
the sections you need:

| To enable... | Set these secrets | Setup guide |
|---|---|---|
| MongoDB Atlas data source + persistence | `MONGODB_URI`, `MONGODB_DATABASE` | `docs/MONGODB_SETUP.md` |
| Snowflake metrics in AI context | `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`, `SNOWFLAKE_ROLE`, `SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_DATABASE`, `SNOWFLAKE_SCHEMA` | `docs/SNOWFLAKE_SETUP.md` |
| AI Mode (LLM insights, what-if/FIRE explanations) | `ANTHROPIC_API_KEY`, `AI_MODEL`, `AI_MAX_TOKENS` | Get a key at https://console.anthropic.com/ |
| FRED macro context (CPI, Fed funds rate, unemployment) | `FRED_API_KEY`, `FRED_BASE_URL` | Free key: https://fred.stlouisfed.org/docs/api/api_key.html |

After saving secrets, the app automatically reboots. `common/bootstrap.py`
copies `st.secrets` into `os.environ` on startup, so
`backend/config/settings.py` picks them up exactly as it would from
`backend/.env` locally - no code changes needed.

## 4. Verify the deployment

Open the deployed URL and check:

1. **Page 1 (Dashboard)** loads with KPIs and charts -> Pandas/DuckDB/Plotly
   working.
2. **Data-source badge** (top of every page) shows the expected source
   (Local CSV, MongoDB, etc.) based on which secrets you configured.
3. **Page 5 (AI Financial Intelligence)**:
   - Without `ANTHROPIC_API_KEY`: shows "⚪ Non-AI Mode" + the JSON context
     package.
   - With `ANTHROPIC_API_KEY`: shows "🟢 AI Mode"; click **"Generate
     Financial Intelligence Report"** to confirm the 5-section report
     renders.
4. **Page 6 (AI What-if Simulator)**: select a scenario, confirm the Plotly
   chart and metrics update; if AI Mode, generate the explanation.
5. **Page 7 (FIRE Planner)**: confirm FIRE Number = Annual Expense x 25 and
   the projection chart render; if AI Mode, generate the explanation.
6. **Page 8 (Dataset Profiling)**: confirm the profiling report renders.

## 5. Running locally (for comparison)

```bash
pip install -r requirements.txt
cp backend/.env.example backend/.env
# edit backend/.env with any credentials you want to use (all optional)
streamlit run app.py
```

## Notes on free-tier limits

- **MongoDB Atlas M0**: 512 MB storage - plenty for this dataset.
- **Snowflake trial**: 30-day / $400 credit; default `COMPUTE_WH`
  auto-suspends when idle.
- **Anthropic API**: usage-based billing; `AI_MAX_TOKENS=1024` (default)
  keeps individual calls small. Each "Generate ..." button click is one API
  call.
- **FRED API**: free, no rate-limit concerns for this app's usage
  (`get_macro_context()` is cached for 6 hours via `@st.cache_data(ttl=...)`).

## Rollback / disabling an integration

Each integration can be disabled independently by removing/blanking its
secret(s) and rebooting the app - the corresponding code path already
handles `None`/unavailable cases (see `docs/ARCHITECTURE.md`, "Non-AI Mode
vs AI Mode").
