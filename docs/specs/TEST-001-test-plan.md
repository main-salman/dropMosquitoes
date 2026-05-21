# TEST-001: Test Plan Specification

**Status:** APPROVED  
**Version:** 1.0  
**Last Updated:** 2026-05-20  
**Owner:** Salman


## 1. Test Philosophy

This system combines computer vision, serial robotics, fluid dynamics, and edge AI — each with distinct failure modes. Tests are organized into **6 layers**, from isolated unit tests (runnable on a Mac) to full outdoor integration tests (Jetson + hardware + weather).

---

## 2. Test Layers

### Layer 0: Smoke Tests (Dev Machine — No Hardware)
> **Goal:** Verify the Flask server, API routes, and GUI work without any Jetson hardware.  
> **Where:** Mac/PC. Run with `--no-ai` flag.

| ID | Test | Pass Criteria |
|:---|:-----|:--------------|
| T0.1 | Server starts in stub mode | No crash, all stub warnings printed |
| T0.2 | Dashboard loads at `/` | HTTP 200, all UI elements render |
| T0.3 | MJPEG streams deliver test patterns | `/stream/scout` and `/stream/sniper` return multipart JPEG |
| T0.4 | All API endpoints accept POST | Every `/api/*` route returns valid JSON |
| T0.5 | Click-to-aim math is correct | Center pixel → (0°, 0°), corners → expected angles |
| T0.6 | Software endstops clamp correctly | Requesting ±200° yaw returns clamped ±80° |
| T0.7 | Relay fire duration clamps | Requesting 10s returns clamped 2.0s |
| T0.8 | Status polling works | `/api/status` returns gimbal, relay, and AI state |

---

### Layer 1: Hardware Unit Tests (Jetson — One Subsystem at a Time)
> **Goal:** Verify each hardware peripheral works independently.  
> **Where:** Jetson Orin Nano with individual components connected.

| ID | Test | Procedure | Pass Criteria |
|:---|:-----|:----------|:--------------|
| T1.1 | Scout camera GStreamer | Run `test_camera.py --scout` | Live 120FPS feed, no dropped frames for 30s |
| T1.2 | Sniper camera GStreamer | Run `test_camera.py --sniper` | Live 30FPS feed, frame shape 1920×1080 |
| T1.3 | GPIO Relay 1 (Pump) | Run `test_relay.py --pump` | Relay audibly clicks ON/OFF, multimeter shows 12V |
| T1.4 | GPIO Relay 2 (Gimbal) | Run `test_relay.py --gimbal` | Relay clicks, gimbal motors power up |
| T1.5 | Serial UART TX | Run `test_serial.py --loopback` | TX→RX loopback receives sent bytes |
| T1.6 | Storm32 response | Run `test_serial.py --storm32` | Board replies with version/status packet |
| T1.7 | TensorRT model load | Run `test_yolo.py` | Model loads in <3s, inference on test image returns detections |

---

### Layer 2: Integration Tests (Jetson — Multiple Subsystems)
> **Goal:** Verify subsystems work together without race conditions or bus conflicts.

| ID | Test | Procedure | Pass Criteria |
|:---|:-----|:----------|:--------------|
| T2.1 | Dual camera simultaneous | Both cameras streaming to MJPEG at once | No bus conflict, both feeds >15FPS |
| T2.2 | Camera + Serial | Stream camera while sending gimbal commands | No serial timeout, no frame drops |
| T2.3 | GPIO + Serial | Fire pump relay while gimbal is moving | No back-EMF interference on UART |
| T2.4 | Full boot sequence | Power on → Relay 2 OFF → Serial init → Relay 2 ON | Gimbal doesn't jerk on boot |
| T2.5 | YOLO + camera | Run inference on live sniper feed | >10 FPS inference, correct bounding boxes |
| T2.6 | Click-to-aim live | Click on Scout feed → gimbal moves to target | Gimbal arrives within ±3° of target |
| T2.7 | Stream-and-Sweep parallel | Trigger fire_sweep() + sweep_async() simultaneously | Pump runs 400ms, gimbal completes sweep, no thread deadlock |

---

### Layer 3: Safety Tests (CRITICAL — Must Pass Before Outdoor Use)
> **Goal:** Verify all safety interlocks work under stress conditions.

| ID | Test | Procedure | Pass Criteria |
|:---|:-----|:----------|:--------------|
| T3.1 | Kill switch | Kill Python process mid-fire | BCM 17 goes LOW within 10ms (measured with oscilloscope or LED) |
| T3.2 | Power loss recovery | Yank DC power during gimbal motion | Gimbal settles safely, no stuck relay |
| T3.3 | Large-Object Rejection | Place large object (person, bird) in sniper FOV | Object rejected as non-target, pump does NOT fire |
| T3.4 | Software endstop enforcement | Command yaw=180° via API | Gimbal clamps to ±80°, no wire strain |

| T3.5 | Death Spiral prevention | Sweep target past 160° boundary | Gimbal unwinds opposite direction, no full rotation |
| T3.6 | Check valve test | Tilt nozzle 45° downward, wait 5 min | No water drip from nozzle (siphon blocked) |
| T3.7 | Back-EMF isolation | Fire pump 100× rapidly (fire_sweep 400ms, 600ms cooldown) | No serial corruption, no Jetson GPIO damage |
| T3.8 | Continuous run stress | Run full system for 4 hours | No memory leak, no thread deadlock, no overheating |

---

### Layer 4: Calibration & Accuracy Tests
> **Goal:** Tune the physics model and validate hit accuracy.

| ID | Test | Procedure | Pass Criteria |
|:---|:-----|:----------|:--------------|
| T4.1 | Pump pressure profiling | Fire at 0.1s increments, measure stream distance | Generate distance-vs-duration curve |
| T4.2 | Linear drop lookup table | Fire at targets at 1m, 2m, 3m, 4m, 5m | Pitch angle produces hit within 15cm circle |
| T4.3 | Phantom Ping wind calibration | Fire test shot, Scout tracks droplet drift | Offset variable updated, next shot corrects |
| T4.4 | Nozzle pattern tuning | Adjust Orbit nozzle from mist → stream | Narrow stream at all tested distances |
| T4.5 | Gimbal repeatability | Send same angle 50 times | Gimbal arrives at same physical position ±0.5° |
| T4.6 | Click-to-aim accuracy | Click 20 known points, measure gimbal arrival | Mean error < 2° |
| T4.7 | Latency measurement | Target appears → water hits target | Total pipeline latency < 500ms |

---

### Layer 5: Environmental & Endurance Tests
> **Goal:** Validate the system survives real-world outdoor conditions.

| ID | Test | Procedure | Pass Criteria |
|:---|:-----|:----------|:--------------|
| T5.1 | Morning dew exposure | Deploy at 5 AM in 85%+ humidity for 2 hours | No condensation inside IP67 box, cameras fog-free |
| T5.2 | Direct sun heat soak | Deploy in full sun for 4 hours | Jetson thermal < 85°C, no throttling |
| T5.3 | Night vision test | Run at dusk/night with IR illuminator only | Scout detects motion, Sniper classifies in IR |
| T5.4 | Wind interference | Test with fan at 10-15 km/h crosswind | Phantom Ping compensates, hit rate >50% at 3m |
| T5.5 | Reservoir depletion | Run until reservoir is empty | Diaphragm pump runs dry safely (no burnout), system detects absent spray via Scout |
| T5.6 | Multi-night endurance | Run dusk-to-dawn (10 hours) for 3 consecutive nights | No crashes, no memory leaks, reservoir lasts |
| T5.7 | Insect discrimination | Deploy with moths, June bugs, and mosquitoes present | Only fires at mosquito-sized targets, ignores moths |

---

## 3. Test Script Files

| Script | Layer | Description |
|:-------|:------|:------------|
| `tests/test_smoke.py` | 0 | Automated: starts server, hits all API endpoints, checks responses |
| `tests/test_camera.py` | 1 | Standalone camera test with FPS counter and frame saver |
| `tests/test_relay.py` | 1 | GPIO relay pulse test with configurable timing |
| `tests/test_serial.py` | 1 | Serial loopback and Storm32 handshake test |
| `tests/test_yolo.py` | 1 | TensorRT model load and single-frame inference |
| `tests/test_safety.py` | 3 | Automated safety interlock verification |
| `tests/test_accuracy.py` | 4 | Click-to-aim and endstop validation |

## 4. Test Results Logging

All test results MUST be logged in `docs/HISTORY.md` with the `[TEST]` category tag:
```
- **[TEST]** T3.1 Kill switch PASSED — GPIO confirmed LOW after SIGKILL
- **[TEST]** T4.2 Linear drop LUT FAILED — 4m target miss by 25cm, adjusting pitch offset
```
