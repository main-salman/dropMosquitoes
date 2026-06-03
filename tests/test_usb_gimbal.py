#!/usr/bin/env python3
import time
import sys
import os
import serial
import struct

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import Jetson.GPIO as GPIO
    from hardware import RelayController, configure_push_pull
    JETSON_AVAILABLE = True
except ImportError:
    JETSON_AVAILABLE = False
    print("Jetson.GPIO not available, running in STUB/DRY-RUN mode.")

def build_storm32_packet(pitch_deg: float, yaw_deg: float) -> bytes:
    pitch_val = int(pitch_deg * 100)
    roll_val = 0
    yaw_val = int(yaw_deg * 100)
    payload = struct.pack('<hhhHH', pitch_val, roll_val, yaw_val, 0, 0)
    payload += b'\x00' * (14 - len(payload))
    header = bytes([0xFA, len(payload), 0x11])
    packet = header + payload
    crc = 0
    for b in packet[1:]:
        crc ^= b
    return packet + bytes([crc])

def test_usb_movement():
    port = "/dev/ttyACM0"
    baud = 115200
    
    try:
        print(f"Opening serial port {port} at {baud} baud...")
        ser = serial.Serial(port, baud, timeout=1.0)
        print(f"Successfully opened {port}!")
    except Exception as e:
        print(f"❌ Failed to open serial port {port}: {e}")
        sys.exit(1)
        
    try:
        # Move Yaw to +20, then -20, then 0
        yaw_targets = [20.0, -20.0, 0.0]
        for y in yaw_targets:
            packet = build_storm32_packet(0.0, y)
            print(f"Aiming: Pitch=0.00, Yaw={y:.2f} -> sending packet: {packet.hex().upper()}")
            ser.write(packet)
            time.sleep(2.0)
            
        # Move Pitch to +10, then -10, then 0
        pitch_targets = [10.0, -10.0, 0.0]
        for p in pitch_targets:
            packet = build_storm32_packet(p, 0.0)
            print(f"Aiming: Pitch={p:.2f}, Yaw=0.00 -> sending packet: {packet.hex().upper()}")
            ser.write(packet)
            time.sleep(2.0)
            
    except KeyboardInterrupt:
        print("\nTest interrupted by user.")
    finally:
        print("Closing serial port...")
        ser.close()
        print("Test complete.")

if __name__ == "__main__":
    test_usb_movement()
