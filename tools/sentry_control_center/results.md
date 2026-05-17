# Sentry Control Center - YOLOv8 Training Results

## Overview
We've successfully updated the `app.py` script to support CLI training. The script dynamically detects hardware acceleration (falling back to Apple Silicon MPS if available) and can be invoked directly from the terminal without the Streamlit UI.

**Command Executed:**
```bash
tools/sentry_control_center/venv/bin/python app.py --train-sniper \
    --data /Users/salman/Documents/dropMosquitoes/tools/sentry_control_center/dataset/data.yaml \
    --epochs 5 \
    --batch 16
```

## Environment & Hardware
- **Engine Detected:** Apple Silicon MPS (M4 Pro)
- **Model:** YOLOv8 Nano (`yolov8n.pt`)
- **Image Size:** 640x640

## Dataset
- **Location:** `tools/sentry_control_center/dataset/`
- **Classes:**
  - `0`: mosquito
  - `1`: fly
- **Distribution:**
  - **Validation:** 353 images

## Training Performance
After 5 epochs of training, the model achieved the following performance on the validation set:

| Class | Instances | Precision (P) | Recall (R) | mAP50 | mAP50-95 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **all** | 271 | 0.932 | 0.831 | **0.91** | 0.603 |
| **mosquito** | 122 | 0.99 | 0.843 | **0.972** | 0.667 |
| **fly** | 149 | 0.873 | 0.819 | **0.847** | 0.539 |

### Inference Speed
- **Pre-process:** 0.1ms per image
- **Inference:** 5.9ms per image
- **Post-process:** 2.4ms per image

## Output & Deployment
- The raw YOLO output is saved in `tools/sentry_control_center/runs/detect/train/`
- The `best.pt` weights have been successfully auto-copied to the deployment folder:
  `models/trained/best.pt`

The model is now fully ready for the deployment pipeline! You can run the `deploy.sh` script to push this newly trained model to the Jetson Orin Nano payload.
