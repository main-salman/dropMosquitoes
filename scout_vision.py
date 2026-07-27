# Implements: SW-001 §2.1 — ScoutAgent
import cv2
import threading
import json
import os
import time
from collections import deque


class ScoutVision:
    """
    Pipeline 1: The Scout
    High-speed motion tracker using OpenCV MOG2.
    Runs in a dedicated background thread to prevent blocking.

    Outputs:
      - (x, y) pixel coordinates of the highest-confidence moving blob
      - (vx, vy) velocity vector in pixels/sec (trajectory prediction)
    """
    # Number of past positions to keep for velocity smoothing
    VELOCITY_WINDOW = 5

    def __init__(self, config_path="scout_config.json", settings_path="settings.json"):
        self.config_path = config_path
        self.settings_path = settings_path
        self.history = 500
        self.threshold = 16
        self.min_area = 500
        self.detect_shadows = False
        self.dead_zone_frac = 0.15

        self.load_config()

        self.target_x = None
        self.target_y = None
        self.velocity_x = 0.0  # px/sec
        self.velocity_y = 0.0  # px/sec
        self.latest_frame = None

        # Ring buffer for trajectory smoothing: (x, y, timestamp)
        self._position_history = deque(maxlen=self.VELOCITY_WINDOW)

        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._cap = None

        self.backSub = cv2.createBackgroundSubtractorMOG2(
            history=self.history,
            varThreshold=self.threshold,
            detectShadows=self.detect_shadows
        )

    def _apply_scout_dict(self, config: dict):
        self.history = int(config.get("history", 500))
        self.threshold = int(config.get("threshold", 16))
        self.min_area = int(config.get("min_area", 500))
        self.detect_shadows = bool(config.get("detect_shadows", False))
        # Fraction of half-frame ignored around center (0.15 ≈ middle 30% box)
        self.dead_zone_frac = float(config.get("dead_zone_frac", 0.15))

    def load_config(self):
        """Prefer settings.json scout section (SW-001 §2.11); else scout_config.json."""
        if os.path.exists(self.settings_path):
            try:
                with open(self.settings_path, 'r') as f:
                    data = json.load(f)
                scout = data.get("scout") if isinstance(data, dict) else None
                if isinstance(scout, dict) and scout:
                    self._apply_scout_dict(scout)
                    print(f"[ScoutVision] Loaded settings.scout: "
                          f"H={self.history}, T={self.threshold}, A={self.min_area}")
                    return
            except Exception as e:
                print(f"[ScoutVision] settings.json skip: {e}")

        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                self._apply_scout_dict(config)
                print(f"[ScoutVision] Loaded {self.config_path}: "
                      f"H={self.history}, T={self.threshold}, A={self.min_area}")
            except Exception as e:
                print(f"[ScoutVision] Failed to load config: {e}")
        else:
            print("[ScoutVision] Config not found, using defaults.")

    def start(self, external_frames: bool = False):
        """
        Start MOG2 tracking.

        external_frames=True: do not open CSI — caller feeds frames via
        process_frame() (used by Flask hunt mode sharing scout_cam).
        """
        if self._running:
            return

        if external_frames:
            self._running = True
            self._thread = None
            self._cap = None
            print("[ScoutVision] Started (external frames — shared scout_cam).")
            return

        # GStreamer pipeline with drop=true max-buffers=1 for strict memory constraint
        # Scout: Arducam NoIR IMX219 @ 1280x720 60fps (Mode 4) — no IR-cut filter for 24/7 ops
        # Both Scout and Sniper use IMX219 sensors, detected by imx219-dual.dtbo
        pipeline = (
            "nvarguscamerasrc sensor-id=0 ! "
            "video/x-raw(memory:NVMM), width=1280, height=720, format=NV12, framerate=60/1 ! "
            "nvvidconv ! video/x-raw, format=BGRx ! "
            "videoconvert ! video/x-raw, format=BGR ! "
            "appsink drop=true max-buffers=1"
        )

        self._cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
        if not self._cap.isOpened():
            print("[ScoutVision] Warning: GStreamer failed. Trying /dev/video0...")
            self._cap = cv2.VideoCapture(0)

        if not self._cap.isOpened():
            print("[ScoutVision] Error: Cannot open Scout camera.")
            return

        self._running = True
        self._thread = threading.Thread(target=self._process_loop, daemon=True)
        self._thread.start()
        print("[ScoutVision] Started.")

    def process_frame(self, frame):
        """
        Run one MOG2 update on an externally supplied BGR frame.
        Used by HuntController with Flask CameraStream frames (SW-001 §2.13).
        """
        if frame is None or not self._running:
            return

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        fgMask = self.backSub.apply(frame)
        fgMask = cv2.morphologyEx(fgMask, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(fgMask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        largest_area = 0
        best_cx, best_cy = None, None

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < self.min_area or area <= largest_area:
                continue
            M = cv2.moments(contour)
            if M["m00"] <= 0:
                continue
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            # Center dead-zone — ignore static center noise (SW-001 §2.13)
            h, w = frame.shape[:2]
            nx = abs((cx / max(w, 1)) - 0.5)
            ny = abs((cy / max(h, 1)) - 0.5)
            if nx < self.dead_zone_frac and ny < self.dead_zone_frac:
                continue
            largest_area = area
            best_cx, best_cy = cx, cy

        now = time.monotonic()
        vx, vy = 0.0, 0.0

        if best_cx is not None and best_cy is not None:
            self._position_history.append((best_cx, best_cy, now))
            if len(self._position_history) >= 2:
                oldest = self._position_history[0]
                newest = self._position_history[-1]
                dt = newest[2] - oldest[2]
                if dt > 0.001:
                    vx = (newest[0] - oldest[0]) / dt
                    vy = (newest[1] - oldest[1]) / dt
        else:
            self._position_history.clear()

        with self._lock:
            self.target_x = best_cx
            self.target_y = best_cy
            self.velocity_x = vx
            self.velocity_y = vy
            self.latest_frame = frame.copy()

    def _process_loop(self):
        while self._running:
            ret, frame = self._cap.read()
            if not ret:
                time.sleep(0.01)
                continue
            self.process_frame(frame)

    def get_target(self):
        """Returns (X, Y) of the largest moving contour, or (None, None)."""
        with self._lock:
            return self.target_x, self.target_y

    def get_target_with_velocity(self):
        """
        Returns (x, y, vx, vy) — position + velocity vector in px/sec.
        Use vx/vy to predict where the target will be in T seconds:
            predicted_x = x + vx * T
            predicted_y = y + vy * T
        """
        with self._lock:
            return self.target_x, self.target_y, self.velocity_x, self.velocity_y

    def get_latest_frame(self):
        """Returns the latest raw BGR frame captured from the shared CSI-0 camera."""
        with self._lock:
            return self.latest_frame.copy() if self.latest_frame is not None else None

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join()
        if self._cap:
            self._cap.release()
        print("[ScoutVision] Stopped.")
