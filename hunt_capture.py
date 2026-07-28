# Implements: SW-001 §2.14 — Hunt attempt stills + trajectory strip
"""
hunt_capture.py — Scout/Sniper stills for hunt attempts.

Retention (dual ring):
  - last MAX_RECENT (10) of *any* attempt (reject or fire)
  - last MAX_INSECT (100) of YOLO insect detections

Trajectory: stills contact-sheet from Sniper burst during fire (no MP4).
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
    import numpy as np
    CV2 = True
except ImportError:
    CV2 = False

MAX_RECENT = 10
MAX_INSECT = 100
AFTER_DELAY_SEC = 0.35
JPEG_QUALITY = 80
STILL_MAX_W = 640
TRAJ_CELL_W = 160
TRAJ_MAX_FRAMES = 12


def annotate_frame(
    frame,
    *,
    label: str,
    point: Optional[Tuple[int, int]] = None,
    crosshair: bool = False,
    boxes: Optional[list] = None,
    hit_px=None,
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
    if hit_px is not None:
        hx, hy = int(hit_px[0] * sx), int(hit_px[1] * sy)
        cv2.circle(out, (hx, hy), 16, (0, 0, 255), 2)
        cv2.drawMarker(out, (hx, hy), (0, 0, 255), cv2.MARKER_TILTED_CROSS, 28, 2)
    cv2.rectangle(out, (0, 0), (w, 28), (0, 0, 0), -1)
    cv2.putText(out, label[:70], (6, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1)
    return out


def _resize(frame, max_w=STILL_MAX_W):
    if frame is None or not CV2:
        return frame
    h, w = frame.shape[:2]
    if w <= max_w:
        return frame
    nh = int(h * (max_w / float(w)))
    return cv2.resize(frame, (max_w, nh))


def build_trajectory_strip(
    frames: list,
    *,
    boxes: Optional[list] = None,
    hit_px=None,
    label: str = "TRAJECTORY",
):
    """Horizontal contact sheet of Sniper burst frames (water path)."""
    if not CV2 or not frames:
        return None
    cells = []
    n = min(len(frames), TRAJ_MAX_FRAMES)
    step = max(1, len(frames) // n) if len(frames) > n else 1
    picked = frames[::step][:n]
    for i, fr in enumerate(picked):
        img = _resize(fr, TRAJ_CELL_W)
        img = annotate_frame(
            img,
            label=f"{i + 1}/{len(picked)}",
            crosshair=True,
            boxes=boxes if i == 0 or i == len(picked) - 1 else None,
            hit_px=hit_px if i == len(picked) - 1 else None,
            color=(0, 255, 255),
        )
        cells.append(img)
    if not cells:
        return None
    h = max(c.shape[0] for c in cells)
    padded = []
    for c in cells:
        if c.shape[0] < h:
            pad = np.zeros((h - c.shape[0], c.shape[1], 3), dtype=c.dtype)
            c = np.vstack([c, pad])
        padded.append(c)
    strip = np.hstack(padded)
    cv2.rectangle(strip, (0, 0), (strip.shape[1], 22), (0, 0, 0), -1)
    cv2.putText(strip, label[:90], (4, 16),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
    return strip


class HuntCaptureStore:
    """Dual ring: recent (any) + insects (YOLO-verified)."""

    def __init__(self, root_dir: str):
        self.root = root_dir
        self._lock = threading.Lock()
        self._recent: List[str] = []
        self._insects: List[str] = []
        self._last_capture_mono = 0.0
        os.makedirs(self.root, exist_ok=True)
        self._load_index()

    def tick(self, scout_frame, sniper_frame) -> None:
        return

    def count(self) -> int:
        with self._lock:
            return len(set(self._recent) | set(self._insects))

    def counts(self) -> dict:
        with self._lock:
            return {
                "recent": len(self._recent),
                "insects": len(self._insects),
                "max_recent": MAX_RECENT,
                "max_insects": MAX_INSECT,
                "total": len(set(self._recent) | set(self._insects)),
            }

    def clear_all(self) -> int:
        with self._lock:
            ids = set(self._recent) | set(self._insects)
            n = len(ids)
            for aid in ids:
                shutil.rmtree(os.path.join(self.root, aid), ignore_errors=True)
            for name in os.listdir(self.root):
                path = os.path.join(self.root, name)
                if os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
            self._recent, self._insects = [], []
            self._save_index()
            return n

    def _index_path(self) -> str:
        return os.path.join(self.root, "index.json")

    def _load_index(self):
        path = self._index_path()
        recent, insects = [], []
        if os.path.isfile(path):
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    recent = data
                else:
                    recent = data.get("recent") or data.get("ids") or []
                    insects = data.get("insects") or []
            except Exception:
                pass
        else:
            recent = sorted(
                [d for d in os.listdir(self.root)
                 if os.path.isdir(os.path.join(self.root, d))],
                reverse=True,
            )
        self._recent = [i for i in recent
                        if os.path.isdir(os.path.join(self.root, i))]
        self._insects = [i for i in insects
                         if os.path.isdir(os.path.join(self.root, i))]
        self._prune_locked()
        self._save_index()

    def _save_index(self):
        with open(self._index_path(), "w") as f:
            json.dump({
                "recent": self._recent,
                "insects": self._insects,
                "max_recent": MAX_RECENT,
                "max_insects": MAX_INSECT,
            }, f, indent=2)

    def list_attempts(self, limit: int = MAX_RECENT,
                      view: str = "recent") -> list:
        with self._lock:
            ids = list(self._insects if view == "insects" else self._recent)
        ids = ids[:max(1, int(limit))]
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
        cooldown_sec: float = 3.0,
        hit_confirmed=None,
        hit_px=None,
        insect_detected: bool = False,
        trajectory_frames: Optional[list] = None,
        hit_verdict=None,
    ) -> Optional[str]:
        # Insect detections always saved; others respect cooldown.
        if not insect_detected and not self.can_capture(cooldown_sec):
            return None

        attempt_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        scout_before = scout_cam.get_frame() if scout_cam else None
        sniper_before = sniper_cam.get_frame() if sniper_cam else None
        if scout_before is not None:
            scout_before = scout_before.copy()
        if sniper_before is not None:
            sniper_before = sniper_before.copy()
        traj = []
        if trajectory_frames:
            traj = [f.copy() for f in trajectory_frames if f is not None]

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
            "media": "stills_traj" if traj else "stills_only",
            "insect_detected": bool(insect_detected),
            "hit_confirmed": hit_confirmed,
            "hit_px": hit_px,
            "hit_verdict": hit_verdict,
            "traj_frames": len(traj),
        }
        with open(os.path.join(dest, "meta.json"), "w") as f:
            json.dump(meta, f, indent=2)

        self._last_capture_mono = time.monotonic()
        with self._lock:
            self._recent.insert(0, attempt_id)
            if insect_detected:
                self._insects.insert(0, attempt_id)
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
                insect_detected=insect_detected,
                trajectory_frames=traj,
                hit_verdict=hit_verdict,
            ),
            daemon=True,
            name=f"hunt-cap-{attempt_id[-6:]}",
        ).start()
        return attempt_id

    def _prune_locked(self):
        while len(self._recent) > MAX_RECENT:
            old = self._recent.pop()
            if old not in self._insects:
                shutil.rmtree(os.path.join(self.root, old), ignore_errors=True)
                print(f"[HuntCapture] pruned recent {old}")
        while len(self._insects) > MAX_INSECT:
            old = self._insects.pop()
            if old not in self._recent:
                shutil.rmtree(os.path.join(self.root, old), ignore_errors=True)
                print(f"[HuntCapture] pruned insect {old}")

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
        insect_detected=False,
        trajectory_frames=None,
        hit_verdict=None,
    ):
        dest = os.path.join(self.root, attempt_id)
        color = (0, 220, 0) if result == "fired" else (0, 165, 255)
        hit_txt = ""
        if hit_confirmed is True:
            hit_txt, color = " | HIT", (0, 255, 0)
        elif hit_confirmed is False:
            hit_txt = " | MISS"
        if hit_verdict and hit_verdict.get("label"):
            hit_txt = f" | {hit_verdict['label']} {hit_verdict.get('score', '?')}/{hit_verdict.get('max_score', 3)}"
            if hit_verdict.get("label") == "HIT":
                color = (0, 255, 0)
            elif hit_verdict.get("label") == "PROBABLE":
                color = (0, 200, 255)
            else:
                hit_txt = f" | {hit_verdict['label']} {hit_verdict.get('score', '?')}/{hit_verdict.get('max_score', 3)}"
        insect_txt = " | INSECT" if insect_detected else ""
        label = (f"{result.upper()}{hit_txt}{insect_txt} | {verify} | "
                 f"p={aim_pitch:.1f} y={aim_yaw:.1f}")
        point = tuple(target_px) if target_px else None

        time.sleep(AFTER_DELAY_SEC)
        scout_after = sniper_after = None
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
                    img, label=label,
                    point=None if sniper else point,
                    crosshair=sniper,
                    boxes=boxes if sniper else None,
                    hit_px=hit_px if sniper else None,
                    color=color,
                )
            cv2.imwrite(os.path.join(dest, name), img,
                        [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])

        _jpg("scout_before.jpg", scout_before)
        _jpg("scout_after.jpg", scout_after)
        _jpg("sniper_before.jpg", sniper_before)
        _jpg("sniper_after.jpg", sniper_after)
        _jpg("scout_before_ann.jpg", scout_before, ann=True)
        _jpg("scout_after_ann.jpg", scout_after, ann=True)
        _jpg("sniper_before_ann.jpg", sniper_before, ann=True, sniper=True)
        _jpg("sniper_after_ann.jpg", sniper_after, ann=True, sniper=True)

        if trajectory_frames and CV2:
            strip = build_trajectory_strip(
                trajectory_frames, boxes=boxes, hit_px=hit_px,
                label=f"WATER PATH{hit_txt} | {verify}",
            )
            if strip is not None:
                cv2.imwrite(
                    os.path.join(dest, "trajectory.jpg"),
                    strip,
                    [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY],
                )

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
            "media": "stills_traj" if trajectory_frames else "stills_only",
            "insect_detected": bool(insect_detected),
            "hit_confirmed": hit_confirmed,
            "hit_px": list(hit_px) if hit_px else None,
            "hit_verdict": hit_verdict,
            "traj_frames": len(trajectory_frames or []),
            "has_trajectory": bool(trajectory_frames),
        }
        with open(os.path.join(dest, "meta.json"), "w") as f:
            json.dump(meta, f, indent=2)
        print(f"[HuntCapture] saved {attempt_id} ({result}, insect={insect_detected}, "
              f"hit={hit_confirmed}, verdict={((hit_verdict or {}).get('summary'))}, "
              f"traj={len(trajectory_frames or [])})")
