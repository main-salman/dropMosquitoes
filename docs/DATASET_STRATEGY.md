# Dataset Strategy — Multi-Bug Target Classification Model

> **Spec Reference:** SW-001 §7.2 — Sniper Training Pipeline (YOLOv8 — GPU-Intensive)

## The Problem

YOLOv8 requires high-quality annotated images to learn the features of different insects. Under the Sentry Turret v5.0 software architecture, we have expanded our target capabilities from a basic single-class mosquito detector to a comprehensive **15-class backyard insect classifier**. 

Without a properly formatted local dataset, the precision Classifier (`SniperAgent`) cannot run inference or verify targets—it will fail to identify any backyard pests.

---

## 🎯 Primary Dataset: Roboflow `tiger-emltm/insects-9yf6s` (v2)

To satisfy the multi-bug sentinel upgrade, we have adopted the public domain **15-Class Insect Dataset** from Roboflow Universe. This provides a robust base of pre-labeled insect images captured from overhead, side, and natural flight angles.

### Labeled Classes (15 Total):
1. `spider`
2. `bees`
3. `butterfly`
4. `mantis`
5. `ant`
6. `beetle`
7. `caterpillar`
8. `centipedes`
9. `cockroach`
10. `dragonfly`
11. `fly`
12. `grasshopper`
13. `ladybug`
14. `mosquito`
15. `wasp`

---

## 🛠️ Automated Dataset Ingestion Pipeline

Instead of manual downloading and directory structure setup, the Sentry Control Center provides an automated dataset preparation utility:

```
[tools/sentry_control_center/download_dataset.py]
```

This utility integrates with Roboflow Universe to handle dataset downloading, extraction, path resolution, and `data.yaml` formatting automatically.

### Step 1: Secure API Keys
Add your Roboflow API key to the local `.env` file (ensure it is ignored by Git in `.gitignore`):
```bash
ROBOFLOW_API_KEY="your_api_key_here"
```

### Step 2: Ingest the Dataset
Run the download script from the project root:
```bash
python tools/sentry_control_center/download_dataset.py
```
This extracts the dataset cleanly into:
`tools/sentry_control_center/dataset/insects/`

---

## 🏋️ Training Protocol (Workstation)

Training is highly compute-intensive and must be run on a dedicated workstation (e.g. RTX 3070 8GB or Apple Silicon M4 Pro) using the Sentry Control Center CLI:

```bash
python tools/sentry_control_center/app.py --train-sniper --data tools/sentry_control_center/dataset/insects/data.yaml --epochs 100
```

### Recommended Configurations:
* **Model Base:** `yolov8n.pt` (Nano weights for minimal edge latency)
* **Epochs:** `100`
* **Batch Size:** `16` (Adjustable based on GPU VRAM availability)
* **Image Size:** `640`

Once training finishes successfully, the CLI runner automatically copies the output weights (`runs/detect/train/weights/best.pt`) to:
`models/trained/best.pt`

---

## 🚀 Edge Deployment Pipeline (Jetson Orin Nano)

### Step 1: Sync Files to the Jetson
Run the deployment script from your workstation:
```bash
./deploy.sh
```
This automatically syncs the repository and runs the **model alignment hook on-device**, copying the new weights (`models/trained/best.pt`) to `best.pt` (for the orchestrator daemon) and `models/yolov8n.pt` (for the MJPEG dashboard).

### Step 2: Compile High-Speed TensorRT Engine
On the Jetson, convert the `.pt` weights to a high-speed FP16 `.engine` file to double execution speed:
```python
from ultralytics import YOLO

# 1. Main Loop Sniper engine
model = YOLO("best.pt")
model.export(format="engine", half=True, workspace=4)

# 2. Visualizer Dashboard engine
model_vis = YOLO("models/yolov8n.pt")
model_vis.export(format="engine", half=True, workspace=4)
```

The `SniperVision` class will automatically detect the presence of `best.engine` and run ultra-low latency FP16 hardware-accelerated inference.

---

## 🔄 Iterative Field Tuning

To keep the model robust against environmental changes:
1. Review the Flask logging systems (`engagements.jsonl`) to identify false positives or missed targets.
2. Isolate captured video frames of missed targets.
3. Upload and label them in your Roboflow workspace.
4. Run the ingestion, training, and deployment pipeline again to compile an updated `best.pt` model.
