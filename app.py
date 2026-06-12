# Implements: SW-001 §2, §2.7 — Flask server, MJPEG streams, REST API, predictive lead
"""
app.py — Sniper Messy Mortar Flask Server

The central orchestrator. Provides:
  - MJPEG video streams for Scout and Sniper cameras
  - REST API for gimbal control, relay switching, LiDAR, ballistic math, and AI tuning
  - Serves the web dashboard (templates/index.html)

Usage:
  python app.py              # Starts on http://0.0.0.0:8000
  python app.py --no-ai      # Disable YOLO (for hardware-only testing)
"""

import argparse
import atexit
import os
import signal
import re
import subprocess
import sys
import time
from flask import Flask, render_template, Response, request, jsonify

from hardware import (
    RelayController, LiDARController, create_turret_controller,
    PrimingSystem,
    pixel_to_angle, compute_ballistic_offset, compute_predictive_lead,
    YAW_LIMIT, PITCH_LIMIT, PITCH_HOME,
    SERVO_YAW_LIMIT, SERVO_PITCH_LIMIT
)
from vision import CameraStream, YOLODetector, VelocityTracker
from calibration_engine import CalibrationTable, HitDetector, AutoCalibrator

# ============================================================================
# FLASK APP INITIALIZATION
# ============================================================================
app = Flask(__name__)
APP_DIR = os.path.dirname(os.path.abspath(__file__))

# Hardware controllers (initialized at module level for atexit cleanup)
relay = RelayController()
gimbal = create_turret_controller()
lidar = LiDARController()

# Velocity tracker for predictive lead — SW-001 §2.7.1
velocity_tracker = VelocityTracker()

# Camera streams — dimensions must match HW-001 §2
# Full Dual-Camera Architecture:
# - Scout camera: CSI-0 (IMX219 NoIR at 1280x720 @ 60 FPS) fixed to enclosure
# - Sniper camera: CSI-1 (IMX219 NoIR with Motorized IR-Cut at 1280x720 @ 60 FPS) on gimbal
scout_cam = CameraStream(sensor_id=0, width=1280, height=720, fps=30, name="Scout")
sniper_cam = CameraStream(sensor_id=1, width=1280, height=720, fps=30, name="Sniper")

# AI detector (lazy-init — may be disabled via --no-ai flag)
detector = None

# Arc Compensation — pitch offset to compensate for stream trajectory drop over distance
ARC_COMPENSATION_DEG = 12.0

# Visual Calibration System — SW-001 §2.8
cal_table = CalibrationTable(filepath=os.path.join(APP_DIR, "calibration_visual.json"))
cal_table.load()  # Load previous calibration if exists
hit_detector = HitDetector()
auto_cal = AutoCalibrator(cal_table, hit_detector)

# Water Line Priming System
primer = PrimingSystem(relay)
primer.start_keepalive(gimbal=gimbal)


# ============================================================================
# CLEANUP — SAFE-001 §2: Guarantee all hardware is safe on exit
# ============================================================================
_cleanup_done = False

def cleanup():
    global _cleanup_done
    if _cleanup_done:
        return
    _cleanup_done = True
    print("\n[app] Shutting down...")
    scout_cam.stop()
    sniper_cam.stop()
    lidar.cleanup()
    gimbal.cleanup()
    relay.cleanup()
    print("[app] Shutdown complete.")

def _signal_handler(signum, frame):
    """Handle SIGTERM/SIGINT to ensure GStreamer pipelines are torn down cleanly.
    Without this, nvarguscamerasrc leaves the MIPI CSI sensor in a bad state,
    causing garbled frames on the next startup."""
    print(f"\n[app] Received signal {signum}, shutting down gracefully...")
    cleanup()
    sys.exit(0)

signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)
atexit.register(cleanup)


# ============================================================================
# MJPEG STREAMING
# ============================================================================

def _mjpeg_generator(camera: CameraStream):
    """
    Generator that yields JPEG frames as a multipart HTTP response.
    This is how the browser receives a "live video" feed.
    """
    while True:
        jpeg = camera.get_jpeg()
        if jpeg is None:
            time.sleep(0.05)
            continue
        yield (
            b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n' + jpeg + b'\r\n'
        )
        # Throttle to ~30fps for the browser (cameras may run faster internally)
        time.sleep(0.033)


@app.route('/stream/scout')
def stream_scout():
    """MJPEG stream from the Scout camera (wide-angle, fixed)."""
    return Response(
        _mjpeg_generator(scout_cam),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )


@app.route('/stream/sniper')
def stream_sniper():
    """MJPEG stream from the Sniper camera (narrow, on gimbal)."""
    return Response(
        _mjpeg_generator(sniper_cam),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )


# ============================================================================
# WEB DASHBOARD
# ============================================================================

@app.route('/')
def index():
    """Serve the main control dashboard."""
    # Detect controller type for dashboard display
    from hardware import ServoTurretController
    is_servo = isinstance(gimbal, ServoTurretController)
    ctrl_type = "servo" if is_servo else "storm32"
    eff_yaw = SERVO_YAW_LIMIT if is_servo else YAW_LIMIT
    eff_pitch = SERVO_PITCH_LIMIT if is_servo else PITCH_LIMIT
    return render_template('index.html',
                           yaw_limit=eff_yaw,
                           pitch_limit=eff_pitch,
                           pitch_home=PITCH_HOME,
                           ctrl_type=ctrl_type)


@app.route('/api/gimbal/set', methods=['POST'])
def api_gimbal_set():
    """Set absolute gimbal angles. Body: {"pitch": float, "yaw": float}"""
    data = request.get_json(force=True)
    pitch = float(data.get('pitch', 0))
    yaw = float(data.get('yaw', 0))
    gimbal.set_angles(pitch, yaw)
    return jsonify(gimbal.get_status())


@app.route('/api/servo/settings', methods=['GET'])
def api_servo_settings_get():
    """Get current servo interpolation parameters."""
    from hardware import ServoTurretController, SERVO_YAW_LIMIT, SERVO_PITCH_LIMIT
    if isinstance(gimbal, ServoTurretController):
        return jsonify({
            "speed": gimbal.INTERP_SPEED,
            "rate_hz": gimbal.INTERP_RATE_HZ,
            "nudge_step": getattr(gimbal, '_nudge_step', 2.0),
            "yaw_limit": SERVO_YAW_LIMIT,
            "pitch_limit": SERVO_PITCH_LIMIT,
        })
    return jsonify({"error": "Not a servo controller"}), 400


@app.route('/api/servo/settings', methods=['POST'])
def api_servo_settings_set():
    """Update servo interpolation parameters at runtime.
    Body: {"speed": float, "rate_hz": int, "nudge_step": float,
           "yaw_limit": float, "pitch_limit": float}
    """
    from hardware import ServoTurretController
    import hardware
    if not isinstance(gimbal, ServoTurretController):
        return jsonify({"error": "Not a servo controller"}), 400

    data = request.get_json(force=True)

    if 'speed' in data:
        val = max(10.0, min(500.0, float(data['speed'])))
        gimbal.INTERP_SPEED = val
    if 'rate_hz' in data:
        val = max(20, min(200, int(data['rate_hz'])))
        gimbal.INTERP_RATE_HZ = val
    if 'nudge_step' in data:
        gimbal._nudge_step = max(0.5, min(20.0, float(data['nudge_step'])))
    if 'yaw_limit' in data:
        hardware.SERVO_YAW_LIMIT = max(10.0, min(90.0, float(data['yaw_limit'])))
    if 'pitch_limit' in data:
        hardware.SERVO_PITCH_LIMIT = max(10.0, min(90.0, float(data['pitch_limit'])))

    print(f"[Settings] Servo: speed={gimbal.INTERP_SPEED}°/s "
          f"rate={gimbal.INTERP_RATE_HZ}Hz "
          f"nudge={getattr(gimbal, '_nudge_step', 2.0)}° "
          f"yaw_limit=±{hardware.SERVO_YAW_LIMIT}° "
          f"pitch_limit=±{hardware.SERVO_PITCH_LIMIT}°")

    return jsonify({
        "speed": gimbal.INTERP_SPEED,
        "rate_hz": gimbal.INTERP_RATE_HZ,
        "nudge_step": getattr(gimbal, '_nudge_step', 2.0),
        "yaw_limit": hardware.SERVO_YAW_LIMIT,
        "pitch_limit": hardware.SERVO_PITCH_LIMIT,
    })


@app.route('/api/gimbal/nudge', methods=['POST'])
def api_gimbal_nudge():
    """Relative gimbal movement. Body: {"d_pitch": float, "d_yaw": float}"""
    data = request.get_json(force=True)
    d_pitch = float(data.get('d_pitch', 0))
    d_yaw = float(data.get('d_yaw', 0))
    gimbal.nudge(d_pitch, d_yaw)
    return jsonify(gimbal.get_status())


@app.route('/api/gimbal/center', methods=['POST'])
def api_gimbal_center():
    """Return gimbal to home (0, 0)."""
    gimbal.center()
    return jsonify(gimbal.get_status())


@app.route('/api/gimbal/click', methods=['POST'])
def api_gimbal_click():
    """
    Click-to-aim with predictive lead + ballistic correction.

    SW-001 §2.7 — Three-stage pipeline:
      1. pixel_to_angle()          → raw pitch/yaw
      2. + velocity lead offsets   → corrected for target movement during ToF
      3. + gravity drop            → final corrected pitch

    Body: {"px": int, "py": int, "frame_w": int, "frame_h": int}
    """
    data = request.get_json(force=True)
    px = int(data.get('px', 0))
    py = int(data.get('py', 0))
    fw = int(data.get('frame_w', 1280))
    fh = int(data.get('frame_h', 800))

    # Stage 1: Pixel → raw angles (§2.7 step 1)
    raw_pitch, raw_yaw = pixel_to_angle(px, py, fw, fh)

    # Stage 1.5: Apply visual calibration offset (camera-nozzle correction)
    cal_d_pitch, cal_d_yaw = cal_table.get_correction(
        distance_m=lidar.read_distance(), pitch=raw_pitch, yaw=raw_yaw)
    raw_pitch += cal_d_pitch
    raw_yaw += cal_d_yaw

    # Get LiDAR distance for ToF calculation
    distance_m = lidar.read_distance()

    # Get target velocity from VelocityTracker (§2.7.1)
    omega_pitch, omega_yaw = velocity_tracker.get_angular_velocity()

    # Stages 2+3: Velocity lead + Arc Compensation (stream trajectory over distance)
    global ARC_COMPENSATION_DEG
    final_pitch, final_yaw, lead_info = compute_predictive_lead(
        raw_pitch, raw_yaw, distance_m, omega_pitch, omega_yaw
    )

    # Move gimbal to fully corrected position
    gimbal.set_angles(final_pitch, final_yaw)

    return jsonify({
        "target_px": [px, py],
        "raw_pitch": round(raw_pitch, 2),
        "raw_yaw": round(raw_yaw, 2),
        "predictive_lead": lead_info,
        "velocity": velocity_tracker.get_velocity(),
        **gimbal.get_status()
    })


# ============================================================================
# LiDAR API — SW-001 §2.5
# ============================================================================

@app.route('/api/lidar')
def api_lidar():
    """Return current LiDAR distance and signal strength."""
    return jsonify(lidar.get_status())


# ============================================================================
# VELOCITY TRACKER API — SW-001 §2.7.1
# ============================================================================

@app.route('/api/velocity')
def api_velocity():
    """Return current target velocity and angular rates."""
    return jsonify(velocity_tracker.get_velocity())


@app.route('/api/velocity/update', methods=['POST'])
def api_velocity_update():
    """
    Feed a centroid position into the velocity tracker.
    Body: {"cx": int, "cy": int}
    Used by the scout agent or for manual testing.
    """
    data = request.get_json(force=True)
    cx = int(data.get('cx', 0))
    cy = int(data.get('cy', 0))
    velocity_tracker.update(cx, cy)
    return jsonify(velocity_tracker.get_velocity())


@app.route('/api/velocity/reset', methods=['POST'])
def api_velocity_reset():
    """Reset velocity tracker (target lost or scene change)."""
    velocity_tracker.reset()
    return jsonify({"reset": True})


# ============================================================================
# RELAY API
# ============================================================================

@app.route('/api/relay/fire', methods=['POST'])
def api_relay_fire():
    """
    Fire the water pump for a specified duration.
    Body: {"duration": float}  (seconds, 0.01–2.0)
    """
    data = request.get_json(force=True)
    duration = float(data.get('duration', 0.025))
    relay.fire_pump(duration)
    primer.mark_fired()
    return jsonify({"fired": True, "duration": duration})


@app.route('/api/relay/pump', methods=['POST'])
def api_relay_pump():
    """Manual pump toggle. Body: {"state": bool}"""
    data = request.get_json(force=True)
    state = bool(data.get('state', False))
    relay.set_pump(state)
    return jsonify(relay.get_status())


@app.route('/api/relay/gimbal_power', methods=['POST'])
def api_relay_gimbal_power():
    """Manual gimbal power toggle. Body: {"state": bool}"""
    data = request.get_json(force=True)
    state = bool(data.get('state', False))
    relay.set_gimbal_power(state)
    return jsonify(relay.get_status())


# ============================================================================
# PRIMING API
# ============================================================================

@app.route('/api/prime/status', methods=['GET'])
def api_prime_status():
    """Get priming system status."""
    return jsonify(primer.get_status())


@app.route('/api/prime/now', methods=['POST'])
def api_prime_now():
    """Manually trigger a prime sequence."""
    result = primer.prime(gimbal=gimbal, camera=sniper_cam)
    return jsonify(result)


@app.route('/api/prime/settings', methods=['GET'])
def api_prime_settings_get():
    """Get priming settings."""
    return jsonify(primer.get_status()["settings"])


@app.route('/api/prime/settings', methods=['POST'])
def api_prime_settings_set():
    """Update priming settings.
    Body: {"prime_duration_ms": int, "keepalive_interval_min": int,
           "keepalive_pulse_ms": int, "auto_detect": bool, "keepalive_enabled": bool}"""
    data = request.get_json(force=True)
    primer.update_settings(data)
    return jsonify(primer.get_status()["settings"])


# ============================================================================
# PUMP STABILIZATION API (Pre-pressurization for diaphragm pump consistency)
# ============================================================================

@app.route('/api/pump/stabilize', methods=['GET'])
def api_pump_stabilize_get():
    """Get pump stabilization settings."""
    return jsonify({
        "pre_pressurize": relay.pre_pressurize,
        "stabilize_ms": relay.stabilize_ms,
        "settle_ms": relay.settle_ms,
    })


@app.route('/api/pump/stabilize', methods=['POST'])
def api_pump_stabilize_set():
    """Update pump stabilization settings.
    Body: {"pre_pressurize": bool, "stabilize_ms": int, "settle_ms": int}"""
    data = request.get_json(force=True)
    if "pre_pressurize" in data:
        relay.pre_pressurize = bool(data["pre_pressurize"])
    if "stabilize_ms" in data:
        relay.stabilize_ms = max(0, min(int(data["stabilize_ms"]), 500))
    if "settle_ms" in data:
        relay.settle_ms = max(0, min(int(data["settle_ms"]), 500))
    print(f"[app] Stabilization: {'ON' if relay.pre_pressurize else 'OFF'}, "
          f"burst={relay.stabilize_ms}ms, settle={relay.settle_ms}ms")
    return jsonify({
        "pre_pressurize": relay.pre_pressurize,
        "stabilize_ms": relay.stabilize_ms,
        "settle_ms": relay.settle_ms,
    })


# ============================================================================
# AI / YOLO API
# ============================================================================

@app.route('/api/ai/confidence', methods=['POST'])
def api_ai_confidence():
    """Set YOLO confidence threshold. Body: {"value": float (0-1)}"""
    if detector is None:
        return jsonify({"error": "AI disabled"}), 400
    data = request.get_json(force=True)
    detector.set_confidence(float(data.get('value', 0.5)))
    return jsonify({"confidence": detector.confidence})


@app.route('/api/ai/min_box', methods=['POST'])
def api_ai_min_box():
    """Set minimum bounding box area. Body: {"value": int}"""
    if detector is None:
        return jsonify({"error": "AI disabled"}), 400
    data = request.get_json(force=True)
    detector.set_min_box_area(int(data.get('value', 100)))
    return jsonify({"min_box_area": detector.min_box_area})


# ============================================================================
# CALIBRATION API — Interactive GUI-based calibration tools
# ============================================================================

@app.route('/api/airburst/set', methods=['POST'])
def api_airburst_set():
    """Set the arc compensation pitch offset (degrees). Body: {"offset": float}"""
    global ARC_COMPENSATION_DEG
    data = request.get_json(force=True)
    ARC_COMPENSATION_DEG = float(data.get('offset', 12.0))
    print(f"[app] Arc Compensation updated to {ARC_COMPENSATION_DEG}°")
    return jsonify({"arc_compensation_deg": ARC_COMPENSATION_DEG})

# In-memory calibration data (persisted to calibration.json on save)
_calibration_log = []
_ballistic_table = {}

import json
CALIBRATION_FILE = os.path.join(APP_DIR, "calibration.json")

# Load existing calibration if present
if os.path.exists(CALIBRATION_FILE):
    try:
        with open(CALIBRATION_FILE, 'r') as f:
            _cal_data = json.load(f)
            _ballistic_table = _cal_data.get("ballistic_table", {})
            print(f"[Calibration] Loaded {len(_ballistic_table)} entries from calibration.json")
    except Exception:
        pass


@app.route('/api/calibration/lidar_check', methods=['POST'])
def api_cal_lidar_check():
    """
    LiDAR verification: user places target at known distance, we compare.
    Body: {"known_distance_m": float, "label": str}
    """
    data = request.get_json(force=True)
    known = float(data.get('known_distance_m', 0))
    label = data.get('label', '')
    measured = lidar.read_distance()
    error = round(measured - known, 3)
    entry = {
        "type": "lidar_check",
        "known_m": known,
        "measured_m": round(measured, 3),
        "error_m": error,
        "error_cm": round(error * 100, 1),
        "label": label,
        "timestamp": time.strftime("%H:%M:%S")
    }
    _calibration_log.append(entry)
    return jsonify(entry)


@app.route('/api/calibration/gimbal_test', methods=['POST'])
def api_cal_gimbal_test():
    """
    Gimbal accuracy test: move to a specific angle and report.
    Body: {"pitch": float, "yaw": float}
    """
    data = request.get_json(force=True)
    pitch = float(data.get('pitch', 0))
    yaw = float(data.get('yaw', 0))
    gimbal.set_angles(pitch, yaw)
    time.sleep(0.3)  # Let gimbal settle
    status = gimbal.get_status()
    entry = {
        "type": "gimbal_test",
        "requested_pitch": pitch,
        "requested_yaw": yaw,
        "actual_pitch": status["pitch"],
        "actual_yaw": status["yaw"],
        "timestamp": time.strftime("%H:%M:%S")
    }
    _calibration_log.append(entry)
    return jsonify(entry)


@app.route('/api/calibration/fire_test', methods=['POST'])
def api_cal_fire_test():
    """
    Ballistic calibration shot: aim at specific angles, fire, record distance.
    Body: {"pitch": float, "yaw": float, "duration": float, "note": str}
    """
    data = request.get_json(force=True)
    pitch = float(data.get('pitch', 0))
    yaw = float(data.get('yaw', 0))
    duration = float(data.get('duration', 0.4))
    note = data.get('note', '')

    # Aim
    gimbal.set_angles(pitch, yaw)
    time.sleep(0.5)

    # Read distance
    distance = lidar.read_distance()

    # Compute what ballistic offset WOULD be
    _, _, offset_info = compute_ballistic_offset(pitch, yaw, distance)

    # Fire
    relay.fire_pump(duration)

    entry = {
        "type": "fire_test",
        "pitch": pitch,
        "yaw": yaw,
        "duration": duration,
        "distance_m": round(distance, 2),
        "predicted_offset": offset_info,
        "note": note,
        "timestamp": time.strftime("%H:%M:%S")
    }
    _calibration_log.append(entry)
    return jsonify(entry)


@app.route('/api/calibration/record_hit', methods=['POST'])
def api_cal_record_hit():
    """
    Record a hit/miss result for the last fire test.
    Body: {"hit": bool, "offset_error_cm": float, "note": str}
    """
    data = request.get_json(force=True)
    hit = bool(data.get('hit', False))
    offset_err = float(data.get('offset_error_cm', 0))
    note = data.get('note', '')

    distance = lidar.read_distance()
    dist_key = str(round(distance * 2) / 2)  # Round to nearest 0.5m

    entry = {
        "type": "hit_record",
        "hit": hit,
        "distance_m": round(distance, 2),
        "offset_error_cm": offset_err,
        "note": note,
        "timestamp": time.strftime("%H:%M:%S")
    }
    _calibration_log.append(entry)

    # Update ballistic table with actual offset needed
    if not hit and offset_err != 0:
        _ballistic_table[dist_key] = {
            "correction_deg": offset_err / 10.0,  # Rough cm-to-deg
            "distance_m": round(distance, 2),
            "samples": _ballistic_table.get(dist_key, {}).get("samples", 0) + 1
        }

    return jsonify(entry)


@app.route('/api/calibration/sweep', methods=['POST'])
def api_cal_sweep():
    """
    Automated gimbal sweep: cycle through angle grid, reading LiDAR at each.
    Body: {"pitch_steps": int, "yaw_steps": int}
    Returns distance map.
    """
    data = request.get_json(force=True)
    p_steps = min(int(data.get('pitch_steps', 5)), 10)
    y_steps = min(int(data.get('yaw_steps', 9)), 18)

    results = []
    for pi in range(p_steps):
        p = -PITCH_LIMIT + (2 * PITCH_LIMIT / max(p_steps - 1, 1)) * pi
        for yi in range(y_steps):
            y = -YAW_LIMIT + (2 * YAW_LIMIT / max(y_steps - 1, 1)) * yi
            gimbal.set_angles(p, y)
            time.sleep(0.2)
            d = lidar.read_distance()
            results.append({
                "pitch": round(p, 1),
                "yaw": round(y, 1),
                "distance_m": round(d, 2)
            })

    gimbal.center()
    return jsonify({"sweep": results, "total_points": len(results)})


@app.route('/api/calibration/save', methods=['POST'])
def api_cal_save():
    """Save calibration data to calibration.json."""
    cal_data = {
        "ballistic_table": _ballistic_table,
        "log": _calibration_log[-50:],  # Keep last 50 entries
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    with open(CALIBRATION_FILE, 'w') as f:
        json.dump(cal_data, f, indent=2)
    return jsonify({"saved": True, "entries": len(_calibration_log)})


@app.route('/api/calibration/log')
def api_cal_log():
    """Return calibration log."""
    return jsonify({"log": _calibration_log, "ballistic_table": _ballistic_table})


@app.route('/api/calibration/clear', methods=['POST'])
def api_cal_clear():
    """Clear calibration log (keeps ballistic table)."""
    _calibration_log.clear()
    return jsonify({"cleared": True})


# ============================================================================
# AUTO-CALIBRATION API — SW-001 §2.8
# ============================================================================

@app.route('/api/calibration/auto/start', methods=['POST'])
def api_cal_auto_start():
    """Start autonomous one-button calibration in a background thread."""
    result = auto_cal.start(
        gimbal=gimbal,
        scout_cam=scout_cam,
        sniper_cam=sniper_cam,
        relay=relay,
        lidar=lidar,
        primer=primer
    )
    return jsonify(result)


@app.route('/api/calibration/auto/status', methods=['GET'])
def api_cal_auto_status():
    """Get live calibration progress (polled by UI every 500ms)."""
    return jsonify(auto_cal.get_status())


@app.route('/api/calibration/auto/stop', methods=['POST'])
def api_cal_auto_stop():
    """Cancel in-progress calibration."""
    auto_cal.stop()
    return jsonify(auto_cal.get_status())


@app.route('/api/calibration/offset', methods=['GET'])
def api_cal_offset_get():
    """Get current calibration offset."""
    return jsonify(cal_table.to_dict())


@app.route('/api/calibration/offset', methods=['POST'])
def api_cal_offset_set():
    """Manually set calibration offset.
    Body: {"offset_pitch": float, "offset_yaw": float}"""
    data = request.get_json(force=True)
    if 'offset_pitch' in data:
        cal_table.offset_pitch = float(data['offset_pitch'])
    if 'offset_yaw' in data:
        cal_table.offset_yaw = float(data['offset_yaw'])
    cal_table.last_updated = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[Calibration] Manual offset: pitch={cal_table.offset_pitch:.2f}° "
          f"yaw={cal_table.offset_yaw:.2f}°")
    return jsonify(cal_table.to_dict())


@app.route('/api/calibration/offset/save', methods=['POST'])
def api_cal_offset_save():
    """Save visual calibration data to JSON."""
    cal_table.save()
    return jsonify({"saved": True, **cal_table.to_dict()})


@app.route('/api/calibration/snapshot')
def api_cal_snapshot():
    """Get annotated sniper frame with hit detection overlay as JPEG."""
    frame = hit_detector.get_annotated_frame()
    if frame is None:
        # Return current sniper frame with crosshair
        frame = sniper_cam.get_frame()
        if frame is None:
            return jsonify({"error": "No frame available"}), 503
    import cv2
    _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return Response(jpeg.tobytes(), mimetype='image/jpeg')


@app.route('/api/calibration/snapshot/before')
def api_cal_snapshot_before():
    """Get the 'before' frame as JPEG."""
    frame = hit_detector.get_before_frame()
    if frame is None:
        return jsonify({"error": "No before frame"}), 404
    import cv2
    _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return Response(jpeg.tobytes(), mimetype='image/jpeg')


@app.route('/api/calibration/freefire', methods=['POST'])
def api_cal_freefire():
    """Free-form calibration: aim → fire → detect hit → return offset.
    Body: {"pitch": float, "yaw": float, "duration": float,
           "aim_px": int, "aim_py": int}"""
    data = request.get_json(force=True)
    pitch = float(data.get('pitch', 0))
    yaw = float(data.get('yaw', 0))
    duration = float(data.get('duration', 0.4))
    aim_px = int(data.get('aim_px', 640))
    aim_py = int(data.get('aim_py', 360))

    # Move to position
    gimbal.set_angles(pitch, yaw)
    time.sleep(1.0)

    # Capture before
    hit_detector.capture_before(sniper_cam)

    # Fire
    relay.fire_pump(duration)
    time.sleep(duration + 0.2)

    # Capture after frames
    for delay in [0.3, 0.6, 1.0]:
        time.sleep(delay)
        hit_detector.capture_after(sniper_cam)

    # Detect hit
    hit = hit_detector.detect()
    distance = lidar.read_distance()

    result = {
        "aimed": {"pitch": pitch, "yaw": yaw, "px": aim_px, "py": aim_py},
        "distance_m": round(distance, 2),
        "detection": hit_detector.get_state(),
    }

    if hit:
        from calibration_engine import CalibrationPoint
        point = CalibrationPoint(
            aim_pitch=pitch, aim_yaw=yaw,
            aim_px=aim_px, aim_py=aim_py,
            hit_px=hit[0], hit_py=hit[1],
            distance_m=distance, hit_confirmed=False)
        point.compute_offset()
        result["offset"] = {
            "pitch": round(point.offset_pitch, 3),
            "yaw": round(point.offset_yaw, 3),
            "px": point.offset_px,
            "py": point.offset_py,
        }

    return jsonify(result)

@app.route('/api/status')
def api_status():
    """Return full system status as JSON — gimbal, relay, LiDAR, AI."""
    from hardware import ServoTurretController
    status = gimbal.get_status()
    status["controller"] = "servo" if isinstance(gimbal, ServoTurretController) else "storm32"
    return jsonify({
        "gimbal": status,
        "relay": relay.get_status(),
        "lidar": lidar.get_status(),
        "ai": {
            "enabled": detector is not None,
            "confidence": detector.confidence if detector else 0,
            "min_box_area": detector.min_box_area if detector else 0
        }
    })


# ============================================================================
# TEST RUNNER API
# ============================================================================

# Registry of available test suites and their CLI commands
TEST_SUITES = {
    "smoke": {
        "name": "Smoke Tests (Layer 0)",
        "description": "Server, API endpoints, MJPEG streams — no hardware needed",
        "script": "tests/test_smoke.py",
        "args": [],
        "layer": 0,
    },
    "camera": {
        "name": "Camera Tests (Layer 1)",
        "description": "GStreamer pipeline, FPS measurement, frame integrity",
        "script": "tests/test_camera.py",
        "args": ["--both", "--duration", "3"],
        "layer": 1,
    },
    "relay": {
        "name": "Relay Tests (Layer 1)",
        "description": "GPIO relay pulse cycles, boot state, duration clamping",
        "script": "tests/test_relay.py",
        "args": ["--all", "--cycles", "2"],
        "layer": 1,
    },

    "yolo": {
        "name": "YOLO / AI Tests (Layer 1)",
        "description": "TensorRT model load, inference FPS, threshold controls",
        "script": "tests/test_yolo.py",
        "args": [],
        "layer": 1,
    },
    "safety": {
        "name": "Safety Tests (Layer 3)",
        "description": "Endstops, death spiral, failsafe, thread safety",
        "script": "tests/test_safety.py",
        "args": [],
        "layer": 3,
    },
    "accuracy": {
        "name": "Accuracy Tests (Layer 4)",
        "description": "Click-to-aim math, gimbal repeatability, ballistic offset",
        "script": "tests/test_accuracy.py",
        "args": [],
        "layer": 4,
    },
    "servo_turret": {
        "name": "Servo Turret Tests (Layer 1)",
        "description": "PCA9685 I2C scan (Bus 7), MG996R servo sweep, chip identity verification",
        "script": "tests/test_servo_turret.py",
        "args": [],
        "layer": 1,
    },

}


@app.route('/api/tests/list')
def api_tests_list():
    """Return the list of available test suites."""
    return jsonify(TEST_SUITES)


@app.route('/api/tests/run', methods=['POST'])
def api_tests_run():
    """
    Run a test suite by name. Returns structured results.
    Body: {"suite": str, "args": [str] (optional extra CLI args)}
    """
    data = request.get_json(force=True)
    suite_id = data.get('suite', '')

    if suite_id not in TEST_SUITES:
        return jsonify({"error": f"Unknown test suite: {suite_id}"}), 400

    suite = TEST_SUITES[suite_id]
    script = os.path.join(APP_DIR, suite["script"])

    if not os.path.exists(script):
        return jsonify({"error": f"Script not found: {suite['script']}"}), 404

    # Build command — use extra args if provided, otherwise defaults
    extra_args = data.get('args', suite["args"])
    cmd = [sys.executable, script] + extra_args

    try:
        result = subprocess.run(
            cmd, cwd=APP_DIR,
            capture_output=True, text=True,
            timeout=120  # 2 minute max
        )
        output = result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        output = "ERROR: Test timed out after 120 seconds."
        result = type('obj', (object,), {'returncode': 1})()

    # Parse output for pass/fail counts
    lines = output.strip().split('\n')
    passed = len([l for l in lines if '✅' in l])
    failed = len([l for l in lines if '❌' in l])

    # Extract the summary line (last line matching "X passed, Y failed")
    summary = ""
    for line in reversed(lines):
        if 'passed' in line and 'failed' in line:
            summary = line.strip()
            break

    return jsonify({
        "suite": suite_id,
        "name": suite["name"],
        "exit_code": result.returncode,
        "passed": passed,
        "failed": failed,
        "summary": summary,
        "output": lines,
    })


@app.route('/api/tests/run_all', methods=['POST'])
def api_tests_run_all():
    """Run all test suites sequentially. Returns combined results."""
    results = []
    total_pass = 0
    total_fail = 0

    # Run in layer order (skip smoke since it starts its own server)
    for suite_id in ["camera", "relay", "serial", "yolo", "safety", "accuracy"]:
        suite = TEST_SUITES[suite_id]
        script = os.path.join(APP_DIR, suite["script"])
        cmd = [sys.executable, script] + suite["args"]

        try:
            result = subprocess.run(
                cmd, cwd=APP_DIR,
                capture_output=True, text=True,
                timeout=120
            )
            output = result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            output = "ERROR: Timed out."
            result = type('obj', (object,), {'returncode': 1})()

        lines = output.strip().split('\n')
        passed = len([l for l in lines if '✅' in l])
        failed = len([l for l in lines if '❌' in l])
        total_pass += passed
        total_fail += failed

        results.append({
            "suite": suite_id,
            "name": suite["name"],
            "passed": passed,
            "failed": failed,
            "exit_code": result.returncode,
        })

    return jsonify({
        "results": results,
        "total_passed": total_pass,
        "total_failed": total_fail,
    })


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Sniper Messy Mortar Server")
    parser.add_argument('--no-ai', action='store_true',
                        help='Disable YOLO AI detection (hardware testing only)')
    parser.add_argument('--port', type=int, default=8000,
                        help='HTTP server port (default: 8000)')
    args = parser.parse_args()

    # Initialize AI detector
    if not args.no_ai:
        detector = YOLODetector()
    else:
        print("[app] AI detection DISABLED (--no-ai flag)")

    # Camera subsystem reset is handled by run-ai.sh (modprobe -r/modprobe nv_imx219).
    # Here we just verify nvargus-daemon is running before opening cameras.
    try:
        result = subprocess.run(['pgrep', '-x', 'nvargus-daemon'], capture_output=True)
        if result.returncode != 0:
            print("[app] nvargus-daemon not running — starting it...")
            subprocess.run(['sudo', 'systemctl', 'start', 'nvargus-daemon'],
                           timeout=10, capture_output=True)
            time.sleep(3)
        print("[app] nvargus-daemon is running.")
    except Exception as e:
        print(f"[app] nvargus-daemon restart skipped: {e}")

    # Start camera streams sequentially with delay.
    # Starting both simultaneously after a restart can garble sensor-id=1.
    scout_cam.start()
    time.sleep(2)  # Let Scout's ISP pipeline fully initialize before Sniper
    sniper_cam.start()

    # Center gimbal to forward-facing home position on startup
    gimbal.center()
    print(f"[app] Gimbal centered to home (pitch={PITCH_HOME}°, yaw=0°).")

    # Apply reduced Yaw Vmax on every startup to prevent motor overheating.
    # The 2805/100T yaw motor runs hot at default Vmax=88. Lowering to 60
    # reduces heat while retaining adequate slew speed for mosquito tracking.
    # This is in RAM only (EEPROM store command not supported), so we must
    # apply it on every boot.
    YAW_VMAX_ADDR = 15
    YAW_VMAX_TARGET = 40
    try:
        ser = gimbal._serial
        if ser and ser.is_open:
            import struct as _struct
            def _crc(data):
                c = 0xFFFF
                for b in data:
                    c ^= b << 8
                    for _ in range(8):
                        c = ((c << 1) ^ 0x1021 if c & 0x8000 else c << 1) & 0xFFFF
                return c
            # CMD 0x04 = SET_PARAMETER: [addr_lo, addr_hi, val_lo, val_hi]
            payload = _struct.pack('<HH', YAW_VMAX_ADDR, YAW_VMAX_TARGET)
            pkt = bytes([0xFA, len(payload), 0x04]) + payload
            pkt += _struct.pack('<H', _crc(pkt))
            ser.reset_input_buffer()
            ser.write(pkt)
            time.sleep(0.2)
            ser.read(200)  # Consume response
            print(f"[app] Yaw Vmax set to {YAW_VMAX_TARGET} (addr={YAW_VMAX_ADDR}).")
        else:
            print("[app] Yaw Vmax tuning skipped — gimbal serial not open.")
    except Exception as e:
        print(f"[app] Yaw Vmax tuning skipped: {e}")

    print(f"\n{'='*60}")
    print(f"  SNIPER MESSY MORTAR — Control Dashboard")
    print(f"  http://0.0.0.0:{args.port}")
    print(f"{'='*60}\n")

    # SAFE-001 §1: Gimbal power stays OFF until user explicitly enables it
    print("[app] Gimbal power is OFF. Enable via dashboard when ready.")

    app.run(host='0.0.0.0', port=args.port, threaded=True, debug=False)
