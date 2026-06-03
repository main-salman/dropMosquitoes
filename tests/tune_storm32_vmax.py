#!/usr/bin/env python3
"""
tune_storm32_vmax.py — Read/write Storm32 motor Vmax via USB serial from Jetson.
Implements: SW-001 (gimbal tuning via o323BGC protocol)

Firmware: v0.90 (confirmed via CMD_GETVERSION)
Protocol: o323BGC serial (FA/FB framing, CRC-CCITT)

Usage:
    python3 tune_storm32_vmax.py                    # Read all motor parameters
    python3 tune_storm32_vmax.py --yaw-vmax 120     # Set yaw Vmax to 120
    python3 tune_storm32_vmax.py --pitch-vmax 150   # Set pitch Vmax to 150
    python3 tune_storm32_vmax.py --all-vmax 100     # Set all motors to 100
    python3 tune_storm32_vmax.py --yaw-vmax 120 --store  # Set AND save to EEPROM
"""
import serial
import struct
import time
import sys
import argparse

PORT = "/dev/ttyACM0"
BAUD = 115200

def crc_ccitt(data):
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc = crc << 1
            crc &= 0xFFFF
    return crc

def build_packet(cmd_id, payload=b''):
    pkt = bytes([0xFA, len(payload), cmd_id]) + payload
    crc = crc_ccitt(pkt)
    pkt += struct.pack('<H', crc)
    return pkt

def send_recv(ser, cmd_id, payload=b'', wait=0.2, read_len=200):
    ser.reset_input_buffer()
    pkt = build_packet(cmd_id, payload)
    ser.write(pkt)
    time.sleep(wait)
    resp = ser.read(read_len)
    return resp

def parse_response(resp):
    if not resp or len(resp) < 3 or resp[0] != 0xFB:
        return None, None, None
    data_len = resp[1]
    cmd = resp[2]
    data = resp[3:3+data_len] if len(resp) >= 3 + data_len else b''
    return cmd, data_len, data

def read_parameter(ser, addr):
    """Read a single parameter by address. Returns (addr_echo, value) or None."""
    payload = struct.pack('<H', addr)
    resp = send_recv(ser, 0x03, payload, wait=0.15)
    if resp:
        cmd, dlen, data = parse_response(resp)
        if cmd == 0x03 and dlen >= 4 and len(data) >= 4:
            addr_echo = struct.unpack('<H', data[0:2])[0]
            value = struct.unpack('<H', data[2:4])[0]
            return addr_echo, value
    return None

def write_parameter(ser, addr, value):
    """Write a single parameter. Returns True on success."""
    payload = struct.pack('<HH', addr, value)
    resp = send_recv(ser, 0x04, payload, wait=0.2)
    if resp:
        cmd, dlen, data = parse_response(resp)
        if cmd == 0x96 and data:
            return data[0] == 0x00  # 0x00 = success
        # Some boards echo back the parameter instead of ACK
        if cmd == 0x04:
            return True
    return False

def store_eeprom(ser):
    """Store parameters to EEPROM. Tries CMD 0x06, then 0x14."""
    for store_cmd in [0x06, 0x14, 0x15]:
        resp = send_recv(ser, store_cmd, wait=0.5)
        if resp:
            cmd, dlen, data = parse_response(resp)
            if cmd == 0x96 and data and data[0] == 0x00:
                return True, store_cmd
    return False, None

# Storm32 v0.90 parameter map (confirmed by probe)
# CMD 0x03 response: FB [len=4] [cmd=0x03] [addr_lo] [addr_hi] [val_lo] [val_hi] [crc]
PARAM_MAP = {
    0: "Pitch P",       1: "Pitch I",       2: "Pitch D",
    3: "Pitch Power",   4: "Roll P",        5: "Roll I",
    6: "Roll D",        7: "Roll Power",    8: "Yaw P",
    9: "Yaw I",         10: "Yaw D",        11: "Yaw Power",
}

VMAX_PARAMS = {
    'pitch': 3,
    'roll': 7,
    'yaw': 11,
}

def main():
    parser = argparse.ArgumentParser(description="Tune Storm32 Vmax via USB serial")
    parser.add_argument('--port', default=PORT, help='Serial port')
    parser.add_argument('--yaw-vmax', type=int, help='Set yaw motor Vmax (0-255)')
    parser.add_argument('--pitch-vmax', type=int, help='Set pitch motor Vmax (0-255)')
    parser.add_argument('--roll-vmax', type=int, help='Set roll motor Vmax (0-255)')
    parser.add_argument('--all-vmax', type=int, help='Set all motors Vmax (0-255)')
    parser.add_argument('--store', action='store_true', default=True,
                        help='Store to EEPROM after write (default: True)')
    parser.add_argument('--no-store', dest='store', action='store_false',
                        help='Do NOT store to EEPROM')
    parser.add_argument('--read-all', action='store_true',
                        help='Read extended parameter range (0-50)')
    args = parser.parse_args()

    print(f"Connecting to {args.port}...")
    try:
        ser = serial.Serial(args.port, BAUD, timeout=1)
        time.sleep(0.5)
        ser.reset_input_buffer()
    except Exception as e:
        print(f"  FAILED: {e}")
        sys.exit(1)

    # --- Read version ---
    resp = send_recv(ser, 0x01, wait=0.2)
    if resp:
        cmd, dlen, data = parse_response(resp)
        if cmd == 0x01 and len(data) >= 2:
            fw_ver = struct.unpack('<H', data[0:2])[0]
            print(f"  Firmware version: v{fw_ver / 100:.2f}")

    # --- Read current PID + Power parameters ---
    max_addr = 50 if args.read_all else 12
    print(f"\n{'='*50}")
    print(f"  Current Motor Parameters")
    print(f"{'='*50}")
    for addr in range(max_addr):
        result = read_parameter(ser, addr)
        if result:
            addr_echo, value = result
            name = PARAM_MAP.get(addr, f"Param-{addr}")
            marker = " ◀ MOTOR POWER" if addr in [3, 7, 11] else ""
            print(f"  [{addr:2d}] {name:20s} = {value:5d}{marker}")
        else:
            name = PARAM_MAP.get(addr, f"Param-{addr}")
            print(f"  [{addr:2d}] {name:20s} → no response")

    # --- Write Vmax if requested ---
    writes = {}
    if args.all_vmax is not None:
        writes[3] = args.all_vmax
        writes[7] = args.all_vmax
        writes[11] = args.all_vmax
    if args.pitch_vmax is not None:
        writes[3] = args.pitch_vmax
    if args.roll_vmax is not None:
        writes[7] = args.roll_vmax
    if args.yaw_vmax is not None:
        writes[11] = args.yaw_vmax

    if writes:
        print(f"\n{'='*50}")
        print(f"  Writing Parameters")
        print(f"{'='*50}")
        for addr, value in writes.items():
            name = PARAM_MAP.get(addr, f"Param-{addr}")
            # Read current value first
            current = read_parameter(ser, addr)
            cur_val = current[1] if current else "?"
            
            ok = write_parameter(ser, addr, value)
            status = "✅" if ok else "❌"
            print(f"  {status} [{addr:2d}] {name}: {cur_val} → {value}")

            # Verify write
            time.sleep(0.1)
            verify = read_parameter(ser, addr)
            if verify:
                ver_val = verify[1]
                match = "✅ verified" if ver_val == value else f"❌ got {ver_val}"
                print(f"       Verify: {match}")

        # Store to EEPROM
        if args.store:
            print(f"\n  Storing to EEPROM...")
            ok, cmd_used = store_eeprom(ser)
            if ok:
                print(f"  ✅ Saved to EEPROM (CMD 0x{cmd_used:02X})")
            else:
                print(f"  ❌ EEPROM store failed (may need power cycle)")
                print(f"     Parameters are active but may not survive reboot")

        # Re-read to confirm
        print(f"\n  Final values:")
        for addr in [3, 7, 11]:
            result = read_parameter(ser, addr)
            if result:
                name = PARAM_MAP.get(addr, f"Param-{addr}")
                print(f"    [{addr:2d}] {name:20s} = {result[1]}")

    ser.close()
    print("\nDone.")

if __name__ == '__main__':
    main()
