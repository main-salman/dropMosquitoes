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

### (this commit) — Add auto-push rule and project history
- Added Rule 12 to `rules.md`: all changes must be committed, pushed, and logged
- Created this `project_history.md` file with retroactive entries for all prior commits
