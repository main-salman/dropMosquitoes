# Implements: SW-001 §2.12 — rotating activity log for field troubleshooting
"""
activity_log.py — Append-only rotating log of arm/fire/solenoid/cal events.

File: activity.log (project root), rotates at 10 MB, keeps 5 backups.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

_LOGGER: logging.Logger | None = None
MAX_BYTES = 10 * 1024 * 1024  # 10 MB
BACKUP_COUNT = 5


def init_activity_log(project_dir: str) -> logging.Logger:
    """Idempotent init; returns the shared activity logger."""
    global _LOGGER
    if _LOGGER is not None:
        return _LOGGER

    path = os.path.join(project_dir, "activity.log")
    logger = logging.getLogger("dropMosquitoes.activity")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        handler = RotatingFileHandler(
            path, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        logger.addHandler(handler)
    _LOGGER = logger
    logger.info("activity_log started path=%s max=%sMB backups=%s",
                path, MAX_BYTES // (1024 * 1024), BACKUP_COUNT)
    return logger


def get_activity_logger() -> logging.Logger:
    if _LOGGER is None:
        # Fallback before app init — cwd-relative
        return init_activity_log(os.getcwd())
    return _LOGGER


def log_event(event: str, **fields):
    """Log a structured one-line event: EVENT key=val key=val ..."""
    parts = [str(event)]
    for key, val in fields.items():
        if val is None:
            continue
        parts.append(f"{key}={val}")
    get_activity_logger().info(" ".join(parts))
