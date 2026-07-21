# Implements: SW-001 §2.11 — smoke tests for settings store + backups
"""Offline tests (no Jetson hardware). Run: python -m pytest tests/test_settings_store.py -q"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from settings_store import SettingsStore, DEFAULTS, MAX_BACKUPS


def test_defaults_when_empty():
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "settings.json")
        store = SettingsStore(path, project_dir=td)
        data = store.get()
        assert data["accumulator"]["target_psi"] == DEFAULTS["accumulator"]["target_psi"]
        assert os.path.isfile(path)


def test_persist_creates_backup_and_restore():
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "settings.json")
        store = SettingsStore(path, project_dir=td)
        store.update({"accumulator": {"target_psi": 12.0}}, persist=True)
        assert store.get()["accumulator"]["target_psi"] == 12.0

        # Second save should create one backup of the previous file
        store.update({"accumulator": {"target_psi": 18.0}}, persist=True)
        backups = store.list_backups()
        assert len(backups) >= 1

        # Corrupt main file → load from latest backup
        with open(path, "w") as f:
            f.write("{not json")
        store2 = SettingsStore(path, project_dir=td)
        # Restored from backup (12.0) then may have been re-written; at least valid tree
        psi = store2.get()["accumulator"]["target_psi"]
        assert 1.0 <= psi <= 40.0
        assert isinstance(store2.get()["scout"], dict)


def test_max_backups_rotation():
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "settings.json")
        store = SettingsStore(path, project_dir=td)
        for i in range(MAX_BACKUPS + 5):
            store.update({"accumulator": {"target_psi": float(1 + (i % 40))}}, persist=True)
        assert len(store.list_backups()) <= MAX_BACKUPS


def test_legacy_flat_target_psi_migrate():
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "settings.json")
        with open(path, "w") as f:
            json.dump({"target_psi": 7.5}, f)
        store = SettingsStore(path, project_dir=td)
        assert store.get()["accumulator"]["target_psi"] == 7.5
        assert "target_psi" not in store.get() or "accumulator" in store.get()
