#!/usr/bin/env python3
# Implements: TEST-001 Layer 0 — Smoke Tests (no hardware required)
"""
test_smoke.py — Automated smoke test suite

Starts the Flask server in stub mode, hits every API endpoint, and verifies
the responses. Can run on any machine (Mac/PC/Jetson).

Usage:
    python3 tests/test_smoke.py
"""

import json
import sys
import time
import subprocess
import urllib.request
import urllib.error
import os

BASE_URL = "http://localhost:8000"
PASS = 0
FAIL = 0
SERVER_PROC = None


def test(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name} — {detail}")


def get(path):
    """HTTP GET, returns (status_code, body_string)."""
    try:
        r = urllib.request.urlopen(f"{BASE_URL}{path}", timeout=5)
        return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return 0, str(e)


def post(path, data=None):
    """HTTP POST with JSON body, returns (status_code, parsed_json)."""
    try:
        body = json.dumps(data or {}).encode()
        req = urllib.request.Request(
            f"{BASE_URL}{path}", data=body,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        r = urllib.request.urlopen(req, timeout=5)
        return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}


def start_server():
    """Start the Flask server in background for testing."""
    global SERVER_PROC
    print("🔧 Starting server in stub mode...")
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    SERVER_PROC = subprocess.Popen(
        [sys.executable, "app.py", "--no-ai", "--port", "8000"],
        cwd=app_dir,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    # Wait for server to be ready
    for _ in range(20):
        try:
            urllib.request.urlopen(f"{BASE_URL}/api/status", timeout=1)
            print("   Server ready.\n")
            return True
        except Exception:
            time.sleep(0.5)
    print("   ❌ Server failed to start!")
    return False


def stop_server():
    global SERVER_PROC
    if SERVER_PROC:
        SERVER_PROC.terminate()
        SERVER_PROC.wait(timeout=5)
        print("\n🛑 Server stopped.")


def run_tests():
    # ---- T0.2: Dashboard loads ----
    print("--- T0.2: Dashboard ---")
    code, body = get("/")
    test("Dashboard returns 200", code == 200)
    test("Dashboard contains title", "Sniper Messy Mortar" in body)
    test("Dashboard has scout feed", "/stream/scout" in body)
    test("Dashboard has sniper feed", "/stream/sniper" in body)

    # ---- T0.4: API endpoints accept POST ----
    print("\n--- T0.4: API Endpoints ---")
    code, data = get("/api/status")
    test("GET /api/status returns 200", code == 200)
    test("Status has gimbal key", "gimbal" in data)
    test("Status has relay key", "relay" in data)

    # ---- Gimbal API ----
    print("\n--- Gimbal API ---")
    code, data = post("/api/gimbal/set", {"pitch": 10, "yaw": 30})
    test("Gimbal set returns 200", code == 200)
    test("Gimbal pitch updated", data.get("pitch") == 10.0)
    test("Gimbal yaw updated", data.get("yaw") == 30.0)

    code, data = post("/api/gimbal/nudge", {"d_pitch": 5, "d_yaw": -10})
    test("Gimbal nudge returns 200", code == 200)
    test("Gimbal pitch nudged", data.get("pitch") == 15.0)
    test("Gimbal yaw nudged", data.get("yaw") == 20.0)

    code, data = post("/api/gimbal/center")
    test("Gimbal center returns 200", code == 200)
    test("Gimbal centered to 0,0", data.get("pitch") == 0.0 and data.get("yaw") == 0.0)

    # ---- T0.5: Click-to-aim math ----
    print("\n--- T0.5: Click-to-Aim ---")
    code, data = post("/api/gimbal/click", {"px": 640, "py": 400, "frame_w": 1280, "frame_h": 800})
    test("Center click returns 200", code == 200)
    test("Center click → pitch ≈ 0", abs(data.get("pitch", 99)) < 1.0, f"got {data.get('pitch')}")
    test("Center click → yaw ≈ 0", abs(data.get("yaw", 99)) < 1.0, f"got {data.get('yaw')}")

    # ---- T0.6: Software endstops ----
    print("\n--- T0.6: Software Endstops ---")
    code, data = post("/api/gimbal/set", {"pitch": 200, "yaw": 200})
    test("Pitch clamped to 20°", data.get("pitch") == 20.0, f"got {data.get('pitch')}")
    test("Yaw clamped to 80°", data.get("yaw") == 80.0, f"got {data.get('yaw')}")

    code, data = post("/api/gimbal/set", {"pitch": -200, "yaw": -200})
    test("Pitch clamped to -20°", data.get("pitch") == -20.0, f"got {data.get('pitch')}")
    test("Yaw clamped to -80°", data.get("yaw") == -80.0, f"got {data.get('yaw')}")

    # ---- Relay API ----
    print("\n--- Relay API ---")
    code, data = post("/api/relay/fire", {"duration": 0.1})
    test("Fire returns 200", code == 200)
    test("Fire confirms duration", data.get("duration") == 0.1)

    code, data = post("/api/relay/pump", {"state": True})
    test("Pump on returns 200", code == 200)
    test("Pump state is on", data.get("pump") == True)

    code, data = post("/api/relay/pump", {"state": False})
    test("Pump off returns 200", code == 200)
    test("Pump state is off", data.get("pump") == False)

    code, data = post("/api/relay/gimbal_power", {"state": True})
    test("Gimbal power on returns 200", code == 200)
    code, data = post("/api/relay/gimbal_power", {"state": False})
    test("Gimbal power off returns 200", code == 200)

    # ---- T0.3: MJPEG streams ----
    print("\n--- T0.3: MJPEG Streams ---")
    try:
        r = urllib.request.urlopen(f"{BASE_URL}/stream/scout", timeout=3)
        chunk = r.read(1024)
        test("Scout stream returns data", len(chunk) > 0)
        test("Scout stream is multipart JPEG", b"--frame" in chunk or b"JFIF" in chunk)
        r.close()
    except Exception as e:
        test("Scout stream accessible", False, str(e))

    # ---- T0.8: Status polling ----
    print("\n--- T0.8: Status Polling ---")
    code, body = get("/api/status")
    data = json.loads(body) if body else {}
    test("Status has gimbal.pitch", "pitch" in data.get("gimbal", {}))
    test("Status has relay.pump", "pump" in data.get("relay", {}))
    test("Status has ai.enabled", "enabled" in data.get("ai", {}))


if __name__ == "__main__":
    if not start_server():
        sys.exit(1)

    try:
        run_tests()
    finally:
        stop_server()

    print(f"\n{'='*50}")
    print(f"  RESULTS: {PASS} passed, {FAIL} failed")
    print(f"{'='*50}")
    sys.exit(0 if FAIL == 0 else 1)
