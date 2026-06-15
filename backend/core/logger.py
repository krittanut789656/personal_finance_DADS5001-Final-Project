"""
Logging Layer
==============
Centralized logger factory used by every other layer (ETL, repositories,
analytics, profiling). Provides:

  - Console output (INFO and above by default)
  - Rotating file output under <LOG_DIR>/<name>.log
  - Consistent formatting with timestamps and module names

Usage:
    from core.logger import get_logger
    logger = get_logger(__name__)
    logger.info("message")
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config.settings import settings

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured_loggers: set[str] = set()


def get_logger(name: str = "personal_finance") -> logging.Logger:
    """
    Return a configured logger. Safe to call multiple times for the same
    name -- handlers are only attached once per logger.
    """
    logger = logging.getLogger(name)

    if name in _configured_loggers:
        return logger

    level = getattr(logging, settings.logging.level.upper(), logging.INFO)
    logger.setLevel(level)
    logger.propagate = False

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Rotating file handler
    log_dir: Path = settings.logging.resolved_log_dir()
    safe_name = name.replace(".", "_")
    file_handler = RotatingFileHandler(
        log_dir / f"{safe_name}.log",
        maxBytes=2 * 1024 * 1024,  # 2 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    _configured_loggers.add(name)
    return logger
