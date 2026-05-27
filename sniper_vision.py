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
            
        # Shared-camera mode: do not open CSI-1 device to prevent I2C timeout crashes.
        self._running = True
        print("[SniperVision] Shared-mode started (no independent camera opened).")

    def _capture_loop(self):
        while self._running:
            ret, frame = self._cap.read()
            if ret:
                with self._lock:
                    self._latest_frame = frame
            else:
                time.sleep(0.01)

    async def verify_target(self, frame=None) -> bool:
        """
        Grabs the passed frame (from shared Scout camera) and runs YOLO inference.
        Returns True if any of the TARGET_CLASSES is detected
        with confidence > 0.80.
        """
        if not self.model or not self._running:
            return False

        if frame is None:
            # Fallback for stub/headless mode without passed frame
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
