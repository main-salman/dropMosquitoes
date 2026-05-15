# Implements: SW-001 §1 — Orchestrator
import asyncio
import time
import sys
from scout_vision import ScoutVision
from sniper_vision import SniperVision
from gimbal_controller import GimbalController
from weapon_system import WeaponSystem

# Coordinate mapping constants (example)
FRAME_W = 1280
FRAME_H = 800
FOV_H = 110.0
FOV_V = 75.0

def pixel_to_angle(px: int, py: int) -> tuple:
    """Map (X, Y) pixel from Scout to physical Pan/Tilt."""
    norm_x = (px / FRAME_W) - 0.5
    norm_y = (py / FRAME_H) - 0.5
    yaw_deg = norm_x * FOV_H
    pitch_deg = -norm_y * FOV_V
    return pitch_deg, yaw_deg

async def orchestrator_loop():
    print("[Main] Initializing subsystems...")
    
    scout = ScoutVision("scout_config.json")
    sniper = SniperVision("best.pt")
    gimbal = GimbalController()
    weapon = WeaponSystem()
    
    scout.start()
    sniper.start()
    
    # Wait for cameras to warm up
    await asyncio.sleep(2.0)
    
    print("[Main] Sentry is ACTIVE. Monitoring sector...")
    
    try:
        while True:
            # 1. Pipeline 1: Scout Detect
            tx, ty = scout.get_target()
            
            if tx is not None and ty is not None:
                print(f"[Main] Target acquired at ({tx}, {ty}). Initiating handoff...")
                
                # 2. Map coordinates & Aim
                raw_pitch, raw_yaw = pixel_to_angle(tx, ty)
                
                # Apply Airburst Offset dynamically
                airburst_pitch = raw_pitch + weapon.get_airburst_offset()
                
                gimbal.aim(airburst_pitch, raw_yaw)
                
                # 3. Asynchronous settle wait
                await asyncio.sleep(0.2)
                
                # 4. Pipeline 2: Sniper Verify
                is_verified = await sniper.verify_target()
                
                if is_verified:
                    print("[Main] Target VERIFIED. Engaging.")
                    # 5. The Trigger
                    # Execute synchronous block in executor if we want strict async, 
                    # but weapon.fire() blocks for duration_sec (0.6).
                    # For simplicity, we just call it directly.
                    weapon.fire(0.6)
                    
                    # Prevent rapid re-firing on the same target
                    await asyncio.sleep(1.0)
                else:
                    print("[Main] Target REJECTED by Sniper. Resuming scan.")
                    
            # Yield event loop
            await asyncio.sleep(0.05)
            
    except KeyboardInterrupt:
        print("\n[Main] Shutdown signal received.")
    finally:
        scout.stop()
        sniper.stop()
        gimbal.cleanup()
        weapon.cleanup()
        print("[Main] Shutdown complete.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(orchestrator_loop())
