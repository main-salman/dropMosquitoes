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
