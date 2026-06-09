#!/usr/bin/env python3
# Implements: SW-001 §2.2 — ServoTurretController hardware verification
"""
test_servo_turret.py — PCA9685 + MG996R Servo Turret Connectivity Tests

Verifies:
  1. I2C bus scan — PCA9685 responds at 0x40
  2. Center command — both servos reach center (0°/0°)
  3. Yaw sweep — CH0 sweeps ±30° in 10° steps
  4. Pitch sweep — CH1 sweeps ±20° in 10° steps
  5. Combined move — simultaneous pitch+yaw
  6. I2C coexistence — LiDAR (0x10) still reads while servos move
  7. Return to center — park servos at 0°/0°

Usage:
  python tests/test_servo_turret.py
"""

import sys
import os
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

passed = 0
failed = 0


def report(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  ✅ {name}" + (f" — {detail}" if detail else ""))
    else:
        failed += 1
        print(f"  ❌ {name}" + (f" — {detail}" if detail else ""))


def test_i2c_scan():
    """Test 1: Scan I2C bus 1 for PCA9685 at address 0x40."""
    print("\n=== Test 1: I2C Bus Scan ===")
    try:
        import board
        import busio
        i2c = busio.I2C(board.SCL, board.SDA)
        while not i2c.try_lock():
            pass
        addrs = i2c.scan()
        i2c.unlock()

        addr_hex = [f"0x{a:02X}" for a in addrs]
        print(f"  Devices found: {addr_hex}")

        has_pca = 0x40 in addrs
        has_lidar = 0x10 in addrs

        report("PCA9685 at 0x40", has_pca,
               "detected" if has_pca else "NOT FOUND — check wiring")
        report("TF-Luna LiDAR at 0x10 (coexistence)", has_lidar,
               "detected" if has_lidar else "not found (optional)")

        return has_pca
    except ImportError:
        report("I2C bus scan", False, "board/busio not installed (pip install adafruit-blinka)")
        return False
    except Exception as e:
        report("I2C bus scan", False, str(e))
        return False


def test_center():
    """Test 2: Command both servos to center (0°/0°)."""
    print("\n=== Test 2: Center Command ===")
    try:
        from hardware import ServoTurretController
        ctrl = ServoTurretController()

        if ctrl._kit is None:
            report("ServoTurretController init", False, "running in STUB mode — no PCA9685")
            return ctrl

        report("ServoTurretController init", True,
               f"PCA9685 at 0x{ctrl.PCA9685_ADDRESS:02X}")

        ctrl.center()
        time.sleep(0.5)
        status = ctrl.get_status()
        report("Center command", True,
               f"pitch={status['pitch']}° yaw={status['yaw']}°")
        return ctrl
    except Exception as e:
        report("Center command", False, str(e))
        return None


def test_yaw_sweep(ctrl):
    """Test 3: Sweep yaw (CH0) from -30° to +30° in 10° steps."""
    print("\n=== Test 3: Yaw Sweep (CH0) ===")
    if ctrl is None or ctrl._kit is None:
        report("Yaw sweep", False, "no controller available")
        return

    try:
        angles = list(range(-30, 35, 10))  # -30, -20, -10, 0, 10, 20, 30
        for angle in angles:
            ctrl.set_angles(0, angle)
            time.sleep(0.3)
            status = ctrl.get_status()
            print(f"    → yaw={status['yaw']}°")

        report("Yaw sweep -30° to +30°", True,
               f"{len(angles)} steps completed")
    except Exception as e:
        report("Yaw sweep", False, str(e))


def test_pitch_sweep(ctrl):
    """Test 4: Sweep pitch (CH1) from -20° to +20° in 10° steps."""
    print("\n=== Test 4: Pitch Sweep (CH1) ===")
    if ctrl is None or ctrl._kit is None:
        report("Pitch sweep", False, "no controller available")
        return

    try:
        angles = list(range(-20, 25, 10))  # -20, -10, 0, 10, 20
        for angle in angles:
            ctrl.set_angles(angle, 0)
            time.sleep(0.3)
            status = ctrl.get_status()
            print(f"    → pitch={status['pitch']}°")

        report("Pitch sweep -20° to +20°", True,
               f"{len(angles)} steps completed")
    except Exception as e:
        report("Pitch sweep", False, str(e))


def test_combined_move(ctrl):
    """Test 5: Simultaneous pitch+yaw to confirm no I2C bus contention."""
    print("\n=== Test 5: Combined Move ===")
    if ctrl is None or ctrl._kit is None:
        report("Combined move", False, "no controller available")
        return

    try:
        positions = [
            (15, 25, "upper-right"),
            (-15, -25, "lower-left"),
            (10, -20, "upper-left"),
            (-10, 20, "lower-right"),
            (0, 0, "center"),
        ]
        for pitch, yaw, label in positions:
            ctrl.set_angles(pitch, yaw)
            time.sleep(0.4)
            status = ctrl.get_status()
            print(f"    → {label}: pitch={status['pitch']}° yaw={status['yaw']}°")

        report("Combined pitch+yaw moves", True,
               f"{len(positions)} positions hit")
    except Exception as e:
        report("Combined move", False, str(e))


def test_i2c_coexistence(ctrl):
    """Test 6: LiDAR still reads while servos are active (shared I2C bus)."""
    print("\n=== Test 6: I2C Coexistence (LiDAR + PCA9685) ===")
    if ctrl is None or ctrl._kit is None:
        report("I2C coexistence", False, "no controller available")
        return

    try:
        from hardware import LiDARController
        lidar = LiDARController()

        # Move servo while reading LiDAR
        ctrl.set_angles(10, 15)
        time.sleep(0.2)
        d1 = lidar.read_distance()

        ctrl.set_angles(-10, -15)
        time.sleep(0.2)
        d2 = lidar.read_distance()

        if d1 > 0 and d2 > 0:
            report("LiDAR reads during servo moves", True,
                   f"d1={d1:.2f}m d2={d2:.2f}m — no I2C bus contention")
        elif d1 == 0 and d2 == 0:
            report("LiDAR reads during servo moves", False,
                   "LiDAR returned 0 both times — possible bus contention or no target")
        else:
            report("LiDAR reads during servo moves", True,
                   f"d1={d1:.2f}m d2={d2:.2f}m — partial reads (LiDAR may have no target)")

        lidar.cleanup()
    except ImportError:
        report("I2C coexistence", False, "LiDARController not available")
    except Exception as e:
        report("I2C coexistence", False, str(e))


def test_return_center(ctrl):
    """Test 7: Park servos at center on exit."""
    print("\n=== Test 7: Return to Center ===")
    if ctrl is None or ctrl._kit is None:
        report("Return to center", False, "no controller available")
        return

    try:
        ctrl.center()
        time.sleep(0.5)
        status = ctrl.get_status()
        ok = status['pitch'] == 0.0 and status['yaw'] == 0.0
        report("Return to center", ok,
               f"pitch={status['pitch']}° yaw={status['yaw']}°")
    except Exception as e:
        report("Return to center", False, str(e))


def main():
    print("=" * 60)
    print("  SERVO TURRET TEST — PCA9685 + MG996R")
    print("=" * 60)

    # Test 1: I2C scan
    pca_found = test_i2c_scan()

    # Test 2: Initialize and center
    ctrl = test_center()

    if ctrl and ctrl._kit:
        # Test 3-7: Only run if real hardware is present
        test_yaw_sweep(ctrl)
        test_pitch_sweep(ctrl)
        test_combined_move(ctrl)
        test_i2c_coexistence(ctrl)
        test_return_center(ctrl)
        ctrl.cleanup()
    else:
        print("\n  ⚠️  Skipping hardware tests — PCA9685 not detected.")
        print("     Verify wiring: Jetson Pin 3 (SDA) → PCA9685 Pin 4 (SDA)")
        print("                    Jetson Pin 5 (SCL) → PCA9685 Pin 3 (SCL)")
        print("                    Jetson Pin 1 (3.3V) → PCA9685 Pin 5 (VCC)")
        print("                    Jetson Pin 6 (GND) → PCA9685 Pin 1 (GND)")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"  {passed} passed, {failed} failed")
    print(f"{'=' * 60}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
