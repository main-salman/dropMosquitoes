# Dataset Strategy — Mosquito Detection Model

> **Spec Reference:** SW-001 §7 — Training & Tuning Pipeline

## The Problem

YOLOv8 needs labeled images to learn what a mosquito looks like. Without a dataset, the Sniper pipeline cannot classify targets — it will reject everything.

## Recommended Approach: Roboflow + Transfer Learning

### Step 1: Find an Existing Dataset

Search Roboflow Universe for mosquito datasets:
- https://universe.roboflow.com/search?q=mosquito
- Look for datasets with at least 500+ images and bounding box annotations
- Prefer datasets with insects photographed from overhead angles (matching our camera perspective)

Candidate datasets:
- "Mosquito Detection" by various authors on Roboflow Universe
- "Insect Detection" datasets (broader but useful for pre-training)

### Step 2: Supplement with Your Own Data

Once the turret hardware is assembled:

1. **Capture mode:** Run the Scout camera in a recording mode that saves frames when motion is detected
2. **Label with Roboflow:** Upload captured frames to a Roboflow project, draw bounding boxes around mosquitoes
3. **Target:** Aim for 1000+ labeled images (500 minimum for decent performance)
4. **Classes:** Start simple — just two classes:
   - `mosquito` — target (fire)
   - `not_target` — moths, leaves, dust, shadows (reject)

### Step 3: Export as YOLOv8 Format

In Roboflow:
1. Generate a version with augmentations (flip, rotate, brightness)
2. Export → Format: "YOLOv8"
3. Download the dataset — it will contain a `data.yaml` file
4. Point the Sentry Control Center Trainer at this `data.yaml`

### Step 4: Train

Use `tools/sentry_control_center/app.py` Tab 2 on your Windows machine (RTX 3070).

Recommended settings for first training run:
- Model: `yolov8n.pt` (Nano — fastest inference on Jetson)
- Epochs: 100
- Batch: 16
- Image Size: 640

### Step 5: Deploy

1. Copy `runs/detect/train/weights/best.pt` to the Jetson
2. On the Jetson, convert to TensorRT (see `gemini.md` §3):
   ```python
   from ultralytics import YOLO
   model = YOLO("best.pt")
   model.export(format="engine", half=True, workspace=4)
   ```
3. Update `sniper_vision.py` to load `best.engine` instead of `best.pt` for maximum FPS

## Sample data.yaml

```yaml
# Placeholder — replace paths with your actual dataset location
train: C:/datasets/mosquito/train/images
val: C:/datasets/mosquito/valid/images
test: C:/datasets/mosquito/test/images

nc: 2
names: ['mosquito', 'not_target']
```

## Iterative Improvement

After field deployment:
1. Review `engagements.jsonl` to identify false positives and missed targets
2. Capture frames from those events
3. Add to Roboflow project, re-label, re-train
4. Repeat until false positive rate is acceptable
