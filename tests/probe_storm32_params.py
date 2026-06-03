#!/usr/bin/env python3
"""
probe_storm32_params.py — Read Storm32 BGC parameters over USB serial.
Discovers the parameter structure so we can find and adjust Vmax.
"""
import serial
import struct
import time
import sys

PORT = "/dev/ttyACM0"
BAUD = 115200

def build_packet(cmd_id, payload=b''):
    """Build an o323BGC protocol packet."""
    pkt = bytes([0xFA, len(payload), cmd_id]) + payload
    pkt += bytes([0x00, 0x00])  # CRC (board doesn't check)
    return pkt

def send_recv(ser, cmd_id, payload=b'', wait=0.3, read_len=500):
    """Send a command and read the response."""
    ser.reset_input_buffer()
    pkt = build_packet(cmd_id, payload)
    ser.write(pkt)
    time.sleep(wait)
    return ser.read(read_len)

# ── Connect ─────────────────────────────────────────────────────────
print(f"Connecting to {PORT}...")
try:
    ser = serial.Serial(PORT, BAUD, timeout=1)
    time.sleep(0.5)
    ser.reset_input_buffer()
    print(f"  Connected on {PORT}")
except Exception as e:
    print(f"  FAILED: {e}")
    sys.exit(1)

# ── CMD_GET_VERSION (0x01) ──────────────────────────────────────────
print("\n--- CMD_GET_VERSION (0x01) ---")
resp = send_recv(ser, 0x01)
if resp:
    print(f"  Response ({len(resp)} bytes): {resp.hex().upper()}")
    # Parse: FB + len + cmd + version_data
    if len(resp) >= 5 and resp[0] == 0xFB:
        data_len = resp[1]
        cmd = resp[2]
        print(f"  Header: FB, len={data_len}, cmd=0x{cmd:02X}")
        if len(resp) > 5:
            version_data = resp[3:3+data_len]
            print(f"  Version data: {version_data.hex().upper()}")
            # Try to decode as uint16 values
            if len(version_data) >= 4:
                v1, v2 = struct.unpack('<HH', version_data[:4])
                print(f"  Firmware: {v1}.{v2}")
else:
    print("  No response")

# ── Probe all commands (0x01 - 0x20) ───────────────────────────────
print("\n--- Probing commands 0x01-0x20 ---")
for cmd_id in range(0x01, 0x21):
    resp = send_recv(ser, cmd_id, wait=0.15, read_len=500)
    if resp and len(resp) > 0:
        tag = ""
        if resp[0] == 0xFB and len(resp) >= 3:
            data_len = resp[1]
            rcmd = resp[2]
            tag = f" [FB len={data_len} cmd=0x{rcmd:02X}]"
        print(f"  CMD 0x{cmd_id:02X}: {len(resp):3d} bytes{tag} → {resp[:40].hex().upper()}")

# ── Try CMD_GETPARAMETERS with larger read ─────────────────────────
print("\n--- Attempting full parameter dump ---")
for cmd_id in [0x02, 0x03, 0x05, 0x14, 0x15]:
    resp = send_recv(ser, cmd_id, wait=0.5, read_len=2000)
    if resp and len(resp) > 10:
        print(f"\n  CMD 0x{cmd_id:02X}: {len(resp)} bytes total")
        # Print header
        if resp[0] == 0xFB:
            data_len = resp[1]
            rcmd = resp[2]
            data = resp[3:3+data_len]
            print(f"  Header: FB, len={data_len}, cmd=0x{rcmd:02X}")
            print(f"  Payload ({len(data)} bytes):")
            # Print as hex dump (16 bytes per line)
            for i in range(0, len(data), 16):
                chunk = data[i:i+16]
                hex_str = ' '.join(f'{b:02X}' for b in chunk)
                ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
                print(f"    {i:04X}: {hex_str:<48s}  {ascii_str}")

ser.close()
print("\nDone.")
