# Sniper Messy Mortar — Comprehensive Change Summary

**Date:** 2026-05-16  
**Commits covered:** `37345b6` → `37e64ab` (7 commits, 27 files changed, +440 / -138 lines)  
**Purpose:** Feed this document into Gemini to restore full context for future planning and research sessions.

---

## Page 1: Executive Summary

### What Changed (High Level)

Three major changes were made to the project in this session:

1. **ECO-2026-003: Pump Hardware Change** — Replaced the 12V submersible centrifugal pump with a 12V DC diaphragm pump (60 PSI, self-priming). This was inspired by water flosser teardown analysis showing that positive-displacement pumps handle rapid on/off cycling without destructive inrush current.

2. **Stream-and-Sweep Firing Logic** — Completely rewrote the orchestrator (`main.py`) and all agent modules to implement parallel fire+sweep behavior. The pump now fires in a background thread while the gimbal simultaneously sweeps along the target's predicted flight path, creating a "wall of water."

3. **Two Comprehensive Audits** — Systematically reviewed every file in the repository for errors, omissions, and stale references. Found and fixed 23 issues across specs, code, diagrams, and operational documentation.

### Physics Model Shift

> **CRITICAL CONCEPTUAL CHANGE:** The diaphragm pump at 60 PSI produces a **direct pressurized stream**, not a gravity-dropped mist cloud. All documentation has been updated to reflect this. The system now SHOOTS water at the target rather than lobbing it above and hoping it falls. The "Airburst Offset" still applies — it compensates for gravity drop over distance (the stream arcs) — but the framing is now "direct fire with trajectory compensation" rather than "mortar-style AoE rain."

---

## Page 2: Hardware Change — ECO-2026-003 (Diaphragm Pump)

### Why the Change

The original 12V submersible centrifugal pump had critical problems for pulse-firing:

| Problem | Impact |
|---------|--------|
| **Destructive short-cycling** | 3-8× inrush current per 600ms burst would burn out the motor within weeks |
| **Priming issues** | Submersible pump must remain submerged; air in lines = no spray |
| **Dribble on shutdown** | Centrifugal impeller can't hold pressure; water dribbles after relay closes |
| **Siphon risk** | When nozzle points down, gravity pulls water through the pump backward |

### The Replacement

**12V DC Diaphragm Pump** (~$25 CAD, 60 PSI, self-priming):

- **Positive displacement** — piston/diaphragm creates pressure mechanically, designed for rapid on/off
- **Self-priming** — can pull water up from reservoir without pre-fill
- **Dry-run safe** — won't burn out if reservoir is empty (just runs without output)
- **Check valve built-in** — no backflow when pump is off
- **~100ms spin-up** — diaphragm motor needs ~100ms to reach full pressure

### Physical Mounting Changes

The pump is now **surface-mounted on a bracket adjacent to the IP67 enclosure** (NOT submerged in the reservoir, NOT inside the Jetson box).

**New physical stacking (top to bottom):**

```
1. Gimbal + Sniper Camera + Nozzle   (highest — on post above enclosure)
2. Diaphragm Pump                     (on bracket, adjacent to enclosure)
3. IP67 Enclosure                     (Jetson, relays, IDC40P terminal block)
4. Water Reservoir                    (ground level — intake tube drops in)
```

### Files Changed for ECO-2026-003

| File | Change |
|------|--------|
| `parts.csv` | Replaced submersible pump entry with diaphragm pump |
| `HW-001-hardware-spec.md` | Updated §8 Fluid System, Wago GND port map, flyback §6.1, added stacking diagram |
| `HISTORY.md` | Logged ECO-2026-003 with rationale |
| `OPS-001-operations-guide.md` | Rewrote §3.2 Water Reservoir & Pump Placement |

### New Diagrams Added

| Image | Description |
|-------|-------------|
| `diagrams/images/physical_stacking_sideview.png` | Side view of gimbal-above-enclosure stacking |
| `diagrams/images/fluid_system_diaphragm.png` | Fluid routing: reservoir → intake tube → pump → tubing → nozzle |
| `diagrams/images/diaphragm_pump_detail.png` | Cutaway showing suction/pressure stroke mechanism |
| `diagrams/images/pump_submersion_DEPRECATED.png` | Old submersible pump diagram (renamed, kept for history) |

---

## Page 3: Stream-and-Sweep Firing Logic

### Old Firing Sequence (v3.0)

```
Scout Detect → Gimbal Aim → sleep(200ms) → Sniper Verify → weapon.fire(0.6) [BLOCKING]
```

- Sequential, blocking — gimbal stops moving during fire
- 600ms pulse — too long, wastes water
- No trajectory prediction — aims at where target WAS, not where it WILL BE
- 200ms settle wait — excessive, pump could be spinning up during this time

### New Firing Sequence (v4.0 — Stream and Sweep)

```
Scout Detect → Predict Position → Aim → Sniper Verify → [ fire_sweep() + sweep_async() ] PARALLEL
```

**Timing breakdown (0ms to 500ms):**

| Time | Scout | Gimbal | Pump (BCM 17) | Sniper |
|------|-------|--------|---------------|--------|
| 0ms | Continuous detection | — | — | — |
| ~50ms | Target + velocity calculated | Aim at predicted position | — | — |
| ~80ms | — | — | — | YOLO verify → VERIFIED |
| 100ms | — | BEGIN SWEEP along flight path | GPIO HIGH (spin-up) | — |
| 200ms | — | Mid-sweep | Water exits nozzle | — |
| 400ms | — | Sweep complete (overshoot) | — | — |
| 500ms | — | — | GPIO LOW (cease fire) | — |

### Key Innovation: Predictive Targeting

The Scout now outputs a **velocity vector** `(vx, vy)` in pixels/sec, calculated from a ring buffer of the last 5 positions. The orchestrator uses this to predict where the target will be in 150ms (the combined gimbal travel + pump spin-up time):

```python
pred_x = tx + vx * PREDICTION_LOOKAHEAD_SEC  # 0.15s
pred_y = ty + vy * PREDICTION_LOOKAHEAD_SEC
```

### Key Innovation: Non-Blocking Fire

`weapon.fire_sweep(0.4)` starts the pump in a **background thread** and returns immediately. This allows the gimbal to begin sweeping while the pump is spinning up. By the time water exits the nozzle (~100ms), the gimbal is mid-sweep → the water stream draws a line across the target's predicted flight path.

---

## Page 4: Module-by-Module Code Changes

### `scout_vision.py` — Added Velocity Vector

**Before:** `get_target()` returns `(x, y)` only  
**After:** `get_target_with_velocity()` returns `(x, y, vx, vy)`

New internals:
- `deque(maxlen=5)` ring buffer of `(x, y, timestamp)` tuples
- Velocity calculated as `(newest - oldest) / dt` from the buffer endpoints
- Thread-safe via existing `_lock`
- `get_target()` still exists for backward compatibility

### `weapon_system.py` — Non-Blocking Fire + Emergency Stop

**New methods:**

| Method | Behavior |
|--------|----------|
| `fire(duration)` | Blocking pulse (legacy) — relay HIGH for duration, then LOW |
| `fire_sweep(duration)` | **Non-blocking** — starts pump in background thread, returns immediately |
| `cease_fire()` | Emergency stop — immediately sets relay LOW regardless of timer |
| `is_firing` (property) | Returns True if pump relay is currently energized |

Internal `_fire_lock` prevents stacking multiple fire commands. `_sweep_worker` thread uses `try/finally` to guarantee relay LOW even on exception (SAFE-001 §2 compliance).

### `gimbal_controller.py` — Async Aim + Linear Sweep

**New methods:**

| Method | Behavior |
|--------|----------|
| `aim_async(pitch, yaw)` | Non-blocking — dispatches serial write to `run_in_executor` |
| `sweep(start, end, steps, delay)` | Synchronous linear interpolation from point A to point B |
| `sweep_async(...)` | Non-blocking sweep via executor thread |

The sweep creates 5 micro-steps (configurable) between start and end angles, with 40ms between each step. Total sweep time ≈ 200ms.

### `main.py` — Complete Orchestrator Rewrite

**New features:**
- `asyncio` event loop (replaces synchronous polling)
- `pixel_to_angle()` coordinate mapping (110° H × 75° V FOV)
- Configurable constants: `PREDICTION_LOOKAHEAD_SEC`, `SWEEP_DURATION_SEC`, `SWEEP_OVERSHOOT_DEG`, `POST_ENGAGEMENT_COOLDOWN_SEC`
- Structured JSONL engagement logging with session statistics
- `logging` module with file + console handlers

**Orchestration flow:**
1. Poll `scout.get_target_with_velocity()` every 50ms
2. Predict target position 150ms ahead
3. Convert to gimbal angles, add airburst offset
4. `gimbal.aim_async()` — non-blocking
5. 50ms settle (reduced from 200ms)
6. `sniper.verify_target()` — YOLO inference
7. If verified → `weapon.fire_sweep(0.4)` + `gimbal.sweep_async()` in parallel
8. 1.0s cooldown

### `sniper_vision.py` — TensorRT Auto-Detection

Now auto-detects `best.engine` before falling back to `best.pt`:

```python
engine_path = model_path.replace('.pt', '.engine')
if os.path.exists(engine_path):
    self.model_path = engine_path  # TensorRT — max FPS
else:
    self.model_path = model_path   # PyTorch fallback
```

Prints a helpful TIP if running on `.pt` suggesting the TensorRT export command.

---

## Page 5: Specification Updates

### SW-001 (v3.0 → v4.0)

| Section | Change |
|---------|--------|
| §2.1 ScoutAgent | Output now includes `(vx, vy)` velocity vector via ring buffer |
| §2.2 TurretAgent | Added `aim_async()`, `sweep_async()` via `run_in_executor` |
| §2.4 TriggerAgent | 600ms → 400ms, added `fire_sweep()` (non-blocking) + `cease_fire()` |
| §3 Orchestration | Complete rewrite: `Scout → Predict → Aim → Verify → [Fire + Sweep] parallel` |
| §5 Physics | "mist cloud/rain AoE" → "direct pressurized stream/sweep curtain" |
| §5 Physics | Pump type: 12V DC Diaphragm, 60 PSI, ~100ms spin-up |

### HW-001 (v4.0)

| Section | Change |
|---------|--------|
| §2 Camera table | Sniper FPS: 60 → 30 (matches actual code) |
| §3 Gimbal | Yaw "±130° hard-limited" → "±130° mechanical (software endstop ±80°)" |
| §4 Wago GND Port 4 | "Velleman Pump" → "Diaphragm Pump" |
| §6.1 Flyback | "Velleman water pump" → "diaphragm pump" |
| §8 Fluid System | Full rewrite for diaphragm pump topology |

### SYS-001 (v2.0 → v3.0)

- Description: "600ms Gravity Airburst" → "400ms Stream-and-Sweep"
- TriggerAgent role: "600ms Airburst pulse" → "400ms Stream-and-Sweep"
- Physical topology: Added "12V Diaphragm Pump" line, "submerged pump" → "intake tube (pump self-primes)"

### SAFE-001 (v1.1)

- §2 Software Safety: Yaw "±130°; rapid unwind" → "±80°; pitch to ±20° (software endstops)"

### TEST-001 (v1.0)

- Added T2.7: Stream-and-Sweep parallel test
- Updated T3.7: fire timing "fire_sweep 400ms, 600ms cooldown"
- Updated T5.5: "Pump does not burn out dry" → "Diaphragm pump runs dry safely"

### OPS-001 (v1.0)

- §1.1: Now references both `parts.csv` AND `moreparts.csv`
- §3.2: Complete rewrite — "pump submerged in reservoir" → diaphragm pump stacking topology
- §6.2: Calibration references "400ms sweep each"
- §8.3: "burns out motor" → "diaphragm pump is dry-run safe"

---

## Page 6: Audit #1 Findings (11 Issues)

### Critical Fixes

| # | Issue | File | Fix |
|---|-------|------|-----|
| 1 | SAFE-001 yaw limit said ±130° | `SAFE-001` | → ±80° (matches endstop) |
| 2 | OPS-001 said "pump submerged" | `OPS-001 §3.2` | Rewrote with diaphragm stacking |
| 3 | phantom_ping.py used 0.6s pulse | `phantom_ping.py` | → 0.4s |
| 4 | OPS-001 said pump "burns out" dry | `OPS-001 §8.3` | Diaphragm is dry-run safe |
| 5 | TEST-001 T5.5 assumed submersible | `TEST-001` | Updated for diaphragm |
| 6 | No Stream-and-Sweep test existed | `TEST-001` | Added T2.7 |

### Moderate Fixes

| # | Issue | Fix |
|---|-------|-----|
| 7 | README described old "Airburst" | Updated to "Stream and Sweep" |
| 8 | OPS-001 calibration timing stale | Added "400ms sweep each" |
| 9 | TEST-001 T3.7 had no timing | Added "fire_sweep 400ms" |
| 10 | sentry.service didn't maximize perf | Added `nvpmodel -m 0` + `jetson_clocks` before start |
| 11 | hardware.py vs gimbal_controller.py | By design (Flask HAL vs agent) — documented |

---

## Page 7: Audit #2 Findings (12 Issues)

### Critical Fixes

| # | Issue | File | Fix |
|---|-------|------|-----|
| 1 | HW-001 §3 yaw "±130° hard-limited" | `HW-001` | Now shows mechanical ±130° + software ±80° |
| 2 | HW-001 Wago GND: "Velleman Pump" | `HW-001` | → "Diaphragm Pump" |
| 3 | HW-001 §6.1 flyback: "Velleman" | `HW-001` | → "diaphragm pump" |
| 4 | HW-001 §2 Sniper: 60 FPS | `HW-001` | → 30 FPS (matches code) |
| 5 | Flask fire default: 0.3s | `app.py` | → 0.4s |

### Physics Model Update (Diaphragm Pump = Direct Fire)

| # | Issue | Fix |
|---|-------|-----|
| 6 | SW-001 "mist cloud / rain AoE" | → "direct pressurized stream / sweep curtain" |
| 7 | SW-001 "falls as wide AoE mist cloud" | → "arcs slightly above, compensating for gravity drop" |

### Code Improvements

| # | Issue | Fix |
|---|-------|-----|
| 8 | sniper_vision.py always loads `.pt` | Auto-detects `.engine` first |
| 9 | Sentry Control Center: no TensorRT guide | Post-training UI shows export + deploy steps |
| 10 | GPIO warnings from multiple modules | Added `setwarnings(False)` |
| 11 | hardware.py endstop comment misleading | Clarified mechanical vs software |
| 12 | OPS-001 only references parts.csv | Now also references `moreparts.csv` |

---

## Page 8: Current Repository File Map

### Core Agent Modules (deployed to Jetson)

| File | Lines | Purpose | Key API |
|------|-------|---------|---------|
| `main.py` | 195 | Async orchestrator — Stream-and-Sweep state machine | `orchestrator_loop()` |
| `scout_vision.py` | 160 | MOG2 motion detection + velocity vector | `get_target_with_velocity()` → `(x,y,vx,vy)` |
| `sniper_vision.py` | 120 | YOLOv8 TensorRT classification | `verify_target()` → `bool` |
| `gimbal_controller.py` | 100 | Storm32 UART serial + async sweep | `aim_async()`, `sweep_async()` |
| `weapon_system.py` | 115 | GPIO BCM 17 relay + non-blocking fire | `fire_sweep(0.4)`, `cease_fire()` |
| `hardware.py` | 622 | Flask HAL (relay, gimbal, LiDAR, ballistics) | Used by `app.py` only |
| `vision.py` | 435 | Flask vision (camera streams, YOLO, velocity) | Used by `app.py` only |
| `ir_controller.py` | 134 | Dusk/dawn IR illuminator scheduling | `IRController(auto_schedule=True)` |
| `status_indicator.py` | 91 | Piezo buzzer status feedback | `boot()`, `engagement()`, `cease_fire()` |
| `phantom_ping.py` | 161 | Interactive airburst calibration tool | CLI: `--offset 12 --count 5 --pulse 0.4` |

### Flask Dashboard (deployed to Jetson)

| File | Lines | Purpose |
|------|-------|---------|
| `app.py` | 725 | Flask web server — MJPEG streams, REST API, calibration |
| `templates/index.html` | — | Dashboard HTML (WASD, click-to-aim, sliders) |

### Windows/Mac Tooling (NOT deployed to Jetson)

| File | Lines | Purpose |
|------|-------|---------|
| `tools/sentry_control_center/app.py` | 269 | Streamlit UI: Scout MOG2 tuner + YOLO trainer |
| `tools/sentry_control_center/requirements.txt` | 14 | PyTorch + Streamlit + Ultralytics |

### Configuration & Deployment

| File | Purpose |
|------|---------|
| `scout_config.json` | MOG2 tuning parameters (exported from Sentry Control Center) |
| `calibration.json` | Airburst offset calibration data (from phantom_ping.py) |
| `deploy.sh` | rsync dev machine → Jetson (excludes tools/, diagrams/) |
| `sentry.service` | systemd auto-start: `nvpmodel -m 0` → `jetson_clocks` → `main.py` |
| `requirements.txt` | Jetson Python deps: flask, pyserial, smbus2, numpy, ultralytics |

### Specifications

| File | Version | Status |
|------|---------|--------|
| `docs/specs/SW-001-software-spec.md` | v4.0 | APPROVED |
| `docs/specs/HW-001-hardware-spec.md` | v4.0 | APPROVED |
| `docs/specs/SYS-001-system-overview.md` | v3.0 | APPROVED |
| `docs/specs/SAFE-001-safety-spec.md` | v1.1 | APPROVED |
| `docs/specs/TEST-001-test-plan.md` | v1.0 | DRAFT |
| `docs/specs/OPS-001-operations-guide.md` | v1.0 | DRAFT |

---

## Page 9: Current System Constants & Configuration

### Timing Constants (`main.py`)

| Constant | Value | Purpose |
|----------|-------|---------|
| `PREDICTION_LOOKAHEAD_SEC` | 0.15 | How far ahead to predict target position |
| `SWEEP_DURATION_SEC` | 0.4 | Total pump-on time (100ms spin-up + 300ms spray) |
| `SWEEP_OVERSHOOT_DEG` | 3.0 | Degrees past predicted position to sweep |
| `SWEEP_STEPS` | 5 | Gimbal micro-steps during sweep |
| `SWEEP_STEP_DELAY` | 0.04 | Seconds between each micro-step |
| `POST_ENGAGEMENT_COOLDOWN_SEC` | 1.0 | Cooldown after engagement |

### Camera Configuration

| Camera | Resolution | FPS | FOV | GStreamer Pipeline |
|--------|-----------|-----|-----|-------------------|
| Scout (IMX219 NoIR) | 1280×720 | 60 | 62.2°H × 48.8°V | `nvarguscamerasrc sensor-id=0` |
| Sniper (IMX219 NoIR) | 1920×1080 | 30 | Standard | `nvarguscamerasrc sensor-id=1` |

Both use `appsink drop=true max-buffers=1` to prevent memory saturation on 8GB Jetson.

### GPIO Pin Map

| Function | BCM | Physical Pin | IDC40P Terminal |
|----------|-----|-------------|-----------------|
| Pump Relay (CH1) | BCM 17 | Pin 11 | Terminal 11 |
| Gimbal Relay (CH2) | BCM 27 | Pin 13 | Terminal 13 |
| Status Buzzer | BCM 4 | Pin 7 | Terminal 7 |
| IR Illuminator (future) | BCM 22 | Pin 15 | Terminal 15 |
| UART TX (Gimbal) | BCM 14 | Pin 8 | Terminal 8 |
| UART RX (Gimbal) | BCM 15 | Pin 10 | Terminal 10 |
| LiDAR I2C SDA | BCM 2 | Pin 3 | Terminal 3 |
| LiDAR I2C SCL | BCM 3 | Pin 5 | Terminal 5 |

### Software Endstops

| Axis | Software Limit | Hardware Mechanical |
|------|---------------|-------------------|
| Yaw | ±80° | ±130° |
| Pitch | ±20° | ±45° |

---

## Page 10: Known Open Items & Next Steps

### Immediate Action Items

1. **Procure the diaphragm pump** — ECO-2026-003 is documented but the physical pump hasn't been purchased yet. Spec: 12V DC, 60 PSI, self-priming, ~$25 CAD.

2. **Build the training dataset** — The YOLO model needs labeled mosquito images. Follow `docs/DATASET_STRATEGY.md`: Roboflow Universe → supplement with own captures → train via Sentry Control Center → export to TensorRT `.engine` on Jetson.

3. **Create test scripts that actually exercise the new code** — The test files exist (`tests/`) but many reference the old Flask-based `hardware.py` API, not the new modular agents. Specifically:
   - `test_relay.py` uses `RelayController` from `hardware.py` — should also test `WeaponSystem.fire_sweep()`
   - No test exercises the async orchestrator loop
   - No test validates the velocity vector calculation

4. **Validate `calibration.json` integration** — `phantom_ping.py` saves calibration data, but `main.py` doesn't currently READ `calibration.json` to set the airburst offset. It uses a hardcoded `weapon.get_airburst_offset()` → always 12.0°.

### Architecture Notes for Future Work

- **`hardware.py` (622 lines) vs agent modules** — Two parallel implementations exist: `hardware.py` is the Flask HAL (used by `app.py` dashboard), while `gimbal_controller.py`/`weapon_system.py`/etc. are the autonomous agents (used by `main.py`). They serve different purposes but could diverge. Consider whether to merge or keep separate.

- **`vision.py` (435 lines) VelocityTracker** — Duplicates the velocity tracking in `scout_vision.py`. Same concern as above: Flask vs autonomous.

- **LiDAR integration** — `hardware.py` has `LiDARController` for the TF-Luna, and `compute_predictive_lead()` uses it for Time-of-Flight calculations. But `main.py` doesn't currently use LiDAR data in its engagement loop — it only uses the Scout's pixel-to-angle conversion. Adding LiDAR distance to the engagement data would improve ballistic accuracy.

- **`moreparts.csv`** — Contains 16 items (cable glands, standoffs, mounting poles, hose clamps, step drill bits) that are REQUIRED for assembly but were not in the original `parts.csv`. OPS-001 now references both files.

### Diagrams Available in `diagrams/`

All `.drawio` wiring diagrams are present. The `diagrams/images/` directory contains:

| Image | Content |
|-------|---------|
| `physical_stacking_sideview.png` | Side view of gimbal-above-enclosure stacking |
| `fluid_system_diaphragm.png` | Self-priming pump fluid routing |
| `diaphragm_pump_detail.png` | Suction/pressure stroke cutaway |
| `stream_sweep_timing.png` | Parallel pump/gimbal/scout/sniper timing diagram |
| `pump_submersion_DEPRECATED.png` | Old submersible pump diagram (historical) |
