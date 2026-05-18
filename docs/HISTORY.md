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

## 2026-05-15 — POST-COMMIT REVIEW & FIXES
- **[BUG FIX]** `weapon_system.py`: Corrected relay pin from 18 (pre-ECO) to BCM 17 (IDC40P Terminal 11) per ECO-2026-002
- **[DOCS]** `agents.md`: Synced agent filenames with actual codebase (`gimbal_control.py` → `gimbal_controller.py`, `sniper_logic.py` → `sniper_vision.py`, `weapons_hot.py` → `weapon_system.py`)
- **[DOCS]** `agents.md`: Updated TriggerAgent specification from 300ms/GPIO 18 to 600ms/BCM 17 (Gravity Airburst)
- **[FEATURE]** Added `💾 Export scout_config.json` button to Sentry Control Center Scout Tuner tab — writes tuned MOG2 parameters for direct Jetson deployment
- **[BUG FIX]** Fixed infinite video loop in Scout Tuner — now processes once and displays frame/detection statistics
- **[FEATURE]** Added post-training `best.pt` path display to Sniper Trainer tab
- **[DOCS]** Rewrote `tools/sentry_control_center/instructions.md` with full export workflow and TensorRT conversion guide
- **[CODE]** Committed previously untracked `3d_prints/viewer.html` (OpenSCAD nozzle bracket viewer)

## 2026-05-15 — GAP ANALYSIS & REMEDIATION
- **[PROCESS]** Conducted full end-to-end project audit — identified 8 gaps across critical, significant, and minor categories
- **[SPEC]** Rewrote `SW-001-software-spec.md` to v3.0: synced all filenames, updated physics to Gravity Airburst, added orchestration sequence (§3), added training pipeline section (§7)
- **[CODE]** Shipped default `scout_config.json` with sensible MOG2 defaults so first Jetson boot doesn't fail
- **[BUG FIX]** Fixed `sentry.service` — changed `ExecStart` from `app.py` to `main.py` to match Two-Brain architecture
- **[CODE]** Created `deploy.sh` — rsync-based deployment script for dev→Jetson code transfer with dependency installation
- **[CODE]** Added persistent engagement logging to `main.py` — structured JSONL log (`engagements.jsonl`) recording every fire/reject event with coordinates, offsets, and session statistics
- **[CODE]** Created `phantom_ping.py` — interactive and CLI calibration tool for tuning airburst offset, saves results to `calibration.json`
- **[CODE]** Created `ir_controller.py` — GPIO-controlled IR illuminator with dusk/dawn auto-scheduling (checks system time every 60s)
- **[DOCS]** Created `docs/DATASET_STRATEGY.md` — end-to-end guide for building the mosquito training dataset (Roboflow workflow, labeling, iterative improvement)
- **[DOCS]** Created `README.md` — project overview, architecture diagram, directory structure, quick start guide
- **[PROCESS]** Updated `.gitignore` — added `engagements.jsonl`, `calibration.json`, `runs/`, `*.pt`, chat history files

## 2026-05-15 — OPERATIONS GUIDE & LIFECYCLE COMPLETION
- **[SPEC]** Created `OPS-001-operations-guide.md` — 9-phase lifecycle guide covering procurement, Jetson setup (WiFi, static IP, SSH), assembly sequence, deployment, calibration, field testing, daily operation, scheduling, and maintenance
- **[SPEC]** Updated `SYS-001-system-overview.md` to v2.0 — synced filenames, strategy, added supporting modules table
- **[SPEC]** Updated `SAFE-001-safety-spec.md` to v1.1 — GPIO 18 → BCM 17
- **[SPEC]** Updated `TEST-001-test-plan.md` — GPIO 18 → BCM 17 in kill switch test
- **[DOCS]** Updated `rules.md` — GPIO 18 → BCM 17, aligned human override note with SAFE-001 §2
- **[CODE]** Created `status_indicator.py` — piezo buzzer controller (BCM 4) with boot/engagement/shutdown chime patterns
- **[CODE]** Integrated `IRController` and `StatusIndicator` into `main.py` orchestrator (auto-schedule IR, buzzer on boot/fire/shutdown)
- **[DESIGN]** Documented water reservoir placement recommendation: above enclosure for gravity-assisted pump feed, minimal tubing length (< 3ft)
- **[DESIGN]** Documented piezo buzzer hardware addition (~$2) for audible human notification
- **[PROCESS]** Documented cron-based scheduling for time-of-day sentry activation

## 2026-05-15 — ECO-2026-003: PUMP TYPE CHANGE
- **[ECO]** Replaced Velleman 12V submersible centrifugal pump with 12V DC diaphragm pump (60 PSI, self-priming)
- **[RATIONALE]** Submersible pumps suffer destructive short cycling (3-8× inrush current per 600ms burst). Diaphragm pumps are positive displacement and designed for rapid on/off duty cycles. Inspired by water flosser reciprocating piston pump teardown analysis.
- **[HW-001]** Updated §8 Fluid System with ECO-2026-003 notice, new pump specs, and mounting instructions
- **[BOM]** Updated `parts.csv` — replaced submersible pump with 12V DC diaphragm pump (~$25 CAD)
- **[IMPACT]** Zero software changes required — relay circuit and GPIO pulse timing are unchanged

## 2026-05-15 — STREAM AND SWEEP FIRING LOGIC
- **[CODE]** `scout_vision.py` — Added trajectory velocity vector (vx, vy px/sec) via ring buffer + `get_target_with_velocity()`
- **[CODE]** `weapon_system.py` — Added non-blocking `fire_sweep()` (background thread), `cease_fire()` emergency stop, `is_firing` property
- **[CODE]** `gimbal_controller.py` — Added `aim_async()`, `sweep()`, `sweep_async()` via `run_in_executor` for non-blocking UART
- **[CODE]** `main.py` — Rewrote orchestrator: predictive targeting + parallel fire/sweep. Pump starts WHILE gimbal sweeps → "wall of water"
- **[SPEC]** `SW-001` updated to v4.0 — documents Stream-and-Sweep sequence, 400ms sweep duration, 100ms pump spin-up compensation
- **[DIAGRAM]** Added `stream_sweep_timing.png` — timing diagram showing parallel pump/gimbal/scout/sniper swim lanes

## 2026-05-16 — COMPREHENSIVE AUDIT #2
- **[SPEC]** `HW-001` Sniper FPS 60→30 (matches code), yaw range annotated with software endstop ±80°, Velleman→Diaphragm pump in Wago GND + flyback §6.1
- **[SPEC]** `SW-001` physics model: "mist cloud/rain AoE" → "direct pressurized stream/sweep curtain" (diaphragm pump shoots, not drops)
- **[SPEC]** `OPS-001` procurement references `moreparts.csv` (16 required items)
- **[CODE]** `app.py` fire endpoint default 0.3s→0.4s; "Gravity Airburst" comment → "Airburst Offset"
- **[CODE]** `sniper_vision.py` auto-detects `.engine` before `.pt` fallback (TensorRT acceleration)
- **[CODE]** `ir_controller.py` + `status_indicator.py` added GPIO.setwarnings(False) to prevent multi-module warnings
- **[CODE]** `hardware.py` endstop comment clarified (mechanical vs software limits)
- **[TOOLS]** `sentry_control_center/app.py` post-training UI now includes TensorRT export instructions

## 2026-05-16 — DIRECT STREAM FIRE: PHYSICS MODEL PIVOT
- **[ARCH]** Officially discarded "Gravity Airburst / mist cloud / AoE rain" paradigm. System now uses DIRECT RECTILINEAR STREAM FIRE — 60 PSI diaphragm pump shoots a pressurized stream directly at or sweeping across the target.
- **[CODE]** Renamed `airburst_offset_deg` → `arc_compensation_deg` across `weapon_system.py`, `main.py`, `hardware.py`, `app.py`, `phantom_ping.py`
- **[CODE]** `main.py` engagement log: mode → `DIRECT_STREAM_SWEEP`, field `sweep_duration_sec` → `stream_duration_ms`, added `arc_compensation_deg` to log
- **[CODE]** `weapon_system.py` getter renamed: `get_airburst_offset()` → `get_arc_compensation()`
- **[CODE]** `phantom_ping.py` reframed: "Airburst Calibration Tool" → "Stream Arc Calibration Tool"
- **[SPEC]** `SW-001` §2.6.3: "Gravity Airburst Offset" → "Arc Compensation" with updated physics rationale
- **[SPEC]** `OPS-001`, `SYS-001`, `spec.md`, `README.md`: all airburst references → arc compensation / direct stream
- **[NOTE]** `HISTORY.md` entries from earlier sessions intentionally preserved as historical record (they reflect the state at the time)
- **[NOTE]** `/api/airburst/set` route name kept for backward compatibility with existing dashboard HTML

## 2026-05-16 — INVERTED GIMBAL GEOMETRY & LINEAR DROP PHYSICS
- **[ARCH]** Redesigned chassis to a vertically condensed "Hanging Dome". Gimbal and cameras now hang INVERTED from the enclosure baseplate and fire downward.
- **[CODE]** `hardware.py` & `main.py`: Inverted `pixel_to_angle` mapping so positive Y pixel offset translates to a positive pitch command (aiming downward).
- **[CODE]** `hardware.py`: Refactored `compute_ballistic_offset` and `compute_predictive_lead`. Replaced parabolic drop math with a direct-fire linear stream drop (-0.5° per meter beyond 3m).
- **[CODE]** `main.py` & `app.py`: Hooked orchestrator directly into `LiDARController` to dynamically calculate linear drop based on distance instead of static GUI slider.
- **[CODE]** `gimbal_controller.py`: Added `downward_bias_deg` to `sweep()` to paint the downward-sloping ground plane during Stream-and-Sweep.
- **[SPEC]** `HW-001` and `SW-001`: Updated to reflect inverted dome orientation, revised physical stacking, and linear trajectory physics.
- **[DIAGRAM]** Regenerated 6 core architectural diagrams to reflect the inverted dome and linear trajectory physics. Moved out-of-date images to `diagrams/images/archive/`.

## 2026-05-16 — GIMBAL PAYLOAD AND NIGHT OPERATION DIAGRAMS
- **[DIAGRAM]** Regenerated `gimbal_payload_v3.png` to highly detailed 3D CAD style, correctly showing the inverted Arducam IMX219, CSI-to-HDMI TX board, FPV HDMI cable, LiDAR, and water nozzle.
- **[DIAGRAM]** Regenerated `night_operation_view.png` to depict the inverted dome turret in low-light conditions with the active 850nm IR illuminator casting a volumetric beam.
- **[DIAGRAM]** Regenerated `full_system_assembled.png`, `10_fluid_system_assembly.png`, `6_enclosure_internal_layout.png`, and `9_csi_camera_chain.png` to reflect the inverted dome architecture, diaphragm pump, and CSI-TX board wiring.
- **[NOTE]** Old diagram versions moved to `diagrams/images/archive/`.

## 2026-05-17 — MULTI-PLATFORM ML ENGINE & DATA GOVERNANCE
- **[TOOL]** Updated `tools/sentry_control_center/app.py` to support dynamic hardware auto-detection (CUDA -> MPS -> CPU) for YOLOv8 training.
- **[TOOL]** Added CLI execution support to `app.py` via `argparse`, bypassing Streamlit UI when invoked directly from the terminal. Resolves YOLO binary path using `sys.executable` to prevent path issues in venv.
- **[TOOL]** Established `tools/sentry_control_center/dataset/` to ingest real Kaggle mosquito/fly data (`FLY_MOS_Dataset`) and prepared it with `data.yaml`.
- **[TEST]** Executed a test training run on Apple Silicon MPS via CLI, verifying model convergence and deployment artifact auto-copy to `models/trained/best.pt`.
- **[GOVERNANCE]** Enforced strict project-wide ban on generating dummy data. Added explicit anti-dummy rules to `rules.md`, `gemini.md`, `agents.md`, and `SW-001`.
- **[DOCS]** Added `results.md` inside `tools/sentry_control_center/` capturing the CLI training metrics and evaluation summary.

## 2026-05-17 — 100-EPOCH TRAINING, SEC-001 INCIDENT, & MOUNTING CONCEPTS
- **[TRAINING]** Successfully completed the 100-epoch YOLOv8 tuning on Apple Silicon (MPS). Automatically captured results to `results.md` (mAP50: 0.956) and deployed `best.pt`.
- **[SECURITY]** GitGuardian alerted an accidental leak of the Roboflow API key in commit `54cf587` because `.env` was not ignored.
- **[SECURITY]** Remediated leak: removed `.env` from git tracking, added to `.gitignore`, and pushed. Advised user to revoke the API key immediately.
- **[GOVERNANCE]** Added Rule 13 (SECRET PROTECTION) to `rules.md` explicitly banning `git add .` and `.env` commits.
- **[DESIGN]** Created `docs/mounting_concepts/README.md` outlining 10 creative hardware-store mounting strategies for the inverted dome turret (umbrella, tripod, gallows, zipline, etc.).
- **[DIAGRAM]** Generated and embedded 10 photorealistic mockups to `docs/mounting_concepts/images/` alongside structural Mermaid diagrams for each concept.
- **[ARCHITECTURE]** Formalized the "Top-Hat Core Suspension Stack" mechanical design. Solved the inverted clearance issue by using the horizontal IP67 box as the structural core, mounting a 12" protective acrylic dome on top, and bolting the inverted Storm32 gimbal through the floor.
- **[DIAGRAM]** Generated a photorealistic visualization of the Top-Hat Core Suspension Stack (`top_hat_core_suspension_*.png`) and added it to the master blueprint in `docs/mounting_concepts/README.md`.
- **[DESIGN]** Added "Part 3: The Weatherproof Inverted Series" to `docs/mounting_concepts/README.md`. Includes the "Inverted Gallows Telescoping Post" and "Inverted Cantilever Umbrella Conversion" specialized for the hanging dome architecture.
- **[DIAGRAM]** Generated and embedded 2 photorealistic mockups (`inverted_gallows_post_*.png`, `inverted_cantilever_umbrella_*.png`) for the Weatherproof Inverted Series.
- **[DESIGN]** Promoted the "Heavy-Duty PA Speaker Stand (Quick-Release Tripod)" to the absolute #1 recommended mounting solution in `docs/mounting_concepts/README.md`. This perfectly pairs with the Top-Hat Flange to allow sub-10 second breakdown between indoor development and outdoor testing.
- **[DESIGN]** Promoted the "Heavy-Duty PA Speaker Stand (Quick-Release Tripod)" to the absolute #1 recommended mounting solution in `docs/mounting_concepts/README.md`. This perfectly pairs with the Top-Hat Flange to allow sub-10 second breakdown between indoor development and outdoor testing.
- **[DIAGRAM]** Generated a photorealistic mockup (`tripod_top_hat_studio_*.png`) showing the PA Tripod setup in an indoor office environment with a water tote counterweight.
- **[ARCHITECTURE]** Formalized the "Deep Bell Canopy" weather shield evolution. Replaced the 12" acrylic top dome with an 18" inverted heavy-duty plastic planter (bell/lampshade).
- **[DESIGN]** The Deep Bell Canopy protects the inverted Storm32 gimbal motors from angled rain by recessing them high inside the bell, while leaving the bottom wide open for unhindered 45 PSI water firing and natural heat sink ventilation.
- **[DIAGRAM]** Generated and embedded a photorealistic mockup (`deep_bell_canopy_*.png`) showing the Deep Bell architecture on the tripod mount.
- **[DESIGN]** Expanded the Deep Bell Canopy section with three commercial-grade aesthetic upgrades: the "Stealth Industrial" Spun Aluminum Pendant Shade (Top Pick, passive heatsink), the "Sci-Fi Orb" Smoked Acrylic Globe (UV blocking, wire-hiding), and the "Mil-Spec Security" Gutted PTZ Housing (built-in fan cooling).
- **[DIAGRAM]** Generated and embedded 2 photorealistic mockups (`stealth_industrial_pendant_*.png`, `scifi_orb_globe_*.png`) showcasing these premium materials.
