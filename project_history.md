# Project History — Git Push Log

> Every change pushed to GitHub is summarized here per Rule 12 in `rules.md`.
> Format: `[COMMIT_HASH] YYYY-MM-DD — Summary`

---

## 2026-05-14

### `fe8c087` — Initial commit: Sniper Messy Mortar
- Flask server (`app.py`) with MJPEG streams, REST API, test runner
- Hardware abstraction (`hardware.py`) with GPIO relay + Storm32 gimbal control
- Vision pipeline (`vision.py`) with GStreamer + YOLOv8 TensorRT
- Web dashboard (`templates/index.html`) with Control + Test Suite tabs
- 7 test suites in `tests/` (smoke, camera, relay, serial, yolo, safety, accuracy — 112 tests total)
- Spec-driven docs: SYS-001, HW-001, SW-001, SAFE-001, TEST-001
- 31 technical illustrations in `diagrams/images/`
- Lifecycle scripts: `run-ai.sh`, `run-no-ai.sh`, `stop.sh`
- `.gitignore` for Python, IDE, runtime, and TensorRT files

### `25a8bc8` — Add missing parts list
- Created `moreparts.csv` with 17 components missing from original BOM
- Identified via cross-referencing technical illustrations against `parts.csv`
- Categories: weatherproofing, mounting hardware, power, fluid, tools

### `61a4417` — Fix moreparts.csv links and power module
- Replaced all fabricated Amazon ASIN URLs with working `amazon.ca/s?k=` search URLs
- Replaced USB-C PD Trigger Module (wrong part) with Male DC Pigtail (5.5mm x 2.5mm)
- Correction: Yahboom Jetson uses DC barrel jack, not USB-C PD

### `7db6016` — User CSV format cleanup
- User converted `moreparts.csv` from tab-delimited to comma-delimited
- Removed outdoor extension cord and deburring tool entries

### `a379d0a` — Add auto-push rule and project history
- Added Rule 12 to `rules.md`: all changes must be committed, pushed, and logged
- Created this `project_history.md` file with retroactive entries for all prior commits

### `7db6016` — User CSV format cleanup (pushed retroactively)
- User converted `moreparts.csv` from tab-delimited to comma-delimited
- Removed outdoor extension cord and deburring tool entries

### (this commit) — 3D printable parts + reference images
- Created `3d_prints/` folder with 5 OpenSCAD parametric models:
  - `01_nozzle_bracket.scad` — Gimbal nozzle mount (replaces $5 bracket)
  - `02_scout_camera_mount.scad` — Scout camera plate (replaces $12 standoff kit)
  - `03_post_clamp.scad` — Two-piece pole clamp (replaces $8 U-bolts)
  - `04_cable_clips.scad` — Snap-on cable clips (replaces $9 zip tie mounts)
  - `05_lens_retainer.scad` — Lens window retainer ring (new part)
- Generated 5 dimensioned 3D reference renders (PNG)
- Created `PRINT_GUIDE.md` with materials, settings, and assembly instructions
- Net savings: ~$34 CAD replaced by ~$3 filament

### `840b45d` — Merge moreparts into master BOM
- Consolidated moreparts.csv entries into parts.csv
- Added TF-Luna LiDAR ($37) to BOM
- Updated total to $1523 CAD

### (this commit) — V2 Software Stack: LiDAR + Ballistic Math + Dashboard
- **hardware.py:** Added `LiDARController` (I2C TF-Luna driver, 100Hz background polling, stub mode)
- **hardware.py:** Added `compute_ballistic_offset()` — overhead parabolic drop correction (gravity-assisted, downward firing from 8-10ft)
- **app.py:** Added `/api/lidar` endpoint, enhanced `/api/gimbal/click` with ballistic correction, LiDAR in `/api/status`
- **templates/index.html:** New telemetry panel (live LiDAR distance, ballistic offset, pitch/yaw), click-to-aim toast notifications
- **vision.py:** Added `get_resolution()` helper to CameraStream
- **HW-001:** Added §6 (TF-Luna LiDAR spec), bumped to v3.0
- **SW-001:** Added §2.5 (LiDAR polling), §2.6 (ballistic engine), updated §4 (overhead physics model), bumped to v2.0

## 2026-05-15

### `c0245b3` — Calibration tab + calibration API endpoints
- **templates/index.html:** New Calibration tab with 4 interactive wizards (LiDAR, gimbal, ballistic, log)
- **app.py:** 8 new `/api/calibration/*` endpoints for calibration workflow

### `0083616` — Detailed wiring diagrams + 11 new reference images
- **diagrams/:** 12 new draw.io wiring diagrams (wire_01 through wire_12)
- **diagrams/images/:** 11 new technical reference images (overhead mount, LiDAR wiring, UART, etc.)

### `155d6e0` — SW-001 §2.7: Predictive Lead Engine spec
- **SW-001:** Added §2.7 (velocity vectoring, ToF lead, parabolic drop sequence)

### Predictive Lead Engine — code implementation
- **vision.py:** Added `VelocityTracker` class (SW-001 §2.7.1) — EMA-based centroid tracking, pixel-to-angular velocity conversion
- **hardware.py:** Added `compute_predictive_lead()` (SW-001 §2.7.2-2.7.3) — 3-stage pipeline: raw angles → velocity lead → gravity drop
- **app.py:** Updated `/api/gimbal/click` to use full 3-stage predictive lead pipeline; added `/api/velocity`, `/api/velocity/update`, `/api/velocity/reset` endpoints; instantiated `VelocityTracker`

### ECO-2026-001: 1N4007 Flyback Diode (Critical Safety Patch)
- **HW-001:** Added §5.1 — Critical Electrical Safety section with flyback diode wiring instructions, bumped to v3.1
- **parts.csv:** Updated flyback diode BOM entry with detailed notes
- **diagrams/wire_03_relay_pump.drawio:** Rebuilt with 1N4007 diode in reverse-bias, CRITICAL callout
- **diagrams/images/flyback_diode_wiring.png:** New wiring reference image with clamped-vs-unclamped spike comparison
- **Cursor extension:** Installed `hediet.vscode-drawio` for native draw.io viewing

## 2026-05-17

### `54cf587` — [TOOL] Add CLI support for Sentry Control Center & Anti-Dummy Data Rules
- Added argparse CLI support to `app.py` for headless execution.
- Added dynamic platform auto-detection (CUDA vs MPS).
- Added formal anti-dummy data rules to documentation.

### `b07c3c9` — [TRAINING] Automated commit: 100-Epoch YOLO Model tuned and deployed
- Automated commit from background monitoring script.
- Updates `models/trained/best.pt` with final weights.
- Appends final mAP50 precision metrics to `results.md`.

### `ff51723` — [SECURITY] Remove .env from version control, add to .gitignore, update rules
- Remediated GitGuardian SEC-001 alert for Roboflow API key.
- `git rm --cached .env` and added `*.env` to `.gitignore`.
- Added strict SECRET PROTECTION rule to `rules.md`.

### `51c38b4` — [DOCS] Add 10 creative mounting concepts with photorealistic mockups
- Created `docs/mounting_concepts/README.md`.
- Added 10 photorealistic mockups to `docs/mounting_concepts/images/`.
- Included Mermaid diagrams for Telescoping pole, Umbrella, Tripod, Gallows, Zipline, C-Stand, Deck Clamp, Speaker Stand, Rolling Base, and Tire Mount.

### (this commit) — [ARCH] Formalize Top-Hat Core Suspension Stack
- Appended the Master Blueprint for the Top-Hat Core Suspension Stack to `docs/mounting_concepts/README.md`.
- Added `top_hat_core_suspension_*.png` to `docs/mounting_concepts/images/`.
- Logged the architectural design decision to `docs/HISTORY.md` resolving the inverted gimbal clearance issue.

### (this commit) — [DOCS] Add Weatherproof Inverted Series concepts
- Added "Part 3: The Weatherproof Inverted Series" to `docs/mounting_concepts/README.md`.
- Added 2 new photorealistic mockups (`inverted_gallows_post_*.png`, `inverted_cantilever_umbrella_*.png`) to `docs/mounting_concepts/images/`.
- Logged the concept additions to `docs/HISTORY.md`.

### (this commit) — [DESIGN] Promote PA Tripod as #1 Mounting Solution
- Reordered `docs/mounting_concepts/README.md` to feature the Quick-Release PA Tripod as the absolute #1 recommended mounting solution.
- Generated and saved `tripod_top_hat_studio_*.png` to `docs/mounting_concepts/images/` showcasing the indoor office testing setup.
- Logged the portable studio-grade architecture decision to `docs/HISTORY.md`.

### (this commit) — [ARCH] Formalize Deep Bell Canopy Weather Shield
- Added "The Weather Shield Evolution: The Deep Bell Canopy" to `docs/mounting_concepts/README.md`.
- Generated and saved `deep_bell_canopy_*.png` to `docs/mounting_concepts/images/`.
- Documented how the 18" inverted planter bell protects the Storm32 gimbal from angled rain while venting heat and allowing unobstructed firing.

### (this commit) — [DOCS] Expand Deep Bell Canopy with Commercial Aesthetics
- Added 3 commercial aesthetic upgrades to `docs/mounting_concepts/README.md`: Spun Aluminum Pendant Shade, Smoked Acrylic Globe, and Gutted PTZ Housing.
- Generated and saved 2 photorealistic mockups (`stealth_industrial_pendant_*.png`, `scifi_orb_globe_*.png`) to `docs/mounting_concepts/images/`.
- Logged the aesthetic upgrades to `docs/HISTORY.md`.
