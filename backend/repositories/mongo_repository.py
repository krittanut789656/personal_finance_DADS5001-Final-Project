"""
MongoDB Repository Layer
===========================
All MongoDB Atlas access goes through this module. Database: the value of
MONGODB_DATABASE (default "personal_finance_db").

Collections (Phase 2 requirement)
----------------------------------
  - transactions       : canonical transaction rows (ETL output)
  - monthly_summary     : DuckDB-derived monthly aggregates
  - budget_plans        : user-defined per-category budgets (app feature)
  - ai_reports          : cached LLM insight reports (AI mode)
  - fire_simulations    : saved FIRE Planner scenarios

Connection is lazily created and memoized on the class (singleton-style),
mirroring how a Streamlit app would wrap this with `@st.cache_resource`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd

from config.settings import settings
from core.logger import get_logger

logger = get_logger(__name__)


class MongoConnectionError(RuntimeError):
    """Raised when a MongoDB Atlas connection cannot be established."""


class MongoRepository:
    """Repository providing CRUD access to all `personal_finance_db` collections."""

    _client: Any = None  # memoized pymongo.MongoClient, shared across instances

    def __init__(self) -> None:
        self.cfg = settings.mongo

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------
    @classmethod
    def get_client(cls):
        """Return a memoized `pymongo.MongoClient`. Creates one on first call."""
        if cls._client is None:
            try:
                from pymongo import MongoClient
            except ImportError as exc:  # pragma: no cover
                raise MongoConnectionError(
                    "pymongo is not installed. Run: pip install 'pymongo[srv]'"
                ) from exc

            uri = settings.mongo.require_uri()
            logger.info("Connecting to MongoDB Atlas ...")
            cls._client = MongoClient(uri, serverSelectionTimeoutMS=10000)
            # Fail fast if the URI/credentials are bad
            cls._client.admin.command("ping")
            logger.info("MongoDB Atlas connection established")
        return cls._client

    def get_db(self):
        return self.get_client()[self.cfg.database]

    @classmethod
    def reset_connection(cls) -> None:
        """Close and forget the memoized client (mainly for tests)."""
        if cls._client is not None:
            cls._client.close()
            cls._client = None

    # ------------------------------------------------------------------
    # Index management (Phase 2 - database initialization)
    # ------------------------------------------------------------------
    def create_indexes(self) -> None:
        """Create all indexes required for efficient querying. Idempotent."""
        db = self.get_db()

        db[self.cfg.COL_TRANSACTIONS].create_index("transaction_id", unique=True, name="uq_transaction_id")
        db[self.cfg.COL_TRANSACTIONS].create_index("transaction_date", name="ix_transaction_date")
        db[self.cfg.COL_TRANSACTIONS].create_index([("category", 1), ("type", 1)], name="ix_category_type")
        db[self.cfg.COL_TRANSACTIONS].create_index("year_month", name="ix_year_month")

        db[self.cfg.COL_MONTHLY_SUMMARY].create_index("year_month", unique=True, name="uq_year_month")

        db[self.cfg.COL_BUDGET_PLANS].create_index([("category", 1), ("period", 1)], name="ix_category_period")

        db[self.cfg.COL_AI_REPORTS].create_index("query_hash", name="ix_query_hash")
        db[self.cfg.COL_AI_REPORTS].create_index("created_at", name="ix_created_at")

        db[self.cfg.COL_FIRE_SIMULATIONS].create_index("created_at", name="ix_created_at")

        logger.info("MongoDB indexes ensured on all collections")

    # ------------------------------------------------------------------
    # transactions
    # ------------------------------------------------------------------
    def upsert_transactions(self, df: pd.DataFrame) -> int:
        """Upsert transaction rows keyed by `transaction_id`. Returns rows processed."""
        from pymongo import UpdateOne

        if df.empty:
            return 0

        db = self.get_db()
        col = db[self.cfg.COL_TRANSACTIONS]

        records = df.to_dict("records")
        ops = [
            UpdateOne({"transaction_id": rec["transaction_id"]}, {"$set": rec}, upsert=True)
            for rec in records
        ]
        result = col.bulk_write(ops, ordered=False)
        return result.upserted_count + result.modified_count + result.matched_count

    def find_transactions(self, query: Optional[dict] = None, limit: int = 0) -> pd.DataFrame:
        db = self.get_db()
        cursor = db[self.cfg.COL_TRANSACTIONS].find(query or {}, {"_id": 0})
        if limit:
            cursor = cursor.limit(limit)
        return pd.DataFrame(list(cursor))

    # ------------------------------------------------------------------
    # monthly_summary
    # ------------------------------------------------------------------
    def upsert_monthly_summary(self, df: pd.DataFrame) -> int:
        """Upsert monthly summary rows keyed by `year_month`."""
        from pymongo import UpdateOne

        if df.empty:
            return 0

        db = self.get_db()
        col = db[self.cfg.COL_MONTHLY_SUMMARY]

        records = df.to_dict("records")
        ops = [
            UpdateOne({"year_month": rec["year_month"]}, {"$set": rec}, upsert=True)
            for rec in records
        ]
        result = col.bulk_write(ops, ordered=False)
        return result.upserted_count + result.modified_count + result.matched_count

    def find_monthly_summary(self) -> pd.DataFrame:
        db = self.get_db()
        cursor = db[self.cfg.COL_MONTHLY_SUMMARY].find({}, {"_id": 0}).sort("year_month", 1)
        return pd.DataFrame(list(cursor))

    # ------------------------------------------------------------------
    # budget_plans
    # ------------------------------------------------------------------
    def create_budget_plan(self, plan: dict) -> str:
        db = self.get_db()
        plan = {**plan, "created_at": datetime.now(timezone.utc).isoformat()}
        result = db[self.cfg.COL_BUDGET_PLANS].insert_one(plan)
        return str(result.inserted_id)

    def list_budget_plans(self, query: Optional[dict] = None) -> pd.DataFrame:
        db = self.get_db()
        cursor = db[self.cfg.COL_BUDGET_PLANS].find(query or {})
        df = pd.DataFrame(list(cursor))
        if not df.empty and "_id" in df.columns:
            df["_id"] = df["_id"].astype(str)
        return df

    def update_budget_plan(self, plan_id: str, updates: dict) -> int:
        from bson import ObjectId

        db = self.get_db()
        updates = {**updates, "updated_at": datetime.now(timezone.utc).isoformat()}
        result = db[self.cfg.COL_BUDGET_PLANS].update_one({"_id": ObjectId(plan_id)}, {"$set": updates})
        return result.modified_count

    def delete_budget_plan(self, plan_id: str) -> int:
        from bson import ObjectId

        db = self.get_db()
        result = db[self.cfg.COL_BUDGET_PLANS].delete_one({"_id": ObjectId(plan_id)})
        return result.deleted_count

    # ------------------------------------------------------------------
    # ai_reports
    # ------------------------------------------------------------------
    def insert_ai_report(self, report: dict) -> str:
        db = self.get_db()
        report = {**report, "created_at": datetime.now(timezone.utc).isoformat()}
        result = db[self.cfg.COL_AI_REPORTS].insert_one(report)
        return str(result.inserted_id)

    def find_ai_report_by_hash(self, query_hash: str) -> Optional[dict]:
        db = self.get_db()
        doc = db[self.cfg.COL_AI_REPORTS].find_one({"query_hash": query_hash}, sort=[("created_at", -1)])
        return doc

    def list_ai_reports(self, limit: int = 50) -> pd.DataFrame:
        db = self.get_db()
        cursor = db[self.cfg.COL_AI_REPORTS].find({}, {"_id": 0}).sort("created_at", -1).limit(limit)
        return pd.DataFrame(list(cursor))

    # ------------------------------------------------------------------
    # fire_simulations
    # ------------------------------------------------------------------
    def insert_fire_simulation(self, simulation: dict) -> str:
        db = self.get_db()
        simulation = {**simulation, "created_at": datetime.now(timezone.utc).isoformat()}
        result = db[self.cfg.COL_FIRE_SIMULATIONS].insert_one(simulation)
        return str(result.inserted_id)

    def list_fire_simulations(self, limit: int = 50) -> pd.DataFrame:
        db = self.get_db()
        cursor = db[self.cfg.COL_FIRE_SIMULATIONS].find({}, {"_id": 0}).sort("created_at", -1).limit(limit)
        return pd.DataFrame(list(cursor))
