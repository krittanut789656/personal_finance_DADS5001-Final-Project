# Presentation Slides Outline

Target: 10-15 minutes, group of 3-5 (DADS5001 final project). Suggested
~12-14 slides at roughly 1 minute each.

## Slide 1 - Title

- **AI Personal Finance Intelligence Platform**
- Subtitle: Data-centric AI app for personal finance analytics, budgeting,
  and FIRE planning
- Team members, course (DADS5001), date

## Slide 2 - Issues / Motivation

- People struggle to see the *big picture* of their spending across
  accounts and categories.
- Manual budgeting tools rarely connect "what happened" (historical
  transactions) with "what should I do" (recommendations).
- Long-term goals like financial independence (FIRE) feel abstract without
  a concrete number and timeline.
- Pain point: most personal finance tools are either pure dashboards (no
  guidance) or pure chatbots (no grounding in your real numbers).

## Slide 3 - Objective

- Build a multi-page Streamlit app that:
  1. Analyzes a personal transaction dataset (income/expenses across
     accounts and categories).
  2. Computes a Financial Health Score and Budget Status.
  3. Lets users simulate "what-if" financial decisions.
  4. Plans for FIRE (Financial Independence, Retire Early).
  5. Optionally layers an LLM on top to *explain* and *contextualize* the
     numbers - never to replace the calculations.
- Course requirements satisfied: Streamlit multi-page, Pandas, DuckDB,
  MongoDB Atlas, Snowflake, Plotly, `st.cache_data`/`st.cache_resource`/
  `st.session_state`, Non-AI + AI modes, Streamlit deployment.

## Slide 4 - High-level architecture

- Show the system diagram from `docs/ARCHITECTURE.md` (system overview
  Mermaid diagram).
- Call out the 3 storage layers: DuckDB (mandatory, in-process analytics),
  MongoDB Atlas (operational store: budgets, AI reports, FIRE scenarios),
  Snowflake (warehouse: monthly summary metrics).
- Call out graceful offline fallback: local CSV + in-memory DuckDB if cloud
  services aren't configured.

## Slide 5 - Data-centric AI design (the key constraint)

- Show the "Data -> Metadata -> Statistical Summary -> Context Package ->
  LLM -> Insight" diagram from `docs/ARCHITECTURE.md`.
- **The LLM never sees raw transactions** - only pre-aggregated JSON
  (DuckDB results, Financial Health Score, Budget Status, Profiling
  Summary, Snowflake metrics, What-if/FIRE results, FRED macro indicators).
- Why this matters: privacy, smaller/cheaper prompts, and reproducibility -
  Python's numbers are the source of truth; the LLM only narrates them.

## Slide 6 - Solution: Non-AI Mode (pages 1-4, 8-9)

- Page 1 Dashboard: KPIs (income, expenses, net, savings rate), trend
  charts.
- Page 2 Expense Analytics: category breakdowns, drill-down by month.
- Page 3 Budget Planner: plan vs. actual, over-budget detection.
- Page 4 Financial Health Score: composite score + sub-scores + band.
- Page 8 Dataset Profiling: schema/quality report (nulls, ranges,
  distributions).
- All built on `analytics/duckdb_engine.py` + Plotly; fully usable with
  zero external services.

## Slide 7 - Solution: AI Financial Intelligence (Page 5)

- Shows the AI context package (expandable JSON) - "this is exactly what
  the AI sees."
- One click -> LLM-generated report with 5 fixed sections: Spending
  Insights, Financial Risks, Budget Problems, Savings Opportunities,
  Recommended Actions.
- Follow-up chat grounded in the same context package.
- Non-AI Mode: same page, same context package, just no LLM call - useful
  for demoing without an API key.

## Slide 8 - Solution: AI What-if Simulator (Page 6)

- 5 named scenarios: Reduce Food Spending, Reduce Shopping Spending,
  Increase Savings, Increase Investment Amount, Increase Income.
- **Python computes** the projected impact (Plotly chart: baseline vs.
  adjusted cumulative net, plus investment growth curve for the investment
  scenario).
- **LLM explains** what the result means in plain language - explicitly
  instructed not to recompute numbers.

## Slide 9 - Solution: FIRE Planner (Page 7)

- Formula: **FIRE Number = Annual Expense x 25** (4% safe withdrawal rate).
- Python computes: Years to FIRE, FIRE Age, portfolio projection chart,
  and scenario tables (alternate return rates / withdrawal rates).
- LLM explains: FIRE Readiness, Risks, Recommendations - using FRED
  macro context (inflation, interest rates) for situational color.
- Scenarios can be saved to MongoDB.

## Slide 10 - Macro context: FRED integration

- `common/fred_data.py` pulls CPI (`CPIAUCSL`, with derived YoY inflation),
  Fed Funds Rate (`FEDFUNDS`), and unemployment (`UNRATE`).
- Cached for 6 hours; gracefully omitted if no API key.
- Used to ground AI explanations in the current macro environment (e.g.
  "inflation is eroding your fixed FIRE number over time").

## Slide 11 - Engineering practices

- `@st.cache_resource`: DB connections + AI client (created once).
- `@st.cache_data`: all query/profiling/context-building functions
  (recomputed only when filters/inputs change).
- `st.session_state`: filters, chat history, what-if/FIRE inputs &
  results persist across reruns.
- Offline-first: every external dependency (Mongo, Snowflake, Anthropic,
  FRED) fails gracefully to a "Non-AI / offline" indicator rather than
  crashing the app.

## Slide 12 - Live demo

- Switch to live app / recorded demo (see `docs/DEMO_SCRIPT.md`).

## Slide 13 - Deployment & repo

- Deployed on Streamlit Community Cloud (see `docs/DEPLOYMENT_GUIDE.md`).
- GitHub repo structure, `.gitignore`, secrets template
  (`.streamlit/secrets.toml.example`).
- Setup guides for MongoDB Atlas and Snowflake included in `docs/`.

## Slide 14 - Wrap-up / Q&A

- Recap: requirement checklist (`docs/VALIDATION_CHECKLIST.md`) - all
  items satisfied.
- Future work: more scenarios, multi-currency, anomaly detection alerts,
  scheduled AI reports.
- Thank you / Q&A.
