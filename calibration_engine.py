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
        """Recompute global offset as the average of all confirmed points."""
        confirmed = [p for p in self.points if p.hit_confirmed]
        if not confirmed:
            return
        self.offset_pitch = sum(p.offset_pitch for p in confirmed) / len(confirmed)
        self.offset_yaw = sum(p.offset_yaw for p in confirmed) / len(confirmed)
        self.last_updated = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[Calibration] Global offset: pitch={self.offset_pitch:.2f}° "
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
    Detect where water hits by comparing before/after camera frames.

    Algorithm:
    1. Capture "before" frame from sniper camera
    2. Fire water
    3. Capture multiple "after" frames (at 0.3s, 0.6s, 1.0s)
    4. Compute absolute difference between before and best after
    5. Threshold + find largest contour → centroid = hit location

    Works best with:
    - Good lighting
    - Dark target surface (water splash = high contrast)
    - Focused water stream (not mist)
    """

    # Tuning parameters
    DIFF_THRESHOLD = 40       # Pixel intensity difference to count as "changed"
    MIN_CONTOUR_AREA = 500    # Minimum splash area in pixels² (raised from 50 to reject noise)
    MAX_CONTOUR_AREA = 50000  # Maximum (reject full-frame changes like lighting)
    BLUR_KERNEL = 7           # Gaussian blur before diff (reduce noise)
    MIN_CHANGE_PCT = 0.3      # Minimum % of total pixels that must change (rejects sensor noise)
    MAX_CHANGE_PCT = 15.0     # Maximum % change (rejects lighting shifts / camera shake)

    def __init__(self):
        self._before_frame: Optional[np.ndarray] = None
        self._after_frames: List[np.ndarray] = []
        self._diff_frame: Optional[np.ndarray] = None
        self._hit_point: Optional[Tuple[int, int]] = None
        self._confidence: float = 0.0
        self._lock = threading.Lock()

    def capture_before(self, camera) -> bool:
        """Capture the 'before' frame. Call this just before firing."""
        frame = camera.get_frame()
        if frame is None:
            return False
        with self._lock:
            self._before_frame = frame.copy()
            self._after_frames.clear()
            self._diff_frame = None
            self._hit_point = None
            self._confidence = 0.0
        return True

    def capture_after(self, camera) -> bool:
        """Capture an 'after' frame. Call multiple times post-fire."""
        frame = camera.get_frame()
        if frame is None:
            return False
        with self._lock:
            self._after_frames.append(frame.copy())
        return True

    def detect(self) -> Optional[Tuple[int, int]]:
        """
        Run hit detection on captured frames.

        Returns:
            (x, y) pixel coordinates of detected hit, or None.
        """
        if not CV2_AVAILABLE:
            return None

        with self._lock:
            if self._before_frame is None or not self._after_frames:
                return None

            before_gray = cv2.cvtColor(self._before_frame, cv2.COLOR_BGR2GRAY)
            before_gray = cv2.GaussianBlur(before_gray, (self.BLUR_KERNEL, self.BLUR_KERNEL), 0)

            best_hit = None
            best_confidence = 0.0
            best_diff = None

            for after_frame in self._after_frames:
                after_gray = cv2.cvtColor(after_frame, cv2.COLOR_BGR2GRAY)
                after_gray = cv2.GaussianBlur(after_gray, (self.BLUR_KERNEL, self.BLUR_KERNEL), 0)

                # Absolute difference
                diff = cv2.absdiff(before_gray, after_gray)

                # Threshold
                _, thresh = cv2.threshold(diff, self.DIFF_THRESHOLD, 255, cv2.THRESH_BINARY)

                # Check overall change percentage — reject if too little (noise) or too much (lighting)
                total_pixels = thresh.shape[0] * thresh.shape[1]
                changed_pixels = cv2.countNonZero(thresh)
                change_pct = changed_pixels / total_pixels * 100

                if change_pct < self.MIN_CHANGE_PCT:
                    # Not enough change — likely no water was fired or too subtle
                    print(f"[HitDetector] Rejected: only {change_pct:.2f}% changed (min {self.MIN_CHANGE_PCT}%)")
                    continue

                if change_pct > self.MAX_CHANGE_PCT:
                    # Too much change — lighting shift or camera shake, not a splash
                    print(f"[HitDetector] Rejected: {change_pct:.2f}% changed (max {self.MAX_CHANGE_PCT}%) — scene-wide change")
                    continue

                # Morphological cleanup — heavier to remove scattered noise
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
                thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)   # Remove small dots
                thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)  # Fill small gaps

                # Find contours
                contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL,
                                               cv2.CHAIN_APPROX_SIMPLE)

                # Filter by area and find the largest valid contour
                for c in contours:
                    area = cv2.contourArea(c)
                    if self.MIN_CONTOUR_AREA <= area <= self.MAX_CONTOUR_AREA:
                        if area > best_confidence:
                            M = cv2.moments(c)
                            if M["m00"] > 0:
                                cx = int(M["m10"] / M["m00"])
                                cy = int(M["m01"] / M["m00"])
                                best_hit = (cx, cy)
                                best_confidence = area
                                best_diff = diff

            if best_hit:
                print(f"[HitDetector] Hit confirmed: ({best_hit[0]},{best_hit[1]}) confidence={best_confidence:.0f}px²")
            else:
                print(f"[HitDetector] No valid hit found")

            self._hit_point = best_hit
            self._confidence = best_confidence
            if best_diff is not None:
                self._diff_frame = best_diff

            return best_hit

    def get_annotated_frame(self) -> Optional[np.ndarray]:
        """
        Get the 'after' frame annotated with hit detection overlay.

        Shows:
        - Green circle at detected hit point
        - Red crosshair at aim point (if set)
        - Diff heatmap overlay
        """
        with self._lock:
            if not self._after_frames:
                return None

            frame = self._after_frames[-1].copy()

            # Overlay diff heatmap (subtle)
            if self._diff_frame is not None:
                heatmap = cv2.applyColorMap(self._diff_frame, cv2.COLORMAP_JET)
                # Only show where diff is significant
                mask = self._diff_frame > self.DIFF_THRESHOLD
                frame[mask] = cv2.addWeighted(frame, 0.5, heatmap, 0.5, 0)[mask]

            # Draw hit point
            if self._hit_point:
                cx, cy = self._hit_point
                cv2.circle(frame, (cx, cy), 15, (0, 255, 0), 2)
                cv2.circle(frame, (cx, cy), 3, (0, 255, 0), -1)
                cv2.putText(frame, f"HIT ({cx},{cy})",
                           (cx + 20, cy - 10), cv2.FONT_HERSHEY_SIMPLEX,
                           0.6, (0, 255, 0), 2)

            return frame

    def get_before_frame(self) -> Optional[np.ndarray]:
        """Return the before frame for UI comparison."""
        with self._lock:
            return self._before_frame.copy() if self._before_frame is not None else None

    def get_state(self) -> dict:
        """Return detection state for the API."""
        with self._lock:
            return {
                "has_before": self._before_frame is not None,
                "after_count": len(self._after_frames),
                "hit_detected": self._hit_point is not None,
                "hit_x": self._hit_point[0] if self._hit_point else None,
                "hit_y": self._hit_point[1] if self._hit_point else None,
                "confidence": round(self._confidence, 1),
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
    1. Retry with longer burst (0.8s instead of 0.4s)
    2. Lower detection threshold (from 40 → 20)
    3. Skip point, use remaining points for offset
    """

    # Configuration
    N_POINTS = 10             # Number of calibration points
    FIRE_DURATION = 0.4       # Default fire pulse (seconds)
    RETRY_DURATION = 0.8      # Longer burst for retry
    SETTLE_TIME = 1.5         # Seconds to wait after servo move
    POST_FIRE_DELAYS = [0.3, 0.6, 1.0]  # Capture intervals after firing
    MAX_RETRIES = 2           # Max retries per point (total 3 attempts)

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
        Fire at a target with retry logic (SW-001 §2.7).

        Every attempt uses the same standard solenoid pulse via AccumulatorManager
        (wait for Target PSI → solenoid-only shot → recharge before return).
        Retries only lower the hit-detection threshold — never a longer pump burst.
        """
        original_threshold = self.detector.DIFF_THRESHOLD

        for attempt in range(self.MAX_RETRIES + 1):
            if not self._running:
                return {"success": False, "skipped": True}

            if attempt == 0:
                self.detector.DIFF_THRESHOLD = original_threshold
                attempt_desc = "standard pulse"
            elif attempt == 1:
                self.detector.DIFF_THRESHOLD = original_threshold
                attempt_desc = "retry same pulse"
            else:
                self.detector.DIFF_THRESHOLD = max(15, original_threshold // 2)
                attempt_desc = "lower threshold"

            self._update(f"Point {point_idx+1}: Waiting for PSI / firing ({attempt_desc})...")

            # Capture before frame
            self.detector.capture_before(self._sniper_cam)

            # Pressure-gated solenoid shot (blocks until recharged)
            pulse_ms = self._accum.DEFAULT_PULSE_SEC * 1000.0
            self._update(
                f"Point {point_idx+1}: Solenoid pulse {pulse_ms:.0f}ms ({attempt_desc})...")
            fire_result = self._accum.fire()  # shared standard pulse from settings
            try:
                from activity_log import log_event
                log_event("AUTOCAL_FIRE", point=point_idx + 1, attempt=attempt + 1,
                          status=fire_result.get("status"),
                          pulse_ms=fire_result.get("duration_ms"),
                          elapsed_ms=fire_result.get("elapsed_ms"),
                          psi_before=fire_result.get("psi_before"),
                          psi_after=fire_result.get("psi_after"))
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

            time.sleep(0.15)  # brief settle after solenoid close

            # Capture after frames
            for delay in self.POST_FIRE_DELAYS:
                time.sleep(delay)
                self.detector.capture_after(self._sniper_cam)

            # Detect hit
            hit = self.detector.detect()

            # Restore threshold
            self.detector.DIFF_THRESHOLD = original_threshold

            if hit:
                # Success! Compute offset and update table
                hit_px, hit_py = hit
                point = CalibrationPoint(
                    aim_pitch=pitch, aim_yaw=yaw,
                    aim_px=aim_px, aim_py=aim_py,
                    hit_px=hit_px, hit_py=hit_py,
                    hit_confirmed=True,
                    distance_m=self._lidar.read_distance(),
                    note=f"auto-cal point {point_idx+1} (attempt {attempt+1})"
                )
                point.compute_offset()
                self.table.add_point(point)

                self._add_log({
                    "type": "hit",
                    "point": point_idx + 1,
                    "attempt": attempt + 1,
                    "aim": f"({aim_px},{aim_py})",
                    "hit": f"({hit_px},{hit_py})",
                    "offset_pitch": round(point.offset_pitch, 2),
                    "offset_yaw": round(point.offset_yaw, 2),
                    "running_offset": f"P={self.table.offset_pitch:.2f}° Y={self.table.offset_yaw:.2f}°",
                    "message": f"✅ Point {point_idx+1}: Hit detected at ({hit_px},{hit_py}). "
                              f"Offset: P={point.offset_pitch:.2f}° Y={point.offset_yaw:.2f}°"
                })

                self._update(
                    f"Point {point_idx+1}: ✅ Hit! "
                    f"Running offset: P={self.table.offset_pitch:.2f}° Y={self.table.offset_yaw:.2f}°")
                return {"success": True, "skipped": False}

            else:
                self._add_log({
                    "type": "miss",
                    "point": point_idx + 1,
                    "attempt": attempt + 1,
                    "attempt_desc": attempt_desc,
                    "message": f"❌ Point {point_idx+1}: No hit detected ({attempt_desc})"
                              + (" — retrying..." if attempt < self.MAX_RETRIES else " — skipping.")
                })

                if attempt < self.MAX_RETRIES:
                    self._update(f"Point {point_idx+1}: Miss — retrying with {attempt_desc}...")
                    time.sleep(0.5)  # Brief pause before retry

        # All retries exhausted
        self._add_log({
            "type": "skip",
            "point": point_idx + 1,
            "message": f"⏭ Point {point_idx+1}: Skipped after {self.MAX_RETRIES + 1} attempts"
        })
        self._update(f"Point {point_idx+1}: Skipped (no hit detected after retries)")
        return {"success": False, "skipped": True}

    def _phase_finalize(self):
        """Phase 3: Save results and report."""
        self.table.save()

        summary = (
            f"Calibration complete! "
            f"{self._success_count} hits, {self._skip_count} skipped, "
            f"{self._fail_count} failed. "
            f"Final offset: P={self.table.offset_pitch:.2f}° Y={self.table.offset_yaw:.2f}°"
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

        # Return to center
        self._gimbal.center()

        with self._lock:
            self._phase = "complete"
            self._point_index = self._total_points
            self._current_status = summary

        print(f"[AutoCal] {summary}")

