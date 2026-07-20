# Implements: SW-001 §2.11
"""
settings_store.py — Central persistent settings (settings.json).

Creates settings.json with defaults on first run. Runtime code reads/writes
through SettingsStore; machine-local values are not committed to git.
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any


# Factory defaults when settings.json is first created.
DEFAULTS: dict[str, Any] = {
    "target_psi": 5.0,  # start small for calibration; raise via GUI
}


class SettingsStore:
    """Thread-safe load/merge/save for the project-root settings.json."""

    def __init__(self, path: str):
        self._path = path
        self._lock = threading.Lock()
        self._data: dict[str, Any] = {}
        self.load()

    @property
    def path(self) -> str:
        return self._path

    def load(self) -> dict[str, Any]:
        """Load from disk, creating the file with defaults if missing."""
        with self._lock:
            if not os.path.isfile(self._path):
                self._data = dict(DEFAULTS)
                self._write_unlocked()
                print(f"[SettingsStore] Created {self._path} with defaults: {self._data}")
                return dict(self._data)
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if not isinstance(loaded, dict):
                    raise ValueError("settings.json root must be an object")
                # Merge so new keys appear when DEFAULTS grows.
                merged = dict(DEFAULTS)
                merged.update(loaded)
                self._data = merged
                # Persist merge if new default keys were added.
                if set(merged.keys()) != set(loaded.keys()):
                    self._write_unlocked()
                print(f"[SettingsStore] Loaded {self._path}: {self._data}")
            except Exception as e:
                print(f"[SettingsStore] Load failed ({e}); using defaults")
                self._data = dict(DEFAULTS)
                self._write_unlocked()
            return dict(self._data)

    def get(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._data)

    def get_value(self, key: str, default=None):
        with self._lock:
            return self._data.get(key, default)

    def update(self, patch: dict[str, Any], persist: bool = True) -> dict[str, Any]:
        """Merge patch into settings. Persist to disk when persist=True."""
        with self._lock:
            for k, v in patch.items():
                if k in DEFAULTS or k in self._data:
                    self._data[k] = v
                else:
                    # Allow forward-compatible new keys from the API.
                    self._data[k] = v
            if persist:
                self._write_unlocked()
            return dict(self._data)

    def _write_unlocked(self):
        tmp = self._path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp, self._path)
