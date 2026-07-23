# Implements: SW-001 §2.11
"""
settings_store.py — Central persistent settings (settings.json).

- Grouped schema for all GUI tunables
- On every permanent save: rotate a copy into settings_backups/ (keep last 30)
- Load order: settings.json → latest backup → factory defaults
- Migrates legacy flat target_psi, scout_config.json, calibration_visual.json
"""

from __future__ import annotations

import glob
import json
import os
import shutil
import threading
from datetime import datetime
from typing import Any


MAX_BACKUPS = 30

# Factory defaults when no settings.json and no backups exist.
DEFAULTS: dict[str, Any] = {
    "accumulator": {
        "target_psi": 5.0,
        "maintain_hysteresis_psi": 0.0,
        "pressure_poll_sec": 60.0,
        "initial_charge_sec": 3.0,
        "topup_charge_sec": 1.0,
        "topup_interval_shots": 10,
        "default_pulse_ms": 100.0,  # shared live+auto-cal; 25ms is often inaudible
        "max_pump_run_sec": 8.0,
        "charge_per_shot": True,
        # Yahboom PY.00 cannot reliably close Monk Makes CH2 — jumper CH2 load
        # (or hardwire fused 12V to module DC IN+) and keep this True.
        "module_12v_hardwired": False,
    },
    "servo": {
        "speed": 120.0,
        "rate_hz": 100,
        "nudge_step": 2.0,
        "yaw_limit": 80.0,
        "pitch_limit": 90.0,
    },
    "pulse": {
        "operational_pulse": 0.100,  # mirrors accumulator.default_pulse_ms
        "cal_pulse": 0.100,
        "cal_retry_pulse": 0.100,
        "prime_duration_ms": 3000,
    },
    "prime": {
        "prime_duration_ms": 3000,
        "auto_detect": True,
    },
    "stabilize": {
        "pre_pressurize": False,
        "stabilize_ms": 50,
        "settle_ms": 80,
    },
    "calibration": {
        "offset_pitch": 0.0,
        "offset_yaw": 0.0,
        "last_updated": "",
        "points": [],
    },
    "scout": {
        "history": 500,
        "threshold": 16,
        "min_area": 500,
        "detect_shadows": False,
    },
}


def deep_merge(base: dict, overlay: dict) -> dict:
    """Recursively merge overlay onto a copy of base (dicts only)."""
    out = dict(base)
    for key, val in overlay.items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], val)
        else:
            out[key] = val
    return out


def _read_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: root must be a JSON object")
    return data


class SettingsStore:
    """Thread-safe load/merge/save for project-root settings.json + backups."""

    def __init__(self, path: str, project_dir: str | None = None):
        self._path = path
        self._dir = project_dir or os.path.dirname(os.path.abspath(path))
        self._backup_dir = os.path.join(self._dir, "settings_backups")
        self._lock = threading.Lock()
        self._data: dict[str, Any] = {}
        self.load()

    @property
    def path(self) -> str:
        return self._path

    @property
    def backup_dir(self) -> str:
        return self._backup_dir

    def load(self) -> dict[str, Any]:
        """Load settings.json, else latest backup, else defaults (+ legacy migrate)."""
        with self._lock:
            loaded = None
            source = None

            if os.path.isfile(self._path):
                try:
                    loaded = _read_json(self._path)
                    source = self._path
                except Exception as e:
                    print(f"[SettingsStore] settings.json unreadable ({e}); trying backup")

            if loaded is None:
                backup = self._latest_backup_unlocked()
                if backup:
                    try:
                        loaded = _read_json(backup)
                        source = backup
                        print(f"[SettingsStore] Restored from backup: {backup}")
                    except Exception as e:
                        print(f"[SettingsStore] Backup unreadable ({e})")

            if loaded is None:
                loaded = {}
                source = "defaults"
                print("[SettingsStore] No settings/backups — using factory defaults")

            loaded = self._migrate_legacy_unlocked(loaded)
            self._data = deep_merge(DEFAULTS, loaded)

            # Always ensure settings.json exists after load
            if source != self._path or not os.path.isfile(self._path):
                self._write_unlocked(backup=False)
            elif self._needs_default_keys(loaded):
                self._write_unlocked(backup=False)

            print(f"[SettingsStore] Active settings from {source}")
            return dict(self._data)

    def get(self) -> dict[str, Any]:
        with self._lock:
            return json.loads(json.dumps(self._data))  # deep copy

    def section(self, name: str) -> dict[str, Any]:
        with self._lock:
            return dict(self._data.get(name, DEFAULTS.get(name, {})))

    def update(self, patch: dict[str, Any], persist: bool = True) -> dict[str, Any]:
        """
        Deep-merge patch into settings.
        persist=True: rotate backup (if file exists) then write settings.json.
        persist=False: memory only (runtime staging — rarely used; Apply uses hardware APIs).
        """
        with self._lock:
            self._data = deep_merge(self._data, patch)
            if persist:
                self._write_unlocked(backup=True)
            return json.loads(json.dumps(self._data))

    def replace(self, data: dict[str, Any], persist: bool = True) -> dict[str, Any]:
        """Replace full tree (merged with DEFAULTS so keys are never lost)."""
        with self._lock:
            self._data = deep_merge(DEFAULTS, data)
            if persist:
                self._write_unlocked(backup=True)
            return json.loads(json.dumps(self._data))

    def list_backups(self) -> list[str]:
        with self._lock:
            return self._list_backups_unlocked()

    # -- internals -----------------------------------------------------------

    def _needs_default_keys(self, loaded: dict) -> bool:
        for key in DEFAULTS:
            if key not in loaded:
                return True
        return False

    def _migrate_legacy_unlocked(self, loaded: dict) -> dict:
        """Normalize flat target_psi and import old sidecar files once."""
        out = dict(loaded)

        # Flat v1: {"target_psi": 5.0}
        if "target_psi" in out and "accumulator" not in out:
            out["accumulator"] = {"target_psi": out.pop("target_psi")}
        elif "target_psi" in out:
            acc = dict(out.get("accumulator") or {})
            acc.setdefault("target_psi", out.pop("target_psi"))
            out["accumulator"] = acc
            out.pop("target_psi", None)

        # SW-001 §2.7 (2026-07-20): no hysteresis; ensure poll interval key exists
        acc = dict(out.get("accumulator") or {})
        if acc:
            acc.setdefault("pressure_poll_sec", DEFAULTS["accumulator"]["pressure_poll_sec"])
            # Old factory was 1.0 PSI hysteresis — new contract is 0
            if acc.get("maintain_hysteresis_psi", 0) == 1.0:
                acc["maintain_hysteresis_psi"] = 0.0
            # 10/25ms pulses were inaudible and hard to verify during auto-cal
            if float(acc.get("default_pulse_ms", 100)) <= 25.0:
                acc["default_pulse_ms"] = 100.0
            acc.setdefault(
                "module_12v_hardwired",
                DEFAULTS["accumulator"]["module_12v_hardwired"],
            )
            out["accumulator"] = acc
            pulse = dict(out.get("pulse") or {})
            pulse["operational_pulse"] = float(acc["default_pulse_ms"]) / 1000.0
            out["pulse"] = pulse

        # Import scout_config.json if scout section missing/empty-ish
        scout_path = os.path.join(self._dir, "scout_config.json")
        if "scout" not in out and os.path.isfile(scout_path):
            try:
                out["scout"] = _read_json(scout_path)
                print(f"[SettingsStore] Migrated scout_config.json → settings.scout")
            except Exception as e:
                print(f"[SettingsStore] scout_config migrate skip: {e}")

        # Import calibration_visual.json offsets/points if calibration missing
        cal_path = os.path.join(self._dir, "calibration_visual.json")
        if "calibration" not in out and os.path.isfile(cal_path):
            try:
                cal = _read_json(cal_path)
                out["calibration"] = {
                    "offset_pitch": cal.get("offset_pitch", 0.0),
                    "offset_yaw": cal.get("offset_yaw", 0.0),
                    "last_updated": cal.get("last_updated", ""),
                    "points": cal.get("points", []),
                }
                print("[SettingsStore] Migrated calibration_visual.json → settings.calibration")
            except Exception as e:
                print(f"[SettingsStore] calibration migrate skip: {e}")

        return out

    def _list_backups_unlocked(self) -> list[str]:
        if not os.path.isdir(self._backup_dir):
            return []
        files = sorted(glob.glob(os.path.join(self._backup_dir, "settings_*.json")))
        return files

    def _latest_backup_unlocked(self) -> str | None:
        files = self._list_backups_unlocked()
        return files[-1] if files else None

    def _rotate_backup_unlocked(self):
        if not os.path.isfile(self._path):
            return
        os.makedirs(self._backup_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        dest = os.path.join(self._backup_dir, f"settings_{stamp}.json")
        shutil.copy2(self._path, dest)
        files = self._list_backups_unlocked()
        while len(files) > MAX_BACKUPS:
            old = files.pop(0)
            try:
                os.remove(old)
            except OSError:
                pass

    def _write_unlocked(self, backup: bool = True):
        if backup and os.path.isfile(self._path):
            self._rotate_backup_unlocked()
        tmp = self._path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp, self._path)
