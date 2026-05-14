#!/usr/bin/env python3
# Implements: TEST-001 Layer 1, T1.7 — TensorRT YOLO model test
"""
test_yolo.py — TensorRT model load and single-frame inference test.

Tests that the YOLOv8 model loads (TensorRT .engine on Jetson, or .pt fallback)
and can run inference on a synthetic or saved test image.

Usage:
    python3 tests/test_yolo.py                        # Default test
    python3 tests/test_yolo.py --image path/to/img.jpg # Test on specific image
"""

import argparse
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vision import YOLODetector, YOLO_AVAILABLE

PASS = 0
FAIL = 0


def test(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name} — {detail}")


def generate_test_frame(width=640, height=480):
    """Generate a synthetic test frame with colored rectangles."""
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    # Background gradient
    for y in range(height):
        frame[y, :] = [int(y/height*100), int(y/height*50), 30]
    # Some rectangles to give YOLO something to look at
    import cv2
    cv2.rectangle(frame, (100, 100), (200, 250), (0, 255, 0), -1)
    cv2.rectangle(frame, (300, 150), (450, 350), (255, 100, 0), -1)
    cv2.circle(frame, (500, 300), 50, (0, 0, 255), -1)
    return frame


def test_model_load():
    """T1.7.1: Model loads without crashing."""
    print(f"\n{'='*50}")
    print(f"  T1.7: YOLO Model Test")
    print(f"{'='*50}")

    if not YOLO_AVAILABLE:
        print("  ⚠️  ultralytics not installed. Testing disabled mode.")
        detector = YOLODetector()
        test("Detector initializes (no model)", detector.model is None)
        test("Detect returns empty list (no model)", detector.detect(np.zeros((480,640,3), dtype=np.uint8)) == [])
        return None

    # Time the model load
    start = time.time()
    detector = YOLODetector()
    load_time = time.time() - start

    test("Model loaded", detector.model is not None,
         f"Check MODEL_PATH in vision.py")
    test(f"Model loaded in <10s ({load_time:.1f}s)", load_time < 10,
         f"took {load_time:.1f}s")

    return detector


def test_inference(detector, image_path=None):
    """T1.7.2: Run inference on a test frame."""
    if detector is None or detector.model is None:
        print("  ⚠️  No model loaded. Skipping inference test.")
        return

    print(f"\n  Running inference...")

    if image_path:
        import cv2
        frame = cv2.imread(image_path)
        test("Test image loaded", frame is not None, f"Cannot read {image_path}")
        if frame is None:
            return
    else:
        frame = generate_test_frame()

    # Time inference
    start = time.time()
    detections = detector.detect(frame)
    infer_time = time.time() - start

    print(f"    Inference time: {infer_time*1000:.1f}ms")
    print(f"    Detections: {len(detections)}")

    test("Inference completes without crash", True)
    test(f"Inference < 500ms ({infer_time*1000:.0f}ms)", infer_time < 0.5,
         f"took {infer_time*1000:.0f}ms")
    test("Detections is a list", isinstance(detections, list))

    for i, det in enumerate(detections):
        print(f"    [{i}] {det['class']} conf={det['confidence']:.2f} "
              f"bbox={det['bbox']} area={det['area']} safe={det['is_safe']}")
        test(f"Detection {i} has required keys",
             all(k in det for k in ['class', 'confidence', 'bbox', 'area', 'is_safe']))

    # Test annotation
    annotated = detector.annotate_frame(frame, detections)
    test("Annotation produces valid frame",
         annotated is not None and annotated.shape == frame.shape)

    # Batch inference for FPS measurement
    print(f"\n  Measuring inference FPS (20 frames)...")
    start = time.time()
    for _ in range(20):
        detector.detect(frame)
    elapsed = time.time() - start
    fps = 20 / elapsed
    print(f"    Inference FPS: {fps:.1f}")
    test(f"Inference FPS > 5 (got {fps:.1f})", fps > 5)


def test_threshold_adjustment(detector):
    """T1.7.3: Dynamic threshold adjustment."""
    if detector is None:
        return

    print(f"\n  Testing threshold adjustment...")

    detector.set_confidence(0.8)
    test("Confidence set to 80%", detector.confidence == 0.8)

    detector.set_confidence(0.01)
    test("Confidence clamped to 5% minimum", detector.confidence == 0.05)

    detector.set_min_box_area(500)
    test("Min box area set to 500", detector.min_box_area == 500)

    detector.set_min_box_area(1)
    test("Min box area clamped to 10 minimum", detector.min_box_area == 10)

    # Reset
    detector.set_confidence(0.5)
    detector.set_min_box_area(100)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YOLO Model Test")
    parser.add_argument('--image', help='Path to test image (optional)')
    args = parser.parse_args()

    detector = test_model_load()
    test_inference(detector, args.image)
    test_threshold_adjustment(detector)

    print(f"\n{'='*50}")
    print(f"  YOLO TESTS: {PASS} passed, {FAIL} failed")
    print(f"{'='*50}")
    sys.exit(0 if FAIL == 0 else 1)
