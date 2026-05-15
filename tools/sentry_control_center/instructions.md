# Sentry Control Center — User Guide

The **Sentry Control Center** is a standalone Streamlit application designed for Windows 10/11 environments with an NVIDIA RTX 3070. It provides a dual-architecture interface for tuning the Scout (OpenCV) motion tracker and training the Sniper (YOLOv8) model.

## Directory Structure

```
tools/sentry_control_center/
├── app.py                 # Main Streamlit application
├── requirements.txt       # Python dependencies
├── instructions.md        # This file
└── scout_config.json      # (Generated) Exported config for Jetson
```

## Installation

1. Ensure you have **Python 3.10+** installed.
2. **Crucial:** Install the CUDA-enabled version of PyTorch first. This ensures the YOLO training leverages your RTX 3070 GPU.
   ```bash
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
   # Or use cu121 if you have CUDA 12.1 installed
   ```
3. Install the remaining dependencies:
   ```bash
   cd tools/sentry_control_center
   pip install -r requirements.txt
   ```

## Launching the App

Run the following command from this directory:
```bash
streamlit run app.py
```
The application will open in your default web browser (typically at `http://localhost:8501`).

---

## Tab 1: Scout Tuner (OpenCV MOG2)

Use this tab to dial in the motion detection parameters before deploying them to the Jetson Orin Nano.

### Workflow

1. **Upload Video:** Click "Browse files" and upload a short `.mp4` or `.avi` clip of a mosquito flying in your target environment.
2. **Tune Threshold:** Adjust the `Threshold` slider (0–255). A higher value filters out background noise but might miss faint insect movement.
3. **Tune Min Contour Area:** Adjust the `Min Contour Area` slider (10–5000 pixels) to reject small dust particles or sensor noise while keeping the insect bounding box active.
4. **Watch the Preview:** The right panel shows your video with green bounding boxes drawn on detected motion. Adjust sliders until you see reliable detection with minimal false positives.
5. **Export Config:** Once satisfied, click the **💾 Export scout_config.json** button. This writes the tuned parameters to a JSON file.
6. **Deploy to Jetson:** Copy the exported `scout_config.json` to the root of your Jetson project directory (next to `main.py`). The `ScoutVision` module will automatically load it at startup.

### Exported File Format

```json
{
  "history": 500,
  "threshold": 16,
  "min_area": 500,
  "detect_shadows": false
}
```

---

## Tab 2: Sniper Trainer (YOLOv8)

Use this tab to retrain the neural network on your custom dataset without crashing the Streamlit UI or running out of memory (OOM) on your 8GB GPU.

### Workflow

1. **Dataset Path:** Provide the absolute path to your `data.yaml` file (e.g., exported from Roboflow).
2. **Base Model:** Select `yolov8n.pt` (Nano) for the fastest inference on Jetson, or `yolov8s.pt` (Small) for slightly better accuracy.
3. **Hyperparameters:**
   - **Epochs:** Default 100. Increase for better accuracy, decrease for quick experiments.
   - **Batch Size:** Hard-capped at 32. Default 16. Do **not** exceed 32 to prevent CUDA OOM errors on the RTX 3070 (8GB VRAM).
   - **Image Size:** Default 640. Reduce to 320 for faster training at the cost of detection accuracy.
4. **Start Training:** Click the **🚀 Start Training** button. The YOLO training process will spawn in a background thread, and live logs will stream directly into the terminal window in the UI.
5. **Wait for completion:** The Streamlit UI will remain responsive during the hours-long training process.
6. **Collect the model:** Once training completes, the app will display the exact path to `best.pt`. Copy this file to your Jetson deployment directory.

### Post-Training: Export to TensorRT

On the Jetson, convert the trained model to a TensorRT engine for maximum inference speed:

```python
from ultralytics import YOLO
model = YOLO("best.pt")
model.export(format="engine", half=True, workspace=4, dynamic=False)
```

This creates `best.engine` which the `SniperVision` module can load directly.
