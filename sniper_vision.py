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
            
        pipeline = (
            "nvarguscamerasrc sensor-id=1 ! "
            "video/x-raw(memory:NVMM), width=1920, height=1080, format=NV12, framerate=30/1 ! "
            "nvvidconv ! video/x-raw, format=BGRx ! "
            "videoconvert ! video/x-raw, format=BGR ! "
            "appsink drop=true max-buffers=1"
        )
        
        self._cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
        if not self._cap.isOpened():
            print("[SniperVision] Warning: GStreamer failed. Trying /dev/video1...")
            self._cap = cv2.VideoCapture(1)
            
        if not self._cap.isOpened():
            print("[SniperVision] Error: Cannot open Sniper camera.")
            return

        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        print("[SniperVision] Started.")

    def _capture_loop(self):
        while self._running:
            ret, frame = self._cap.read()
            if ret:
                with self._lock:
                    self._latest_frame = frame
            else:
                time.sleep(0.01)

    async def verify_target(self) -> bool:
        """
        Grabs the latest frame and runs YOLO inference.
        Returns True if any of the 14 verified backyard bug classes is detected
        with confidence > 0.80.
        """
        if not self.model or not self._running:
            return False

        with self._lock:
            if self._latest_frame is None:
                return False
            frame_to_process = self._latest_frame.copy()

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
