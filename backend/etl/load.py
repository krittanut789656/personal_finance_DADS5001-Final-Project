"""
ETL Pipeline - Load Step
==========================
Loads cleaned transaction rows (and derived monthly summaries) into the two
external data stores:

  - MongoDB Atlas  -> operational store (repositories.mongo_repository)
  - Snowflake      -> analytical warehouse (repositories.snowflake_repository)

Both targets are optional and independently toggleable so the ETL pipeline
can run in offline/dev mode without cloud credentials.
"""

from __future__ import annotations

import pandas as pd

from core.logger import get_logger

logger = get_logger(__name__)


def load_transactions_to_mongo(df: pd.DataFrame) -> int:
    """Upsert transaction rows into MongoDB's `transactions` collection."""
    from repositories.mongo_repository import MongoRepository

    repo = MongoRepository()
    n = repo.upsert_transactions(df)
    logger.info("MongoDB: upserted %d transaction(s) into 'transactions'", n)
    return n


def load_transactions_to_snowflake(df: pd.DataFrame) -> int:
    """Merge transaction rows into Snowflake's TRANSACTIONS table."""
    from repositories.snowflake_repository import SnowflakeRepository

    repo = SnowflakeRepository()
    repo.ensure_objects()
    n = repo.load_transactions(df)
    logger.info("Snowflake: loaded %d transaction(s) into TRANSACTIONS", n)
    return n


def load_monthly_summary_to_mongo(df: pd.DataFrame) -> int:
    """Upsert monthly summary rows into MongoDB's `monthly_summary` collection."""
    from repositories.mongo_repository import MongoRepository

    repo = MongoRepository()
    n = repo.upsert_monthly_summary(df)
    logger.info("MongoDB: upserted %d monthly summary row(s)", n)
    return n


def load_monthly_summary_to_snowflake(df: pd.DataFrame) -> int:
    """Merge monthly summary rows into Snowflake's MONTHLY_SUMMARY table."""
    from repositories.snowflake_repository import SnowflakeRepository

    repo = SnowflakeRepository()
    repo.ensure_objects()
    n = repo.load_monthly_summary(df)
    logger.info("Snowflake: loaded %d monthly summary row(s) into MONTHLY_SUMMARY", n)
    return n
