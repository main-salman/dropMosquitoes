# Project History — Sniper Messy Mortar

> This file is automatically maintained. Every significant project action is logged here with a timestamp, category, and description. AI agents MUST append to this log when making changes.

---

## 2026-05-11 — PROJECT INCEPTION
- **[DESIGN]** Initial concept defined: AI-driven autonomous mosquito sentry turret
- **[DESIGN]** Four-agent architecture established: ScoutAgent, TurretAgent, SniperAgent, TriggerAgent
- **[CODE]** `scout_vision.py` scaffolded with GStreamer pipeline for OV9281

## 2026-05-12 — HARDWARE RESEARCH (Iteration 1)
- **[PROCUREMENT]** Initial parts list created with Amazon.ca links
- **[PROCUREMENT]** Multiple broken links discovered — Amazon ASINs unreliable for specialty robotics parts
- **[DECISION]** Adopted "Hybrid Vendor" strategy: specialty parts from RobotShop/Waveshare, generic from Amazon

## 2026-05-13 — HARDWARE RESEARCH (Iteration 2)
- **[PROCUREMENT]** Custom Python web scraper (DuckDuckGo + ASIN extraction) built to find verified Amazon.ca product links
- **[PROCUREMENT]** 14 of 15 Amazon items resolved to direct `/dp/ASIN` URLs via scraper
- **[BUG FIX]** Corrected camera spec: IMX477 NoIR does not exist → switched to IMX219 NoIR w/ Motorized IR-Cut
- **[BUG FIX]** ASIN B0829HZ3Q7 was a 2MP USB webcam, not 12MP IMX477 — removed incorrect link
- **[DECISION]** Arducam direct links blocked by Cloudflare (403) → replaced with Arducam store search URL

## 2026-05-14 — HARDWARE FINALIZATION & USER TAKEOVER
- **[PROCUREMENT]** User manually verified and replaced ALL parts.csv entries with hand-picked, confirmed URLs from RobotShop, AliExpress, and Amazon.ca
- **[DECISION]** Final camera selection: Arducam NoIR 8MP IMX219 w/ Motorized IR-Cut Filter (from ca.robotshop.com)
- **[DECISION]** Compute platform upgraded: Waveshare Orin Nano → Yahboom Orin Nano SUPER Mini PC Kit ($800 CAD)
- **[DECISION]** Relay changed: generic opto-isolated → Monk Makes Dual Relay Module (from ca.robotshop.com)
- **[DECISION]** Nozzle changed: generic barbed nozzle → Orbit 66190 Flex-Mist Adjustable Micro Sprinkler

## 2026-05-14 — WIRING DIAGRAMS
- **[DIAGRAM]** Created `sentry_diagram.drawio` — combined 3-zone wiring schematic (Power, Logic, Fluid)
- **[DIAGRAM]** Created `assembly_1_topdown.drawio` — top-down IP67 enclosure internal layout
- **[DIAGRAM]** Created `assembly_2_sideview.drawio` — side view with cable gland weatherproofing
- **[DIAGRAM]** Created `assembly_3_gimbal.drawio` — gimbal payload detail view

## 2026-05-14 — DETAILED ZONE DIAGRAMS
- **[DIAGRAM]** Created `diagrams/zone1_power.drawio` — detailed Wago 221-415 port-by-port wiring
- **[DIAGRAM]** Created `diagrams/zone2_logic.drawio` — camera chains with Scout FIXED, Sniper on gimbal
- **[DIAGRAM]** Created `diagrams/zone3_fluid.drawio` — complete water path with zip tie anchors
- **[DIAGRAM]** Created `diagrams/gimbal_payload.drawio` — sniper + nozzle + service loop + FPC strain relief
- **[DECISION]** Scout camera (OV9281) is FIXED to enclosure — does NOT ride on gimbal

## 2026-05-14 — 3D TECHNICAL ILLUSTRATIONS
- **[DIAGRAM]** Generated 5 multi-angle technical illustrations (front isometric, side profile, top-down FOV, rear cable routing, exploded assembly)
- **[DIAGRAM]** Generated 5 assembly step illustrations (enclosure layout, cable glands, Wago wiring, CSI chain, fluid system)
- **[DIAGRAM]** All 10 images saved to `diagrams/images/`

## 2026-05-14 — SPEC-DRIVEN DEVELOPMENT SETUP
- **[PROCESS]** Created `docs/specs/` folder with formal specifications:
  - `SYS-001-system-overview.md` — top-level system architecture
  - `HW-001-hardware-spec.md` — complete hardware specification with Wago port maps
  - `SW-001-software-spec.md` — agent architecture and physics model
  - `SAFE-001-safety-spec.md` — hardware/software/operational safety measures
- **[PROCESS]** Created `docs/HISTORY.md` — this file
- **[PROCESS]** Updated `agents.md`, `gemini.md`, `rules.md` with spec-driven development enforcement rules

## 2026-05-14 — SOFTWARE STACK v1.0
- **[CODE]** Created `hardware.py` — GPIO relay control (Monk Makes Dual Relay) + Storm32 serial gimbal controller with o323BGC protocol + pixel-to-angle math
- **[CODE]** Created `vision.py` — Threaded GStreamer camera capture with MJPEG encoding, TensorRT YOLOv8 inference wrapper, test pattern fallback for dev machines
- **[CODE]** Created `app.py` — Flask server with MJPEG streams, REST API for gimbal/relay/AI control, atexit safety cleanup
- **[CODE]** Created `templates/index.html` — Dark-mode web dashboard with live feeds, click-to-aim, WASD control, burst testing, AI sliders, relay toggles
- **[DECISION]** Software endstops set to ±80° yaw, ±20° pitch (more conservative than hardware limits for cable protection)
- **[DECISION]** All hardware modules include STUB mode for development/testing without Jetson hardware

## 2026-05-14 — TEST SUITE & OPS SCRIPTS
- **[PROCESS]** Created `docs/specs/TEST-001-test-plan.md` — 6-layer test plan (Smoke → Environmental)
- **[CODE]** Created `tests/test_smoke.py` (Layer 0) — 35 API endpoint validations
- **[CODE]** Created `tests/test_camera.py` (Layer 1) — GStreamer FPS + frame integrity
- **[CODE]** Created `tests/test_relay.py` (Layer 1) — GPIO pulse cycles + boot state + duration clamp
- **[CODE]** Created `tests/test_serial.py` (Layer 1) — Loopback, Storm32 handshake, full sweep
- **[CODE]** Created `tests/test_yolo.py` (Layer 1) — Model load + inference FPS
- **[CODE]** Created `tests/test_safety.py` (Layer 3) — Endstops, death spiral, failsafe, thread safety
- **[CODE]** Created `tests/test_accuracy.py` (Layer 4) — Click-to-aim math, repeatability, range sweep
- **[CODE]** Created `run-ai.sh`, `run-no-ai.sh`, `stop.sh` — Server lifecycle scripts
- **[TEST]** All 112 tests pass in stub mode (35 smoke + 10 camera + 8 relay + 19 serial + 2 yolo + 24 safety + 14 accuracy)

## 2026-05-14 — GUI TEST RUNNER & APPLE REDESIGN
- **[CODE]** Added `/api/tests/list`, `/api/tests/run`, `/api/tests/run_all` API routes to `app.py`
- **[CODE]** Added tabbed dashboard: Control tab + Test Suite tab with per-test run buttons, live log, pass/fail badges
- **[DESIGN]** Redesigned GUI with Apple-inspired aesthetics: Inter font, frosted glass blur, iOS toggles, pill badges, SF Mono terminal output

## 2026-05-15 — ECO-2026-002: External Terminal Block Hub

- **[ECO]** Transitioning from friction-fit internal GPIO jumpers to robust External Terminal Block Hub architecture
- **[PROCUREMENT]** Added 40-Pin F/F IDC Ribbon Cable (0.3m, 2.54mm) to BOM (parts.csv line 45)
- **[PROCUREMENT]** Added IDC40P 40-Pin Male Header Terminal Block Breakout to BOM (parts.csv line 46)
- **[DESIGN]** New wiring hierarchy: Jetson GPIO → Ribbon Cable (inside Yahboom) → IDC40P Breakout (inside IP67) → Device wiring
- **[DESIGN]** System Isolation Rules: Yahboom case sealed with only ribbon cable + DC power exiting
- **[CODE]** `hardware.py` GPIO pins changed: RELAY_PUMP_PIN 18→17 (BCM17 = Pin 11), RELAY_GIMBAL_PIN 24→27 (BCM27 = Pin 13)
- **[SPEC]** HW-001 updated to v4.0: New §5 GPIO Routing with terminal mapping table, §5.2 assembly rules, §5.3 pin-to-terminal map
- **[SPEC]** HW-001 §7 LiDAR: Pin table now references IDC40P terminal numbers instead of Jetson pins
- **[DIAGRAM]** Created `wire_11_terminal_block_hub.drawio` — visualizes full chain with Yahboom/IP67 zone separation
- **[DIAGRAM]** Updated `wire_09_gpio_pinout.drawio` — new pin assignments (BCM17/27), IDC40P terminal branding
- **[DIAGRAM]** Updated `wire_06_lidar_i2c.drawio` — source changed from Jetson GPIO to IDC40P screw terminals
- **[DIAGRAM]** Updated `wire_04_relay_gimbal.drawio` — BCM 27 (Terminal 13), terminal block as source
- **[DIAGRAM]** Updated `zone2_logic.drawio` — terminal block as central routing hub
- **[DIAGRAM]** Improved text contrast across all updated diagrams (bright text on dark backgrounds)
- **[DIAGRAM]** Repositioned wire labels to avoid overlap with wire paths and objects
- **[ECO]** CSI-to-HDMI "Umbilical" physical topology — Zone A/B/C separation for Sniper camera chain
- **[SPEC]** HW-001 §2.1: Added Vision Subsystem Physical Topology (Zone A: gimbal payload, Zone B: FPV umbilical, Zone C: static enclosure)
- **[SPEC]** HW-001 §2.2: Scout camera simplified chain documented
- **[BOM]** HDMI cable constraint: Must be ultra-thin FPV-grade, ribbon-like. Standard monitor cables PROHIBITED (will stall Storm32 motors)
- **[DIAGRAM]** Rebuilt `wire_07_camera_csi_chain.drawio` with Zone A/B/C color-coded separation and wavy FPV cable visualization
- **[DIAGRAM]** Rebuilt `wire_11_terminal_block_hub.drawio` — fixed empty rendering issue

## 2026-05-15 — GRAVITY AIRBURST & SENTRY CONTROL CENTER
- **[FEATURE]** Implemented "Gravity Airburst" fluid dynamics strategy in `hardware.py`
- **[CODE]** `hardware.py`: Replaced parabolic drop with `AIRBURST_PITCH_OFFSET` (default +12°) in `compute_predictive_lead`
- **[CODE]** `hardware.py`: Increased `trigger_pump` pulse duration from 0.3s to 0.6s to maximize Orbit Micro-Mist nozzle pressure
- **[GUI]** Added dynamic Airburst Pitch Offset slider to `templates/index.html` (range 0° to +30°) and created `/api/airburst/set` in `app.py`
- **[TOOL]** Created `tools/sentry_control_center/app.py` — Windows 10/11 Streamlit GUI for dual-architecture tuning
- **[TOOL]** Implemented OpenCV MOG2 Scout Tuner tab with Threshold/Min Area sliders and live video preview
- **[TOOL]** Implemented YOLOv8 Sniper Trainer tab with background `subprocess.Popen` execution to prevent Streamlit UI freeze during hours-long training
- **[DOCS]** Added `tools/sentry_control_center/requirements.txt` with strict instructions for CUDA PyTorch installation to utilize RTX 3070 VRAM
- **[DOCS]** Added `tools/sentry_control_center/instructions.md` with usage instructions

## 2026-05-15 — TWO-BRAIN DUAL-PIPELINE REFACTORING
- **[ARCHITECTURE]** Refactored monolithic Flask app into a high-performance modular pipeline for Jetson deployment
- **[CODE]** Created `scout_vision.py` (Pipeline 1) running GStreamer `sensor-id=0` at 120FPS with OpenCV MOG2 in a dedicated background thread
- **[CODE]** Created `sniper_vision.py` (Pipeline 2) running GStreamer `sensor-id=1` with YOLOv8 classification evaluating for 'Mosquito' with >0.80 confidence
- **[CODE]** Created `gimbal_controller.py` to decouple Storm32 UART communication
- **[CODE]** Created `weapon_system.py` to decouple Jetson.GPIO relay pulse (preserving 0.6s Airburst specification)
- **[CODE]** Created `main.py` orchestrator using asyncio (`asyncio.sleep(0.2)`) to manage the deterministic sequence: Detect → Aim → Settle → Verify → Fire
- **[PERFORMANCE]** Enforced `appsink drop=true max-buffers=1` on all GStreamer pipelines to prevent buffer build-up and avoid CUDA OOM crashes on the 8GB Orin Nano
- **[COMPLIANCE]** Added spec traceability docstring headers (`# Implements: SW-001...`) to all newly created Python modules to enforce spec-driven development rules
