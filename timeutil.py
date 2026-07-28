# Implements: SW-001 §1 — Eastern Time for logs, gallery, GUI stamps
"""
timeutil.py — Project-wide America/New_York (EST/EDT) timestamps.

Jetson OS timezone should also be America/New_York (timedatectl). This module
forces ET even if the host TZ drifts, so gallery/logs/GUI stay consistent.
"""

from __future__ import annotations

import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


def ensure_process_tz() -> None:
    """Pin process localtime to Eastern (affects time.strftime + logging asctime)."""
    os.environ["TZ"] = "America/New_York"
    if hasattr(time, "tzset"):
        time.tzset()


def now() -> datetime:
    """Timezone-aware now in America/New_York."""
    return datetime.now(ET)


def stamp_file() -> str:
    """Filesystem-safe id stamp: YYYYMMDD_HHMMSS_mmm"""
    return now().strftime("%Y%m%d_%H%M%S_%f")[:-3]


def stamp_iso() -> str:
    """ISO-8601 with offset, second resolution."""
    return now().isoformat(timespec="seconds")


def stamp_full() -> str:
    """Human full local stamp: YYYY-MM-DD HH:MM:SS"""
    return now().strftime("%Y-%m-%d %H:%M:%S")


def stamp_hms() -> str:
    """HH:MM:SS for compact log lines."""
    return now().strftime("%H:%M:%S")
