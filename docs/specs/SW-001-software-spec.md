# SW-001: Software Specification

**Status:** DRAFT  
**Version:** 1.0  
**Last Updated:** 2026-05-14  
**Owner:** Salman

## 1. Runtime Environment

- **Platform:** NVIDIA Jetson Orin Nano SUPER (JetPack 6.0)
- **Python:** 3.10+
- **Inference:** YOLOv8n exported to TensorRT `.engine` (FP16)
- **Camera Pipeline:** GStreamer (mandatory — no raw `cv2.VideoCapture`)

## 2. Agent Architecture

All agents run as asynchronous processes communicating via `queue.Queue` (thread-safe).

### 2.1 ScoutAgent (`scout_vision.py`)
- **Input:** `/dev/video0` (OV9281 @ 120FPS via GStreamer)
- **Processing:** OpenCV MOG2 Background Subtraction
- **Output:** `(x, y, vx, vy)` of highest-confidence moving blob → `scout_queue`

### 2.2 TurretAgent (`gimbal_control.py`)
- **Input:** `scout_queue`
- **Processing:** Pixel-to-degree conversion, yaw boundary enforcement (±130°)
- **Output:** Serial commands to Storm32 via `/dev/ttyTHS0` @ 115200

### 2.3 SniperAgent (`sniper_logic.py`)
- **Input:** `/dev/video1` (IMX219 @ 60FPS via GStreamer)
- **Processing:** YOLOv8 TensorRT classification + parabolic intercept + vector lead
- **Output:** `target_locked` boolean + corrected angles → `fire_queue`

### 2.4 TriggerAgent (`weapons_hot.py`)
- **Input:** `fire_queue`
- **Guard:** `target_locked == True` AND `human_in_frame == False`
- **Output:** GPIO 18 HIGH for 300ms, then LOW

## 3. Safety Interlocks (see SAFE-001)

- Human/pet override: `person`, `dog`, `cat` confidence > 0.45 → instant `is_safe_to_fire = False`
- Biological heuristic: bounding box too large → ignore (moth/June bug filter)
- GPIO fail-safe: `try/finally` ensuring pin LOW on crash
- Death Spiral prevention: yaw hard-limited ±130°, rapid unwind if target crosses 180°

## 4. Physics Model

- **Effective Range:** 1.0 – 5.0 meters
- **Water Exit Velocity:** ~7 m/s
- **Pump Pulse Duration:** 300ms constant
- **Trajectory:** Parabolic (pitch-up required for gravity drop)
- **Wind Calibration:** "Phantom Ping" — test shot, track droplet drift, update offset

## 5. Calibration Procedure

1. Boot Jetson, wait for 15s relay boot delay
2. Run `phantom_ping.py` to fire test shots at known distances
3. Scout camera tracks water droplet trajectory
4. System generates parabolic lookup table (distance → pitch angle)
5. Store calibration in `calibration.json`
