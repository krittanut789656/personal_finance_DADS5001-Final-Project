"""
Data Profiling Pipeline
==========================
Runs structural and statistical checks on the raw and/or cleaned
transaction dataset and produces a JSON profile report under `reports/`.

Two layers of checks:
  1. Structural / data-quality checks (nulls, dtypes, duplicates,
     value ranges) -- plain Pandas, run on the RAW dataframe so issues
     are caught *before* the ETL transform step "fixes" them.
  2. Statistical / distribution profiling (category breakdown, amount
     stats, date coverage) -- delegated to the DuckDB Analytics Layer
     (mandatory), run on the CLEANED dataframe.

Output: a single JSON report combining both layers, plus a summary
logged to the console/log file.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from analytics.duckdb_engine import DuckDBAnalytics
from config.settings import BASE_DIR
from core.logger import get_logger
from etl.extract import extract_transactions
from etl.transform import transform_transactions

logger = get_logger(__name__)

REPORTS_DIR = BASE_DIR / "reports"


def _structural_profile(raw_df: pd.DataFrame) -> dict[str, Any]:
    """Schema-level checks on the RAW (pre-transform) dataframe."""
    profile: dict[str, Any] = {
        "row_count": int(len(raw_df)),
        "column_count": int(len(raw_df.columns)),
        "columns": {},
        "duplicate_rows": int(raw_df.duplicated().sum()),
    }

    for col in raw_df.columns:
        series = raw_df[col]
        col_profile: dict[str, Any] = {
            "dtype": str(series.dtype),
            "null_count": int(series.isna().sum()),
            "null_pct": round(100 * series.isna().mean(), 2),
            "unique_count": int(series.nunique()),
        }
        if pd.api.types.is_numeric_dtype(series):
            col_profile.update(
                {
                    "min": float(series.min()) if not series.empty else None,
                    "max": float(series.max()) if not series.empty else None,
                    "mean": float(series.mean()) if not series.empty else None,
                    "negative_count": int((series < 0).sum()),
                    "zero_count": int((series == 0).sum()),
                }
            )
        else:
            top_values = series.value_counts().head(10).to_dict()
            col_profile["top_values"] = {str(k): int(v) for k, v in top_values.items()}

        profile["columns"][col] = col_profile

    return profile


def _statistical_profile(duck: DuckDBAnalytics) -> dict[str, Any]:
    """Distribution / coverage checks on the CLEANED dataframe, via DuckDB SQL."""
    date_range = duck.date_range()

    category_breakdown = duck.category_breakdown()
    type_totals = duck.run_query(
        "SELECT type, CAST(SUM(amount) AS DOUBLE) AS total_amount, COUNT(*) AS n "
        "FROM transactions GROUP BY type"
    )
    account_breakdown = duck.account_breakdown()

    amount_stats = duck.run_query(
        "SELECT "
        "CAST(MIN(amount) AS DOUBLE) AS min_amount, "
        "CAST(MAX(amount) AS DOUBLE) AS max_amount, "
        "CAST(AVG(amount) AS DOUBLE) AS avg_amount, "
        "CAST(STDDEV_SAMP(amount) AS DOUBLE) AS std_amount, "
        "CAST(MEDIAN(amount) AS DOUBLE) AS median_amount "
        "FROM transactions"
    ).iloc[0].to_dict()

    return {
        "date_range": date_range,
        "type_totals": type_totals.to_dict(orient="records"),
        "category_breakdown": category_breakdown.to_dict(orient="records"),
        "account_breakdown": account_breakdown.to_dict(orient="records"),
        "amount_stats": amount_stats,
    }


def run_profiling(csv_path: str | None = None, save_report: bool = True) -> dict[str, Any]:
    """
    Run the full profiling pipeline and return (and optionally persist) a
    JSON-serializable report.
    """
    logger.info("=== Data profiling starting ===")

    raw_df = extract_transactions(csv_path)
    clean_df = transform_transactions(raw_df)

    structural = _structural_profile(raw_df)

    with DuckDBAnalytics(db_path=":memory:") as duck:
        duck.load_transactions(clean_df, mode="replace")
        statistical = _statistical_profile(duck)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_rows": int(len(raw_df)),
        "clean_rows": int(len(clean_df)),
        "rows_dropped_in_transform": int(len(raw_df) - len(clean_df)),
        "structural": structural,
        "statistical": statistical,
    }

    logger.info(
        "Profiling complete: %d source rows -> %d clean rows, %d duplicate rows, date range %s to %s",
        report["source_rows"],
        report["clean_rows"],
        structural["duplicate_rows"],
        statistical["date_range"]["min_date"],
        statistical["date_range"]["max_date"],
    )

    if save_report:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        out_path = REPORTS_DIR / f"profile_report_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)
        logger.info("Profile report written to %s", out_path)

    return report
