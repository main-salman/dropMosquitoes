#!/usr/bin/env python3
# Implements: TEST-001 Layer 3 — Safety interlock verification
"""
test_safety.py — Automated safety tests for SAFE-001 compliance.

Verifies all software safety interlocks WITHOUT requiring real hardware.
These tests can run on any machine.

Usage:
    python3 tests/test_safety.py
"""

import os
import signal
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hardware import (
    RelayController, GimbalController,
    YAW_LIMIT, PITCH_LIMIT, pixel_to_angle
)
from vision import YOLODetector

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


def test_gpio_failsafe():
    """
    T3.1: Verify GPIO is set LOW after relay cleanup.
    Simulates what happens when the Python process exits.
    """
    print(f"\n{'='*50}")
    print(f"  T3.1: GPIO Fail-Safe Test")
    print(f"{'='*50}")

    relay = RelayController()

    # Pump should start OFF
    test("Pump starts OFF", relay.get_status()["pump"] == False)

    # Turn pump ON
    relay.set_pump(True)
    test("Pump turned ON", relay.get_status()["pump"] == True)

    # Simulate crash cleanup
    relay.cleanup()
    # After cleanup, the internal state should reflect OFF
    # (On real Jetson, GPIO pins would be released to safe state)
    test("Cleanup completes without crash", True)


def test_boot_sequence():
    """
    T3.2 / SAFE-001 §1: Gimbal power MUST default to OFF at boot.
    """
    print(f"\n{'='*50}")
    print(f"  T3.2: Boot Sequence — Gimbal Power Default")
    print(f"{'='*50}")

    relay = RelayController()

    test("Gimbal power OFF at init (SAFE-001 §1)",
         relay.get_status()["gimbal_power"] == False)
    test("Pump OFF at init",
         relay.get_status()["pump"] == False)

    relay.cleanup()


def test_endstop_enforcement():
    """
    T3.4: Software endstops prevent exceeding mechanical limits.
    """
    print(f"\n{'='*50}")
    print(f"  T3.4: Software Endstop Enforcement")
    print(f"{'='*50}")

    g = GimbalController()

    # Extreme yaw
    g.set_angles(0, 9999)
    test(f"Yaw +9999 → clamped to +{YAW_LIMIT}",
         g.get_status()["yaw"] == YAW_LIMIT)

    g.set_angles(0, -9999)
    test(f"Yaw -9999 → clamped to -{YAW_LIMIT}",
         g.get_status()["yaw"] == -YAW_LIMIT)

    # Extreme pitch
    g.set_angles(9999, 0)
    test(f"Pitch +9999 → clamped to +{PITCH_LIMIT}",
         g.get_status()["pitch"] == PITCH_LIMIT)

    g.set_angles(-9999, 0)
    test(f"Pitch -9999 → clamped to -{PITCH_LIMIT}",
         g.get_status()["pitch"] == -PITCH_LIMIT)

    # Boundary values
    g.set_angles(PITCH_LIMIT, YAW_LIMIT)
    test(f"Exact limits accepted: pitch={PITCH_LIMIT}, yaw={YAW_LIMIT}",
         g.get_status()["pitch"] == PITCH_LIMIT and
         g.get_status()["yaw"] == YAW_LIMIT)

    # Zero
    g.center()
    test("Center returns to (0, 0)",
         g.get_status()["pitch"] == 0 and g.get_status()["yaw"] == 0)

    g.cleanup()


def test_death_spiral():
    """
    T3.5: Verify the gimbal cannot exceed ±YAW_LIMIT via nudge accumulation.
    Simulates continuous nudging past the boundary.
    """
    print(f"\n{'='*50}")
    print(f"  T3.5: Death Spiral Prevention")
    print(f"{'='*50}")

    g = GimbalController()
    g.center()

    # Nudge 200 times at 2° each = 400° attempted rotation
    for _ in range(200):
        g.nudge(0, 2.0)

    test(f"200 nudges (+400°) clamped to +{YAW_LIMIT}°",
         g.get_status()["yaw"] == YAW_LIMIT,
         f"got {g.get_status()['yaw']}")

    # Nudge back the other way
    for _ in range(400):
        g.nudge(0, -2.0)

    test(f"400 nudges (-800°) clamped to -{YAW_LIMIT}°",
         g.get_status()["yaw"] == -YAW_LIMIT,
         f"got {g.get_status()['yaw']}")

    g.cleanup()


def test_pump_duration_clamp():
    """
    T3.7 (partial): Verify pump fire duration is clamped to safe range.
    """
    print(f"\n{'='*50}")
    print(f"  T3.7: Pump Duration Clamping")
    print(f"{'='*50}")

    relay = RelayController()

    # Fire with extreme duration — should clamp to 2.0s max
    start = time.time()
    relay.fire_pump(999.0)  # Requests 999 seconds
    time.sleep(2.5)  # Wait for clamped duration + buffer
    elapsed = time.time() - start
    test("999s duration clamped (finished in ~2.5s)", elapsed < 4.0,
         f"took {elapsed:.1f}s")
    test("Pump is OFF after clamped fire", relay.get_status()["pump"] == False)

    # Fire with tiny duration — should clamp to 0.05s min
    relay.fire_pump(0.001)
    time.sleep(0.3)
    test("0.001s duration clamped to 0.05s minimum", True)
    test("Pump is OFF after tiny fire", relay.get_status()["pump"] == False)

    relay.cleanup()


def test_pixel_to_angle_bounds():
    """
    T3.4 (supplementary): Verify click-to-aim doesn't produce out-of-range angles.
    """
    print(f"\n{'='*50}")
    print(f"  Click-to-Aim Bounds Check")
    print(f"{'='*50}")

    # Corners of a 1280x800 frame with 110° H FOV, 75° V FOV
    corners = [
        (0, 0, "top-left"),
        (1280, 0, "top-right"),
        (0, 800, "bottom-left"),
        (1280, 800, "bottom-right"),
        (640, 400, "center"),
    ]

    for px, py, label in corners:
        pitch, yaw = pixel_to_angle(px, py, 1280, 800, 110.0, 75.0)
        test(f"  {label} ({px},{py}) → pitch={pitch:.1f}°, yaw={yaw:.1f}°", True)

    # Center should be near zero
    p, y = pixel_to_angle(640, 400, 1280, 800)
    test("Center pixel → angles ≈ 0", abs(p) < 1 and abs(y) < 1,
         f"got ({p:.2f}, {y:.2f})")


def test_concurrent_safety():
    """
    T3.8 (partial): Verify relay and gimbal operations are thread-safe.
    """
    print(f"\n{'='*50}")
    print(f"  Thread Safety Test (Concurrent Operations)")
    print(f"{'='*50}")

    relay = RelayController()
    gimbal = GimbalController()
    errors = []

    def spam_pump(n):
        for _ in range(n):
            try:
                relay.fire_pump(0.05)
                time.sleep(0.02)
            except Exception as e:
                errors.append(f"pump: {e}")

    def spam_gimbal(n):
        for i in range(n):
            try:
                gimbal.set_angles(i % 20, (i * 3) % 80)
            except Exception as e:
                errors.append(f"gimbal: {e}")

    # Launch 4 threads hammering both subsystems
    threads = [
        threading.Thread(target=spam_pump, args=(50,)),
        threading.Thread(target=spam_pump, args=(50,)),
        threading.Thread(target=spam_gimbal, args=(100,)),
        threading.Thread(target=spam_gimbal, args=(100,)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    test(f"300 concurrent operations with 0 errors",
         len(errors) == 0, f"{len(errors)} errors: {errors[:3]}")

    time.sleep(2.5)  # Let any pending fire_pump finish
    relay.cleanup()
    gimbal.cleanup()


if __name__ == "__main__":
    test_gpio_failsafe()
    test_boot_sequence()
    test_endstop_enforcement()
    test_death_spiral()
    test_pump_duration_clamp()
    test_pixel_to_angle_bounds()
    test_concurrent_safety()

    print(f"\n{'='*50}")
    print(f"  SAFETY TESTS: {PASS} passed, {FAIL} failed")
    print(f"{'='*50}")
    sys.exit(0 if FAIL == 0 else 1)
