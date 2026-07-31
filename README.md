# Bug Sniper

An autonomous backyard insect turret: find the bug, aim, and hit it with a short, high-pressure water shot — built around an NVIDIA Jetson Orin Nano.

**Repo:** [github.com/main-salman/bugsniper](https://github.com/main-salman/bugsniper)  
(formerly `dropMosquitoes` — that URL still redirects)

**Blog:** [Introducing Bug Sniper!](https://salmannaqvi.com/2026/07/30/introducing-bug-sniper/)

### Watch the walkthrough

[![Watch the video](https://img.youtube.com/vi/79xdgrtEbzE/0.jpg)](https://www.youtube.com/watch?v=79xdgrtEbzE)

*[Watch on YouTube](https://www.youtube.com/watch?v=79xdgrtEbzE)* · *[Read the post](https://salmannaqvi.com/2026/07/30/introducing-bug-sniper/)*

## Intro

Bug Sniper started as a half-serious answer to “can I automate the patio slap?” and turned into a full electromechanical build: dual cameras, a pan-tilt payload, night IR, closed-loop water pressure, and a phone-friendly web dashboard. The idea is simple — Scout watches a wide scene for motion, Sniper verifies on the gimbal, then a pressure-gated solenoid fires a brief straight stream at the aim point — but making that reliable outdoors (foliage false positives, tiny targets at a few meters, plumbing that actually holds PSI) is most of the work.

This is a living DIY project, not a product. Some nights Scout chases leaves and YOLO hallucinates ladybugs on empty frames; other nights the hunt loop locks, tracks, and punches a clean shot. Hardware has migrated hard since v1 (brushless drone gimbal → geared servo turret; relay-timed pump mist → accumulator + solenoid gate). Software lives in a Flask dashboard with hunt mode, calibration, Insect Train dry-fire, and operator Correct/Wrong feedback — specs in `docs/specs/`, full story in `docs/HISTORY.md`.

Full walkthrough (architecture, plumbing, hunt loop, fails) is in the [video](https://www.youtube.com/watch?v=79xdgrtEbzE) and [blog post](https://salmannaqvi.com/2026/07/30/introducing-bug-sniper/). The sections below are the accurate snapshot of what’s running now.

## License

**Source available** under [PolyForm Noncommercial 1.0.0](LICENSE) — personal/home/hobby use only.

Commercial use of any part of this project (code, firmware, hardware designs, docs) requires a license. Contact: [salmannaqvi.com](https://salmannaqvi.com/centered-heading-with-contact-form/). See [COMMERCIAL.md](COMMERCIAL.md).

## How it works

**Two-camera handoff**

1. **Scout** (OpenCV MOG2) — Fixed Arducam NoIR IMX219 watches a wide FOV for motion (daylight pink cast is fine; night uses always-on 850 nm IR). Highest-confidence moving blob → pixel coords + velocity to the turret.
2. **Sniper** (YOLOv8 / TensorRT) — Gimbal-mounted IMX219 with motorized IR-cut (LDR auto day/night) verifies the target. Hunt gates prefer a binary “insect present” decision (domain `insect.engine` when available); multi-class Roboflow weights are legacy bootstrap, not the long-term fire model.
3. **Shot** — Pump only **charges** a pre-pressurized accumulator. A **GOODRIG NC solenoid** on the turret (0° / straight-stream nozzle mounted **directly** on the valve — no Orbit mist sprinkler) opens for a short Pico-timed pulse when PSI is at target. Gimbal may lead/sweep along the track; water is a directed stream, not a fog cloud.

**Safety (high level):** human-in-frame checks, pressure sensor fault → disarm + alarm, yaw/pitch software limits, Insect Train never fires water. See [SAFE-001](docs/specs/SAFE-001-safety-spec.md).

## Fluid path (ECO-2026-004)

```
Reservoir → diaphragm pump → check valve → accumulator tank
         → pressure tee + transducer (ADS1115)
         → GOODRIG solenoid (on turret) → 0° stream nozzle (direct mount)
```

- **Pump** charges only (solenoid closed) until target PSI.
- **Check valve** (Feelers 1/4" inline) between pump and tank holds pressure when the pump is off.
- **Accumulator** (Swess ~0.75 L) flattens cam pulsation for repeatable shots.
- **Transducer** (AUTEX 0–100 PSI) closes the pressure loop in software.
- **Solenoid pulse** via Raspberry Pi Pico W → IRLB8721 MOSFET (USB CDC from Jetson). Pump stays on Monk Makes relay CH1.

## Hardware (as-built)

| Piece | What |
|-------|------|
| Compute | Yahboom Jetson Orin Nano SUPER 8 GB (JetPack 6) |
| Scout | Arducam NoIR IMX219 — fixed to enclosure, CSI-0 |
| Sniper | Arducam IMX219 + motorized IR-cut (UC-350 Mode A LDR) — on turret, CSI-1 |
| Turret | Geared servo pan/tilt (MG996R + PCA9685) — replaced Storm32 BGC ([ADR-002](docs/specs/ADR-002-geared-turret-migration.md)) |
| Illumination | Univivi 850 nm IR flood (hardwired with system power) |
| Ranging | Benewake TF-Luna LiDAR (I2C) — **optional; currently not installed** (last unit shorted). Software reports `connected: false` / `distance_m: null` (no fake ranges). |
| Pump | 12 V diaphragm (charge only) via Monk Makes dual relay CH1 |
| Tank | Swess 0.75 L mini accumulator |
| Valve | GOODRIG 12 V NC solenoid + **0° / straight stream nozzle** (direct; **not** Orbit 66190 Flex-Mist) |
| Check | Feelers 1/4" one-way (pump → accumulator) |
| Pressure | AUTEX transducer + ADS1115 |
| Solenoid drive | Pico W + IRLB8721 (production); legacy MOSFET-module path optional |

## Software

Primary runtime is the **Flask dashboard** (`app.py` / `sentry.service`) with autonomous **HuntController**, settings in `settings.json`, calibration, diagnostics, and Insect Train. Legacy asyncio agents in `main.py` remain for reference; day-to-day ops are dashboard-first.

```
├── app.py                 # Web dashboard + hunt / cal / train APIs
├── hunt_controller.py     # Autonomous Scout → aim → verify → fire
├── scout_vision.py        # MOG2 motion (Scout)
├── sniper_vision.py       # YOLO verify helpers
├── hardware.py            # Relay, accumulator, servo turret, LiDAR, pressure
├── pico_solenoid.py       # USB CDC solenoid pulses
├── settings_store.py      # settings.json + backups
├── learning_store.py      # Operator Correct/Wrong RL
├── insect_train_store.py  # Dry-fire training samples
├── run-ai.sh / deploy.sh  # Deploy to Jetson
├── docs/specs/            # SW-001, HW-001, SAFE-001, …
├── docs/HISTORY.md        # Full changelog
├── firmware/pico_solenoid/
├── tools/sentry_control_center/  # Windows Scout tune + YOLO train
└── diagrams/              # Wiring & fluid draw.io
```

## Quick start

### Dev machine (tune / train)

```bash
cd tools/sentry_control_center
pip install -r requirements.txt
streamlit run app.py
```

### Jetson

```bash
# From your Mac/PC (preferred)
./run-ai.sh              # deploy + reboot (clean CSI)
./run-ai.sh --restart    # deploy + soft restart

# Dashboard
open http://<jetson-ip>:8000
```

Manual: `pip install -r requirements.txt`, then `python3 app.py` (or enable `sentry.service`).

## Documentation

| Document | Description |
|----------|-------------|
| [SW-001](docs/specs/SW-001-software-spec.md) | Software architecture |
| [HW-001](docs/specs/HW-001-hardware-spec.md) | Hardware, GPIO, fluid path |
| [SAFE-001](docs/specs/SAFE-001-safety-spec.md) | Safety interlocks |
| [ADR-002](docs/specs/ADR-002-geared-turret-migration.md) | Storm32 → servo turret |
| [Dataset strategy](docs/DATASET_STRATEGY.md) | Training data notes |
| [History](docs/HISTORY.md) | Changelog |

## Status (honest)

Outdoor insect ID at 1–5 m is still an active fight (pixels, FOV, domain weights). Plumbing and pressure-gated fire are much further along. See `temp/insect_id_overhaul_next_steps.html` (local) and HISTORY for the current insect-ID plan — binary detector + narrower Sniper optics, not more Roboflow species names alone.
