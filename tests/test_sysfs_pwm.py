#!/usr/bin/env python3
"""
test_sysfs_pwm.py — Direct sysfs PWM test (bypasses Jetson.GPIO entirely).

Writes directly to /sys/class/pwm/ to drive hardware PWM channels.
This eliminates Jetson.GPIO as a variable in debugging.

Requires root (sudo) for /dev/mem pinmux writes.
PWM sysfs writes work without root if permissions allow.
"""
import os
import sys
import time

# ── Pinmux configuration ───────────────────────────────────────────
print("--- Step 1: Pinmux ---")
try:
    import mmap
    import struct
    with open("/dev/mem", "r+b") as f:
        mem = mmap.mmap(f.fileno(), 0x10000, offset=0x2430000)
        mem[0x4080:0x4084] = struct.pack("<I", 0x5)  # BCM12 (Pin 32) → output
        mem[0x4040:0x4044] = struct.pack("<I", 0x4)  # BCM13 (Pin 33) → output
        mem.close()
    print("  ✅ Pinmux set to output for BCM 12 and BCM 13")
except PermissionError:
    print("  ❌ Need root for /dev/mem. Run with: sudo python3 test_sysfs_pwm.py")
    sys.exit(1)
except Exception as e:
    print(f"  ❌ Pinmux failed: {e}")
    sys.exit(1)

# ── sysfs PWM helpers ──────────────────────────────────────────────
def pwm_export(chip):
    """Export pwm0 channel on the given chip if not already exported."""
    base = f"/sys/class/pwm/pwmchip{chip}"
    pwm_path = f"{base}/pwm0"
    if not os.path.exists(pwm_path):
        with open(f"{base}/export", "w") as f:
            f.write("0")
        time.sleep(0.1)
    return pwm_path


def pwm_configure(chip, period_ns, duty_ns):
    """Configure and enable a PWM channel."""
    pwm_path = pwm_export(chip)
    # Disable first (required to change period)
    with open(f"{pwm_path}/enable", "w") as f:
        f.write("0")
    with open(f"{pwm_path}/period", "w") as f:
        f.write(str(period_ns))
    with open(f"{pwm_path}/duty_cycle", "w") as f:
        f.write(str(duty_ns))
    with open(f"{pwm_path}/enable", "w") as f:
        f.write("1")
    return pwm_path


def pwm_set_duty(chip, duty_ns):
    """Change duty cycle on a running PWM channel."""
    with open(f"/sys/class/pwm/pwmchip{chip}/pwm0/duty_cycle", "w") as f:
        f.write(str(duty_ns))


def pwm_disable(chip):
    """Disable a PWM channel."""
    try:
        with open(f"/sys/class/pwm/pwmchip{chip}/pwm0/enable", "w") as f:
            f.write("0")
    except Exception:
        pass


def angle_to_ns(angle_deg, rc_range=45.0):
    """Convert angle to PWM pulse width in nanoseconds (1000-2000 μs range)."""
    clamped = max(-rc_range, min(rc_range, angle_deg))
    normalized = (clamped + rc_range) / (2.0 * rc_range)  # 0.0 → 1.0
    pulse_us = 1000.0 + normalized * 1000.0  # 1000 → 2000 μs
    return int(pulse_us * 1000)  # → nanoseconds


# ── Constants ──────────────────────────────────────────────────────
PERIOD_NS = 20_000_000   # 20ms = 50Hz
CENTER_NS = 1_500_000    # 1500μs = center

# PWM chip mapping (from Jetson.GPIO internal data):
#   BCM 12 (Pin 32, Pitch)  → pwmchip3
#   BCM 13 (Pin 33, Yaw)    → pwmchip2
PITCH_CHIP = 3
YAW_CHIP = 2

# ── Setup ──────────────────────────────────────────────────────────
print("\n--- Step 2: sysfs PWM setup ---")
try:
    pwm_configure(PITCH_CHIP, PERIOD_NS, CENTER_NS)
    print(f"  ✅ pwmchip{PITCH_CHIP}/pwm0 (Pitch): {PERIOD_NS}ns period, {CENTER_NS}ns duty, ENABLED")
except Exception as e:
    print(f"  ❌ Pitch PWM failed: {e}")
    sys.exit(1)

try:
    pwm_configure(YAW_CHIP, PERIOD_NS, CENTER_NS)
    print(f"  ✅ pwmchip{YAW_CHIP}/pwm0 (Yaw): {PERIOD_NS}ns period, {CENTER_NS}ns duty, ENABLED")
except Exception as e:
    print(f"  ❌ Yaw PWM failed: {e}")
    sys.exit(1)

print("  Waiting 3 seconds at center position...")
time.sleep(3)

# ── Yaw sweep ──────────────────────────────────────────────────────
print("\n--- Step 3: Yaw Sweep ---")
for angle in [0, 15, 30, 15, 0, -15, -30, -15, 0]:
    ns = angle_to_ns(angle)
    pwm_set_duty(YAW_CHIP, ns)
    print(f"  ✅ Yaw {angle:+4.0f}° → {ns:>7d}ns ({ns/1000:.0f}μs)")
    time.sleep(1.0)

# ── Pitch sweep ────────────────────────────────────────────────────
print("\n--- Step 4: Pitch Sweep ---")
for angle in [0, 10, 20, 10, 0, -10, -20, -10, 0]:
    ns = angle_to_ns(angle)
    pwm_set_duty(PITCH_CHIP, ns)
    print(f"  ✅ Pitch {angle:+4.0f}° → {ns:>7d}ns ({ns/1000:.0f}μs)")
    time.sleep(1.0)

# ── Cleanup ────────────────────────────────────────────────────────
print("\n--- Cleanup ---")
pwm_set_duty(YAW_CHIP, CENTER_NS)
pwm_set_duty(PITCH_CHIP, CENTER_NS)
time.sleep(0.5)
pwm_disable(YAW_CHIP)
pwm_disable(PITCH_CHIP)
print("  ✅ PWM disabled")

print(f"\n{'='*60}")
print("  DONE — did the gimbal physically move?")
print("  If NO: the Storm32 RC inputs may need to be enabled")
print("  in the o323BGCTool GUI on a Windows PC.")
print(f"{'='*60}")
