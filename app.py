# Implements: SW-001 §2 — Flask server, MJPEG streams, REST API
"""
app.py — Sniper Messy Mortar Flask Server

The central orchestrator. Provides:
  - MJPEG video streams for Scout and Sniper cameras
  - REST API for gimbal control, relay switching, and AI tuning
  - Serves the web dashboard (templates/index.html)

Usage:
  python app.py              # Starts on http://0.0.0.0:5000
  python app.py --no-ai      # Disable YOLO (for hardware-only testing)
"""

import argparse
import atexit
import os
import re
import subprocess
import sys
import time
from flask import Flask, render_template, Response, request, jsonify

from hardware import (
    RelayController, GimbalController, pixel_to_angle,
    YAW_LIMIT, PITCH_LIMIT
)
from vision import CameraStream, YOLODetector

# ============================================================================
# FLASK APP INITIALIZATION
# ============================================================================
app = Flask(__name__)
APP_DIR = os.path.dirname(os.path.abspath(__file__))

# Hardware controllers (initialized at module level for atexit cleanup)
relay = RelayController()
gimbal = GimbalController()

# Camera streams — dimensions must match HW-001 §2
# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
# CUSTOMIZE: Adjust resolution/fps to match your actual camera capabilities.
# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
scout_cam = CameraStream(sensor_id=0, width=1280, height=800, fps=120, name="Scout")
sniper_cam = CameraStream(sensor_id=1, width=1920, height=1080, fps=30, name="Sniper")

# AI detector (lazy-init — may be disabled via --no-ai flag)
detector = None


# ============================================================================
# CLEANUP — SAFE-001 §2: Guarantee all hardware is safe on exit
# ============================================================================
def cleanup():
    print("\n[app] Shutting down...")
    scout_cam.stop()
    sniper_cam.stop()
    gimbal.cleanup()
    relay.cleanup()
    print("[app] Shutdown complete.")

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
    return render_template('index.html',
                           yaw_limit=YAW_LIMIT,
                           pitch_limit=PITCH_LIMIT)


# ============================================================================
# GIMBAL API
# ============================================================================

@app.route('/api/gimbal/set', methods=['POST'])
def api_gimbal_set():
    """Set absolute gimbal angles. Body: {"pitch": float, "yaw": float}"""
    data = request.get_json(force=True)
    pitch = float(data.get('pitch', 0))
    yaw = float(data.get('yaw', 0))
    gimbal.set_angles(pitch, yaw)
    return jsonify(gimbal.get_status())


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
    Click-to-aim: receive pixel coordinates from a video feed click,
    convert to angles, and move the gimbal.
    Body: {"px": int, "py": int, "frame_w": int, "frame_h": int}
    """
    data = request.get_json(force=True)
    px = int(data.get('px', 0))
    py = int(data.get('py', 0))
    fw = int(data.get('frame_w', 1280))
    fh = int(data.get('frame_h', 800))

    pitch, yaw = pixel_to_angle(px, py, fw, fh)
    gimbal.set_angles(pitch, yaw)
    return jsonify({"target_px": [px, py], **gimbal.get_status()})


# ============================================================================
# RELAY API
# ============================================================================

@app.route('/api/relay/fire', methods=['POST'])
def api_relay_fire():
    """
    Fire the water pump for a specified duration.
    Body: {"duration": float}  (seconds, 0.05–2.0)
    """
    data = request.get_json(force=True)
    duration = float(data.get('duration', 0.3))
    relay.fire_pump(duration)
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
# STATUS API
# ============================================================================

@app.route('/api/status')
def api_status():
    """Return full system status as JSON."""
    return jsonify({
        "gimbal": gimbal.get_status(),
        "relay": relay.get_status(),
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
    "serial": {
        "name": "Serial / Gimbal Tests (Layer 1)",
        "description": "UART comms, Storm32 handshake, full angle sweep",
        "script": "tests/test_serial.py",
        "args": ["--sweep"],
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
        "description": "Click-to-aim math, gimbal repeatability, full sweep",
        "script": "tests/test_accuracy.py",
        "args": [],
        "layer": 4,
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

    # Start camera streams
    scout_cam.start()
    sniper_cam.start()

    print(f"\n{'='*60}")
    print(f"  SNIPER MESSY MORTAR — Control Dashboard")
    print(f"  http://0.0.0.0:{args.port}")
    print(f"{'='*60}\n")

    # SAFE-001 §1: Gimbal power stays OFF until user explicitly enables it
    print("[app] Gimbal power is OFF. Enable via dashboard when ready.")

    app.run(host='0.0.0.0', port=args.port, threaded=True, debug=False)
