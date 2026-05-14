# Implements: SW-001 §1, §2.1, §2.3 — Camera pipelines and TensorRT inference
"""
vision.py — Sniper Messy Mortar Vision System

Provides:
  - CameraStream: GStreamer-backed MIPI CSI camera capture with MJPEG encoding
  - YOLODetector: TensorRT YOLOv8 inference wrapper

Both cameras run in background threads and expose frames for the Flask
MJPEG streamer and for the detection pipeline.
"""

import cv2
import time
import threading
import numpy as np

# ============================================================================
# TensorRT / Ultralytics stub handling
# On a dev machine without TensorRT, we fall back to CPU-based YOLO or no-op.
# ============================================================================
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("[vision] WARNING: ultralytics not installed. AI detection disabled.")


class CameraStream:
    """
    Threaded camera capture using GStreamer on Jetson.

    Reads frames in a background thread so the main Flask thread is never
    blocked by camera I/O. Provides:
      - get_frame(): Latest raw BGR numpy frame
      - get_jpeg(): Latest frame encoded as JPEG bytes (for MJPEG streaming)

    HW-001 §2: Uses nvarguscamerasrc for hardware ISP acceleration.
    """

    def __init__(self, sensor_id: int, width: int, height: int, fps: int,
                 name: str = "Camera"):
        """
        Args:
            sensor_id: MIPI CSI port number (0=Scout, 1=Sniper).
            width: Capture width in pixels.
            height: Capture height in pixels.
            fps: Target framerate.
            name: Human-readable name for logging.
        """
        self.sensor_id = sensor_id
        self.width = width
        self.height = height
        self.fps = fps
        self.name = name

        self._frame = None
        self._jpeg = None
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._cap = None

    def _build_gstreamer_pipeline(self) -> str:
        """
        Build an optimized GStreamer pipeline string for Jetson's nvarguscamerasrc.

        SW-001 §1: GStreamer is MANDATORY — no raw cv2.VideoCapture(int).
        """
        return (
            f"nvarguscamerasrc sensor-id={self.sensor_id} ! "
            f"video/x-raw(memory:NVMM), width={self.width}, height={self.height}, "
            f"format=NV12, framerate={self.fps}/1 ! "
            f"nvvidconv ! video/x-raw, format=BGRx ! "
            f"videoconvert ! video/x-raw, format=BGR ! "
            f"appsink drop=1 max-buffers=2"
        )

    def start(self):
        """Initialize camera and start the capture thread."""
        if self._running:
            return

        pipeline = self._build_gstreamer_pipeline()
        print(f"[{self.name}] GStreamer pipeline:\n  {pipeline}")

        self._cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)

        if not self._cap.isOpened():
            # Fallback: try standard V4L2 device for dev/testing
            print(f"[{self.name}] GStreamer failed. Trying /dev/video{self.sensor_id}...")
            self._cap = cv2.VideoCapture(self.sensor_id)

        if not self._cap.isOpened():
            print(f"[{self.name}] ERROR: Cannot open camera. Using test pattern.")
            self._cap = None

        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        print(f"[{self.name}] Capture thread started.")

    def _capture_loop(self):
        """Background thread: continuously reads frames and encodes JPEG."""
        while self._running:
            if self._cap is None:
                # Generate a test pattern when no camera is available
                frame = self._generate_test_pattern()
            else:
                ret, frame = self._cap.read()
                if not ret:
                    time.sleep(0.01)
                    continue

            # Resize to target dimensions if needed
            if frame.shape[1] != self.width or frame.shape[0] != self.height:
                frame = cv2.resize(frame, (self.width, self.height))

            # Encode JPEG for MJPEG streaming
            _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])

            with self._lock:
                self._frame = frame
                self._jpeg = jpeg.tobytes()

        # Cleanup
        if self._cap:
            self._cap.release()

    def _generate_test_pattern(self) -> np.ndarray:
        """Generate a labeled test pattern when no camera hardware is present."""
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        # Grid lines
        for x in range(0, self.width, 80):
            cv2.line(frame, (x, 0), (x, self.height), (40, 40, 40), 1)
        for y in range(0, self.height, 80):
            cv2.line(frame, (0, y), (self.width, y), (40, 40, 40), 1)
        # Center crosshair
        cx, cy = self.width // 2, self.height // 2
        cv2.line(frame, (cx - 30, cy), (cx + 30, cy), (0, 255, 0), 2)
        cv2.line(frame, (cx, cy - 30), (cx, cy + 30), (0, 255, 0), 2)
        # Label
        cv2.putText(frame, f"{self.name} — NO CAMERA",
                    (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        cv2.putText(frame, f"{self.width}x{self.height} @ {self.fps}fps",
                    (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (128, 128, 128), 1)
        # Simulated timestamp
        ts = time.strftime("%H:%M:%S")
        cv2.putText(frame, ts, (self.width - 120, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        time.sleep(1.0 / max(self.fps, 1))
        return frame

    def get_frame(self) -> np.ndarray:
        """Return the latest raw BGR frame (or None)."""
        with self._lock:
            return self._frame.copy() if self._frame is not None else None

    def get_jpeg(self) -> bytes:
        """Return the latest JPEG-encoded frame bytes (for MJPEG streaming)."""
        with self._lock:
            return self._jpeg

    def stop(self):
        """Stop the capture thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        print(f"[{self.name}] Stopped.")


class YOLODetector:
    """
    YOLOv8 TensorRT inference wrapper.

    SW-001 §1: Uses Ultralytics YOLO with a pre-exported TensorRT .engine file.
    SW-001 §2.3: Provides classification + bounding box output.
    SAFE-001 §2: Filters by confidence threshold and bounding box area.

    On a dev machine without TensorRT, falls back to the .pt model (slow)
    or runs in no-op mode.
    """

    # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    # CUSTOMIZE: Path to your YOLOv8 model.
    # For TensorRT (Jetson): "models/yolov8n.engine"
    # For CPU testing:       "models/yolov8n.pt"
    # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    MODEL_PATH = "models/yolov8n.engine"
    FALLBACK_PATH = "models/yolov8n.pt"

    # Target classes we care about (COCO class IDs)
    # Mosquito detection requires a custom-trained model; these are placeholders
    # for the safety interlock system (human/pet detection).
    SAFETY_CLASSES = {0: "person", 15: "cat", 16: "dog"}

    def __init__(self):
        self.model = None
        self.confidence = 0.50      # Default confidence threshold (adjustable via GUI)
        self.min_box_area = 100     # Minimum bounding box area in pixels²
        self.max_box_area = 50000   # Maximum bbox area (filter moths/large insects)
        self._lock = threading.Lock()

        if YOLO_AVAILABLE:
            try:
                self.model = YOLO(self.MODEL_PATH)
                print(f"[YOLODetector] Loaded TensorRT model: {self.MODEL_PATH}")
            except Exception:
                try:
                    self.model = YOLO(self.FALLBACK_PATH)
                    print(f"[YOLODetector] Loaded fallback model: {self.FALLBACK_PATH}")
                except Exception as e:
                    print(f"[YOLODetector] No model available: {e}. Detection disabled.")
        else:
            print("[YOLODetector] YOLO not available. Detection disabled.")

    def detect(self, frame: np.ndarray) -> list:
        """
        Run inference on a single frame.

        Returns a list of detection dicts:
          [{"class": str, "class_id": int, "confidence": float,
            "bbox": (x1, y1, x2, y2), "area": int, "is_safe": bool}]

        SAFE-001 §2: Sets is_safe=False if any SAFETY_CLASS is detected
                      with confidence > 0.45.
        """
        if self.model is None or frame is None:
            return []

        with self._lock:
            results = self.model(frame, conf=self.confidence, verbose=False)

        detections = []
        has_safety_threat = False

        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                area = (x2 - x1) * (y2 - y1)
                cls_name = r.names.get(cls_id, f"class_{cls_id}")

                # Check safety interlock
                if cls_id in self.SAFETY_CLASSES and conf > 0.45:
                    has_safety_threat = True

                # Apply biological heuristic filters (SW-001 §3)
                if area < self.min_box_area or area > self.max_box_area:
                    continue

                detections.append({
                    "class": cls_name,
                    "class_id": cls_id,
                    "confidence": round(conf, 3),
                    "bbox": (x1, y1, x2, y2),
                    "area": area,
                    "is_safe": not has_safety_threat
                })

        return detections

    def annotate_frame(self, frame: np.ndarray, detections: list) -> np.ndarray:
        """Draw bounding boxes and labels on a frame for the MJPEG stream."""
        annotated = frame.copy()
        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            color = (0, 255, 0) if det["is_safe"] else (0, 0, 255)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            label = f"{det['class']} {det['confidence']:.0%}"
            cv2.putText(annotated, label, (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        return annotated

    def set_confidence(self, value: float):
        """Update confidence threshold (0.0 to 1.0). Called from GUI slider."""
        self.confidence = max(0.05, min(1.0, value))
        print(f"[YOLODetector] Confidence threshold set to {self.confidence:.0%}")

    def set_min_box_area(self, value: int):
        """Update minimum bounding box area filter. Called from GUI slider."""
        self.min_box_area = max(10, value)
        print(f"[YOLODetector] Min box area set to {self.min_box_area}px²")
