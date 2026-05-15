# Implements: SW-001 §2.1 — ScoutAgent
import cv2
import threading
import json
import os
import time

class ScoutVision:
    """
    Pipeline 1: The Scout
    High-speed motion tracker using OpenCV MOG2.
    Runs in a dedicated background thread to prevent blocking.
    """
    def __init__(self, config_path="scout_config.json"):
        self.config_path = config_path
        self.history = 500
        self.threshold = 16
        self.min_area = 500
        
        self.load_config()
        
        self.target_x = None
        self.target_y = None
        
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._cap = None
        
        self.backSub = cv2.createBackgroundSubtractorMOG2(
            history=self.history, 
            varThreshold=self.threshold, 
            detectShadows=False
        )

    def load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    self.history = config.get("history", 500)
                    self.threshold = config.get("threshold", 16)
                    self.min_area = config.get("min_area", 500)
                print(f"[ScoutVision] Loaded config: H={self.history}, T={self.threshold}, A={self.min_area}")
            except Exception as e:
                print(f"[ScoutVision] Failed to load config: {e}")
        else:
            print("[ScoutVision] Config not found, using defaults.")

    def start(self):
        if self._running:
            return
            
        # GStreamer pipeline with drop=true max-buffers=1 for strict memory constraint
        pipeline = (
            "nvarguscamerasrc sensor-id=0 ! "
            "video/x-raw(memory:NVMM), width=1280, height=800, format=NV12, framerate=120/1 ! "
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

    def _process_loop(self):
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        
        while self._running:
            ret, frame = self._cap.read()
            if not ret:
                time.sleep(0.01)
                continue
                
            fgMask = self.backSub.apply(frame)
            fgMask = cv2.morphologyEx(fgMask, cv2.MORPH_OPEN, kernel)
            
            contours, _ = cv2.findContours(fgMask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            largest_area = 0
            best_cx, best_cy = None, None
            
            for contour in contours:
                area = cv2.contourArea(contour)
                if area >= self.min_area and area > largest_area:
                    largest_area = area
                    M = cv2.moments(contour)
                    if M["m00"] > 0:
                        best_cx = int(M["m10"] / M["m00"])
                        best_cy = int(M["m01"] / M["m00"])
            
            with self._lock:
                self.target_x = best_cx
                self.target_y = best_cy

    def get_target(self):
        """Returns (X, Y) of the largest moving contour, or (None, None)."""
        with self._lock:
            return self.target_x, self.target_y

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join()
        if self._cap:
            self._cap.release()
        print("[ScoutVision] Stopped.")
