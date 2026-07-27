# Implements: SW-001 §2.14 — Hunt attempt stills (lightweight)
"""
hunt_capture.py — Scout/Sniper stills for hunt attempts.

Stills-only (no video encode) to protect Jetson CPU/RAM/MJPEG streams.
Keeps last MAX_ATTEMPTS dirs under hunt_captures/. Cooldown enforced by caller.
"""

from __future__ import annotations

import json
import os
import shutil
import threading
import time
from datetime import datetime
from typing import List, Optional, Tuple

try:
    import cv2
    CV2 = True
except ImportError:
    CV2 = False

MAX_ATTEMPTS = 5
AFTER_DELAY_SEC = 0.4  # single after still (no multi-second clip)
JPEG_QUALITY = 80
# Downscale stills for disk + browser bandwidth
STILL_MAX_W = 640


def annotate_frame(
    frame,
    *,
    label: str,
    point: Optional[Tuple[int, int]] = None,
    crosshair: bool = False,
    boxes: Optional[list] = None,
    color=(0, 255, 0),
):
    if frame is None or not CV2:
        return frame
    out = frame.copy()
    h, w = out.shape[:2]
    sx = w / 1280.0
    sy = h / 720.0
    if crosshair:
        cx, cy = w // 2, h // 2
        cv2.line(out, (cx, 0), (cx, h), color, 1)
        cv2.line(out, (0, cy), (w, cy), color, 1)
        cv2.circle(out, (cx, cy), 14, color, 2)
    if point is not None:
        px, py = int(point[0] * sx), int(point[1] * sy)
        cv2.circle(out, (px, py), 12, color, 2)
        cv2.drawMarker(out, (px, py), color, cv2.MARKER_CROSS, 20, 2)
    if boxes:
        for b in boxes:
            x1, y1, x2, y2 = b.get("bbox", (0, 0, 0, 0))
            x1, y1, x2, y2 = int(x1 * sx), int(y1 * sy), int(x2 * sx), int(y2 * sy)
            cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
            name = b.get("label") or b.get("class") or ""
            if name:
                cv2.putText(out, str(name), (x1, max(14, y1 - 4)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
    cv2.rectangle(out, (0, 0), (w, 28), (0, 0, 0), -1)
    cv2.putText(out, label[:70], (6, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1)
    return out


def _resize(frame):
    if frame is None or not CV2:
        return frame
    h, w = frame.shape[:2]
    if w <= STILL_MAX_W:
        return frame
    nh = int(h * (STILL_MAX_W / float(w)))
    return cv2.resize(frame, (STILL_MAX_W, nh))


class HuntCaptureStore:
    """Disk-backed ring of the last MAX_ATTEMPTS hunt attempts (stills only)."""

    def __init__(self, root_dir: str):
        self.root = root_dir
        self._lock = threading.Lock()
        self._index: List[str] = []
        self._last_capture_mono = 0.0
        os.makedirs(self.root, exist_ok=True)
        self._load_index()

    def tick(self, scout_frame, sniper_frame) -> None:
        """No-op: stills-only path snapshots at engage time (saves RAM)."""
        return

    def count(self) -> int:
        with self._lock:
            return len(self._index)

    def clear_all(self) -> int:
        """Delete every attempt dir + reset index. Returns removed count."""
        with self._lock:
            n = len(self._index)
            for aid in list(self._index):
                shutil.rmtree(os.path.join(self.root, aid), ignore_errors=True)
            # orphan dirs
            for name in os.listdir(self.root):
                path = os.path.join(self.root, name)
                if os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
            self._index = []
            self._save_index()
            return n

    def _index_path(self) -> str:
        return os.path.join(self.root, "index.json")

    def _load_index(self):
        path = self._index_path()
        if os.path.isfile(path):
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                ids = data if isinstance(data, list) else data.get("ids", [])
                self._index = [i for i in ids
                               if os.path.isdir(os.path.join(self.root, i))][:MAX_ATTEMPTS]
            except Exception:
                self._index = []
        else:
            dirs = sorted(
                [d for d in os.listdir(self.root)
                 if os.path.isdir(os.path.join(self.root, d))],
                reverse=True,
            )
            self._index = dirs[:MAX_ATTEMPTS]
        self._prune_locked()
        self._save_index()

    def _save_index(self):
        with open(self._index_path(), "w") as f:
            json.dump({"ids": self._index, "max": MAX_ATTEMPTS}, f, indent=2)

    def list_attempts(self, limit: int = MAX_ATTEMPTS) -> list:
        with self._lock:
            ids = list(self._index[:limit])
        out = []
        for aid in ids:
            meta = self.get_meta(aid)
            if meta:
                out.append(meta)
        return out

    def get_meta(self, attempt_id: str) -> Optional[dict]:
        path = os.path.join(self.root, attempt_id, "meta.json")
        if not os.path.isfile(path):
            return None
        try:
            with open(path, "r") as f:
                meta = json.load(f)
            meta["id"] = attempt_id
            base = f"/api/hunt/captures/{attempt_id}"
            files = {}
            d = os.path.join(self.root, attempt_id)
            for name in os.listdir(d):
                if name == "meta.json":
                    continue
                files[name] = f"{base}/{name}"
            meta["files"] = files
            return meta
        except Exception:
            return None

    def resolve_file(self, attempt_id: str, filename: str) -> Optional[str]:
        if ".." in attempt_id or ".." in filename or "/" in filename or "\\" in filename:
            return None
        path = os.path.join(self.root, attempt_id, filename)
        return path if os.path.isfile(path) else None

    def can_capture(self, cooldown_sec: float) -> bool:
        return (time.monotonic() - self._last_capture_mono) >= cooldown_sec

    def save_attempt_async(
        self,
        *,
        result: str,
        verify: str,
        target_px,
        aim_pitch: float,
        aim_yaw: float,
        distance_m: float,
        scout_cam,
        sniper_cam,
        boxes: Optional[list] = None,
        cooldown_sec: float = 8.0,
        hit_confirmed=None,
        hit_px=None,
    ) -> Optional[str]:
        """Snapshot before/after JPEGs on a daemon thread. No video."""
        if not self.can_capture(cooldown_sec):
            return None

        attempt_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        scout_before = scout_cam.get_frame() if scout_cam else None
        sniper_before = sniper_cam.get_frame() if sniper_cam else None
        if scout_before is not None:
            scout_before = scout_before.copy()
        if sniper_before is not None:
            sniper_before = sniper_before.copy()

        dest = os.path.join(self.root, attempt_id)
        os.makedirs(dest, exist_ok=True)
        meta = {
            "id": attempt_id,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "result": result,
            "verify": verify,
            "target_px": list(target_px) if target_px else None,
            "aim_pitch": round(float(aim_pitch), 2),
            "aim_yaw": round(float(aim_yaw), 2),
            "distance_m": round(float(distance_m), 2) if distance_m is not None else None,
            "status": "recording",
            "media": "stills_only",
            "hit_confirmed": hit_confirmed,
            "hit_px": hit_px,
        }
        with open(os.path.join(dest, "meta.json"), "w") as f:
            json.dump(meta, f, indent=2)

        self._last_capture_mono = time.monotonic()
        with self._lock:
            self._index.insert(0, attempt_id)
            self._prune_locked()
            self._save_index()

        threading.Thread(
            target=self._finalize,
            kwargs=dict(
                attempt_id=attempt_id,
                result=result,
                verify=verify,
                target_px=target_px,
                aim_pitch=aim_pitch,
                aim_yaw=aim_yaw,
                distance_m=distance_m,
                scout_before=scout_before,
                sniper_before=sniper_before,
                scout_cam=scout_cam,
                sniper_cam=sniper_cam,
                boxes=boxes or [],
                hit_confirmed=hit_confirmed,
                hit_px=hit_px,
            ),
            daemon=True,
            name=f"hunt-cap-{attempt_id[-6:]}",
        ).start()
        return attempt_id

    def _prune_locked(self):
        while len(self._index) > MAX_ATTEMPTS:
            old = self._index.pop()
            shutil.rmtree(os.path.join(self.root, old), ignore_errors=True)
            print(f"[HuntCapture] pruned {old}")

    def _finalize(
        self,
        *,
        attempt_id,
        result,
        verify,
        target_px,
        aim_pitch,
        aim_yaw,
        distance_m,
        scout_before,
        sniper_before,
        scout_cam,
        sniper_cam,
        boxes,
        hit_confirmed=None,
        hit_px=None,
    ):
        dest = os.path.join(self.root, attempt_id)
        color = (0, 220, 0) if result == "fired" else (0, 165, 255)
        hit_txt = ""
        if hit_confirmed is True:
            hit_txt = " | HIT"
            color = (0, 255, 0)
        elif hit_confirmed is False:
            hit_txt = " | MISS"
        label = f"{result.upper()}{hit_txt} | {verify} | p={aim_pitch:.1f} y={aim_yaw:.1f}"
        point = tuple(target_px) if target_px else None

        time.sleep(AFTER_DELAY_SEC)
        scout_after = None
        sniper_after = None
        if scout_cam is not None:
            f = scout_cam.get_frame()
            scout_after = f.copy() if f is not None else None
        if sniper_cam is not None:
            f = sniper_cam.get_frame()
            sniper_after = f.copy() if f is not None else None

        def _jpg(name, frame, ann=False, sniper=False):
            if frame is None or not CV2:
                return
            img = _resize(frame)
            if ann:
                img = annotate_frame(
                    img,
                    label=label,
                    point=None if sniper else point,
                    crosshair=sniper,
                    boxes=boxes if sniper else None,
                    color=color,
                )
            cv2.imwrite(
                os.path.join(dest, name),
                img,
                [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY],
            )

        _jpg("scout_before.jpg", scout_before)
        _jpg("scout_after.jpg", scout_after)
        _jpg("sniper_before.jpg", sniper_before)
        _jpg("sniper_after.jpg", sniper_after)
        _jpg("scout_before_ann.jpg", scout_before, ann=True)
        _jpg("scout_after_ann.jpg", scout_after, ann=True)
        _jpg("sniper_before_ann.jpg", sniper_before, ann=True, sniper=True)
        _jpg("sniper_after_ann.jpg", sniper_after, ann=True, sniper=True)

        meta = {
            "id": attempt_id,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "result": result,
            "verify": verify,
            "target_px": list(target_px) if target_px else None,
            "aim_pitch": round(float(aim_pitch), 2),
            "aim_yaw": round(float(aim_yaw), 2),
            "distance_m": round(float(distance_m), 2) if distance_m is not None else None,
            "status": "ready",
            "media": "stills_only",
            "hit_confirmed": hit_confirmed,
            "hit_px": hit_px,
        }
        with open(os.path.join(dest, "meta.json"), "w") as f:
            json.dump(meta, f, indent=2)
        print(f"[HuntCapture] saved {attempt_id} ({result}, hit={hit_confirmed})")
