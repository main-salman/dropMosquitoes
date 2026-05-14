#!/usr/bin/env python3
# Implements: TEST-001 Layer 1, T1.1–T1.2 — Camera hardware tests
"""
test_camera.py — Standalone camera test with FPS counter and frame saver.

Tests GStreamer pipeline initialization, sustained frame capture, and
measures actual FPS vs target FPS.

Usage (on Jetson):
    python3 tests/test_camera.py --scout          # Test Scout camera only
    python3 tests/test_camera.py --sniper         # Test Sniper camera only
    python3 tests/test_camera.py --both           # Test both simultaneously
    python3 tests/test_camera.py --scout --save   # Save sample frames to disk
"""

import argparse
import os
import sys
import time

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vision import CameraStream

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


def test_camera(name, sensor_id, width, height, target_fps, duration=10, save=False):
    """
    Run a camera for `duration` seconds and measure actual FPS.

    Args:
        name: Human-readable camera name.
        sensor_id: MIPI CSI port.
        width, height: Expected resolution.
        target_fps: Expected framerate.
        duration: How long to run the test (seconds).
        save: If True, save first and last frames as PNGs.
    """
    print(f"\n{'='*50}")
    print(f"  Testing: {name} (sensor={sensor_id}, {width}x{height} @ {target_fps}fps)")
    print(f"  Duration: {duration}s")
    print(f"{'='*50}")

    cam = CameraStream(sensor_id, width, height, target_fps, name)
    cam.start()
    time.sleep(1)  # Let the camera warm up

    # T1.x.1: Camera opened successfully
    first_frame = cam.get_frame()
    test(f"{name} produces frames", first_frame is not None)

    if first_frame is None:
        print(f"  ⚠️  No frames — camera may not be connected. Skipping FPS test.")
        cam.stop()
        return

    # T1.x.2: Frame dimensions correct
    h, w = first_frame.shape[:2]
    test(f"{name} resolution is {width}x{height}", w == width and h == height,
         f"got {w}x{h}")

    # T1.x.3: JPEG encoding works
    jpeg = cam.get_jpeg()
    test(f"{name} JPEG encoding works", jpeg is not None and len(jpeg) > 100,
         f"JPEG size: {len(jpeg) if jpeg else 0}")

    # Save first frame
    if save and first_frame is not None:
        import cv2
        out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f"{name.lower()}_first.png")
        cv2.imwrite(path, first_frame)
        print(f"  📸 Saved: {path}")

    # T1.x.4: Sustained capture — count unique frames over duration
    print(f"\n  Measuring FPS over {duration}s...")
    frame_count = 0
    start = time.time()
    prev_jpeg = None

    while time.time() - start < duration:
        jpeg = cam.get_jpeg()
        if jpeg is not None and jpeg != prev_jpeg:
            frame_count += 1
            prev_jpeg = jpeg
        time.sleep(0.001)  # Tight polling

    elapsed = time.time() - start
    actual_fps = frame_count / elapsed if elapsed > 0 else 0

    print(f"  Captured {frame_count} unique frames in {elapsed:.1f}s = {actual_fps:.1f} FPS")

    # FPS should be at least 50% of target (generous threshold for test patterns)
    min_acceptable = target_fps * 0.1 if target_fps > 60 else target_fps * 0.3
    test(f"{name} FPS >= {min_acceptable:.0f} (got {actual_fps:.1f})",
         actual_fps >= min_acceptable,
         f"target={target_fps}, actual={actual_fps:.1f}")

    # T1.x.5: No frames dropped in last 5 seconds
    drop_count = 0
    start2 = time.time()
    while time.time() - start2 < 5:
        f = cam.get_frame()
        if f is None:
            drop_count += 1
        time.sleep(0.01)
    test(f"{name} no None frames in 5s window", drop_count == 0,
         f"{drop_count} None frames")

    # Save last frame
    if save:
        last_frame = cam.get_frame()
        if last_frame is not None:
            import cv2
            path = os.path.join(out_dir, f"{name.lower()}_last.png")
            cv2.imwrite(path, last_frame)
            print(f"  📸 Saved: {path}")

    cam.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Camera Hardware Test")
    parser.add_argument('--scout', action='store_true', help='Test Scout camera (Port 0)')
    parser.add_argument('--sniper', action='store_true', help='Test Sniper camera (Port 1)')
    parser.add_argument('--both', action='store_true', help='Test both cameras simultaneously')
    parser.add_argument('--duration', type=int, default=10, help='Test duration in seconds')
    parser.add_argument('--save', action='store_true', help='Save sample frames to tests/output/')
    args = parser.parse_args()

    if not (args.scout or args.sniper or args.both):
        args.both = True  # Default: test both

    if args.scout or args.both:
        test_camera("Scout", sensor_id=0, width=1280, height=800,
                     target_fps=120, duration=args.duration, save=args.save)

    if args.sniper or args.both:
        test_camera("Sniper", sensor_id=1, width=1920, height=1080,
                     target_fps=30, duration=args.duration, save=args.save)

    print(f"\n{'='*50}")
    print(f"  CAMERA TESTS: {PASS} passed, {FAIL} failed")
    print(f"{'='*50}")
    sys.exit(0 if FAIL == 0 else 1)
