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
- **[ARCHITECTURE]** Formalized the "Tiered Lighthouse Assembly." This master architecture solves the FOV problem by splitting vision and mechanics. The stationary Scout/IR array sits in an upright clear 8" dome on the *roof* of the IP67 box, while the Storm32 Gimbal/Sniper array hangs in a 16" black pendant shade from the *floor* of the IP67 box.
- **[DIAGRAM]** Generated a photorealistic mockup (`tiered_lighthouse_assembly_*.png`) showing this dual-stack maritime defense aesthetic.
- **[DESIGN]** Added three High-End Commercial Lighthouse forms: the Scandinavian Architectural Pillar (clear polycarbonate with metal caps), the Streamlined Marine Radome (fiberglass dome with panoramic tinted window), and the Minimalist Tech-Pod (smoked dark acrylic cylinder with internal floating chassis).
- **[DIAGRAM]** Generated and embedded 3 photorealistic mockups (`scandinavian_pillar_*.png`, `marine_radome_*.png`, `minimalist_tech_pod_*.png`) visualizing these premium aesthetic product designs.
- **[DESIGN]** Added three Off-The-Shelf Commercial Conversions to the Lighthouse architecture section: the "Studio-Tech" Column (Acrylic Display Cylinder + Anodized Wine Chiller), the "Bollard Monolith" (Commercial Pathway Lens + Internal Vinyl Masking), and the "Mil-Spec Marine" Shroud (Brushed Stainless Steel Vessel + Panoramic Optical Slot).
- **[DIAGRAM]** Generated and embedded 3 photorealistic mockups (`studio_tech_column_*.png`, `bollard_monolith_*.png`, `milspec_marine_shroud_*.png`) visualizing these readily available design options.
- **[DESIGN]** Expanded the Off-The-Shelf Commercial Conversions with 3 more variations: the "Dual-Tier Urban" Post Globe, the "Scandinavian Tiered" Canopy, and the "Tech Capsule."
- **[DIAGRAM]** Generated and embedded 3 photorealistic mockups (`dual_tier_urban_globe_*.png`, `scandinavian_tiered_canopy_*.png`, `tech_capsule_*.png`) showcasing these additional aesthetic options.
- **[ARCHITECTURE]** User selected the "Scandinavian Tiered Canopy" (Nesting Matte-Black Metal Pendant Shades) as the FINAL structural design.
- **[SPEC]** Created `docs/specs/HW-002-scandinavian-canopy.md` establishing the formal build guide, Home Depot / Amazon Bill of Materials (BOM), and step-by-step assembly instructions.
- **[DIAGRAM]** Generated 7 highly detailed photorealistic images exploring the Scandinavian Tiered Canopy from various angles (front, high, low, exploded, gap close-up, skirt interior, night mode) and embedded them into the `HW-002` spec.

## 2026-05-19 — SCANDINAVIAN CANOPY DESIGN SCHEMATIC UPDATE
- **[DIAGRAM]** Added the final "Scandinavian Tiered" canopy design layout/schematic diagram to `docs/specs/HW-002-scandinavian-canopy.md` and moved the image asset to the centralized `docs/mounting_concepts/images/` directory.

## 2026-05-20 — MULTI-BUG TRAINING AND TARGET VERIFICATION
- **[FEATURE]** Expanded precision classifier from single-class (mosquito) / dual-class targeting to support 15 common backyard bug classes.
- **[CODE]** `download_dataset.py`: Sourced and ingested version 2 of the `tiger-emltm/insects-9yf6s` YOLOv8 dataset (15 classes) from Roboflow Universe using `.env` secrets.
- **[CODE]** `sniper_vision.py`: Refactored target verification to case-insensitively check predicted labels against all 15 insect classes (`spider`, `bees`, `butterfly`, `mantis`, `ant`, `beetle`, `caterpillar`, `centipedes`, `cockroach`, `dragonfly`, `fly`, `grasshopper`, `ladybug`, `mosquito`, `wasp`).
- **[CODE]** `vision.py`: Modified legacy/fallback `YOLODetector.detect` to include `"is_safe": True` in all returned detection dicts to ensure full backward compatibility with testing suites.
- **[SPEC]** `SW-001` updated to v5.0: Synced target classification logic, safety parameters, and training pipeline descriptions.
- **[DEPLOYMENT]** Proactively updated `deploy.sh` to automatically copy the compiled 15-class `best.pt` model weights to both `best.pt` (for `main.py` daemon) and `models/yolov8n.pt` (for `app.py` dashboard visualizer) on the Jetson, and added system checks requesting a TensorRT engine re-export to accommodate the 15-class detect head changes.


## 2026-05-20 — 100-EPOCH MULTI-CLASS YOLO TRAINING COMPLETE

- **[TRAINING]** Completed 100-epoch YOLOv8n training on 15-class insect dataset (`tiger-emltm/insects-9yf6s`) on Apple M4 Pro (MPS). Total wall-clock time: **11.593 hours**.
- **[TRAINING]** Final validated metrics (best.pt): **mAP50 = 0.891**, mAP50-95 = 0.565, Precision = 0.891, Recall = 0.842. 925 images, 1028 instances evaluated.
- **[TRAINING]** Per-class mAP50: Butterfly 0.988, Fly 0.993, Spider 0.965, Ladybug 0.961, Mosquito **0.918** (primary target), Caterpillar 0.901, Wasp 0.862, Cockroach 0.853, Dragonfly 0.794, Grasshopper 0.847, Ant 0.833, Centipedes 0.836, Beetle 0.837, Bees 0.888, Mantis 0.887.
- **[DEPLOYMENT]** Trained weights automatically deployed to `models/trained/best.pt` by Sentry Control Center CLI post-training hook.
- **[DEPLOYMENT]** `deploy.sh` confirmed up-to-date — Jetson-side alignment hook copies weights to `best.pt` (main orchestrator) and `models/yolov8n.pt` (dashboard visualizer) with TensorRT re-export prompt.
- **[DOCS]** `docs/DATASET_STRATEGY.md` updated to reflect 15-class automated ingestion pipeline and CLI training → deploy.sh workflow.
- **[DOCS]** `docs/specs/SW-001-software-spec.md` corrected to v5.0: class count annotation 14 → 15.
- **[DOCS]** `docs/specs/TEST-001-test-plan.md` promoted DRAFT → APPROVED; T3.3 updated to "Large-Object Rejection".
- **[DECISION]** Removed `*.pt` exclusion from `.gitignore` following user design request to track custom model weight files in version control.

## 2026-05-26 — INITIAL JETSON DEPLOYMENT AND CONNECTION VERIFICATION
- **[CONNECTION]** Successfully verified physical connection to the NVIDIA Jetson Orin Nano SUPER (192.168.0.196) via network ping and automated SSH passwordless login using local SSH keys.
- **[DEPLOY]** Deployed the first software stack to `/home/jetson/dropMosquitoes` on the Jetson Orin Nano SUPER using the system's `deploy.sh` script.
- **[BUG FIX]** Resolved a NumPy 2.2.6 compatibility issue on the Jetson that broke OpenCV and Ultralytics by downgrading it to `numpy<2` (specifically version `1.26.4`). Locked the numpy dependency in `requirements.txt` to `numpy>=1.24.0,<2.0.0` to prevent future deployment breakage.
- **[CAMERA DETECT]** Investigated camera detection of newly connected OV9281 (Scout) and IMX219 (Sniper). Found they are currently undetected due to the active `primary` boot label in `extlinux.conf` disabling overlays on boot, and noted that JetPack 6 lacks the out-of-the-box driver module for OV9281.
- **[CAMERA CONFIG]** Patched the Jetson bootloader `/boot/extlinux/extlinux.conf` to boot via `JetsonIO` by default. Triggered a remote reboot to load the device tree overlays.
- **[CAMERA VERIFY]** Verified that the reboot successfully brought the physical IMX219 (Sniper Camera) online at `/dev/video0`. The background systemd `sentry` daemon automatically started on boot, claimed the IMX219 camera device, and is successfully capturing frames!

## 2026-05-27 — ECO-2026-004: SCOUT CAMERA OV9281 → IMX219 SWAP
- **[DIAGNOSTIC]** Ran comprehensive I2C bus scan across all buses (0-11) on the Jetson Orin Nano SUPER to locate the OV9281 sensor.
- **[DIAGNOSTIC]** Confirmed OV9281 hardware is **100% functional** — Chip ID register read (`i2ctransfer -y 9 w2@0x60 0x30 0x0a r2`) returned `0x92 0x81` (correct silicon ID for OV9281).
- **[DIAGNOSTIC]** OV9281 detected at I2C address `0x60` on both bus 9 (CSI mux channel 0) and bus 2 (raw I2C bus).
- **[DIAGNOSTIC]** Root cause identified: `dmesg` shows `imx219 9-0010: imx219_board_setup: error during i2c read probe (-121)` — the `imx219-dual.dtbo` overlay tries to probe bus 9 at address `0x10` (IMX219 default), but the OV9281 lives at `0x60`.
- **[DIAGNOSTIC]** Confirmed **no kernel driver** (`nv_ov9281.ko`) exists anywhere in `/lib/modules/5.15.148-tegra/`. No Arducam packages are installed.
- **[DIAGNOSTIC]** Confirmed **no device tree overlay** for OV9281 exists in `/boot/`. Only IMX219 and IMX477 overlays are available in JetPack 6 (L4T R36.4.7).
- **[RESEARCH]** Exhaustive search of Arducam GitHub (`MIPI_Camera` repo), Arducam Docs, NVIDIA Developer Forums, and public kernel sources. Result: No pre-built OV9281 driver or DTBO available for L4T 36.x. Arducam's Jetvariety driver only provides pre-built binaries for old Nano and Xavier NX, and requires a proprietary adapter board.
- **[ECO]** **ECO-2026-004 Decision:** Replace the OV9281 Scout Camera with a second Arducam NoIR IMX219 8MP module. Rationale:
  - The existing `tegra234-p3767-camera-p3768-imx219-dual.dtbo` overlay will instantly detect both cameras on buses 9 and 10 with zero kernel modifications.
  - The Scout camera's MOG2 background subtraction pipeline does not benefit from global shutter — rolling shutter at 60fps is more than sufficient for blob centroid detection.
  - Cost: ~$25 CAD. Time to operational: immediate (plug and play).
- [CODE] `scout_vision.py`: Updated GStreamer pipeline from `1280x800@120fps` (OV9281) to `1280x720@60fps` (IMX219 Mode 4).
- [CODE] `main.py`: Updated Scout FOV constants from OV9281 (110°H × 75°V, 1280×800) to IMX219 (62.2°H × 48.8°V, 1280×720).
- [SPEC] `HW-001-hardware-spec.md`: Updated §2 camera table and §2.2 Scout Camera section with ECO-2026-004 notice and new IMX219 specifications.

## 2026-05-27 — MONOCULAR SHARED-CAMERA RECOVERY
- **[DECISION]** Aborted custom out-of-tree OV9281 driver compilation on JetPack 6 to eliminate kernel panics.
- **[ARCH]** Implemented Monocular Shared-Camera Architecture (Option 1) using a single physical IMX219 on CSI-0 (`/dev/video0`).
- **[CODE]** `vision.py`: Created `SharedCameraStream` proxy class and added `os.path.exists` device safety checks.
- **[CODE]** `app.py`: Hooked up Sniper stream to consume from Scout's CSI-0 feed.
- **[CODE]** `scout_vision.py`: Switched to native GStreamer Mode 4 (1280x720@60fps) and cached latest frames.
- **[CODE]** `sniper_vision.py`: Bypassed CSI-1 raw device probing and refactored `verify_target` to accept frames.
- **[CODE]** `main.py`: Retrieved frames from Scout and passed them to Sniper for YOLO target verification.
- **[CODE]** `deploy.sh`: Made custom driver loading conditional to prevent deploy exit failures in Monocular Mode.
- **[TEST]** Verified 60.2 FPS GStreamer capture on Jetson CSI-0 and running background sentry systemd daemon.

## 2026-05-27 — WATCHDOG INTEGRATION & GIMBAL SERIAL PATH CORRECTION
- **[BUG FIX]** `main.py`: Implemented systemd watchdog keep-alive loop (`watchdog_ping_loop`) running asynchronously every 15 seconds to satisfy `WatchdogSec=60` and prevent premature systemd SIGABRT daemon termination.
- **[BUG FIX]** `sentry.service`: Corrected absolute path of `nvpmodel` pre-start command to `/usr/sbin/nvpmodel`.
- **[CODE]** `gimbal_controller.py` & `hardware.py`: Implemented dynamic gimbal serial port auto-detection (prioritizing `/dev/ttyTHS1` over `/dev/ttyTHS0`) to natively support the Yahboom carrier board header pins under JetPack 6.
- **[CODE]** `tests/test_serial.py`: Changed default test argument port to `/dev/ttyTHS1`.
- **[SPEC]** `HW-001`, `SW-001`, `spec.md`, `agents.md`: Updated hardware serial communications specification to document `/dev/ttyTHS1` and active systemd watchdog notification pings.

## 2026-05-27 — PROCUREMENT ADVICE: SCOUT CAMERA REPLACEMENT (IMX219)
- **[PROCUREMENT]** Evaluated and confirmed compatibility of the **Arducam IMX219 8MP Camera Module ($24.28 CAD)** as the permanent replacement for the Scout Camera (OV9281).
- **[DECISION]** Confirmed plug-and-play compatibility with JetPack 6's built-in `imx219-dual.dtbo` overlay. Recommended the **Arducam NoIR IMX219** variant for night operation consistency with the 850nm IR illuminator.

## 2026-05-27 — PROCUREMENT ADVICE: SCOUT CAMERA REPLACEMENT (NoIR IMX219)
- **[PROCUREMENT]** Evaluated and confirmed the **Arducam NoIR IMX219 8MP Camera Module ($53.70 CAD)** as the optimal 24/7 replacement for the Scout Camera.
- **[DECISION]** Confirmed 100% hardware compatibility (includes 15-to-22 pin FPC cable for Orin Nano CSI ports).
- **[DESIGN]** Verified that the lack of an IR-cut filter enables flawless night tracking using the 850nm IR illuminator. Documented that while daylight footage will appear pink/purple (due to solar IR), this color distortion has zero negative impact on the Scout's OpenCV MOG2 Background Subtraction, which analyzes grayscale motion blobs.

## 2026-05-27 — SCOUT CAMERA ORDERED: FULL CODEBASE DOCUMENTATION SWEEP
- **[PROCUREMENT]** User ordered the **Arducam NoIR IMX219 8MP Camera Module ($53.70 CAD)**.
- **[SPEC]** `HW-001`: Removed transitional ECO-2026-004 references. Scout camera row now reads "Arducam NoIR IMX219 8MP". §2.2 rewritten to describe 24/7 day+night operation.
- **[SPEC]** `SW-001`: Updated ScoutAgent input from `OV9281 @ 120FPS` to `IMX219 NoIR @ 60FPS`.
- **[SPEC]** `SYS-001`: Updated ScoutAgent role and Physical Topology section.
- **[SPEC]** `OPS-001`: Updated incoming inspection, assembly step 10, and camera calibration section.
- **[SPEC]** `spec.md`: Updated Scout Camera entry with correct resolution and FPS.
- **[CODE]** `scout_vision.py`: Updated GStreamer pipeline comments to reference IMX219 NoIR.
- **[CODE]** `main.py`: Updated FOV constant comments to reference IMX219 NoIR 24/7 operation.
- **[CODE]** `deploy.sh`: Removed legacy OV9281 kernel driver sync block (both cameras now native IMX219).
- **[DOCS]** `gemini.md`: Updated camera verification comments.
- **[DOCS]** `README.md`: Updated Scout Camera description and hardware list.
- **[DOCS]** `prompt.md`: Updated Scout Camera from OV9281 to IMX219 NoIR.
- **[DOCS]** `3d_prints/PRINT_GUIDE.md`: Updated PCB references from OV9281 to IMX219 NoIR.
- **[DOCS]** `docs/mounting_concepts/README.md`: Updated Lighthouse architecture camera reference.
- **[DIAGRAM]** `sentry_diagram.drawio`: Updated Scout camera cell from OV9281 to Arducam NoIR IMX219.
- **[DIAGRAM]** `diagrams/arch_11_software_v2.drawio`: Updated ScoutAgent camera from OV9281@120fps to IMX219 NoIR@60fps.
- **[DIAGRAM]** `diagrams/wire_07_camera_csi_chain.drawio`: Updated Scout Camera note.
- **[DIAGRAM]** `diagrams/zone2_logic.drawio`: Updated Scout label from OV9281 to IMX219 NoIR.

## 2026-05-27 — FIX: run-ai.sh / stop.sh now target Jetson via SSH
- **[FIX]** `run-ai.sh`: Was running the Flask server **locally on the dev machine**, using the Mac's webcam instead of the Jetson's CSI cameras. Rewritten to: (1) deploy code to Jetson, (2) SSH in, (3) start `app.py` on the Jetson with `nohup`. Dashboard is now accessed via `http://<JETSON_IP>:8000`.
- **[FIX]** `stop.sh`: Now stops both local and Jetson servers. Connects to Jetson via SSH to kill the remote process.
- **[FIX]** `vision.py`: `CameraStream.start()` now detects Jetson vs dev machine. On macOS, falls back to `cv2.VideoCapture(index)` for webcam dev testing.
- **[FIX]** `vision.py`: `VelocityTracker` defaults updated from OV9281 specs (120fps, 110°×75°, 1280×800) to IMX219 NoIR specs (60fps, 62.2°×48.8°, 1280×720).
- **[FIX]** `templates/index.html`: Updated Scout card title from "OV9281 Fixed · 120 FPS" to "IMX219 NoIR Fixed · 60 FPS". Fixed click-to-aim frame height from 800→720.
- **[USAGE]** `./run-ai.sh` — deploy + start on Jetson (default). `./run-ai.sh --local` — dev testing on Mac. `./run-ai.sh --no-deploy` — start without re-deploying.

## 2026-05-27 — REMOTE SHUTDOWN UTILITY
- **[CODE]** Created `shutdown.sh`: Added utility script to remotely power off the Jetson Orin Nano from the host Mac/PC. The script (1) triggers `./stop.sh` to gracefully stop running servers and services, (2) checks network reachability of the Jetson, and (3) logs in via SSH to run `sudo shutdown now` using the password configured in `.env`.

## 2026-05-28 — SCHEMATIC UPDATE: DETAILED POWER DISTRIBUTION
- **[DIAGRAM]** `diagrams/images/power_distribution.png`: Generated a highly detailed wiring schematic clarifying power pathways. The Jetson Orin Nano is connected to a 12V 5A main source via an always-on bypass (no relay). The 12V pump (Relay Channel 1) and the Storm32 turret gimbal (Relay Channel 2) are wired through the Monk Makes Dual Relay Module to enable software power control.
- **[DIAGRAM]** `diagrams/images/power_distribution_with_gpio.png`: Created a dedicated version of the schematic showing the GPIO logic control lines. Pin 11 (BCM 17) uses a Yellow wire to trigger Relay CH1 (Pump), Pin 13 (BCM 27) uses an Orange wire to trigger Relay CH2 (Gimbal), and Pin 9 (GND) connects to the logic ground on the Monk Makes Dual Relay Module.
- **[DIAGRAM]** `diagrams/images/scout_and_ir_placement.png`: Created a detailed dual-view (Front View and Side View) mechanical assembly drawing showing the optimal physical mounting layout of the Scout Camera and the Univivi IR Blaster on the vertical post. Illustrates depth protrusion (camera forward by 1-2" to prevent washout), vertical separation (6-12" to prevent backscatter), and elevation stacking (IR blaster on top so rising heat and bugs swarm clear of the lens).
- **[DIAGRAM]** `diagrams/images/power_distribution_with_wago.png`: Created an advanced wiring schematic showcasing the exact 5-port Wago lever-nut wiring routes for dividing the +12V rail (always-on bypass to Jetson, power to relay inputs) and consolidating the central grounds (Jetson, Relay, Pump, Gimbal) into a unified GND bus.
- **[DIAGRAM]** `diagrams/power_distribution_with_wago.drawio`: Authored a highly accurate vector `.drawio` schematic mirroring the power and control logic routing. Resolves AI rendering anomalies (such as duplicate channel names and overlapping wire routes) by using standard Draw.io shapes, precise connection coordinates, and clear orthogonal routing for Wago ports and GPIO connections.
- **[DIAGRAM]** `diagrams/power_distribution_with_wago.drawio`: Added a 1N4007 flyback protection diode wired in reverse-bias directly in parallel across the 12V diaphragm pump's input terminals (Cathode stripe to positive switched feed, Anode to negative return line) to safely suppress motor voltage spikes and protect the Monk Makes Relay module.
- **[DIAGRAM]** `diagrams/power_distribution_with_wago.drawio`: Redesigned layout to utilize a crisp white background with highly visible dark high-contrast fonts. Simplified the 1N4007 flyback diode wiring by representing it as a direct vertical parallel "ladder bridge" tapped directly into the positive and ground terminals right before they enter the pump motor, completely eliminating loop wires.

## 2026-06-01 — RESTORE FULL DUAL-CAMERA ARCHITECTURE & HARDWARE RESOLUTION
- **[ARCH]** Restored full dual-camera pipeline as both IMX219 NoIR cameras are now physically connected to the system and fully functional.
- **[HW]** Resolved physical camera connectivity issues:
  - Isolated camera port failure by swapping CSI-0 and CSI-1 camera ports on the Jetson, validating the driver and device tree configurations while confirming one of the original camera cables was damaged.
  - Resolved signal issues with the Petit Studio CSI-to-HDMI extension adapters by correcting the ribbon cable orientation (fixing pins being backwards due to a flipped ribbon cable at the connector interface).
  - Replaced the failing ribbon cable with a verified new high-bandwidth flex cable, restoring reliable high-speed GStreamer captures on both MIPI CSI buses.
- **[CODE]** `app.py`: Reverted from shared monocular camera stream to independent `CameraStream(sensor_id=1)` on CSI-1 for the Sniper, while retaining `CameraStream(sensor_id=0)` on CSI-0 for the Scout. Removed unused `SharedCameraStream` imports.
- **[CODE]** `sniper_vision.py`: Restored independent thread capture loop with optimized CSI-1 GStreamer capture pipeline. Integrated an automatic high-performance test pattern fallback for dev machine (non-Jetson) robustness.
- **[CODE]** `main.py`: Reverted the transitional verification logic, calling `sniper.verify_target()` without arguments to trigger target verification directly from the Sniper's independent gimbal-mounted video stream.


## 2026-06-01 — PHYSICAL RELAY MAPPING
- **[DIAGRAM]** `diagrams/power_distribution_with_wago.drawio`: Updated the Monk Makes Dual Relay Module representation to precisely mirror the physical v1b hardware board. Mapped the 3 left input header pins (A, B, GND) to their respective GPIO control feeds (Yellow BCM 17, Orange BCM 27, Black Logic GND) and the 4 right green screw terminal slots (two top slots for A, two bottom slots for B) to the interrupted +12V power feeds to the Pump and Gimbal.

## 2026-06-01 — GPIO PINMUX PUSH-PULL REG OVERRIDE (ECO-2026-004)
- **[HW]** Identified that third-party Jetson carrier boards (Yahboom) initialize the 40-pin header's BCM 17 (Pin 11 / PR.04) and BCM 27 (Pin 13 / PY.00) in Open-Drain mode rather than Push-Pull by default, preventing the pins from sourcing 3.3V logic high signals to trigger external relay modules.
- **[CODE]** `hardware.py`: Integrated `_configure_push_pull()` in `RelayController.__init__` to directly map physical pad multiplexer memory pages (`0x02430000`) and clear Bit 4 (Open Drain) from register `0x02430098` (PR4) and `0x0243d030` (PY0) on startup (works automatically when run as root systemd service).
- **[CODE]** `run-ai.sh`: Added the same `/dev/mem` pad register bitwise override to the startup shell deploy script utilizing `sudo` to configure the pinmux for immediate standard push-pull operation when launching the Flask dashboard.

## 2026-06-01 — GIMBAL PAYLOAD MOUNT SCHEMATIC
- **[DIAGRAM]** `diagrams/images/gimbal_mount_design.png`: Created a highly detailed CAD-style mechanical engineering design schematic (Front View and Side View) demonstrating how to mount a custom 4cm x 4cm sniper camera, a 1cm x 2cm TF-Luna LiDAR, and a 0.75cm x 0.75cm water nozzle onto the action-camera brushless gimbal. Illustrates the vertical co-axial stacking order for perfect roll-axis balance and perfect alignment of all three components' center of gravity with the brushless pitch motor pivot shaft to prevent motor overload.

## 2026-06-02 — GIMBAL WIRING SCHEMATICS CLARIFICATION
- **[DIAGRAM]** `diagrams/wire_04_relay_gimbal.drawio`: Redesigned to clarify physical gimbal power routing. Replaced the generic relay symbol with the custom Monk Makes Dual Relay v1b layout (showing A, B, GND inputs and A/B green output screw terminals). Clearly illustrated the 12V high-power circuit loops: Switched +12V (Screw terminal B2) to Gimbal Red (+) power wire, and Gimbal Black (-) power wire directly back to the central GND Wago Bus (Port 5).
- **[DIAGRAM]** `diagrams/wire_05_gimbal_serial.drawio`: Redesigned to resolve RC header confusion. Added the physical dual-row 2x6 RC header layout (showing GND, RC-0, RC-1, RC-2, and RC-3/RC pins) and explicitly showed that the two rows (inner and outer) are electrically connected in parallel. Documented the exact three-wire UART connection from the Jetson GPIO breakout (Terminals 8, 10, 14) to the outer row pins (GND, RC-0/Pitch, and RC-2/Yaw) to ensure the user knows exactly where to plug in their jumpers.

## 2026-06-02 — GIMBAL SERIAL INTERFACE SELECTION (UART OVER USB)
- **[HW]** Evaluated physical connection options (Direct USB-A-to-Mini-USB vs. 3-Wire UART via IDC40P). Selected standard 3-Wire UART control to align with user's pre-wired setup.
- **[SPEC]** `HW-001-hardware-spec.md` & `SW-001-software-spec.md`: Retained UART communication on `/dev/ttyTHS1` and the physical Terminal Block mappings (Terminals 8, 10, and 14).
- **[CODE]** `hardware.py`: Prioritized `/dev/ttyTHS1` and `/dev/ttyTHS0` at the front of the auto-detect list in `GimbalController.__init__` while retaining USB serial (`ttyUSB0`/`ttyACM0`) as fallback options.
- **[DIAGRAM]** `diagrams/wire_05_gimbal_serial.drawio`: Authored a highly detailed 2x6 dual-row parallel RC pinout schematic showing exactly how to wire the green (TX), blue (RX), and black (GND) jumpers to the outer row pins (GND, RC-0/Pitch, and RC-2/Yaw) from the IDC40P breakout.
## 2026-06-02 — GIMBAL USB INTEGRATION (ECO-2026-005)
- **[HW]** Upgraded gimbal communication interface to use a direct USB-A to Mini-USB cable (connecting Jetson USB 3.2 port to Storm32 Mini-USB port) instead of the 3-wire UART jumper cables to achieve complete electromagnetic noise immunity (from the 12V pump) and eliminate physical connector fatigue/vibration failures.
- **[SPEC]** `HW-001-hardware-spec.md` & `SW-001-software-spec.md`: Updated serial communications sections to adopt USB interfaces and marked the terminal block UART pins 8, 10, and 14 as reserved/unused.
- **[CODE]** `hardware.py`: Added `/dev/ttyUSB0` and `/dev/ttyACM0` to the serial port auto-detection array in `GimbalController.__init__` for plug-and-play USB connection support.
- **[DIAGRAM]** `diagrams/wire_05_gimbal_serial.drawio`: Modified diagram layout to show a direct, single USB cable run from the Jetson's USB-A port to the Storm32's Mini-USB port (labeled USB/调参), replacing the multi-wire UART jumper design.

## 2026-06-02 — GUI GIMBAL CONTROL BUG FIX
- **[BUG FIX]** `templates/index.html`: Fixed HTML ID collision where both the Gimbal Power toggle checkbox and the Test Grid container shared `id="tg"`. Renamed the Test Grid container to `id="test-grid"` and updated `loadTests()` to select `$('test-grid')`. This resolves a critical issue where navigating to the Tests tab destroyed/corrupted the Gimbal Power toggle checkbox, preventing users from turning on gimbal power and causing WASD controls to appear non-functional.

## 2026-06-02 — HARDWARE LIFECYCLE & PINMUX STABILIZATION
- **[CODE]** `hardware.py` & `weapon_system.py`: Refactored `configure_push_pull()` to a module-level helper function and postponed its call to execute immediately **after** `GPIO.setup()` inside both `RelayController.__init__` and `WeaponSystem.__init__`. This prevents `Jetson.GPIO` (which uses `/sys/class/gpio` exports) from resetting the pad registers back to Open-Drain mode.
- **[CODE]** `run-ai.sh`: Updated Step 3 to start `app.py` in background as **root** (using `sudo`) so it possesses mmap write access to `/dev/mem` for register modifications.
- **[CODE]** `run-ai.sh`: Updated Step 2 to terminate existing python processes gracefully (`SIGTERM` via `killall` first, sleeping for 2 seconds, and only then falling back to `kill -9` as a final measure). This allows OpenCV and GStreamer's `nvarguscamerasrc` to safely execute their `atexit` cleanups, close their sockets, and release the CSI-1/CSI-0 camera handles, preventing horizontal line noise/distortion (garbled Bayer outputs) on subsequent startups.

## 2026-06-02 — GIMBAL PURE USB TRANSITION & PROTOCOL FIX
- **[HW]** Purged all UART fallback ports (`/dev/ttyTHS0`/`/dev/ttyTHS1`) from gimbal auto-detection connection lists and serial tests.
- **[CODE]** `gimbal_controller.py`: Refactored to build and transmit standard 18-byte binary `o323BGC` packets over USB instead of NMEA `$CMD` strings, resolving the "limp/dead" non-responsive gimbal behavior in autonomous tracking mode.
- **[CODE]** `tests/`: Refactored `test_usb_gimbal.py`, `test_usb_gimbal_long.py`, and `test_serial.py` to use pure USB (`/dev/ttyACM0`) and serialize commands using the binary protocol.
- **[SPEC]** Updated `HW-001`, `SW-001`, `TEST-001`, `OPS-001`, `spec.md`, and `agents.md` to establish USB serial as the exclusive gimbal communications channel.

## 2026-06-03 — FUSED GIMBAL POWER & RELAY BYPASS (ECO-2026-006)
- **[HW]** Gimbal transitioned to a direct 2A fused power connection on the 12V star topology, completely bypassing the BCM 27 (Relay CH2) power interlock for reliability and constant calibration.
- **[CODE]** `hardware.py`: Refactored `RelayController` to bypass BCM 27 relay logic and report gimbal power state as always `True` (since it is directly powered).
- **[CODE]** `tests/`: Removed relay power toggling and startup boot delays from `test_usb_gimbal.py`, `test_usb_gimbal_long.py`, and `test_usb_gimbal_binary.py`.
- **[SPEC]** Updated `HW-001`, `SAFE-001`, `TEST-001`, `OPS-001`, and `spec.md` to define BCM 27 as reserved/unused and establish the 2A fused power design.

## 2026-06-03 — CATASTROPHIC HARDWARE FAILURE: GIMBAL SHORT CIRCUIT
- **[INCIDENT]** Melted red wire detected, indicating a catastrophic dead short circuit where the gimbal controller (or wiring) created a direct bridge between the 12V and Ground lines.
- **[ANALYSIS]** Because the relay was bypassed and there was likely no inline fuse installed (or it was bypassed), the gimbal pulled the maximum amperage the power supply could deliver (10+ Amps) until the wire physically acted as a fuse and melted.
- **[DIAGNOSTIC]** The audible "beep" during the failure was analyzed:
  - **Power Supply (Most Likely):** Internal Over-Current Protection (OCP) tripped. Rapid discharge of massive internal capacitors when unplugged can produce a sharp electronic "squeak" or double-beep.
  - **Gimbal Motors:** Blown motor driver MOSFETs or voltage regulators on the Storm32 board could cause residual power draining through coils to emit a high-pitched beep/whine as they die.
- **[VERDICT]** The Storm32 controller board is dead and must be quarantined. Do not attempt to wire this gimbal board back to power or connect it to the Jetson via USB or UART, as it is a fire hazard and could push 12V back up the data lines.
- **[RECOVERY PLAN]** Established step-by-step recovery process:
  - **Step A:** Test Power Supply in isolation using a multimeter (expect ~12V; 0V or smell indicates death).
  - **Step B:** Inspect Jetson Orin Nano for physical damage, re-power in isolation, and check status of power LED and booting behavior.

## 2026-06-03 — GIMBAL UART-ONLY TRANSITION & ISOLATION RECOVERY (ECO-2026-007)
- **[HW]** Gimbal transitioned to exclusive 3-Wire UART control (TX on Terminal 8, RX on Terminal 10, GND on Terminal 14). Bypassed and completely disconnected the USB data connection to prevent ground loops and 5V regulator clashes during live operations.
- **[CODE]** `hardware.py` & `gimbal_controller.py`: Restored `/dev/ttyTHS1` and `/dev/ttyTHS0` to the serial port dynamic auto-detection lists with top priority.
- **[CODE]** `gimbal_controller.py`: Fixed `aim()` method to serialize target angles using correct binary `o323BGC` float32 layout and 2-byte zero CRC, matching the Flask HAL protocol.
- **[SPEC]** Updated `HW-001`, `SW-001`, `SAFE-001`, `spec.md`, and `agents.md` specifications to enforce the USB disconnect rule and formalize the UART-only control design.
- **[TEST]** Updated `tests/test_serial.py`, `tests/test_usb_gimbal.py`, `tests/test_usb_gimbal_binary.py`, and `tests/test_usb_gimbal_long.py` to default to `/dev/ttyTHS1` and use the corrected float32 formatting. Successfully verified dynamic serial port activation and sweep operation on the Jetson Orin Nano.

## 2026-06-03 — GIMBAL USB SERIAL CONTROL RESTORED

- **[HW]** Discovered UART pins (Terminals 8/10 on IDC40P) are non-functional for gimbal communication. No electrical activity detected.
- **[HW]** Confirmed IDC40P PWM pins (Terminals 32/33) are dead — Yahboom carrier board reads constant 2.90V DC regardless of software PWM state.
- **[HW]** Reconnected USB cable from Storm32 gimbal to Jetson via `/dev/ttyACM0`. This is the ONLY working communication method.
- **[CODE]** `hardware.py`: Switched serial port priority to `/dev/ttyACM0` (USB) as primary gimbal interface.
- **[DECISION]** USB serial via o323BGC binary protocol is the sole viable gimbal control method on this hardware.

## 2026-06-03 — PITCH OSCILLATION FIX & GIMBAL LIMITS CONFIRMED

- **[BUG]** Gimbal pitch motor oscillated continuously when PITCH_HOME was set to -20° or lower. Root cause: commanding angles beyond mechanical endstop (±25°) caused PID hunting.
- **[CODE]** `hardware.py`: Changed `PITCH_HOME` from `-20.0` to `0.0`. Expanded `PITCH_LIMIT` to `100.0` for user calibration via WASD keys.
- **[HW-FINDING]** Gimbal spec sheet confirms mechanical limits: Pitch ±25° (50° total), Roll ±25°, Yaw ±90°. Firmware v0.90 (o323bgc-release-v090), Hardware V130.
- **[HW-FINDING]** Mounting geometry problem: with ±25° pitch and camera pointing down at gimbal 0°, max forward tilt = 25° from vertical — insufficient for horizontal targeting. Payload bracket must be pre-angled ~65° toward forward.

## 2026-06-03 — SNIPER VIDEO GARBLING: ROOT CAUSE & FIX

- **[BUG]** Sniper camera (sensor-id=1, IMX219 on MIPI CSI Port 1) produced garbled video on every `run-ai.sh` restart. Only a full Jetson reboot restored clean video.
- **[ANALYSIS]** Investigated: nvargus-daemon restart (insufficient), kernel module reload via `modprobe -r nv_imx219` (works but had race condition), direct `gst-launch-1.0` test (confirmed clean frames after modprobe — proving teardown is the issue).
- **[ROOT CAUSE]** `CameraStream.stop()` in `vision.py` called `cap.release()` inside the capture thread AFTER the while loop exited, but `cap.read()` blocks indefinitely. The 2-second `thread.join()` timeout expired, `stop()` returned, process was killed — leaving the GStreamer pipeline orphaned and CSI sensor corrupted.
- **[CODE]** `vision.py`: Fixed `stop()` to call `cap.release()` BEFORE joining the thread, unblocking stuck `cap.read()`. Added exception handling for externally-released pipeline.
- **[CODE]** `run-ai.sh`: Added full camera subsystem reset in stop phase — `modprobe -r nv_imx219` / `modprobe nv_imx219` (software-equivalent reboot for camera subsystem).
- **[CODE]** `app.py`: Reduced camera FPS 60→30. Added 2-second sequential delay between Scout and Sniper camera start.

## 2026-06-03 — YAW MOTOR OVERHEATING & VMAX TUNING

- **[HW-FINDING]** Yaw motor runs significantly hotter than pitch/roll. Yaw uses larger 2805/100T motor vs 2206/100T for pitch/roll.
- **[ANALYSIS]** Likely caused by excessive Vmax (motor power) in Storm32 firmware PID. o323BGCTool Windows download links are broken (GitHub repo and wiki).
- **[CODE]** `tests/tune_storm32_vmax.py`: Created Jetson-based Python script to read/write Storm32 motor parameters via USB serial. Uses o323BGC CMD 0x03 (GET_PARAMETER) and CMD 0x04 (SET_PARAMETER) with proper 4-byte response parsing.
- **[PROBE]** Confirmed firmware v0.90 via CMD 0x01. Parameter map: Pitch Power (addr 3) = 95, Roll Power (addr 7), Yaw Power (addr 11). Full PID + Power addresses 0-11 validated.
- **[PROBE]** Corrected parameter map to 6-per-axis grouping: Pitch Vmax=addr3 (95), Roll Vmax=addr9 (105), Yaw Vmax=addr15 (88).
- **[HW]** Yaw Vmax lowered: 88 → 60 → 40. Motor heat significantly reduced at Vmax=40.
- **[CODE]** `app.py`: Auto-applies Yaw Vmax=40 on every startup via gimbal serial connection (EEPROM store not supported by firmware).
- **[FINDING]** CMD 0x15 is "restore FROM EEPROM" not "store TO EEPROM" — discovered when write was verified then overwritten.

## 2026-06-03 — SYSTEMD AUTO-START & RESTART SCRIPT

- **[CODE]** `sentry.service`: Updated systemd service to run `app.py` (was `main.py`). Added full camera subsystem reset (`modprobe -r/modprobe nv_imx219`), nvargus-daemon management, pinmux configuration, and log redirection to `sentry.log`.
- **[CODE]** `restart.sh`: Created script to remotely reboot Jetson. Supports `--wait` flag that polls SSH + dashboard until accessible (~90s).
- **[CODE]** `run-ai.sh`: Removed `systemctl disable sentry` — service now runs same `app.py`, no conflict. Stays enabled for auto-start on boot.
- **[OPS]** Installed and enabled sentry.service on Jetson via `systemctl enable sentry.service`. App will auto-start on every boot with clean video (fresh CSI state).

## 2026-06-03 — CRITICAL BUG FIXES (Dashboard Crash + Garbled Video)

- **[BUG FIX]** `hardware.py`: Added `global JETSON_AVAILABLE` to `RelayController.__init__`. Python treated the variable as local due to `except` block assignments, causing `UnboundLocalError` on line 135 — the app crashed before Flask ever started. This was the root cause of dashboard unreachability.
- **[BUG FIX]** `app.py`: Fixed typo `nvargus-daemo` → `nvargus-daemon` in `pgrep` check at startup. The misspelling meant the daemon check always failed and triggered unnecessary restarts.
- **[BUG FIX]** `vision.py`: Fixed invalid GStreamer pipeline syntax. `nvvidconv memory:NVMM ! video/x-raw(memory:NVMM), format=RGB` is not valid — `memory:NVMM` is a caps feature not an element property. Replaced with standard `nvvidconv ! video/x-raw, format=BGRx` which lets nvvidconv handle the NVMM→CPU transition correctly, avoiding the software fallback path that caused garbled horizontal color lines.
- **[BUG FIX]** `run-ai.sh`: Eliminated dual-process port conflict. Step 3 was starting `app.py` via `nohup` AND then restarting `sentry.service` which also runs `app.py` on port 8000. Two processes fought for the port and both died. Now uses `sentry.service` as the single server lifecycle manager.

## 2026-06-03 — GARBLED SNIPER VIDEO ROOT CAUSE (CSI PHY)

- **[DIAGNOSIS]** Confirmed via direct `gst-launch` tests that sensor-1 (Sniper) garbling is NOT caused by Python/GStreamer pipeline configuration. The garbled horizontal color lines persist even with standalone `gst-launch-1.0` after a `modprobe -r`/`modprobe` cycle.
- **[DIAGNOSIS]** Confirmed that sensor-1 produces clean video after a full Jetson reboot. Scout (sensor-0) always works regardless of reset method.
- **[ROOT CAUSE]** The MIPI CSI-2 PHY hardware on the Orin Nano retains lane synchronization state that `modprobe -r nv_imx219` cannot clear. Only a full power-cycle (reboot) resets the CSI PHY registers for CSI lane 1. This is a known Jetson platform limitation.
- **[CODE]** `run-ai.sh`: Replaced the broken `modprobe -r`/`modprobe` camera reset with a full Jetson reboot. After deploying code, the script reboots the Jetson and polls SSH + dashboard until both are reachable (~60-90s). `sentry.service` auto-starts on boot with clean CSI state.
- **[CODE]** `sentry.service`: Removed the harmful `modprobe -r`/`modprobe` cycle from ExecStartPre. On a clean boot, the kernel loads nv_imx219 with fresh CSI state — no modprobe cycling needed. On a `systemctl restart`, the modprobe cycle was actively causing the garbling. Replaced with a simple `systemctl restart nvargus-daemon`.

## 2026-06-03 — GIMBAL PITCH LIMITATION ANALYSIS

- **[ARCHITECTURE]** Identified that Storm32 gimbal pitch range (±45° mechanical, ±25° joystick) is insufficient for ceiling-mount at 8-10ft where ~45° outward tilt is needed to cover mosquito flight zones at ground level.
- **[ARCHITECTURE]** Analyzed 5 alternative mounting options: (1) 45° wedge bracket, (2) 90° perpendicular side mount, (3) drop-arm with swivel ball joint, (4) high wall mount, (5) 3D-printed angled payload cradle. Generated photorealistic reference images for each.
- **[ARCHITECTURE]** Recommended Option 1 (wedge bracket) as primary solution — minimal mechanical change, zero motor stress, full 360° coverage, easy fabrication. Fallback: Option 4 (wall mount) for corner deployments.
- **[DOCS]** Saved mounting options analysis to `docs/gimbal/mounting_options.md` with 5 photorealistic reference images in `docs/gimbal/mounting_options/`.

## 2026-06-03 — PERPENDICULAR PAYLOAD MOUNTING: ROLL MOTOR CLEARANCE

- **[ARCHITECTURE]** Focused analysis on the specific problem: rotating camera/LiDAR/nozzle 90° on the Storm32 payload cradle causes collision with the roll motor housing. Stock cradle provides only ~10-15mm clearance vs. ~25mm needed for sideways IMX219.
- **[ARCHITECTURE]** Analyzed 5 payload-level mechanical solutions: (1) Drop-down L-bracket adapter, (2) Side-mount offset plate, (3) Extended taller custom cradle, (4) 45° wedge adapter, (5) Pendulum extension arm. Generated photorealistic concept images for each.
- **[ARCHITECTURE]** Recommended Solution 1 (Drop-Down L-Bracket) as primary — zero gimbal modification, ~15g added weight, ~30mm clearance gained, easy 3D print, fully reversible. Fallback: Solution 4 (45° wedge) as simplest first step giving ~85° total range when combined with gimbal pitch.
- **[DOCS]** Saved perpendicular mounting analysis to `docs/gimbal/perpendicular_mounting.md` with 6 concept images in `docs/gimbal/perpendicular_mounting/`.

## 2026-06-04 — GIMBAL SERIAL PORT DETECTION FIX & PID INVESTIGATION

- **[BUG FIX]** WASD gimbal controls were non-functional. Root cause: Storm32 BGC is connected via USB (enumerates as `/dev/ttyACM0` or `/dev/ttyACM1` depending on boot order), but the port detection code tried `/dev/ttyTHS1` first — a built-in Jetson hardware UART with nothing connected. Since `ttyTHS1` exists and opens successfully, the code latched onto it and sent commands into the void.
- **[CODE]** `hardware.py` + `gimbal_controller.py`: Replaced blind port detection with probe-based detection. Now sends a GET_VERSION command (0xFA 0x00 0x01) to each candidate port and only accepts ports where the Storm32 responds with a valid 0xFB header. Also added `/dev/ttyACM1` to the port list. USB serial ports prioritized over hardware UART.
- **[DIAGNOSIS]** Storm32 firmware confirmed: OlliW o323BGC v0.90 on STM32F103RC (v1.30 hardware). Successfully communicated via binary protocol (GET_VERSION, GET_DATA, SET_ANGLES) and text commands ('v', 'g', 'd').
- **[DIAGNOSIS]** Gimbal was initially stuck in STARTUP_RELEVEL state (state 3) with all status flags zero (IMU not detected, motors off). After user balanced the perpendicular payload with a counterweight, gimbal reached NORMAL state (state 6).
- **[DIAGNOSIS]** Investigated PID oscillation caused by perpendicular payload mount. Read full PID parameter block via 'g' text command (381 bytes). Original PIDs: Pitch P=540/I=4000/D=350, Roll P=800/I=4800/D=2000, Yaw P=460/I=1400/D=1000. Tested two PID adjustments but oscillation was mechanical (balance), not PID. Original PID values backed up to `~/storm32_params_backup.bin` on Jetson and restored.
- **[DIAGNOSIS]** Systematic PID re-tuning from safe baseline (P=100, I=0, D=100). P swept to 500 on all 3 axes with no oscillation — confirmed payload is well-balanced. Adding I=500 and D=200 reintroduced jerkiness. Final stable values: P=400, I=0, D=100 for all axes.
- **[DIAGNOSIS]** Root cause of original oscillation: factory I gains (4000-4800) were causing integral windup under the new payload geometry. The I term accumulated positional error and caused aggressive overcorrection loops.

## 2026-06-04 — ARCHITECTURE: GEARED SERVO TURRET MIGRATION

- **[ARCHITECTURE]** Decision to migrate from Storm32 brushless gimbal to geared MG996R servo pan-tilt system. Brushless motors lacked mechanical holding torque — couldn't fight water hose spring tension, causing stall and violent oscillation. Servos provide 10-13 kg·cm torque with mechanical gear locking.
- **[BOM]** Bolsen 2-DOF aluminum pan-tilt bracket kit (rigid metal cage, ball bearings). Aideepen MG996R metal-gear servos (6-pack). DWEII 12V→5V 10A buck converter (isolated servo power, prevents Jetson brownout).
- **[ARCHITECTURE]** Electrical isolation: dedicated 10A buck converter for servo power, common ground tie to Jetson for PWM signal reference. Eliminates the USB/UART ground loop that caused previous short circuit.
- **[CODE]** Added `ServoTurretController` class in `hardware.py` — PCA9685 I2C servo driver (addr 0x40) on I2C Bus 1. Same API as `GimbalController` (`set_angles`, `nudge`, `center`, `get_status`, `cleanup`). Dashboard, AI pipeline, and tests require zero changes.
- **[CODE]** Added `create_turret_controller()` factory function — auto-detects PCA9685 (new) vs Storm32 (legacy) at startup. PCA9685 takes priority when detected.
- **[FLAG]** Yahboom carrier board GPIO PWM pins are dead (ECO-2026-008). PCA9685 I2C servo driver board required for PWM generation. Shares I2C Bus 1 with TF-Luna LiDAR (addr 0x10, no conflict).
- **[DOCS]** Architecture review saved to `docs/gimbal/geared_turret_architecture.md`.

## 2026-06-06 — DOCS: SERVO TURRET ASSEMBLY & WIRING GUIDES

- **[DOCS]** Created interactive 3D assembly guide (`docs/gimbal/turret_3d_assembly.html`) using Three.js with OrbitControls. 5-step walkthrough: component layout → pan servo mount → U-bracket + tilt servo → electronics wiring → payload mounting. Features explode view, animated camera transitions, and keyboard nav. Models match actual Bolsen black anodized bracket kit from user photos.
- **[DOCS]** Created draw.io wiring diagram (`docs/gimbal/turret_wiring.drawio`) showing complete cabling between Jetson Orin Nano IDC40P header, SunFounder PCA9685 I2C servo driver, DWEII 12V→5V 10A buck converter, and two MG996R servos. Color-coded wire routing with safety notes (ground tie jumper, power isolation, TF-Luna I2C coexistence).

## 2026-06-09 — SERVO TURRET: APP INTEGRATION + CONNECTIVITY TEST

- **[CODE]** Modified `app.py` to use `create_turret_controller()` factory instead of hardcoded `GimbalController()`. System now auto-detects PCA9685 (servo turret) vs Storm32 (legacy gimbal) at startup. Zero API changes — all gimbal endpoints (`/api/gimbal/set`, `/api/gimbal/nudge`, `/api/gimbal/center`) work with both controllers.
- **[CODE]** Created `tests/test_servo_turret.py` — hardware connectivity test for PCA9685 + MG996R servos. 7 tests: I2C bus scan (0x40), center command, yaw sweep ±30°, pitch sweep ±20°, combined move, LiDAR I2C coexistence, return-to-center. Follows ✅/❌ output format for dashboard integration.
- **[CODE]** Added `servo_turret` to `TEST_SUITES` registry in `app.py` — appears in dashboard test runner alongside other test suites.
- **[UI]** Updated dashboard to display controller type: header shows "Servo Turret" or "Storm32 Gimbal", WASD card title adapts dynamically, endstop limits reflect actual controller limits (servo: ±80° yaw / ±90° pitch vs storm32: ±80° yaw / ±20° pitch).
- **[UI]** Status API (`/api/status`) now includes `gimbal.controller` field ("servo" or "storm32") for runtime detection.
- **[DOCS]** Updated wiring diagram with detailed PCA9685 board layout (6-pin left header, screw terminal, 3-pin channel headers) and signal-only wiring to match as-built configuration.
- **[BUG FIX]** Adafruit Blinka maps `board.SCL`/`board.SDA` to I2C buses 8/9 on Yahboom carrier board instead of bus 1. Rewrote `ServoTurretController` to use raw PCA9685 register writes via `smbus2.SMBus(1)` — same proven I2C path as TF-Luna LiDAR.
- **[BUG FIX]** Yahboom carrier board has onboard INA3221 power monitor at I2C address `0x40` — same default address as PCA9685. Kernel driver blocks userspace access. Added `_unbind_ina3221()` to auto-unbind at startup.
- **[FLAG]** ECO-2026-009: Yahboom carrier board INA3221 at 0x40 conflicts with PCA9685 default address. Auto-unbind workaround added but a permanent fix would be to bridge the PCA9685 A0 jumper to change its address to 0x41.
- **[TEST]** Servo turret test results on Jetson: 9 passed, 1 failed (LiDAR at 0x10 blocked by Yahboom onboard chip — separate issue). Yaw sweep ±30°, pitch sweep ±20°, combined moves, and I2C coexistence all pass.

## 2026-06-09 — I2C BUS DISCOVERY & SERVO FIX

- **[BUG FIX]** **Root cause found:** PCA9685 was never communicating because pins 3/5 on Yahboom board map to I2C Gen8 controller which is **disabled** in the Yahboom DTB (`status = "disabled"` at `i2c@31e0000`). All previous I2C writes at Bus 7 (c250000.i2c) were going nowhere. Bus 1 device at 0x40 was the onboard INA3221, not the PCA9685.
- **[HARDWARE]** Chip identity diagnostic confirmed: Register 0xFE at Bus 1 0x40 returns `0x54` (TI Manufacturer ID) and 0xFF returns `0x32` (INA3221 Die ID). The PCA9685 was invisible on all 9 I2C buses.
- **[HARDWARE]** Decompiled hdr40 device tree overlay revealed: Pin 3 = `gen8_i2c_sda_pdd2`, Pin 5 = `gen8_i2c_scl_pdd1` → I2C Gen8 (disabled). Pin 27 = `gen2_i2c_sda_pdd0` → Bus 1 (enabled).
- **[HARDWARE]** **Wiring change:** PCA9685 SDA/SCL moved from Pin 3/5 to Pin 27/28. PCA9685 now appears on Bus 1 alongside onboard INA3221 (address collision at 0x40).
- **[BUG FIX]** **Dual-address pattern:** Write via 0x40 (both INA3221 + PCA9685 receive), verify via 0x71 (PCA9685 Sub Address 1 — only PCA9685 responds). Enables collision-free reads without hardware modifications.
- **[BUG FIX]** **EXTCLK fix:** Previous address-collision writes set the EXTCLK bit in PCA9685 MODE1 register (disabling the internal 25MHz oscillator, killing all PWM output). Software reset via General Call (`write_byte(0x00, 0x06)`) at startup clears this sticky bit.
- **[CODE]** `ServoTurretController`: `I2C_BUS = 1`, `PCA9685_READ = 0x71`, software reset in `_init_pca9685()`, MODE1 keeps SUB1+SUB2+SUB3 enabled (0x2E when awake, 0x1E when sleeping).
- **[CODE]** Factory `create_turret_controller()`: Probes PCA9685 via sub-address 0x71 after software reset — eliminates false positives from INA3221.
- **[CODE]** Removed Storm32 test suites from dashboard (serial, pwm_gimbal, sysfs_pwm) — hardware retired.
- **[TEST]** 9/9 hardware tests pass. Both yaw and pitch servos physically confirmed moving.
- **[FLAG]** DTB overlay attempts (`tegra234-p3767-0000+p3509-a02-hdr40.dtbo` and custom `i2c8-enable.dtbo`) both caused boot failures on Yahboom Super board. Reverted. Pin 27/28 solution requires no DTB changes.

## 2026-06-09 — SERVO SMOOTHNESS & VISUAL CALIBRATION SYSTEM

- **[CODE]** `hardware.py`: Implemented smooth servo interpolation via background daemon thread at 100Hz, replacing jerky discrete steps with configurable speed (default 120°/s).
- **[CODE]** `app.py`: Added `/api/servo/settings` GET/POST endpoints for runtime servo parameter tuning (speed, update rate, nudge step, endstop limits).
- **[UI]** `index.html`: Added ⚙️ Settings tab with sliders for Travel Speed, Update Rate, Nudge Step, Yaw/Pitch Limits, and 4 motion presets (Ultra Smooth, Balanced, Fast, Max Speed).
- **[CODE]** `calibration_engine.py` [NEW]: Visual calibration system — SW-001 §2.8. `CalibrationTable` for offset storage + JSON persistence, `HitDetector` for frame differencing water splash detection, `CalibrationWizard` 5-step guided state machine.
- **[CODE]** `app.py`: Added visual calibration wizard API (`/api/calibration/wizard/*`), offset management (`/api/calibration/offset`), free-form fire-and-detect (`/api/calibration/freefire`), annotated snapshot endpoints.
- **[CODE]** `app.py`: Click-to-aim pipeline (`api_gimbal_click`) now applies visual calibration offsets before ballistic/lead corrections.
- **[UI]** `index.html`: Replaced basic calibration tab with full wizard-based interface — progress dots, sniper feed click-to-aim, before/after image comparison, manual offset sliders, free-form fire-and-detect.

## 2026-06-10 — ONE-BUTTON AUTO-CALIBRATION (COMMERCIAL UX)

- **[DESIGN]** User requirement: "dead easy, one button, system calibrates itself" for commercial product.
- **[CODE]** `calibration_engine.py`: Replaced `CalibrationWizard` with `AutoCalibrator` — fully autonomous background thread calibration. `TargetSelector` uses Shi-Tomasi corner detection (`cv2.goodFeaturesToTrack`) on Scout camera with greedy farthest-point sampling for spatial spread.
- **[CODE]** `AutoCalibrator`: Adaptive offset (running average applied to next shot for progressive accuracy). 3-tier retry on miss: longer burst (0.8s) → lower threshold (15px) → skip point. Fallback grid pattern when feature detection fails.
- **[CODE]** `app.py`: Replaced wizard endpoints with 3 auto-cal endpoints: `POST /api/calibration/auto/start`, `GET /api/calibration/auto/status`, `POST /api/calibration/auto/stop`. Background thread + UI polling at 500ms.
- **[UI]** `index.html`: One-button "🎯 Auto-Calibrate" interface with animated progress bar, live stats (hits/misses/skips), rolling activity log, before/after comparison, and manual fine-tuning sliders.

## 2026-06-10 — WATER LINE PRIMING SYSTEM

- **[DESIGN]** Silicone tube from reservoir to nozzle fills with air when idle. First shot fires air, not water. Solution: auto-prime before every fire command.
- **[CODE]** `hardware.py`: Added `PrimingSystem` class. Aims nozzle straight down (90° pitch), pumps for configurable duration (default 3000ms), auto-detects water flow via frame differencing on sniper camera (>0.5% pixel change = water flowing).
- **[CODE]** `PrimingSystem`: Keep-alive background thread pulses pump every N minutes (default 5 min, 200ms pulse) to prevent air from creeping back into the line during idle periods.
- **[CODE]** `calibration_engine.py`: Added `_phase_prime()` to `AutoCalibrator` — primes water line before first calibration shot. `AutoCalibrator.start()` now accepts `primer=` parameter.
- **[CODE]** `app.py`: Auto-prime check in `/api/relay/fire` endpoint. New endpoints: `GET /api/prime/status`, `POST /api/prime/now`, `GET|POST /api/prime/settings`. `PrimingSystem` initialized at startup with keep-alive thread.
- **[UI]** `index.html`: Settings tab — "💧 Water Line Priming" card with sliders for prime duration (500-10000ms), keep-alive interval (1-30 min), keep-alive pulse (50-1000ms), auto-detect toggle, keep-alive toggle, and "Prime Now" button.
- **[HW]** Nozzle leak identified at silicone-tube-to-nozzle barb junction. Recommendation: replace barb with 1/4" NPT threaded connection + brass adjustable jet nozzle + PTFE tape for permanent seal.

## 2026-06-11 — FALSE HIT DETECTION FIX & MICRO-PULSE TUNING

- **[BUG]** Auto-calibration falsely detecting "hits" when no water was fired. Root cause: `MIN_CONTOUR_AREA=50` too low — natural scene noise (lighting, wind, sensor drift) triggers false positives.
- **[CODE]** `calibration_engine.py` HitDetector: Raised `DIFF_THRESHOLD` 30→40, `MIN_CONTOUR_AREA` 50→500px², `BLUR_KERNEL` 5→7. Added `MIN_CHANGE_PCT=0.3%` and `MAX_CHANGE_PCT=15%` gates — rejects frames with too little change (noise) or too much (lighting shift). Heavier morphological cleanup (7×7 kernel). Debug logging for rejected/confirmed hits.
- **[CODE]** `hardware.py`: Lowered `fire_pump()` minimum clamp from 0.05s→0.01s, default from 0.4s→0.025s. User reports 0.05s still delivers too much water for insect deterrence.
- **[UI]** `index.html`: Pulse slider min=0.01s, step=0.005s, default=0.025s (was min=0.05, step=0.05, default=0.6). Free-fire pulse default 0.4→0.025s.
- **[CODE]** `app.py`: Removed auto-priming from `/api/relay/fire` — Test Fire now fires immediately. Priming remains in auto-calibration `_phase_prime()` only.
- **[UI]** `index.html`: Added dedicated "💧 PRIME LINE" button in Fire Control card below Test Fire. Calls `/api/prime/now` with inline status feedback.
- **[HW]** User replaced nozzle assembly — upgraded from leaking barb-to-silicone junction to improved nozzle fitting (details TBD by user).

## 2026-06-11 — PUMP STABILIZATION (PRE-PRESSURIZATION FIX)

- **[BUG]** 10ms shots inconsistent: ~70% land within 5cm, ~10% land 50cm away. Root cause: diaphragm pump pulsation — 10ms catches random point in stroke cycle (peak vs valley pressure).
- **[CODE]** `hardware.py` `RelayController`: Added pre-pressurization sequence: (1) stabilize burst (50ms) positions diaphragm at end-of-stroke, (2) settle gap (80ms) lets spring return to known position, (3) actual fire pulse from consistent starting pressure. Configurable via `stabilize_ms`, `settle_ms`, `pre_pressurize` class attributes.
- **[CODE]** `app.py`: New endpoints `GET|POST /api/pump/stabilize` for stabilization settings (enable/disable, burst ms, settle ms).
- **[UI]** `index.html`: Settings tab — "🎯 Pump Stabilization" card with enable toggle, burst slider (0-200ms), settle slider (0-300ms), and Apply button.

## 2026-06-12 — MICRO-PULSE & SEPARATE PULSE CONFIGURATION

- **[CODE]** `hardware.py`: Lowered `fire_pump()` minimum clamp from 0.01s→0.001s (1ms). Enables ultra-fine water control for insect deterrence.
- **[CODE]** `app.py`: New endpoints `GET|POST /api/pulse/config` for separate calibration pulse, operational pulse, calibration retry pulse, and prime duration. Modifies `AutoCalibrator.FIRE_DURATION` and `AutoCalibrator.RETRY_DURATION` at runtime.
- **[UI]** `index.html`: Test Fire pulse slider now goes down to 1ms (step=1ms), shows ms for <100ms values. Added "🔥 Fire Pulse Configuration" card in Settings tab with separate sliders for: Operational Pulse (1-500ms), Calibration Pulse (10-2000ms), Calibration Retry Pulse (10-2000ms), and Prime Duration (500-10000ms). Settings sync with Test Fire slider on apply.

## 2026-06-12 — ⚠️ SOFTWARE STABILIZATION FAILED — HARDWARE MIGRATION REQUIRED

> **CRITICAL FINDING:** The software pre-pressurization approach (stabilize burst → settle → fire)
> does NOT solve the shot consistency problem. The root cause is fundamentally hardware, not software.
> No software timing trick can compensate for the physics of diaphragm pump pulsation + elastic tubing.

### Root Cause Analysis (Confirmed by Testing)

Three factors combine to make sub-10ms relay-gated diaphragm pump shots inherently unreliable:

1. **Sinusoidal Cam Strike:** Diaphragm pump uses a wobbling cam to push a flexible membrane. A 10ms relay closure randomly hits peak (max pressure) or intake (min pressure) of the cam cycle → ~2x pressure variance between shots.
2. **Silicone Tube Slingshot Effect:** 50cm silicone tube has significant elastic compliance. At peak cam stroke, the tube balloons and stores elastic potential energy. When relay cuts power, stored energy snaps back and fires an extra high-velocity "slingshot" pulse through the nozzle → explains why wild shots land exactly in-line but 50cm further.
3. **Mechanical Relay Jitter:** Standard mechanical relay has ±3-5ms bounce/float. At 10ms target pulse, this is 30-50% error in volume and pressure delivery.

### Required Hardware Migration: Constant-Pressure Accumulator + Solenoid Gate

```
[Reservoir] → [Diaphragm Pump] → [Check Valve] → [Accumulator Tank] → [12V Solenoid] → [Nozzle]
                (runs continuously)                  (absorbs pulsation)    (MOSFET-gated)
```

**Parts to source:**
- **Accumulator tank** (0.75-1L, pre-charged, 1/4" NPT) — ~$25. Absorbs all pump oscillation → flat pressure line.
- **12V direct-acting solenoid valve** (1/4" NPT, normally closed, stainless/brass) — ~$10-15. Must be direct-acting (not pilot-operated). Sub-ms response time.
- **IRLB8721 or TIP120 MOSFET/transistor** — replaces mechanical relay for solenoid switching. Microsecond precision, zero jitter/bounce.
- **Pressure switch** (optional, 30-50 PSI cutoff) — auto-stops pump when accumulator is full.

**Software changes needed post-migration:**
- `hardware.py`: Replace `RelayController` relay GPIO with MOSFET GPIO for solenoid control. Remove pre-pressurization code (no longer needed with constant-pressure system).
- `app.py`: Add pump control API (continuous run / auto with pressure switch).
- HW-001 spec: Update wiring diagram, GPIO assignments, BOM.

## 2026-06-12 — ECO-2026-004: PARTS ORDERED — ACCUMULATOR + SOLENOID UPGRADE

- **[HW]** HW-001 updated to v5.0 (ECO-2026-004). Complete fluid architecture redesign.
- **[PROCUREMENT]** Parts ordered from Amazon.ca (all arriving same day):
  - Swess 0.75L Accumulator Tank, 125 PSI — $49.99
  - GOODRIG 12V DC Solenoid Valve (NC, Direct-Acting, 1/4" FNPT) — $12.99
  - IRLB8721PBF N-Channel MOSFET ×5 (30V/62A, 3.3V logic) — $8.99
  - Kozelo 1/4" Barb × 1/4" MNPT Brass Adapter ×2 — $9.19
  - uxcell 1/4" Barb × 1/2" FNPT Brass Adapter ×2 — $17.59
  - **Total: $98.75 CAD**
- **[SPEC]** HW-001 §5.3: BCM 27 (Pin 13, Terminal 13) reassigned from "Reserved" to Solenoid MOSFET Gate.
- **[SPEC]** HW-001 §5.4: New MOSFET switching circuit schematic (IRLB8721 + 10kΩ pull-down + 1N4007 flyback).
- **[SPEC]** HW-001 §8: Complete rewrite — accumulator + solenoid topology with full plumbing diagram and routing.
- **[SPEC]** HW-001 §12.1: New BOM section for ECO-2026-004 parts with prices and thread specs.

## 2026-06-12 — SOLENOID MOUNTED ON SERVO TURRET (ZERO DEAD VOLUME)

- **[DECISION]** Solenoid valve MUST be mounted directly on servo turret payload, connected directly to nozzle with ZERO tubing between them. Rationale: Any flexible tubing after the solenoid creates "dead volume" — the tube balloons under pressure, absorbing the 10ms pulse energy and producing a dribble instead of a laser stream. Direct connection keeps 40 PSI right at the nozzle tip.
- **[DECISION]** MG996R servos (11 kg·cm stall torque) can easily handle ~275g turret payload (camera + solenoid + adapters + nozzle = 2.5% of capacity). Mount solenoid near pivot center to minimize rotational inertia.
- **[DECISION]** Fallback if servos struggle: replace silicone tubing (accumulator→turret) with rigid PTFE/Teflon tubing and move solenoid off-turret. Rigid tubing preserves pulse integrity but restricts turret movement.
- **[SPEC]** HW-001 §8.3: Updated fluid routing — solenoid on turret, direct to nozzle. Added §8.4 weight budget, §8.5 fallback plan.
- **[DIAGRAMS]** Updated all ECO-2026-004 diagrams (3 draw.io + 3 reference images) to show servo turret (not Storm32 gimbal) with solenoid + nozzle on payload plate.

## 2026-06-12 — ECO-2026-004: SOFTWARE IMPLEMENTATION — CHARGE-ON-DEMAND + SOLENOID CONTROL

- **[SW]** `hardware.py`: GPIO reassignment — `RELAY_GIMBAL_PIN` (BCM 27) renamed to `SOLENOID_PIN`. Now drives IRLB8721 MOSFET gate for solenoid valve instead of Relay CH2. Gimbal relay code replaced with solenoid control methods (`set_solenoid()`, `fire_solenoid()`).
- **[SW]** `hardware.py`: NEW `AccumulatorManager` class — charge-on-demand strategy for R385 pump:
  - `arm()`: Pump ON 3s (solenoid closed) → pump OFF → system holds ~30 PSI passively
  - `fire()`: Pulse solenoid MOSFET 10ms → pump stays OFF → accumulator provides pressure
  - `_topup()`: After 10 shots or 60s, brief 1s pump burst to recharge
  - `disarm()`: Everything OFF, solenoid closed, pump cold
  - Deadhead protection: MAX_PUMP_RUN_SEC=5s absolute limit
  - Background timer thread for periodic top-ups
- **[SW]** `hardware.py`: Pre-pressurization (`stabilize_ms`/`settle_ms`) disabled by default — accumulator eliminates pulsation.
- **[SW]** `app.py`: NEW accumulator API endpoints:
  - `POST /api/accumulator/arm` — charge and arm
  - `POST /api/accumulator/disarm` — safe shutdown
  - `POST /api/accumulator/fire` — precision solenoid pulse
  - `GET /api/accumulator/status` — state, shot count, config
  - `GET/POST /api/accumulator/config` — runtime tuning
- **[TEST]** `tests/test_pressure_drawdown.py`: NEW calibration script — fires N shots after M seconds charge, user marks first weak shot, calculates optimal top-up interval. Sweep mode tests 7 charge durations.
- **[DIAGRAMS]** `eco004_unified_wiring.drawio`: NEW unified wiring schematic showing both GPIO paths (BCM 17→Relay→Pump, BCM 27→MOSFET→Solenoid) with software state machine logic.
- **[DIAGRAMS]** `eco004_wiring_migration.drawio`: NEW before/after 2-page wiring migration guide. Page 1: current wiring (BCM 27→Relay CH2, unused). Page 2: new wiring (BCM 27→MOSFET gate) with 7-step instructions for physical rewire.

## 2026-06-16 — AIDLC WORKFLOW INTEGRATION & CUSTOM EXTENSIONS

- **[ARCHITECTURE]** Integrated AWS AI-DLC (AI-Driven Life Cycle) v0.1.8 adaptive workflow steering rules from [awslabs/aidlc-workflows](https://github.com/awslabs/aidlc-workflows). Three-phase methodology (Inception → Construction → Operations) now available via `Using AI-DLC, ...` invocation.
- **[ARCHITECTURE]** Downloaded AIDLC core workflow rules to `.aidlc/aidlc-rules/` (gitignored — re-downloadable from GitHub releases). Core rules include workspace detection, reverse engineering, requirements analysis, user stories, workflow planning, application design, and units generation.
- **[ARCHITECTURE]** Created `.agent/rules/ai-dlc.md` — Antigravity IDE steering file that activates AIDLC when invoked and resolves rule detail paths.
- **[PROCESS]** Created custom TDD (Test-Driven Development) extension in `.aidlc-rule-details/extensions/testing/tdd/`:
  - `tdd-enforcement.md`: 6 blocking rules (TDD-01 through TDD-06) enforcing test-first mandate, layer-appropriate testing per TEST-001, safety test gates for SAFE-001 code, regression prevention, mock boundary enforcement, and test results logging.
  - `tdd-enforcement.opt-in.md`: Opt-in prompt with Full/Partial/No enforcement options.
- **[PROCESS]** Created custom SDD (Spec-Driven Development) extension in `.aidlc-rule-details/extensions/spec-driven/baseline/`:
  - `spec-driven-development.md`: 6 blocking rules (SDD-01 through SDD-06) enforcing spec-before-code mandate per agents.md, history logging, spec traceability headers, spec review gates, no-dummy-data policy, and safety spec compliance.
  - `spec-driven-development.opt-in.md`: Opt-in prompt with Full/Partial/No enforcement options.
- **[DECISION]** Custom extensions placed in `.aidlc-rule-details/` (version-controlled) rather than inside `.aidlc/` (gitignored). This ensures project-specific TDD and SDD rules survive fresh clones while core AIDLC rules are re-downloaded from the release.
- **[CONFIG]** Updated `.gitignore` to exclude `.aidlc/` (downloaded content) while keeping `.aidlc-rule-details/` tracked.

## 2026-06-16 — SOLENOID TESTING & CALIBRATION GUI

- **[GUI]** Added new `💉 Solenoid` tab to the web dashboard (`templates/index.html`) with 4 panels for solenoid bring-up and calibration:
  - **Step 1 — MOSFET Smoke Test:** Toggles BCM 27 HIGH/LOW without pump or accumulator. Verifies solenoid clicks. Adjustable hold time slider.
  - **Step 2 — Arm → Fire → Disarm:** Full accumulator cycle with adjustable solenoid pulse slider (1–500ms). ARM charges accumulator (~3s), FIRE pulses solenoid, DISARM shuts everything down. Shot-by-shot log output.
  - **Live Accumulator Status:** Real-time polling (1.5s) showing state (idle/charging/armed/firing), shot count, top-up countdown, timing telemetry, and solenoid/pump override toggles.
  - **Step 3 — Pressure Drawdown Calibration:** GUI version of `test_pressure_drawdown.py`. Configurable charge time, shot count, pulse, and delay sliders. Fires N shots, displays clickable shot grid — user clicks first weak shot, system computes recommended top-up settings, one-click apply.
  - **Accumulator Configuration:** Runtime tuning for initial charge, top-up charge, top-up interval, and default pulse. Load current and apply changes instantly.
- **[CODE]** `app.py`: Added 3 new API endpoints:
  - `POST /api/solenoid/test` — Quick MOSFET click test (toggle solenoid without pump/accumulator)
  - `POST /api/solenoid/drawdown` — GUI-driven pressure drawdown test (charge → N shots → disarm → results)
  - `POST /api/solenoid/drawdown/apply` — Apply recommended drawdown calibration settings

## 2026-06-22 — ECO-004: SOLENOID DRIVER = D4184 MOSFET MODULE (2A LOAD)
- **[HW]** Confirmed GOODRIG solenoid spec: 12V DC, **2A nominal**, 1/4" NPT, brass, direct-acting normally-closed. This 2A load drives the final driver choice.
- **[DECISION]** Selected a pre-built **D4184 logic-level MOSFET trigger module** (DC 5–36V, ~15A/400W) over: (a) ULN2803 Darlington array — rejected, 500mA/channel and package can't dissipate ~2.6W at 2A even with ganged channels; (b) bare discrete MOSFET — rejected, the hand-wired gate kept failing (no flyback + ESD + likely counterfeit parts); (c) Relay CH2 — works but has the 1–5ms variable mechanical delay the design wants to avoid. The module gives µs, repeatable switching with no fragile bare gate, and at 2A dissipates ~0.02W (runs cold).
- **[HW]** Must be **logic-level (3.3V trigger)** — D4184-based boards trigger at ~2V Vgs(th); avoid IRF520 boards (need 4–5V, won't fully turn on at 3.3V). Pair with a **1N5408 (3A)** flyback across the coil (not the 1N4007) for the 2A inductive load.
- **[SW]** No software change: solenoid stays on **BCM 27 / T13 via libgpiod** (clean 3.3V cleanly triggers the module; the weak ~1.6V Jetson.GPIO would not). The 4.7kΩ pull-up is dropped.
- **[DIAGRAM]** Created `diagrams/eco004_mosfet_module_option.drawio` — "wires to move" guide: REMOVE MOSFET + 4.7kΩ/1kΩ + T17 wire; MOVE green (T13) → module SIG; module control GND → Jetson GND (shared, required); +12V → DC+, GND → DC−; OUT+ → solenoid (+), OUT− → solenoid (−); 1N5408 flyback across coil (band → OUT+ side).
- **[PROCUREMENT]** `parts.csv`: added "Solenoid Driver — Kioiner dual-MOS trigger module (D4184-class, $10)" and "1N5408 flyback diode 3A ($8)"; grand total 1686 → 1704 CAD.
- **[DIAGRAM]** `eco004_mosfet_module_option.drawio`: redrew the module as a realistic blue PCB (3-pin SIG/VCC/GND header, DC-IN and OUT green screw terminals with +/− screws, two D4184 MOSFETs with metal tabs, indicator LED, cap) so each wire lands on the actual pad/terminal; added note that silkscreen labels may vary (PWM/TRIG = SIG).
- **[PROCUREMENT]** Driver = dual-MOS "trigger switch drive module" (D4184-class, DC 5–36V, 15A/400W, supports PWM 0–20kHz, explicitly rated for solenoid valves). Two equivalent boards evaluated on Amazon.ca: Seloky (spec confirms **digital trigger 3.3–20V**, ~$15–19) and **Kioiner (~$10, ordered for faster delivery)** — same D4184-class dual-MOS board; trigger voltage not listed but these reliably trigger from 3.3V GPIO. Diagram generalized from "D4184" to "dual-MOSFET module"; trigger pin may be labeled PWM/TRIG = SIG. Module does NOT include a load flyback → external 1N5408 still required. 12V power-in from existing bus (not the 5V servo rail). Fallback if 3.3V trigger is marginal: 10kΩ pull-up SIG→+3.3V or level-shift from 5V rail.

## 2026-06-22 — ECO-004: ABANDON MOSFET, REVERT SOLENOID TO RELAY CH2
- **[HW/DEBUG]** Extended MOSFET bring-up troubleshooting (Rev C/D). With T17 a solid +3.3V, the gate would only reach ~2.1V when the MOSFET was connected (3.3V open-circuit, sags to ~2.1V under MOSFET load), idle ~1.3V. Adding a 1kΩ in parallel with the 4.7kΩ pull-up did NOT raise the gate (still ~2.1V) — ruling out a simple resistive divider/leak.
- **[HW/DEBUG]** Diagnosis: the gate is being CLAMPED at ~2.1V (not divided), the classic signature of a damaged/punctured MOSFET gate oxide behaving like a leaky ~2V zener. Confirmed by R(G→GND) ≈ 8.8kΩ and ~1.45mA continuous gate current (a healthy gate draws ~0). All three "new" MOSFETs showed the same ~2V clamp + warming.
- **[HW/DEBUG]** Probable root cause of repeated gate failure: the **1N4007 flyback diode was never installed**. Switching the inductive solenoid with no flyback generates kickback spikes that couple through Cgd and punch the gate oxide — degrading each MOSFET to a ~2V clamp after a few clicks. The earlier melted-wire short likely damaged the first unit.
- **[DECISION]** Abandon the direct-MOSFET gate-drive approach for the solenoid and revert to switching it with **Monk Makes Relay CH2** (driven by BCM 27 / T13 — same pin as Rev B). Avoids gate-drive marginality on the Yahboom PY.00 pad and removes the MOSFET as a failure point. Trade-off accepted: relay adds small, consistent switching delay vs. the MOSFET's intended microsecond pulses.
- **[DIAGRAM]** Created `diagrams/eco004_relay_option.drawio` — migration "wires to move" guide: REMOVE MOSFET + 4.7kΩ/1kΩ + T17 wire; MOVE green (T13) → Relay CH2 IN; +12V → CH2 COM; CH2 NO → solenoid (+); MOVE blue solenoid (−) → GND; keep 1N4007 flyback across the coil. Relay Vcc/GND shared with CH1. Notes that BCM 27 software is unchanged (HIGH closes CH2 → solenoid opens).

## 2026-06-22 — ECO-004 REV D: SOLENOID GATE DRIVEN VIA LIBGPIOD (FIX INTERMITTENT CLICK)
- **[HW/DEBUG]** Root-caused intermittent solenoid: gate stuck ~1.6V at idle even though Jetson.GPIO reported output-LOW. Bench test driving BCM 27 directly with `gpioset gpiochip0 122=1` produced a clean **3.33V and the solenoid clicked**. Conclusion: Jetson.GPIO does not properly drive PY.00 (SPI-function pad) on the Yahboom carrier (lib warns it is unverified); libgpiod does.
- **[CODE]** `hardware.py`: New `_LibGpiodSolenoid` driver — requests `gpiochip0` line 122 (`PY.00`) once and holds it (persistent push-pull, precise pulses). `RelayController` now drives the solenoid via libgpiod; pump stays on Jetson.GPIO. PADCTL `configure_push_pull()` still applied first for pinmux.
- **[DEP]** Installed `python3-libgpiod` (v1.6.3) via apt on Jetson; documented in `requirements.txt` (apt, not pip — pip `gpiod` is incompatible v2 API).
- **[GUI]** `templates/index.html`: New "🔌 Gate Voltage Test (libgpiod)" card in Solenoid tab — holds gate HIGH 1–30s for multimeter measurement (expect ~3.3V at gate junction).
- **[API]** `app.py`: `POST /api/solenoid/gate_hold` — holds gate HIGH for N seconds then LOW; reports `backend` (libgpiod/stub). Verified live: `{"backend":"libgpiod","held_sec":3}` + OPEN/CLOSED in log.
- **[SPEC]** HW-001 §5.4 → Rev D (libgpiod gate drive note).

## 2026-06-21 — DOCS: REMOVE STALE REV B / RELAY CH2 SOLENOID COMMENTS
- **[CODE]** `hardware.py`: RelayController docstring — solenoid via MOSFET only; CH2 unused.
- **[TEST]** `test_gpio_pinmux.py`: Rev C probe guide (gate junction, not T13/CH2).
- **[SPEC]** `spec.md`: BCM 27 documented as solenoid MOSFET gate (was "unused").
- **[GUI]** Solenoid tab Click Test hint updated for 4.7kΩ pull-up at gate junction.

## 2026-06-21 — ECO-004 DIAGRAM: SIMPLIFIED TO SINGLE AS-BUILT VIEW
- **[DIAGRAM]** `eco004_wiring_migration.drawio`: Removed BEFORE/AFTER and all "remove/change" migration content. Now a single current as-built schematic: Jetson terminals (T11/T13/T17/+12V/GND), Relay CH1→pump, GATE JUNCTION (green + 4.7kΩ leg + MOSFET G), 4.7kΩ→T17 pull-up, IRLB8721, GOODRIG solenoid, 1N4007 flyback, common GND bus, and a "How it works" legend with bench-probe note.

## 2026-06-19 — ECO-004 DIAGRAM: GATE JUNCTION CLARITY (REV C)
- **[DIAGRAM]** `eco004_wiring_migration.drawio`: Added GATE JUNCTION callout (parallel 4.7kΩ, not in series), multimeter probe guide, real pinout photo placement, rewired schematic to ★ node.

## 2026-06-19 — ECO-004 REV C: 4.7kΩ PULL-UP DIRECT MOSFET GATE (NO RELAY CH2)
- **[SPEC]** HW-001 §5.3–§5.4 Rev C: GREEN T13 → MOSFET Gate; 4.7kΩ (472) T17 (+3.3V) → Gate. Relay CH2 unused for solenoid. Replaces Rev B relay gate-drive approach.
- **[DIAGRAM]** `eco004_wiring_migration.drawio`: AFTER panel updated for Rev C pull-up wiring; step-by-step instructions revised.
- **[CODE]** `hardware.py`: Comments aligned to Rev C gate + pull-up architecture.

## 2026-06-19 — ECO-004 REV B: RELAY CH2 GATE DRIVE FOR SOLENOID MOSFET
- **[SPEC]** HW-001 §5.3–§5.4 Rev B: BCM 27 (GREEN) → Monk Makes Relay IN B (control only). Terminal 17 (+3.3V) → CH2 screw B1 → B2 → IRLB8721 Gate. Removes direct GPIO-to-gate wiring — Yahboom PY.00 sources only ~1.5–1.6V HIGH, insufficient for MOSFET turn-on.
- **[DIAGRAM]** `eco004_wiring_migration.drawio`: Before/after updated — BEFORE shows failed direct gate wiring; AFTER shows 3 wire moves (GREEN→IN B, T17→B1, B2→Gate) plus removal of 104 pull-ups and old CH2 12V feed.
- **[DIAGRAM]** `eco004_mosfet_circuit.drawio`: Schematic redrawn for Relay CH2 + Terminal 17 gate drive path.

## 2026-06-19 — GPIO PADCTL FIX (1.5V → 3.3V ON BCM 17/27)
- **[BUG FIX]** `hardware.py`: `configure_push_pull()` now writes full PADCTL value `0x05` (GPIO output) to PR.04 and PY.00 instead of only clearing bit 4. Old approach left tristate + internal pull-down active — multimeter read ~1.5V on Terminal 11 during ARM and ~0V on Terminal 13; MOSFET never fully conducted.
- **[CODE]** Re-apply `configure_push_pull()` before every pump/solenoid `GPIO.output()` (Jetson.GPIO can reset pad registers).
- **[CODE]** `sentry.service`: ExecStartPre updated to write `0x05` to both pad registers.
- **[TEST]** Added `tests/test_gpio_pinmux.py` — root diagnostic for PADCTL register values and 3s GPIO HIGH hold.

## 2026-06-19 — ECO-004 MOSFET PINOUT CLARITY
- **[DOCS]** `eco004_wiring_migration.drawio`, `eco004_mosfet_circuit.drawio`, HW-001 §5.4: Clarified IRLB8721 TO-220AB pinout — metal tab and middle pin are both Drain (same node); wire solenoid (−) to middle pin only. Added explicit 10kΩ pull-down wiring (Gate ↔ GND, parallel with green wire).

## 2026-06-25 — ECO-004 REV E: SOLENOID TRIGGER RELOCATED PY.00 → PR.05 (FIX WEAK SIG)
- **[HW/DEBUG]** Dual-MOSFET module bring-up: installed the module, but the **12V adapter died** during first wire-up — root-caused to **reverse polarity on DC IN** (the board's reverse-protection element looks like a dead short when fed backwards). Fixed polarity; the original module was suspected damaged so it was **replaced with a fresh unit**.
- **[HW/DEBUG]** With the fresh module: pressing "Hold Gate HIGH" lights the module LED, DC IN reads 12V, but **OUT never switches** — OUT+→GND = 12V, OUT−→GND = 12V, OUT+→OUT− = 0V (low-side MOSFET not pulling OUT− down). No click on Click Test or Hold Gate HIGH.
- **[HW/DEBUG]** Probed the trigger: **SIG→GND = 1.9V** and **SIG→DC IN− = 1.9V** when driven HIGH; touching SIG with the meter drops the LED. Common ground confirmed good (Jetson GND ↔ module DC IN− ≈ 0Ω). Root cause: **BCM 27 / PY.00 is a weak pad** — even via libgpiod it only sources ~1.9V into the module's internal SIG pull-down, **below the module's ~3.3V trigger threshold**, so the MOSFETs never turn on. (The earlier "libgpiod = 3.33V" reading was the 4.7kΩ pull-up on the bare-MOSFET gate doing the work; the module has no such pull-up and instead loads the pad.)
- **[DECISION]** Rejected a pull-up fix on PY.00 — against the module's internal pull-down and PY.00's weak sink, the OFF state risks staying above threshold (solenoid stuck open). Instead **relocate the trigger to a strong push-pull pin**.
- **[HW]** Enumerated Jetson GPIO (`gpioinfo`): pump = line 112 `PR.04` (proven strong), old solenoid = line 122 `PY.00` (weak). Chose **`PR.05` = line 113 = BCM 16 = Pin 36 / Terminal 36** — the sister pad in the same GPIO port as the working pump pad PR.04, currently unused. Bench-drove it with `gpioset --drive=push-pull --mode=time gpiochip0 113=1` for multimeter verification (expect clean ~3.3V at T36).
- **[CODE]** `hardware.py`: `SOLENOID_LINE_NAME` `PY.00`→`PR.05`, `SOLENOID_LINE_OFFSET` `122`→`113`, `SOLENOID_PIN` `27`→`16`. Removed `PY.00` from `_PADCTL_REGS` (PR.05 boots in GPIO mode → no PADCTL fix needed; PR.04 entry kept for the pump). Updated `_LibGpiodSolenoid`/`RelayController` docstrings.
- **[SPEC]** `spec.md` Pinout: solenoid trigger now BCM 16 / PR.05 / Terminal 36 → dual-MOSFET module SIG (was BCM 27 + IRLB8721 + 4.7kΩ pull-up).
- **[DIAGRAM]** `eco004_mosfet_module_option.drawio`: SIG source T13/BCM 27 → **T36/BCM 16 (PR.05)**; title tagged Rev E; step 3 explains the weak-pad move; Software note updated (libgpiod line 122→113, no PADCTL fix).
- **[LESSON]** PY.00 (an SPI-function pad on the Yahboom carrier) is unreliable for driving real logic loads in either direction; prefer the `PR.x` GPIO port (same family as the working pump pad) for new outputs. Never feed these MOSFET modules reversed DC IN — the reverse-protection looks like a short and can take out the supply.
- **[BUG FIX]** After deploying Rev E, T36 read 0V and the module LED stayed dark: PR.05 was relocated but **omitted from `_PADCTL_REGS`**, so its pad booted tristated and output 0V even though libgpiod held the line as OUTPUT. Pulled authoritative pad register addresses from Jetson.GPIO `reg_addr` (PR.04=0x2430098→off 0x98, **PR.05=0x2430090→off 0x90**, PY.00=0x243d030). Added `("PR.05", 0x90)` to `_PADCTL_REGS` so `configure_push_pull()` writes `0x05`. Verified live after restart: both PR.04 and PR.05 pad registers read `0x5`, line 113 held by `sentry-solenoid`.
- **[HW/DEBUG]** Isolation tests after the pad was confirmed good: (A) green wire off the module, **T36→GND = 3.3V** open-circuit → Jetson drive is perfect; (B) jumper module **SIG → DC IN+ (12V, in-spec trigger 3.3–20V) → solenoid clicked** → module + solenoid + flyback + power all good. So the only fault was SIG sagging to ~1.9V when connected — i.e. lost drive between T36 and SIG, not the pad or the module.
- **[RESOLVED ✅]** Root cause of the persistent ~1.9V sag was an **intermittent/loose physical connection between T36 and the module SIG pin** (not the GPIO pad). After re-seating/securing the T36↔SIG wire, **Click Test works reliably** (solenoid clicks open + closed). SIG now reaches ~2.8V on Hold Gate HIGH and sits ~1.5V steady at idle (below the module's switch threshold → valve stays closed). **No pull-up resistor was needed.** Software unchanged from the Rev E + PADCTL fix above. Next: live water test.
- **[LESSON]** When a logic level "sags under load" but the pad measures full voltage open-circuit, suspect the wire/terminal connection before adding pull-ups or swapping parts — an intermittent IDC40P screw/crimp mimics a weak driver.

## 2026-06-25 — ECO-004: CHARGE-PER-SHOT FIRING MODE (CONSISTENT SHOT DISTANCE)
- **[DESIGN]** Observed shots fading across successive fires until re-arm. Root cause is normal accumulator **drawdown**: the old config fired up to `TOPUP_INTERVAL_SHOTS=10` shots from one ~30 PSI charge, so pressure (and distance) dropped shot-to-shot. Key physics: distance ∝ exit velocity ∝ √(pressure); the solenoid pulse width sets volume, NOT velocity, so a longer pulse cannot restore distance — only consistent pressure can.
- **[DECISION]** No electronic pressure sensor added (avoid extra hardware). Instead use the pump's natural dead-head **pressure ceiling** as a free, repeatable reference and fire from it every time.
- **[SPEC]** SW-001 §2.7 (new): "Accumulator Firing Strategy" — documents charge-per-shot vs burst/N-shot modes, the √pressure physics, and the runtime tunables.
- **[CODE]** `hardware.py AccumulatorManager`: added `CHARGE_PER_SHOT` (default True). `_topup_if_needed()` now recharges after **every** shot when enabled (else every N shots). `update_config()`/`get_status()` expose `charge_per_shot`.
- **[GUI/API]** `templates/index.html`: Accumulator Configuration card gains a "Charge-per-shot" toggle (wired through the existing `POST /api/accumulator/config`).
- **[CALIBRATION]** To set the ceiling charge time: increase `initial_charge_sec`/`topup_charge_sec` until firing longer no longer increases shot distance (that's the plateau). Optional temporary $5 mechanical gauge can confirm the plateau; not a permanent sensor.
- **[PROCUREMENT]** `parts.csv`: added closed-loop pressure measurement parts from Amazon order 701-8218549-9648204 (ordered Jun 25 2026): AUTEX 0-100 PSI 5V pressure transducer with 1/8"-27 NPT harness ($35.99), AHFMANG 2-pack 1/8" NPT F/F/F brass tee ($12.99), and ADS1115 16-bit I2C ADC module ($10.99). Grand total updated `1916` → `1976` CAD. These are for replacing timed-only accumulator charging with measured pressure setpoints.

## 2026-07-02 — [DIAGRAM] ADS1115 PRESSURE TRANSDUCER WIRING
- **[DIAGRAM]** Created `diagrams/eco004_ads1115_pressure.drawio` — wiring for the ECO-004 pressure loop (AUTEX transducer → ADS1115 → Jetson I2C).
- **[DESIGN]** ADS1115 joins the **existing I2C bus** (SDA=T3/Pin3, SCL=T5/Pin5) already shared with the TF-Luna LiDAR. ADS1115 addr `0x48` (ADDR→GND) vs LiDAR `0x10` → no bus conflict.
- **[SAFETY]** ADS1115 **VDD = 3.3V** (Jetson Pin 1), NOT 5V. The module's onboard SDA/SCL pull-ups tie to VDD; powering at 5V would over-voltage the Jetson's 3.3V I2C lines. Documented as the diagram's primary warning.
- **[DESIGN]** Transducer needs 5V excitation (T4) but outputs 0.5–4.5V, which exceeds the 3.3V ADC rail. Added a **voltage divider** R1=10kΩ / R2=20kΩ (ratio 2/3) on SIG → A0: 0.5V→0.33V, 4.5V→3.0V (stays under 3.3V VDD). Firmware undoes the divider: Vsig = Vtap×30/20; PSI = ((Vsig−0.5)/4.0)×100. PGA set to ±4.096V FSR so the tap never clips.
- **[NOTE]** No code/spec change yet — this is the hardware wiring reference to enable the future measured-pressure setpoint feature over the current timed charge-per-shot logic.

## 2026-07-02 — [FEATURE] ADS1115 PRESSURE SENSING (SOFTWARE)
- **[SPEC]** Spec-first per AGENTS.md: added `HW-001 §7.1` (ADS1115 @ 0x48 + AUTEX transducer wiring, 3.3V-VDD I2C safety, 10k/20k divider, PGA ±4.096V, wiring table, PSI transfer function) and `SW-001 §2.9` (PressureSensor behavior). Renumbered from §2.8 → §2.9 to avoid clashing with the existing Visual Calibration §2.8.
- **[CODE]** `hardware.py`: new `PressureSensor` class + constants. Single-shot ADS1115 A0 reads over the **shared LiDAR I2C bus** (`PRESSURE_I2C_BUS = LIDAR_I2C_BUS`, addr `0x48`, config `0xC383`). Converts count → Vtap (×4.096/32768) → Vsig (×30/20, undo divider) → PSI (`((Vsig−0.5)/4.0)×100`, clamped 0–100). Background ~5Hz poll; `read_psi()` / `get_status()`.
- **[POLICY]** No mock data: when smbus2 or the ADS1115 is absent, the sensor reports `connected:False`, `psi:None` — it never fabricates pressure (unlike the LiDAR stub's random values). Complies with the "no fake data in dev/prod" rule.
- **[API]** `app.py`: instantiate `PressureSensor`, add `GET /api/pressure`, include `pressure` in `GET /api/status`, and clean up on shutdown.
- **[GUI]** `templates/index.html`: "Pressure" readout in the Live Accumulator Status card, fed from `/api/status`; shows `no sensor` when disconnected.
- **[CALIBRATION]** Divider/transducer constants (`PRESSURE_DIVIDER_R1/R2`, `PRESSURE_V_AT_0PSI`, `PRESSURE_V_AT_FULL`, `PRESSURE_FULL_PSI`) are top-level in `hardware.py` — tune after bench-checking the transducer against a mechanical gauge before trusting PSI values.
- **[NEXT]** Measured-pressure setpoint charging (fire only at/above a target PSI) is not wired into `AccumulatorManager` yet — this commit adds the sensing layer; the control loop is a follow-up.

## 2026-07-02 — [FIX] ADS1115 BUS CORRECTION (Pin 3/5 disabled → Bus 1 Pin 27/28)
- **[BUG]** Initial ADS1115 wiring/code put the ADC on the LiDAR's "Bus 7" (header Pin 3/5). Re-checking against the 2026-06-09 DTB investigation (ECO-2026-009): **Pin 3/5 map to I2C Gen8 (`c250000.i2c`), which is DISABLED in the Yahboom device tree** — that controller is electrically dead (it's why the TF-Luna on Pin 3/5 never enumerated and the servos were relocated). The ADS1115 would never respond there.
- **[FIX]** Moved the ADS1115 to **I2C Bus 1 (`c240000.i2c`, Pin 27/28)** — the only enabled header bus. `hardware.py`: `PRESSURE_I2C_BUS = 1` (was `LIDAR_I2C_BUS`=7). Spec HW-001 §7.1 + SW-001 §2.9 and `diagrams/eco004_ads1115_pressure.drawio` updated to Pin 27/28.
- **[VERIFY — no servo conflict]** Bus 1 already hosts the PCA9685 servo driver and the Yahboom onboard INA3221, both at `0x40`. The ADS1115 is at `0x48` → **unique address, no conflict** (I2C is multi-drop). Confirm on the Jetson with `i2cdetect -y 1` (expect `40` and, once wired, `48`).
- **[TERMINALS]** Power/ground pins are shared rails and safe to tap: Pin 1 (3.3V, ADS1115 VDD; Pin 17 also free now that the discrete-MOSFET pull-up is gone), Pin 4 (5V, transducer excitation ~10mA), Pin 6/Pin 9 (GND, common). Keep ADS1115 VDD at 3.3V so its onboard SDA/SCL pull-ups match the bus level.
- **[NOTE]** The stale `diagrams/turret_wiring.drawio` still shows the PCA9685 on Pin 3/5 (pre-2026-06-09). Code is authoritative: servos are on Bus 1 / Pin 27/28.

## 2026-07-02 — [GUI] PRESSURE TRANSDUCER TEST CARD
- **[GUI]** `templates/index.html`: added a "🩺 Pressure Transducer Test (ADS1115)" card in the Solenoid & Accumulator tab. Live telemetry (Sensor connected / PSI / transducer volts) with Start/Stop live polling (~2Hz) + a one-shot "Read Once". Uses the existing `GET /api/pressure` (SW-001 §2.9) — no backend change.
- **[UX]** When the ADC is absent it shows `none ❌` and the log guides the user to check Pin 27/28 + `i2cdetect -y 1` (expect 0x48). Live poll is stopped on tab switch (`ptStopLive()` in `tab()`).

## 2026-07-02 — [DIAGRAM] ADS1115 divider redrawn with Wago 221 levers
- **[DIAGRAM]** `diagrams/eco004_ads1115_pressure.drawio`: rebuilt the voltage-divider region as an explicit vertical schematic using **three Wago 221 lever connectors** (the user wires with Wago levers): Wago#1 221-412 (SIG↔R1), Wago#2 221-413 (TAP: R1·R2·A0), Wago#3 221-412 (R2↔GND). Added a step-by-step "exactly what connects where" list and kept the 3.3V/PGA/PSI notes. Previous divider was ambiguous about the tap junction.
- **[NOTE]** Clarifies the 3-way tap node (R1 lower lead + R2 upper lead + A0 signal) all land in the single 3-port Wago#2 — the point that was unclear before. GND from Wago#3 is the same net as ADS1115 GND + transducer GND (T6/Pin 9).

## 2026-07-02 — [FIX] Divider R2 20k → 22k (on-hand resistor value)
- **[HW]** User's resistor kit has no 20k (has 2k/2.2k/4.7k/5.6k/10k/22k/47k/100k). Chose **R2 = 22k** with R1 = 10k → ratio 0.6875, so 4.5V maps to ~3.09V (safe under 3.3V VDD, good ADC range use). 47k would push the tap to 3.71V (over 3.3V) → rejected.
- **[CODE]** `hardware.py`: `PRESSURE_DIVIDER_R2 = 22000.0`. Conversion is parameterized (`Vsig = Vtap × (R1+R2)/R2`), so only the constant changes; PSI math now matches the physical part (else ~3% scale error).
- **[SPEC/DIAGRAM]** HW-001 §7.1, SW-001 §2.9, and `eco004_ads1115_pressure.drawio` updated to R2=22k, ratio 0.6875, tap 0.34–3.09V, `Vsig = Vtap × 32/22`.

## 2026-07-03 — [DEPLOY] Pressure code pushed to Jetson + transducer bring-up check
- **[DEPLOY]** Jetson found on LAN at **192.168.0.196** (hostname `yahboom`; `jetson.local` mDNS did not resolve from the dev Mac). Ran `./deploy.sh 192.168.0.196` — rsynced `hardware.py`, `app.py`, `templates/index.html`, specs; `smbus2` 0.5.0 already present.
- **[VERIFY — software OK]** Ran the deployed `PressureSensor` directly on the Jetson: it initializes on **bus 1 / 0x48**, and with no ADC present it correctly logs "ADS1115 not detected ([Errno 121] Remote I/O error). Reporting disconnected (no synthetic data)" and returns `{'psi': None, 'volts': None, 'connected': False}`. Confirms the no-mock-data policy end-to-end.
- **[BLOCKER — hardware]** `i2cdetect` on **every** enabled bus (0,1,2,4,5,7,9,10,11) shows **no device at 0x48** — the ADS1115 is not acknowledging anywhere. Bus 1 shows only `40` (PCA9685/INA3221) + `25/71/72/74` (servo driver sub-addrs). So the transducer path is not yet live: the ADS1115 is either unpowered (VDD not on Pin 1 3.3V), unwired (SDA/SCL not on Pin 27/28), or mis-seated. This is a wiring/power issue, not software.
- **[PENDING]** Running service still executes the pre-pressure `app.py` (its `/api/status` has no `pressure` key). `sudo systemctl restart sentry` needs the Jetson sudo password (not available non-interactively) → user must restart to expose `/api/pressure` + the GUI test card. Restarting is only meaningful once the ADS1115 enumerates at 0x48.

## 2026-07-03 — [SAFETY] MOSFET hot / solenoid ON at boot → add 10kΩ gate pull-down
- **[SYMPTOM]** On cold start the dual-MOSFET module ran hot and the solenoid was energized (LED dim/flickering); after a click-test it cooled and the LED went dim. Live check: `gpioinfo` shows `PR.05` held `output` by `sentry-solenoid` once `app.py` (PID 1992, service active) is up — so the problem is only the boot window.
- **[ROOT CAUSE]** The module's SIG/gate has no effective pull-down. From power-on until `app.py` claims PR.05 and drives it to a hard 0V (~30–60s: nvargus + camera + model load), the Jetson pad floats to ~2.8V (matches the earlier T36 idle reading). 2.8V half-enhances the logic-level MOSFET → linear region → solenoid energized + MOSFET dissipating (V·2A) → hot; partial/noisy gate → dim, flickering LED. Software cannot cover the pre-app window → hardware fix required (SAFE-001: weapon must be de-energized at boot/fault).
- **[FIX — hardware]** Add a **10kΩ (¼W; 4.7kΩ also OK) resistor GATE→GND** at the module input, wired via **two Wago 221-413 levers**: Wago #1 (GATE node) = green T36/PR.05 wire + jumper to module SIG pin + resistor leg 1; Wago #2 (GND node) = Jetson GND (T6/T9/T14) + jumper to module GND pin + resistor leg 2. Guarantees gate=0V (MOSFET OFF, valve CLOSED) whenever the Jetson isn't actively driving 3.3V HIGH (boot, reset, crash, wire-off).
- **[DIAGRAM]** `diagrams/eco004_mosfet_module_option.drawio` bumped to Rev F: added the two Wago levers + 10kΩ resistor, rerouted green(SIG) and GND through the Wagos, added a "why the pull-down" callout, and rewrote the step-by-step for the Wago wiring + a cold-boot `SIG→GND ≈ 0V` verification (was ~2.8V). Corrected the stale "runs cold / no PADCTL needed" note.
- **[VERIFY]** Before reconnecting the solenoid: cold-boot the Jetson and measure SIG→GND — expect ~0V for the entire boot and LED OFF until the app fires.
- **[FLYBACK]** Re-confirm the 1N5408 sits across the coil (band/cathode → +12V/OUT+). Steady-state heat here is the gate float, not the flyback, but do not pulse-fire without it.

## 2026-07-03 — [DIAGRAM] Clarify MOSFET Wago #2 GND node (remove redundant bus wire)
- **[DIAGRAM]** `eco004_mosfet_module_option.drawio`: removed the extra dashed Wago #2 → COMMON GND BUS edge that implied a 4th connection. Wago #2 (GND node) holds exactly three conductors: (1) one wire to Jetson GND (T6/T9/T14 — this *is* the common-ground tie), (2) jumper to the module 3-pin header GND pin, (3) the 10kΩ pull-down leg. "T6/9/14" and "common GND bus" are the same net — one ground wire, not two.

## 2026-07-04 — [FAILURE] Dual-MOSFET module output failed SHORT → Rev G (replace module + 3A fuse)
- **[EVENT]** At Jetson power-on the solenoid clicked repeatedly, the module ran hot, and the Jetson eventually shut off. After power-cycling: click test dead, module LED never lights.
- **[DIAGNOSIS]** User measurements (power off, solenoid disconnected): **OUT+ ↔ OUT− = 9 Ω** (healthy = open) → **output MOSFETs failed SHORT**. Q&A confirmed: 10k pull-down WAS correctly installed per Rev F, 1N5408 flyback WAS installed (band → OUT+), and the **Jetson shares the same 12V adapter** as the solenoid/module. Failure chain: FET (already wounded by the earlier no-flyback sessions) went short → 12V flowed to the solenoid regardless of gate → damaged 9Ω die in series with the ~6Ω coil left the valve at ~half voltage → chatter ("many clicks") + ~5W in the FET (hot) → shared rail sagged → Jetson brownout. **The pull-down did not fail — no gate network can turn off a shorted transistor.** Pull-down + flyback stay in the design.
- **[FIX]** Replace the module with a spare from the Kioiner 5-pack (straight one-for-one wire swap, nothing changes at the Jetson/Wagos/solenoid ends) and add a **3A inline fuse in the +12V → DC IN+ feed** so a future shorted FET blows the fuse instead of dragging the shared rail (and the Jetson) down. Recommended follow-up for the commercial design: separate supplies for compute vs. actuators.
- **[DIAGRAM]** `eco004_mosfet_module_option.drawio` → **Rev G**: red fault banner (9Ω finding + why), 3A fuse drawn in the +12V feed, step-by-step rewritten as an ordered module-replacement wire-move list (steps 2-6, each wire FROM dead module TO same-named terminal on new module) plus a power-up verification sequence V1-V4 (meter checks → 12V-only LED-off check → cold-boot SIG≈0V check → click test) before reconnecting the solenoid.
- **[DIAGRAM]** `eco004_ads1115_pressure.drawio`: wiring content re-audited — correct (Bus 1 Pin 27/28, 0x48 via ADDR→GND, 3.3V VDD, 10k/22k divider + tap math match HW-001 §7.1 / hardware.py). Added a VERIFY panel (Ω checks → voltage checks → `i2cdetect -y -r 1` expect 0x48 → 0-PSI analog checkpoints). ADS1115 still not yet confirmed at 0x48 (Jetson has been off).
- **[PROCUREMENT]** parts.csv: added inline fuse holder + 3A fuses (~$9). Grand total 1976 → 1985 CAD.

## 2026-07-04 — [AUDIT] "Could the new resistors have burned the module?" — re-audit of both ECO-004 diagrams
- **[ANALYSIS]** Resistors are non-polarized — they cannot be installed "the wrong way". User's own measurement (SIG→GND ≈ 10k) confirms correct value/placement of the pull-down; a correct 10k pull-down is electrically incapable of damaging the module. The only recently-added part that CAN be reversed and WILL destroy the module is the **1N5408 flyback**: band toward (−) makes it a dead short across the supply every time the valve fires. Primary theory remains the prior linear-region cooking (boot-float episode), but reversed flyback is the one wrong-way failure mode to physically rule out.
- **[DIAGRAM]** `eco004_mosfet_module_option.drawio`: flyback box expanded — "only polarized part in this circuit" warning, reversed = dead-short consequence, and the correct test method (verify band VISUALLY toward the RED/+ wire; meter diode-mode can't test it in-circuit because the ~6Ω coil masks it — lift one leg to meter-test). Fixed garbled verification step V2: with the Jetson pigtail unplugged from the shared 12V split, apply 12V to the module only — LED must stay OFF (pull-down holds SIG at 0V).
- **[DIAGRAM]** `eco004_ads1115_pressure.drawio`: VERIFY panel gains the divider Ω row — SIG↔tap ≈ 10k (R1), tap↔GND ≈ 22k (R2), SIG↔GND ≈ 32k series; a 10k straight SIG↔GND means R1's far leg landed in the GND Wago.
- **[NOTE]** Full pre-power-on Ω checklist (module, pull-down, coil, diode, fuse, divider, I2C) issued to user in chat for verification before next power-up.

## 2026-07-13 — [BENCH] Pre-power-on Ω results: new module GOOD; ADS1115 ADDR floating; divider resistors wrong
- **[PASS]** New MOSFET module: OUT+↔OUT− = OL (healthy; dead one read 9Ω), DC IN caps charging normally. Gate path: T36↔SIG = 0Ω; SIG↔GND = 4.75k (user pull-down in parallel with the module's onboard ~10k, or a 4.7k was used — either is fine, boot-safe). Grounds 0Ω, fuse 0Ω, coil 8.7Ω, **flyback visually confirmed band → (+)** — reversed-diode failure mode ruled out.
- **[RECHECK]** DC IN+ ↔ OUT+ read OL (expected ~0Ω, normally same copper). Suspected probe contact on empty screw terminals; V2 power check (OUT+ ↔ GND = 12V) will settle it.
- **[ROOT CAUSE CANDIDATE — ADS1115 never at 0x48]** **ADDR is floating** (user: "not connected"). ADS1115 requires ADDR tied — GND = 0x48; floating = undefined/unresponsive address. Fix: jumper ADDR → GND (adjacent GND pin on the ADS header; same net as Jetson/IDC40P ground).
- **[FAULT — divider]** Transducer SIG↔GND through the divider = **96.5kΩ, expected ~32kΩ** (10k+22k). Suspect both resistors are 47k (94k nominal) or a 100k misread as 10k (brown-black-yellow vs -orange). User to measure SIG↔Wago#2 (R1) and Wago#2↔GND (R2) separately; resistors to be swapped to true 10k/22k so the firmware ratio (22/32) stays valid.
- **[CLARIFIED]** "Tap" = Wago #2, the 3-port node joining R1 bottom leg + R2 top leg + the A0 wire.

## 2026-07-14 — [BENCH] All pre-power-on checks PASS — cleared for power-up
- **[PASS]** Follow-up measurements: ADS1115 VDD↔GND ≈ 491 (matches baseline, no short — earlier "R5=0" was a meter/notation artifact); Wago#1↔GND = 24k (predicted ~24.8k: 10k+22k divider with transducer ~110k internal impedance in parallel); ADDR↔VDD ≈ 493k (= VDD↔GND, correct for ADDR tied to GND → 0x48).
- **[RESOLVED]** Divider resistors were correct all along (R1=9.17k, R2=18.6k in-circuit are exactly right for 10k/22k with parallel paths). The old 96.5k SIG↔GND reading was the transducer's internal impedance alone — the divider ground leg was open at the time and got fixed during the ADDR-jumper rework. Firmware constants (10k/22k, ratio 22/32) unchanged.
- **[STATUS]** New MOSFET module verified good (OUT open, DC IN+↔OUT+ tied, gate 4.75k pull-down, flyback band→+, fuse, coil 8.7Ω). ADS1115 fully wired (Bus 1, 0x48, divider verified). Next: V1-V4 power-up sequence (solenoid disconnected → 12V-only LED-off check → cold boot SIG≈0V → click test), then remote verification of 0x48 + /api/pressure once the Jetson is online.

## 2026-07-14 — [ROOT CAUSE] Boot firmware actively drives PR.05 HIGH — pull-down cannot win; relay-gated 12V required
- **[OBSERVED]** Power-up sequence run (solenoid disconnected). 12V only: module LED OFF (pull-down works when Jetson unpowered). Jetson BOOTING: LED goes BRIGHT → the boot firmware actively drives PR.05 high during the boot window (a driven pin defeats any pull-down; ~2.8V was measured at T36 in this state historically). After boot: LED dim/near-off (app.py claims PR.05 via libgpiod and drives 0). Module briefly went warm when the solenoid was accidentally left connected during one boot — user cut power fast; module survived (LED behavior normal afterward, no heat with solenoid off). This boot-drive is the true killer of module #1.
- **[FIX PLAN]** Software cannot close the pre-app window. Route the MOSFET module's 12V (DC IN+) through a Monk Makes relay channel (same delayed-power pattern as gimbal 12V; second dual-relay module has free channels): relay open during boot → module unpowered regardless of gate state → valve cannot open until app is up. Solenoid stays DISCONNECTED until this interlock is wired.
- **[REMOTE CHECK]** Jetson online at 192.168.0.196: sentry active and running the NEW pressure code (/api/pressure live, correctly reports connected:false / psi:null — no fake data). PR.05 shown claimed by sentry-solenoid as output. **ADS1115 STILL absent at 0x48** on bus 1 after the ADDR fix → live-voltage checks issued (VDD/SDA/SCL at the ADS pins); prime suspect if voltages pass: SDA↔SCL wires swapped (passes continuity, kills comms).
- **[TRANSDUCER]** User measured transducer SIG ≈ 2.8V steady after boot (≈57 PSI) — accumulator apparently still holding pressure from earlier sessions; 1.1V mid-boot consistent with 5V excitation still ramping. Sensor + divider behaving ratiometrically as designed.

## 2026-07-14 — [BENCH] ADS1115 SDA/SCL swap did NOT fix detection — suspect wrong header pins / broken jumper
- **[RESULT]** After the user swapped SDA↔SCL at the ADS end: rescan of bus 1 still shows no 0x48 (direct `i2cget` probes of 0x48–0x4B all fail). Bus 1 itself is healthy — PCA9685 (0x40) and other carrier devices answer normally.
- **[INSIGHT]** The earlier "SDA=3.3V, SCL=3.3V at the ADS" readings prove nothing about bus connectivity: the ADS1115 breakout has onboard pull-ups to VDD, so its I2C pins read 3.3V even with the wires disconnected. Only VDD power was actually confirmed.
- **[NEXT]** Power-off continuity checks issued: Jetson header pin 27 ↔ ADS SDA and pin 28 ↔ ADS SCL must each read ~0Ω. Prime suspects: jumpers landed on the wrong 40-pin header pins (miscount) or a broken jumper wire (same failure class as the T36 loose-wire episode).
- **[RESOLVED — 1.62V on MOSFET SIG]** Log confirms PADCTL is applied to PR.05 (PR.05=0x5) but only re-applied on each GPIO action, not guaranteed from cold boot; a 25s remote gate-hold was run + released, forcing the pad into driven mode (idle SIG now hard 0V). Reinforces that the relay-gated 12V interlock remains required for the boot window.

## 2026-07-14 — [BENCH] Wiring continuity PASS but ADS1115 still silent; module LED floating (rework disturbance); Rev H interlock implemented
- **[BENCH]** User continuity checks: **pin 27 ↔ ADS SDA = 0Ω, pin 28 ↔ ADS SCL = 0Ω** — I2C wiring is correct and intact after the SDA/SCL swap. SDA↔SCL = 2.6kΩ = normal (series pull-up networks through the 3.3V rail, not a fault). Remaining suspects for the missing 0x48 ACK: dead ADS1115 module, or pins 27/28 not routing to bus 1 on the Yahboom carrier → next power-up, scan ALL /dev/i2c-* buses for 0x48 to discriminate.
- **[FAULT]** Module LED ON with the Jetson OFF, and it dims/turns off when probed — floating SIG signature. On 07-14 the same state (12V only) had LED OFF, so the gate pull-down path got disturbed during the ADDR/SDA-SCL rework. Check: SIG→GND must read ~4.7k; if OL, re-seat the pull-down/wires in the gate Wagos. Solenoid stays disconnected until fixed.
- **[CODE — Rev H]** Solenoid 12V boot interlock implemented per HW-001 §5.5 (new): Relay CH2 (BCM 27 / PY.00 / T13 — free since the gimbal moved to the 5V buck) gates the MOSFET module's DC IN+. `hardware.py`: PY.00 (0xD030) re-added to `_PADCTL_REGS`; `_LibGpiodSolenoid` parameterized (line name/offset/consumer/label); `RelayController` claims PR.05 LOW first, then energizes CH2 (`set_solenoid_power`), drops CH2 before releasing SIG on cleanup; `solenoid_12v` added to `get_status()`. BCM 27's boot float (~2.8V) cannot energize a relay input, unlike the MOSFET gate it used to drive.
- **[SPEC]** HW-001: §5.4 rewritten for the D4184-class module as-built (was stale IRLB8721 Rev D text); new §5.5 "Solenoid 12V Boot Interlock — Relay CH2"; §5.3 pin map + §6 relay usage updated (CH2 no longer "unused").
- **[DIAGRAM]** `eco004_mosfet_module_option.drawio` → **Rev H**: banner now explains the boot-drive root cause; Relay CH2 box added with T13→IN, +12V→fuse→COM, NO→DC IN+ wiring; protection callout split into pull-down (float cases) vs relay interlock (boot window); steps panel rewritten as the 3-wire interlock install + V1-V4 verification (LED must stay OFF for the entire boot, CH2 clicks when app.py starts).

## 2026-07-14 — [DIAGRAM] Power-off Ω expectations annotated on every wire (MOSFET Rev H + ADS1115 diagrams)
- **[DIAGRAM]** `eco004_mosfet_module_option.drawio`: each wire label now carries its expected power-off resistance (all plain wires = 0Ω probe-to-probe at the screws/levers they join). New teal "Ω VERIFY" legend with node checks: SIG↔GND = 4.7k–10k (OL = pull-down leg popped → floating-LED fault), CH2 COM↔NO = OL when unpowered, OUT+↔OUT− = OL without solenoid (9Ω = shorted FETs) / ≈8.7Ω with coil, DC IN+↔DC IN− = climbing kΩ (caps), DC IN+↔OUT+ = 0Ω, fuse path 0Ω (OL = blown fuse).
- **[DIAGRAM]** `eco004_ads1115_pressure.drawio`: 0Ω annotations on the 5V/GND/SIG/tap/VDD/SDA/SCL/divider-GND wires (SDA/SCL marked ✓ verified 07-14); R1/R2 boxes show in-circuit expectations (9–10k / 18–22k, user's 9.17k/18.6k noted); ADDR note gains ADDR↔T14 = 0Ω / ADDR↔VDD ≈ 490k. VERIFY panel updated: SDA↔SCL ≈ 2–3k flagged as NORMAL (series pull-up networks), live 3.3V on SDA/SCL flagged as non-probative (onboard pull-ups), and status line updated — all Ω checks pass yet no ACK, remaining suspects = dead ADS1115 or Pin 27/28 not on bus 1 (all-bus scan next power-up).

## 2026-07-17 — [DIAGRAM] Rev H relay section redrawn to match the real Monk Makes board (user photo)
- **[CORRECTION]** The Monk Makes Dual Relay is **solid-state**: 3-pin header (IN A · IN B · GND, 4mA @ 3.3V) + 4-screw block where each channel is a plain 2-terminal switch. The previous drawing wrongly showed **Vcc←T2 (no Vcc pin exists)** and **COM/NO terminals (don't exist)**. It is also silent — the earlier "listen for the CH2 click" verification step was wrong for this board.
- **[DIAGRAM]** `eco004_mosfet_module_option.drawio`: relay redrawn as the physical board — header pins IN A (pump, existing), **IN B ← T13 (new wire)**, **GND ← GND bus**; screw block A①A②/B①B② with **+12V→fuse→B①** and **B②→module DC IN+**. Steps + V1-V3 rewritten with the real terminal names (B①↔B② = OL when off; V3 now checks DC IN+ = 12V after app start instead of listening for a click). Ω legend updated. Ratings noted: 2A/16V max, 1.5A continuous — solenoid's ~2A flows only during ≤0.4s pulses.
- **[SPEC]** HW-001 §5.5 updated to the same terminal naming, no-Vcc note, and current-rating note.

## 2026-07-17 — [DEPLOY] Rev H interlock code deployed to Jetson; awaiting user power-cycle to activate
- **[HARDWARE]** User completed the Rev H relay wiring (T13→IN B, +12V→fuse→B①, B②→module DC IN+).
- **[DEPLOY]** Full `deploy.sh` run to 192.168.0.196 — hardware.py (PY.00 interlock) + diagnostics.py (was missing on target) now on the Jetson; md5 verified. Remote `sudo` requires a password, so the root-owned sentry service could not be restarted remotely — user to power-cycle, which also properly tests the boot window (module LED must stay OFF during the entire boot, DC IN+ = 12V only after app.py starts).

## 2026-07-17 — [SUCCESS] Rev H boot interlock LIVE — click test passes; ADS1115 isolated to the module itself
- **[PASS]** User power-cycled after the Rev H deploy: module LED stayed OFF through boot, click test WORKS. Remote status confirms `solenoid_12v: true` (channel B energized by app.py), solenoid closed at rest. The boot-window kill-chain is closed.
- **[ANALYSIS — ADS1115]** All-bus I2C scan (0/1/2/4/5/7/9/10): 0x48 nowhere. Bus 1 shows 0x40 + 0x71/0x72/0x74 — the PCA9685's sub-addresses — and the PCA9685 is wired to the SAME Pin 27/28 terminals (HW-001 §3) with working servos → **the bus electrically reaches those terminals; carrier routing is ruled out**. With power (3.3V), ADDR→GND, and wire continuity all previously verified, the fault is isolated to the ADS1115 board itself.
- **[PRIME SUSPECT]** Unsoldered header pins — these modules ship with a loose pin strip; pins pushed through unsoldered pass a pin-to-wire continuity check and even show 3.3V at the pin, while the chip pads stay disconnected. User to check for solder fillets on the back and re-test continuity from wire → PCB pad (not pin). If soldered: module dead → replace (~$11).

## 2026-07-19 — [SUCCESS] Replacement ADS1115 detected at 0x48 — pressure loop LIVE
- **[PASS]** New ADS1115 installed and powered: `i2cdetect -y -r 1` shows **48** alongside PCA9685 `40` / `71`/`72`/`74`. `/api/pressure` → `connected:true`, `volts:0.492`, `psi:0.0` (matches AUTEX 0.5V @ 0 PSI within divider/noise). Direct `i2cget` of conversion register succeeds. Prior no-name module confirmed dead; breakout replacement + existing Bus 1 / Pin 27-28 / 10k/22k divider / ADDR→GND path is correct.

## 2026-07-19 — [ROOT CAUSE] Keep-alive pump toggle glitched MOSFET SIG (PR.05) → valve stuck ON / hot
- **[OBSERVED]** User: 5‑min Priming keep-alive coincided with solenoid click; dual-MOSFET then stayed ON and ran hot (power cut quickly). Jetson still on pre-restart code (keep-alive active). Log shows keep-alive only called `fire_pump` — no `Solenoid OPEN` line — so software never intentionally opened the valve.
- **[MECHANISM]** `_set_pump()` called `configure_push_pull()` which re-wrote **PR.05** PADCTL on every pump edge while libgpiod owned the solenoid line. That pad rewrite can glitch SIG high → MOSFET on. With a weak/disturbed pull-down the FET can stay in conduction and cook.
- **[FIX]** `configure_push_pull(only=…)`: pump path only programs **PR.04**; full pad set reserved for init. On pump OFF, force solenoid line LOW. Keep-alive already removed in favor of PSI maintain — **restart sentry** required to load both fixes.

## 2026-07-19 — [FEATURE] Replace timed keep-alive/top-up with pressure maintain
- **[REMOVED]** PrimingSystem 5‑min `fire_pump` keep-alive (app no longer starts it; GUI sliders removed). One-shot "Prime Now" remains for line fill.
- **[REMOVED]** Accumulator timed top-up timer (`TOPUP_INTERVAL_SEC` ~60s) — not needed with live PSI.
- **[ADDED]** While ARMED, AccumulatorManager pressure-maintain loop: if PSI &lt; `target_psi − maintain_hysteresis_psi` (default 1.0), recharge to target. Calibrate via GUI **Target PSI**. SW-001 §2.7 updated.

## 2026-07-20 — [FEATURE] settings.json + Target PSI in Calibration & Settings
- **[SPEC]** SW-001 §2.11: central `settings.json` (auto-created), `GET/POST /api/settings`, Calibration runtime override + confirm "Save as permanent?", Settings tab permanent control. Factory default `target_psi=5`.
- **[CODE]** `settings_store.py`; `app.py` loads/applies at boot; clamp 1–40 PSI. GUI: Calibration card (live PSI, immediate apply, Save/Reload); Settings permanent card; post-auto-cal confirm prompt. `settings.json` gitignored.
- **[NOTE]** Former Solenoid-tab-only slider remains as a convenience mirror; permanent source of truth is settings.json.

## 2026-07-19 — [FEATURE] Closed-loop charge-to-PSI (default target 15 PSI)
- **[GUIDANCE]** 2–5 PSI too weak for useful throw (distance ∝ √P; nozzle ~30 PSI class). Default **TARGET_PSI = 15** for consistency tests; raise toward 20–30 after watching the live plateau. Keep setpoint below pump dead-head so charges finish fast.
- **[SPEC]** SW-001 §2.7 updated: when PressureSensor is connected, arm/top-up pump until PSI ≥ `target_psi`; timed `initial_charge_sec`/`topup_charge_sec` are fallbacks only; `MAX_PUMP_RUN_SEC` hard timeout stays.
- **[CODE]** `AccumulatorManager`: optional `pressure` arg; `_charge()` closed-loop loop (50ms poll); `TARGET_PSI` + config/API/GUI slider; arm/fire/status report real PSI; `app.py` wires `AccumulatorManager(relay, pressure)`. No fabricated PSI if sensor absent.

## 2026-07-07 — [FEATURE] GUI Diagnostics Suite — 59 targeted tests (SW-001 §2.10)
- **[SPEC]** Added SW-001 §2.10 "GUI Diagnostics Suite": registry of fine-grained, individually runnable diagnostics with `status ∈ {pass, warn, fail, skip}`, actuator-safety gating (`confirm: true` required for tests that move hardware), and a no-mock-data guarantee.
- **[CODE]** New `diagnostics.py` — decorator-based test registry (59 tests, 10 categories) + `init()` dependency injection from `app.py`. Categories: Pressure/Transducer (9: ADS1115 ACK, connected, range, zero-baseline, noise σ, poll thread, charge-Δ, 10s leak-down, PSI-per-shot), I2C & GPIO (5: bus-1 scan, PCA9685, TF-Luna probe on both buses, PR.05 line state, PADCTL 0x90/0x98 readback), Servo/Gimbal (8: controller/settings, center, yaw/pitch sweeps, ±limit clamp [SAFE-001], repeatability, power-relay toggle), Cameras (8: frame/FPS/exposure/focus × Scout+Sniper), AI/Vision (6: detector loaded, .engine present, inference latency, thresholds, pixel_to_angle + predictive-lead math), LiDAR (3), Solenoid/Trigger (5: libgpiod backend, closed-at-rest, click, 10ms pulse timing, fire-lockout-when-disarmed), Pump/Accumulator (5: rest-off, burst, arm/disarm cycle, config bounds, priming keepalive), Calibration (4), System (6: thermal zones, nvpmodel, disk, memory, nvargus-daemon, log error scan).
- **[CODE]** `app.py`: three new routes — `GET /api/diag/list`, `POST /api/diag/run`, `POST /api/diag/run_category`; `diagnostics.init()` injects relay/accum/gimbal/lidar/pressure/cams/primer/cal_table plus lazy getters for detector and arc compensation.
- **[GUI]** `templates/index.html`: new 🩺 Diagnostics tab (between Tests and Settings). Per-category cards with per-test rows (badge, name, description, live message + elapsed ms, Run button), "Run All Safe Tests", "Run category", and an explicit ⚠️ "arm actuator tests" checkbox that unlocks the ACTUATOR-tagged rows (servo sweeps, pump bursts, solenoid pulses, pressure charge/leak/shot tests). Unarmed actuator tests report `skip` — enforced server-side, not just in the UI.
- **[SAFETY]** Actuator gating is server-side (`run_test` refuses without `confirm`), and the fire-lockout test itself verifies `accum.fire()` returns `not_armed` when disarmed. Water-dependent tests (charge-Δ, leak, PSI-per-shot) skip cleanly when the ADS1115 is absent — no fabricated readings.
- **[VERIFY]** Off-target smoke run on the dev Mac: registry lists 59 tests / 10 categories; `sys_disk` and `math_pixel_to_angle` pass; `sol_click` correctly refused without confirm; `cal_ballistic_table` warns (file absent). `py_compile` clean.
- **[DEPLOY]** Jetson offline (no ping at 192.168.0.196) — deploy + on-target bring-up of the new tab pending next power-up (blocked on the Rev G MOSFET module replacement anyway).

## 2026-07-20 — DEPLOY/RESTART VIA run-ai.sh
- **[PROCESS]** Restored non-interactive Jetson restart: `deploy.sh` loads `.env` and pipes `JETSON_PASSWORD` to `sudo -S systemctl restart sentry` (same pattern as `run-ai.sh`).
- **[PROCESS]** `run-ai.sh` default is now deploy + restart (not full reboot). Use `./run-ai.sh --reboot` for CSI-clean reboot; `./run-ai.sh --no-deploy` for restart-only.
- **[DEPLOY]** Ran `./run-ai.sh` → synced to 192.168.0.196 and restarted `sentry.service`.

## 2026-07-20 — MOSFET HOT: PULSE-POWER CH2 (Rev I)
- **[INCIDENT]** Dual-MOSFET module turned ON and ran hot twice with no operator input (~10–12 min after soft restart). Jetson power-cycled both times.
- **[ROOT CAUSE]** Rev H left Relay CH2 (module 12V) latched ON for the whole `app.py` session after claiming PR.05 LOW. Any later SIG glitch (or unclean release) powered the FETs continuously.
- **[FIX]** Rev I pulse-power: CH2 OFF at idle; `_set_solenoid(True)` gates 12V only for the open pulse; close cuts SIG then CH2. Specs: HW-001 §5.5, SAFE-001, SW-001 §2.7.
- **[CSI]** Confirmed soft `systemctl restart` still leaves Sniper black (`NvBufSurfaceFromFd Failed` / 0 flushed frames). Restored `./run-ai.sh` default to full reboot; `--restart` for soft-only.
- **[DEPLOY]** Pending `./run-ai.sh` (deploy + reboot).

## 2026-07-20 — MOSFET SIG LED AT IDLE
- **[OBSERVED]** Dual-MOSFET SIG LED on while module stayed cold; click test turned LED off. Duration unknown.
- **[ANALYSIS]** LED tracks SIG HIGH, not FET load current. Rev I CH2-off explains cold+LED: trigger asserted, 12V gated away. Click close re-drove SIG LOW.
- **[CODE]** Idle watchdog every 1s re-asserts SIG LOW + CH2 OFF when not intentionally open; re-assert after pump edges; HW-001 notes SIG LED semantics.

## 2026-07-20 — [FEATURE] Unify all GUI tunables into settings.json + 30 backups
- **[DECISION]** Everything in the GUI persists to one file; Apply = temporary runtime; Save as permanent = disk. Solenoid accumulator + calibration offsets + scout MOG2 merge into the same tree. Last 30 saves backed up; corrupt/missing `settings.json` restores from latest backup; no backups → factory defaults then create `settings.json`.
- **[SPEC]** SW-001 §2.11 rewritten for grouped schema, backup policy, Apply vs Save. ScoutAgent §2.1 prefers `settings.scout`.
- **[CODE]** `settings_store.py`: groups `accumulator/servo/pulse/prime/stabilize/calibration/scout`; migrate legacy flat `target_psi`, `scout_config.json`, `calibration_visual.json`; `settings_backups/` rotate max 30. `app.py` `apply_settings_to_runtime()` at boot; `GET/POST /api/settings` full tree. `CalibrationTable` persists via store. `ScoutVision`/`main.py` load `settings.scout`.
- **[GUI]** Settings **Save All as Permanent**; Apply buttons labeled runtime; Solenoid accum Save as Permanent; Calibration offset Save confirms → settings.json. Nested `settings.accumulator.target_psi` reads fixed.
- **[GIT]** `.gitignore`: `settings_backups/`.

## 2026-07-20 — [BUG FIX] Sniper black after soft update — detect CSI PHY death + auto-reboot
- **[BUG]** After `./run-ai.sh --restart` / `deploy.sh` soft restart, Sniper (CSI-1) showed no video: `NvBufSurfaceFromFd Failed`, flushed 0 frames. Scout OK. Confirmed soft recovery (stop sentry + restart nvargus + sniper-only gst-launch) **cannot** clear Orin CSI-1 PHY — only full reboot works (same root cause as 2026-06-03).
- **[CODE]** `vision.py`: if Jetson open succeeds but flush==0 → release dead pipeline, `error=csi_phy_dead`, overlay "CSI DEAD — ./run-ai.sh"; `get_status()`.
- **[CODE]** `app.py`: `GET /api/cameras/status` (`ok`, `reboot_required`); CRITICAL log when Sniper unhealthy at start.
- **[OPS]** `deploy.sh`: after soft restart, poll camera status; if `reboot_required`, auto-reboot and wait for dashboard. Prevents the persistent “updated but Sniper invisible” loop.

## 2026-07-20 — [FEATURE] Pressure-gated solenoid-only fire (live + auto-cal)
- **[DECISION]** Pump only maintains Target PSI (solenoid closed). Every shot waits until pressure ready, fires **solenoid-only** (pump OFF, no overlap), then recharges before the next shot. Maintain polls every **60 s** while ARMED, **no hysteresis**. Sensor fault → disarm + alarm. Same path for auto-cal and live mosquito fire; one standard pulse.
- **[SPEC]** SW-001 §2.7 rewritten to the charge/fire contract above.
- **[CODE]** `AccumulatorManager`: `_ensure_pressure_ready`, fire gate + post-shot recharge, `PRESSURE_POLL_SEC`, hyst=0, `_fail_sensor` + `on_alarm`, arm refuses if target not reached with live sensor.
- **[CODE]** `AutoCalibrator` / freefire: use `accum.fire()` (no `fire_pump` shots); arm before cal, disarm after.
- **[GUI]** Settings → Pressure Maintain card: target PSI, poll interval, standard pulse, max pump run; Apply runtime + Save as permanent.
- **[SETTINGS]** Defaults: `pressure_poll_sec=60`, `maintain_hysteresis_psi=0`, `default_pulse_ms=25`.

## 2026-07-20 — [BUG FIX] Auto-cal “no click” + Click Test broken after cal + activity.log
- **[ROOT CAUSE]** Logs showed auto-cal *did* command OPEN/CLOSE at **25ms** — often inaudible. Worse: `AccumulatorManager.fire()` called unlocked `_set_solenoid()`; during the 15ms CH2 settle the idle watchdog saw `_solenoid_state=False` but `_sol_12v_state=True` and **cut module 12V mid-pulse**, so the coil never got a clean open. After many cycles Click Test became unreliable until hold-time fiddling / recover.
- **[CODE]** `RelayController.pulse_solenoid()` — entire open window under lock; watchdog skips when CH2 ON; `recover_solenoid()` re-pinmux + SIG/CH2 safe. Fire + Click Test use locked pulse; disarm/auto-cal end always recover.
- **[CODE]** `activity_log.py` — rotating **10 MB** `activity.log` (5 backups) for ARM/FIRE/CLICK_TEST/AUTOCAL_*.
- **[SETTINGS]** Shared pulse default **100ms** (migrate ≤25ms → 100); Settings slider 10–500ms with audible hint.
- **[NOTE]** Pressure not holding with a 10 PSI air pre-charge also needs a sealed valve; race above could flutter the valve. Re-test hold after this fix.

## 2026-07-20 — [FEATURE] Control tab DRAIN PIPE (15s)
- **[CODE]** `RelayController.drain_line()`: solenoid OPEN + pump ON for N seconds under lock, then safe idle. `POST /api/line/drain` disarms first, drains, `recover_solenoid()`. GUI Control → Fire Control **DRAIN PIPE (15s)** with confirm.
- **[SPEC]** SW-001 §2.7 notes maintenance drain as the only intentional pump+open-valve overlap.

## 2026-07-20 — [BUG FIX] Auto-cal clicks die after ~3 shots (CH2 SSR thrash)
- **[OBSERVED]** Second auto-cal: audible click on first ~3 of ~30 shots; software still logged OPEN/CLOSE every time.
- **[ROOT CAUSE]** Every pump charge edge called `_force_solenoid_safe()` (cut CH2) and/or PADCTL rewrite on PR.04. Combined with per-shot CH2 pulse-power, the Monk Makes SSR was cycled dozens of times per cal → intermittent no-click while libgpiod still “succeeded”.
- **[FIX]** While ARMED: `set_module_power_hold(True)` keeps CH2 ON; shots are SIG-only. Pump edges only soft-assert SIG LOW (never cut CH2 / no padmux). Settle 80ms for cold CH2. Click/drain recover without PR.05 remap.
- **[SPEC]** SW-001 §2.7 updated for ARMED-session module power.

## 2026-07-20 — [BUG FIX] CH2 hold “ON in software” but LED off / ~4 clicks
- **[OBSERVED]** Auto-cal with hold: sentry.log showed `ch2_held=True` and `CH2 hold ON` for every shot; operator saw Monk Makes CH2 LED not staying on; only ~4 audible solenoid clicks; PSI barely dropped on most shots.
- **[ROOT CAUSE]** Software cached `_sol_12v_state=True` and skipped re-driving PY.00. If the SSR/GPIO dropped after a few shots, SIG still pulsed (module SIG LED blinks) with no module 12V → silent “fires”.
- **[FIX]** Always `_drive_module_12v_on()` before SIG open, after SIG close (while hold), on every pump edge while armed, and every 0.5s watchdog tick while hold. Log CH2 libgpiod readback on FIRE (`ch2_rb`).
- **[NOTE]** Monk Makes CH2 is a silent SSR — listen for the **solenoid** click, watch **Relay CH2 IN LED** (not the MOSFET SIG LED).

## 2026-07-20 — [HW/SW] Rev J: CH2 never closes — hardwire module 12V
- **[OBSERVED]** Auto-cal: MOSFET SIG LED lights on every shot, **zero** solenoid clicks; Monk Makes Channel B never turns on; both relay LEDs dim/flicker. Logs: `ch2_rb=1` every FIRE.
- **[ROOT CAUSE]** Yahboom **PY.00** reports HIGH to software but does not drive enough current into Monk Makes SSR IN B — Channel B stays open → module DC IN+ dead → SIG LED (logic) still works, coil never moves.
- **[FIX]** Default `module_12v_hardwired=true`: leave CH2 GPIO idle; operator **jumpers CH2 load screws** (or feeds fused 12V to module). CH2 drive moved to Jetson.GPIO for gated experiments. GUI Step 0 + `/api/solenoid/ch2_hold`. Specs HW/SW/SAFE updated Rev J.

## 2026-07-20 — [PROCESS] Catch-up: HISTORY + commits for solenoid troubleshooting saga
- **[MISS]** Multi-step ECO-004 solenoid/auto-cal work was documented in HISTORY but **not git-committed** after each step (violates agents.md Commit Every Step).
- **[ACTION]** Expanded this log with the index below; created/updated `history.txt` mirror; split catch-up into discrete commits matching the steps.
- **[TROUBLESHOOTING INDEX — solenoid click / CH2 / auto-cal]**
  1. Rev I pulse-power CH2 (module hot when 12V latched) → CH2 OFF at idle.
  2. SIG LED on while cold → idle SIG watchdog; LED ≠ coil power.
  3. Soft restart → Sniper CSI PHY dead → detect + `deploy.sh` auto-reboot.
  4. Pressure-gated solenoid-only fire (pump ≠ shot); 60s maintain; no hysteresis.
  5. Auto-cal “no click”: 25ms inaudible + idle watchdog cut CH2 mid-settle → locked `pulse_solenoid`, 100ms default, `activity.log`.
  6. DRAIN PIPE (15s) intentional pump+open overlap.
  7. Clicks die after ~3 shots: pump-edge CH2/padmux thrash → ARMED `module_power_hold`.
  8. Hold ON in logs / LED off / ~4 clicks: cached `_sol_12v_state` skipped re-drive → always re-assert CH2 + `ch2_rb` log.
  9. Zero clicks; SIG LED on; Channel B never on; `ch2_rb=1`: PY.00 too weak for SSR → **Rev J hardwire** (jumper CH2 load).
- **[OPERATOR]** Until Channel B can be driven strongly: jumper Monk Makes CH2 load screws (or fused 12V → module DC IN+); keep `module_12v_hardwired=true`; Click Test should then click.

## 2026-07-21 — [TROUBLESHOOT] Auto-cal still silent under hardwired=True
- **[OBSERVED]** Latest auto-cal: 28 FIRE events, `hardwired=True`, `ch2_rb=0`, SIG OPEN/CLOSE logged; PSI barely moves (e.g. 2.0→1.9); operator reports no clicks.
- **[ANALYSIS]** Software path is correct for Rev J (SIG-only). Silent coil + flat PSI means **module DC IN+ still has no 12V** — Channel B load was almost certainly **not jumpered** (or jumper on wrong channel / open fuse). SIG LED can still light.
- **[CODE]** Auto-cal start now **blocks** unless `confirm_module_12v_jumper=true`; GUI checkbox + amber warning on Calibration tab.
- **[OPERATOR]** On Monk Makes: short the **two Channel B screw terminals** together (B①↔B②), or bypass relay and land fused +12V on module DC IN+. Then Click Test → expect two clicks → auto-cal with checkbox checked.
- **[IF STILL SILENT AFTER JUMPER]** Meter module DC IN+ (~12V), then OUT+/OUT− during Click Test; check 3A fuse and solenoid coil wiring.

## 2026-07-21 — [BUG FIX] Intermittent clicks after CH2 jumper (SIG hammering)
- **[OBSERVED]** After jumpering Channel B: clicks sometimes work in a row, sometimes absent, sometimes multiple per “shot”; Click Test flaky.
- **[EVIDENCE]** Auto-cal logs clean single 100ms OPEN/CLOSE per FIRE; points retry up to **3** attempts (sounds like multi-click). PSI sometimes dumps 1.7→0.1 (real open), sometimes flat (missed actuation). Extra `Solenoid CLOSED` lines from redundant writes.
- **[ROOT CAUSE]** With module 12V latched ON, idle watchdog + pump edges **re-wrote SIG LOW every 0.5s / every pump edge** even when already LOW — Yahboom PR.05 glitches → phantom / missed clicks. Rapid Click Test double-submit overlapped pulses. Auto-cal retries amplified “multiple clicks”.
- **[FIX]** Watchdog/pump only clear SIG if stuck HIGH; hardwired open = clean rising edge (no pre-LOW toggle); idempotent close; `pulse_busy` rejects overlap; skip recover before Click Test when hardwired; 40ms post-close settle; auto-cal `MAX_RETRIES=1` + 350ms settle.
- **[OPERATOR]** One Click Test press → expect **two** clicks (open+close). Auto-cal: up to **two** pulses per point if miss. Keep jumper solid (no intermittent contact).

## 2026-07-21 — [VERIFY] CH2 jumper: reliable clicks; keep Rev J hardwired
- **[OPERATOR]** With Channel B load jumpered: Click Test and auto-cal clicks are reliable.
- **[DECISION]** Do **not** restore CH2 SSR gating via PY.00 — Yahboom pad cannot drive Monk Makes IN B. Leave jumper (or fused 12V → module DC IN+) and `module_12v_hardwired=true`.
- **[NOTE]** Multiple clicks per auto-cal “shot” are mostly intended: 2 per pulse (open+close); up to 2 pulses/point on miss → up to 4 clicks/point. GUI Calibration panel notes this.

## 2026-07-22 — [BUG FIX] Control TEST FIRE / DRAIN / Solenoid FIRE paths
- **[OBSERVED]** Checklist: Solenoid ARM/FIRE seemed to run pump not solenoid; Control TEST FIRE ran pump and left solenoid stuck OPEN until Click Test; DRAIN kept pump on but valve clicked open/closed repeatedly; Click Test then failed.
- **[ROOT CAUSE]** (1) `/api/relay/fire` still called legacy `fire_pump`. (2) `_set_pump` closed SIG whenever valve was open — broke DRAIN (OPEN then immediate CLOSE). (3) Solenoid FIRE slider defaulted to **10ms** (inaudible) while post-shot recharge pump was loud.
- **[FIX]** TEST FIRE → `accum.fire()` (auto-arm); DRAIN uses direct pump GPIO with valve held OPEN; pump start never closes intentional open; Solenoid FIRE default **100ms**; Click Test always `recover_solenoid` first; cal `fire_test` uses accum.
- **[GUI]** Labels clarify pump=charge, FIRE=solenoid (2 clicks).

## 2026-07-22 — [SAFE] MOSFET hot at boot with Channel B jumpered (Rev J.1)
- **[OBSERVED]** After jumpering CH2 load for reliable clicks, dual-MOSFET module gets hot during Jetson boot.
- **[ROOT CAUSE]** Expected: jumper removes CH2 boot interlock; Orin firmware drives PR.05 (SIG) HIGH before `app.py` claims it → FETs conduct with 12V present.
- **[OPS]** Prefer **SPST switch in series with jumper** (OFF at power-on, ON after dashboard / SIG LED dark). Or remove jumper for each reboot.
- **[CODE]** `scripts/claim_sig_low.py` + `sentry.service` ExecStartPre (before and after nvargus wait) to shorten userspace HIGH window. Cannot cover firmware window.
- **[SPEC]** HW-001 §5.5 Rev J.1 + SAFE-001 updated; GUI Step 0 boot-heat warning.

## 2026-07-21 — [HW/SW] Rev K: CH2 IN moved T13 → T22 (restore gated 12V)
- **[HW]** Operator moved Monk Makes **IN B** from **T13 (BCM 27 / PY.00)** to **T22 (BCM 25 / PY.01)** and removed Channel B load jumper (SSR gating restored).
- **[CODE]** `hardware.py`: `RELAY_SOL12V_PIN=25`; PADCTL `PY.01` @ `0xD000` (was PY.00 @ `0xD030`); default `module_12v_hardwired=False`. `claim_sig_low.py`, settings default, GUI Step 0 / auto-cal confirm (gated path skips jumper checkbox).
- **[SPEC]** HW-001 §5.3/§5.5, SW-001 §2.7, SAFE-001 — Rev K gated default; hardwired remains fallback.
- **[TEST]** Deploy + force settings hardwired=false; CH2 hold → Channel B LED bright; Click Test → 2 clicks; MOSFET cold at idle.

## 2026-07-21 — [ROOT CAUSE] T22/PY.01 also too weak for Monk Makes CH2 → Rev L T29
- **[OBSERVED]** After Rev K: CH2 hold reports `ch2_rb=1` / `BCM25/T22` but **Channel B LED stays off**; Click Test silent (same signature as PY.00/T13).
- **[ROOT CAUSE]** Entire Yahboom **PY.*** SPI bank is too weak to source Monk Makes IN B current; moving T13→T22 stayed in that bank.
- **[FIX — Rev L]** Move CH2 IN to **T29 / BCM 5 / PQ.05** (PADCTL `0x68`, same PADCTL_A0 block as proven PR.04/PR.05). Software + specs updated; operator must move IN B wire T22→T29 (Channel B still not jumpered).

## 2026-07-21 — [DECISION] Rev M: abandon CH2 GPIO gating; restore hardwired jumper
- **[OBSERVED]** T29/PQ.05 also fails: Hold CH2 → `pin=BCM5/T29` `ch2_rb=1`, Channel B LED off, Click Test silent. Three pads exhausted (T13/T22/T29).
- **[DECISION]** Stop pin-hopping. Restore **Rev J hardwired**: jumper Channel B load + `module_12v_hardwired=true` (factory default). Boot-heat mitigation = series MODULE 12V switch. Long-term gated CH2 needs **transistor buffer** on IN B, not another header pin.
- **[CODE/SPEC]** Defaults/GUI/HW-001/SW-001/SAFE-001 → Rev M hardwired.

## 2026-07-21 — [DIAGRAM] Rev N 2N3904 CH2 buffer wiring guide
- **[DIAGRAM]** Rewrote `diagrams/eco004_mosfet_module_option.drawio` for **2N3904 emitter follower**: T29→1k→Base, T17→Collector, Emitter→IN B + 10k→GND. Explicit REMOVE jumper / MOVE IN B wire / ADD parts checklist. SIG path unchanged.

## 2026-07-23 — [OPS] Gated CH2 for T29 bench test (jumper removed; pre-transistor)
- **[OPERATOR]** Channel B load jumper removed. Suspect intermittent clicks were a **loose T29↔IN B wire**, not necessarily weak-pad alone. Will Click Test / auto-cal on direct T29 drive before installing 2N3904.
- **[CODE]** Default `module_12v_hardwired=false` again (settings_store / RelayController / app.py sync). GUI Step 0: gated/T29 primary; auto-cal jumper box hidden unless hardwired.
- **[DEPLOY]** Force Jetson settings hardwired=false; soft-restart for gated CH2 on BCM 5 / T29.

## 2026-07-23 — [DIAG] Mixed LEDs; fix Gate Hold; transistor still likely
- **[OBSERVED]** Hold duration: MOSFET LED tracks full time; Channel B only flashes on Click Test; auto-cal Channel B stays lit, SIG flashes, **no clicks**.
- **[ANALYSIS]** Logs show both `ch2_hold` and `gate_hold`. Old `gate_hold` called `set_solenoid(True)` which also enables CH2 — confused LED diagnosis. Click Test pulse-power = brief CH2 flash (expected). Auto-cal CH2 hold + SIG pulse with silence ⇒ SSR/load not delivering coil 12V (weak T29 and/or B①/B② feed after un-jumper).
- **[FIX]** `hold_sig()` = SIG only, CH2 forced OFF; `hold_ch2()` uses pulse_busy + clear logs. GUI clarifies which button is which.
- **[NEXT]** Verify load: +12V→fuse→B①, B②→DC IN+. Meter DC IN+ during auto-cal (expect ~12V). If LED on but DC IN+=0 or no click → **2N3904 still needed** (or restore jumper temporarily to confirm).

## 2026-07-23 — [VERIFY] Gated T29 works without transistor (after reseat)
- **[OPERATOR]** Click Test + auto-cal clicks succeed with Channel B **not jumpered**, `hardwired=false`, **no 2N3904** — after reseating T29↔IN B (loose-wire theory).
- **[STATE]** Jetson `settings.json` has `module_12v_hardwired=false` (survives reboot). Code on `main` / origin at `fb608f2` + this note.
- **[NOTE]** Keep 2N3904 kit for later if flaky again; not required while T29 drive stays solid.

## 2026-07-23 — [PROCUREMENT] Option B Pico solenoid path → parts.csv
- **[BOM]** `parts.csv`: to-order Pico W SCO918 ($15.90), 8-value diode kit w/ 1N5408 ($10), USB-A↔Micro-B ($8); ON HAND IRLB8721 5-pack ($9), BOJACK transistor kit ($14.99). Prior 1N4007 already on BOM (no double-count). Grand total 1985 → **2034.89** CAD.
- **[INTENT]** Option B: Jetson→USB→Pico→IRLB8721→solenoid (drop dual-MOS module + CH2 for valve); pump stays on Monk Makes CH1.

## 2026-07-24 — [DIAGRAM] Option B cable map clarity (C1–C8)
- **[DIAGRAM]** `eco004_mosfet_module_option.drawio`: rewritten as explicit **cable map** — numbered C1–C8 with END A → END B for every connection, R1–R4 remove list, colored arrows on layout picture, build order 1–9.

## 2026-07-24 — [DIAGRAM] Option B after-wire Ω table
- **[DIAGRAM]** Same drawio: added **AFTER WIRED** resistance/diode table (GP15↔Gate ~220Ω, Gate↔GND ~10kΩ, Source/Pico GND continuity, coil/fuse/diode/FET checks). 12V must stay unplugged for Ω tests.

## 2026-07-25 — [DIAGRAM] Fix C5 arrow landing on +12V (looked like Source→12V)
- **[DIAGRAM]** `eco004_mosfet_module_option.drawio`: C5 Source arrow tip was at the red **+12V** box coords — retargeted to black **GND** (T6/T9/T14). Labels: Source → GND only (never +12V); +12V is C7→solenoid RED only.

## 2026-07-26 — [OPS] Pico W flashed on Jetson (Option B)
- **[OPS]** First cable was power-only (LED off, no USB enum). Data cable → BOOTSEL `2e8a:0003` / `RPI-RP2`.
- **[FW]** Copied MicroPython UF2 `RPI_PICO_W` + `firmware/pico_solenoid/main.py` via mpremote on Jetson.
- **[VERIFY]** Serial: `CLOSE→OK CLOSE`, `PING→PONG`, `FIRE 5→OK FIRE 5`. Device `2e8a:0005` MicroPython FS mode `/dev/ttyACM0`.
- **[SW]** Restarted `sentry`: `[PicoSolenoid] Connected /dev/ttyACM0 @ 115200 — gate CLOSED.`

## 2026-07-27 — [DIAGRAM/SPEC] External check valve as-built (pump→accumulator)
- **[HW]** Feelers 1/4" one-way check valve **installed** between pump outlet and accumulator (arrow toward tank) — holds PSI when pump OFF.
- **[DIAGRAM]** Rewrote `diagrams/eco004_fluid_topology.drawio` with check valve + transducer tee; updated `eco004_vertical_stack.drawio` pump note.
- **[SPEC]** `HW-001` §8: check valve mandatory (pump internals insufficient); topology + routing updated for Option B solenoid drive.
- **[BOM]** `parts.csv` Feelers check valve → **have** / installed.

## 2026-07-27 — [FIX] Pico USB reseat auto-reconnect (no sentry restart)
- **[ROOT CAUSE]** After unplug, pyserial often still reports `is_open`; by-id node is gone. Idle loop never reconnected until restart. New/bad cables also show **no USB enum** (LED off / no `2e8a`).
- **[FIX]** `pico_solenoid.py`: treat missing device node as dead; `health_check()` every 0.5s; FIRE retries reconnect + 300ms settle; rate-limit STUB logs; log `reconnected after USB reseat`.
- **[FIX]** `RelayController` idle watchdog calls `pico.health_check()` continuously.

## 2026-07-27 — [UI] Mobile dashboard: Control tab + slider pan
- **[BUG]** On phone, tab bar overflow hid **Control**; dragging range sliders panned the whole page sideways.
- **[FIX]** `templates/index.html`: wrap tabs on narrow screens; `overflow-x:hidden` + `overscroll-behavior-x:none`; `touch-action:none` on range inputs; tighter mobile tab/slider spacing.

## 2026-07-27 — [DEPLOY] Hunt mode to Jetson + reboot verify
- **[DEPLOY]** `./run-ai.sh` → rsync incl. `hunt_controller.py` / `app.py` / `templates/index.html` / SW-001 §2.13 → full reboot `192.168.0.196`.
- **[VERIFY]** After boot: dashboard HTTP 200; `sentry` active; `/api/hunt/status` → `mode=HUNTING`, `armed=true`, insect `best.engine` loaded; Start/Stop in served HTML.
- **[NOTE]** `run-ai.sh` 90s dashboard poll timed out once (arm + TensorRT load delayed bind); service was healthy immediately after — consider longer wait later if this recurs.

## 2026-07-27 — [FEATURE] Hunt attempt capture gallery (stills + ≤5s video)
- **[SPEC]** `SW-001` §2.14 v5.2: while HUNTING, record Scout+Sniper before/after JPEGs (raw + annotated) and ≤5s clips for verified fires **and** rejects; retain last 50 under `hunt_captures/` (auto-prune).
- **[CODE]** `hunt_capture.py` — ring buffers @10 FPS, async finalize, MP4/`mp4v` with MJPEG `.avi` fallback.
- **[CODE]** `hunt_controller.py` — tick buffers while hunting; `_record_attempt` on fire/reject/arm-fail.
- **[API]** `GET /api/hunt/captures`, `/api/hunt/captures/<id>`, `/api/hunt/captures/<id>/<file>`.
- **[UI]** Control-tab **Hunt Attempts** card — thumbnails, expand to play stills/videos.
- **[GIT]** `.gitignore` → `hunt_captures/`.

## 2026-07-27 — [DEPLOY] Hunt capture gallery to Jetson
- **[DEPLOY]** `./run-ai.sh --restart` → soft restart hit Sniper CSI PHY dead → auto-reboot; cameras healthy after.
- **[VERIFY]** Dashboard 200; hunt `HUNTING`+armed; `/api/hunt/captures` returning items; `HuntCapture` saving rejects to `hunt_captures/`.

## 2026-07-27 — [BUG FIX] Hunt captures overloaded Jetson (stuck feeds)
- **[ROOT CAUSE]** Reject storm (300+) wrote dual MP4 + 8 JPEGs ~every 200ms; app.py ~4.6GB RAM / 150%+ CPU; gallery polled 50 thumbs/4s; GStreamer `gst_sample_get_caps() NULL`; OpenCV `mp4v` unplayable in browsers.
- **[OPS]** Paused hunt via `/api/hunt/stop` before fix.
- **[SPEC]** `SW-001` §2.14 → v5.3: **stills only**, retain **5**, **8s cooldown**, no frame ring, Control-tab-only gallery poll.
- **[CODE]** Rewrote `hunt_capture.py` lightweight; UI stops polling off Control tab; no `<video>`.
- **[DEPLOY]** Wipe `hunt_captures/`, `./run-ai.sh` full reboot.

## 2026-07-27 — [FEATURE] Hunt track + online boresight + hit verify
- **[SPEC]** `SW-001` §2.13 v5.4: Scout dead-zone; continuous track for flying bugs; Sniper YOLO closed-loop center; HitDetector splash confirm; EMA Scout↔Sniper boresight from insect/splash error.
- **[CODE]** `boresight.py`; `scout_vision` `dead_zone_frac`; rewrite `hunt_controller` track/fire/hit; captures store `hit_confirmed`/`hit_px`.
- **[UI]** Hunt Attempts show HIT/MISS.
- **[DEPLOY]** Full reboot; verified targets off-center (e.g. 1265,292) not stuck at 640,360; `boresight` in `/api/hunt/status`.

## 2026-07-28 — [DIAGRAM] Sniper IR-cut wiring (CSI alone insufficient)
- **[FINDING]** Motorized IR-cut is not carried on CSI→HDMI; Sniper currently CSI-only.
- **[DIAGRAM]** `diagrams/wire_13_sniper_ircut.drawio` — Modes A–D; Mode B = IR+GND umbilical → BCM22/T15.
- **[SPEC]** HW-001 §2 updated; `camera_optics` points at WIRE 13.

## 2026-07-28 — [DOCS/SW] Scout vs Sniper IR-cut profiles (parts.csv)
- **[FINDING]** Scout = permanent NoIR; Sniper = motorized IR-cut — only comments before; **not software-switched**.
- **[CODE]** `camera_optics.py`; `/api/status` → `cameras_optics`; camera card titles updated.
- **[SPEC]** HW-001 §2 table + SW-001 §2.12c v5.13.

## 2026-07-28 — [DOCS/SW] IR always-on awareness in live dashboard
- **[AS-BUILT]** Univivi 850nm hardwired to system 12V — ON whenever powered (not GPIO).
- **[CODE]** `ir_controller.get_illumination_status()`; `app.py` `/api/status` → `ir`; header pill **IR always on**.
- **[SPEC]** SW-001 §2.12b v5.12.

## 2026-07-28 — [FIX] Hit verdict: drop PSI; splash optional + gravity-aware
- **[FEEDBACK]** PSI flutters → not a hit signal. Splash often invisible at range/angle.
- **[CODE]** `hit_verdict` v5.11: core = lock + traj_corridor + ballistic (≥2/3 HIT). Splash N/A if missing; if present must match gravity-expected impact or veto HIT.
- **[SPEC]** SW-001 §2.13 v5.11.

## 2026-07-28 — [FEATURE] Multi-signal hit verdict (≥3/4)
- **[SPEC]** SW-001 §2.13 v5.10: HIT only if ≥3 of psi_drop / insect_locked / traj_through_bbox / splash_near_bbox.
- **[CODE]** `hit_verdict.py`; hunt fire uses hardened HitDetector + `evaluate_hit`; gallery shows score + signal row.
- **[NOTE]** PROBABLE = 2/4; dry/false splash alone cannot confirm HIT.

## 2026-07-28 — [FIX] Auto-cal false hits on dry fire
- **[ROOT]** HitDetector treated AE/noise as splash; Scout px vs Sniper hit; retries lowered threshold; 2/10 “hits” polluted offset.
- **[CODE]** Noise floor ×3, AE-stable before, circularity/area, multi-frame consensus, aim=Sniper crosshair, median offset, reject save unless ≥3 hits; no loosened retry.
- **[UI]** Calibration copy: dry ≈0 hits; rejected keeps previous offset.
- **[SPEC]** SW-001 §6 v5.9.

## 2026-07-27 — [CONFIG] Field start: 15 PSI / 10 ms pulse; cal=hunt setpoint
- **[DEFAULTS]** `target_psi=15`, `default_pulse_ms=10` (settings_store + AccumulatorManager).
- **[SPEC]** SW-001 v5.8: flight lead + linear drop are partial; cal must match hunt PSI/pulse; multi-PSI cal deferred.
- **[CODE]** ToF exit velocity scales with √(psi/15); AutoCal status shows PSI+ms.

## 2026-07-27 — [FEATURE] Hunt gallery: 10 recent + 100 insects + water trajectory
- **[SPEC]** SW-001 §2.14 v5.7: dual retention (recent 10 any / insects 100); Sniper burst contact-sheet `trajectory.jpg` during fire + HitDetector splash.
- **[CODE]** `hunt_capture` dual index; insect detections skip cooldown; fire-path traj burst in `hunt_controller`.
- **[UI]** Control-tab Recent 10 / Insects 100 toggles; trajectory strip in detail.
- **[RATIONALE]** Best trajectory check without MP4/high-speed cam: stills strip of the jet + splash marker vs insect bbox.
- **[OPS]** Jetson unreachable at deploy time — run `./run-ai.sh` when back online.

## 2026-07-27 — [FIX] Align Scout↔Gimbal UI + hunt follow scale
- **[FIX]** Align ORB is **single-pass at home** only (2nd pass after large yaw moved Sniper off shared scene and inflated bias).
- **[UX]** Align was never in the GUI (only background boresight). Added Control-tab **Align Scout↔Gimbal** card + `POST /api/hunt/align` (ORB match at home → mount bias).
- **[CODE]** `boresight.estimate_from_frames`; hunt `fov_scale` default 1.35 for snappier Scout→gimbal follow; align pause/resume hunt + persist mount.
- **[FIX]** ORB uses Lowe+RANSAC homography + **18° reject cap**; reset Jetson mount bias to 0 after flaky earlier align.
- **[NOTE]** Hunt pitch range = Scout FOV cone (~±24° × scale), not full mechanical cal sweep — explained in UI.
- **[SPEC]** SW-001 §2.13 v5.6.

## 2026-07-27 — [FIX] Scout↔Sniper aim geometry (upside-down + 30° low)
- **[ROOT CAUSE]** Hunt track applied nozzle `calibration.offset_pitch≈+29°` to Scout→gimbal camera aim → systematically ~30° too low; Sniper physically upside-down; boresight was overwriting nozzle cal.
- **[CODE]** `vision.CameraStream.rotate_180` for Sniper; hunt track uses mount/boresight only; **nozzle cal on FIRE only**; auto-save mount bias to `settings.hunt.sniper_mount_*`.
- **[SPEC]** SW-001 §2.13 v5.5.

## 2026-07-25 — [SW] Option B Pico W solenoid driver live
- **[SPEC]** `SW-001` §2.7 / `HW-001` §5.4: Pico CDC protocol `FIRE`/`OPEN`/`CLOSE`/`PING`; default `solenoid_driver=pico`.
- **[FW]** `firmware/pico_solenoid/main.py` — MicroPython GP15 timer.
- **[SW]** `pico_solenoid.py` — Jetson USB CDC client (auto-detect ttyACM/by-id).
- **[SW]** `hardware.RelayController` — pulses via Pico `FIRE <ms>`; legacy module path retained as `legacy_module`.
- **[SETTINGS]** `settings_store` defaults: `solenoid_driver=pico`, `pico_port=""`, `pico_baud=115200`; `app.apply_settings_to_runtime` syncs driver.
- **[DIAGRAM]** Software note on `eco004_mosfet_module_option.drawio` updated to LIVE Pico FIRE path.

## 2026-07-24 — [DIAGRAM/SPEC] Option B Rev O install guide (Pico + IRLB8721 + 1N5408)
- **[PROCUREMENT]** Pico W, diode kit, USB-A↔Micro-B marked **have** in `parts.csv` (received).
- **[SPEC]** `HW-001` §5.4 Rev O = production Option B; §5.4b/§5.5 module+CH2 marked legacy. `SW-001` §2.7 notes hardware cutover pending Pico CDC driver (live code still T36 SIG + T29/CH2).
- **[DIAGRAM]** Rewrote `diagrams/eco004_mosfet_module_option.drawio` — wire-move guide: remove dual-MOS module / T36 / T29–CH2 from valve; add Pico USB+GP15 → 220Ω → IRLB8721 G, 10k G→GND, S→GND, D←solenoid(−), +12V fused→solenoid(+), 1N5408 across coil (band→+). Includes pre-wire FET Ω/diode health table. **No 2N3904** on this path.
- **[SOFTWARE CHECK]** Confirmed `hardware.py`: `RELAY_SOL12V_PIN=5` (CH2), `SOLENOID_LINE_NAME=PR.05` (T36). Click Test will not drive Option B until Pico firmware/driver ships.

## 2026-07-27 — [LICENSE] Source-available PolyForm Noncommercial
- **[LICENSE]** Added repo-root `LICENSE` (PolyForm Noncommercial 1.0.0) with Required Notice for Salman Abbas Naqvi.
- **[DOCS]** `COMMERCIAL.md` — commercial use requires negotiated license via https://salmannaqvi.com/centered-heading-with-contact-form/
- **[DOCS]** README license section: personal/home only; not positioned as open source.
- **[SCOPE]** Applies to entire repo (software, firmware, hardware designs, diagrams, docs).

## 2026-07-28 — [FINDING] Sniper = UC-350 Rev.C (photos)
- **[FINDING]** Back pads GND/IR/SCL/SDA/FSTROBE/GP0/GND/3V3; red/black = local IR-cut motor (not laser); LDR present → Mode A as-built.
- **[DIAGRAM]** Updated `diagrams/wire_13_sniper_ircut.drawio` to UC-350-specific Mode A–D + Mode B tap points.
- **[SPEC]** HW-001 §2 Sniper row + IR-cut connectivity; `camera_optics` pcb/ldr fields.

## 2026-07-28 — [DECISION] Sniper IR-cut Mode A (LDR auto)
- **[DECISION]** Leave UC-350 as Mode A — LDR working as expected; no GPIO/umbilical IR-cut wires.
- **[SPEC]** HW-001 §2 + SW-001 §2.12c; `camera_optics`/`ir_controller` note Mode A verified; Mode B deferred.
- **[DIAGRAM]** wire_13 footer → Mode A chosen.

## 2026-07-28 — [DEPLOY] Mode A optics + pending hunt/hit code → Jetson reboot
- **[DEPLOY]** `./run-ai.sh` → 192.168.0.196; dashboard HTTP 200 after ~70s.
- **[VERIFY]** `/api/status` ir/cameras_optics show Sniper Mode A LDR auto (verified).

## 2026-07-28 — [PROCESS] Enforce AGENTS.md commit-every-step
- **[PROCESS]** User: always follow AGENTS.md — commit on every change/discovery/deploy; catch up uncommitted work.
- **[RULE]** `.cursor/rules/agents-commit-every-step.mdc` (alwaysApply) — overrides ask-before-commit for this repo.

## 2026-07-28 — [PROCESS] Commit and push every step
- **[PROCESS]** User: commit **and push** every change/discovery/deploy.
- **[RULE]** `.cursor/rules/agents-commit-every-step.mdc` updated — push after each commit (no force).
- **[RULE]** Cursor rule now requires **push after every commit** (not ask-first).

## 2026-07-28 — [PROCESS] agents.md commit+push every step
- **[PROCESS]** `agents.md` Spec-Driven rule 3 → **Commit and Push Every Step** (discoveries included; no force-push).

## 2026-07-28 — [BUG FIX] Pulse setting reverted to 100ms on every boot
- **[ROOT CAUSE]** `settings_store._migrate_legacy` forced `default_pulse_ms ≤ 25` → **100** on every load, undoing Save Permanent after reboot.
- **[FIX]** Remove that migration; allow **1–500 ms** on Settings slider (step 1); sync `operational_pulse` with standard pulse; Save All prefers std pulse.
- **[SPEC]** SW-001 §2.7: allowed 1–2000 ms; no auto-bump to 100 ms.
- **[DEPLOY]** `./run-ai.sh --restart` → auto full reboot for CSI; verified `default_pulse_ms=10` persists after boot.

## 2026-07-28 — [TUNING] Outdoor live-test: temper Scout + gimbal
- **[OPS]** First outdoor water live test — too many motion tracks / gimbal thrash.
- **[LIVE]** Applied via `/api/settings` (no wait): Scout T=40 min_area=2000 dead_zone=0.25; fov_scale=1.0; servo 55°/s.
- **[CODE]** `hunt.min_speed_px_s` (default 80) gates slow blobs; factory defaults match tempered outdoor profile.
- **[SPEC]** SW-001 §2.13 outdoor-tempered defaults.
- **[DEPLOY]** Tempered outdoor profile live after restart/reboot; Scout/servo/fov applied.

## 2026-07-28 — [TROUBLESHOOT] Auto-cal misses visible wet spots on deck
- **[SYMPTOM]** Outdoor live cal: water visible in Sniper GUI + wet deck boards, but HitDetector logs `no_blob` / `low_change@0–0.85%`.
- **[TEST]** Log pattern: most frames fail `MIN_CHANGE_PCT=0.9` at `DIFF_THRESHOLD=48`; when change ~1–2.5% still `no_blob` (area/circ/aim gates).
- **[TEST]** Live Sniper noise + synthetic wet: diffuse wood stains need lower thr / smaller min area / later capture than current POST_FIRE_DELAYS≤0.70s.
- **[CONTEXT]** Pulse ~11ms; nozzle right of Sniper; large pole in FOV; wet = darkening not bright splash.
- **[NEXT]** Ask operator 10 questions before changing HitDetector.

## 2026-07-28 — [FIX] Auto-cal wet-stain detection + pulse ladder
- **[OPERATOR]** Wet = coin-size, slightly dark, low of crosshair, visible ~0.5s @ 11ms/15PSI, 1–3m; wants both sensitivity + 11/15/20/30ms escalate.
- **[CODE]** HitDetector v5.14: darkening+absdiff, lower thr/area, aim-down bias, captures 0.35–1.30s, require net darken.
- **[CODE]** AutoCal: pulse ladder 11→15→20→30ms (4 attempts); same PSI.
- **[SPEC]** SW-001 §6 updated.
- **[DEPLOY]** Wet-stain HitDetector + pulse ladder live on Jetson (reboot if CSI needed).

## 2026-07-28 — [TROUBLESHOOT] Hunt: motion yes, insect confirm/fire no (1.5h backyard)
- **[STATUS]** HUNTING+armed; detections=207, verifications=1573, rejections=207, shot_count=0, hits=0.
- **[PATTERN]** Captures almost all `verify=no_insect`. Scout *is* triggering; Sniper YOLO almost never confirms.
- **[EXCEPTION]** One `ladybug:0.84` still `rejected` — insect bbox far below crosshair; track timed out without centered fire.
- **[OFFLINE]** YOLO on recent reject stills: empty even at conf 0.15 (or tiny ladybug 0.17) — frames often lack a resolvable insect.
- **[CONTEXT]** Outdoor temper Scout min_area=2000/T=40/min_speed=80; hunt YOLO conf hard-coded **0.80**; targets often near frame edge; range ~1.7–3.3 m on 1280×720 wide FOV.
- **[NEXT]** 10 operator questions before any change.

## 2026-07-28 — [FIX] Hunt first-field: ROI zoom + lower YOLO + opportunity fire
- **[FINDING]** Operator cannot see mosquitoes on Scout/Sniper; gallery = false motion; 207 motion / 0 shots; ladybug confirmed but never centered → reject.
- **[FIX]** `hunt.yolo_conf=0.35`, `roi_zoom=2` digital center crop for YOLO, wider `center_ok_frac=0.18`, opportunity-fire after refine / end-of-track.
- **[TUNING]** Scout slightly relaxed (T=32, min_area=1200, min_speed=55) for flies/bees.
- **[SPEC]** SW-001 §2.13 updated.
- **[DEPLOY]** Hunt ROI/conf/opportunity-fire live; applied scout/hunt settings on Jetson.

## 2026-07-28 — [UI] Cal splash: bright-red diff + last-10 hit gallery
- **[UI]** HitDetector after-frame paints changed pixels **bright red** (not jet colormap).
- **[FEATURE]** `cal_hit_store.py` keeps last 10 successful before/after/diff under `cal_hits/`; Calibration tab gallery + `/api/calibration/hits`.
- **[SPEC]** SW-001 §6 gallery note.
- **[DEPLOY]** Bright-red cal diff + last-10 hit gallery live on Jetson.

## 2026-07-28 — [TROUBLESHOOT] Auto-cal hit pixel wrong → wild offsets
- **[OPERATOR]** Diff red overlay + HIT marker often not on real wet spot (e.g. Point 8 HIT 647,643 vs actual impact in pink box).
- **[LOGS]** Latest run 8 “hits”: per-point offsets pitch ≈ −22…+19°, yaw ≈ −30…+29° — impossible for rigid nozzle↔camera; median saved P=10.03° Y=2.28°.
- **[PATTERN]** Hit pixels scatter to frame edges/corners (29,1237,905,y=33/643); AIM_DOWN_BIAS + largest darkening blob ≠ water stain; board/shadow noise painted red.
- **[CONTEXT]** Operator: mount rigid; cal purpose mainly ideal PSI/pulse for insects, not wildly varying geometric offset.
- **[NEXT]** 10 questions before fix.

## 2026-07-28 — [FIX] Auto-cal: near-crosshair hits + reject wild offsets
- **[OPERATOR]** Answers: HIT marker wrong most of the time; real wet = fresh dark stain; fully auto reject bad HITs; offset nearly fixed; 30 ms clearest; mixed surfaces; longer cal OK.
- **[ROOT]** AIM_DOWN_BIAS + largest-darkening score locked onto board/shadow noise far from crosshair → ±20–30° junk offsets.
- **[FIX]** HitDetector: ROI-only change% near crosshair; score proximity+darken; bias 0.03; `MAX_AIM_DIST≈0.14`.
- **[FIX]** CalibrationTable: reject |offset|>8°; inlier median (±5°); clamp global ±8°.
- **[FIX]** Auto-cal pulse ladder **30/30/35/40 ms**; rejected outliers retry (no gallery pollute).
- **[SPEC]** SW-001 §6 → v5.15.

## 2026-07-28 — [DEPLOY] Near-crosshair auto-cal fix live
- **[DEPLOY]** `calibration_engine.py` v5.15 (near-crosshair + |offset|>8° reject + 30ms pulse) live after soft-restart→auto-reboot; Scout+Sniper healthy.

## 2026-07-28 — [FIX] Auto-cal: persistent darken contrast (false HIT near crosshair)
- **[OPERATOR]** Point 10 HIT (744,417) still false; pink circle = real wet further right.
- **[ROOT]** Noise floor often 9–18% but min_change capped at 2.5% → accepted AE noise near aim; real wet @~(865,307) (~11° yaw) outside tight ROI / outscored.
- **[FIX]** HitDetector v5.16: persistent darken votes, contrast score, edge margin, refuse floor>3.5%, wider ±14° search; offset gate ±15°.
- **[VERIFY]** Offline on Point10 gallery: new HIT (865,307) matches true wet (was 744,417).
- **[SPEC]** SW-001 §6 → v5.16.

## 2026-07-28 — [DEPLOY] Persistent-darken HitDetector v5.16 live
- **[DEPLOY]** Auto-reboot after soft restart; Scout+Sniper healthy. Expect fewer accepted hits, HIT nearer real wet, skips when scene unstable.

## 2026-07-28 — [FIX] EST timezone + HitDetector v5.17 (operator labels)
- **[OPS]** Jetson timezone Asia/Shanghai → **America/New_York** (EDT). `timeutil.py`, `sentry.service` TZ, deploy.sh timedatectl, app `ensure_process_tz`, `/api/status` time_et. Gallery shows ET.
- **[OPERATOR]** GOOD P7 (772,406) tarp accurate; BAD P6 (739,320) foliage; BAD (471,495) deck AE; BAD P7 (832,474) should be lower.
- **[FIX]** HitDetector v5.17: refuse foliage/wind ROI, top-exclude canopy, larger puddles, gravity+darken score, down-weight blue furniture. Offline: (471,495)→(713,599); (832,474)→(776,586); P10 wet still (865,307).
- **[SPEC]** SW-001 §1 timezone + §6 v5.17.

## 2026-07-28 — [DEPLOY] EST timezone + HitDetector v5.17 live
- **[DEPLOY]** America/New_York confirmed (EDT); `/api/status` exposes time_et; Scout+Sniper healthy after auto-reboot.
