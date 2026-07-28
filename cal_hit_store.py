# Implements: SW-001 §6 — Calibration successful-hit gallery
"""
cal_hit_store.py — Keep last N successful auto-cal splash before/after stills.

Stores under cal_hits/<id>/{before.jpg,after.jpg,diff.jpg,meta.json}
and an index.json ring of the newest MAX_HITS entries.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from typing import Any, List, Optional

try:
    import cv2
    CV2 = True
except ImportError:
    CV2 = False

MAX_HITS = 10
DIR_NAME = "cal_hits"


class CalHitStore:
    def __init__(self, root_dir: str, max_hits: int = MAX_HITS):
        self.root = os.path.join(root_dir, DIR_NAME)
        self.max_hits = max_hits
        self._lock = threading.Lock()
        self._index_path = os.path.join(self.root, "index.json")
        os.makedirs(self.root, exist_ok=True)

    def _load_index(self) -> List[str]:
        if not os.path.isfile(self._index_path):
            return []
        try:
            data = json.load(open(self._index_path, "r"))
            if isinstance(data, dict):
                return list(data.get("hits") or [])
            if isinstance(data, list):
                return list(data)
        except Exception:
            pass
        return []

    def _save_index(self, hits: List[str]) -> None:
        tmp = self._index_path + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"hits": hits, "max": self.max_hits}, f, indent=2)
            f.write("\n")
        os.replace(tmp, self._index_path)

    def save(
        self,
        before_bgr,
        after_bgr,
        diff_bgr,
        meta: Optional[dict] = None,
    ) -> Optional[str]:
        """Persist one successful hit trio. Returns hit id or None."""
        if not CV2 or before_bgr is None or after_bgr is None:
            return None
        hid = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        folder = os.path.join(self.root, hid)
        try:
            os.makedirs(folder, exist_ok=True)
            cv2.imwrite(os.path.join(folder, "before.jpg"), before_bgr,
                        [cv2.IMWRITE_JPEG_QUALITY, 90])
            cv2.imwrite(os.path.join(folder, "after.jpg"), after_bgr,
                        [cv2.IMWRITE_JPEG_QUALITY, 90])
            if diff_bgr is not None:
                cv2.imwrite(os.path.join(folder, "diff.jpg"), diff_bgr,
                            [cv2.IMWRITE_JPEG_QUALITY, 90])
            else:
                cv2.imwrite(os.path.join(folder, "diff.jpg"), after_bgr,
                            [cv2.IMWRITE_JPEG_QUALITY, 90])
            payload = {
                "id": hid,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                **(meta or {}),
            }
            with open(os.path.join(folder, "meta.json"), "w") as f:
                json.dump(payload, f, indent=2)
                f.write("\n")
        except Exception as e:
            print(f"[CalHitStore] save failed: {e}")
            return None

        with self._lock:
            hits = self._load_index()
            hits.append(hid)
            while len(hits) > self.max_hits:
                old = hits.pop(0)
                self._purge(old)
            self._save_index(hits)
        return hid

    def _purge(self, hid: str) -> None:
        folder = os.path.join(self.root, hid)
        if not os.path.isdir(folder):
            return
        for name in ("before.jpg", "after.jpg", "diff.jpg", "meta.json"):
            try:
                os.remove(os.path.join(folder, name))
            except OSError:
                pass
        try:
            os.rmdir(folder)
        except OSError:
            pass

    def list_hits(self) -> List[dict[str, Any]]:
        """Newest-first list of hit metas (max MAX_HITS)."""
        with self._lock:
            ids = list(reversed(self._load_index()))
        out = []
        for hid in ids:
            meta_path = os.path.join(self.root, hid, "meta.json")
            entry = {"id": hid}
            if os.path.isfile(meta_path):
                try:
                    entry.update(json.load(open(meta_path, "r")))
                except Exception:
                    pass
            entry["urls"] = {
                "before": f"/api/calibration/hits/{hid}/before.jpg",
                "after": f"/api/calibration/hits/{hid}/after.jpg",
                "diff": f"/api/calibration/hits/{hid}/diff.jpg",
            }
            out.append(entry)
        return out

    def file_path(self, hid: str, kind: str) -> Optional[str]:
        if kind not in ("before", "after", "diff"):
            return None
        # prevent path traversal
        if "/" in hid or "\\" in hid or ".." in hid:
            return None
        path = os.path.join(self.root, hid, f"{kind}.jpg")
        return path if os.path.isfile(path) else None
