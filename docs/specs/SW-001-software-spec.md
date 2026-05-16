# SW-001: Software Specification

**Status:** APPROVED  
**Version:** 4.0  
**Last Updated:** 2026-05-15  
**Owner:** Salman

## 1. Runtime Environment

- **Platform:** NVIDIA Jetson Orin Nano SUPER (JetPack 6.0)
- **Python:** 3.10+
- **Inference:** YOLOv8n exported to TensorRT `.engine` (FP16)
- **Camera Pipeline:** GStreamer `nvarguscamerasrc` (mandatory — no raw `cv2.VideoCapture`)
- **Orchestrator:** `main.py` — asyncio event loop managing all agents

## 2. Agent Architecture

All agents run as threaded modules coordinated by the asyncio orchestrator in `main.py`.

### 2.1 ScoutAgent (`scout_vision.py`)
- **Input:** `/dev/video0` (OV9281 @ 120FPS via GStreamer `nvarguscamerasrc sensor-id=0`)
- **Pipeline:** `appsink drop=true max-buffers=1` (mandatory for 8GB memory constraint)
- **Processing:** OpenCV MOG2 Background Subtraction
- **Config:** Reads tuning parameters from `scout_config.json` (exported by Sentry Control Center)
- **Output:** `(x, y)` pixel coordinates + `(vx, vy)` velocity vector (px/sec) via `get_target_with_velocity()`
- **Trajectory:** Ring buffer of last 5 positions calculates smoothed velocity for predictive targeting
- **Threading:** Dedicated background thread; main loop polls via thread-safe lock

### 2.2 TurretAgent (`gimbal_controller.py`)
- **Input:** `(x, y)` pixel coordinates from ScoutAgent
- **Processing:** `pixel_to_angle()` conversion, pitch/yaw boundary enforcement (±20° pitch, ±80° yaw)
- **Output:** Serial command string to Storm32 via `/dev/ttyTHS0` @ 115200 baud
- **Async:** `aim_async()` and `sweep_async()` dispatch serial writes via `run_in_executor` — never blocks asyncio loop
- **Sweep:** `sweep()` performs multi-step linear gimbal motion from point A to B, used during Stream-and-Sweep firing

### 2.3 SniperAgent (`sniper_vision.py`)
- **Input:** `/dev/video1` (IMX219 @ 30FPS via GStreamer `nvarguscamerasrc sensor-id=1`)
- **Pipeline:** `appsink drop=true max-buffers=1`
- **Processing:** YOLOv8 TensorRT classification
- **Output:** `True` if `class == 'Mosquito'` AND `confidence > 0.80`, else `False`
- **Threading:** Dedicated capture thread; inference called via `verify_target()`

### 2.4 TriggerAgent (`weapon_system.py`)
- **Input:** Boolean from SniperAgent
- **Guard:** `target_locked == True`
- **Output:** GPIO BCM 17 (IDC40P Terminal 11) HIGH for 400ms (Stream-and-Sweep), then LOW
- **Pump:** 12V DC Diaphragm Pump (ECO-2026-003) — ~100ms mechanical spin-up delay
- **Modes:**
  - `fire(duration)` — Blocking pulse (legacy)
  - `fire_sweep(duration)` — Non-blocking: starts pump in background thread, returns immediately so gimbal can sweep concurrently
  - `cease_fire()` — Emergency stop, immediately sets relay LOW
- **Safety:** Relay defaults to LOW at boot. `try/finally` ensures LOW on crash. Complies with SAFE-001 §2.

### 2.5 LiDAR Polling (`hardware.py — LiDARController`)
- **Input:** I2C Bus 1, address `0x10` (Benewake TF-Luna)
- **Processing:** Background thread reads distance at ~100Hz
- **Output:** `distance_m` (float), `signal_strength` (int) available via `read_distance()`

### 2.6 Predictive Lead Engine (`hardware.py — compute_predictive_lead()`)

The following stages execute **in sequence** for every fire decision:

#### 2.6.1 Velocity Vectoring (`vision.py`)
- Track bounding box centroid across **N consecutive frames** (minimum 3, ideally 5–8 at 120 FPS).
- Compute angular velocity `(ω_pitch, ω_yaw)` using the camera's known FOV and resolution.

#### 2.6.2 Time-of-Flight Lead
- Using the LiDAR's Z-distance `d`, compute water stream's **Time-of-Flight (ToF)**:
  ```
  ToF = d / (v₀ · cos(α))
  ```
  where `v₀` = water exit velocity (~7 m/s), `α` = current pitch angle.
- Apply target's velocity over the ToF window to predict future position:
  ```
  lead_yaw   = ω_yaw  × ToF   (degrees)
  lead_pitch = ω_pitch × ToF   (degrees)
  ```

#### 2.6.3 Gravity Airburst Offset (Final Stage)
- After velocity lead offsets, apply `AIRBURST_PITCH_OFFSET` (default +12°) to the **final pitch angle**.
- This intentionally over-aims so the pressurized stream arcs slightly above the target, compensating for gravity drop over distance.
- Execution order:
  1. `pixel_to_angle()` → raw pitch/yaw
  2. `+ lead_pitch / lead_yaw` → velocity-corrected aim point
  3. `+ airburst_offset_deg` → final corrected pitch
- The offset is dynamically tunable via the Flask dashboard slider (0° to +30°).

## 3. Orchestration Sequence — "Stream and Sweep" (`main.py`)

```
Scout Detect → Predict Position → Gimbal Aim → Sniper Verify → [ Fire Pump + Sweep Gimbal ] (parallel)
```

1. `scout_vision.get_target_with_velocity()` returns `(x, y, vx, vy)` or `(None, None, 0, 0)`
2. **Predict:** `pred_x = x + vx × LOOKAHEAD`, `pred_y = y + vy × LOOKAHEAD` (default 150ms lookahead)
3. `pixel_to_angle(pred_x, pred_y)` maps predicted position to degrees
4. Airburst offset added to predicted pitch
5. `gimbal.aim_async(pitch, yaw)` — non-blocking serial write
6. 50ms settle wait (reduced from 200ms — diaphragm pump spin-up covers remaining settle)
7. `sniper_vision.verify_target()` runs YOLOv8 inference
8. If TRUE → **two actions fire in parallel:**
   - `weapon.fire_sweep(0.4)` — starts pump in background thread (non-blocking)
   - `gimbal.sweep_async(aim → aim+overshoot)` — sweeps along velocity vector
   - Pump spin-up (~100ms) occurs while gimbal begins sweep → water exits mid-sweep
9. 1.0s cooldown prevents rapid re-firing

## 4. Safety Interlocks (see SAFE-001)

- Biological heuristic: bounding box too large → ignore (moth/June bug filter)
- GPIO fail-safe: `try/finally` ensuring BCM 17 LOW on crash
- Death Spiral prevention: yaw hard-limited ±80°, pitch ±20°
- Airburst offset clamped: final pitch cannot exceed `PITCH_LIMIT` (±20°)

> **Detection Strategy:** Mosquitoes are not in the COCO-80 class set. The primary
> targeting method is **MOG2 motion detection** (ScoutAgent §2.1), which fires at
> any small, fast-moving object in the field of view. The system intentionally
> targets **any flying insect in the 1×–3× mosquito body size range** (roughly
> 3–20mm, mapped to bounding box area thresholds at the given LiDAR distance).
> YOLOv8 TensorRT is used by the SniperAgent (§2.3) for secondary classification
> and large-object rejection only (e.g., filtering out birds, leaves, moths).

## 5. Physics Model

- **Mounting:** Overhead, 8–10 feet (2.4–3.0m) above ground level, firing DOWNWARD
- **Effective Range:** 1.0 – 5.0 meters (LiDAR-measured slant distance to background)
- **Water Exit Velocity:** ~7 m/s
- **Pump Type:** 12V DC Diaphragm Pump (ECO-2026-003), 60 PSI, self-priming
- **Pump Spin-Up:** ~100ms mechanical delay (diaphragm motor to full pressure)
- **Sweep Duration:** 400ms total (100ms spin-up + 300ms active spray)
- **Firing Mode:** "Stream and Sweep" — pump fires while gimbal sweeps along target's predicted flight path, creating a moving wall of water
- **Airburst Strategy:** Pitch offset lobs the 60 PSI pressurized stream slightly above the target's projected flight path, compensating for gravity drop at range. Combined with the sweep, this creates a curtain of water across the flight path.
- **Airburst Offset:** Default +12° above calculated target pitch (tunable 0°–30° via dashboard)

## 6. Calibration Procedure

1. Boot Jetson, wait for 15s relay boot delay
2. Run `phantom_ping.py` to fire test shots at known distances
3. Scout camera tracks water droplet trajectory
4. System generates lookup table (distance → optimal airburst offset)
5. Store calibration in `calibration.json`

## 7. Training & Tuning Pipeline

Training and tuning are performed on a **separate Windows workstation** (RTX 3070 8GB), NOT on the Jetson.

### 7.1 Scout Tuning (OpenCV — No AI)
- Tool: `tools/sentry_control_center/app.py` Tab 1
- Upload test video → adjust MOG2 sliders → export `scout_config.json`
- Copy `scout_config.json` to Jetson project root

### 7.2 Sniper Training (YOLOv8 — GPU-Intensive)
- Tool: `tools/sentry_control_center/app.py` Tab 2
- Provide labeled dataset (`data.yaml` from Roboflow)
- Train model → collect `best.pt`
- Copy `best.pt` to Jetson → convert to TensorRT `.engine` (see `gemini.md` §3)
