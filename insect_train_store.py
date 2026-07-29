# Implements: SW-001 §2.16 — Insect Training Mode (indoor dry-fire samples)
"""
insect_train_store.py — Persist indoor insect viewing/ID samples (no water).

Stores under insect_train/<id>/{sniper.jpg,scout.jpg,meta.json}.
Real camera frames only — never invents imagery.
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, List, Optional

import cv2

from timeutil import stamp_file, stamp_iso

DIR_NAME = "insect_train"
MAX_SAMPLES = 200
INSECT_CLASS_CHOICES = [
    "mosquito", "fly", "bee", "wasp", "moth", "butterfly", "ladybug",
    "beetle", "ant", "spider", "dragonfly", "grasshopper", "caterpillar",
    "centipede", "other", "unknown", "none",
]


class InsectTrainStore:
    def __init__(self, root_dir: str):
        self.root = os.path.join(root_dir, DIR_NAME)
        os.makedirs(self.root, exist_ok=True)
        self._lock = threading.Lock()
        self._index_path = os.path.join(self.root, "index.json")

    def _load_index(self) -> List[str]:
        if not os.path.isfile(self._index_path):
            return []
        try:
            data = json.load(open(self._index_path, "r"))
            ids = data.get("ids") if isinstance(data, dict) else data
            return [str(i) for i in (ids or [])]
        except Exception:
            return []

    def _save_index(self, ids: List[str]) -> None:
        tmp = self._index_path + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"ids": ids[:MAX_SAMPLES]}, f, indent=2)
            f.write("\n")
        os.replace(tmp, self._index_path)

    def _prune(self, ids: List[str]) -> List[str]:
        while len(ids) > MAX_SAMPLES:
            old = ids.pop()
            folder = os.path.join(self.root, old)
            if os.path.isdir(folder):
                for name in os.listdir(folder):
                    try:
                        os.remove(os.path.join(folder, name))
                    except OSError:
                        pass
                try:
                    os.rmdir(folder)
                except OSError:
                    pass
        return ids

    def save_sample(
        self,
        *,
        sniper_bgr,
        scout_bgr=None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Write one training sample. Returns id or None."""
        if sniper_bgr is None:
            return None
        sid = stamp_file()
        folder = os.path.join(self.root, sid)
        os.makedirs(folder, exist_ok=True)
        ok, buf = cv2.imencode(".jpg", sniper_bgr, [cv2.IMWRITE_JPEG_QUALITY, 90])
        if not ok:
            return None
        open(os.path.join(folder, "sniper.jpg"), "wb").write(buf.tobytes())
        if scout_bgr is not None:
            ok2, buf2 = cv2.imencode(".jpg", scout_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if ok2:
                open(os.path.join(folder, "scout.jpg"), "wb").write(buf2.tobytes())
        payload = dict(meta or {})
        payload.update({
            "id": sid,
            "timestamp": stamp_iso(),
            "dry_fire": True,
            "water_fired": False,
        })
        with open(os.path.join(folder, "meta.json"), "w") as f:
            json.dump(payload, f, indent=2, default=str)
            f.write("\n")
        with self._lock:
            ids = self._load_index()
            if sid in ids:
                ids.remove(sid)
            ids.insert(0, sid)
            ids = self._prune(ids)
            self._save_index(ids)
        return sid

    def update_meta(self, sid: str, patch: Dict[str, Any]) -> Optional[dict]:
        if "/" in sid or "\\" in sid or ".." in sid:
            return None
        path = os.path.join(self.root, sid, "meta.json")
        if not os.path.isfile(path):
            return None
        try:
            meta = json.load(open(path, "r"))
        except Exception:
            meta = {"id": sid}
        meta.update(patch)
        meta["id"] = sid
        with open(path, "w") as f:
            json.dump(meta, f, indent=2, default=str)
            f.write("\n")
        return meta

    def list_samples(self, limit: int = 40) -> List[dict]:
        with self._lock:
            ids = self._load_index()[: max(1, min(int(limit or 40), MAX_SAMPLES))]
        out = []
        for sid in ids:
            meta_path = os.path.join(self.root, sid, "meta.json")
            entry: Dict[str, Any] = {"id": sid}
            if os.path.isfile(meta_path):
                try:
                    entry.update(json.load(open(meta_path, "r")))
                except Exception:
                    pass
            entry["urls"] = {
                "sniper": f"/api/train/samples/{sid}/sniper.jpg",
                "scout": f"/api/train/samples/{sid}/scout.jpg",
            }
            out.append(entry)
        return out

    def file_path(self, sid: str, kind: str) -> Optional[str]:
        if kind not in ("sniper", "scout"):
            return None
        if "/" in sid or "\\" in sid or ".." in sid:
            return None
        path = os.path.join(self.root, sid, f"{kind}.jpg")
        return path if os.path.isfile(path) else None

    def counts(self) -> dict:
        with self._lock:
            n = len(self._load_index())
        return {"samples": n, "max": MAX_SAMPLES}
