#!/usr/bin/env python3
# Implements: SW-001 §6 — Calibration Procedure
"""
phantom_ping.py — Airburst Calibration Tool

Fires test shots at multiple airburst offset angles to help you visually
determine the optimal offset for your installation height and water pressure.

Usage:
    python3 phantom_ping.py                    # Interactive mode
    python3 phantom_ping.py --offset 12 --count 3   # Fire 3 shots at +12°

The results are saved to calibration.json for future reference.
"""

import argparse
import json
import time
import sys
import os

# Allow importing sibling modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gimbal_controller import GimbalController
from weapon_system import WeaponSystem

CALIBRATION_FILE = "calibration.json"

def load_calibration():
    if os.path.exists(CALIBRATION_FILE):
        with open(CALIBRATION_FILE, "r") as f:
            return json.load(f)
    return {"shots": [], "best_offset": 12.0}

def save_calibration(data):
    with open(CALIBRATION_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"[phantom_ping] Calibration saved to {CALIBRATION_FILE}")

def fire_test_shot(gimbal, weapon, pitch, yaw, pulse_sec, label=""):
    """Fire a single test shot and record it."""
    print(f"\n{'='*50}")
    print(f"  TEST SHOT {label}")
    print(f"  Pitch: {pitch:.1f}°  |  Yaw: {yaw:.1f}°  |  Pulse: {pulse_sec}s")
    print(f"{'='*50}")
    
    # Aim
    gimbal.aim(pitch, yaw)
    print("[phantom_ping] Gimbal moving... waiting 1s to settle.")
    time.sleep(1.0)
    
    # Countdown
    for i in range(3, 0, -1):
        print(f"  Firing in {i}...")
        time.sleep(1.0)
    
    # Fire
    print("  🔥 FIRING!")
    weapon.fire(pulse_sec)
    print("  Shot complete.")
    
    return {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "pitch": pitch,
        "yaw": yaw,
        "pulse_sec": pulse_sec,
        "label": label
    }

def interactive_mode():
    """Walk the user through a calibration sequence."""
    gimbal = GimbalController()
    weapon = WeaponSystem()
    cal = load_calibration()
    
    print("\n" + "="*60)
    print("  PHANTOM PING — Airburst Calibration Tool")
    print("="*60)
    print("\nThis tool fires test shots at different airburst offsets.")
    print("Watch where the water lands and note which offset gives")
    print("the best coverage over the target zone.\n")
    print("The gimbal will aim straight down (Pitch=0, Yaw=0) and")
    print("apply the airburst offset you specify.\n")
    
    pulse = 0.6  # Standard Airburst pulse
    yaw = 0.0     # Straight ahead
    
    try:
        while True:
            offset = input("\nEnter airburst offset (degrees, or 'q' to quit): ").strip()
            if offset.lower() == 'q':
                break
            
            try:
                offset_deg = float(offset)
            except ValueError:
                print("Invalid number. Try again.")
                continue
            
            pitch = offset_deg  # Pure offset from center
            
            shot = fire_test_shot(
                gimbal, weapon, pitch, yaw, pulse,
                label=f"Offset +{offset_deg}°"
            )
            cal["shots"].append(shot)
            
            rating = input("Rate this shot (1=miss, 2=partial, 3=direct hit): ").strip()
            shot["rating"] = int(rating) if rating.isdigit() else 0
            
            if shot.get("rating") == 3:
                cal["best_offset"] = offset_deg
                print(f"  ✅ Marking +{offset_deg}° as best offset!")
            
    except KeyboardInterrupt:
        print("\n\nCalibration interrupted.")
    finally:
        save_calibration(cal)
        gimbal.aim(0, 0)  # Return to center
        gimbal.cleanup()
        weapon.cleanup()
        
        print(f"\n{'='*60}")
        print(f"  Results: {len(cal['shots'])} shots fired")
        print(f"  Best offset: +{cal['best_offset']}°")
        print(f"  Saved to: {CALIBRATION_FILE}")
        print(f"{'='*60}")

def single_shot_mode(offset, count, pulse):
    """Fire a fixed number of shots at a given offset."""
    gimbal = GimbalController()
    weapon = WeaponSystem()
    cal = load_calibration()
    
    for i in range(count):
        shot = fire_test_shot(
            gimbal, weapon, offset, 0.0, pulse,
            label=f"#{i+1}/{count} at +{offset}°"
        )
        cal["shots"].append(shot)
        if i < count - 1:
            time.sleep(2.0)
    
    save_calibration(cal)
    gimbal.aim(0, 0)
    gimbal.cleanup()
    weapon.cleanup()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phantom Ping — Airburst Calibration")
    parser.add_argument("--offset", type=float, help="Airburst offset in degrees")
    parser.add_argument("--count", type=int, default=1, help="Number of shots to fire")
    parser.add_argument("--pulse", type=float, default=0.6, help="Pulse duration in seconds")
    args = parser.parse_args()
    
    if args.offset is not None:
        single_shot_mode(args.offset, args.count, args.pulse)
    else:
        interactive_mode()
