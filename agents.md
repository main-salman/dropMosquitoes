# Software Modules (Agents)

The system is divided into four asynchronous agents communicating via thread-safe queues.

> **Spec Reference:** All agent implementations MUST conform to [SW-001](docs/specs/SW-001-software-spec.md).
> Any deviation from the spec requires updating the spec FIRST, then the code.

1. **ScoutAgent (`scout_vision.py`):**
   - Reads `/dev/video0` via GStreamer `nvarguscamerasrc sensor-id=0`.
   - Uses OpenCV Background Subtraction (MOG2).
   - Loads tuning parameters from `settings.json` (`scout` section); falls back to legacy `scout_config.json`.
   - Outputs `(x, y)` pixel coordinates + `(vx, vy)` velocity vector of the highest-confidence moving blob.
   - **Mount: FIXED to IP67 enclosure (does NOT ride on gimbal).**
   
2. **TurretAgent (`gimbal_controller.py`):**
   - Translates Cartesian pixel coordinates into Pitch/Yaw degree commands.
   - Enforces the -80/+80 Yaw boundary.
   - Commands the Storm32 gimbal via binary o323BGC packets over UART (/dev/ttyTHS1 or /dev/ttyTHS0).
   
3. **SniperAgent (`sniper_vision.py`):**
   - Reads `/dev/video1` via GStreamer `nvarguscamerasrc sensor-id=1`.
   - Runs YOLOv8 TensorRT engine for object classification.
   - Returns TRUE if `class == 'Mosquito'` AND `confidence > 0.80`.
   - **Mount: ON GIMBAL PAYLOAD (moves with turret).**
   
4. **TriggerAgent (`weapon_system.py`):**
   - If `target_locked == True` AND `human_in_frame == False`.
   - Actuates GPIO BCM 17 (IDC40P Terminal 11) `HIGH` for 400ms (Stream-and-Sweep), then `LOW`.
   - Supports non-blocking `fire_sweep()` for parallel pump+gimbal operation.
   - **Safety: MUST comply with [SAFE-001](docs/specs/SAFE-001-safety-spec.md).**

---

## Spec-Driven Development Rules

1. **Spec Before Code:** No new agent or feature may be implemented without a corresponding spec in `docs/specs/`. Create or update the spec first, then implement.
2. **History Logging:** Every code change, architectural decision, procurement action, discovery, or **troubleshooting step** MUST be appended to `docs/HISTORY.md` with a `[CATEGORY]` tag and timestamp. Mirror the same entry in `history.txt` (do not delete prior `history.txt` content).
3. **Commit and Push Every Step:** After each discrete step (spec update, feature, bug fix, finding, diagram, deploy-related ops note), create a **git commit** and **`git push`** to the tracked remote. Do not leave multi-step work uncommitted or unpushed across sessions. Prefer small commits that match HISTORY entries. Never force-push to `main`/`master`.
4. **Spec Traceability:** All code files should reference their governing spec in a docstring header (e.g., `# Implements: SW-001 §2.1`).
5. **No Dummy Data:** NEVER create dummy data (videos, datasets, etc.) for testing or training. Always ask the user for real data if needed.


# Jetson Hardware Setup & TensorRT Export Guide

> **Spec Reference:** See [HW-001](docs/specs/HW-001-hardware-spec.md) for full hardware details.
> All hardware changes MUST update HW-001 first, then this file.
> All actions MUST be logged in [docs/HISTORY.md](docs/HISTORY.md).

This file contains manual terminal commands required to prep the Jetson environment before running the Python architecture.

## 1. Maximize Jetson Performance
`sudo nvpmodel -m 0`
`sudo jetson_clocks`

## 2. Install Ultralytics with TensorRT Support
`pip install ultralytics onnx`

## 3. The YOLOv8 TensorRT Export Pipeline
Run this python script once to convert the standard YOLOv8 model into a high-speed `.engine` file optimized for the Orin Nano.

```python
from ultralytics import YOLO

# Load the base model (Nano for maximum FPS)
model = YOLO("yolov8n.pt") 

# Export to TensorRT. 
# half=True sets FP16 precision, which doubles the speed on Orin Nano.
model.export(format="engine", half=True, workspace=4, dynamic=False)
```

## 4. Verify Camera Interfaces
```bash
# Scout camera (IMX219 NoIR, FIXED to enclosure, MIPI Port 0)
v4l2-ctl --list-devices
# Should show /dev/video0

# Sniper camera (IMX219 NoIR, ON GIMBAL, MIPI Port 1)
# Should show /dev/video1
```

## 5. Test GPIO Relay
```python
import Jetson.GPIO as GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(17, GPIO.OUT)     # BCM 17 = Pin 11 = IDC40P Terminal 11
GPIO.output(17, GPIO.HIGH)   # Relay CH1 closes → Pump fires
import time; time.sleep(0.3)
GPIO.output(17, GPIO.LOW)    # Relay CH1 opens → Pump stops
GPIO.cleanup()
```

## 6. AI Agent Guidelines
- **No Dummy Data:** NEVER create dummy data (videos, datasets, etc.) for testing or training. Always ask the user for real data if needed.