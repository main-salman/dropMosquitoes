# Implements: HW-001 §5.4 Rev O — Pico W solenoid gate timer
# MicroPython main.py — copy to Pico root after flashing MicroPython UF2.
#
# Wiring: GP15 → 220Ω → IRLB8721 Gate; 10k Gate→GND; Source→GND; Drain→coil(−)
# Protocol (USB CDC, newline-terminated, case-insensitive):
#   FIRE <ms> | OPEN | CLOSE | PING

from machine import Pin
import sys
import time

GATE_PIN = 15
gate = Pin(GATE_PIN, Pin.OUT, value=0)  # SAFE: closed at boot


def _pulse_ms(ms):
    ms = max(1, min(int(ms), 2000))
    gate.value(1)
    time.sleep_ms(ms)
    gate.value(0)
    return ms


def handle(line):
    parts = line.strip().upper().split()
    if not parts:
        return
    cmd = parts[0]
    try:
        if cmd == "PING":
            print("PONG")
        elif cmd == "CLOSE":
            gate.value(0)
            print("OK CLOSE")
        elif cmd == "OPEN":
            gate.value(1)
            print("OK OPEN")
        elif cmd == "FIRE":
            ms = int(float(parts[1])) if len(parts) > 1 else 5
            done = _pulse_ms(ms)
            print("OK FIRE", done)
        else:
            print("ERR UNKNOWN", cmd)
    except Exception as e:
        gate.value(0)
        print("ERR", e)


print("PICO_SOLENOID READY GP15")
gate.value(0)

while True:
    try:
        line = sys.stdin.readline()
        if line:
            handle(line)
    except Exception as e:
        gate.value(0)
        print("ERR", e)
        time.sleep_ms(50)
