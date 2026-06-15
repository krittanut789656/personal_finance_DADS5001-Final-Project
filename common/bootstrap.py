"""
Bootstrap
=========
Adds the Phase 2 `backend/` package to `sys.path` so every Streamlit page
can import backend modules using the same absolute import paths the
backend itself uses internally, e.g.:

    from config.settings import settings
    from analytics.duckdb_engine import DuckDBAnalytics
    from repositories.mongo_repository import MongoRepository

Import this module first (before any backend import) in every page:

    import common.bootstrap  # noqa: F401
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


# ----------------------------------------------------------------------
# Streamlit Secrets -> environment variables
# ----------------------------------------------------------------------
# `backend/config/settings.py` reads configuration exclusively from
# `os.environ` (via `.env` for local dev). On Streamlit Community Cloud
# there is no `.env` file - secrets are configured in the app's "Secrets"
# panel (`.streamlit/secrets.toml`, see `.streamlit/secrets.toml.example`).
# To keep a single configuration path, copy any matching keys from
# `st.secrets` into `os.environ` (without overwriting a real env var /
# local `.env` value) the first time this module is imported.
def _load_secrets_into_env() -> None:
    try:
        import streamlit as st
    except ImportError:  # pragma: no cover - streamlit always available in-app
        return

    try:
        secrets = st.secrets
    except Exception:
        return

    try:
        keys = list(secrets.keys())
    except Exception:
        return

    for key in keys:
        if key in os.environ:
            continue
        try:
            value = secrets[key]
        except Exception:
            continue
        if isinstance(value, (str, int, float, bool)):
            os.environ[key] = str(value)


_load_secrets_into_env()
