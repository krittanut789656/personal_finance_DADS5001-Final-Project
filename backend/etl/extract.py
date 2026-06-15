"""
ETL Pipeline - Extract Step
=============================
Reads the raw "Financial Transactions" CSV dataset into a Pandas DataFrame
and performs minimal structural validation (required columns present).

No business-logic cleaning happens here -- that belongs to transform.py.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from config.settings import settings
from core.logger import get_logger

logger = get_logger(__name__)

REQUIRED_COLUMNS = ["date_time", "category", "account", "amount", "currency", "tags"]


class ExtractError(RuntimeError):
    """Raised when the raw dataset cannot be read or is structurally invalid."""


def extract_transactions(path: str | Path | None = None) -> pd.DataFrame:
    """
    Read the raw transactions CSV into a DataFrame.

    Parameters
    ----------
    path : str | Path | None
        Optional override for the CSV path. Defaults to
        ``settings.data.resolved_raw_path()``.

    Returns
    -------
    pd.DataFrame
        Raw (unmodified) transaction rows.
    """
    csv_path = Path(path) if path is not None else settings.data.resolved_raw_path()

    if not csv_path.exists():
        raise ExtractError(f"Raw data file not found: {csv_path}")

    logger.info("Extracting raw transactions from %s", csv_path)
    df = pd.read_csv(csv_path)

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ExtractError(f"Dataset is missing required columns: {missing}")

    logger.info("Extracted %d raw rows, %d columns", len(df), len(df.columns))
    return df
