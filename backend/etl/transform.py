"""
ETL Pipeline - Transform Step
================================
Cleans and standardizes raw transaction rows into the canonical schema
shared by MongoDB, Snowflake, and the DuckDB analytics layer.

Canonical "transactions" schema
--------------------------------
transaction_id      str   - stable hash, unique per row
transaction_date    date  - YYYY-MM-DD (date portion of date_time)
transaction_datetime str  - ISO 8601 timestamp (original date_time)
year                int
month               int
year_month          str   - "YYYY-MM"
category            str
type                str   - "Income" | "Expense" (derived via category_mapping)
account             str
amount              float - always >= 0 (absolute magnitude)
currency            str
tags                str
source              str   - provenance tag, e.g. "csv_seed"
ingested_at         str   - ISO 8601 UTC timestamp of ETL run
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import pandas as pd

from config.settings import settings
from core.logger import get_logger

logger = get_logger(__name__)

CANONICAL_COLUMNS = [
    "transaction_id",
    "transaction_date",
    "transaction_datetime",
    "year",
    "month",
    "year_month",
    "category",
    "type",
    "account",
    "amount",
    "currency",
    "tags",
    "source",
    "ingested_at",
]


class TransformError(RuntimeError):
    """Raised when the raw dataframe cannot be transformed into the canonical schema."""


def _classify_type(category: str) -> str:
    """Map a raw category string to 'Income' or 'Expense' using config/category_mapping.json."""
    mapping = settings.category_mapping.get("mapping", {})
    default_type = settings.category_mapping.get("default_type", "Expense")
    return mapping.get(category, default_type)


def _make_transaction_id(row: pd.Series, idx: int) -> str:
    """Deterministic hash so re-running the ETL on the same file is idempotent."""
    raw = f"{row['date_time']}|{row['category']}|{row['account']}|{row['amount']}|{row['tags']}|{idx}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def transform_transactions(df: pd.DataFrame, source: str = "csv_seed") -> pd.DataFrame:
    """
    Transform raw extracted rows into the canonical transaction schema.

    Parameters
    ----------
    df : pd.DataFrame
        Raw dataframe as returned by ``etl.extract.extract_transactions``.
    source : str
        Provenance label stored on each row (e.g. "csv_seed", "manual_entry").

    Returns
    -------
    pd.DataFrame
        Cleaned dataframe with columns == CANONICAL_COLUMNS.
    """
    if df.empty:
        raise TransformError("Cannot transform an empty dataframe.")

    work = df.copy()

    # --- Parse datetime -------------------------------------------------
    work["transaction_datetime"] = pd.to_datetime(work["date_time"], errors="coerce")
    n_bad_dates = work["transaction_datetime"].isna().sum()
    if n_bad_dates:
        logger.warning("Dropping %d row(s) with unparseable date_time", n_bad_dates)
        work = work.dropna(subset=["transaction_datetime"])

    # --- Clean amount -----------------------------------------------------
    work["amount"] = pd.to_numeric(work["amount"], errors="coerce")
    n_bad_amount = work["amount"].isna().sum()
    if n_bad_amount:
        logger.warning("Dropping %d row(s) with non-numeric amount", n_bad_amount)
        work = work.dropna(subset=["amount"])
    work["amount"] = work["amount"].abs()

    # --- Clean text fields --------------------------------------------------
    for col in ["category", "account", "currency", "tags"]:
        work[col] = work[col].astype(str).str.strip()

    # --- Derived date parts -------------------------------------------------
    work["transaction_date"] = work["transaction_datetime"].dt.date.astype(str)
    work["year"] = work["transaction_datetime"].dt.year.astype(int)
    work["month"] = work["transaction_datetime"].dt.month.astype(int)
    work["year_month"] = work["transaction_datetime"].dt.strftime("%Y-%m")

    # --- Type classification -------------------------------------------------
    work["type"] = work["category"].apply(_classify_type)

    # --- Provenance -----------------------------------------------------------
    ingested_at = datetime.now(timezone.utc).isoformat()
    work["source"] = source
    work["ingested_at"] = ingested_at

    # --- Stable transaction_id -------------------------------------------------
    work = work.reset_index(drop=True)
    work["transaction_id"] = [
        _make_transaction_id(row, idx) for idx, row in work.iterrows()
    ]

    # --- ISO string for datetime (JSON/Mongo/Snowflake friendly) -----------------
    work["transaction_datetime"] = work["transaction_datetime"].dt.strftime("%Y-%m-%dT%H:%M:%S")

    # --- Drop duplicates by transaction_id ------------------------------------
    before = len(work)
    work = work.drop_duplicates(subset=["transaction_id"])
    if len(work) != before:
        logger.warning("Dropped %d duplicate row(s) by transaction_id", before - len(work))

    result = work[CANONICAL_COLUMNS].reset_index(drop=True)
    logger.info(
        "Transformed %d rows -> %d clean rows (%d Income / %d Expense)",
        len(df),
        len(result),
        (result["type"] == "Income").sum(),
        (result["type"] == "Expense").sum(),
    )
    return result
