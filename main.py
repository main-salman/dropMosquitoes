# Implements: SW-001 §3 — Orchestrator
import asyncio
import logging
import json
import time
import sys
import os
from datetime import datetime
from scout_vision import ScoutVision
from sniper_vision import SniperVision
from gimbal_controller import GimbalController
from weapon_system import WeaponSystem
from ir_controller import IRController
from status_indicator import StatusIndicator

# ==============================================================================
# Logging — Persistent engagement log + console output
# ==============================================================================
LOG_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(LOG_DIR, "sentry.log")
ENGAGEMENT_LOG = os.path.join(LOG_DIR, "engagements.jsonl")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("sentry")

def log_engagement(event_type: str, data: dict):
    """Append a structured JSON line to the engagement log."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "event": event_type,
        **data
    }
    try:
        with open(ENGAGEMENT_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        log.warning(f"Failed to write engagement log: {e}")

# ==============================================================================
# Coordinate Mapping
# ==============================================================================
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

# ==============================================================================
# Main Orchestration Loop
# ==============================================================================
async def orchestrator_loop():
    log.info("Initializing subsystems...")
    
    scout = ScoutVision("scout_config.json")
    sniper = SniperVision("best.pt")
    gimbal = GimbalController()
    weapon = WeaponSystem()
    ir = IRController(auto_schedule=True)
    buzzer = StatusIndicator()
    
    scout.start()
    sniper.start()
    
    # Wait for cameras to warm up
    await asyncio.sleep(2.0)
    
    buzzer.boot()
    log.info("Sentry is ACTIVE. Monitoring sector...")
    log_engagement("system_start", {"airburst_offset": weapon.get_airburst_offset()})
    
    # Session statistics
    stats = {"detections": 0, "verifications": 0, "engagements": 0, "rejections": 0}
    
    try:
        while True:
            # 1. Pipeline 1: Scout Detect
            tx, ty = scout.get_target()
            
            if tx is not None and ty is not None:
                stats["detections"] += 1
                log.info(f"Target acquired at ({tx}, {ty}). Initiating handoff...")
                
                # 2. Map coordinates & Aim
                raw_pitch, raw_yaw = pixel_to_angle(tx, ty)
                airburst_offset = weapon.get_airburst_offset()
                airburst_pitch = raw_pitch + airburst_offset
                
                gimbal.aim(airburst_pitch, raw_yaw)
                
                # 3. Asynchronous settle wait
                await asyncio.sleep(0.2)
                
                # 4. Pipeline 2: Sniper Verify
                is_verified = await sniper.verify_target()
                stats["verifications"] += 1
                
                if is_verified:
                    stats["engagements"] += 1
                    log.info(f"Target VERIFIED. Engaging. (Engagement #{stats['engagements']})")
                    buzzer.engagement()
                    
                    log_engagement("fire", {
                        "target_px": [tx, ty],
                        "raw_pitch": round(raw_pitch, 2),
                        "raw_yaw": round(raw_yaw, 2),
                        "airburst_offset": airburst_offset,
                        "final_pitch": round(airburst_pitch, 2),
                        "pulse_sec": 0.6,
                        "session_stats": stats.copy()
                    })
                    
                    weapon.fire(0.6)
                    
                    # Prevent rapid re-firing on the same target
                    await asyncio.sleep(1.0)
                else:
                    stats["rejections"] += 1
                    log.info("Target REJECTED by Sniper. Resuming scan.")
                    log_engagement("reject", {
                        "target_px": [tx, ty],
                        "raw_pitch": round(raw_pitch, 2),
                        "raw_yaw": round(raw_yaw, 2)
                    })
                    
            # Yield event loop
            await asyncio.sleep(0.05)
            
    except KeyboardInterrupt:
        log.info("Shutdown signal received.")
    finally:
        buzzer.shutdown()
        log_engagement("system_stop", {"session_stats": stats})
        log.info(f"Session stats: {stats}")
        scout.stop()
        sniper.stop()
        gimbal.cleanup()
        weapon.cleanup()
        ir.cleanup()
        buzzer.cleanup()
        log.info("Shutdown complete.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(orchestrator_loop())
