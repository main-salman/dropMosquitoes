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

    def __init__(self, filepath: str = "calibration.json"):
        self.filepath = filepath
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
        """Persist calibration data to JSON."""
        data = {
            "offset_pitch": self.offset_pitch,
            "offset_yaw": self.offset_yaw,
            "last_updated": self.last_updated,
            "points": [asdict(p) for p in self.points],
        }
        with open(self.filepath, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"[Calibration] Saved {len(self.points)} points to {self.filepath}")

    def load(self) -> bool:
        """Load calibration data from JSON. Returns True if loaded."""
        if not os.path.exists(self.filepath):
            return False
        try:
            with open(self.filepath, 'r') as f:
                data = json.load(f)
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
    DIFF_THRESHOLD = 30       # Pixel intensity difference to count as "changed"
    MIN_CONTOUR_AREA = 50     # Minimum splash area in pixels²
    MAX_CONTOUR_AREA = 50000  # Maximum (reject full-frame changes like lighting)
    BLUR_KERNEL = 5           # Gaussian blur before diff (reduce noise)

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

                # Morphological cleanup
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
                thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
                thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

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
# CALIBRATION WIZARD — Step-by-step guided calibration
# ============================================================================

class CalibrationWizard:
    """
    Guided calibration state machine.

    Steps:
    1. CENTER — Verify sniper camera sees the scene correctly
    2. AIM — User clicks on a target in the sniper feed
    3. FIRE — System fires water, captures before/after
    4. VERIFY — User confirms or corrects detected hit location
    5. NEXT — Move to next calibration point or finish

    Calibration pattern: center + 4 corners (5 points total).
    """

    STEPS = ["idle", "center", "aim", "fire", "verify", "complete"]

    # Default 5-point calibration pattern (pitch, yaw) in degrees
    CALIBRATION_PATTERN = [
        (0, 0),       # Center
        (-15, -20),   # Top-left
        (-15, 20),    # Top-right
        (15, -20),    # Bottom-left
        (15, 20),     # Bottom-right
    ]

    def __init__(self, cal_table: CalibrationTable, hit_detector: HitDetector):
        self.table = cal_table
        self.detector = hit_detector
        self._step = "idle"
        self._point_index = 0
        self._current_point: Optional[CalibrationPoint] = None
        self._fire_duration = 0.4  # Default fire pulse
        self._lock = threading.Lock()

    @property
    def step(self) -> str:
        with self._lock:
            return self._step

    def start(self):
        """Start the calibration wizard."""
        with self._lock:
            self.table.clear()
            self._step = "center"
            self._point_index = 0
            self._current_point = None
        print("[Wizard] Started calibration wizard")

    def get_state(self) -> dict:
        """Return full wizard state for the UI."""
        with self._lock:
            pattern_point = self.CALIBRATION_PATTERN[self._point_index] \
                if self._point_index < len(self.CALIBRATION_PATTERN) else (0, 0)
            return {
                "step": self._step,
                "point_index": self._point_index,
                "total_points": len(self.CALIBRATION_PATTERN),
                "pattern_pitch": pattern_point[0],
                "pattern_yaw": pattern_point[1],
                "current_point": asdict(self._current_point) if self._current_point else None,
                "instructions": self._get_instructions(),
                "hit_detector": self.detector.get_state(),
                "table": self.table.to_dict(),
            }

    def _get_instructions(self) -> str:
        """Human-readable instructions for the current step."""
        if self._step == "idle":
            return "Click 'Start Calibration' to begin the guided wizard."
        elif self._step == "center":
            p, y = self.CALIBRATION_PATTERN[self._point_index]
            return (f"Point {self._point_index + 1}/{len(self.CALIBRATION_PATTERN)}: "
                    f"Aim servos to ({p}°, {y}°). "
                    f"Click 'Next' when the sniper camera shows the scene.")
        elif self._step == "aim":
            return ("Click on a visible target in the sniper feed. "
                    "Choose something easy to see (edge of a box, corner of a poster, etc.).")
        elif self._step == "fire":
            return "Ready to fire. Click 'Fire' to shoot water at the target."
        elif self._step == "verify":
            return ("Check the result. Green circle = detected hit. "
                    "Click 'Confirm' if correct, or click on the actual hit location to correct it.")
        elif self._step == "complete":
            return (f"Calibration complete! {len(self.table.points)} points recorded. "
                    f"Global offset: pitch={self.table.offset_pitch:.2f}° "
                    f"yaw={self.table.offset_yaw:.2f}°. Click 'Save' to persist.")
        return ""

    def advance_to_aim(self):
        """Move from CENTER to AIM step (user confirmed servo position)."""
        with self._lock:
            if self._step == "center":
                self._step = "aim"
                self._current_point = CalibrationPoint(
                    aim_pitch=self.CALIBRATION_PATTERN[self._point_index][0],
                    aim_yaw=self.CALIBRATION_PATTERN[self._point_index][1],
                )

    def record_aim(self, px: int, py: int):
        """User clicked on the target — record aim pixel coordinates."""
        with self._lock:
            if self._step == "aim" and self._current_point:
                self._current_point.aim_px = px
                self._current_point.aim_py = py
                self._step = "fire"

    def fire_and_detect(self, camera, relay, fire_duration: float = 0.4,
                        distance_m: float = 2.0) -> dict:
        """
        Execute the fire-and-detect sequence:
        1. Capture before frame
        2. Fire water
        3. Wait + capture after frames
        4. Run hit detection
        5. Advance to verify step

        Returns detection result dict.
        """
        # Capture before
        self.detector.capture_before(camera)

        # Fire
        relay.fire(fire_duration)
        time.sleep(fire_duration + 0.2)

        # Capture after frames at intervals
        for delay in [0.3, 0.6, 1.0]:
            time.sleep(delay)
            self.detector.capture_after(camera)

        # Detect hit
        hit = self.detector.detect()

        with self._lock:
            if self._current_point:
                self._current_point.distance_m = distance_m
                if hit:
                    self._current_point.hit_px = hit[0]
                    self._current_point.hit_py = hit[1]
                self._step = "verify"

        return self.detector.get_state()

    def verify_hit(self, confirmed: bool, corrected_px: int = None,
                   corrected_py: int = None):
        """
        User confirms or corrects the detected hit location.
        Computes offset and advances to next point.
        """
        with self._lock:
            if self._step != "verify" or not self._current_point:
                return

            if corrected_px is not None and corrected_py is not None:
                self._current_point.hit_px = corrected_px
                self._current_point.hit_py = corrected_py

            self._current_point.hit_confirmed = confirmed
            self._current_point.timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            self._current_point.compute_offset()

            # Add to table
            self.table.add_point(self._current_point)

            # Advance to next point or complete
            self._point_index += 1
            if self._point_index >= len(self.CALIBRATION_PATTERN):
                self._step = "complete"
            else:
                self._step = "center"
                self._current_point = None

    def skip_point(self):
        """Skip the current calibration point."""
        with self._lock:
            self._point_index += 1
            if self._point_index >= len(self.CALIBRATION_PATTERN):
                self._step = "complete"
            else:
                self._step = "center"
                self._current_point = None

    def reset(self):
        """Reset wizard to idle state."""
        with self._lock:
            self._step = "idle"
            self._point_index = 0
            self._current_point = None
