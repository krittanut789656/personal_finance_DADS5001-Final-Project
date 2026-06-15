# 3-5 Minute Demo Script

Assumes the app is running (locally or on Streamlit Community Cloud) with
the local CSV dataset loaded. AI Mode steps are marked **[AI]** - skip them
(or show the Non-AI Mode message) if no `ANTHROPIC_API_KEY` is configured.

## 0:00 - 0:30 | Dashboard (Page 1)

- Open the app -> Page 1 (Dashboard).
- Point out the **data-source badge** (Local CSV / MongoDB / Snowflake).
- Highlight the KPI row (total income, expenses, net, savings rate) and the
  monthly trend chart.
- *Say:* "This is our Non-AI baseline - fully functional with Pandas,
  DuckDB, and Plotly, no AI required."

## 0:30 - 1:00 | Filters + Expense Analytics (Page 2)

- Use the sidebar filters (period slider, accounts, categories) - show the
  page reacting live.
- Switch to Page 2, show the category breakdown chart.
- *Say:* "Filters are shared across every page via `st.session_state`, and
  every query goes through our DuckDB analytics engine."

## 1:00 - 1:30 | Budget Planner + Financial Health Score (Pages 3-4)

- Page 3: show plan-vs-actual table, point out an over-budget category if
  present.
- Page 4: show the Financial Health Score composite + sub-scores.
- *Say:* "These scores and budget statuses are exactly the kind of
  aggregated numbers we'll hand to the AI next - never the raw rows."

## 1:30 - 2:30 | AI Financial Intelligence (Page 5) **[AI]**

- Open Page 5. Expand **"AI context package"** - scroll briefly to show
  it's JSON aggregates (DuckDB results, health score, budget status,
  profiling summary, Snowflake metrics if connected, FRED macro).
- *Say:* "This is the entire data-centric AI workflow: Data -> Metadata ->
  Statistical Summary -> Context Package -> LLM. No transaction-level data
  ever leaves this app."
- Click **"Generate Financial Intelligence Report"** - wait for the 5
  sections (Spending Insights, Financial Risks, Budget Problems, Savings
  Opportunities, Recommended Actions).
- (Optional, if time) Ask one follow-up question in the chat box.
- **If Non-AI Mode**: click the same button, show the context package /
  Non-AI Mode message instead, and say "the app is fully usable without an
  API key - this is exactly what would be sent."

## 2:30 - 3:30 | AI What-if Simulator (Page 6)

- Select **"Reduce Food Spending"**, move the slider - show the Plotly
  chart and metrics update instantly (Python-computed).
- Switch to **"Increase Investment Amount"** - show the investment growth
  curve.
- *Say:* "All of this math is deterministic Python - reproducible and
  fast."
- **[AI]** Click **"Generate AI explanation"** - show the plain-language
  explanation appear, and note it references the FRED macro context.

## 3:30 - 4:30 | FIRE Planner (Page 7)

- Adjust income/expense/return inputs if needed.
- Point out: **FIRE Number = Annual Expense x 25** metric, FIRE Age, Years
  to FIRE, and the portfolio projection chart with the FIRE-number
  horizontal line.
- Scroll to Scenario Analysis tables (return-rate and withdrawal-rate
  variants).
- **[AI]** Click **"Generate AI explanation"** - show FIRE Readiness,
  Risks, Recommendations.
- (Optional) Click **"Save FIRE scenario"** to show MongoDB persistence (if
  connected).

## 4:30 - 5:00 | Wrap-up

- Quick flash of Page 8 (Dataset Profiling) and Page 9 (Project
  Methodology) - "full data quality report and methodology docs are also
  built in."
- *Say:* "Everything you saw runs identically with or without MongoDB,
  Snowflake, the Anthropic API, or FRED - the app degrades gracefully,
  which made it easy to develop and demo offline, and easy to deploy."
- End on the architecture diagram (`docs/ARCHITECTURE.md`) as a recap
  slide if presenting live.

## Tips for recording

- Pre-warm caches by loading each page once before recording (avoids
  visible spinner delays from `@st.cache_data`/`@st.cache_resource` cold
  starts).
- If demoing AI Mode, generate at least one report/explanation per AI page
  *before* recording so the cached `st.session_state` result is ready to
  show instantly, then click "Clear"/regenerate live if you want to show
  the spinner.
- Keep the sidebar filters at a period with non-trivial data (avoid empty
  "No transactions match the current filters" states).
