#!/usr/bin/env python3
# Implements: TEST-001 Layer 1, T1.5–T1.6 — Serial UART tests
"""
test_serial.py — Serial loopback and Storm32 handshake test.

Tests the UART connection to the Storm32 BGC board. Includes:
  - Loopback test (TX→RX with wire jumper)
  - Storm32 version query
  - Angle command round-trip

Usage (on Jetson):
    python3 tests/test_serial.py --loopback           # TX→RX loopback test
    python3 tests/test_serial.py --storm32             # Storm32 handshake
    python3 tests/test_serial.py --sweep               # Full angle sweep test
"""

import argparse
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hardware import GimbalController, YAW_LIMIT, PITCH_LIMIT

PASS = 0
FAIL = 0

try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False


def test(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name} — {detail}")


def test_loopback(port, baud=115200):
    """
    T1.5: Serial loopback test. Requires a physical wire jumper
    connecting TX to RX on the Jetson UART header.
    """
    print(f"\n{'='*50}")
    print(f"  T1.5: Serial Loopback Test")
    print(f"  Port: {port} @ {baud}")
    print(f"  ⚠️  Requires TX→RX jumper wire on UART header!")
    print(f"{'='*50}")

    if not SERIAL_AVAILABLE:
        print("  ❌ pyserial not installed. Skipping.")
        return

    try:
        ser = serial.Serial(port, baud, timeout=1.0)
    except serial.SerialException as e:
        test("Serial port opens", False, str(e))
        return

    test("Serial port opens", ser.is_open)

    # Send test patterns
    patterns = [b'\xAA\x55', b'\x00\xFF', b'HELLO', b'\xFA\x0E\x11']
    for pat in patterns:
        ser.reset_input_buffer()
        ser.write(pat)
        time.sleep(0.1)
        received = ser.read(len(pat))
        test(f"Loopback {pat.hex()} → {received.hex()}", received == pat,
             f"sent {pat.hex()}, got {received.hex()}")

    ser.close()


def test_storm32(port, baud=115200):
    """
    T1.6: Storm32 BGC board handshake test.
    Sends a GetVersion command and checks for a valid response.
    """
    print(f"\n{'='*50}")
    print(f"  T1.6: Storm32 Handshake Test")
    print(f"  Port: {port} @ {baud}")
    print(f"{'='*50}")

    if not SERIAL_AVAILABLE:
        print("  ❌ pyserial not installed. Skipping.")
        return

    try:
        ser = serial.Serial(port, baud, timeout=2.0)
    except serial.SerialException as e:
        test("Serial port opens", False, str(e))
        return

    test("Serial port opens", ser.is_open)

    # Storm32 GetVersion command (o323BGC protocol)
    # 0xFA = start, 0x00 = data_len, 0x01 = CMD_GET_VERSION
    cmd = bytes([0xFA, 0x00, 0x01, 0x01])  # Last byte = CRC
    ser.reset_input_buffer()
    ser.write(cmd)
    time.sleep(0.5)

    response = ser.read(64)
    test("Storm32 responded", len(response) > 0,
         "No response — check wiring and power")

    if len(response) > 3:
        test("Response has valid start marker (0xFB)",
             response[0] == 0xFB,
             f"got 0x{response[0]:02X}")
        print(f"    Raw response ({len(response)} bytes): {response.hex()}")

    # Try sending a center command
    print("\n  Sending center command (pitch=0, yaw=0)...")
    g = GimbalController()
    if g._serial and g._serial.is_open:
        g._serial.close()
    # Use our opened serial
    g._serial = ser
    g.set_angles(0.0, 0.0)
    time.sleep(1)
    test("Center command sent without error", True)

    ser.close()


def test_sweep():
    """
    Sweep the gimbal through its full range to verify mechanical response.
    """
    print(f"\n{'='*50}")
    print(f"  Gimbal Sweep Test (Yaw ±{YAW_LIMIT}°, Pitch ±{PITCH_LIMIT}°)")
    print(f"{'='*50}")

    g = GimbalController()

    if not g.get_status()["connected"]:
        print("  ⚠️  STUB MODE — verifying logic only.")

    # Center first
    g.center()
    time.sleep(0.5)

    # Yaw sweep
    print("\n  Yaw sweep: 0° → +max → -max → 0°")
    steps = [0, YAW_LIMIT/2, YAW_LIMIT, YAW_LIMIT/2, 0,
             -YAW_LIMIT/2, -YAW_LIMIT, -YAW_LIMIT/2, 0]
    for yaw in steps:
        g.set_angles(0, yaw)
        status = g.get_status()
        test(f"Yaw → {yaw:+.0f}°", status["yaw"] == yaw, f"got {status['yaw']}")
        time.sleep(0.3)

    # Pitch sweep
    print("\n  Pitch sweep: 0° → +max → -max → 0°")
    steps = [0, PITCH_LIMIT/2, PITCH_LIMIT, 0, -PITCH_LIMIT, 0]
    for pitch in steps:
        g.set_angles(pitch, 0)
        status = g.get_status()
        test(f"Pitch → {pitch:+.0f}°", status["pitch"] == pitch, f"got {status['pitch']}")
        time.sleep(0.3)

    # Endstop enforcement
    print("\n  Endstop enforcement:")
    g.set_angles(0, 999)
    test(f"Yaw clamped to +{YAW_LIMIT}°", g.get_status()["yaw"] == YAW_LIMIT)
    g.set_angles(0, -999)
    test(f"Yaw clamped to -{YAW_LIMIT}°", g.get_status()["yaw"] == -YAW_LIMIT)
    g.set_angles(999, 0)
    test(f"Pitch clamped to +{PITCH_LIMIT}°", g.get_status()["pitch"] == PITCH_LIMIT)
    g.set_angles(-999, 0)
    test(f"Pitch clamped to -{PITCH_LIMIT}°", g.get_status()["pitch"] == -PITCH_LIMIT)

    g.center()
    g.cleanup()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Serial UART Test")
    parser.add_argument('--loopback', action='store_true', help='TX→RX loopback test')
    parser.add_argument('--storm32', action='store_true', help='Storm32 handshake test')
    parser.add_argument('--sweep', action='store_true', help='Full gimbal angle sweep')
    parser.add_argument('--port', default='/dev/ttyTHS0', help='Serial port')
    parser.add_argument('--baud', type=int, default=115200, help='Baud rate')
    args = parser.parse_args()

    if not (args.loopback or args.storm32 or args.sweep):
        args.sweep = True  # Default: sweep test (works in stub mode)

    if args.loopback:
        test_loopback(args.port, args.baud)
    if args.storm32:
        test_storm32(args.port, args.baud)
    if args.sweep:
        test_sweep()

    print(f"\n{'='*50}")
    print(f"  SERIAL TESTS: {PASS} passed, {FAIL} failed")
    print(f"{'='*50}")
    sys.exit(0 if FAIL == 0 else 1)
