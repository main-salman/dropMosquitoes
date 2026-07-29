# Implements: SW-001 §2.8 — Visual Calibration System
"""
calibration_engine.py — Camera-Nozzle Offset Calibration

Discovers and compensates for the physical offset between the Sniper camera
and the water nozzle so that "click here" in the feed means "water hits here".

Uses frame differencing to auto-detect where water actually lands, then builds
a correction table indexed by distance and angle.

Key classes:
  - CalibrationPoint: Single measurement (aim → fire → detect hit → compute offset)
  - CalibrationTable: Collection of points with interpolation + persistence
  - HitDetector: Frame differencing to find water splash location
  - CalibrationWizard: Step-by-step guided calibration state machine
"""

import json
import time
import math
import os
import threading
import numpy as np
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Tuple

from timeutil import stamp_full, stamp_hms

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


# ============================================================================
# CALIBRATION DATA STRUCTURES
# ============================================================================

@dataclass
class CalibrationPoint:
    """A single calibration measurement."""
    # What we aimed at
    aim_pitch: float          # Servo pitch angle we commanded
    aim_yaw: float            # Servo yaw angle we commanded
    aim_px: int = 0           # Pixel X where user clicked in sniper feed
    aim_py: int = 0           # Pixel Y where user clicked in sniper feed

    # Where water actually hit (detected or user-corrected)
    hit_px: int = 0           # Pixel X of detected water impact
    hit_py: int = 0           # Pixel Y of detected water impact
    hit_confirmed: bool = False  # True if user confirmed/corrected

    # Computed offset (error to correct)
    offset_pitch: float = 0.0    # Degrees to add to pitch to correct aim
    offset_yaw: float = 0.0      # Degrees to add to yaw to correct aim
    offset_px: int = 0           # Pixel error X (hit - aim)
    offset_py: int = 0           # Pixel error Y (hit - aim)

    # Context
    distance_m: float = 2.0      # LiDAR distance at time of measurement
    timestamp: str = ""          # When this measurement was taken
    note: str = ""               # User note

    def compute_offset(self, fov_h: float = 62.2, fov_v: float = 48.8,
                       frame_w: int = 1280, frame_h: int = 720):
        """Compute angular offset from pixel error."""
        self.offset_px = self.hit_px - self.aim_px
        self.offset_py = self.hit_py - self.aim_py
        # Convert pixel offset to angular offset
        deg_per_px_h = fov_h / frame_w
        deg_per_px_v = fov_v / frame_h
        self.offset_yaw = self.offset_px * deg_per_px_h
        self.offset_pitch = self.offset_py * deg_per_px_v


class CalibrationTable:
    """
    Collection of calibration points with global offset computation
    and JSON persistence.

    Rigid mount: per-point angular offsets must stay small. Wild ±20° “hits”
    from false blobs are rejected; global offset = median of inliers only.
    """

    # Max |offset| accepted for a single point (degrees).
    # True landing can sit well off crosshair until cal converges.
    MAX_POINT_OFFSET_DEG = 18.0
    # Inliers for median must lie within this of the provisional median
    INLIER_BAND_DEG = 7.0

    def __init__(self, filepath: str = "calibration.json", settings_store=None):
        self.filepath = filepath
        self._settings_store = settings_store  # SW-001 §2.11 — preferred persistence
        self.points: List[CalibrationPoint] = []
        self.offset_pitch: float = 0.0   # Global pitch correction (degrees)
        self.offset_yaw: float = 0.0     # Global yaw correction (degrees)
        self.last_updated: str = ""

    def add_point(self, point: CalibrationPoint) -> bool:
        """
        Add a calibration measurement if geometric offset is plausible.
        Returns False if rejected as an outlier / false splash localization.
        """
        if not point.timestamp:
            point.timestamp = stamp_full()
        if (abs(point.offset_pitch) > self.MAX_POINT_OFFSET_DEG
                or abs(point.offset_yaw) > self.MAX_POINT_OFFSET_DEG):
            print(f"[Calibration] REJECT point — offset too large for rigid mount "
                  f"P={point.offset_pitch:.1f}° Y={point.offset_yaw:.1f}° "
                  f"(max ±{self.MAX_POINT_OFFSET_DEG}°)")
            return False
        self.points.append(point)
        self._recompute_offset()
        return True

    def _recompute_offset(self):
        """Median of inliers within INLIER_BAND of provisional median."""
        confirmed = [p for p in self.points if p.hit_confirmed]
        if not confirmed:
            return
        pitches = sorted(p.offset_pitch for p in confirmed)
        yaws = sorted(p.offset_yaw for p in confirmed)

        def _med(vals):
            m = len(vals) // 2
            if len(vals) % 2:
                return vals[m]
            return 0.5 * (vals[m - 1] + vals[m])

        med_p, med_y = _med(pitches), _med(yaws)
        inliers = [
            p for p in confirmed
            if abs(p.offset_pitch - med_p) <= self.INLIER_BAND_DEG
            and abs(p.offset_yaw - med_y) <= self.INLIER_BAND_DEG
        ]
        if len(inliers) < max(1, len(confirmed) // 2):
            # Fall back to all confirmed if band too tight
            inliers = confirmed
        pitches = sorted(p.offset_pitch for p in inliers)
        yaws = sorted(p.offset_yaw for p in inliers)
        self.offset_pitch = _med(pitches)
        self.offset_yaw = _med(yaws)
        # Clamp global offset to rigid-mount envelope
        self.offset_pitch = max(-self.MAX_POINT_OFFSET_DEG,
                                min(self.MAX_POINT_OFFSET_DEG, self.offset_pitch))
        self.offset_yaw = max(-self.MAX_POINT_OFFSET_DEG,
                              min(self.MAX_POINT_OFFSET_DEG, self.offset_yaw))
        self.last_updated = stamp_full()
        print(f"[Calibration] Global offset (inlier median): "
              f"pitch={self.offset_pitch:.2f}° yaw={self.offset_yaw:.2f}° "
              f"({len(inliers)}/{len(confirmed)} inliers)")

    def get_correction(self, distance_m: float = 2.0,
                       pitch: float = 0.0, yaw: float = 0.0) -> Tuple[float, float]:
        """
        Get the pitch/yaw correction for a given aim point.

        Currently returns the global average offset. Future: interpolate
        by distance and angle for per-region corrections.

        Returns:
            (d_pitch, d_yaw) — degrees to ADD to the raw aim angles.
        """
        if not self.points:
            return 0.0, 0.0

        # For now, use global offset (average of all confirmed points)
        # TODO: Distance-weighted interpolation for multi-distance accuracy
        return self.offset_pitch, self.offset_yaw

    def clear(self):
        """Reset all calibration data."""
        self.points.clear()
        self.offset_pitch = 0.0
        self.offset_yaw = 0.0
        self.last_updated = ""

    def save(self):
        """Persist calibration data to settings.json (preferred) and legacy file."""
        data = {
            "offset_pitch": self.offset_pitch,
            "offset_yaw": self.offset_yaw,
            "last_updated": self.last_updated,
            "points": [asdict(p) for p in self.points],
        }
        if self._settings_store is not None:
            self._settings_store.update({"calibration": data}, persist=True)
            print(f"[Calibration] Saved {len(self.points)} points to settings.json")
        try:
            with open(self.filepath, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[Calibration] Legacy file write skip: {e}")

    def load(self) -> bool:
        """Load from settings.json calibration section, else legacy filepath."""
        data = None
        if self._settings_store is not None:
            try:
                sec = self._settings_store.section("calibration")
                if sec and (sec.get("offset_pitch") is not None or sec.get("points")):
                    data = sec
            except Exception as e:
                print(f"[Calibration] settings load skip: {e}")
        if data is None and os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r') as f:
                    data = json.load(f)
            except Exception as e:
                print(f"[Calibration] Load error: {e}")
                return False
        if not data:
            return False
        try:
            self.offset_pitch = data.get("offset_pitch", 0.0)
            self.offset_yaw = data.get("offset_yaw", 0.0)
            self.last_updated = data.get("last_updated", "")
            self.points = [CalibrationPoint(**p) for p in data.get("points", [])]
            print(f"[Calibration] Loaded {len(self.points)} points. "
                  f"Offset: pitch={self.offset_pitch:.2f}° yaw={self.offset_yaw:.2f}°")
            return True
        except Exception as e:
            print(f"[Calibration] Load error: {e}")
            return False

    def to_dict(self) -> dict:
        """Return calibration state as a dict for the API."""
        return {
            "offset_pitch": round(self.offset_pitch, 3),
            "offset_yaw": round(self.offset_yaw, 3),
            "last_updated": self.last_updated,
            "point_count": len(self.points),
            "confirmed_count": sum(1 for p in self.points if p.hit_confirmed),
            "points": [asdict(p) for p in self.points[-10:]],  # Last 10 for UI
        }


# ============================================================================
# HIT DETECTION — Frame Differencing
# ============================================================================

class HitDetector:
    """
    Localize where water lands in the Sniper feed — same evidence a human sees.

    Humans spot the landing by watching motion over time. Single before/after
    stills often peak on AE/shadow while the real landing is a subtler transient.
    v5.18:
      - dense post-fire frame burst (use camera rate, not 5 sparse samples)
      - score temporal onset + brief persistence (wet appears then may fade)
      - soft expected-impact prior: a bit right of aim + gravity drop vs range
      - still refuse foliage-wind / unstable AE
    """

    DIFF_THRESHOLD = 20
    DARKEN_THRESHOLD = 18
    MIN_CONTOUR_AREA = 120
    MAX_CONTOUR_AREA = 10000
    BLUR_KERNEL = 5
    MIN_CIRCULARITY = 0.12
    # With a burst, wet need only appear in a few frames (not most)
    MIN_VOTE_FRAC = 0.18
    MIN_VOTES_ABS = 3
    MAX_AIM_DIST_FRAC = 0.32
    MIN_MEAN_DARKEN = 14.0
    MIN_CONTRAST = 10.0
    MIN_SCORE = 10.0
    MAX_NOISE_FLOOR_PCT = 3.5
    MAX_PERSISTENT_ROI_PCT = 12.0
    RING_PX = 28
    EDGE_MARGIN_PX = 80
    TOP_EXCLUDE_FRAC = 0.22
    FOLIAGE_G_MARGIN = 14.0
    # Operator: landing is always a bit right of aim; farther → lower (gravity)
    RIGHT_BIAS_PX = 70
    PRIOR_SIGMA_FRAC = 0.12   # soft Gaussian around expected impact
    PRIOR_STRENGTH = 0.55     # blend weight for prior (learned via feedback)
    BELOW_BONUS = 0.85        # reinforce lower-than-aim landings (learned)
    BURST_DURATION_S = 1.45
    BURST_TARGET_FPS = 30

    def __init__(self):
        self._before_frame: Optional[np.ndarray] = None
        self._after_frames: List[np.ndarray] = []
        self._diff_frame: Optional[np.ndarray] = None
        self._hit_point: Optional[Tuple[int, int]] = None
        self._confidence: float = 0.0
        self._last_reason: str = ""
        self._noise_floor_pct: float = 0.0
        self._impact_mask_u8 = None
        self._best_after_idx: int = -1
        self._lock = threading.Lock()

    def _gray(self, frame):
        g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        k = self.BLUR_KERNEL | 1
        return cv2.GaussianBlur(g, (k, k), 0)

    def _change_pct(self, a, b) -> float:
        """Ambient flicker metric (absdiff ∪ darken) for AE / noise floor."""
        diff = cv2.absdiff(a, b)
        _, thresh = cv2.threshold(diff, self.DIFF_THRESHOLD, 255, cv2.THRESH_BINARY)
        darken = cv2.subtract(a, b)
        _, dth = cv2.threshold(darken, self.DARKEN_THRESHOLD, 255, cv2.THRESH_BINARY)
        mask = cv2.bitwise_or(thresh, dth)
        return 100.0 * cv2.countNonZero(mask) / float(mask.shape[0] * mask.shape[1])

    def measure_noise_floor(self, camera, samples: int = 4, delay: float = 0.12) -> float:
        """Ambient before/after change with no fire (AE / scene noise)."""
        if not CV2_AVAILABLE or camera is None:
            return 0.0
        frames = []
        for _ in range(max(2, samples)):
            f = camera.get_frame()
            if f is not None:
                frames.append(self._gray(f))
            time.sleep(delay)
        if len(frames) < 2:
            return 0.0
        pcts = [self._change_pct(frames[i], frames[i + 1]) for i in range(len(frames) - 1)]
        floor = float(np.median(pcts)) if pcts else 0.0
        with self._lock:
            self._noise_floor_pct = floor
        print(f"[HitDetector] noise floor={floor:.3f}%")
        return floor

    def capture_before(self, camera) -> bool:
        """Capture the 'before' frame. Call this just before firing."""
        frame = camera.get_frame() if camera is not None else None
        if frame is None:
            return False
        with self._lock:
            self._before_frame = frame.copy()
            self._after_frames.clear()
            self._diff_frame = None
            self._hit_point = None
            self._confidence = 0.0
            self._last_reason = ""
            self._impact_mask_u8 = None
            self._best_after_idx = -1
        return True

    def capture_before_stable(self, camera, tries: int = 10, max_pct: float = 0.35) -> bool:
        """Wait until consecutive frames are similar (AE settled), then lock before."""
        if not CV2_AVAILABLE or camera is None:
            return self.capture_before(camera)
        prev = None
        last = None
        for _ in range(tries):
            f = camera.get_frame()
            if f is None:
                time.sleep(0.08)
                continue
            g = self._gray(f)
            last = f
            if prev is not None and self._change_pct(prev, g) <= max_pct:
                with self._lock:
                    self._before_frame = f.copy()
                    self._after_frames.clear()
                    self._diff_frame = None
                    self._hit_point = None
                    self._confidence = 0.0
                    self._last_reason = ""
                    self._impact_mask_u8 = None
                    self._best_after_idx = -1
                return True
            prev = g
            time.sleep(0.12)
        if last is None:
            return False
        with self._lock:
            self._before_frame = last.copy()
            self._after_frames.clear()
            self._diff_frame = None
            self._hit_point = None
            self._confidence = 0.0
            self._last_reason = "ae_unstable"
            self._impact_mask_u8 = None
            self._best_after_idx = -1
        return True

    def capture_after(self, camera) -> bool:
        """Capture an 'after' frame. Prefer capture_after_burst for splash finding."""
        frame = camera.get_frame() if camera is not None else None
        if frame is None:
            return False
        with self._lock:
            self._after_frames.append(frame.copy())
        return True

    def capture_after_burst(self, camera, duration_s: Optional[float] = None,
                            target_fps: Optional[float] = None) -> int:
        """
        Grab a dense post-fire burst — matches how a human watches the landing.
        Skips duplicate frames when the camera has not updated yet.
        Returns number of unique frames captured.
        """
        if not CV2_AVAILABLE or camera is None:
            return 0
        duration = float(duration_s if duration_s is not None else self.BURST_DURATION_S)
        fps = float(target_fps if target_fps is not None else self.BURST_TARGET_FPS)
        interval = 1.0 / max(fps, 1.0)
        t_end = time.monotonic() + duration
        last_sig = None
        n = 0
        while time.monotonic() < t_end:
            t0 = time.monotonic()
            frame = camera.get_frame()
            if frame is not None:
                # Cheap signature so we only keep new camera frames
                h, w = frame.shape[:2]
                sig = (int(frame[h // 2, w // 2].sum())
                       ^ int(frame[h // 4, w // 4].sum())
                       ^ int(frame[3 * h // 4, 3 * w // 4].sum()))
                if sig != last_sig:
                    last_sig = sig
                    with self._lock:
                        self._after_frames.append(frame.copy())
                    n += 1
            dt = time.monotonic() - t0
            time.sleep(max(0.0, interval - dt))
        print(f"[HitDetector] after-burst {n} unique frames in {duration:.2f}s")
        return n

    def _blob_contrast(self, darken, mask) -> Tuple[float, float]:
        """Return (mean_darken, darken_contrast vs ring)."""
        mean_dark = float(cv2.mean(darken, mask=mask)[0])
        ring_k = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (self.RING_PX * 2 + 1, self.RING_PX * 2 + 1))
        dil = cv2.dilate(mask, ring_k)
        ring = cv2.subtract(dil, mask)
        if cv2.countNonZero(ring) < 20:
            return mean_dark, mean_dark
        ring_m = float(cv2.mean(darken, mask=ring)[0])
        return mean_dark, mean_dark - ring_m

    def _is_foliage(self, after_bgr, mask) -> bool:
        if after_bgr is None:
            return False
        mean = cv2.mean(after_bgr, mask=mask)
        b, g, r = float(mean[0]), float(mean[1]), float(mean[2])
        return g > r + self.FOLIAGE_G_MARGIN and g > b + self.FOLIAGE_G_MARGIN

    def _surface_weight(self, after_bgr, mask) -> float:
        if after_bgr is None:
            return 1.0
        mean = cv2.mean(after_bgr, mask=mask)
        b, g, r = float(mean[0]), float(mean[1]), float(mean[2])
        if b > 150 and b > r + 40 and b > g + 10:
            return 0.35
        return 1.0

    def _expected_impact(self, aim_xy, distance_m, w, h) -> Tuple[float, float]:
        """Soft prior: a bit right of aim + gravity drop with range."""
        drop_px = 0.0
        try:
            from hit_verdict import drop_px_for_distance
            drop_px = float(drop_px_for_distance(distance_m, frame_h=h))
        except Exception:
            if distance_m is not None and distance_m > 0.3:
                drop_px = 8.0 * float(distance_m)  # ~fallback
        ex = float(aim_xy[0]) + self.RIGHT_BIAS_PX
        ey = float(aim_xy[1]) + drop_px
        return (
            max(0.0, min(float(w - 1), ex)),
            max(0.0, min(float(h - 1), ey)),
        )

    def detect(self, aim_xy: Optional[Tuple[int, int]] = None,
               noise_floor_pct: Optional[float] = None,
               distance_m: Optional[float] = None) -> Optional[Tuple[int, int]]:
        """
        Find where water landed using the post-fire burst (human-visible motion).
        """
        if not CV2_AVAILABLE:
            return None

        with self._lock:
            if self._before_frame is None or not self._after_frames:
                self._last_reason = "no_frames"
                return None

            before_gray = self._gray(self._before_frame)
            h, w = before_gray.shape[:2]
            if aim_xy is None:
                aim_xy = (w // 2, h // 2)
            aim_xy = (int(aim_xy[0]), int(aim_xy[1]))
            max_dist = self.MAX_AIM_DIST_FRAC * math.hypot(w, h)
            exp_xy = self._expected_impact(aim_xy, distance_m, w, h)
            prior_sigma = max(40.0, self.PRIOR_SIGMA_FRAC * math.hypot(w, h))

            floor = (self._noise_floor_pct if noise_floor_pct is None
                     else float(noise_floor_pct))
            if floor > self.MAX_NOISE_FLOOR_PCT:
                self._hit_point = None
                self._confidence = 0.0
                self._last_reason = f"scene_unstable@{floor:.2f}%"
                print(f"[HitDetector] No hit — {self._last_reason}")
                return None

            n_after = len(self._after_frames)
            need = max(self.MIN_VOTES_ABS, int(math.ceil(self.MIN_VOTE_FRAC * n_after)))
            need = min(need, max(2, n_after))

            votes = np.zeros((h, w), dtype=np.uint16)
            darken_max = np.zeros((h, w), dtype=np.float32)
            darken_sum = np.zeros((h, w), dtype=np.float32)
            motion_max = np.zeros((h, w), dtype=np.float32)
            per_frame_darken = []
            prev_gray = before_gray
            best_idx = 0
            best_idx_score = -1.0

            for i, after_frame in enumerate(self._after_frames):
                after_gray = self._gray(after_frame)
                darken = cv2.subtract(before_gray, after_gray)
                per_frame_darken.append(darken)
                darken_f = darken.astype(np.float32)
                darken_max = np.maximum(darken_max, darken_f)
                darken_sum += darken_f
                _, dth = cv2.threshold(darken, self.DARKEN_THRESHOLD, 1, cv2.THRESH_BINARY)
                votes = votes + dth.astype(np.uint16)
                # Frame-to-frame motion (stream / splash arrival a human notices)
                motion = cv2.absdiff(prev_gray, after_gray).astype(np.float32)
                motion_max = np.maximum(motion_max, motion)
                prev_gray = after_gray
                # Track which after frame best shows the eventual hit region later
                # (filled after we pick hit — provisional: max mean darken)
                mscore = float(darken_f.mean())
                if mscore > best_idx_score:
                    best_idx_score = mscore
                    best_idx = i

            mean_darken = (darken_sum / float(n_after)).astype(np.float32)
            self._diff_frame = darken_max.astype(np.uint8)

            persistent = (votes >= need).astype(np.uint8) * 255
            # Also keep strong single-frame onsets that move (splash flash)
            _, onset = cv2.threshold(
                darken_max.astype(np.uint8), self.DARKEN_THRESHOLD + 6, 255,
                cv2.THRESH_BINARY)
            _, moved = cv2.threshold(
                motion_max.astype(np.uint8), self.DIFF_THRESHOLD + 8, 255,
                cv2.THRESH_BINARY)
            flash = cv2.bitwise_and(onset, moved)
            search = cv2.bitwise_or(persistent, flash)

            roi = np.zeros((h, w), dtype=np.uint8)
            cv2.circle(roi, aim_xy, int(max_dist), 255, -1)
            m = self.EDGE_MARGIN_PX
            top_cut = max(m, int(self.TOP_EXCLUDE_FRAC * h))
            roi[:top_cut, :] = 0
            roi[h - m:, :] = 0
            roi[:, :m] = 0
            roi[:, w - m:] = 0
            search = cv2.bitwise_and(search, roi)

            roi_area = float(cv2.countNonZero(roi)) or 1.0
            persist_pct = 100.0 * cv2.countNonZero(persistent & roi) / roi_area
            if persist_pct > self.MAX_PERSISTENT_ROI_PCT:
                self._impact_mask_u8 = search
                self._hit_point = None
                self._confidence = 0.0
                self._last_reason = f"foliage_or_wind@{persist_pct:.1f}%"
                print(f"[HitDetector] No hit — {self._last_reason}")
                return None

            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            search = cv2.morphologyEx(search, cv2.MORPH_OPEN, kernel)
            search = cv2.morphologyEx(search, cv2.MORPH_CLOSE, kernel)
            self._impact_mask_u8 = search

            after_bgr = self._after_frames[-1]
            contours, _ = cv2.findContours(
                search, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cands = []
            for c in contours:
                area = cv2.contourArea(c)
                if area < self.MIN_CONTOUR_AREA or area > self.MAX_CONTOUR_AREA:
                    continue
                peri = cv2.arcLength(c, True)
                circ = (4.0 * math.pi * area / (peri * peri)) if peri > 1 else 0.0
                if circ < self.MIN_CIRCULARITY:
                    continue
                M = cv2.moments(c)
                if M["m00"] <= 0:
                    continue
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                if math.hypot(cx - aim_xy[0], cy - aim_xy[1]) > max_dist:
                    continue
                mask = np.zeros((h, w), dtype=np.uint8)
                cv2.drawContours(mask, [c], -1, 255, -1)
                if self._is_foliage(after_bgr, mask) and cy < aim_xy[1] + int(0.1 * h):
                    continue
                mean_dark, contrast = self._blob_contrast(mean_darken, mask)
                peak_dark = float(cv2.mean(darken_max, mask=mask)[0])
                peak_motion = float(cv2.mean(motion_max, mask=mask)[0])
                if peak_dark < self.MIN_MEAN_DARKEN and mean_dark < self.MIN_MEAN_DARKEN:
                    continue
                if contrast < self.MIN_CONTRAST and peak_motion < self.DIFF_THRESHOLD:
                    continue
                # Soft prior: right + gravity-expected impact (does not replace seeing)
                dist_prior = math.hypot(cx - exp_xy[0], cy - exp_xy[1])
                prior = math.exp(-0.5 * (dist_prior / prior_sigma) ** 2)
                # Prefer slightly right/low of raw aim (operator physics + RL)
                right = max(0.0, (cx - aim_xy[0]) / float(w))
                below = max(0.0, (cy - aim_xy[1]) / float(h))
                geom = (1.0 + 0.6 * right) * (1.0 + float(self.BELOW_BONUS) * below)
                surf = self._surface_weight(after_bgr, mask)
                dark_term = min((max(peak_dark, mean_dark) / 28.0) ** 1.25, 2.6)
                motion_term = 0.7 + 0.3 * min(peak_motion / 40.0, 1.5)
                area_term = max(0.35, min(1.0, 1.0 - abs(area - 1000.0) / 10000.0))
                ps = max(0.15, min(0.85, float(self.PRIOR_STRENGTH)))
                score = (((1.0 - ps) + ps * prior) * (0.5 + 0.5 * circ) * area_term
                         * geom * surf * dark_term * motion_term
                         * (0.6 + 0.4 * min(contrast / 20.0, 1.5)))
                cands.append({
                    "xy": (cx, cy), "area": area, "circ": circ,
                    "darken": mean_dark, "peak": peak_dark, "contrast": contrast,
                    "motion": peak_motion, "prior": prior, "score": score,
                })
            cands.sort(key=lambda x: x["score"], reverse=True)

            hit = None
            conf = 0.0
            if cands and cands[0]["score"] >= self.MIN_SCORE:
                best = cands[0]
                if len(cands) > 1 and best["score"] < cands[1]["score"] * 1.10:
                    reason = (f"ambiguous@{best['score']:.0f}/"
                              f"{cands[1]['score']:.0f}")
                else:
                    hit = best["xy"]
                    conf = float(best["score"])
                    reason = (f"burst_{n_after} "
                              f"pk={best['peak']:.0f} "
                              f"mv={best['motion']:.0f} "
                              f"pr={best['prior']:.2f}")
                    # Pick gallery after-frame where this blob was darkest
                    hx, hy = hit
                    best_i, best_s = 0, -1.0
                    for i, dmap in enumerate(per_frame_darken):
                        y0, y1 = max(0, hy - 20), min(h, hy + 21)
                        x0, x1 = max(0, hx - 20), min(w, hx + 21)
                        s = float(dmap[y0:y1, x0:x1].mean())
                        if s > best_s:
                            best_s, best_i = s, i
                    best_idx = best_i
            elif cands:
                reason = f"weak_score@{cands[0]['score']:.1f}"
            else:
                reason = f"no_splash_blob(n={n_after},votes≥{need})"

            self._best_after_idx = best_idx
            self._hit_point = hit
            self._confidence = conf
            self._last_reason = reason
            if hit:
                print(f"[HitDetector] Hit ({hit[0]},{hit[1]}) conf={conf:.0f} "
                      f"floor={floor:.2f}% n={n_after} ({reason})")
            else:
                print(f"[HitDetector] No hit — {reason} (floor={floor:.2f}% n={n_after})")
            return hit

    def get_annotated_frame(self) -> Optional[np.ndarray]:
        """Best after-frame with splash mask + hit marker."""
        with self._lock:
            if not self._after_frames:
                return None
            idx = self._best_after_idx if 0 <= self._best_after_idx < len(self._after_frames) else -1
            frame = self._after_frames[idx].copy()
            mask = getattr(self, "_impact_mask_u8", None)
            if mask is not None and mask.shape[:2] == frame.shape[:2]:
                red = frame.copy()
                red[mask > 0] = (0, 0, 255)
                frame = cv2.addWeighted(frame, 0.45, red, 0.55, 0)
            if self._hit_point:
                cx, cy = self._hit_point
                cv2.circle(frame, (cx, cy), 18, (0, 255, 255), 2)
                cv2.circle(frame, (cx, cy), 4, (0, 255, 255), -1)
                cv2.putText(frame, f"HIT ({cx},{cy})",
                           (cx + 22, cy - 10), cv2.FONT_HERSHEY_SIMPLEX,
                           0.65, (0, 255, 255), 2)
            return frame

    def get_before_frame(self) -> Optional[np.ndarray]:
        with self._lock:
            return self._before_frame.copy() if self._before_frame is not None else None

    def get_after_frame(self) -> Optional[np.ndarray]:
        with self._lock:
            if not self._after_frames:
                return None
            idx = self._best_after_idx if 0 <= self._best_after_idx < len(self._after_frames) else -1
            return self._after_frames[idx].copy()

    def get_state(self) -> dict:
        with self._lock:
            return {
                "has_before": self._before_frame is not None,
                "after_count": len(self._after_frames),
                "hit_detected": self._hit_point is not None,
                "hit_x": self._hit_point[0] if self._hit_point else None,
                "hit_y": self._hit_point[1] if self._hit_point else None,
                "confidence": round(self._confidence, 1),
                "noise_floor_pct": round(self._noise_floor_pct, 3),
                "last_reason": self._last_reason,
            }


# ============================================================================
# TARGET SELECTION — Feature Detection for Auto-Calibration
# ============================================================================

class TargetSelector:
    """
    Scan the scene and pick well-distributed high-contrast target points.

    Uses Shi-Tomasi corner detection on the Scout camera (wide-angle, fixed)
    to find features, then selects N points that are maximally spread across
    the servo's range of motion using greedy farthest-point sampling.
    """

    # Shi-Tomasi parameters
    MAX_CORNERS = 200         # Maximum corners to detect
    QUALITY_LEVEL = 0.05      # Minimum corner quality (0-1)
    MIN_DISTANCE = 40         # Minimum pixel distance between corners
    BLOCK_SIZE = 7            # Neighborhood size for corner detection

    # Frame margins — exclude edges where servos can't reach
    MARGIN_FRACTION = 0.08    # Skip outer 8% of frame (endstop dead zone)

    def __init__(self, fov_h: float = 110.0, fov_v: float = 75.0,
                 frame_w: int = 1280, frame_h: int = 720):
        self.fov_h = fov_h
        self.fov_v = fov_v
        self.frame_w = frame_w
        self.frame_h = frame_h

    def detect_targets(self, frame: np.ndarray, n_targets: int = 10) -> List[dict]:
        """
        Detect N well-distributed target points in the frame.

        Args:
            frame: BGR image from the Scout camera.
            n_targets: Number of targets to select.

        Returns:
            List of dicts: [{"px": int, "py": int, "pitch": float, "yaw": float,
                            "quality": float}, ...]
        """
        if not CV2_AVAILABLE or frame is None:
            return self._fallback_grid(n_targets)

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Detect Shi-Tomasi corners
        corners = cv2.goodFeaturesToTrack(
            gray,
            maxCorners=self.MAX_CORNERS,
            qualityLevel=self.QUALITY_LEVEL,
            minDistance=self.MIN_DISTANCE,
            blockSize=self.BLOCK_SIZE
        )

        if corners is None or len(corners) < n_targets:
            print(f"[TargetSelector] Only {len(corners) if corners is not None else 0} "
                  f"corners found, falling back to grid pattern")
            return self._fallback_grid(n_targets)

        # Filter out margins
        margin_x = int(self.frame_w * self.MARGIN_FRACTION)
        margin_y = int(self.frame_h * self.MARGIN_FRACTION)
        valid = []
        for c in corners:
            px, py = int(c[0][0]), int(c[0][1])
            if margin_x < px < self.frame_w - margin_x and \
               margin_y < py < self.frame_h - margin_y:
                valid.append((px, py))

        if len(valid) < n_targets:
            return self._fallback_grid(n_targets)

        # Greedy farthest-point sampling for maximum spatial spread
        selected = [valid[0]]  # Start with first valid point
        remaining = valid[1:]

        while len(selected) < n_targets and remaining:
            best_point = None
            best_min_dist = -1
            for p in remaining:
                min_dist = min(
                    math.sqrt((p[0] - s[0])**2 + (p[1] - s[1])**2)
                    for s in selected
                )
                if min_dist > best_min_dist:
                    best_min_dist = min_dist
                    best_point = p
            if best_point:
                selected.append(best_point)
                remaining.remove(best_point)

        # Convert pixel → servo angles
        targets = []
        for px, py in selected:
            pitch, yaw = self._pixel_to_angle(px, py)
            targets.append({
                "px": px, "py": py,
                "pitch": round(pitch, 2),
                "yaw": round(yaw, 2),
                "quality": round(gray[py, px] / 255.0, 2) if 0 <= py < gray.shape[0] else 0.5
            })

        print(f"[TargetSelector] Selected {len(targets)} targets via feature detection")
        return targets

    def _pixel_to_angle(self, px: int, py: int) -> Tuple[float, float]:
        """Convert Scout camera pixel to approximate servo angles."""
        norm_x = (px / self.frame_w) - 0.5
        norm_y = (py / self.frame_h) - 0.5
        yaw = norm_x * self.fov_h
        pitch = norm_y * self.fov_v
        return pitch, yaw

    def _fallback_grid(self, n_targets: int) -> List[dict]:
        """Generate a fixed grid pattern when feature detection fails."""
        print("[TargetSelector] Using fallback grid pattern")
        targets = []
        # Generate a roughly circular pattern
        if n_targets <= 5:
            pattern = [(0, 0), (-15, -20), (-15, 20), (15, -20), (15, 20)]
        else:
            pattern = [
                (0, 0),          # Center
                (-20, 0),        # Top
                (20, 0),         # Bottom
                (0, -30),        # Left
                (0, 30),         # Right
                (-15, -20),      # Top-left
                (-15, 20),       # Top-right
                (15, -20),       # Bottom-left
                (15, 20),        # Bottom-right
                (0, 0),          # Center re-verify
            ]
        for i, (pitch, yaw) in enumerate(pattern[:n_targets]):
            # Convert angles back to approximate pixel coords
            px = int((yaw / self.fov_h + 0.5) * self.frame_w)
            py = int((pitch / self.fov_v + 0.5) * self.frame_h)
            targets.append({
                "px": max(0, min(px, self.frame_w - 1)),
                "py": max(0, min(py, self.frame_h - 1)),
                "pitch": pitch, "yaw": yaw,
                "quality": 0.5
            })
        return targets


# ============================================================================
# AUTO-CALIBRATOR — One-Button Autonomous Calibration
# ============================================================================

class AutoCalibrator:
    """
    Fully autonomous one-button calibration system.

    Press one button → system scans scene → picks 10 targets → fires at each →
    detects hits → adapts offset in real-time → saves. Designed for commercial
    one-button UX.

    Runs in a background thread so the API doesn't block. The UI polls
    get_status() for live progress updates.

    Adaptive offset: After each successful hit, the running offset average
    is updated and applied to the NEXT shot. This means later shots are
    progressively more accurate.

    3-tier retry on miss:
    1. Prefer 30 ms pulse (clearest wet on deck); slight escalate if needed
    2. Near-crosshair HitDetector + reject |offset| > 8° (false blob)
    3. Skip point, use remaining inlier points for offset
    """

    # Configuration
    N_POINTS = 10             # Number of calibration points
    # Hunt pulse stays at settings default; auto-cal uses a visible wet pulse
    # (same PSI → aim geometry stays comparable). Operator: 30 ms clearest.
    FIRE_DURATION = 0.030
    RETRY_DURATION = 0.040
    CAL_PULSE_MS_LADDER = (30, 30, 35, 40)
    SETTLE_TIME = 1.5         # Seconds to wait after servo move
    MAX_RETRIES = 3           # 4 attempts at ~30–40 ms
    MIN_HITS_TO_SAVE = 3      # Dry/noise "hits" must not overwrite a good offset
    SNIPER_W = 1280
    SNIPER_H = 720

    def __init__(self, cal_table: CalibrationTable, hit_detector: HitDetector,
                 hit_store=None):
        self.table = cal_table
        self.detector = hit_detector
        self.hit_store = hit_store
        self.target_selector = TargetSelector()

        # State
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()

        # Progress (read by UI via get_status())
        self._phase = "idle"           # idle, scanning, calibrating, complete, error, cancelled
        self._point_index = 0
        self._total_points = self.N_POINTS
        self._targets: List[dict] = []
        self._log: List[dict] = []     # Rolling log of results
        self._current_status = ""      # Human-readable status line
        self._success_count = 0
        self._fail_count = 0
        self._skip_count = 0
        self._prev_offset = (0.0, 0.0)
        self._rejected_save = False

        # Hardware refs (set during start)
        self._gimbal = None
        self._scout_cam = None
        self._sniper_cam = None
        self._relay = None
        self._lidar = None
        self._primer = None
        self._accum = None

    def start(self, gimbal, scout_cam, sniper_cam, relay, lidar, primer=None, accum=None):
        """
        Start autonomous calibration in a background thread.

        Args:
            gimbal: ServoTurretController instance
            scout_cam: Scout CameraStream (wide-angle, fixed)
            sniper_cam: Sniper CameraStream (on gimbal)
            relay: RelayController instance
            lidar: LiDARController instance
            primer: PrimingSystem instance (optional, for auto-priming)
            accum: AccumulatorManager — required for pressure-gated solenoid shots
        """
        with self._lock:
            if self._running:
                return {"error": "Calibration already in progress"}

            self._gimbal = gimbal
            self._scout_cam = scout_cam
            self._sniper_cam = sniper_cam
            self._relay = relay
            self._lidar = lidar
            self._primer = primer
            self._accum = accum

            # Keep previous offset if this run fails dry / too few real hits
            self._prev_offset = (self.table.offset_pitch, self.table.offset_yaw)
            self._rejected_save = False
            self.table.clear()
            self._phase = "scanning"
            self._point_index = 0
            self._targets = []
            self._log = []
            self._current_status = "Scanning scene for targets..."
            self._success_count = 0
            self._fail_count = 0
            self._skip_count = 0
            self._running = True

        self._thread = threading.Thread(target=self._run, daemon=True, name="auto-cal")
        self._thread.start()
        print("[AutoCal] Started autonomous calibration")
        return self.get_status()

    def stop(self):
        """Cancel in-progress calibration."""
        with self._lock:
            if self._running:
                self._running = False
                self._phase = "cancelled"
                self._current_status = "Calibration cancelled by user."
        print("[AutoCal] Calibration cancelled")

    def get_status(self) -> dict:
        """Return full calibration status for the UI (polled every 500ms)."""
        with self._lock:
            return {
                "phase": self._phase,
                "point_index": self._point_index,
                "total_points": self._total_points,
                "progress_pct": int(self._point_index / max(self._total_points, 1) * 100),
                "status": self._current_status,
                "success_count": self._success_count,
                "fail_count": self._fail_count,
                "skip_count": self._skip_count,
                "rejected_save": self._rejected_save,
                "min_hits_to_save": self.MIN_HITS_TO_SAVE,
                "targets": self._targets,
                "log": self._log[-15:],   # Last 15 entries for UI
                "table": self.table.to_dict(),
                "hit_detector": self.detector.get_state(),
                "running": self._running,
            }

    def _update(self, status: str, **kwargs):
        """Update progress state (thread-safe)."""
        with self._lock:
            self._current_status = status
            for k, v in kwargs.items():
                setattr(self, f"_{k}", v)

    def _add_log(self, entry: dict):
        """Append to the rolling log."""
        entry["timestamp"] = stamp_hms()
        with self._lock:
            self._log.append(entry)
        print(f"[AutoCal] {entry}")

    def _run(self):
        """Main calibration loop (runs in background thread)."""
        try:
            # Phase 1: Scan scene and select targets
            self._phase_scan()

            if not self._running:
                return

            # Phase 1.5: Prime the water line before first shot
            self._phase_prime()

            if not self._running:
                return

            # Phase 1.6: Arm accumulator — charge to Target PSI (solenoid shots only)
            if not self._phase_arm_accumulator():
                return

            if not self._running:
                return

            # Phase 2: Calibrate each target
            self._phase_calibrate()

            if not self._running:
                return

            # Phase 3: Finalize and save
            self._phase_finalize()

        except Exception as e:
            self._update(f"Error: {e}", phase="error")
            self._add_log({"type": "error", "message": str(e)})
            print(f"[AutoCal] Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if self._accum is not None:
                try:
                    self._accum.disarm(reason="auto-cal end")
                except Exception:
                    pass
            # Extra recover even if accum was None — Click Test must work next
            if self._relay is not None:
                try:
                    self._relay.recover_solenoid(re_pinmux=False)
                except Exception:
                    pass
            try:
                from activity_log import log_event
                log_event("AUTOCAL_END", phase=self._phase,
                          success=self._success_count, skipped=self._skip_count)
            except Exception:
                pass
            with self._lock:
                self._running = False

    def _phase_scan(self):
        """Phase 1: Move to center, capture scout frame, detect features."""
        self._update("Moving to center position...", phase="scanning")

        # Center the gimbal so scout camera has a clean reference
        self._gimbal.center()
        time.sleep(self.SETTLE_TIME)

        # Capture a frame from the scout camera
        self._update("Scanning scene for high-contrast targets...")
        frame = self._scout_cam.get_frame()

        if frame is None:
            self._add_log({"type": "warning", "message": "Scout camera unavailable, using grid pattern"})

        # Detect targets
        targets = self.target_selector.detect_targets(frame, self.N_POINTS)
        with self._lock:
            self._targets = targets
            self._total_points = len(targets)

        self._add_log({
            "type": "scan_complete",
            "message": f"Found {len(targets)} calibration targets",
            "targets": [(t["pitch"], t["yaw"]) for t in targets]
        })

    def _phase_arm_accumulator(self) -> bool:
        """Charge to Target PSI and arm — required before any solenoid shot."""
        if self._accum is None:
            self._update("Error: AccumulatorManager not available", phase="error")
            self._add_log({"type": "error",
                           "message": "Auto-cal requires AccumulatorManager for solenoid shots"})
            return False
        self._update("Charging accumulator to Target PSI...", phase="arming")
        result = self._accum.arm()
        if result.get("status") != "armed":
            err = result.get("error") or result.get("status")
            self._update(f"Arm failed: {err}", phase="error")
            self._add_log({"type": "error", "message": f"Arm failed: {err}"})
            return False
        psi = result.get("psi")
        self._add_log({
            "type": "armed",
            "message": f"Armed at {psi} PSI (target {result.get('target_psi')} PSI) — "
                       f"shots are solenoid-only"
        })
        self._update(f"Armed at {psi} PSI — starting calibration shots...")
        return True

    def _phase_prime(self):
        """Phase 1.5: Prime the water line if needed."""
        if self._primer and self._primer.needs_priming():
            self._update("Priming water line — aiming down & pumping...", phase="priming")
            self._add_log({
                "type": "priming",
                "message": f"💧 Priming water line ({self._primer.prime_duration_ms}ms)..."
            })

            result = self._primer.prime(
                gimbal=self._gimbal,
                camera=self._sniper_cam
            )

            status = "✅ Water detected" if result.get("water_detected") == True else \
                     "⚠️ Primed (uncertain)" if result.get("status") == "prime_uncertain" else \
                     "✅ Primed"

            self._add_log({
                "type": "prime_complete",
                "message": f"💧 Priming complete: {status}",
                "result": result
            })
        else:
            self._add_log({
                "type": "prime_skip",
                "message": "💧 Water line already primed — skipping"
            })

    def _phase_calibrate(self):
        """Phase 2: Fire at each target, detect hits, adapt offset."""
        self._update("Starting calibration sequence...", phase="calibrating")

        for i, target in enumerate(self._targets):
            if not self._running:
                return

            with self._lock:
                self._point_index = i

            pitch = target["pitch"]
            yaw = target["yaw"]
            aim_px = target["px"]
            aim_py = target["py"]

            self._update(f"Point {i+1}/{len(self._targets)}: "
                        f"Aiming at ({pitch:.1f}°, {yaw:.1f}°)...")

            # Apply current offset correction to this shot
            corrected_pitch = pitch + self.table.offset_pitch
            corrected_yaw = yaw + self.table.offset_yaw

            # Move servos
            self._gimbal.set_angles(corrected_pitch, corrected_yaw)
            time.sleep(self.SETTLE_TIME)

            # Try to fire and detect hit (with retries)
            result = self._fire_and_detect_with_retry(
                i, corrected_pitch, corrected_yaw, aim_px, aim_py)

            if result["success"]:
                with self._lock:
                    self._success_count += 1
            elif result["skipped"]:
                with self._lock:
                    self._skip_count += 1
            else:
                with self._lock:
                    self._fail_count += 1

    def _fire_and_detect_with_retry(self, point_idx: int,
                                     pitch: float, yaw: float,
                                     aim_px: int, aim_py: int) -> dict:
        """
        Fire at a target with retry logic.

        Splash is measured in the Sniper frame vs the sniper crosshair (not
        Scout pixel coords). Detection uses darkening-aware HitDetector.
        Retries prefer 30 ms pulse (clearest wet); escalate slightly if needed.
        HitDetector refuses unstable scenes and weak/ambiguous darken blobs.
        """
        # Offset = splash vs where the Sniper camera was aimed (crosshair)
        sniper_aim_px = self.SNIPER_W // 2
        sniper_aim_py = self.SNIPER_H // 2

        for attempt in range(self.MAX_RETRIES + 1):
            if not self._running:
                return {"success": False, "skipped": True}

            pulse_ms = float(
                self.CAL_PULSE_MS_LADDER[
                    min(attempt, len(self.CAL_PULSE_MS_LADDER) - 1)
                ]
            )
            attempt_desc = f"{pulse_ms:.0f}ms pulse"

            self._update(f"Point {point_idx+1}: Measuring noise floor...")
            noise = self.detector.measure_noise_floor(self._sniper_cam)
            # Outdoor AE/leaf flicker: wait rather than fire into noise
            for _settle in range(4):
                if noise <= self.detector.MAX_NOISE_FLOOR_PCT:
                    break
                self._update(
                    f"Point {point_idx+1}: Scene unstable "
                    f"({noise:.1f}%) — waiting for AE...")
                time.sleep(0.7)
                noise = self.detector.measure_noise_floor(self._sniper_cam)
            if noise > self.detector.MAX_NOISE_FLOOR_PCT:
                self._add_log({
                    "type": "miss",
                    "point": point_idx + 1,
                    "attempt": attempt + 1,
                    "pulse_ms": pulse_ms,
                    "noise_floor": round(noise, 3),
                    "reason": f"scene_unstable@{noise:.2f}%",
                    "message": (
                        f"❌ Point {point_idx+1}: Scene too unstable "
                        f"({noise:.1f}% noise) — skipping fire"
                        + (" — retrying..." if attempt < self.MAX_RETRIES
                           else " — skipping.")
                    ),
                })
                if attempt < self.MAX_RETRIES:
                    time.sleep(0.5)
                continue

            self._update(f"Point {point_idx+1}: Waiting for AE / firing ({attempt_desc})...")
            self.detector.capture_before_stable(self._sniper_cam)

            psi_set = getattr(self._accum, "TARGET_PSI", None)
            self._update(
                f"Point {point_idx+1}: {pulse_ms:.0f}ms @ "
                f"{psi_set:.1f} PSI ({attempt_desc})..."
                if psi_set is not None else
                f"Point {point_idx+1}: Solenoid pulse {pulse_ms:.0f}ms ({attempt_desc})...")
            fire_result = self._accum.fire(pulse_ms / 1000.0)
            try:
                from activity_log import log_event
                log_event("AUTOCAL_FIRE", point=point_idx + 1, attempt=attempt + 1,
                          status=fire_result.get("status"),
                          pulse_ms=fire_result.get("duration_ms", pulse_ms),
                          elapsed_ms=fire_result.get("elapsed_ms"),
                          psi_before=fire_result.get("psi_before"),
                          psi_after=fire_result.get("psi_after"),
                          noise_floor=noise)
            except Exception:
                pass
            if fire_result.get("status") == "sensor_fault":
                self._update(f"Sensor fault: {fire_result.get('error')}", phase="error")
                self._add_log({"type": "error",
                               "message": f"🚨 Sensor fault — disarmed: {fire_result.get('error')}"})
                self._running = False
                return {"success": False, "skipped": True}
            if fire_result.get("status") != "fired":
                self._add_log({
                    "type": "miss",
                    "point": point_idx + 1,
                    "attempt": attempt + 1,
                    "message": f"❌ Point {point_idx+1}: Fire refused "
                               f"({fire_result.get('status')}: {fire_result.get('error')})"
                })
                if attempt >= self.MAX_RETRIES:
                    break
                time.sleep(0.5)
                continue

            time.sleep(0.08)
            # Dense burst — watch the landing the way a human does (not 5 stills)
            self._update(f"Point {point_idx+1}: Watching splash burst...")
            n_burst = self.detector.capture_after_burst(self._sniper_cam)
            dist_m = None
            try:
                dist_m = self._lidar.read_distance()
            except Exception:
                dist_m = None
            hit = self.detector.detect(
                aim_xy=(sniper_aim_px, sniper_aim_py),
                noise_floor_pct=noise,
                distance_m=dist_m,
            )
            det = self.detector.get_state()
            if n_burst:
                det = {**det, "burst_frames": n_burst}

            if hit:
                hit_px, hit_py = hit
                point = CalibrationPoint(
                    aim_pitch=pitch, aim_yaw=yaw,
                    aim_px=sniper_aim_px, aim_py=sniper_aim_py,
                    hit_px=hit_px, hit_py=hit_py,
                    hit_confirmed=True,
                    distance_m=self._lidar.read_distance(),
                    note=(f"auto-cal point {point_idx+1} attempt {attempt+1} "
                          f"pulse={pulse_ms:.0f}ms "
                          f"scout_feat=({aim_px},{aim_py})")
                )
                point.compute_offset()
                accepted = self.table.add_point(point)
                if not accepted:
                    # False localization far from crosshair — do not pollute gallery/offset
                    self._add_log({
                        "type": "reject",
                        "point": point_idx + 1,
                        "attempt": attempt + 1,
                        "pulse_ms": pulse_ms,
                        "aim": f"({sniper_aim_px},{sniper_aim_py})",
                        "hit": f"({hit_px},{hit_py})",
                        "offset_pitch": round(point.offset_pitch, 2),
                        "offset_yaw": round(point.offset_yaw, 2),
                        "reason": "offset_outlier",
                        "message": (
                            f"❌ Point {point_idx+1}: Rejected false hit "
                            f"@ ({hit_px},{hit_py}) "
                            f"P={point.offset_pitch:.1f}° Y={point.offset_yaw:.1f}° "
                            f"(max ±{self.table.MAX_POINT_OFFSET_DEG}°)"
                            + (" — retrying..." if attempt < self.MAX_RETRIES
                               else " — skipping.")
                        ),
                    })
                    if attempt < self.MAX_RETRIES:
                        nxt = self.CAL_PULSE_MS_LADDER[
                            min(attempt + 1, len(self.CAL_PULSE_MS_LADDER) - 1)
                        ]
                        self._update(
                            f"Point {point_idx+1}: False hit rejected — "
                            f"retrying at {nxt}ms...")
                        time.sleep(0.5)
                    continue

                # Persist before / after / bright-red diff for gallery (last 10)
                try:
                    if self.hit_store is not None:
                        hid = self.hit_store.save(
                            self.detector.get_before_frame(),
                            self.detector.get_after_frame(),
                            self.detector.get_annotated_frame(),
                            meta={
                                "point": point_idx + 1,
                                "attempt": attempt + 1,
                                "pulse_ms": pulse_ms,
                                "hit_px": hit_px,
                                "hit_py": hit_py,
                                "offset_pitch": round(point.offset_pitch, 2),
                                "offset_yaw": round(point.offset_yaw, 2),
                                "reason": det.get("last_reason"),
                            },
                        )
                        if hid:
                            print(f"[AutoCal] Saved hit gallery id={hid}")
                except Exception as e:
                    print(f"[AutoCal] hit gallery save skip: {e}")

                self._add_log({
                    "type": "hit",
                    "point": point_idx + 1,
                    "attempt": attempt + 1,
                    "pulse_ms": pulse_ms,
                    "aim": f"({sniper_aim_px},{sniper_aim_py})",
                    "hit": f"({hit_px},{hit_py})",
                    "offset_pitch": round(point.offset_pitch, 2),
                    "offset_yaw": round(point.offset_yaw, 2),
                    "noise_floor": round(noise, 3),
                    "reason": det.get("last_reason"),
                    "running_offset": f"P={self.table.offset_pitch:.2f}° Y={self.table.offset_yaw:.2f}°",
                    "message": f"✅ Point {point_idx+1}: Splash @ ({hit_px},{hit_py}) "
                              f"@ {pulse_ms:.0f}ms. Offset P={point.offset_pitch:.2f}° "
                              f"Y={point.offset_yaw:.2f}°"
                })
                self._update(
                    f"Point {point_idx+1}: ✅ Hit @ {pulse_ms:.0f}ms! "
                    f"Running offset: P={self.table.offset_pitch:.2f}° Y={self.table.offset_yaw:.2f}°")
                return {"success": True, "skipped": False}

            self._add_log({
                "type": "miss",
                "point": point_idx + 1,
                "attempt": attempt + 1,
                "attempt_desc": attempt_desc,
                "pulse_ms": pulse_ms,
                "noise_floor": round(noise, 3),
                "reason": det.get("last_reason"),
                "message": (f"❌ Point {point_idx+1}: No splash "
                            f"({det.get('last_reason') or attempt_desc})"
                            + (" — retrying..." if attempt < self.MAX_RETRIES
                               else " — skipping."))
            })
            if attempt < self.MAX_RETRIES:
                nxt = self.CAL_PULSE_MS_LADDER[
                    min(attempt + 1, len(self.CAL_PULSE_MS_LADDER) - 1)
                ]
                self._update(
                    f"Point {point_idx+1}: Miss — retrying at {nxt}ms...")
                time.sleep(0.5)

        self._add_log({
            "type": "skip",
            "point": point_idx + 1,
            "message": f"⏭ Point {point_idx+1}: Skipped after {self.MAX_RETRIES + 1} attempts"
        })
        self._update(f"Point {point_idx+1}: Skipped (no splash after retries)")
        return {"success": False, "skipped": True}

    def _phase_finalize(self):
        """Phase 3: Save only if enough consensus hits; else keep previous offset."""
        if self._success_count < self.MIN_HITS_TO_SAVE:
            self.table.points.clear()
            self.table.offset_pitch, self.table.offset_yaw = self._prev_offset
            self._rejected_save = True
            summary = (
                f"Calibration REJECTED — only {self._success_count} reliable splash "
                f"hit(s) (need ≥{self.MIN_HITS_TO_SAVE}). Dry-fire / AE noise often "
                f"fakes 1–2 hits. Previous offset kept: "
                f"P={self.table.offset_pitch:.2f}° Y={self.table.offset_yaw:.2f}°. "
                f"Use water + a visible impact surface, then re-run."
            )
            self._add_log({
                "type": "rejected",
                "success": self._success_count,
                "skipped": self._skip_count,
                "failed": self._fail_count,
                "offset_pitch": round(self.table.offset_pitch, 3),
                "offset_yaw": round(self.table.offset_yaw, 3),
                "message": summary
            })
            self._gimbal.center()
            with self._lock:
                self._phase = "error"
                self._point_index = self._total_points
                self._current_status = summary
            print(f"[AutoCal] {summary}")
            return

        self.table.save()
        summary = (
            f"Calibration complete! "
            f"{self._success_count} hits, {self._skip_count} skipped, "
            f"{self._fail_count} failed. "
            f"Final offset (median): P={self.table.offset_pitch:.2f}° "
            f"Y={self.table.offset_yaw:.2f}°"
        )
        self._add_log({
            "type": "complete",
            "success": self._success_count,
            "skipped": self._skip_count,
            "failed": self._fail_count,
            "offset_pitch": round(self.table.offset_pitch, 3),
            "offset_yaw": round(self.table.offset_yaw, 3),
            "message": summary
        })
        self._gimbal.center()
        with self._lock:
            self._phase = "complete"
            self._point_index = self._total_points
            self._current_status = summary
        print(f"[AutoCal] {summary}")

