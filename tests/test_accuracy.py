#!/usr/bin/env python3
# Implements: TEST-001 Layer 4 — Calibration and accuracy tests
"""
test_accuracy.py — Click-to-aim accuracy and gimbal repeatability tests.

Validates the coordinate math, gimbal positioning precision, and measures
system latency.

Usage:
    python3 tests/test_accuracy.py
    python3 tests/test_accuracy.py --live    # With real hardware (on Jetson)
"""

import argparse
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hardware import GimbalController, pixel_to_angle, YAW_LIMIT, PITCH_LIMIT

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


def test_click_to_aim_math():
    """
    T4.6: Validate pixel-to-angle conversion at known grid points.
    """
    print(f"\n{'='*50}")
    print(f"  T4.6: Click-to-Aim Math Validation")
    print(f"{'='*50}")

    W, H = 1280, 800
    FOV_H, FOV_V = 110.0, 75.0

    # Known test points: (px, py) → expected (pitch°, yaw°)
    # Center of frame → (0, 0)
    test_points = [
        (W//2, H//2, 0.0, 0.0, "center"),
        (W, H//2, 0.0, FOV_H/2, "right edge"),
        (0, H//2, 0.0, -FOV_H/2, "left edge"),
        (W//2, 0, FOV_V/2, 0.0, "top edge"),       # top → positive pitch (look up)
        (W//2, H, -FOV_V/2, 0.0, "bottom edge"),    # bottom → negative pitch
        (W, 0, FOV_V/2, FOV_H/2, "top-right"),
        (0, H, -FOV_V/2, -FOV_H/2, "bottom-left"),
    ]

    for px, py, exp_pitch, exp_yaw, label in test_points:
        pitch, yaw = pixel_to_angle(px, py, W, H, FOV_H, FOV_V)
        err_p = abs(pitch - exp_pitch)
        err_y = abs(yaw - exp_yaw)
        test(f"  {label} ({px},{py}) → p={pitch:.1f}° y={yaw:.1f}° "
             f"(expected p={exp_pitch:.1f}° y={exp_yaw:.1f}°)",
             err_p < 0.5 and err_y < 0.5,
             f"error: Δp={err_p:.2f}° Δy={err_y:.2f}°")

    # Linearity check: evenly spaced pixels should produce evenly spaced angles
    print("\n  Linearity check (10 evenly spaced horizontal points):")
    angles = []
    for i in range(10):
        px = int(W * (i / 9))
        _, yaw = pixel_to_angle(px, H//2, W, H, FOV_H, FOV_V)
        angles.append(yaw)

    # Check that spacing is roughly constant
    spacings = [angles[i+1] - angles[i] for i in range(len(angles)-1)]
    avg_spacing = sum(spacings) / len(spacings)
    max_dev = max(abs(s - avg_spacing) for s in spacings)
    test(f"Angle spacing is linear (max deviation {max_dev:.2f}°)",
         max_dev < 1.0, f"spacings: {[f'{s:.1f}' for s in spacings]}")


def test_gimbal_repeatability():
    """
    T4.5: Send the same angle 50 times and verify consistency.
    """
    print(f"\n{'='*50}")
    print(f"  T4.5: Gimbal Repeatability Test")
    print(f"{'='*50}")

    g = GimbalController()

    target_pitch = 10.0
    target_yaw = 45.0
    errors_p = []
    errors_y = []

    for i in range(50):
        g.set_angles(target_pitch, target_yaw)
        status = g.get_status()
        errors_p.append(abs(status["pitch"] - target_pitch))
        errors_y.append(abs(status["yaw"] - target_yaw))

    mean_err_p = sum(errors_p) / len(errors_p)
    mean_err_y = sum(errors_y) / len(errors_y)
    max_err_p = max(errors_p)
    max_err_y = max(errors_y)

    test(f"Pitch mean error < 0.5° (got {mean_err_p:.3f}°)", mean_err_p < 0.5)
    test(f"Yaw mean error < 0.5° (got {mean_err_y:.3f}°)", mean_err_y < 0.5)
    test(f"Pitch max error < 1.0° (got {max_err_p:.3f}°)", max_err_p < 1.0)
    test(f"Yaw max error < 1.0° (got {max_err_y:.3f}°)", max_err_y < 1.0)

    # In stub mode these should all be 0.0 (perfect)
    if not g.get_status()["connected"]:
        print("  ℹ️  STUB MODE — errors are 0.0 (no physical gimbal).")

    g.cleanup()


def test_full_range_sweep():
    """
    Systematic sweep across the full angular range to verify no dead zones.
    """
    print(f"\n{'='*50}")
    print(f"  Full Range Sweep (5° increments)")
    print(f"{'='*50}")

    g = GimbalController()
    dead_zones = []

    # Sweep yaw
    yaw_steps = list(range(int(-YAW_LIMIT), int(YAW_LIMIT) + 1, 5))
    for yaw in yaw_steps:
        g.set_angles(0, yaw)
        actual = g.get_status()["yaw"]
        if abs(actual - yaw) > 0.5:
            dead_zones.append(f"yaw={yaw}→{actual}")

    test(f"Yaw sweep ({len(yaw_steps)} positions, 0 dead zones)",
         len(dead_zones) == 0,
         f"dead zones: {dead_zones}")

    # Sweep pitch
    dead_zones = []
    pitch_steps = list(range(int(-PITCH_LIMIT), int(PITCH_LIMIT) + 1, 2))
    for pitch in pitch_steps:
        g.set_angles(pitch, 0)
        actual = g.get_status()["pitch"]
        if abs(actual - pitch) > 0.5:
            dead_zones.append(f"pitch={pitch}→{actual}")

    test(f"Pitch sweep ({len(pitch_steps)} positions, 0 dead zones)",
         len(dead_zones) == 0,
         f"dead zones: {dead_zones}")

    g.center()
    g.cleanup()


def test_api_latency():
    """
    T4.7 (partial): Measure the round-trip time for a gimbal command via API.
    Requires the server to be running.
    """
    print(f"\n{'='*50}")
    print(f"  T4.7: Command Latency Measurement")
    print(f"{'='*50}")

    import urllib.request
    import json

    try:
        # Check if server is running
        urllib.request.urlopen("http://localhost:8000/api/status", timeout=1)
    except Exception:
        print("  ⚠️  Server not running. Skipping API latency test.")
        print("     Start with: python3 app.py --no-ai")
        return

    url = "http://localhost:8000/api/gimbal/set"
    latencies = []

    for i in range(20):
        data = json.dumps({"pitch": i % 10, "yaw": i * 3 % 60}).encode()
        req = urllib.request.Request(url, data=data,
                                     headers={"Content-Type": "application/json"})
        start = time.time()
        urllib.request.urlopen(req, timeout=5)
        latencies.append((time.time() - start) * 1000)

    avg = sum(latencies) / len(latencies)
    p95 = sorted(latencies)[int(len(latencies) * 0.95)]
    mx = max(latencies)

    print(f"    20 commands: avg={avg:.1f}ms, p95={p95:.1f}ms, max={mx:.1f}ms")

    test(f"Average API latency < 50ms (got {avg:.1f}ms)", avg < 50)
    test(f"P95 API latency < 100ms (got {p95:.1f}ms)", p95 < 100)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Accuracy & Calibration Tests")
    parser.add_argument('--live', action='store_true',
                        help='Include API latency tests (requires running server)')
    args = parser.parse_args()

    test_click_to_aim_math()
    test_gimbal_repeatability()
    test_full_range_sweep()

    if args.live:
        test_api_latency()

    print(f"\n{'='*50}")
    print(f"  ACCURACY TESTS: {PASS} passed, {FAIL} failed")
    print(f"{'='*50}")
    sys.exit(0 if FAIL == 0 else 1)
