"""
Configuration Layer
====================
Centralized application configuration loaded from environment variables
(with a local ".env" file for local development via python-dotenv).

All other layers (ETL, repositories, analytics, profiling) read settings
from this module ONLY -- never read os.environ directly elsewhere.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dotenv is optional at runtime
    load_dotenv = None

# ------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
ENV_PATH = BASE_DIR / ".env"
CATEGORY_MAPPING_PATH = BASE_DIR / "config" / "category_mapping.json"

# Load .env if it exists (does nothing if python-dotenv isn't installed)
if load_dotenv is not None and ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)


def _get(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


def _get_required(name: str) -> str:
    value = os.environ.get(name)
    if value is None or value == "":
        raise MissingConfigError(
            f"Required environment variable '{name}' is not set. "
            f"Copy '.env.example' to '.env' and fill in real values."
        )
    return value


class MissingConfigError(RuntimeError):
    """Raised when a required configuration value is missing."""


# ------------------------------------------------------------------
# MongoDB Atlas
# ------------------------------------------------------------------
@dataclass(frozen=True)
class MongoConfig:
    uri: str | None = field(default_factory=lambda: _get("MONGODB_URI"))
    database: str = field(default_factory=lambda: _get("MONGODB_DATABASE", "personal_finance_db"))

    # Canonical collection names (Phase 2 requirement)
    COL_TRANSACTIONS: str = "transactions"
    COL_MONTHLY_SUMMARY: str = "monthly_summary"
    COL_BUDGET_PLANS: str = "budget_plans"
    COL_AI_REPORTS: str = "ai_reports"
    COL_FIRE_SIMULATIONS: str = "fire_simulations"

    def require_uri(self) -> str:
        if not self.uri:
            raise MissingConfigError("MONGODB_URI is not set.")
        return self.uri


# ------------------------------------------------------------------
# Snowflake
# ------------------------------------------------------------------
@dataclass(frozen=True)
class SnowflakeConfig:
    account: str = field(default_factory=lambda: _get("SNOWFLAKE_ACCOUNT", "mj18661"))
    user: str | None = field(default_factory=lambda: _get("SNOWFLAKE_USER"))
    password: str | None = field(default_factory=lambda: _get("SNOWFLAKE_PASSWORD"))
    role: str = field(default_factory=lambda: _get("SNOWFLAKE_ROLE", "ACCOUNTADMIN"))
    warehouse: str = field(default_factory=lambda: _get("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"))
    database: str = field(default_factory=lambda: _get("SNOWFLAKE_DATABASE", "PERSONAL_FINANCE_DB"))
    schema: str = field(default_factory=lambda: _get("SNOWFLAKE_SCHEMA", "PUBLIC"))

    # Canonical table names (Phase 2 requirement)
    TBL_TRANSACTIONS: str = "TRANSACTIONS"
    TBL_MONTHLY_SUMMARY: str = "MONTHLY_SUMMARY"
    TBL_BUDGET_PLANS: str = "BUDGET_PLANS"
    TBL_AI_REPORTS: str = "AI_REPORTS"
    TBL_FIRE_SIMULATIONS: str = "FIRE_SIMULATIONS"

    def require_credentials(self) -> tuple[str, str, str]:
        if not self.user or not self.password:
            raise MissingConfigError(
                "SNOWFLAKE_USER and SNOWFLAKE_PASSWORD must be set."
            )
        return self.account, self.user, self.password


# ------------------------------------------------------------------
# DuckDB
# ------------------------------------------------------------------
@dataclass(frozen=True)
class DuckDBConfig:
    path: str = field(default_factory=lambda: _get("DUCKDB_PATH", ":memory:"))

    def resolved_path(self) -> str:
        """Return the DuckDB path, creating the parent directory if needed."""
        if self.path == ":memory:":
            return self.path
        p = Path(self.path)
        if not p.is_absolute():
            p = BASE_DIR / p
        p.parent.mkdir(parents=True, exist_ok=True)
        return str(p)


# ------------------------------------------------------------------
# Data / Logging
# ------------------------------------------------------------------
@dataclass(frozen=True)
class DataConfig:
    raw_data_path: str = field(default_factory=lambda: _get("RAW_DATA_PATH", "data/raw/Expenses_clean.csv"))

    def resolved_raw_path(self) -> Path:
        p = Path(self.raw_data_path)
        if not p.is_absolute():
            p = BASE_DIR / p
        return p


@dataclass(frozen=True)
class LoggingConfig:
    level: str = field(default_factory=lambda: _get("LOG_LEVEL", "INFO"))
    log_dir: str = field(default_factory=lambda: _get("LOG_DIR", "logs"))

    def resolved_log_dir(self) -> Path:
        p = Path(self.log_dir)
        if not p.is_absolute():
            p = BASE_DIR / p
        p.mkdir(parents=True, exist_ok=True)
        return p


# ------------------------------------------------------------------
# AI Layer (Phase 4)
# ------------------------------------------------------------------
@dataclass(frozen=True)
class AIConfig:
    """
    Configuration for the data-centric AI layer.

    AI is OPTIONAL: if ANTHROPIC_API_KEY is not set, `get_ai_client()`
    returns None and every AI-powered page degrades gracefully to
    "Non-AI Mode" (Python-only calculations, no LLM narrative).
    """

    api_key: str | None = field(default_factory=lambda: _get("ANTHROPIC_API_KEY"))
    model: str = field(default_factory=lambda: _get("AI_MODEL", "claude-sonnet-4-6"))
    max_tokens: int = field(default_factory=lambda: int(_get("AI_MAX_TOKENS", "1024") or "1024"))

    def is_configured(self) -> bool:
        return bool(self.api_key)


# ------------------------------------------------------------------
# FRED (Federal Reserve Economic Data) - macroeconomic context
# ------------------------------------------------------------------
@dataclass(frozen=True)
class FREDConfig:
    """
    Configuration for the FRED macroeconomic data integration.

    FRED is OPTIONAL: if FRED_API_KEY is not set, macro-context helpers
    return an "unavailable" payload and the app continues to run without
    macro data (Non-AI / offline-safe).
    """

    api_key: str | None = field(default_factory=lambda: _get("FRED_API_KEY"))
    base_url: str = field(default_factory=lambda: _get("FRED_BASE_URL", "https://api.stlouisfed.org/fred"))
    indicators: Dict[str, str] = field(
        default_factory=lambda: {
            "CPIAUCSL": "Consumer Price Index (All Urban Consumers, seasonally adjusted)",
            "FEDFUNDS": "Effective Federal Funds Rate",
            "UNRATE": "Civilian Unemployment Rate",
        }
    )

    def is_configured(self) -> bool:
        return bool(self.api_key)


# ------------------------------------------------------------------
# Category -> Transaction Type mapping
# ------------------------------------------------------------------
def load_category_mapping() -> Dict[str, str]:
    """
    Load the category -> type ("Income"/"Expense") mapping used by the ETL
    transform step. Falls back to an all-"Expense" mapping with "Job" as
    "Income" if the JSON file is missing.
    """
    if CATEGORY_MAPPING_PATH.exists():
        with open(CATEGORY_MAPPING_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    return {"default_type": "Expense", "mapping": {"Job": "Income"}}


# ------------------------------------------------------------------
# Singleton-style accessors
# ------------------------------------------------------------------
class Settings:
    """Aggregated settings object. Use settings = Settings() once per process."""

    def __init__(self) -> None:
        self.mongo = MongoConfig()
        self.snowflake = SnowflakeConfig()
        self.duckdb = DuckDBConfig()
        self.data = DataConfig()
        self.logging = LoggingConfig()
        self.ai = AIConfig()
        self.fred = FREDConfig()
        self.category_mapping = load_category_mapping()


settings = Settings()
