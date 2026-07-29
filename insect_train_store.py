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
META_CSV = "metadata.csv"
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
        self._append_metadata_csv(payload)
        with self._lock:
            ids = self._load_index()
            if sid in ids:
                ids.remove(sid)
            ids.insert(0, sid)
            ids = self._prune(ids)
            self._save_index(ids)
        return sid

    def _append_metadata_csv(self, meta: dict) -> None:
        """Insect Detect–style rolling metadata for active learning / offline classify."""
        import csv
        path = os.path.join(self.root, META_CSV)
        fields = [
            "id", "timestamp", "lighting", "distance_m", "label", "confidence",
            "predicted_class", "true_class", "verified", "verify",
            "x_min", "y_min", "x_max", "y_max", "file_path", "crop_path",
            "water_fired", "note",
        ]
        bbox = None
        boxes = meta.get("boxes") or []
        if boxes:
            top = max(boxes, key=lambda b: float(b.get("confidence") or 0))
            bbox = top.get("bbox")
        row = {
            "id": meta.get("id"),
            "timestamp": meta.get("timestamp"),
            "lighting": meta.get("lighting"),
            "distance_m": meta.get("distance_m"),
            "label": meta.get("predicted_class") or "insect",
            "confidence": meta.get("predicted_confidence"),
            "predicted_class": meta.get("predicted_class"),
            "true_class": meta.get("true_class"),
            "verified": meta.get("verified"),
            "verify": meta.get("verify"),
            "x_min": bbox[0] if bbox else "",
            "y_min": bbox[1] if bbox else "",
            "x_max": bbox[2] if bbox else "",
            "y_max": bbox[3] if bbox else "",
            "file_path": f"{meta.get('id')}/sniper.jpg",
            "crop_path": f"{meta.get('id')}/crop.jpg",
            "water_fired": False,
            "note": meta.get("note") or "",
        }
        write_header = not os.path.isfile(path)
        with open(path, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            if write_header:
                w.writeheader()
            w.writerow(row)

    def export_active_learning(self) -> dict:
        """
        Sort crops into export/{class}/ for Roboflow/Colab retrain
        (Insect Detect active-learning loop).
        """
        import shutil
        export_root = os.path.join(self.root, "export")
        os.makedirs(export_root, exist_ok=True)
        counts: Dict[str, int] = {}
        with self._lock:
            ids = self._load_index()
        for sid in ids:
            meta_path = os.path.join(self.root, sid, "meta.json")
            crop = os.path.join(self.root, sid, "crop.jpg")
            sniper = os.path.join(self.root, sid, "sniper.jpg")
            src = crop if os.path.isfile(crop) else sniper
            if not os.path.isfile(src):
                continue
            meta = {}
            if os.path.isfile(meta_path):
                try:
                    meta = json.load(open(meta_path, "r"))
                except Exception:
                    meta = {}
            cls = (meta.get("true_class") or meta.get("predicted_class") or "unlabeled")
            cls = str(cls).lower().strip() or "unlabeled"
            if meta.get("insect_present") is False or cls in ("none",):
                cls = "empty"
            dest_dir = os.path.join(export_root, cls)
            os.makedirs(dest_dir, exist_ok=True)
            dest = os.path.join(dest_dir, f"{sid}.jpg")
            try:
                shutil.copy2(src, dest)
                counts[cls] = counts.get(cls, 0) + 1
            except OSError:
                pass
        return {"ok": True, "export_dir": export_root, "counts": counts}

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
                "crop": f"/api/train/samples/{sid}/crop.jpg",
            }
            out.append(entry)
        return out

    def file_path(self, sid: str, kind: str) -> Optional[str]:
        if kind not in ("sniper", "scout", "crop"):
            return None
        if "/" in sid or "\\" in sid or ".." in sid:
            return None
        path = os.path.join(self.root, sid, f"{kind}.jpg")
        return path if os.path.isfile(path) else None

    def counts(self) -> dict:
        with self._lock:
            n = len(self._load_index())
        return {"samples": n, "max": MAX_SAMPLES}
