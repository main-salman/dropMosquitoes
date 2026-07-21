#!/usr/bin/env python3
# Implements: TEST-001 — GPIO pinmux / voltage verification for BCM 17 & BCM 27
"""
test_gpio_pinmux.py — Verify PADCTL registers and GPIO toggle on Yahboom Orin Nano.

Run ON THE JETSON as root:
    sudo python3 tests/test_gpio_pinmux.py

Rev C (HW-001 §5.4): BCM 27 drives the IRLB8721 gate directly (+ 4.7kΩ pull-up
from T17). Monk Makes Relay CH2 is NOT used for the solenoid.

Probe guide:
  - T11 (pump): expect ~3.3V when pump ON (relay IN may read ~1.5V — OK).
  - T13 (BCM 27): may read ~1.6V even when HIGH — weak Yahboom GPIO; do not
    use T13 alone to judge solenoid drive.
  - Gate junction (G pin): probe HERE — ~0V when CLOSED, ~3.3V when OPEN.
"""

import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PADCTL_BASE = 0x02430000
REGS = {
    "PR.04 / BCM 17 / Terminal 11 (pump relay)": 0x98,
    "PR.05 / BCM 16 / Terminal 36 (solenoid SIG)": 0x90,
    "PQ.05 / BCM 5 / Terminal 29 (Relay CH2 / module 12V)": 0x68,
}
GPIO_OUTPUT = 0x05


def read_regs():
    import mmap
    with open("/dev/mem", "r+b") as f:
        mem = mmap.mmap(f.fileno(), 0x10000, offset=PADCTL_BASE)
        vals = {name: struct.unpack("<I", mem[off:off + 4])[0] for name, off in REGS.items()}
        mem.close()
    return vals


def main():
    print("=" * 60)
    print("  GPIO Pinmux Diagnostic — BCM 17 & BCM 27 (Rev C MOSFET)")
    print("=" * 60)

    if os.geteuid() != 0:
        print("\n  ⚠️  Not running as root — PADCTL writes will fail.")
        print("     Run: sudo python3 tests/test_gpio_pinmux.py\n")

    print("\n--- PADCTL registers (before) ---")
    before = read_regs()
    for name, val in before.items():
        ok = val == GPIO_OUTPUT
        mark = "✅" if ok else "❌"
        print(f"  {mark} {name}: {val:#010x}  (want {GPIO_OUTPUT:#010x})")

    from hardware import RelayController, configure_push_pull, JETSON_AVAILABLE

    if not JETSON_AVAILABLE:
        print("\n  ❌ Jetson.GPIO not available — run on the Jetson.")
        sys.exit(1)

    configure_push_pull()
    relay = RelayController()

    print("\n--- PADCTL registers (after configure_push_pull) ---")
    after = read_regs()
    for name, val in after.items():
        ok = val == GPIO_OUTPUT
        mark = "✅" if ok else "❌"
        print(f"  {mark} {name}: {val:#010x}")

    print("\n--- GPIO toggle (3s each) ---")
    print("  Pump ON 3s → probe T11 (~3.3V or ~1.5V at relay IN is OK)")
    relay.set_pump(True)
    time.sleep(3)
    relay.set_pump(False)
    time.sleep(1)

    print("  Solenoid OPEN 3s → probe GATE JUNCTION (~3.3V), not T13")
    print("  (T13 may stay ~1.6V; 4.7kΩ pull-up from T17 lifts gate to ~3.3V)")
    relay.set_solenoid(True)
    time.sleep(3)
    relay.set_solenoid(False)

    relay.cleanup()
    print("\n  Done. Gate junction should read ~0V after cleanup (solenoid CLOSED).")
    print("  If gate never drops to ~0V, BCM 27 is not pulling LOW — check PADCTL")
    print("  (both registers must be 0x00000005) and run sentry as root.")


if __name__ == "__main__":
    main()
