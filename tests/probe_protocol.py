#!/usr/bin/env python3
"""
Test Storm32 using the CORRECT protocol from the working ROS2 driver.

Protocol: o323BGC
- Start byte: 0xFA (outgoing)
- Response start: 0xFB (incoming)
- CMD_SET_ANGLES = 0x11
- Angles encoded as float32 (IEEE 754, little-endian)
- CRC: 2 bytes, hardcoded to 0x00 0x00 (board doesn't check)
- Flags: 0x00 0x00 (unlimited) or 0x07 0x00 (limited)

Packet: [0xFA] [payload_len] [cmd_id] [pitch_f32] [roll_f32] [yaw_f32] [flags_2b] [crc_lo] [crc_hi]
"""
import serial
import struct
import time

def float_to_bytes_le(value):
    """Convert float to 4 little-endian bytes (same as the ROS2 driver)."""
    return list(struct.pack('<f', value))

def build_set_angles(pitch_deg, roll_deg, yaw_deg, unlimited=True):
    """Build a CMD_SET_ANGLES (0x11) packet using float32 angles."""
    CMD_SET_ANGLES = 0x11
    
    data = []
    data.extend(float_to_bytes_le(pitch_deg))
    data.extend(float_to_bytes_le(roll_deg))
    data.extend(float_to_bytes_le(yaw_deg))
    
    # Flags: 0x00 0x00 = unlimited, 0x07 0x00 = limited by RC settings
    if unlimited:
        data.extend([0x00, 0x00])
    else:
        data.extend([0x07, 0x00])
    
    payload_len = len(data)  # Should be 14 (4+4+4+2)
    
    # Build message: header + len + cmd + payload + crc(2 bytes)
    msg = [0xFA, payload_len, CMD_SET_ANGLES]
    msg.extend(data)
    msg.extend([0x00, 0x00])  # CRC - board doesn't check
    
    return bytes(msg)

def hex_dump(data):
    return " ".join(f"{b:02X}" for b in data)

print("=" * 60)
print("  Storm32 CORRECT Protocol Test")
print("  Using ROS2 driver format: 0xFA + float32 angles")
print("=" * 60)

ser = serial.Serial("/dev/ttyACM0", 115200, timeout=2.0)
time.sleep(0.5)
ser.reset_input_buffer()

# Test 0: Get version first to confirm comms
ver_cmd = bytes([0xFA, 0x00, 0x01, 0x00, 0x00])  # cmd=0x01, no payload, crc=0x00 0x00
print(f"\n--- Test 0: GetVersion ---")
print(f"  TX: {hex_dump(ver_cmd)}")
ser.write(ver_cmd)
time.sleep(0.5)
resp = ser.read(256)
print(f"  RX ({len(resp)} bytes): {hex_dump(resp)}")
if resp:
    print(f"  ASCII: {repr(resp)}")

# Test 1: Center (pitch=0, yaw=0)
packet = build_set_angles(0.0, 0.0, 0.0)
print(f"\n--- Test 1: Center (pitch=0, yaw=0) ---")
print(f"  TX ({len(packet)} bytes): {hex_dump(packet)}")
ser.reset_input_buffer()
ser.write(packet)
time.sleep(2)
resp = ser.read(256)
print(f"  RX ({len(resp)} bytes): {hex_dump(resp)}")
if resp:
    print(f"  ASCII: {repr(resp)}")

# Test 2: Yaw +30
packet = build_set_angles(0.0, 0.0, 30.0)
print(f"\n--- Test 2: Yaw +30 ---")
print(f"  TX ({len(packet)} bytes): {hex_dump(packet)}")
ser.reset_input_buffer()
ser.write(packet)
time.sleep(3)
resp = ser.read(256)
print(f"  RX ({len(resp)} bytes): {hex_dump(resp)}")
if resp:
    print(f"  ASCII: {repr(resp)}")

# Test 3: Yaw -30
packet = build_set_angles(0.0, 0.0, -30.0)
print(f"\n--- Test 3: Yaw -30 ---")
print(f"  TX ({len(packet)} bytes): {hex_dump(packet)}")
ser.reset_input_buffer()
ser.write(packet)
time.sleep(3)
resp = ser.read(256)
print(f"  RX ({len(resp)} bytes): {hex_dump(resp)}")
if resp:
    print(f"  ASCII: {repr(resp)}")

# Test 4: Pitch +15
packet = build_set_angles(15.0, 0.0, 0.0)
print(f"\n--- Test 4: Pitch +15 ---")
print(f"  TX ({len(packet)} bytes): {hex_dump(packet)}")
ser.reset_input_buffer()
ser.write(packet)
time.sleep(3)
resp = ser.read(256)
print(f"  RX ({len(resp)} bytes): {hex_dump(resp)}")
if resp:
    print(f"  ASCII: {repr(resp)}")

# Test 5: Pitch -15
packet = build_set_angles(-15.0, 0.0, 0.0)
print(f"\n--- Test 5: Pitch -15 ---")
print(f"  TX ({len(packet)} bytes): {hex_dump(packet)}")
ser.reset_input_buffer()
ser.write(packet)
time.sleep(3)
resp = ser.read(256)
print(f"  RX ({len(resp)} bytes): {hex_dump(resp)}")
if resp:
    print(f"  ASCII: {repr(resp)}")

# Test 6: Center again
packet = build_set_angles(0.0, 0.0, 0.0)
print(f"\n--- Test 6: Center ---")
print(f"  TX ({len(packet)} bytes): {hex_dump(packet)}")
ser.reset_input_buffer()
ser.write(packet)
time.sleep(2)
resp = ser.read(256)
print(f"  RX ({len(resp)} bytes): {hex_dump(resp)}")
if resp:
    print(f"  ASCII: {repr(resp)}")

ser.close()
print("\n" + "=" * 60)
print("  DONE — did the gimbal physically move?")
print("=" * 60)
