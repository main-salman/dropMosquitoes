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

    The global offset represents the average camera-nozzle misalignment
    that applies to ALL angles. Per-point residuals are stored for
    fine-grained interpolation at specific distances/angles.
    """

    def __init__(self, filepath: str = "calibration.json", settings_store=None):
        self.filepath = filepath
        self._settings_store = settings_store  # SW-001 §2.11 — preferred persistence
        self.points: List[CalibrationPoint] = []
        self.offset_pitch: float = 0.0   # Global pitch correction (degrees)
        self.offset_yaw: float = 0.0     # Global yaw correction (degrees)
        self.last_updated: str = ""

    def add_point(self, point: CalibrationPoint):
        """Add a calibration measurement and recompute global offset."""
        if not point.timestamp:
            point.timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self.points.append(point)
        self._recompute_offset()

    def _recompute_offset(self):
        """Recompute global offset as the median of confirmed points (outlier-robust)."""
        confirmed = [p for p in self.points if p.hit_confirmed]
        if not confirmed:
            return
        pitches = sorted(p.offset_pitch for p in confirmed)
        yaws = sorted(p.offset_yaw for p in confirmed)
        mid = len(confirmed) // 2
        if len(confirmed) % 2:
            self.offset_pitch = pitches[mid]
            self.offset_yaw = yaws[mid]
        else:
            self.offset_pitch = 0.5 * (pitches[mid - 1] + pitches[mid])
            self.offset_yaw = 0.5 * (yaws[mid - 1] + yaws[mid])
        self.last_updated = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[Calibration] Global offset (median): pitch={self.offset_pitch:.2f}° "
              f"yaw={self.offset_yaw:.2f}° ({len(confirmed)} points)")

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
    Detect where water hits by comparing before/after Sniper frames.

    Tuned for real outdoor impacts (coin-size dark wet stains on wood/concrete),
    not only bright specular splash:
      - absdiff + **darkening** mask (after darker than before)
      - pre-fire noise floor (must exceed ~2× ambient)
      - stable before-frame (AE settled)
      - small-blob gates (coin @ 1–3 m)
      - search biased **below** Sniper crosshair (nozzle gravity / low impacts)
      - multi-frame consensus (≥2 after-frames agree)
    """

    # Pixel gates — sensitive enough for subtle wet darkening humans can see
    DIFF_THRESHOLD = 24          # absdiff (was 48 — missed deck stains)
    DARKEN_THRESHOLD = 10        # before−after gray (wet wood / most surfaces)
    MIN_CONTOUR_AREA = 220       # coin-size @ ~1–3 m on 1280×720
    MAX_CONTOUR_AREA = 35000
    BLUR_KERNEL = 7
    MIN_CHANGE_PCT = 0.12        # was 0.9 — wet stains are tiny % of frame
    MAX_CHANGE_PCT = 12.0
    NOISE_MULTIPLIER = 2.0
    MIN_CIRCULARITY = 0.05       # irregular stains OK
    CONSENSUS_PX = 56
    MIN_CONSENSUS = 2
    MAX_AIM_DIST_FRAC = 0.58
    # Prefer impacts below crosshair (user: wet is low; gravity)
    AIM_DOWN_BIAS_FRAC = 0.14
    MIN_MEAN_DARKEN = 4.0        # blob must be net darker after (reduces AE false +)

    def __init__(self):
        self._before_frame: Optional[np.ndarray] = None
        self._after_frames: List[np.ndarray] = []
        self._diff_frame: Optional[np.ndarray] = None
        self._hit_point: Optional[Tuple[int, int]] = None
        self._confidence: float = 0.0
        self._last_reason: str = ""
        self._noise_floor_pct: float = 0.0
        self._lock = threading.Lock()

    def _gray(self, frame):
        g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        k = self.BLUR_KERNEL | 1
        return cv2.GaussianBlur(g, (k, k), 0)

    def _change_pct(self, a, b) -> float:
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
        return True

    def capture_before_stable(self, camera, tries: int = 6, max_pct: float = 0.45) -> bool:
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
                return True
            prev = g
            time.sleep(0.1)
        if last is None:
            return False
        with self._lock:
            self._before_frame = last.copy()
            self._after_frames.clear()
            self._diff_frame = None
            self._hit_point = None
            self._confidence = 0.0
            self._last_reason = "ae_unstable"
        return True

    def capture_after(self, camera) -> bool:
        """Capture an 'after' frame. Call multiple times post-fire."""
        frame = camera.get_frame() if camera is not None else None
        if frame is None:
            return False
        with self._lock:
            self._after_frames.append(frame.copy())
        return True

    def _impact_mask(self, before_gray, after_gray):
        """Union of absdiff and darkening — wet stains darken most surfaces."""
        diff = cv2.absdiff(before_gray, after_gray)
        _, abs_th = cv2.threshold(diff, self.DIFF_THRESHOLD, 255, cv2.THRESH_BINARY)
        darken = cv2.subtract(before_gray, after_gray)
        _, dark_th = cv2.threshold(darken, self.DARKEN_THRESHOLD, 255, cv2.THRESH_BINARY)
        return cv2.bitwise_or(abs_th, dark_th), diff, darken

    def _candidates_from_diff(self, before_gray, after_frame, min_pct: float,
                              aim_xy, max_dist_px: float):
        after_gray = self._gray(after_frame)
        thresh, diff, darken = self._impact_mask(before_gray, after_gray)
        total = thresh.shape[0] * thresh.shape[1]
        change_pct = 100.0 * cv2.countNonZero(thresh) / float(total)
        if change_pct < min_pct:
            return [], change_pct, diff, "low_change"
        if change_pct > self.MAX_CHANGE_PCT:
            return [], change_pct, diff, "scene_change"

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
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
            if aim_xy is not None and max_dist_px > 0:
                if math.hypot(cx - aim_xy[0], cy - aim_xy[1]) > max_dist_px:
                    continue
            # Require net darkening inside contour (wet vs AE bright flicker)
            mask = np.zeros(before_gray.shape, dtype=np.uint8)
            cv2.drawContours(mask, [c], -1, 255, -1)
            mean_dark = float(cv2.mean(darken, mask=mask)[0])
            if mean_dark < self.MIN_MEAN_DARKEN:
                continue
            # Score: darker + lower in frame (prefer below crosshair)
            below = max(0, cy - aim_xy[1]) if aim_xy else 0
            score = area * (1.0 + 0.02 * mean_dark) * (1.0 + 0.001 * below)
            cands.append({
                "xy": (cx, cy), "area": area, "circ": circ,
                "darken": mean_dark, "score": score,
            })
        cands.sort(key=lambda x: x["score"], reverse=True)
        return cands[:3], change_pct, diff, ("ok" if cands else "no_blob")

    def detect(self, aim_xy: Optional[Tuple[int, int]] = None,
               noise_floor_pct: Optional[float] = None) -> Optional[Tuple[int, int]]:
        """
        Run hit detection on captured frames.

        Returns (x, y) of splash in Sniper pixels, or None.
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
            # Bias search center downward — impacts land low of crosshair
            aim_xy = (
                int(aim_xy[0]),
                int(min(h - 1, aim_xy[1] + self.AIM_DOWN_BIAS_FRAC * h)),
            )
            max_dist = self.MAX_AIM_DIST_FRAC * math.hypot(w, h)
            floor = (self._noise_floor_pct if noise_floor_pct is None
                     else float(noise_floor_pct))
            min_pct = max(self.MIN_CHANGE_PCT, floor * self.NOISE_MULTIPLIER)

            per_frame = []
            best_diff = None
            reasons = []
            for after_frame in self._after_frames:
                cands, change_pct, diff, reason = self._candidates_from_diff(
                    before_gray, after_frame, min_pct, aim_xy, max_dist)
                reasons.append(f"{reason}@{change_pct:.2f}%")
                if cands:
                    per_frame.append(cands[0])
                    if best_diff is None:
                        best_diff = diff

            hit = None
            conf = 0.0
            reason = "no_consensus"
            if len(per_frame) >= self.MIN_CONSENSUS:
                best_n, best_seed = 0, None
                for i, a in enumerate(per_frame):
                    n = 1
                    ax, ay = a["xy"]
                    score_sum = a.get("score", a["area"])
                    for j, b in enumerate(per_frame):
                        if i == j:
                            continue
                        if math.hypot(ax - b["xy"][0], ay - b["xy"][1]) <= self.CONSENSUS_PX:
                            n += 1
                            score_sum += b.get("score", b["area"])
                    if n > best_n:
                        best_n, best_seed = n, (ax, ay, score_sum / n)
                if best_seed is not None and best_n >= self.MIN_CONSENSUS:
                    hit = (int(best_seed[0]), int(best_seed[1]))
                    conf = float(best_seed[2])
                    reason = f"consensus_{best_n}/{len(per_frame)}"
            elif len(per_frame) == 1:
                reason = "single_frame_only:" + ",".join(reasons)
            else:
                reason = "no_blob:" + ",".join(reasons)

            self._hit_point = hit
            self._confidence = conf
            self._last_reason = reason
            if best_diff is not None:
                self._diff_frame = best_diff

            if hit:
                print(f"[HitDetector] Hit ({hit[0]},{hit[1]}) conf={conf:.0f} "
                      f"min_pct={min_pct:.2f} ({reason})")
            else:
                print(f"[HitDetector] No hit — {reason} (min_pct={min_pct:.2f})")
            return hit

    def get_annotated_frame(self) -> Optional[np.ndarray]:
        with self._lock:
            if not self._after_frames:
                return None
            frame = self._after_frames[-1].copy()
            if self._diff_frame is not None:
                heatmap = cv2.applyColorMap(self._diff_frame, cv2.COLORMAP_JET)
                mask = self._diff_frame > self.DIFF_THRESHOLD
                frame[mask] = cv2.addWeighted(frame, 0.5, heatmap, 0.5, 0)[mask]
            if self._hit_point:
                cx, cy = self._hit_point
                cv2.circle(frame, (cx, cy), 15, (0, 255, 0), 2)
                cv2.circle(frame, (cx, cy), 3, (0, 255, 0), -1)
                cv2.putText(frame, f"HIT ({cx},{cy})",
                           (cx + 20, cy - 10), cv2.FONT_HERSHEY_SIMPLEX,
                           0.6, (0, 255, 0), 2)
            return frame

    def get_before_frame(self) -> Optional[np.ndarray]:
        with self._lock:
            return self._before_frame.copy() if self._before_frame is not None else None

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
    1. Escalating solenoid pulse for visibility: 11 → 15 → 20 → 30 ms (same PSI)
    2. Same HitDetector gates (darkening-aware wet stain detection)
    3. Skip point, use remaining points for offset
    """

    # Configuration
    N_POINTS = 10             # Number of calibration points
    # Hunt pulse stays at settings default; auto-cal may escalate volume so the
    # wet stain is visible (same PSI → aim geometry stays comparable).
    FIRE_DURATION = 0.011
    RETRY_DURATION = 0.030
    CAL_PULSE_MS_LADDER = (11, 15, 20, 30)
    SETTLE_TIME = 1.5         # Seconds to wait after servo move
    # Wet stains appear ~0.5 s; sample through ~1.3 s
    POST_FIRE_DELAYS = [0.35, 0.50, 0.70, 1.00, 1.30]
    MAX_RETRIES = 3           # 4 attempts → full 11/15/20/30 ms ladder
    MIN_HITS_TO_SAVE = 3      # Dry/noise "hits" must not overwrite a good offset
    SNIPER_W = 1280
    SNIPER_H = 720

    def __init__(self, cal_table: CalibrationTable, hit_detector: HitDetector):
        self.table = cal_table
        self.detector = hit_detector
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
        entry["timestamp"] = time.strftime("%H:%M:%S")
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
        Retries escalate pulse 11→15→20→30 ms (same PSI) so coin-size wet
        stains become visible without loosening gates.
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

            time.sleep(0.15)
            t0 = time.monotonic()
            for delay in self.POST_FIRE_DELAYS:
                wait = delay - (time.monotonic() - t0)
                if wait > 0:
                    time.sleep(wait)
                self.detector.capture_after(self._sniper_cam)

            hit = self.detector.detect(
                aim_xy=(sniper_aim_px, sniper_aim_py),
                noise_floor_pct=noise,
            )
            det = self.detector.get_state()

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
                self.table.add_point(point)

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

