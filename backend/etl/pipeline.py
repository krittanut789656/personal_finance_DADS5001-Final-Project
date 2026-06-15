"""
ETL Pipeline - Orchestration
===============================
End-to-end pipeline:

    extract (CSV) -> transform (clean/derive) -> DuckDB (canonical analytics
    store + monthly_summary derivation) -> load (MongoDB Atlas, Snowflake)

DuckDB is mandatory and sits in the middle of the pipeline: the cleaned
transaction set is always persisted into DuckDB first, and the
`monthly_summary` table that gets pushed to Mongo/Snowflake is *derived from
DuckDB SQL*, not recomputed ad-hoc in Pandas.

Mongo and Snowflake loads are optional and individually toggleable so this
pipeline can run end-to-end offline (e.g. CI, local dev without cloud
credentials).
"""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

import pandas as pd

from analytics.duckdb_engine import DuckDBAnalytics
from core.logger import get_logger
from etl.extract import extract_transactions
from etl.load import (
    load_monthly_summary_to_mongo,
    load_monthly_summary_to_snowflake,
    load_transactions_to_mongo,
    load_transactions_to_snowflake,
)
from etl.transform import transform_transactions

logger = get_logger(__name__)


class PipelineResult(TypedDict):
    rows_extracted: int
    rows_loaded: int
    months_summarized: int
    mongo_transactions: int | None
    mongo_monthly_summary: int | None
    snowflake_transactions: int | None
    snowflake_monthly_summary: int | None
    errors: list[str]


def run_etl(
    csv_path: str | Path | None = None,
    load_mongo: bool = True,
    load_snowflake: bool = True,
    duckdb_path: str | None = None,
) -> PipelineResult:
    """
    Run the full ETL pipeline.

    Parameters
    ----------
    csv_path : optional override for the raw dataset path.
    load_mongo : if False, skip writing to MongoDB Atlas.
    load_snowflake : if False, skip writing to Snowflake.
    duckdb_path : optional override for the DuckDB database file/connection.

    Returns
    -------
    PipelineResult
        Summary of row counts written to each target and any non-fatal errors.
    """
    errors: list[str] = []

    logger.info("=== ETL pipeline starting ===")

    # 1. Extract -----------------------------------------------------------
    raw_df = extract_transactions(csv_path)

    # 2. Transform -----------------------------------------------------------
    clean_df = transform_transactions(raw_df)

    # 3. DuckDB: persist canonical transactions + derive monthly_summary -------
    with DuckDBAnalytics(db_path=duckdb_path) as duck:
        duck.load_transactions(clean_df, mode="replace")
        monthly_df = duck.monthly_summary()
    logger.info(
        "DuckDB: persisted %d transactions, derived %d monthly summary rows",
        len(clean_df),
        len(monthly_df),
    )

    result: PipelineResult = {
        "rows_extracted": len(raw_df),
        "rows_loaded": len(clean_df),
        "months_summarized": len(monthly_df),
        "mongo_transactions": None,
        "mongo_monthly_summary": None,
        "snowflake_transactions": None,
        "snowflake_monthly_summary": None,
        "errors": errors,
    }

    # 4. Load: MongoDB ---------------------------------------------------------
    if load_mongo:
        try:
            result["mongo_transactions"] = load_transactions_to_mongo(clean_df)
            result["mongo_monthly_summary"] = load_monthly_summary_to_mongo(monthly_df)
        except Exception as exc:  # noqa: BLE001 - surface but don't crash pipeline
            msg = f"MongoDB load failed: {exc}"
            logger.error(msg)
            errors.append(msg)
    else:
        logger.info("Skipping MongoDB load (load_mongo=False)")

    # 5. Load: Snowflake ---------------------------------------------------------
    if load_snowflake:
        try:
            result["snowflake_transactions"] = load_transactions_to_snowflake(clean_df)
            result["snowflake_monthly_summary"] = load_monthly_summary_to_snowflake(monthly_df)
        except Exception as exc:  # noqa: BLE001
            msg = f"Snowflake load failed: {exc}"
            logger.error(msg)
            errors.append(msg)
    else:
        logger.info("Skipping Snowflake load (load_snowflake=False)")

    logger.info("=== ETL pipeline finished: %s ===", {k: v for k, v in result.items() if k != "errors"})
    if errors:
        logger.warning("Pipeline completed with %d error(s): %s", len(errors), errors)

    return result
