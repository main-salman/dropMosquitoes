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
