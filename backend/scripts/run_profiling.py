"""
Profiling Runner
==================
CLI entry point for the data profiling pipeline. Writes a JSON report to
`reports/` and prints a short summary.

Usage:
    python scripts/run_profiling.py
    python scripts/run_profiling.py --csv data/raw/Expenses_clean.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from profiling.profiler import run_profiling  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the data profiling pipeline.")
    parser.add_argument("--csv", default=None, help="Path to the raw transactions CSV")
    parser.add_argument("--no-save", action="store_true", help="Don't write a JSON report to reports/")
    args = parser.parse_args()

    report = run_profiling(csv_path=args.csv, save_report=not args.no_save)

    print(f"Source rows      : {report['source_rows']}")
    print(f"Clean rows        : {report['clean_rows']}")
    print(f"Duplicate rows    : {report['structural']['duplicate_rows']}")
    print(f"Date range        : {report['statistical']['date_range']['min_date']} -> "
          f"{report['statistical']['date_range']['max_date']}")
    print("Type totals       :")
    for row in report["statistical"]["type_totals"]:
        print(f"  {row['type']:<10} total={row['total_amount']:>10.2f}  n={row['n']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
