"""
Database Initialization Script
==================================
Run this once (and any time schemas change) to provision external storage:

  - MongoDB Atlas : create collections (implicitly) + indexes
  - Snowflake     : create warehouse, database, schema, and tables if missing

Usage:
    python scripts/init_db.py                 # initialize both
    python scripts/init_db.py --mongo-only
    python scripts/init_db.py --snowflake-only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.logger import get_logger  # noqa: E402

logger = get_logger(__name__)


def init_mongo() -> None:
    from repositories.mongo_repository import MongoRepository

    logger.info("Initializing MongoDB Atlas (database + indexes) ...")
    repo = MongoRepository()
    repo.create_indexes()
    logger.info("MongoDB Atlas initialization complete.")


def init_snowflake() -> None:
    from repositories.snowflake_repository import SnowflakeRepository

    logger.info("Initializing Snowflake (warehouse/database/schema/tables) ...")
    repo = SnowflakeRepository()
    repo.ensure_objects()
    logger.info("Snowflake initialization complete.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize MongoDB Atlas and/or Snowflake objects.")
    parser.add_argument("--mongo-only", action="store_true", help="Only initialize MongoDB Atlas")
    parser.add_argument("--snowflake-only", action="store_true", help="Only initialize Snowflake")
    args = parser.parse_args()

    do_mongo = not args.snowflake_only
    do_snowflake = not args.mongo_only

    if do_mongo:
        try:
            init_mongo()
        except Exception as exc:  # noqa: BLE001
            logger.error("MongoDB initialization failed: %s", exc)
            return 1

    if do_snowflake:
        try:
            init_snowflake()
        except Exception as exc:  # noqa: BLE001
            logger.error("Snowflake initialization failed: %s", exc)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
