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
# Scout camera (OV9281, FIXED to enclosure, MIPI Port 0)
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