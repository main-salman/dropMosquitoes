# Implements: SW-001 §2.3 — SniperAgent
import cv2
import os
import threading
import time

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("[SniperVision] WARNING: ultralytics not installed. AI disabled.")

class SniperVision:
    """
    Pipeline 2: The Sniper
    Precision classifier using YOLOv8.
    Auto-detects TensorRT .engine for maximum FPS, falls back to .pt.
    """
    # Implements: SW-001 §2.3 — Sourced from Roboflow tiger-emltm/insects-9yf6s v2 dataset
    TARGET_CLASSES = {
        'spider', 'bees', 'butterfly', 'mantis', 'ant', 'beetle', 'caterpillar',
        'centipedes', 'cockroach', 'dragonfly', 'fly', 'grasshopper',
        'ladybug', 'mosquito', 'wasp'
    }

    def __init__(self, model_path="best.pt"):
        # Try TensorRT engine first for maximum FPS on Jetson
        engine_path = model_path.replace('.pt', '.engine')
        if os.path.exists(engine_path):
            self.model_path = engine_path
            print(f"[SniperVision] Found TensorRT engine: {engine_path}")
        else:
            self.model_path = model_path
            if YOLO_AVAILABLE:
                print(f"[SniperVision] No .engine found, using PyTorch: {model_path}")
                print(f"[SniperVision] TIP: Convert with: model.export(format='engine', half=True)")
        
        self.model = None
        self.confidence_threshold = 0.80
        
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._cap = None
        self._latest_frame = None

        if YOLO_AVAILABLE:
            try:
                self.model = YOLO(self.model_path)
                print(f"[SniperVision] Loaded model: {self.model_path}")
            except Exception as e:
                print(f"[SniperVision] Failed to load model {self.model_path}: {e}")

    def start(self):
        if self._running:
            return
            
        # GStreamer pipeline with drop=true max-buffers=1 for strict memory constraint
        # Sniper: Arducam NoIR IMX219 w/ Motorized IR-Cut @ 1280x720 60fps (Mode 4) on CSI-1
        pipeline = (
            "nvarguscamerasrc sensor-id=1 ! "
            "video/x-raw(memory:NVMM), width=1280, height=720, format=NV12, framerate=60/1 ! "
            "nvvidconv ! video/x-raw, format=BGRx ! "
            "videoconvert ! video/x-raw, format=BGR ! "
            "appsink drop=true max-buffers=1"
        )

        import os
        is_jetson = os.path.exists("/etc/nv_tegra_release") or os.path.exists("/proc/device-tree/compatible")

        if is_jetson and os.path.exists("/dev/video1"):
            print(f"[SniperVision] GStreamer pipeline:\n  {pipeline}")
            self._cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
            if not self._cap.isOpened():
                print("[SniperVision] Warning: GStreamer failed. Trying /dev/video1...")
                self._cap = cv2.VideoCapture(1)
        else:
            print("[SniperVision] Stub/Dev mode: Camera index 1 not found. Using simulated stream.")
            self._cap = None

        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        print("[SniperVision] Started.")

    def _capture_loop(self):
        while self._running:
            if self._cap is None:
                frame = self._generate_test_pattern()
                ret = True
            else:
                ret, frame = self._cap.read()

            if ret:
                with self._lock:
                    self._latest_frame = frame
                if self._cap is None:
                    time.sleep(1.0 / 60.0)
            else:
                time.sleep(0.01)

    def _generate_test_pattern(self):
        import numpy as np
        height, width = 720, 1280
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        # Grid lines
        for x in range(0, width, 80):
            cv2.line(frame, (x, 0), (x, height), (30, 30, 40), 1)
        for y in range(0, height, 80):
            cv2.line(frame, (0, y), (width, y), (30, 30, 40), 1)
        # Crosshair
        cx, cy = width // 2, height // 2
        cv2.line(frame, (cx - 30, cy), (cx + 30, cy), (0, 0, 255), 2)
        cv2.line(frame, (cx, cy - 30), (cx, cy + 30), (0, 0, 255), 2)
        # Label
        cv2.putText(frame, "Sniper (CSI-1) — NO CAMERA",
                    (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        return frame

    async def verify_target(self, frame=None) -> bool:
        """
        Grabs the latest frame from its own gimbal-mounted CSI-1 camera and runs YOLO inference.
        Returns True if any of the TARGET_CLASSES is detected with confidence > 0.80.
        """
        if not self.model or not self._running:
            return False

        if frame is None:
            with self._lock:
                if self._latest_frame is None:
                    return False
                frame_to_process = self._latest_frame.copy()
        else:
            frame_to_process = frame.copy()

        # Run inference (blocking, but we are inside an async wrapper usually or run_in_executor)
        results = self.model(frame_to_process, conf=self.confidence_threshold, verbose=False)
        
        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                cls_name = r.names.get(cls_id, f"class_{cls_id}")
                
                # Check condition case-insensitively
                if cls_name.lower() in self.TARGET_CLASSES and conf > self.confidence_threshold:
                    print(f"[SniperVision] Target Verified: {cls_name} ({conf:.2f})")
                    return True

        return False

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join()
        if self._cap:
            self._cap.release()
        print("[SniperVision] Stopped.")

