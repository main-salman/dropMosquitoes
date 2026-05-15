# Sentry Control Center — User Guide

The **Sentry Control Center** is a standalone Streamlit application designed for Windows 10/11 environments with an NVIDIA RTX 3070. It provides a dual-architecture interface for tuning the Scout (OpenCV) motion tracker and training the Sniper (YOLOv8) model.

## Installation

1. Ensure you have Python 3.10+ installed.
2. **Crucial:** Install the CUDA-enabled version of PyTorch first. This ensures the YOLO training leverages your RTX 3070 to prevent slow CPU training.
   ```bash
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
   # Or cu121 if you have CUDA 12.1 installed
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

1. **Upload Video:** Click "Browse files" and upload a short `.mp4` or `.avi` clip of a mosquito flying in your target environment.
2. **Tune Threshold:** Adjust the `Threshold` slider. A higher value filters out background noise but might miss faint insect movement.
3. **Tune Min Contour Area:** Adjust the `Min Contour Area` to reject small dust particles or sensor noise while keeping the insect bounding box active.
4. **Export Settings:** Note down the optimal `Threshold` and `Min Area` values. You will input these into the Jetson's `scout_config.json` file.

---

## Tab 2: Sniper Trainer (YOLOv8)

Use this tab to retrain the neural network on your custom dataset without crashing the Streamlit UI or running out of memory (OOM) on your 8GB GPU.

1. **Dataset Path:** Provide the absolute path to your `data.yaml` file (e.g., exported from Roboflow).
2. **Base Model:** Select `yolov8n.pt` (Nano) for the fastest inference on Jetson, or `yolov8s.pt` (Small) for slightly better accuracy.
3. **Hyperparameters:**
   - **Batch Size:** Hard-capped at 32. Do not exceed 16-32 to prevent CUDA OOM errors on the RTX 3070 (8GB VRAM).
   - **Image Size:** Keep at 640 for standard performance, or reduce to 320 for speed.
4. **Start Training:** Click the button. The YOLO training process will spawn in a background thread, and live logs will stream directly into the dark terminal window in the UI. 

> **Note:** The Streamlit UI will remain responsive during the hours-long training process. Once training completes, the optimized weights will be saved in your active directory under `runs/detect/train/weights/best.pt`. Copy this file to your Jetson deployment.
