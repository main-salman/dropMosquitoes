# SW-001: Software Specification

**Status:** APPROVED  
**Version:** 5.0  
**Last Updated:** 2026-05-20  
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
- **Input:** `/dev/video0` (IMX219 NoIR @ 60FPS via GStreamer `nvarguscamerasrc sensor-id=0`)
- **Pipeline:** `appsink drop=true max-buffers=1` (mandatory for 8GB memory constraint)
- **Processing:** OpenCV MOG2 Background Subtraction
- **Config:** Prefers `settings.json` → `scout` section (SW-001 §2.11); falls back to legacy `scout_config.json`
- **Output:** `(x, y)` pixel coordinates + `(vx, vy)` velocity vector (px/sec) via `get_target_with_velocity()`
- **Trajectory:** Ring buffer of last 5 positions calculates smoothed velocity for predictive targeting
- **Threading:** Dedicated background thread; main loop polls via thread-safe lock

### 2.2 TurretAgent (`gimbal_controller.py`)
- **Input:** `(x, y)` pixel coordinates from ScoutAgent
- **Processing:** `pixel_to_angle()` conversion, pitch/yaw boundary enforcement (±20° pitch, ±80° yaw)
- **Output:** Binary command packet (`o323BGC` protocol) to Storm32 via UART serial `/dev/ttyTHS1` or `/dev/ttyTHS0` (auto-detected) @ 115200 baud. USB is disabled during live operations to prevent ground loops.


- **Async:** `aim_async()` and `sweep_async()` dispatch serial writes via `run_in_executor` — never blocks asyncio loop
- **Sweep:** `sweep()` performs multi-step linear gimbal motion from point A to B, used during Stream-and-Sweep firing

### 2.3 SniperAgent (`sniper_vision.py`)
- **Input:** `/dev/video1` (IMX219 @ 30FPS via GStreamer `nvarguscamerasrc sensor-id=1`)
- **Pipeline:** `appsink drop=true max-buffers=1`
- **Processing:** YOLOv8 TensorRT classification
- **Output:** `True` if `class` falls in the set of 15 verified backyard bug classes AND `confidence > 0.80`, else `False`
  *(Target classes: `spider`, `bees`, `butterfly`, `mantis`, `ant`, `beetle`, `caterpillar`, `centipedes`, `cockroach`, `dragonfly`, `fly`, `grasshopper`, `ladybug`, `mosquito`, `wasp`)*
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

#### 2.6.3 Linear Drop Compensation (Final Stage)
- After velocity lead offsets, apply `drop_offset_deg` to the **final pitch angle**.
- The turret is mounted inverted in an overhead dome enclosure, firing downward. The 45 PSI diaphragm pump fires a direct pressurized stream. Under 3m, the stream is dead-straight. Over 3m, we apply a slight negative pitch offset (aiming closer to horizon) to compensate for trajectory drop.
- Execution order:
  1. `pixel_to_angle()` → raw pitch/yaw (positive pitch = moves camera DOWN)
  2. `+ lead_pitch / lead_yaw` → velocity-corrected aim point
  3. `+ drop_offset_deg` → final corrected pitch

### 2.7 Accumulator Firing Strategy (`hardware.py — AccumulatorManager`)

The GOODRIG 12V solenoid is fed from a 0.75L pre-charged accumulator (ECO-2026-004).
The R385 pump has **no pressure switch** and must not run continuously against a
closed solenoid (deadhead → overheat), so the accumulator is charged in bursts
and the solenoid pulse releases stored pressure.

**MOSFET module 12V (HW-001 §5.5 Rev N):** Production is **automated gated CH2**
(`module_12v_hardwired=false`) after the 2N3904 buffer is installed — no operator
MODULE 12V switch. Software opens CH2 at boot/idle and closes it when armed/firing.
Interim without buffer: `hardwired=true` + jumper (manual boot switch only until
buffer is fitted).

**Physics constraint:** shot distance ∝ exit velocity ∝ √(pressure). The solenoid
pulse width sets shot *volume/duration*, NOT velocity — so consistent distance
requires firing from a **consistent pressure**, not a longer pulse.

**Charge / fire contract (ECO-004 — live fire AND auto-cal):**
1. **Pump = pressure only.** Pump runs only with solenoid **CLOSED**, until PSI ≥
   `target_psi`. Never use the pump to propel a shot.
2. **Shot = solenoid only.** Open the solenoid for the **standard pulse**
   (`default_pulse_ms`). Pump must be **OFF** for the entire open pulse (no overlap).
3. **Gate every shot:** do not open the solenoid until PSI ≥ `target_psi`
   (“pressure ready”). If `MAX_PUMP_RUN_SEC` expires without reaching target,
   refuse the shot (`pressure_not_ready`).
4. **After every shot:** re-read PSI and recharge to `target_psi` **before** the
   next shot may proceed (auto-cal and live mosquito fire).
5. **Maintain (ARMED only):** poll every `pressure_poll_sec` (factory **60 s**) and
   recharge if PSI &lt; `target_psi`. **No hysteresis** (`maintain_hysteresis_psi = 0`).
   Inactive when disarmed.
6. **Sensor fault:** disconnect / no readings while armed or firing → **disarm** and
   **alarm** (buzzer error + status `alarm`). Do not silently timed-charge shots
   after pressure-gated operation has started.
7. **Arm:** charge to `target_psi`, then start maintain. Timed
   `initial_charge_sec` / `topup_charge_sec` are arm-time fallbacks only when the
   sensor was never connected (bench/stub).

**Setpoint / persistence:** factory `target_psi` = **5 PSI** (GUI 1–40) in
`settings.json` (§2.11). Pressure tunables on Settings tab with **Save as permanent**.

**Key tunables** (`settings.accumulator` / `POST /api/accumulator/config`):
`target_psi`, `pressure_poll_sec` (default 60), `maintain_hysteresis_psi` (default 0),
`default_pulse_ms` (shared live + auto-cal; factory **100 ms**), `max_pump_run_sec`,
timed fallbacks. Charge-after-shot is always on.
**Solenoid drive:** every open pulse must run under `RelayController.pulse_solenoid()`
(lock held for the open window). While **ARMED**, Relay CH2 (module 12V) stays
**ON for the session** (`set_module_power_hold(True)`); shots only toggle SIG.
CH2 GPIO is re-asserted on each fire/pump/watchdog tick (PQ.05/SSR can drop
while cached state still says ON — LED off, silent shots). Idle: CH2 OFF;
watchdog keeps SIG LOW. Do **not** rewrite PR.05 PADCTL after libgpiod claims
the line. Disarm / auto-cal end: drop hold + `recover_solenoid()`.
Pump edges must not cut CH2 or rewrite padmux.
**Maintenance drain:** `POST /api/line/drain` (Control tab **DRAIN PIPE**) runs
solenoid OPEN + pump ON for N seconds (default **15**, clamp 1–30) under the
relay lock, then pump OFF / valve CLOSED + `recover_solenoid()`. Disarms
accumulator first. This is the only intentional pump+open-valve overlap.
**Removed:** pump-as-shot for engagements; timed Priming keep-alive.

### 2.12 Activity Log (`activity_log.py`)

Rotating field log for post-run troubleshooting: project-root `activity.log`,
**10 MB** per file, **5** backups (`activity.log.1` …). Records ARM / FIRE /
CLICK_TEST / AUTOCAL_* (and related) with PSI and pulse timing. Gitignored.

### 2.9 Pressure Sensing (`hardware.py — PressureSensor`)

Reads accumulator pressure via an ADS1115 ADC over I2C (HW-001 §7.1). This
instruments the §2.7 dead-head reference so charge setpoints can eventually
replace timed-only charging.

- **Input:** I2C **Bus 1** (`c240000.i2c`, Pin 27/28 — the only enabled header bus;
  Pin 3/5 Gen8 is disabled in the Yahboom DTB, see HW-001 §7.1). ADS1115 address
  `0x48`, single-ended channel A0. Shares Bus 1 with the PCA9685 servo driver and
  INA3221 (both `0x40`) — unique addresses, no conflict.
- **ADS1115 config:** single-shot conversion, MUX = AINp=A0/AINn=GND, PGA = ±4.096V (FSR), 128 SPS.
- **Processing:** Background thread samples A0 at ~5Hz, converts count → volts → transducer volts → PSI:
  - `Vtap = raw × 4.096 / 32768`
  - `Vsig = Vtap × (R1+R2)/R2 = Vtap × 32/22` (undo the 10k/22k divider)
  - `PSI = ((Vsig − 0.5) / 4.0) × 100`, clamped to the 0–100 PSI range.
- **Output:** `read_psi()` (float or `None`) and `get_status()` → `{psi, volts, connected}`.
- **No mock data (project rule):** if the ADS1115 is absent or `smbus2` is
  unavailable, the sensor reports `connected: False` and `psi: None`. It never
  fabricates readings — dev/prod must not depend on synthetic pressure.
- **Divider / PGA calibration constants** (`PRESSURE_DIVIDER_R1`, `PRESSURE_DIVIDER_R2`,
  `PRESSURE_V_AT_0PSI`, `PRESSURE_V_AT_FULL`, `PRESSURE_FULL_PSI`) live in `hardware.py`
  and are exposed read-only via `GET /api/pressure`.

### 2.10 GUI Diagnostics Suite (`diagnostics.py`)

A registry of fine-grained, individually runnable hardware/software diagnostics
exposed in the dashboard's **Diagnostics** tab. Complements the coarse CLI test
suites (`/api/tests/*`) with ~50 targeted checks a field operator can run without
a terminal.

- **Registry:** each test = `{id, name, category, description, actuator}` +
  a callable returning `{status, message, data?}` with
  `status ∈ {pass, warn, fail, skip}`.
- **Categories:** Pressure/Transducer, I2C & GPIO, Servo/Gimbal, Cameras,
  AI/Vision, LiDAR, Solenoid/Trigger, Pump/Accumulator, Calibration, System.
- **Actuator safety:** tests flagged `actuator: true` move hardware or open
  valves. The API refuses them unless the request body carries `confirm: true`
  (the GUI gates this behind an explicit "arm actuator tests" checkbox).
  Non-actuator tests are always safe (read-only).
- **API:**
  - `GET /api/diag/list` → `{tests: [...], categories: [...]}`
  - `POST /api/diag/run` body `{id, confirm?}` → result of one test
  - `POST /api/diag/run_category` body `{category, confirm?}` → results list
    (actuator tests are `skip`ped unless confirmed)
- **No mock data (project rule):** absent hardware yields `fail`/`skip` with a
  diagnostic message — never fabricated readings.
- **Timeouts:** every test must complete or fail within 30s; long operations
  (sweeps, FPS sampling) keep well under this.

### 2.11 Central Settings (`settings.json` / `settings_store.py`)

Single project-root file for **all** operator tunables that must survive reboot.
Grouped schema (not flat). Legacy `scout_config.json` / `calibration_visual.json` /
flat `{"target_psi": N}` are migrated on first load.

- **Path:** `settings.json` next to `app.py`.
- **Load order:** `settings.json` → latest file in `settings_backups/` → factory
  `DEFAULTS` (then write a fresh `settings.json`).
- **Backups:** every permanent save copies the previous `settings.json` into
  `settings_backups/settings_YYYYMMDD_HHMMSS_*.json` and keeps the **last 30**.
- **Groups:** `accumulator`, `servo`, `pulse`, `prime`, `stabilize`,
  `calibration` (offsets + points), `scout` (MOG2). Factory `accumulator.target_psi`
  = **5.0** (GUI range 1–40).
- **Apply vs Save:**
  - Legacy endpoints (`/api/accumulator/config`, `/api/servo/settings`, etc.) and
    GUI **Apply (runtime)** buttons change live hardware only — lost on reboot.
  - `POST /api/settings` (GUI **Save as permanent** / **Save All**) deep-merges,
    rotates a backup, writes `settings.json`, then applies to runtime.
- **API:**
  - `GET /api/settings` → `{settings, runtime, backups, path, backup_dir}`
  - `POST /api/settings` body partial or full tree (also accepts legacy flat
    `target_psi`) → merge → backup → write → apply
- **GUI:**
  - **Calibration:** Target PSI immediate runtime; Save prompts permanent confirm.
    Offset Save → `settings.calibration`.
  - **Solenoid:** Accumulator Apply = runtime; Save as Permanent →
    `settings.accumulator`.
  - **Settings:** per-card Apply = runtime; **Save All as Permanent** collects the
    full GUI tree into one POST.
- **Startup:** `app.py` loads store and `apply_settings_to_runtime()` before serving.
  `ScoutVision` / `main.py` read `settings.scout` (fallback: `scout_config.json`).
- **Git:** `settings.json` and `settings_backups/` are machine-local (gitignored).

## 3. Orchestration Sequence — "Stream and Sweep" (`main.py`)

```
Scout Detect → Predict Position → Gimbal Aim → Sniper Verify → [ Fire Pump + Sweep Gimbal ] (parallel)
```

1. `scout_vision.get_target_with_velocity()` returns `(x, y, vx, vy)` or `(None, None, 0, 0)`
2. **Predict:** `pred_x = x + vx × LOOKAHEAD`, `pred_y = y + vy × LOOKAHEAD` (default 150ms lookahead)
3. `pixel_to_angle(pred_x, pred_y)` maps predicted position to degrees
4. Linear drop compensation added to predicted pitch
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
- Linear drop compensation clamped: final pitch cannot exceed `PITCH_LIMIT` (±20°)

> **Detection Strategy:** Mosquitoes are not in the COCO-80 class set. The primary
> targeting method is **MOG2 motion detection** (ScoutAgent §2.1), which fires at
> any small, fast-moving object in the field of view. The system intentionally
> targets **any flying insect in the 1×–3× mosquito body size range** (roughly
> 3–20mm, mapped to bounding box area thresholds at the given LiDAR distance).
> YOLOv8 TensorRT is used by the SniperAgent (§2.3) for secondary classification
> and large-object rejection only (e.g., filtering out birds, leaves, moths).
> With the multi-bug upgrade, the model is trained to recognize 15 insect classes
> and verify target classifications using the Roboflow `tiger-emltm/insects-9yf6s` dataset.


## 5. Physics Model

- **Mounting:** Overhead, 8–10 feet (2.4–3.0m) above ground level, firing DOWNWARD from an INVERTED dome enclosure.
- **Coordinate System:** Pitch axis is inverted. Positive pitch commands move the payload DOWN toward the base. Negative pitch looks OUT toward the horizon.
- **Effective Range:** 1.0 – 5.0 meters (LiDAR-measured slant distance to background)
- **Water Exit Velocity:** ~7 m/s
- **Pump Type:** 12V DC Diaphragm Pump (ECO-2026-003), 45 PSI, self-priming
- **Pump Spin-Up:** ~100ms mechanical delay (diaphragm motor to full pressure)
- **Sweep Duration:** 400ms total (100ms spin-up + 300ms active spray)
- **Firing Mode:** "Stream and Sweep" — pump fires while gimbal sweeps along target's predicted flight path, creating a moving wall of water. Sweep includes a downward bias to match trajectory incidence.
- **Drop Compensation:** Pitch offset compensates for gravity-induced stream drop over distance. Since gimbal is inverted, aiming "up" means negative pitch. Under 3m, correction is 0.0°. Over 3m, correction is -0.5° per meter.

## 6. Calibration Procedure

1. Power on gimbal and Jetson, wait 15s for gimbal IMU calibration
2. Run `phantom_ping.py` to fire test shots at known distances
3. Scout camera tracks water stream impact point
4. System generates lookup table (distance → optimal linear drop compensation)
5. Store calibration in `calibration.json`

## 7. Training & Tuning Pipeline

Training and tuning are performed on a **separate Windows workstation** (RTX 3070 8GB), NOT on the Jetson.

### 7.1 Scout Tuning (OpenCV — No AI)
- Tool: `tools/sentry_control_center/app.py` Tab 1
- Upload test video → adjust MOG2 sliders → export `scout_config.json`
- Copy `scout_config.json` to Jetson project root

### 7.2 Sniper Training (YOLOv8 — GPU-Intensive)
- Tool: `tools/sentry_control_center/app.py` Tab 2
- Provide labeled dataset (`data.yaml` from Roboflow Universe `tiger-emltm/insects-9yf6s` v2)
- Sourced and managed via `tools/sentry_control_center/download_dataset.py` using `ROBOFLOW_API_KEY`
- Train model → collect `best.pt`
- Copy `best.pt` to Jetson → convert to TensorRT `.engine` (see `gemini.md` §3)

> **Important Rule:** NEVER create dummy data (dummy videos, generated images, fake datasets, etc.) for tuning or training. If sample data is not provided, prompt the user for real data.
