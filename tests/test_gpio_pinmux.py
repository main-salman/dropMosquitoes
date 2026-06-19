#!/usr/bin/env python3
# Implements: TEST-001 — GPIO pinmux / voltage verification for BCM 17 & BCM 27
"""
test_gpio_pinmux.py — Verify PADCTL registers and GPIO HIGH voltage on Yahboom Orin Nano.

Run ON THE JETSON as root:
    sudo python3 tests/test_gpio_pinmux.py

Expected: Terminal 11 ~1.5V OK for relay IN; Terminal 13 same. Gate voltage (~3.3V)
requires Relay CH2 path per HW-001 §5.4 Rev B — do not measure T13 as gate voltage.
"""

import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PADCTL_BASE = 0x02430000
REGS = {
    "PR.04 / BCM 17 / Terminal 11 (pump)": 0x98,
    "PY.00 / BCM 27 / Terminal 13 (Relay CH2)": 0xD030,
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
    print("  GPIO Pinmux Diagnostic — BCM 17 & BCM 27")
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

    print("\n--- GPIO toggle (3s each — probe Terminal 11 & 13 with multimeter) ---")
    print("  Pump ON 3s → Terminal 11 should read ~3.3V")
    relay.set_pump(True)
    time.sleep(3)
    relay.set_pump(False)
    time.sleep(1)

    print("  Solenoid OPEN 3s → Terminal 13 should read ~3.3V")
    relay.set_solenoid(True)
    time.sleep(3)
    relay.set_solenoid(False)

    relay.cleanup()
    print("\n  Done. If multimeter still shows ~1.5V, PADCTL write did not stick.")
    print("  Check register values above — both must be 0x00000005.")


if __name__ == "__main__":
    main()
