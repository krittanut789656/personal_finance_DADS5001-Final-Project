"""
Page 8 - Dataset Profiling
============================
Runs (and caches) the Phase 2 data profiling pipeline:
  - Structural / data-quality profile (Pandas, on the RAW dataset)
  - Statistical / distribution profile (DuckDB, on the CLEANED dataset)
"""

from __future__ import annotations

import common.bootstrap  # noqa: F401

import pandas as pd
import plotly.express as px
import streamlit as st

from common.data_access import get_profile_report
from common.ui import configure_page, page_header, render_sidebar_header

configure_page("Dataset Profiling")
render_sidebar_header()

with st.sidebar:
    st.markdown("#### 🔎 Filters")
    st.caption("This page profiles the *entire* raw + cleaned dataset, independent of the period/category filters used elsewhere.")

page_header(
    "Dataset Profiling",
    subtitle="Structural data-quality checks (Pandas, raw data) and statistical distributions (DuckDB, cleaned data).",
    icon="🔍",
)
st.write("")

report = get_profile_report()
structural = report["structural"]
statistical = report["statistical"]

# ----------------------------------------------------------------------
# Top-level summary
# ----------------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Source rows", f"{report['source_rows']:,}")
c2.metric("Clean rows", f"{report['clean_rows']:,}")
c3.metric("Rows dropped in transform", f"{report['rows_dropped_in_transform']:,}")
c4.metric("Duplicate rows (raw)", f"{structural['duplicate_rows']:,}")

st.caption(f"Profile generated at {report['generated_at']} (UTC). Results are cached for this session via `@st.cache_data`.")

st.divider()

# ----------------------------------------------------------------------
# Structural profile (column-level)
# ----------------------------------------------------------------------
st.markdown("#### Structural Profile (raw dataset, per column)")

rows = []
for col, info in structural["columns"].items():
    rows.append(
        {
            "column": col,
            "dtype": info["dtype"],
            "null_count": info["null_count"],
            "null_pct": info["null_pct"],
            "unique_count": info["unique_count"],
            "min": info.get("min"),
            "max": info.get("max"),
            "mean": info.get("mean"),
            "negative_count": info.get("negative_count"),
            "zero_count": info.get("zero_count"),
        }
    )
col_df = pd.DataFrame(rows)
st.dataframe(col_df, use_container_width=True, hide_index=True)

with st.expander("Top values for categorical columns"):
    for col, info in structural["columns"].items():
        if "top_values" in info:
            st.markdown(f"**{col}**")
            tv_df = pd.DataFrame(list(info["top_values"].items()), columns=["value", "count"])
            st.dataframe(tv_df, use_container_width=True, hide_index=True)

st.divider()

# ----------------------------------------------------------------------
# Statistical profile (DuckDB, cleaned dataset)
# ----------------------------------------------------------------------
st.markdown("#### Statistical Profile (cleaned dataset, via DuckDB)")

dr = statistical["date_range"]
st.caption(f"📅 Date range: {dr['min_date']} → {dr['max_date']}  |  📄 {dr['row_count']:,} rows")

c1, c2 = st.columns(2, gap="large")
with c1:
    st.markdown("##### Income vs. Expense Totals")
    type_df = pd.DataFrame(statistical["type_totals"])
    if not type_df.empty:
        fig = px.pie(type_df, names="type", values="total_amount", hole=0.45)
        fig.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(type_df.style.format({"total_amount": "{:,.2f}"}), use_container_width=True, hide_index=True)

with c2:
    st.markdown("##### Amount Statistics")
    amt = statistical["amount_stats"]
    st.dataframe(
        pd.DataFrame([amt]).style.format(
            {"min_amount": "{:,.2f}", "max_amount": "{:,.2f}", "avg_amount": "{:,.2f}", "std_amount": "{:,.2f}", "median_amount": "{:,.2f}"}
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("##### Account Breakdown")
    acct_df = pd.DataFrame(statistical["account_breakdown"])
    st.dataframe(
        acct_df.style.format({"total_expense": "{:,.2f}", "total_income": "{:,.2f}", "transaction_count": "{:,}"}),
        use_container_width=True,
        hide_index=True,
    )

st.markdown("##### Category Breakdown (all categories)")
cat_df = pd.DataFrame(statistical["category_breakdown"])
if not cat_df.empty:
    fig2 = px.bar(
        cat_df.sort_values("total_amount", ascending=False),
        x="category",
        y="total_amount",
        color="type",
        barmode="group",
    )
    fig2.update_layout(height=400, margin=dict(l=10, r=10, t=30, b=10), xaxis_title=None, yaxis_title="Total Amount (BYN)")
    st.plotly_chart(fig2, use_container_width=True)
    st.dataframe(
        cat_df.style.format({"total_amount": "{:,.2f}", "avg_amount": "{:,.2f}", "transaction_count": "{:,}"}),
        use_container_width=True,
        hide_index=True,
    )
