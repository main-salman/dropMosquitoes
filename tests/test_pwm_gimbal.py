#!/usr/bin/env python3
"""
test_pwm_gimbal.py — Test PWM control of Storm32 gimbal via RC input pins.

The Storm32's RC input pins expect standard RC PWM signals:
  1000μs pulse (5.0% duty @ 50Hz)  → minimum angle (-45°)
  1500μs pulse (7.5% duty @ 50Hz)  → center (0°)
  2000μs pulse (10.0% duty @ 50Hz) → maximum angle (+45°)

Wiring (IDC40P → Storm32 2x6 RC header outer row):
  Terminal 32 (BCM 12, PWM0) → Storm32 RC-0 (Pitch)
  Terminal 33 (BCM 13, PWM2) → Storm32 RC-2 (Yaw)
  Terminal 14 (GND)          → Storm32 RC GND
"""
import os
import subprocess
import time
import sys

try:
    import Jetson.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False

# ── PWM Configuration ──────────────────────────────────────────────
PWM_FREQ = 50          # Hz (20ms period = standard RC)

# BCM pin numbers → Storm32 RC inputs (HARDWARE PWM CAPABLE)
PITCH_PIN_BCM = 12     # Physical Pin 32 (PWM0) → Storm32 RC-0 (Pitch)
YAW_PIN_BCM   = 13     # Physical Pin 33 (PWM2) → Storm32 RC-2 (Yaw)

# Duty cycle boundaries (derived from pulse width / period)
MIN_DUTY    = 5.0      # 1000μs / 20000μs
CENTER_DUTY = 7.5      # 1500μs / 20000μs
MAX_DUTY    = 10.0     # 2000μs / 20000μs

# Default Storm32 RC range: ±45° maps to 1000–2000μs
RC_RANGE_DEG = 45.0

passed = 0
failed = 0


def angle_to_duty(angle_deg, rc_range=RC_RANGE_DEG):
    """Map an angle in degrees to an RC PWM duty cycle percentage."""
    clamped = max(-rc_range, min(rc_range, angle_deg))
    normalized = (clamped + rc_range) / (2.0 * rc_range)   # 0.0 → 1.0
    return MIN_DUTY + normalized * (MAX_DUTY - MIN_DUTY)    # 5.0 → 10.0


def ok(msg):
    global passed
    passed += 1
    print(f"  ✅ {msg}")


def fail(msg):
    global failed
    failed += 1
    print(f"  ❌ {msg}")


def configure_pwm_pinmux():
    """
    ECO-2026-008: Force pinmux to OUTPUT mode for PWM pins.
    Without this, the Jetson Orin Nano leaves BCM 12/13 in INPUT mode
    and no PWM signal reaches the physical pins.
    Uses direct /dev/mem writes (same as hardware.py configure_push_pull).
    """
    try:
        import mmap
        import struct
        with open("/dev/mem", "r+b") as f:
            # BCM 12 (Pin 32, PWM0) at register 0x2434080 → write 0x5 (output)
            mem1 = mmap.mmap(f.fileno(), 0x10000, offset=0x2430000)
            mem1[0x4080:0x4084] = struct.pack("<I", 0x5)
            mem1.close()

            # BCM 13 (Pin 33, PWM2) at register 0x2434040 → write 0x4 (output)
            mem2 = mmap.mmap(f.fileno(), 0x10000, offset=0x2430000)
            mem2[0x4040:0x4044] = struct.pack("<I", 0x4)
            mem2.close()
        return True
    except Exception as e:
        print(f"     Pinmux write failed: {e}")
        return False


# ── Main Test ───────────────────────────────────────────────────────
print("=" * 60)
print("  PWM Gimbal Sweep Test")
print(f"  Pitch: BCM {PITCH_PIN_BCM} (Pin 32, PWM0)")
print(f"  Yaw:   BCM {YAW_PIN_BCM} (Pin 33, PWM2)")
print(f"  Frequency: {PWM_FREQ} Hz · RC Range: ±{RC_RANGE_DEG}°")
print("=" * 60)

if not GPIO_AVAILABLE:
    fail("Jetson.GPIO not available — cannot run on this platform")
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1)

# ── Pinmux Fix ─────────────────────────────────────────────────────
print("\n--- Pinmux Configuration ---")
if configure_pwm_pinmux():
    ok("Pinmux forced to OUTPUT for BCM 12 and BCM 13")
else:
    fail("Pinmux configuration failed (needs root/sudo)")

# ── Setup ───────────────────────────────────────────────────────────
print("\n--- GPIO Setup ---")
pitch_pwm = None
yaw_pwm = None

try:
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(PITCH_PIN_BCM, GPIO.OUT)
    GPIO.setup(YAW_PIN_BCM, GPIO.OUT)
    ok("GPIO pins configured as output")
except Exception as e:
    fail(f"GPIO setup failed: {e}")
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1)

try:
    pitch_pwm = GPIO.PWM(PITCH_PIN_BCM, PWM_FREQ)
    yaw_pwm   = GPIO.PWM(YAW_PIN_BCM, PWM_FREQ)
    ok("PWM objects created (hardware PWM)")
except Exception as e:
    fail(f"PWM creation failed: {e}")
    try:
        GPIO.cleanup([PITCH_PIN_BCM, YAW_PIN_BCM])
    except Exception:
        pass
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1)

# ── Phase 1: Center ────────────────────────────────────────────────
print("\n--- Phase 1: Center ---")
try:
    pitch_pwm.start(CENTER_DUTY)
    yaw_pwm.start(CENTER_DUTY)
    ok(f"PWM started at center (duty={CENTER_DUTY}%)")
    print("     Waiting 3s for gimbal to read PWM signal...")
    time.sleep(3)
except Exception as e:
    fail(f"PWM start failed: {e}")

# ── Phase 2: Yaw Sweep ─────────────────────────────────────────────
print("\n--- Phase 2: Yaw Sweep (0° → +30° → -30° → 0°) ---")
yaw_targets = [0, 10, 20, 30, 20, 10, 0, -10, -20, -30, -20, -10, 0]
try:
    for angle in yaw_targets:
        duty = angle_to_duty(angle)
        yaw_pwm.ChangeDutyCycle(duty)
        print(f"     Yaw: {angle:+4.0f}° → duty {duty:.2f}%")
        time.sleep(1.0)
    ok("Yaw sweep complete (13 steps)")
except Exception as e:
    fail(f"Yaw sweep failed: {e}")

# ── Phase 3: Pitch Sweep ───────────────────────────────────────────
print("\n--- Phase 3: Pitch Sweep (0° → +20° → -20° → 0°) ---")
pitch_targets = [0, 10, 20, 10, 0, -10, -20, -10, 0]
try:
    for angle in pitch_targets:
        duty = angle_to_duty(angle)
        pitch_pwm.ChangeDutyCycle(duty)
        print(f"     Pitch: {angle:+4.0f}° → duty {duty:.2f}%")
        time.sleep(1.5)
    ok("Pitch sweep complete (9 steps)")
except Exception as e:
    fail(f"Pitch sweep failed: {e}")

# ── Phase 4: Combined ──────────────────────────────────────────────
print("\n--- Phase 4: Combined Movement ---")
try:
    pitch_pwm.ChangeDutyCycle(angle_to_duty(15))
    yaw_pwm.ChangeDutyCycle(angle_to_duty(20))
    print(f"     Pitch: +15° → duty {angle_to_duty(15):.2f}%")
    print(f"     Yaw:   +20° → duty {angle_to_duty(20):.2f}%")
    time.sleep(2)
    ok("Combined movement complete")
except Exception as e:
    fail(f"Combined movement failed: {e}")

# ── Cleanup ─────────────────────────────────────────────────────────
print("\n--- Cleanup ---")
try:
    pitch_pwm.ChangeDutyCycle(CENTER_DUTY)
    yaw_pwm.ChangeDutyCycle(CENTER_DUTY)
    time.sleep(0.5)
    pitch_pwm.stop()
    yaw_pwm.stop()
    ok("PWM stopped and centered")
except Exception as e:
    # Yahboom carrier board has a known cleanup bug — non-fatal
    ok(f"PWM stopped (cleanup warning: {e})")

try:
    GPIO.cleanup([PITCH_PIN_BCM, YAW_PIN_BCM])
except Exception:
    pass  # Known Yahboom GPIO cleanup issue — non-fatal

# ── Summary ─────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"  {passed} passed, {failed} failed")
print(f"  WATCH THE GIMBAL — did it physically move?")
print(f"  If not: enable RC-0/RC-2 in o323BGCTool GUI")
print(f"{'='*60}")

sys.exit(0 if failed == 0 else 1)
