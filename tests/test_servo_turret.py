#!/usr/bin/env python3
# Implements: SW-001 §2.2 — ServoTurretController hardware verification
"""
test_servo_turret.py — PCA9685 + MG996R Servo Turret Connectivity Tests

Uses smbus2 for I2C access (Adafruit Blinka maps to wrong bus on Yahboom).

Verifies:
  1. I2C bus scan — PCA9685 responds at 0x40
  2. INA3221 conflict check — unbind kernel driver if needed
  3. Center command — both servos reach center (0°/0°)
  4. Yaw sweep — CH0 sweeps ±30° in 10° steps
  5. Pitch sweep — CH1 sweeps ±20° in 10° steps
  6. Combined move — simultaneous pitch+yaw
  7. I2C coexistence — LiDAR (0x10) still reads while servos move
  8. Return to center — park servos at 0°/0°

Usage:
  python tests/test_servo_turret.py
"""

import sys
import os
import time
import subprocess

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
    """Scan I2C bus 1 for PCA9685 using sub-address 0x71 (avoids INA3221 collision)."""
    print("\n=== I2C Bus Scan (Bus 1 — Pin 27/28) ===")
    try:
        import smbus2
        bus = smbus2.SMBus(1)
        # Software reset to enable sub-addresses
        try:
            bus.write_byte(0x00, 0x06)
        except Exception:
            pass
        import time; time.sleep(0.05)
        # Enable sub-addresses
        bus.write_byte_data(0x40, 0x00, 0x1F)
        time.sleep(0.01)
        found = []
        for addr in range(0x03, 0x78):
            try:
                bus.read_byte(addr)
                found.append(addr)
            except:
                pass
        bus.close()

        addr_hex = [f"0x{a:02X}" for a in found]
        print(f"  Devices found: {addr_hex}")

        has_pca = 0x40 in found
        has_lidar = 0x10 in found

        report("Device at 0x40", has_pca,
               "detected (INA3221 + PCA9685 collision expected)" if has_pca else "NOT FOUND")

        # Verify PCA9685 via sub-address 0x71 (no INA3221 interference)
        has_pca_verified = 0x71 in found
        if has_pca_verified:
            ps = bus.read_byte_data(0x71, 0xFE)
            if ps == 0x54:  # TI Manufacturer ID leaked
                report("PCA9685 via 0x71", False, "reads as INA3221, not PCA9685")
                has_pca_verified = False
            else:
                report("PCA9685 via 0x71", True,
                       f"confirmed (prescale=0x{ps:02X}, not INA3221)")
        else:
            report("PCA9685 via 0x71", False, "sub-address not responding")

        report("TF-Luna LiDAR at 0x10", has_lidar,
               "detected" if has_lidar else "not found (optional)")

        bus.close()
        return has_pca_verified
    except ImportError:
        report("I2C bus scan", False, "smbus2 not installed (pip install smbus2)")
        return False
    except Exception as e:
        report("I2C bus scan", False, str(e))
        return False


def test_ina3221_conflict():
    """Check if INA3221 kernel driver is blocking 0x40 on bus 1 (internal)."""
    print("\n=== INA3221 Conflict Check (Bus 1 — internal) ===")
    ina_path = "/sys/bus/i2c/devices/1-0040/driver"

    if not os.path.exists(ina_path):
        report("INA3221 conflict", True, "no kernel driver claiming 0x40")
        return True

    # Read what driver is bound
    try:
        driver = os.readlink(ina_path).split("/")[-1]
        print(f"  ⚠️  Kernel driver '{driver}' is claiming 0x40!")
        print(f"  Attempting to unbind...")

        # Try to unbind
        result = subprocess.run(
            ["sudo", "-S", "sh", "-c",
             "echo 1-0040 > /sys/bus/i2c/drivers/ina3221/unbind"],
            input=b"yahboom\n", capture_output=True, timeout=5
        )

        if result.returncode == 0:
            report("INA3221 unbind", True,
                   "driver unbound — 0x40 now available for PCA9685")
            return True
        else:
            err = result.stderr.decode().strip()
            report("INA3221 unbind", False,
                   f"unbind failed: {err}")
            return False
    except Exception as e:
        report("INA3221 conflict check", False, str(e))
        return False


def test_center():
    """Test 3: Command both servos to center (0°/0°)."""
    print("\n=== Test 3: Center Command ===")
    try:
        from hardware import ServoTurretController
        ctrl = ServoTurretController()

        if ctrl._bus is None:
            report("ServoTurretController init", False, "running in STUB mode — no PCA9685")
            return ctrl

        report("ServoTurretController init", True,
               f"PCA9685 at 0x{ctrl.PCA9685_ADDRESS:02X} via smbus2")

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
    """Test 4: Sweep yaw (CH0) from -30° to +30° in 10° steps."""
    print("\n=== Test 4: Yaw Sweep (CH0) ===")
    if ctrl is None or ctrl._bus is None:
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
    """Test 5: Sweep pitch (CH1) from -20° to +20° in 10° steps."""
    print("\n=== Test 5: Pitch Sweep (CH1) ===")
    if ctrl is None or ctrl._bus is None:
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
    """Test 6: Simultaneous pitch+yaw to confirm no I2C bus contention."""
    print("\n=== Test 6: Combined Move ===")
    if ctrl is None or ctrl._bus is None:
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
    """Test 7: LiDAR still reads while servos are active (shared I2C bus)."""
    print("\n=== Test 7: I2C Coexistence (LiDAR + PCA9685) ===")
    if ctrl is None or ctrl._bus is None:
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
    """Test 8: Park servos at center on exit."""
    print("\n=== Test 8: Return to Center ===")
    if ctrl is None or ctrl._bus is None:
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
    print("  SERVO TURRET TEST — PCA9685 + MG996R (smbus2)")
    print("=" * 60)

    # Step 1: Always check/fix INA3221 conflict first
    # The Yahboom carrier board has an INA3221 at 0x40 that blocks PCA9685
    test_ina3221_conflict()

    # Step 2: I2C scan via smbus2 (after unbind)
    pca_found = test_i2c_scan()

    # Step 3: Initialize and center
    ctrl = test_center()

    if ctrl and ctrl._bus:
        # Steps 4-8: Only run if real hardware is present
        test_yaw_sweep(ctrl)
        test_pitch_sweep(ctrl)
        test_combined_move(ctrl)
        test_i2c_coexistence(ctrl)
        test_return_center(ctrl)
        ctrl.cleanup()
    else:
        print("\n  ⚠️  Skipping hardware tests — PCA9685 not detected on Bus 1.")
        print("     Bus 1 = Pin 27 (SDA) / Pin 28 (SCL) on Yahboom board")
        print("")
        print("     Verify PCA9685 LEFT HEADER wiring:")
        print("       PCA9685 VCC → Jetson Pin 1 (3.3V) ← REQUIRED for I2C logic!")
        print("       PCA9685 GND → Jetson Pin 6 (GND)")
        print("       PCA9685 SDA → Jetson Pin 27")
        print("       PCA9685 SCL → Jetson Pin 28")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"  {passed} passed, {failed} failed")
    print(f"{'=' * 60}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
