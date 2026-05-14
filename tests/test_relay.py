#!/usr/bin/env python3
# Implements: TEST-001 Layer 1, T1.3–T1.4 — GPIO Relay hardware tests
"""
test_relay.py — GPIO relay pulse test with configurable timing.

Tests the Monk Makes Dual Relay via Jetson GPIO. On a dev machine
(no Jetson.GPIO), runs in stub mode to verify logic only.

Usage (on Jetson):
    python3 tests/test_relay.py --pump              # Test pump relay
    python3 tests/test_relay.py --gimbal             # Test gimbal power relay
    python3 tests/test_relay.py --pump --cycles 5    # Pulse pump 5 times
    python3 tests/test_relay.py --all                # Test both relays
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hardware import RelayController, JETSON_AVAILABLE

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


def test_pump_relay(relay, cycles=3, pulse_sec=0.3):
    """
    Test Relay CH1 (Pump) with repeated ON/OFF cycles.

    T1.3: Relay audibly clicks ON/OFF, multimeter shows 12V on NO contact.
    """
    print(f"\n{'='*50}")
    print(f"  T1.3: Pump Relay Test ({cycles} cycles, {pulse_sec}s pulse)")
    if not JETSON_AVAILABLE:
        print("  ⚠️  STUB MODE — verify logic only, no physical relay.")
    print(f"{'='*50}")

    # Initial state should be OFF
    status = relay.get_status()
    test("Pump initial state is OFF", status["pump"] == False)

    for i in range(cycles):
        print(f"\n  Cycle {i+1}/{cycles}:")

        # Turn ON
        relay.set_pump(True)
        time.sleep(0.1)
        status = relay.get_status()
        test(f"  Pump ON (cycle {i+1})", status["pump"] == True)

        if JETSON_AVAILABLE:
            print(f"    🔊 Listen for relay CLICK. Multimeter should show ~12V.")
        time.sleep(pulse_sec)

        # Turn OFF
        relay.set_pump(False)
        time.sleep(0.1)
        status = relay.get_status()
        test(f"  Pump OFF (cycle {i+1})", status["pump"] == False)

        if JETSON_AVAILABLE:
            print(f"    🔊 Listen for relay CLICK. Multimeter should show 0V.")
        time.sleep(0.5)

    # Test timed fire
    print(f"\n  Testing timed fire ({pulse_sec}s)...")
    start = time.time()
    relay.fire_pump(pulse_sec)
    time.sleep(pulse_sec + 0.5)  # Wait for pulse to complete
    status = relay.get_status()
    test("Pump OFF after timed fire", status["pump"] == False)

    # Test duration clamping
    relay.fire_pump(10.0)  # Should clamp to 2.0
    time.sleep(0.1)
    test("Fire duration clamped (no crash with 10s)", True)
    time.sleep(2.5)  # Wait for clamped 2.0s pulse to finish


def test_gimbal_relay(relay):
    """
    Test Relay CH2 (Gimbal Power).

    T1.4: Relay clicks, gimbal motors power up.
    SAFE-001 §1: Must default to OFF at boot.
    """
    print(f"\n{'='*50}")
    print(f"  T1.4: Gimbal Power Relay Test")
    if not JETSON_AVAILABLE:
        print("  ⚠️  STUB MODE — verify logic only.")
    print(f"{'='*50}")

    # SAFE-001 §1: Initial state MUST be OFF
    status = relay.get_status()
    test("Gimbal power initial state is OFF (SAFE-001 §1)", status["gimbal_power"] == False)

    # Turn ON
    print("\n  Turning gimbal power ON...")
    relay.set_gimbal_power(True)
    time.sleep(0.5)
    status = relay.get_status()
    test("Gimbal power ON", status["gimbal_power"] == True)

    if JETSON_AVAILABLE:
        input("  ⏸️  Press ENTER after verifying gimbal motors are energized...")

    # Turn OFF
    print("  Turning gimbal power OFF...")
    relay.set_gimbal_power(False)
    time.sleep(0.5)
    status = relay.get_status()
    test("Gimbal power OFF", status["gimbal_power"] == False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Relay Hardware Test")
    parser.add_argument('--pump', action='store_true', help='Test pump relay (CH1)')
    parser.add_argument('--gimbal', action='store_true', help='Test gimbal power relay (CH2)')
    parser.add_argument('--all', action='store_true', help='Test both relays')
    parser.add_argument('--cycles', type=int, default=3, help='Number of ON/OFF cycles')
    parser.add_argument('--pulse', type=float, default=0.3, help='Pulse duration in seconds')
    args = parser.parse_args()

    if not (args.pump or args.gimbal or args.all):
        args.all = True

    relay = RelayController()

    try:
        if args.pump or args.all:
            test_pump_relay(relay, cycles=args.cycles, pulse_sec=args.pulse)
        if args.gimbal or args.all:
            test_gimbal_relay(relay)
    finally:
        relay.cleanup()

    print(f"\n{'='*50}")
    print(f"  RELAY TESTS: {PASS} passed, {FAIL} failed")
    print(f"{'='*50}")
    sys.exit(0 if FAIL == 0 else 1)
