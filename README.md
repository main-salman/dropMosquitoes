# 🎯 Sniper Messy Mortar

An autonomous AI-powered mosquito sentry turret built on the NVIDIA Jetson Orin Nano.

## How It Works

The system uses a **"Two-Brain" dual-pipeline architecture**:

1. **The Scout** (OpenCV) — A high-speed global shutter camera (OV9281 @ 120FPS) detects motion using background subtraction. When it spots a flying insect, it hands off coordinates to the gimbal.

2. **The Sniper** (YOLOv8) — A precision RGB-IR camera (IMX219 @ 30FPS) mounted on the gimbal verifies the target using a custom-trained neural network. If it confirms "mosquito" with >80% confidence, it authorizes the shot.

3. **Stream and Sweep** — Instead of a static shot, the system fires the 12V diaphragm pump while simultaneously sweeping the gimbal along the target's predicted flight path. This creates a moving "wall of water" that intercepts the insect mid-flight. The mist is lobbed *above* the target's trajectory and falls as a wide area-of-effect cloud.

## Project Structure

```
├── main.py                  # Async orchestrator (the brain)
├── scout_vision.py          # Pipeline 1: OpenCV MOG2 motion tracking
├── sniper_vision.py         # Pipeline 2: YOLOv8 target verification
├── gimbal_controller.py     # Storm32 gimbal serial interface
├── weapon_system.py         # GPIO relay control (water pump)
├── ir_controller.py         # IR illuminator dusk/dawn automation
├── hardware.py              # LiDAR, ballistics, velocity tracking
├── phantom_ping.py          # Airburst calibration tool
├── app.py                   # Flask web dashboard (manual control)
├── deploy.sh                # Dev machine → Jetson deployment
├── sentry.service           # Systemd auto-start on boot
├── scout_config.json        # MOG2 tuning parameters
├── docs/
│   ├── specs/               # Formal specifications (SW-001, HW-001, SAFE-001)
│   ├── HISTORY.md           # Project changelog
│   └── DATASET_STRATEGY.md  # How to build the training dataset
├── tools/
│   └── sentry_control_center/  # Windows Streamlit app for tuning & training
├── tests/                   # 112 automated tests
└── diagrams/                # Draw.io wiring & architecture diagrams
```

## Quick Start

### On Your Dev Machine (Windows/Mac)

```bash
# Tune Scout parameters & train the YOLO model
cd tools/sentry_control_center
pip install -r requirements.txt
streamlit run app.py
```

### On the Jetson

```bash
# Deploy code from dev machine
./deploy.sh <jetson-ip>

# Or manually:
pip install -r requirements.txt
python3 main.py
```

### Calibrate

```bash
# Interactive calibration — fire test shots at different offsets
python3 phantom_ping.py
```

## Documentation

| Document | Description |
|----------|-------------|
| [SW-001](docs/specs/SW-001-software-spec.md) | Software architecture & agent specifications |
| [HW-001](docs/specs/HW-001-hardware-spec.md) | Hardware BOM, wiring, GPIO pinout |
| [SAFE-001](docs/specs/SAFE-001-safety-spec.md) | Safety interlocks & operational procedures |
| [Dataset Strategy](docs/DATASET_STRATEGY.md) | How to build the mosquito training dataset |
| [Project History](docs/HISTORY.md) | Full changelog with timestamps |

## Hardware

- **Compute:** NVIDIA Jetson Orin Nano SUPER 8GB
- **Scout Camera:** OV9281 Global Shutter (120FPS, fixed mount)
- **Sniper Camera:** IMX219 NoIR with IR-Cut (on gimbal)
- **Gimbal:** Storm32 2-Axis BGC
- **Pump:** 12V micro diaphragm via Monk Makes relay
- **Nozzle:** Orbit 66190 Flex-Mist Micro Sprinkler
- **Ranging:** Benewake TF-Luna LiDAR (I2C)
