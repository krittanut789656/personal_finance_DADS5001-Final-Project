"""
ETL Runner
============
CLI entry point for the ETL pipeline (extract -> transform -> DuckDB ->
load to MongoDB/Snowflake).

Usage:
    python scripts/run_etl.py
    python scripts/run_etl.py --csv data/raw/Expenses_clean.csv
    python scripts/run_etl.py --no-mongo --no-snowflake   # offline/dev mode
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.logger import get_logger  # noqa: E402
from etl.pipeline import run_etl  # noqa: E402

logger = get_logger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the ETL pipeline.")
    parser.add_argument("--csv", default=None, help="Path to the raw transactions CSV")
    parser.add_argument("--no-mongo", action="store_true", help="Skip loading into MongoDB Atlas")
    parser.add_argument("--no-snowflake", action="store_true", help="Skip loading into Snowflake")
    parser.add_argument("--duckdb-path", default=None, help="Override DuckDB database path")
    args = parser.parse_args()

    result = run_etl(
        csv_path=args.csv,
        load_mongo=not args.no_mongo,
        load_snowflake=not args.no_snowflake,
        duckdb_path=args.duckdb_path,
    )

    print(json.dumps(result, indent=2, default=str))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
