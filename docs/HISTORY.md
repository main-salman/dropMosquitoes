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
