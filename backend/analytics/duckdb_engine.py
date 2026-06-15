"""
DuckDB Analytics Layer (MANDATORY)
=====================================
Every analytical computation in this platform - monthly summaries, category
breakdowns, trends, savings-rate, anomaly detection, and (later) What-If /
FIRE simulator math - is expressed as SQL and executed through DuckDB.

This module is the *only* place SQL analytics queries live. Other layers
(ETL, profiling, future Streamlit pages) call into `DuckDBAnalytics` rather
than re-implementing aggregations in Pandas.

DuckDB can run against:
  - an in-memory database (default for quick/test runs, DUCKDB_PATH=":memory:")
  - a persistent .duckdb file (DUCKDB_PATH=data/duckdb/personal_finance.duckdb)

Both Mongo-sourced and Snowflake-sourced DataFrames can be registered as
DuckDB tables/views, so DuckDB also acts as the unifying query layer across
the two cloud stores.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import duckdb
import pandas as pd

from config.settings import settings
from core.logger import get_logger

logger = get_logger(__name__)

TRANSACTIONS_TABLE = "transactions"


class DuckDBAnalytics:
    """Thin wrapper around a DuckDB connection providing canonical analytics queries."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is not None:
            path = db_path
            if path != ":memory:":
                Path(path).parent.mkdir(parents=True, exist_ok=True)
        else:
            path = settings.duckdb.resolved_path()
        logger.info("Opening DuckDB connection: %s", path)
        self.con = duckdb.connect(database=path)

    # ------------------------------------------------------------------
    # Data loading / registration
    # ------------------------------------------------------------------
    def load_transactions(self, df: pd.DataFrame, mode: str = "replace") -> int:
        self.con.register("_incoming_transactions", df)
        try:
            if mode == "replace":
                self.con.execute(
                    f"CREATE OR REPLACE TABLE {TRANSACTIONS_TABLE} AS "
                    f"SELECT * FROM _incoming_transactions"
                )
            elif mode == "append":
                exists = self.con.execute(
                    "SELECT count(*) FROM information_schema.tables "
                    "WHERE table_name = ?",
                    [TRANSACTIONS_TABLE],
                ).fetchone()[0]
                if exists:
                    self.con.execute(
                        f"INSERT INTO {TRANSACTIONS_TABLE} "
                        f"SELECT * FROM _incoming_transactions AS new_rows "
                        f"WHERE new_rows.transaction_id NOT IN "
                        f"(SELECT transaction_id FROM {TRANSACTIONS_TABLE})"
                    )
                else:
                    self.con.execute(
                        f"CREATE TABLE {TRANSACTIONS_TABLE} AS "
                        f"SELECT * FROM _incoming_transactions"
                    )
            else:
                raise ValueError(f"Unknown mode '{mode}', expected 'replace' or 'append'")
        finally:
            self.con.unregister("_incoming_transactions")

        count = self.con.execute(f"SELECT count(*) FROM {TRANSACTIONS_TABLE}").fetchone()[0]
        return count

    def register_dataframe(self, name: str, df: pd.DataFrame) -> None:
        self.con.register(name, df)

    # ------------------------------------------------------------------
    # Generic passthrough
    # ------------------------------------------------------------------
    def run_query(self, sql: str, params: Optional[list] = None) -> pd.DataFrame:
        if params:
            return self.con.execute(sql, params).fetchdf()
        return self.con.execute(sql).fetchdf()

    # ------------------------------------------------------------------
    # Canonical analytics queries
    # ------------------------------------------------------------------
    def monthly_summary(self) -> pd.DataFrame:
        sql = f"""
            SELECT
                year_month,
                CAST(SUM(CASE WHEN type = 'Income'  THEN amount ELSE 0 END) AS DOUBLE) AS total_income,
                CAST(SUM(CASE WHEN type = 'Expense' THEN amount ELSE 0 END) AS DOUBLE) AS total_expense,
                CAST(SUM(CASE WHEN type = 'Income'  THEN amount ELSE -amount END) AS DOUBLE) AS net,
                COUNT(*) AS transaction_count
            FROM {TRANSACTIONS_TABLE}
            GROUP BY year_month
            ORDER BY year_month
        """
        df = self.run_query(sql)
        df["savings_rate_pct"] = df.apply(
            lambda r: round((r["net"] / r["total_income"]) * 100, 2) if r["total_income"] > 0 else None,
            axis=1,
        )
        df["generated_at"] = datetime.now(timezone.utc).isoformat()
        return df

    def category_breakdown(self, year_month: Optional[str] = None, type_filter: Optional[str] = None) -> pd.DataFrame:
        where = []
        params: list = []
        if year_month:
            where.append("year_month = ?")
            params.append(year_month)
        if type_filter:
            where.append("type = ?")
            params.append(type_filter)
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""

        sql = f"""
            SELECT
                category,
                type,
                CAST(SUM(amount) AS DOUBLE) AS total_amount,
                COUNT(*) AS transaction_count,
                CAST(AVG(amount) AS DOUBLE) AS avg_amount
            FROM {TRANSACTIONS_TABLE}
            {where_sql}
            GROUP BY category, type
            ORDER BY total_amount DESC
        """
        return self.run_query(sql, params or None)

    def top_categories(self, n: int = 5, type_filter: str = "Expense") -> pd.DataFrame:
        sql = f"""
            SELECT
                category,
                CAST(SUM(amount) AS DOUBLE) AS total_amount,
                COUNT(*) AS transaction_count
            FROM {TRANSACTIONS_TABLE}
            WHERE type = ?
            GROUP BY category
            ORDER BY total_amount DESC
            LIMIT ?
        """
        return self.run_query(sql, [type_filter, n])

    def monthly_trends(self) -> pd.DataFrame:
        sql = f"""
            WITH monthly AS (
                SELECT
                    year_month,
                    SUM(CASE WHEN type = 'Income'  THEN amount ELSE 0 END) AS total_income,
                    SUM(CASE WHEN type = 'Expense' THEN amount ELSE 0 END) AS total_expense
                FROM {TRANSACTIONS_TABLE}
                GROUP BY year_month
            )
            SELECT
                year_month,
                total_income,
                total_expense,
                total_income - total_expense AS net,
                ROUND(
                    100.0 * (total_expense - LAG(total_expense) OVER (ORDER BY year_month))
                    / NULLIF(LAG(total_expense) OVER (ORDER BY year_month), 0),
                    2
                ) AS expense_mom_change_pct,
                ROUND(
                    100.0 * (total_income - LAG(total_income) OVER (ORDER BY year_month))
                    / NULLIF(LAG(total_income) OVER (ORDER BY year_month), 0),
                    2
                ) AS income_mom_change_pct,
                ROUND(AVG(total_expense) OVER (
                    ORDER BY year_month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
                ), 2) AS expense_3mo_avg
            FROM monthly
            ORDER BY year_month
        """
        return self.run_query(sql)

    def account_breakdown(self) -> pd.DataFrame:
        sql = f"""
            SELECT
                account,
                CAST(SUM(CASE WHEN type = 'Expense' THEN amount ELSE 0 END) AS DOUBLE) AS total_expense,
                CAST(SUM(CASE WHEN type = 'Income'  THEN amount ELSE 0 END) AS DOUBLE) AS total_income,
                COUNT(*) AS transaction_count
            FROM {TRANSACTIONS_TABLE}
            GROUP BY account
            ORDER BY total_expense DESC
        """
        return self.run_query(sql)

    def detect_anomalies(self, z_threshold: float = 2.0) -> pd.DataFrame:
        sql = f"""
            WITH cat_month AS (
                SELECT
                    category,
                    year_month,
                    SUM(amount) AS month_total
                FROM {TRANSACTIONS_TABLE}
                WHERE type = 'Expense'
                GROUP BY category, year_month
            ),
            cat_stats AS (
                SELECT
                    category,
                    AVG(month_total) AS mean_total,
                    STDDEV_SAMP(month_total) AS std_total
                FROM cat_month
                GROUP BY category
            )
            SELECT
                cm.category,
                cm.year_month,
                ROUND(cm.month_total, 2) AS month_total,
                ROUND(cs.mean_total, 2) AS category_mean,
                ROUND(cs.std_total, 2) AS category_std,
                ROUND((cm.month_total - cs.mean_total) / NULLIF(cs.std_total, 0), 2) AS z_score
            FROM cat_month cm
            JOIN cat_stats cs USING (category)
            WHERE cs.std_total IS NOT NULL
              AND cs.std_total > 0
              AND ABS((cm.month_total - cs.mean_total) / cs.std_total) >= ?
            ORDER BY ABS((cm.month_total - cs.mean_total) / cs.std_total) DESC
        """
        return self.run_query(sql, [z_threshold])

    # ------------------------------------------------------------------
    # Filter-aware analytics (Streamlit layer - Phase 3)
    # ------------------------------------------------------------------
    @staticmethod
    def _build_where(filters: Optional[dict]) -> tuple[str, list]:
        clauses: list[str] = []
        params: list = []
        if not filters:
            return "", params

        if filters.get("start_ym"):
            clauses.append("year_month >= ?")
            params.append(filters["start_ym"])
        if filters.get("end_ym"):
            clauses.append("year_month <= ?")
            params.append(filters["end_ym"])
        for key, column in (("accounts", "account"), ("categories", "category"), ("types", "type")):
            values = filters.get(key)
            if values:
                placeholders = ", ".join(["?"] * len(values))
                clauses.append(f"{column} IN ({placeholders})")
                params.extend(values)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return where_sql, params

    def monthly_summary_filtered(self, filters: Optional[dict] = None) -> pd.DataFrame:
        where_sql, params = self._build_where(filters)
        sql = f"""
            SELECT
                year_month,
                CAST(SUM(CASE WHEN type = 'Income'  THEN amount ELSE 0 END) AS DOUBLE) AS total_income,
                CAST(SUM(CASE WHEN type = 'Expense' THEN amount ELSE 0 END) AS DOUBLE) AS total_expense,
                CAST(SUM(CASE WHEN type = 'Income'  THEN amount ELSE -amount END) AS DOUBLE) AS net,
                COUNT(*) AS transaction_count
            FROM {TRANSACTIONS_TABLE}
            {where_sql}
            GROUP BY year_month
            ORDER BY year_month
        """
        df = self.run_query(sql, params or None)
        df["savings_rate_pct"] = df.apply(
            lambda r: round((r["net"] / r["total_income"]) * 100, 2) if r["total_income"] > 0 else None,
            axis=1,
        )
        return df

    def category_breakdown_filtered(self, filters: Optional[dict] = None) -> pd.DataFrame:
        where_sql, params = self._build_where(filters)
        sql = f"""
            SELECT
                category,
                type,
                CAST(SUM(amount) AS DOUBLE) AS total_amount,
                COUNT(*) AS transaction_count,
                CAST(AVG(amount) AS DOUBLE) AS avg_amount
            FROM {TRANSACTIONS_TABLE}
            {where_sql}
            GROUP BY category, type
            ORDER BY total_amount DESC
        """
        return self.run_query(sql, params or None)

    def top_categories_filtered(self, filters: Optional[dict] = None, n: int = 5, type_filter: str = "Expense") -> pd.DataFrame:
        merged = dict(filters or {})
        merged["types"] = [type_filter]
        where_sql, params = self._build_where(merged)
        sql = f"""
            SELECT
                category,
                CAST(SUM(amount) AS DOUBLE) AS total_amount,
                COUNT(*) AS transaction_count
            FROM {TRANSACTIONS_TABLE}
            {where_sql}
            GROUP BY category
            ORDER BY total_amount DESC
            LIMIT ?
        """
        return self.run_query(sql, params + [n])

    def monthly_trends_filtered(self, filters: Optional[dict] = None) -> pd.DataFrame:
        where_sql, params = self._build_where(filters)
        sql = f"""
            WITH monthly AS (
                SELECT
                    year_month,
                    SUM(CASE WHEN type = 'Income'  THEN amount ELSE 0 END) AS total_income,
                    SUM(CASE WHEN type = 'Expense' THEN amount ELSE 0 END) AS total_expense
                FROM {TRANSACTIONS_TABLE}
                {where_sql}
                GROUP BY year_month
            )
            SELECT
                year_month,
                total_income,
                total_expense,
                total_income - total_expense AS net,
                ROUND(
                    100.0 * (total_expense - LAG(total_expense) OVER (ORDER BY year_month))
                    / NULLIF(LAG(total_expense) OVER (ORDER BY year_month), 0),
                    2
                ) AS expense_mom_change_pct,
                ROUND(
                    100.0 * (total_income - LAG(total_income) OVER (ORDER BY year_month))
                    / NULLIF(LAG(total_income) OVER (ORDER BY year_month), 0),
                    2
                ) AS income_mom_change_pct,
                ROUND(AVG(total_expense) OVER (
                    ORDER BY year_month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
                ), 2) AS expense_3mo_avg
            FROM monthly
            ORDER BY year_month
        """
        return self.run_query(sql, params or None)

    def account_breakdown_filtered(self, filters: Optional[dict] = None) -> pd.DataFrame:
        where_sql, params = self._build_where(filters)
        sql = f"""
            SELECT
                account,
                CAST(SUM(CASE WHEN type = 'Expense' THEN amount ELSE 0 END) AS DOUBLE) AS total_expense,
                CAST(SUM(CASE WHEN type = 'Income'  THEN amount ELSE 0 END) AS DOUBLE) AS total_income,
                COUNT(*) AS transaction_count
            FROM {TRANSACTIONS_TABLE}
            {where_sql}
            GROUP BY account
            ORDER BY total_expense DESC
        """
        return self.run_query(sql, params or None)

    def filtered_transactions(self, filters: Optional[dict] = None, limit: Optional[int] = None) -> pd.DataFrame:
        where_sql, params = self._build_where(filters)
        sql = f"""
            SELECT *
            FROM {TRANSACTIONS_TABLE}
            {where_sql}
            ORDER BY transaction_date DESC
        """
        if limit:
            sql += " LIMIT ?"
            params = params + [limit]
        return self.run_query(sql, params or None)

    def available_year_months(self) -> list[str]:
        df = self.run_query(f"SELECT DISTINCT year_month FROM {TRANSACTIONS_TABLE} ORDER BY year_month")
        return df["year_month"].tolist()

    def available_accounts(self) -> list[str]:
        df = self.run_query(f"SELECT DISTINCT account FROM {TRANSACTIONS_TABLE} ORDER BY account")
        return df["account"].tolist()

    def available_categories(self) -> list[str]:
        df = self.run_query(f"SELECT DISTINCT category FROM {TRANSACTIONS_TABLE} ORDER BY category")
        return df["category"].tolist()

    def date_range(self) -> dict:
        sql = f"""
            SELECT
                MIN(transaction_date) AS min_date,
                MAX(transaction_date) AS max_date,
                COUNT(*) AS row_count
            FROM {TRANSACTIONS_TABLE}
        """
        row = self.run_query(sql).iloc[0]
        return {"min_date": row["min_date"], "max_date": row["max_date"], "row_count": int(row["row_count"])}

    # ------------------------------------------------------------------
    def close(self) -> None:
        self.con.close()

    def __enter__(self) -> "DuckDBAnalytics":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
