# SW-001: Software Specification

**Status:** DRAFT  
**Version:** 2.0  
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

### 2.5 LiDAR Polling (`hardware.py — LiDARController`)
- **Input:** I2C Bus 1, address `0x10` (Benewake TF-Luna)
- **Processing:** Background thread reads distance at ~100Hz
- **Output:** `distance_m` (float), `signal_strength` (int) available via `read_distance()`

### 2.6 Ballistic Offset Engine (`hardware.py — compute_ballistic_offset()`)
- **Input:** Raw pitch/yaw from pixel_to_angle() + Z-distance from LiDAR
- **Processing:** Overhead parabolic drop correction (see §4)
- **Output:** Corrected `(pitch, yaw)` tuple compensating for gravity drop

### 2.7 Predictive Lead Engine — Ballistics Math (CRITICAL)

The following three stages execute **in sequence** for every fire decision. Together they answer: *"Where will the mosquito be when the water arrives?"*

#### 2.7.1 Velocity Vectoring (`vision.py`)
- Track bounding box centroid across **N consecutive frames** (minimum 3, ideally 5–8 at 120 FPS).
- Compute a 2D **Velocity Vector** `(vx, vy)` in pixels/second using a simple linear regression or exponential moving average of the centroid deltas.
- Convert pixel velocity to **angular velocity** `(ω_pitch, ω_yaw)` using the camera's known FOV and resolution.
- Output is passed alongside `(x, y)` in `scout_queue` — already partially implemented as `(x, y, vx, vy)` in §2.1.

#### 2.7.2 Time-of-Flight Lead (`hardware.py`)
- Using the LiDAR's Z-distance `d`, compute the water stream's **Time-of-Flight (ToF)**:
  ```
  ToF = d / (v₀ · cos(α))
  ```
  where `v₀` = water exit velocity (~7 m/s), `α` = current pitch angle.
- Apply the target's Velocity Vector over the ToF window to predict where the target **will be** when the water arrives:
  ```
  lead_yaw  = ω_yaw  × ToF   (degrees)
  lead_pitch = ω_pitch × ToF   (degrees)
  ```
- Add these lead offsets to the raw gimbal Pitch/Yaw commands **before** the parabolic drop correction.

#### 2.7.3 Parabolic Drop (Final Stage)
- After the velocity lead offsets are applied, apply the Z-distance ballistic drop offset (§2.6) to the **final Pitch angle**.
- Execution order:
  1. `pixel_to_angle()` → raw pitch/yaw
  2. `+ lead_pitch / lead_yaw` → velocity-corrected aim point
  3. `+ Δpitch (gravity drop)` → final corrected pitch
- The corrected `(pitch, yaw)` is sent to the Storm32 gimbal.


## 3. Safety Interlocks (see SAFE-001)

- Human/pet override: `person`, `dog`, `cat` confidence > 0.45 → instant `is_safe_to_fire = False`
- Biological heuristic: bounding box too large → ignore (moth/June bug filter)
- GPIO fail-safe: `try/finally` ensuring pin LOW on crash
- Death Spiral prevention: yaw hard-limited ±130°, rapid unwind if target crosses 180°

## 4. Physics Model

- **Mounting:** Overhead, 8–10 feet (2.4–3.0m) above ground level, firing DOWNWARD
- **Effective Range:** 1.0 – 5.0 meters (LiDAR-measured slant distance to background)
- **Water Exit Velocity:** ~7 m/s
- **Pump Pulse Duration:** 300ms constant
- **Trajectory:** Downward parabolic — gravity ASSISTS the shot
- **Ballistic Offset:** Since the turret fires downward from overhead, gravity accelerates the water stream toward the target zone. The pitch correction is smaller than for a ground-level turret. The offset formula accounts for the downward slant angle.
- **Formula:** `Δpitch = -arctan(g · d² / (2 · v₀² · cos²(α)))` where `d` = LiDAR distance, `α` = raw pitch angle, `g` = 9.81 m/s², `v₀` = 7 m/s. Negative because gravity pulls the stream INTO the target zone (downward assist).
- **Wind Calibration:** "Phantom Ping" — test shot, track droplet drift, update offset

## 5. Calibration Procedure

1. Boot Jetson, wait for 15s relay boot delay
2. Run `phantom_ping.py` to fire test shots at known distances
3. Scout camera tracks water droplet trajectory
4. System generates parabolic lookup table (distance → pitch angle)
5. Store calibration in `calibration.json`

