# Implements: SW-001 §3 — Orchestrator ("Stream and Sweep" v2)
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
from hardware import LiDARController

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
# Coordinate Mapping — Scout pixel → Gimbal degrees
# ==============================================================================
FRAME_W = 1280
FRAME_H = 720
# Scout IMX219 camera FOV (replaces OV9281 — see HISTORY.md 2026-05-27)
FOV_H = 62.2   # IMX219 horizontal FOV (degrees)
FOV_V = 48.8   # IMX219 vertical FOV (degrees)

def pixel_to_angle(px: int, py: int) -> tuple:
    """Map (X, Y) pixel from Scout to physical Pan/Tilt."""
    norm_x = (px / FRAME_W) - 0.5
    norm_y = (py / FRAME_H) - 0.5
    yaw_deg = norm_x * FOV_H
    pitch_deg = norm_y * FOV_V   # POSITIVE y = DOWN = POSITIVE pitch
    return pitch_deg, yaw_deg

# ==============================================================================
# Stream-and-Sweep Configuration
# ==============================================================================

# How far ahead (in seconds) to predict the target's position.
# At 120FPS the Scout updates ~every 8ms. This lookahead compensates for
# the gimbal settle time + pump spin-up (~100ms mechanical delay).
PREDICTION_LOOKAHEAD_SEC = 0.15

# Total pump-on duration during a sweep (includes ~100ms spin-up)
SWEEP_DURATION_SEC = 0.4

# Gimbal sweep parameters — how far past the target to sweep
SWEEP_OVERSHOOT_DEG = 3.0  # Degrees past predicted position
SWEEP_STEPS = 5            # Number of gimbal micro-steps during sweep
SWEEP_STEP_DELAY = 0.04    # Seconds between each micro-step

# Cooldown after engagement to prevent rapid re-firing
POST_ENGAGEMENT_COOLDOWN_SEC = 1.0

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
    lidar = LiDARController()

    scout.start()
    sniper.start()

    # Wait for cameras to warm up
    await asyncio.sleep(2.0)

    buzzer.boot()
    log.info("Sentry is ACTIVE. Monitoring sector...")
    log_engagement("system_start", {
        "arc_compensation_deg": weapon.get_arc_compensation(),
        "sweep_duration": SWEEP_DURATION_SEC,
        "prediction_lookahead": PREDICTION_LOOKAHEAD_SEC
    })

    # Session statistics
    stats = {"detections": 0, "verifications": 0, "engagements": 0, "rejections": 0}

    try:
        while True:
            # ── Phase 1: Scout Detect ────────────────────────────────
            tx, ty, vx, vy = scout.get_target_with_velocity()

            if tx is not None and ty is not None:
                stats["detections"] += 1

                # ── Phase 2: Predict target position ─────────────────
                # Where will the target be when the pump actually fires?
                # Account for gimbal travel + pump spin-up (~150ms total)
                pred_x = tx + vx * PREDICTION_LOOKAHEAD_SEC
                pred_y = ty + vy * PREDICTION_LOOKAHEAD_SEC

                # Clamp predicted position to frame bounds
                pred_x = max(0, min(FRAME_W, pred_x))
                pred_y = max(0, min(FRAME_H, pred_y))

                # Convert to gimbal angles
                raw_pitch, raw_yaw = pixel_to_angle(tx, ty)
                pred_pitch, pred_yaw = pixel_to_angle(pred_x, pred_y)

                # Apply linear drop compensation (pitch offset for stream trajectory over distance)
                distance_m = lidar.read_distance()
                if distance_m <= 3.0:
                    arc_comp = 0.0
                else:
                    arc_comp = -0.5 * (distance_m - 3.0)

                aim_pitch = pred_pitch + arc_comp

                log.info(
                    f"Target at ({tx},{ty}) vel=({vx:.0f},{vy:.0f}) px/s → "
                    f"predicted ({pred_x:.0f},{pred_y:.0f})"
                )

                # ── Phase 3: Aim at predicted position ───────────────
                await gimbal.aim_async(aim_pitch, pred_yaw)

                # Brief settle — gimbal mechanical response
                await asyncio.sleep(0.05)

                # ── Phase 4: Sniper Verify ───────────────────────────
                is_verified = await sniper.verify_target()
                stats["verifications"] += 1

                if is_verified:
                    stats["engagements"] += 1
                    log.info(
                        f"TARGET VERIFIED. Engaging with Stream-and-Sweep. "
                        f"(Engagement #{stats['engagements']})"
                    )
                    buzzer.engagement()

                    # ── Phase 5: STREAM AND SWEEP ────────────────────
                    # Step 1: Start pump NOW (non-blocking).
                    #         The pump takes ~100ms to spin up. By the time
                    #         the diaphragm builds pressure, the gimbal will
                    #         be mid-sweep → "wall of water" across flight path.
                    weapon.fire_sweep(SWEEP_DURATION_SEC)

                    # Step 2: While pump is running, sweep the gimbal along
                    #         the target's velocity vector to create a moving
                    #         curtain of water across the predicted flight path.
                    sweep_end_pitch = aim_pitch
                    sweep_end_yaw = pred_yaw

                    # Overshoot: extend the sweep in the direction of travel
                    if abs(vx) > 10 or abs(vy) > 10:
                        # Target is moving — sweep along velocity vector
                        sweep_end_yaw += (SWEEP_OVERSHOOT_DEG if vx > 0 else -SWEEP_OVERSHOOT_DEG)
                        sweep_end_pitch += (SWEEP_OVERSHOOT_DEG if vy > 0 else -SWEEP_OVERSHOOT_DEG)

                    await gimbal.sweep_async(
                        aim_pitch, pred_yaw,          # Start: current aim point
                        sweep_end_pitch, sweep_end_yaw,  # End: overshoot
                        steps=SWEEP_STEPS,
                        step_delay=SWEEP_STEP_DELAY
                    )

                    log_engagement("fire", {
                        "mode": "DIRECT_STREAM_SWEEP",
                        "target_px": [tx, ty],
                        "velocity_px_s": [round(vx, 1), round(vy, 1)],
                        "predicted_px": [round(pred_x), round(pred_y)],
                        "aim_pitch": round(aim_pitch, 2),
                        "aim_yaw": round(pred_yaw, 2),
                        "arc_compensation_deg": round(arc_comp, 2),
                        "sweep_end_pitch": round(sweep_end_pitch, 2),
                        "sweep_end_yaw": round(sweep_end_yaw, 2),
                        "stream_duration_ms": int(SWEEP_DURATION_SEC * 1000),
                        "session_stats": stats.copy()
                    })

                    # Cooldown — prevent rapid re-firing on the same target
                    await asyncio.sleep(POST_ENGAGEMENT_COOLDOWN_SEC)
                else:
                    stats["rejections"] += 1
                    log.info("Target REJECTED by Sniper. Resuming scan.")
                    log_engagement("reject", {
                        "target_px": [tx, ty],
                        "raw_pitch": round(raw_pitch, 2),
                        "raw_yaw": round(raw_yaw, 2)
                    })

            # Yield event loop — ~50ms scan rate
            await asyncio.sleep(0.05)

    except KeyboardInterrupt:
        log.info("Shutdown signal received.")
    finally:
        weapon.cease_fire()  # Safety: ensure pump is OFF
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
