# Implements: SW-001 §2.10 — GUI Diagnostics Suite
"""
diagnostics.py — Registry of fine-grained, individually runnable diagnostics
for the dashboard's Diagnostics tab.

Each test is registered with @test(...) and returns a dict:
    {"status": "pass" | "warn" | "fail" | "skip", "message": str, "data": {...}}

Tests flagged actuator=True move hardware / open valves and are refused by
run_test() unless confirm=True (SW-001 §2.10 actuator safety).

No mock data (project rule): absent hardware -> fail/skip with a diagnostic
message, never fabricated readings.
"""

import os
import subprocess
import time

APP_DIR = os.path.dirname(os.path.abspath(__file__))

_CTX = {}     # hardware handles injected by app.py via init()
TESTS = []    # ordered registry


# ============================================================================
# FRAMEWORK
# ============================================================================

def init(**ctx):
    """app.py injects hardware handles (relay, gimbal, pressure, cams, ...)."""
    _CTX.update(ctx)


def _c(name):
    obj = _CTX.get(name)
    if callable(obj) and name in ("detector", "arc_comp"):
        return obj()  # lazily-bound getters
    return obj


def test(tid, name, category, description, actuator=False):
    def deco(fn):
        TESTS.append({"id": tid, "name": name, "category": category,
                      "description": description, "actuator": actuator, "fn": fn})
        return fn
    return deco


def _ok(msg, **data):   return {"status": "pass", "message": msg, "data": data}
def _warn(msg, **data): return {"status": "warn", "message": msg, "data": data}
def _fail(msg, **data): return {"status": "fail", "message": msg, "data": data}
def _skip(msg, **data): return {"status": "skip", "message": msg, "data": data}


def list_tests():
    cats, seen = [], set()
    for t in TESTS:
        if t["category"] not in seen:
            seen.add(t["category"]); cats.append(t["category"])
    return {"tests": [{k: t[k] for k in ("id", "name", "category", "description", "actuator")}
                      for t in TESTS],
            "categories": cats}


def run_test(tid, confirm=False):
    t = next((t for t in TESTS if t["id"] == tid), None)
    if t is None:
        return {"id": tid, "status": "fail", "message": f"Unknown test: {tid}"}
    if t["actuator"] and not confirm:
        return {"id": tid, "status": "skip",
                "message": "Actuator test — enable 'arm actuator tests' to run."}
    t0 = time.time()
    try:
        r = t["fn"]() or _fail("test returned nothing")
    except Exception as e:
        r = _fail(f"exception: {type(e).__name__}: {e}")
    r["id"] = tid
    r["elapsed_ms"] = round((time.time() - t0) * 1000, 1)
    return r


def run_category(category, confirm=False):
    return [run_test(t["id"], confirm=confirm) for t in TESTS if t["category"] == category]


# ---- shared helpers --------------------------------------------------------

def _sh(cmd, timeout=15):
    """Run a shell command, return (rc, output)."""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).strip()
    except Exception as e:
        return -1, str(e)


def _i2c_probe(bus, addr):
    """True if a device ACKs at addr on bus (read probe, non-destructive)."""
    try:
        import smbus2
        b = smbus2.SMBus(bus)
        try:
            b.read_byte(addr)
            return True
        finally:
            b.close()
    except Exception:
        return False


def _frame_stats(cam):
    """(frame, mean_brightness, laplacian_variance) or (None, 0, 0)."""
    f = cam.get_frame() if cam else None
    if f is None:
        return None, 0.0, 0.0
    import cv2
    g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
    return f, float(g.mean()), float(cv2.Laplacian(g, cv2.CV_64F).var())


def _sample_psi(n, dt):
    p = _c("pressure")
    vals = []
    for _ in range(n):
        v = p.read_psi()
        if v is not None:
            vals.append(v)
        time.sleep(dt)
    return vals


def _std(vals):
    if len(vals) < 2:
        return 0.0
    m = sum(vals) / len(vals)
    return (sum((v - m) ** 2 for v in vals) / (len(vals) - 1)) ** 0.5


# ============================================================================
# PRESSURE / TRANSDUCER (ECO-004, SW-001 §2.9)
# ============================================================================

@test("press_ads_detect", "ADS1115 on I2C bus", "Pressure / Transducer",
      "ADC must ACK at 0x48 on bus 1 (Pin 27/28).")
def _t_press_ads():
    from hardware import PRESSURE_I2C_BUS, PRESSURE_ADS1115_ADDR
    if _i2c_probe(PRESSURE_I2C_BUS, PRESSURE_ADS1115_ADDR):
        return _ok(f"ADS1115 ACKs at 0x{PRESSURE_ADS1115_ADDR:02X} on bus {PRESSURE_I2C_BUS}")
    return _fail(f"No ACK at 0x{PRESSURE_ADS1115_ADDR:02X} on bus {PRESSURE_I2C_BUS} — "
                 "check VDD=Pin1 3.3V, SDA=Pin27, SCL=Pin28, ADDR=GND")


@test("press_connected", "PressureSensor connected", "Pressure / Transducer",
      "Driver poll thread sees the ADC (no synthetic data).")
def _t_press_conn():
    s = _c("pressure").get_status()
    return _ok("connected", **s) if s.get("connected") else _fail("driver reports disconnected", **s)


@test("press_reading_sane", "Reading in range", "Pressure / Transducer",
      "PSI within 0-100 and tap volts within the divider window.")
def _t_press_sane():
    s = _c("pressure").get_status()
    psi, v = s.get("psi"), s.get("volts")
    if psi is None:
        return _skip("no reading (sensor disconnected)")
    if not (0.0 <= psi <= 100.0):
        return _fail(f"PSI out of range: {psi}")
    if v is not None and not (0.25 <= v <= 3.2):
        return _fail(f"tap voltage {v:.3f}V outside 0.28-3.09V divider window — check R1/R2")
    return _ok(f"{psi:.1f} PSI @ {v:.3f}V tap")


@test("press_idle_zero", "Zero-pressure baseline", "Pressure / Transducer",
      "With system depressurized, expect ~0 PSI (transducer 0.5V).")
def _t_press_zero():
    psi = _c("pressure").read_psi()
    if psi is None:
        return _skip("no reading")
    if psi <= 3.0:
        return _ok(f"baseline {psi:.2f} PSI")
    return _warn(f"{psi:.1f} PSI — depressurize first, or transducer offset needs calibration")


@test("press_noise", "Reading noise/stability", "Pressure / Transducer",
      "Std-dev of ~15 samples over 3s; noisy wiring shows here.")
def _t_press_noise():
    vals = _sample_psi(15, 0.2)
    if len(vals) < 5:
        return _skip("not enough samples (sensor disconnected?)")
    sd = _std(vals)
    if sd < 1.0:
        return _ok(f"σ={sd:.2f} PSI over {len(vals)} samples")
    return (_warn if sd < 2.5 else _fail)(f"noisy: σ={sd:.2f} PSI — check divider joints/grounds")


@test("press_poll_alive", "Poll thread alive (~5Hz)", "Pressure / Transducer",
      "Background sampler must be running and updating.")
def _t_press_poll():
    p = _c("pressure")
    th = getattr(p, "_thread", None)
    if th is None or not th.is_alive():
        return _fail("poll thread not running")
    return _ok("poll thread alive")


@test("press_charge_delta", "Pressure rises on charge", "Pressure / Transducer",
      "Runs pump 1s (solenoid closed) — PSI must increase. WATER SYSTEM MUST BE PLUMBED.",
      actuator=True)
def _t_press_charge():
    p, relay = _c("pressure"), _c("relay")
    before = p.read_psi()
    if before is None:
        return _skip("no pressure reading — connect ADS1115 first")
    relay.set_pump(True); time.sleep(1.0); relay.set_pump(False)
    time.sleep(0.6)
    after = p.read_psi()
    delta = (after or 0) - before
    if delta >= 1.0:
        return _ok(f"{before:.1f} → {after:.1f} PSI (Δ{delta:+.1f})")
    return _fail(f"no rise ({before:.1f} → {after:.1f} PSI) — pump, plumbing, or tee placement")


@test("press_leak_rate", "Leak-down rate", "Pressure / Transducer",
      "Watches PSI for 10s after charge — a fast drop means a leak.", actuator=True)
def _t_press_leak():
    p = _c("pressure")
    start = p.read_psi()
    if start is None or start < 3.0:
        return _skip(f"needs pressure in the accumulator (now {start}) — run charge test first")
    time.sleep(10)
    end = p.read_psi() or 0
    drop = start - end
    if drop <= 1.0:
        return _ok(f"{start:.1f} → {end:.1f} PSI in 10s (Δ{drop:.1f})")
    return (_warn if drop <= 3.0 else _fail)(f"leaking: {start:.1f} → {end:.1f} PSI in 10s")


@test("press_shot_delta", "Pressure drop per shot", "Pressure / Transducer",
      "Arms, fires one 10ms pulse, reports the PSI cost of a shot.", actuator=True)
def _t_press_shot():
    p, accum = _c("pressure"), _c("accum")
    if p.read_psi() is None:
        return _skip("no pressure reading")
    arm = accum.arm()
    if arm.get("status") != "armed":
        return _fail(f"arm failed: {arm}")
    time.sleep(0.5)
    before = p.read_psi()
    accum.fire_blocking(0.010)
    time.sleep(0.5)
    after = p.read_psi()
    accum.disarm()
    if before is None or after is None:
        return _fail("lost pressure reading mid-test")
    return _ok(f"shot cost {before - after:+.2f} PSI ({before:.1f} → {after:.1f})")


# ============================================================================
# I2C & GPIO
# ============================================================================

@test("i2c_bus1_scan", "I2C bus 1 scan", "I2C & GPIO",
      "Full i2cdetect of the header bus — expect 0x40 (PCA9685/INA3221) and 0x48 (ADS1115).")
def _t_i2c_scan():
    rc, out = _sh("i2cdetect -y -r 1", timeout=20)
    if rc != 0:
        return _fail(f"i2cdetect failed: {out[:200]}")
    found = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if not parts:
            continue
        row = int(parts[0].rstrip(':'), 16)
        for i, cell in enumerate(parts[1:]):
            if cell not in ("--", "UU"):
                found.append(f"0x{row + i:02X}")
    msg = f"devices: {', '.join(found) if found else 'none'}"
    if "0x48" in found and "0x40" in found:
        return _ok(msg, found=found)
    return _warn(msg + " (expected 0x40 and 0x48)", found=found)


@test("i2c_pca9685", "PCA9685 servo driver ACK", "I2C & GPIO",
      "Servo PWM chip must ACK at 0x40 on bus 1.")
def _t_i2c_pca():
    return _ok("0x40 ACKs on bus 1") if _i2c_probe(1, 0x40) else \
        _fail("no ACK at 0x40 — servos will not move (check PCA9685 wiring/power)")


@test("i2c_tfluna", "TF-Luna LiDAR probe", "I2C & GPIO",
      "Probes 0x10 on buses 1 and 7 (Pin 3/5 bus is disabled in the Yahboom DTB).")
def _t_i2c_luna():
    on1, on7 = _i2c_probe(1, 0x10), _i2c_probe(7, 0x10)
    if on1:
        return _ok("TF-Luna found on bus 1")
    if on7:
        return _warn("TF-Luna ACKs on bus 7 — code expects it per LIDAR_I2C_BUS")
    return _warn("TF-Luna not found (known issue: Pin 3/5 bus disabled — rewire to Pin 27/28)")


@test("gpio_pr05", "Solenoid line PR.05 state", "I2C & GPIO",
      "PR.05 (BCM16/T36) must be claimed as output by sentry-solenoid.")
def _t_gpio_pr05():
    rc, out = _sh("gpioinfo gpiochip0 2>/dev/null | grep 'PR.05'")
    if rc != 0 or not out:
        return _fail("PR.05 not found on gpiochip0")
    if "sentry-solenoid" in out and "output" in out:
        return _ok(out.strip())
    return _warn(f"unexpected state: {out.strip()}")


@test("gpio_padctl", "PADCTL pinmux (PR.04/PR.05)", "I2C & GPIO",
      "Both pads must read 0x05 (GPIO push-pull) — else pins float at boot.")
def _t_padctl():
    try:
        import mmap, struct
        with open("/dev/mem", "r+b") as f:
            m = mmap.mmap(f.fileno(), 0x10000, offset=0x02430000)
            vals = {off: struct.unpack("<I", m[off:off + 4])[0] for off in (0x90, 0x98)}
            m.close()
        bad = {f"0x{k:X}": f"0x{v:X}" for k, v in vals.items() if v != 0x5}
        if not bad:
            return _ok("PR.05(0x90)=0x5, PR.04(0x98)=0x5")
        return _fail(f"pads not in GPIO mode: {bad} — run configure_push_pull()")
    except PermissionError:
        return _skip("needs root (/dev/mem)")


# ============================================================================
# SERVO / GIMBAL
# ============================================================================

@test("servo_controller", "Servo controller active", "Servo / Gimbal",
      "Turret must be the PCA9685 servo backend and report connected.")
def _t_servo_ctrl():
    from hardware import ServoTurretController
    g = _c("gimbal")
    if not isinstance(g, ServoTurretController):
        return _warn(f"controller is {type(g).__name__}, not ServoTurretController")
    s = g.get_status()
    return _ok("servo controller connected", **s) if s.get("connected") else \
        _fail("servo controller reports disconnected", **s)


@test("servo_settings", "Servo settings sane", "Servo / Gimbal",
      "Interpolation speed/rate/nudge inside allowed bounds.")
def _t_servo_settings():
    g = _c("gimbal")
    speed = getattr(g, "INTERP_SPEED", None)
    rate = getattr(g, "INTERP_RATE_HZ", None)
    if speed is None:
        return _skip("not a servo controller")
    if 10 <= speed <= 500 and 20 <= rate <= 200:
        return _ok(f"speed={speed}°/s rate={rate}Hz")
    return _fail(f"out of bounds: speed={speed} rate={rate}")


@test("gimbal_center", "Center (home) move", "Servo / Gimbal",
      "Moves turret to (0,0) and verifies reported position.", actuator=True)
def _t_gimbal_center():
    g = _c("gimbal")
    g.center(); time.sleep(1.0)
    s = g.get_status()
    if abs(s.get("pitch", 99)) <= 1.5 and abs(s.get("yaw", 99)) <= 1.5:
        return _ok(f"home at pitch={s['pitch']:.1f}° yaw={s['yaw']:.1f}°")
    return _fail(f"did not reach home: {s}")


@test("gimbal_yaw_sweep", "Yaw sweep ±30°", "Servo / Gimbal",
      "Sweeps yaw -30 → +30 → 0. Watch for stalls/judder.", actuator=True)
def _t_yaw_sweep():
    g = _c("gimbal")
    for y in (-30, 30, 0):
        g.set_angles(0, y); time.sleep(1.2)
    s = g.get_status()
    return _ok(f"sweep complete, ended yaw={s['yaw']:.1f}°") if abs(s.get("yaw", 99)) <= 2 \
        else _fail(f"ended off-target: {s}")


@test("gimbal_pitch_sweep", "Pitch sweep ±10°", "Servo / Gimbal",
      "Sweeps pitch -10 → +10 → home.", actuator=True)
def _t_pitch_sweep():
    g = _c("gimbal")
    for p in (-10, 10, 0):
        g.set_angles(p, 0); time.sleep(1.2)
    s = g.get_status()
    return _ok(f"sweep complete, ended pitch={s['pitch']:.1f}°") if abs(s.get("pitch", 99)) <= 2 \
        else _fail(f"ended off-target: {s}")


@test("gimbal_limit_clamp", "Yaw limit enforcement", "Servo / Gimbal",
      "Commands yaw far beyond the ±limit — must clamp (SAFE-001 death-spiral guard).",
      actuator=True)
def _t_limit_clamp():
    import hardware
    g = _c("gimbal")
    limit = getattr(hardware, "SERVO_YAW_LIMIT", hardware.YAW_LIMIT)
    g.set_angles(0, 999); time.sleep(1.0)
    s = g.get_status()
    g.center()
    if s.get("yaw", 999) <= limit + 0.5:
        return _ok(f"999° request clamped to {s['yaw']:.1f}° (limit ±{limit}°)")
    return _fail(f"NOT CLAMPED: reported yaw {s.get('yaw')}° > limit {limit}° — SAFE-001 violation")


@test("gimbal_repeatability", "Move repeatability", "Servo / Gimbal",
      "Moves to (10,10), homes, repeats — both arrivals must match.", actuator=True)
def _t_repeat():
    g = _c("gimbal")
    arrivals = []
    for _ in range(2):
        g.set_angles(10, 10); time.sleep(1.2)
        s = g.get_status(); arrivals.append((s["pitch"], s["yaw"]))
        g.center(); time.sleep(1.0)
    dp = abs(arrivals[0][0] - arrivals[1][0]); dy = abs(arrivals[0][1] - arrivals[1][1])
    if dp <= 0.5 and dy <= 0.5:
        return _ok(f"repeatable within Δp={dp:.2f}° Δy={dy:.2f}°")
    return _warn(f"spread Δp={dp:.2f}° Δy={dy:.2f}° — check servo slop/brackets")


@test("gimbal_power_relay", "Gimbal power relay", "Servo / Gimbal",
      "Toggles the gimbal 12V relay OFF then back to its prior state.", actuator=True)
def _t_gimbal_power():
    relay = _c("relay")
    prior = relay.get_status().get("gimbal_power", False)
    relay.set_gimbal_power(False); time.sleep(0.5)
    off = relay.get_status().get("gimbal_power")
    relay.set_gimbal_power(prior); time.sleep(0.5)
    back = relay.get_status().get("gimbal_power")
    if off is False and back == prior:
        return _ok(f"toggled OFF and restored to {prior}")
    return _fail(f"relay state mismatch (off={off}, restored={back}, prior={prior})")


# ============================================================================
# CAMERAS
# ============================================================================

def _cam_frame_test(cam, name, w=1280, h=720):
    f, _, _ = _frame_stats(cam)
    if f is None:
        return _fail(f"{name}: no frame — camera not started or pipeline dead")
    if f.shape[1] != w or f.shape[0] != h:
        return _warn(f"{name}: unexpected shape {f.shape[1]}x{f.shape[0]} (want {w}x{h})")
    return _ok(f"{name}: {f.shape[1]}x{f.shape[0]} frame OK")


def _cam_fps_test(cam, name, seconds=2.0, min_fps=15):
    if cam is None or cam.get_frame() is None:
        return _skip(f"{name}: no frames")
    seen, t_end = set(), time.time() + seconds
    while time.time() < t_end:
        f = cam.get_frame()
        if f is not None:
            seen.add(hash(f[::173, ::173].tobytes()))
        time.sleep(0.01)
    fps = len(seen) / seconds
    if fps >= min_fps:
        return _ok(f"{name}: ~{fps:.0f} distinct FPS")
    return (_warn if fps >= 5 else _fail)(f"{name}: only ~{fps:.0f} FPS (want ≥{min_fps})")


def _cam_exposure_test(cam, name):
    f, mean, _ = _frame_stats(cam)
    if f is None:
        return _skip(f"{name}: no frames")
    if 10 <= mean <= 245:
        return _ok(f"{name}: mean brightness {mean:.0f}/255")
    return _warn(f"{name}: brightness {mean:.0f} — image {'black' if mean < 10 else 'blown out'}")


def _cam_focus_test(cam, name):
    f, _, lap = _frame_stats(cam)
    if f is None:
        return _skip(f"{name}: no frames")
    if lap >= 25:
        return _ok(f"{name}: focus metric {lap:.0f}")
    return _warn(f"{name}: focus metric {lap:.0f} (<25) — blurry, refocus lens")


@test("cam_scout_frame", "Scout frame capture", "Cameras", "Grabs a frame from CSI-0.")
def _t_scout_frame(): return _cam_frame_test(_c("scout_cam"), "Scout")

@test("cam_sniper_frame", "Sniper frame capture", "Cameras", "Grabs a frame from CSI-1.")
def _t_sniper_frame(): return _cam_frame_test(_c("sniper_cam"), "Sniper")

@test("cam_scout_fps", "Scout FPS", "Cameras", "Counts distinct frames over 2s (want ≥15).")
def _t_scout_fps(): return _cam_fps_test(_c("scout_cam"), "Scout")

@test("cam_sniper_fps", "Sniper FPS", "Cameras", "Counts distinct frames over 2s (want ≥15).")
def _t_sniper_fps(): return _cam_fps_test(_c("sniper_cam"), "Sniper")

@test("cam_scout_exposure", "Scout exposure", "Cameras", "Mean brightness sanity (not black/blown).")
def _t_scout_exp(): return _cam_exposure_test(_c("scout_cam"), "Scout")

@test("cam_sniper_exposure", "Sniper exposure", "Cameras", "Mean brightness sanity.")
def _t_sniper_exp(): return _cam_exposure_test(_c("sniper_cam"), "Sniper")

@test("cam_scout_focus", "Scout focus metric", "Cameras",
      "Laplacian sharpness — catches a knocked/defocused lens.")
def _t_scout_focus(): return _cam_focus_test(_c("scout_cam"), "Scout")

@test("cam_sniper_focus", "Sniper focus metric", "Cameras",
      "Laplacian sharpness on the gimbal camera.")
def _t_sniper_focus(): return _cam_focus_test(_c("sniper_cam"), "Sniper")


# ============================================================================
# AI / VISION
# ============================================================================

@test("ai_loaded", "YOLO detector loaded", "AI / Vision", "Detector object must exist (not --no-ai).")
def _t_ai_loaded():
    d = _c("detector")
    return _ok("detector loaded") if d is not None else _warn("AI disabled (--no-ai or load failure)")


@test("ai_model_file", "TensorRT engine present", "AI / Vision",
      "Prefer .engine over .pt (10x faster on Jetson).")
def _t_ai_model():
    eng = [p for p in ("best.engine", "models/yolov8n.engine") if os.path.exists(os.path.join(APP_DIR, p))]
    pt = [p for p in ("best.pt", "models/yolov8n.pt") if os.path.exists(os.path.join(APP_DIR, p))]
    if eng:
        return _ok(f"engine: {eng[0]}")
    if pt:
        return _warn(f"only .pt found ({pt[0]}) — export TensorRT engine for speed")
    return _fail("no model file found")


@test("ai_inference", "Inference smoke + latency", "AI / Vision",
      "One detect() on the live sniper frame; alerts on slow inference.")
def _t_ai_infer():
    d = _c("detector")
    if d is None:
        return _skip("AI disabled")
    f = _c("sniper_cam").get_frame()
    if f is None:
        return _skip("no sniper frame")
    t0 = time.time(); dets = d.detect(f); ms = (time.time() - t0) * 1000
    msg = f"{len(dets)} detections in {ms:.0f}ms"
    if ms <= 300:
        return _ok(msg)
    return (_warn if ms <= 1000 else _fail)(msg + " — slow; check TensorRT/power mode")


@test("ai_thresholds", "Detection thresholds sane", "AI / Vision",
      "Confidence must sit in a usable 0.05-0.95 band.")
def _t_ai_thresh():
    d = _c("detector")
    if d is None:
        return _skip("AI disabled")
    c = d.confidence
    return _ok(f"confidence={c}, min_box={d.min_box_area}px²") if 0.05 <= c <= 0.95 \
        else _fail(f"confidence {c} outside 0.05-0.95")


@test("math_pixel_to_angle", "pixel_to_angle() math", "AI / Vision",
      "Frame center must map to ~(0°,0°); corners inside limits.")
def _t_math_p2a():
    from hardware import pixel_to_angle
    p, y = pixel_to_angle(640, 360, 1280, 720)
    if abs(p) < 1.0 and abs(y) < 1.0:
        return _ok(f"center → pitch={p:.2f}° yaw={y:.2f}°")
    return _fail(f"center maps to pitch={p:.2f}° yaw={y:.2f}° (want ~0,0)")


@test("math_predictive_lead", "Predictive lead math", "AI / Vision",
      "Zero target velocity must not change the aim point.")
def _t_math_lead():
    from hardware import compute_predictive_lead
    p, y, info = compute_predictive_lead(5.0, 5.0, 2.0, 0.0, 0.0)
    if abs(y - 5.0) < 0.01:
        return _ok(f"zero-velocity lead: pitch {p:.2f}°, yaw {y:.2f}° (arc comp applies to pitch)")
    return _fail(f"unexpected lead with zero velocity: pitch={p}, yaw={y}, info={info}")


# ============================================================================
# LiDAR
# ============================================================================

@test("lidar_connected", "LiDAR connected", "LiDAR", "TF-Luna driver state.")
def _t_lidar_conn():
    s = _c("lidar").get_status()
    return _ok("connected", **s) if s.get("connected") else \
        _warn("not connected (known: Pin 3/5 bus disabled — rewire to Bus 1)", **s)


@test("lidar_range", "Distance in range", "LiDAR", "Reading must be 0.1-8m to be usable.")
def _t_lidar_range():
    l = _c("lidar")
    if not l.get_status().get("connected"):
        return _skip("LiDAR not connected")
    d = l.read_distance()
    return _ok(f"{d:.2f} m") if 0.1 <= d <= 8.0 else _warn(f"{d:.2f} m outside usable 0.1-8m")


@test("lidar_stability", "Distance stability", "LiDAR",
      "10 samples on a static scene; σ should be <5cm.")
def _t_lidar_stab():
    l = _c("lidar")
    if not l.get_status().get("connected"):
        return _skip("LiDAR not connected")
    vals = [l.read_distance() for _ in range(10) if not time.sleep(0.1)]
    sd = _std(vals)
    return _ok(f"σ={sd * 100:.1f} cm") if sd < 0.05 else _warn(f"σ={sd * 100:.1f} cm — jittery")


# ============================================================================
# SOLENOID / TRIGGER
# ============================================================================

@test("sol_backend", "libgpiod backend live", "Solenoid / Trigger",
      "Solenoid line must be real (not stub) — PR.05 via libgpiod.")
def _t_sol_backend():
    r = _c("relay")
    sol = getattr(r, "_solenoid", None)
    if sol is not None and getattr(sol, "available", False):
        return _ok("libgpiod line acquired (PR.05)")
    return _fail("solenoid is in STUB mode — python3-libgpiod missing or line unavailable")


@test("sol_rest_closed", "Valve closed at rest", "Solenoid / Trigger",
      "SAFE-001: solenoid must report CLOSED when idle.")
def _t_sol_rest():
    s = _c("relay").get_status()
    return _ok("closed") if not s.get("solenoid") else \
        _fail("SOLENOID REPORTS OPEN AT REST — investigate before powering 12V")


@test("sol_click", "Solenoid click test", "Solenoid / Trigger",
      "300ms open/close — listen for TWO clicks.", actuator=True)
def _t_sol_click():
    r = _c("relay")
    r.set_solenoid(True); time.sleep(0.3); r.set_solenoid(False)
    return _ok("pulse sent — did you hear two clicks?") if not r.get_status()["solenoid"] \
        else _fail("solenoid still reports OPEN after test")


@test("sol_pulse_timing", "10ms pulse timing", "Solenoid / Trigger",
      "Fires a firing-width pulse and measures actual wall time.", actuator=True)
def _t_sol_timing():
    r = _c("relay")
    t0 = time.time()
    r.set_solenoid(True); time.sleep(0.010); r.set_solenoid(False)
    ms = (time.time() - t0) * 1000
    if ms <= 40:
        return _ok(f"10ms pulse took {ms:.1f}ms wall time")
    return _warn(f"pulse took {ms:.1f}ms — GPIO/scheduler latency high")


@test("safe_fire_lockout", "Fire lockout when disarmed", "Solenoid / Trigger",
      "accum.fire() while DISARMED must refuse (SAFE-001). If broken, one 10ms pulse escapes.",
      actuator=True)
def _t_lockout():
    accum = _c("accum")
    if accum.get_status().get("armed"):
        return _skip("system is armed — disarm first, then run")
    r = accum.fire(0.010)
    if r.get("status") == "not_armed":
        return _ok("fire correctly refused while disarmed")
    return _fail(f"LOCKOUT FAILED — fire() returned {r}")


# ============================================================================
# PUMP / ACCUMULATOR
# ============================================================================

@test("pump_rest_off", "Pump off at rest", "Pump / Accumulator", "Relay CH1 must be LOW when idle.")
def _t_pump_rest():
    s = _c("relay").get_status()
    return _ok("pump off") if not s.get("pump") else _fail("PUMP REPORTS ON AT REST")


@test("pump_burst", "Pump 200ms burst", "Pump / Accumulator",
      "Short pump run — listen/feel for the diaphragm motor.", actuator=True)
def _t_pump_burst():
    r = _c("relay")
    r.fire_pump(0.2)
    time.sleep(0.3)
    return _ok("burst sent") if not r.get_status()["pump"] else _fail("pump still ON after burst")


@test("accum_cycle", "Arm → status → disarm cycle", "Pump / Accumulator",
      "Full accumulator cycle: charges (pump runs!), verifies ARMED, disarms.", actuator=True)
def _t_accum_cycle():
    accum = _c("accum")
    arm = accum.arm()
    if arm.get("status") != "armed":
        accum.disarm()
        return _fail(f"arm failed: {arm}")
    st = accum.get_status()
    dis = accum.disarm()
    if st.get("armed") and dis.get("status") == "disarmed":
        return _ok("arm/disarm cycle clean")
    return _fail(f"cycle inconsistent: status={st}, disarm={dis}")


@test("accum_config", "Accumulator config sane", "Pump / Accumulator",
      "Charge/topup/pulse tunables inside spec bounds (SW-001 §2.7).")
def _t_accum_cfg():
    cfg = _c("accum").get_status().get("config", {})
    ic = cfg.get("initial_charge_sec", 0); pm = cfg.get("default_pulse_ms", 0)
    if 0.5 <= ic <= 10 and 1 <= pm <= 2000:
        return _ok(f"charge={ic}s pulse={pm}ms cps={cfg.get('charge_per_shot')}")
    return _fail(f"config out of bounds: {cfg}")


@test("prime_keepalive", "Priming keepalive", "Pump / Accumulator",
      "Priming system status + keepalive thread reachable.")
def _t_prime():
    s = _c("primer").get_status()
    return _ok(f"primed={s.get('primed')} keepalive={s.get('settings', {}).get('keepalive_enabled')}", **{})


# ============================================================================
# CALIBRATION
# ============================================================================

@test("cal_visual_offsets", "Visual calibration offsets", "Calibration",
      "Camera↔nozzle offsets loaded and plausible (<10°).")
def _t_cal_vis():
    ct = _c("cal_table")
    p, y = ct.offset_pitch, ct.offset_yaw
    if abs(p) < 10 and abs(y) < 10:
        return _ok(f"offset pitch={p:.2f}° yaw={y:.2f}° (updated {ct.last_updated or 'never'})")
    return _warn(f"large offsets pitch={p:.1f}° yaw={y:.1f}° — recalibrate")


@test("cal_ballistic_table", "Ballistic table entries", "Calibration",
      "Distance→correction table from calibration.json.")
def _t_cal_ball():
    import json
    fp = os.path.join(APP_DIR, "calibration.json")
    if not os.path.exists(fp):
        return _warn("calibration.json missing — run fire-test calibration")
    with open(fp) as f:
        n = len(json.load(f).get("ballistic_table", {}))
    return _ok(f"{n} distance entries") if n else _warn("table empty — run fire-test calibration")


@test("cal_arc_comp", "Arc compensation value", "Calibration",
      "Stream-drop pitch offset must be 0-30°.")
def _t_cal_arc():
    v = _c("arc_comp")
    return _ok(f"{v}°") if 0 <= v <= 30 else _fail(f"{v}° outside 0-30°")


@test("cal_hit_detector", "Hit detector ready", "Calibration",
      "Before/after differencing needs a live sniper frame.")
def _t_cal_hit():
    return _ok("sniper frame available for hit detection") \
        if _c("sniper_cam").get_frame() is not None else _fail("no sniper frame")


# ============================================================================
# SYSTEM
# ============================================================================

@test("sys_thermal", "SoC temperatures", "System", "All thermal zones <70°C (warn), <85°C (fail).")
def _t_thermal():
    temps = []
    for zdir in sorted(os.listdir("/sys/class/thermal")):
        if zdir.startswith("thermal_zone"):
            try:
                with open(f"/sys/class/thermal/{zdir}/temp") as f:
                    temps.append(int(f.read().strip()) / 1000.0)
            except Exception:
                pass
    if not temps:
        return _skip("no thermal zones readable")
    mx = max(temps)
    if mx < 70:
        return _ok(f"max {mx:.1f}°C across {len(temps)} zones")
    return (_warn if mx < 85 else _fail)(f"max {mx:.1f}°C — check fan/airflow")


@test("sys_power_mode", "Power mode (MAXN)", "System",
      "nvpmodel should be MAXN with jetson_clocks for full inference speed.")
def _t_power():
    rc, out = _sh("nvpmodel -q 2>/dev/null | head -3")
    if rc != 0 or not out:
        return _skip("nvpmodel unavailable")
    return _ok(out.replace("\n", " · ")) if "MAXN" in out else \
        _warn(f"not MAXN: {out.splitlines()[-1]} — run: sudo nvpmodel -m 0 && sudo jetson_clocks")


@test("sys_disk", "Disk space", "System", "Root filesystem must keep >2GB free.")
def _t_disk():
    import shutil as sh
    free_gb = sh.disk_usage("/").free / 1e9
    return _ok(f"{free_gb:.1f} GB free") if free_gb > 2 else _fail(f"only {free_gb:.1f} GB free")


@test("sys_memory", "Available memory", "System", ">500MB must stay available (8GB board).")
def _t_mem():
    with open("/proc/meminfo") as f:
        for line in f:
            if line.startswith("MemAvailable"):
                mb = int(line.split()[1]) / 1024
                return _ok(f"{mb:.0f} MB available") if mb > 500 else \
                    _warn(f"only {mb:.0f} MB available — risk of OOM during inference")
    return _skip("MemAvailable not found")


@test("sys_nvargus", "nvargus camera daemon", "System",
      "GStreamer CSI capture requires nvargus-daemon.")
def _t_nvargus():
    rc, _ = _sh("pgrep -x nvargus-daemon")
    return _ok("running") if rc == 0 else _fail("nvargus-daemon not running — cameras will fail")


@test("sys_log_errors", "Recent log errors", "System",
      "Scans the last 300 lines of sentry.log for tracebacks/errors.")
def _t_logs():
    fp = os.path.join(APP_DIR, "sentry.log")
    if not os.path.exists(fp):
        return _skip("sentry.log not found (running in foreground?)")
    rc, out = _sh(f"tail -n 300 '{fp}' | grep -cE 'Traceback|ERROR|CRITICAL'")
    n = int(out) if out.isdigit() else 0
    return _ok("no recent errors") if n == 0 else _warn(f"{n} error lines in last 300 — check log")
