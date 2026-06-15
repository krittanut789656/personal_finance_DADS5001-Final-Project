# Deployment Checklist

Run through before submitting / presenting.

## Repository

- [ ] `.gitignore` present and excludes `backend/.env`,
      `.streamlit/secrets.toml`, `*.duckdb`, `logs/`, `__pycache__/`
- [ ] No real credentials committed (`backend/.env`, `.streamlit/secrets.toml`
      do not exist in the repo - only the `.example` versions)
- [ ] `requirements.txt` (root) installs cleanly:
      `pip install -r requirements.txt`
- [ ] `backend/requirements.txt` includes `anthropic` and `requests`
      (Phase 4 additions)

## Configuration files

- [ ] `backend/.env.example` documents all env vars: MongoDB, Snowflake,
      DuckDB, Data, Logging, **AI (`ANTHROPIC_API_KEY`, `AI_MODEL`,
      `AI_MAX_TOKENS`)**, **FRED (`FRED_API_KEY`, `FRED_BASE_URL`)**
- [ ] `.streamlit/config.toml` sets theme + `headless = true`
- [ ] `.streamlit/secrets.toml.example` documents the Streamlit Cloud
      secrets format (mirrors `.env.example`)
- [ ] `common/bootstrap.py` copies `st.secrets` -> `os.environ` so secrets
      work without code changes

## Local run (offline / Non-AI Mode)

- [ ] `streamlit run app.py` starts without errors with no `backend/.env`
- [ ] Data-source badge shows "Local CSV (offline)" on every page
- [ ] Pages 1-4, 8-9 render KPIs/tables/charts
- [ ] Pages 5-7 render with "⚪ Non-AI Mode" messages and show their
      context packages / Python-computed results

## Local run (AI Mode)

- [ ] `ANTHROPIC_API_KEY` set in `backend/.env`
- [ ] Page 5 shows "🟢 AI Mode" and generates a 5-section report
- [ ] Page 5 chat answers a follow-up question
- [ ] Page 6 generates a what-if explanation for at least 2 scenarios
- [ ] Page 7 generates a FIRE explanation (3 sections)

## Optional integrations (test independently)

- [ ] MongoDB Atlas: data-source badge shows "MongoDB"; budget plans / AI
      reports / FIRE simulations persist (see `docs/MONGODB_SETUP.md`)
- [ ] Snowflake: Page 5 context package includes
      `"snowflake_metrics": {"available": true, ...}` (see
      `docs/SNOWFLAKE_SETUP.md`)
- [ ] FRED: Page 5/6/7 context packages include `"macro": {"available":
      true, ...}` with CPI/FEDFUNDS/UNRATE

## Streamlit Community Cloud

- [ ] Repo pushed to GitHub (public or accessible to grader)
- [ ] App deployed at share.streamlit.io with main file `app.py`
- [ ] Secrets configured in App settings (only for integrations being
      demoed)
- [ ] Deployed app reproduces the local run checks above
- [ ] App URL recorded for submission

## Documentation

- [ ] `README.md` up to date (Phase 4 AI layer, doc index, project
      structure)
- [ ] `docs/ARCHITECTURE.md` reflects as-built system
- [ ] `docs/PRESENTATION_OUTLINE.md` and `docs/DEMO_SCRIPT.md` ready
- [ ] `docs/VALIDATION_CHECKLIST.md` fully checked off (see that file)

## Submission

- [ ] GitHub repo link
- [ ] Deployed app link
- [ ] Demo video (recorded from `docs/DEMO_SCRIPT.md`)
- [ ] Presentation slides (from `docs/PRESENTATION_OUTLINE.md`)
