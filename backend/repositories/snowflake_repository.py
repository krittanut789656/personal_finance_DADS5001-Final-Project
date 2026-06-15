"""
Snowflake Repository Layer
=============================
All Snowflake access goes through this module.

Per Phase 2 requirements, this repository is responsible for **automatically
creating Snowflake objects if they do not already exist**:

    - Warehouse  : SNOWFLAKE_WAREHOUSE  (default COMPUTE_WH)
    - Database   : SNOWFLAKE_DATABASE   (default PERSONAL_FINANCE_DB)
    - Schema     : SNOWFLAKE_SCHEMA     (default PUBLIC)
    - Tables     : TRANSACTIONS, MONTHLY_SUMMARY, BUDGET_PLANS,
                    AI_REPORTS, FIRE_SIMULATIONS  (see sql/snowflake_ddl.sql)

Table DDL lives in ``sql/snowflake_ddl.sql`` and is executed verbatim by
``ensure_objects()`` -- keeping the SQL schema definition in one place that
can also be run manually in the Snowflake UI / SnowSQL.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from config.settings import settings
from core.logger import get_logger

logger = get_logger(__name__)

DDL_PATH = Path(__file__).resolve().parent.parent / "sql" / "snowflake_ddl.sql"

# Column order must match sql/snowflake_ddl.sql exactly (Snowflake stores
# unquoted identifiers in UPPERCASE).
TRANSACTIONS_COLUMNS = [
    "TRANSACTION_ID", "TRANSACTION_DATE", "TRANSACTION_DATETIME", "YEAR", "MONTH",
    "YEAR_MONTH", "CATEGORY", "TYPE", "ACCOUNT", "AMOUNT", "CURRENCY", "TAGS",
    "SOURCE", "INGESTED_AT",
]
MONTHLY_SUMMARY_COLUMNS = [
    "YEAR_MONTH", "TOTAL_INCOME", "TOTAL_EXPENSE", "NET", "SAVINGS_RATE_PCT",
    "TRANSACTION_COUNT", "GENERATED_AT",
]


class SnowflakeConnectionError(RuntimeError):
    """Raised when a Snowflake connection cannot be established."""


class SnowflakeRepository:
    """Repository providing auto-provisioning + CRUD access to PERSONAL_FINANCE_DB."""

    _connection: Any = None  # memoized snowflake.connector.SnowflakeConnection

    def __init__(self) -> None:
        self.cfg = settings.snowflake

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------
    @classmethod
    def get_connection(cls):
        """Return a memoized Snowflake connection (account/user/password/role/warehouse/db/schema)."""
        if cls._connection is None:
            try:
                import snowflake.connector
            except ImportError as exc:  # pragma: no cover
                raise SnowflakeConnectionError(
                    "snowflake-connector-python is not installed. "
                    "Run: pip install snowflake-connector-python"
                ) from exc

            cfg = settings.snowflake
            account, user, password = cfg.require_credentials()

            logger.info("Connecting to Snowflake account=%s ...", account)
            cls._connection = snowflake.connector.connect(
                account=account,
                user=user,
                password=password,
                role=cfg.role,
                warehouse=cfg.warehouse,
                database=cfg.database,
                schema=cfg.schema,
                client_session_keep_alive=True,
            )
            logger.info("Snowflake connection established")
        return cls._connection

    @classmethod
    def reset_connection(cls) -> None:
        if cls._connection is not None:
            cls._connection.close()
            cls._connection = None

    # ------------------------------------------------------------------
    # Auto-provisioning (Phase 2 requirement)
    # ------------------------------------------------------------------
    def ensure_objects(self) -> None:
        """
        Create the warehouse, database, schema, and all tables if they do
        not already exist. Safe to call on every app/ETL startup.
        """
        import snowflake.connector

        cfg = settings.snowflake
        account, user, password = cfg.require_credentials()

        # Step 1: bootstrap connection without DB/schema/warehouse context,
        # since they may not exist yet.
        logger.info("Ensuring Snowflake objects exist (warehouse/database/schema/tables) ...")
        bootstrap_conn = snowflake.connector.connect(
            account=account,
            user=user,
            password=password,
            role=cfg.role,
        )
        try:
            cur = bootstrap_conn.cursor()
            cur.execute(
                f"CREATE WAREHOUSE IF NOT EXISTS {cfg.warehouse} "
                f"WAREHOUSE_SIZE = 'XSMALL' AUTO_SUSPEND = 60 AUTO_RESUME = TRUE "
                f"INITIALLY_SUSPENDED = TRUE"
            )
            cur.execute(f"CREATE DATABASE IF NOT EXISTS {cfg.database}")
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {cfg.database}.{cfg.schema}")
            logger.info(
                "Warehouse '%s', database '%s', schema '%s' ensured",
                cfg.warehouse, cfg.database, cfg.schema,
            )
        finally:
            cur.close()
            bootstrap_conn.close()

        # Step 2: connect with full context and create tables from DDL file.
        conn = self.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(f"USE WAREHOUSE {cfg.warehouse}")
            cur.execute(f"USE DATABASE {cfg.database}")
            cur.execute(f"USE SCHEMA {cfg.schema}")

            ddl_sql = DDL_PATH.read_text(encoding="utf-8")
            statements = [s.strip() for s in ddl_sql.split(";")]
            for stmt in statements:
                # strip comment-only / blank statements
                lines = [l for l in stmt.splitlines() if not l.strip().startswith("--") and l.strip()]
                if not lines:
                    continue
                cleaned = "\n".join(lines)
                cur.execute(cleaned)
            logger.info("Snowflake tables ensured from %s", DDL_PATH.name)
        finally:
            cur.close()

    # ------------------------------------------------------------------
    # Generic helpers
    # ------------------------------------------------------------------
    def run_query(self, sql: str, params: Optional[list] = None) -> pd.DataFrame:
        conn = self.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(sql, params or [])
            return cur.fetch_pandas_all()
        finally:
            cur.close()

    def _merge_dataframe(self, df: pd.DataFrame, table: str, key_columns: list[str], all_columns: list[str]) -> int:
        """
        Load `df` into Snowflake `table` via a temporary staging table + MERGE
        (upsert) on `key_columns`. `all_columns` must be UPPERCASE and match
        the table's column order.
        """
        from snowflake.connector.pandas_tools import write_pandas

        if df.empty:
            return 0

        conn = self.get_connection()
        stage_table = f"{table}_STAGE_{uuid.uuid4().hex[:8]}"

        # Ensure dataframe columns are uppercase to match Snowflake defaults
        df_upper = df.copy()
        df_upper.columns = [c.upper() for c in df_upper.columns]
        df_upper = df_upper[all_columns]

        write_pandas(
            conn,
            df_upper,
            table_name=stage_table,
            auto_create_table=True,
            overwrite=True,
            temp_table=True,
        )

        update_clause = ", ".join(f"t.{c} = s.{c}" for c in all_columns if c not in key_columns)
        on_clause = " AND ".join(f"t.{c} = s.{c}" for c in key_columns)
        insert_cols = ", ".join(all_columns)
        insert_vals = ", ".join(f"s.{c}" for c in all_columns)

        merge_sql = f"""
            MERGE INTO {table} t
            USING {stage_table} s
            ON {on_clause}
            WHEN MATCHED THEN UPDATE SET {update_clause}
            WHEN NOT MATCHED THEN INSERT ({insert_cols}) VALUES ({insert_vals})
        """

        cur = conn.cursor()
        try:
            cur.execute(merge_sql)
            return cur.rowcount or len(df_upper)
        finally:
            cur.close()

    # ------------------------------------------------------------------
    # TRANSACTIONS
    # ------------------------------------------------------------------
    def load_transactions(self, df: pd.DataFrame) -> int:
        return self._merge_dataframe(df, "TRANSACTIONS", ["TRANSACTION_ID"], TRANSACTIONS_COLUMNS)

    # ------------------------------------------------------------------
    # MONTHLY_SUMMARY
    # ------------------------------------------------------------------
    def load_monthly_summary(self, df: pd.DataFrame) -> int:
        return self._merge_dataframe(df, "MONTHLY_SUMMARY", ["YEAR_MONTH"], MONTHLY_SUMMARY_COLUMNS)

    # ------------------------------------------------------------------
    # BUDGET_PLANS
    # ------------------------------------------------------------------
    def create_budget_plan(self, plan: dict) -> str:
        conn = self.get_connection()
        budget_id = plan.get("budget_id") or str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO BUDGET_PLANS "
                "(budget_id, category, monthly_limit, period, currency, created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (
                    budget_id,
                    plan["category"],
                    plan["monthly_limit"],
                    plan.get("period"),
                    plan.get("currency", "BYN"),
                    now,
                    now,
                ),
            )
        finally:
            cur.close()
        return budget_id

    def list_budget_plans(self) -> pd.DataFrame:
        return self.run_query("SELECT * FROM BUDGET_PLANS ORDER BY created_at DESC")

    # ------------------------------------------------------------------
    # AI_REPORTS
    # ------------------------------------------------------------------
    def insert_ai_report(self, report: dict) -> str:
        conn = self.get_connection()
        report_id = report.get("report_id") or str(uuid.uuid4())
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO AI_REPORTS "
                "(report_id, report_type, query_hash, metadata_snapshot, prompt, response, model, created_at) "
                "SELECT %s, %s, %s, PARSE_JSON(%s), %s, %s, %s, %s",
                (
                    report_id,
                    report.get("report_type"),
                    report.get("query_hash"),
                    json.dumps(report.get("metadata_snapshot", {})),
                    report.get("prompt"),
                    report.get("response"),
                    report.get("model"),
                    datetime.now(timezone.utc),
                ),
            )
        finally:
            cur.close()
        return report_id

    def list_ai_reports(self, limit: int = 50) -> pd.DataFrame:
        return self.run_query(f"SELECT * FROM AI_REPORTS ORDER BY created_at DESC LIMIT {int(limit)}")

    # ------------------------------------------------------------------
    # FIRE_SIMULATIONS
    # ------------------------------------------------------------------
    def insert_fire_simulation(self, simulation: dict) -> str:
        conn = self.get_connection()
        simulation_id = simulation.get("simulation_id") or str(uuid.uuid4())
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO FIRE_SIMULATIONS (simulation_id, params, results, created_at) "
                "SELECT %s, PARSE_JSON(%s), PARSE_JSON(%s), %s",
                (
                    simulation_id,
                    json.dumps(simulation.get("params", {})),
                    json.dumps(simulation.get("results", {})),
                    datetime.now(timezone.utc),
                ),
            )
        finally:
            cur.close()
        return simulation_id

    def list_fire_simulations(self, limit: int = 50) -> pd.DataFrame:
        return self.run_query(f"SELECT * FROM FIRE_SIMULATIONS ORDER BY created_at DESC LIMIT {int(limit)}")
