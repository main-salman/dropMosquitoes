# Implements: HW-001 §3-§6, SW-001 §2.2, §2.4-§2.7, SAFE-001 §1-§2
# Hardware abstraction layer for GPIO relays, Storm32 gimbal, TF-Luna LiDAR,
# overhead ballistic offset math, and predictive lead engine.
"""
hardware.py — Sniper Messy Mortar Hardware Control

Provides:
  - RelayController: GPIO-based relay switching for pump and gimbal power
  - GimbalController: Serial UART interface to the Storm32 BGC board
  - LiDARController: I2C interface to Benewake TF-Luna distance sensor
  - pixel_to_angle(): Pixel-to-degree math for click-to-aim
  - compute_ballistic_offset(): Overhead parabolic drop correction

SAFETY: All GPIO access wrapped in try/finally to guarantee LOW on crash.
"""

import math
import time
import struct
import threading

# ============================================================================
# HARDWARE STUB MODE
# When running on a dev machine (not a Jetson), we use stubs so the Flask
# server can still start and the GUI can be tested without real hardware.
# ============================================================================
try:
    import Jetson.GPIO as GPIO
    JETSON_AVAILABLE = True
except ImportError:
    JETSON_AVAILABLE = False
    print("[hardware] WARNING: Jetson.GPIO not found. Running in STUB mode.")

try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    print("[hardware] WARNING: pyserial not found. Gimbal commands will be no-ops.")

def configure_push_pull():
    """
    ECO-2026-004: Directly clear Bit 4 (Open Drain) from the pinmux registers of
    BCM 17 (PR.04) and BCM 27 (PY.00) to force them into standard 3.3V Push-Pull GPIO mode.
    Needs root privileges to write to /dev/mem.
    """
    try:
        import mmap
        import struct
        # PR.04 (Pin 11): Reg 0x02430098
        # PY.00 (Pin 13): Reg 0x0243d030
        with open("/dev/mem", "r+b") as f:
            mem = mmap.mmap(f.fileno(), 0x10000, offset=0x02430000)
            
            # PR.04 (Pin 11) - clear Bit 4 (Open Drain)
            val_pr4 = struct.unpack("<I", mem[0x98:0x9c])[0]
            new_pr4 = val_pr4 & ~(1 << 4)
            mem[0x98:0x9c] = struct.pack("<I", new_pr4)
            
            # PY.00 (Pin 13) - clear Bit 4 (Open Drain)
            val_py0 = struct.unpack("<I", mem[0xd030:0xd034])[0]
            new_py0 = val_py0 & ~(1 << 4)
            mem[0xd030:0xd034] = struct.pack("<I", new_py0)
            
            print(f"[PADMUX] Pinmux forced to Push-Pull: PR4={hex(new_pr4)}, PY0={hex(new_py0)}")
    except Exception as e:
        print(f"[PADMUX] WARNING: Could not force Push-Pull mode (needs root): {e}")


def configure_pwm_pinmux():
    """
    ECO-2026-008: Configure pinmux for PWM output on BCM 12 (Pin 32) and BCM 13 (Pin 33).
    These pins drive the Storm32 RC-0 (Pitch) and RC-2 (Yaw) inputs via hardware PWM.
    Without this, the pins are locked to INPUT mode and no PWM signal reaches the wires.
    Uses direct /dev/mem writes (same approach as configure_push_pull).
    Needs root privileges.
    """
    try:
        import mmap
        import struct
        with open("/dev/mem", "r+b") as f:
            # BCM 12 (Pin 32, PWM0) at register 0x2434080 → write 0x5 (output)
            mem1 = mmap.mmap(f.fileno(), 0x10000, offset=0x2430000)
            mem1[0x4080:0x4084] = struct.pack("<I", 0x5)
            mem1.close()

            # BCM 13 (Pin 33, PWM2) at register 0x2434040 → write 0x4 (output)
            mem2 = mmap.mmap(f.fileno(), 0x10000, offset=0x2430000)
            mem2[0x4040:0x4044] = struct.pack("<I", 0x4)
            mem2.close()

        print("[PADMUX] PWM pinmux configured: BCM12=0x5 (output), BCM13=0x4 (output)")
    except Exception as e:
        print(f"[PADMUX] WARNING: Could not configure PWM pinmux: {e}")


try:
    import smbus2
    I2C_AVAILABLE = True
except ImportError:
    I2C_AVAILABLE = False
    print("[hardware] WARNING: smbus2 not found. LiDAR will be stubbed.")


# ============================================================================
# GPIO PIN ASSIGNMENTS — ECO-2026-002
# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
# ROUTING: Jetson GPIO Header → 40-pin F/F Ribbon Cable → IDC40P Terminal Block
# All wiring connects to screw terminals on the IDC40P breakout, NOT the Jetson.
# Terminal numbers match physical pin numbers 1:1.
# See: https://www.jetsonhacks.com/nvidia-jetson-orin-nano-gpio-header-pinout/
# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
RELAY_PUMP_PIN = 17       # BCM 17 = Pin 11 → IDC40P Terminal 11 → Relay CH1 (Pump)
RELAY_GIMBAL_PIN = 27     # BCM 27 = Pin 13 → IDC40P Terminal 13 → Relay CH2 (Gimbal)
# ============================================================================


class RelayController:
    """
    Controls the Monk Makes Dual Relay via Jetson GPIO.

    CH1 (RELAY_PUMP_PIN):  Water pump. Pulsed for N ms to fire a shot.
    CH2 (RELAY_GIMBAL_PIN): Gimbal power. Held OFF on boot; turned ON
                            only after Jetson has initialized serial comms.

    SAFE-001 §1: Relay CH2 MUST initialize to OFF (gimbal unpowered at boot).
    SAFE-001 §2: All GPIO access uses try/finally to guarantee LOW on crash.
    """

    def __init__(self):
        global JETSON_AVAILABLE
        self._pump_state = False
        self._gimbal_state = True  # Always True since gimbal is directly powered via 2A fuse
        self._lock = threading.Lock()

        if JETSON_AVAILABLE:
            try:
                GPIO.setmode(GPIO.BCM)
                GPIO.setwarnings(False)
                GPIO.setup(RELAY_PUMP_PIN, GPIO.OUT, initial=GPIO.LOW)
                GPIO.setup(RELAY_GIMBAL_PIN, GPIO.OUT, initial=GPIO.LOW)
                configure_push_pull()
                print(f"[RelayController] GPIO initialized and Pinmux forced to Push-Pull. Pump=Pin{RELAY_PUMP_PIN}, Gimbal=Pin{RELAY_GIMBAL_PIN}")
            except OSError as e:
                # Device busy or unavailable – fall back to stub mode
                print(f"[RelayController] GPIO init failed ({e}); running in STUB mode.")
                JETSON_AVAILABLE = False
            except Exception as e:
                print(f"[RelayController] Unexpected GPIO init error: {e}; proceeding in STUB mode.")
                JETSON_AVAILABLE = False
        else:
            print("[RelayController] STUB MODE — no real GPIO control.")


    # Pre-pressurization settings (configurable via API)
    # Solves diaphragm pump pulsation inconsistency:
    # - stabilize_ms: Short burst to move diaphragm to end-of-stroke
    # - settle_ms: Wait for diaphragm spring to return to known start position
    # - Then fire actual pulse from a consistent pressure state
    stabilize_ms = 50         # Pre-fire stabilization burst (ms)
    settle_ms = 80            # Gap after stabilization for diaphragm return (ms)
    pre_pressurize = True     # Enable/disable pre-pressurization

    def fire_pump(self, duration_sec: float = 0.025):
        """
        Fire the water pump for a specified duration.
        Default: 25ms (micro-pulse for insect deterrence).

        If pre_pressurize is enabled, runs a stabilization sequence first
        to ensure consistent diaphragm pump pressure:
        1. Pump ON for stabilize_ms → positions diaphragm at end-of-stroke
        2. Pump OFF for settle_ms → diaphragm spring returns to known position
        3. Pump ON for actual pulse → consistent pressure every time

        Args:
            duration_sec: Pulse length in seconds (0.01 to 2.0).
        """
        duration_sec = max(0.01, min(duration_sec, 2.0))  # Clamp to safe range

        if self.pre_pressurize:
            print(f"[RelayController] FIRE! Stabilize {self.stabilize_ms}ms → "
                  f"settle {self.settle_ms}ms → pulse {duration_sec*1000:.0f}ms")
        else:
            print(f"[RelayController] FIRE! Pump ON for {duration_sec:.3f}s")

        def _pulse():
            with self._lock:
                try:
                    if self.pre_pressurize and self.stabilize_ms > 0:
                        # Step 1: Stabilization burst — move diaphragm to end-of-stroke
                        self._set_pump(True)
                        time.sleep(self.stabilize_ms / 1000.0)

                        # Step 2: Settle — let diaphragm spring return
                        self._set_pump(False)
                        time.sleep(self.settle_ms / 1000.0)

                    # Step 3: Actual fire pulse — from consistent starting pressure
                    self._set_pump(True)
                    time.sleep(duration_sec)
                finally:
                    # SAFE-001 §2: ALWAYS turn off, even on exception
                    self._set_pump(False)

        # Run in a thread so we don't block the Flask request
        threading.Thread(target=_pulse, daemon=True).start()

    def set_pump(self, state: bool):
        """Manual pump toggle (for the GUI override switches)."""
        with self._lock:
            self._set_pump(state)

    def _set_pump(self, state: bool):
        self._pump_state = state
        if JETSON_AVAILABLE:
            GPIO.output(RELAY_PUMP_PIN, GPIO.HIGH if state else GPIO.LOW)
        print(f"[RelayController] Pump {'ON' if state else 'OFF'}")

    def set_gimbal_power(self, state: bool):
        """
        Turn gimbal power ON or OFF (Bypassed via 2A inline fuse).
        Gimbal is always powered. Keep state as True.
        """
        with self._lock:
            self._gimbal_state = True
            print(f"[RelayController] Gimbal power relay bypassed (2A fuse). Gimbal is always ON.")

    # -- Status ---------------------------------------------------------------

    def get_status(self) -> dict:
        return {
            "pump": self._pump_state,
            "gimbal_power": self._gimbal_state
        }

    # -- Cleanup --------------------------------------------------------------

    def cleanup(self):
        """Ensure all relays are OFF and release GPIO pins."""
        print("[RelayController] Cleaning up GPIO...")
        try:
            if JETSON_AVAILABLE:
                GPIO.output(RELAY_PUMP_PIN, GPIO.LOW)
                GPIO.output(RELAY_GIMBAL_PIN, GPIO.LOW)
                GPIO.cleanup()
        except Exception as e:
            print(f"[RelayController] Cleanup error: {e}")


# ============================================================================
# PRIMING SYSTEM — Ensures water line is filled before firing
# ============================================================================

class PrimingSystem:
    """
    Manages water line priming to ensure water reaches the nozzle before
    the first shot.

    Features:
    - Pre-fire priming: Before any fire command, checks if primed.
      If not, aims nozzle straight down, pumps for configured duration,
      optionally auto-detects water flow via camera frame differencing.
    - Keep-alive: Background thread periodically pulses the pump to
      prevent air from creeping back into the line during idle periods.

    Settings (configurable via GUI):
    - prime_duration_ms: How long to pump for priming (default 3000ms)
    - keepalive_interval_min: Minutes between keep-alive pulses (default 5)
    - keepalive_pulse_ms: Keep-alive pump pulse duration (default 200ms)
    - auto_detect: Whether to use camera to confirm water flow
    """

    # Pitch angle that points the nozzle straight down
    PRIME_PITCH = 90.0  # Max downward pitch
    PRIME_YAW = 0.0     # Center yaw

    def __init__(self, relay: RelayController):
        self._relay = relay
        self._lock = threading.Lock()

        # State
        self._primed = False
        self._priming_in_progress = False
        self._last_prime_time = 0.0
        self._last_fire_time = 0.0

        # Settings (defaults)
        self.prime_duration_ms = 3000      # 3 seconds default
        self.keepalive_interval_min = 5    # 5 minutes
        self.keepalive_pulse_ms = 200      # 200ms pulse
        self.auto_detect = True            # Use camera to confirm
        self.keepalive_enabled = True

        # Keep-alive thread
        self._keepalive_thread = None
        self._keepalive_running = False

    def start_keepalive(self, gimbal=None):
        """Start the keep-alive background thread."""
        if self._keepalive_running:
            return
        self._keepalive_running = True
        self._gimbal_ref = gimbal
        self._keepalive_thread = threading.Thread(
            target=self._keepalive_loop, daemon=True, name="prime-keepalive")
        self._keepalive_thread.start()
        print(f"[Priming] Keep-alive started: every {self.keepalive_interval_min} min, "
              f"{self.keepalive_pulse_ms}ms pulse")

    def stop_keepalive(self):
        """Stop the keep-alive thread."""
        self._keepalive_running = False
        if self._keepalive_thread:
            self._keepalive_thread.join(timeout=2)
        print("[Priming] Keep-alive stopped")

    def _keepalive_loop(self):
        """Background thread: periodically pulse the pump."""
        while self._keepalive_running:
            interval_sec = self.keepalive_interval_min * 60
            time.sleep(interval_sec)

            if not self._keepalive_running or not self.keepalive_enabled:
                continue

            # Only pulse if we haven't fired recently
            since_last_fire = time.time() - self._last_fire_time
            if since_last_fire > interval_sec * 0.8:
                print(f"[Priming] Keep-alive pulse: {self.keepalive_pulse_ms}ms")
                self._relay.fire_pump(self.keepalive_pulse_ms / 1000.0)
                # Keep-alive doesn't count as "primed" because it's a tiny pulse

    def needs_priming(self) -> bool:
        """Check if the system needs priming before firing."""
        with self._lock:
            if not self._primed:
                return True
            # Re-prime if it's been too long since last fire
            since_last = time.time() - self._last_fire_time
            idle_threshold = self.keepalive_interval_min * 60 * 2
            if since_last > idle_threshold:
                self._primed = False
                return True
            return False

    def prime(self, gimbal=None, camera=None) -> dict:
        """
        Run the priming sequence:
        1. Aim nozzle straight down
        2. Pump for configured duration
        3. (Optional) Auto-detect water via camera
        4. Mark as primed

        Args:
            gimbal: ServoTurretController to aim the nozzle down
            camera: Sniper CameraStream for auto-detection (optional)

        Returns:
            dict with priming results
        """
        with self._lock:
            if self._priming_in_progress:
                return {"status": "already_priming"}
            self._priming_in_progress = True

        result = {"status": "priming", "duration_ms": self.prime_duration_ms}

        try:
            # Step 1: Aim straight down
            if gimbal:
                print(f"[Priming] Aiming nozzle down ({self.PRIME_PITCH}°, {self.PRIME_YAW}°)")
                # Save current position to restore later
                current_status = gimbal.get_status()
                restore_pitch = current_status.get("pitch", 0)
                restore_yaw = current_status.get("yaw", 0)

                gimbal.set_angles(self.PRIME_PITCH, self.PRIME_YAW)
                time.sleep(1.5)  # Let servo settle
                result["aimed_down"] = True

            # Step 2: Capture 'before' frame for auto-detection
            before_frame = None
            if self.auto_detect and camera:
                before_frame = camera.get_frame()
                if before_frame is not None:
                    before_frame = before_frame.copy()

            # Step 3: Pump for the configured duration
            duration_sec = self.prime_duration_ms / 1000.0
            print(f"[Priming] Pumping for {self.prime_duration_ms}ms...")
            self._relay.set_pump(True)
            time.sleep(duration_sec)
            self._relay.set_pump(False)
            result["pumped_sec"] = duration_sec

            # Step 4: Auto-detect water flow
            water_detected = False
            if self.auto_detect and camera and before_frame is not None:
                time.sleep(0.3)  # Brief settle
                after_frame = camera.get_frame()
                if after_frame is not None:
                    water_detected = self._detect_water_flow(before_frame, after_frame)
                    result["water_detected"] = water_detected

            if not self.auto_detect:
                water_detected = True  # Assume success without detection
                result["water_detected"] = "assumed"

            # Step 5: Restore gimbal position
            if gimbal:
                print(f"[Priming] Restoring gimbal to ({restore_pitch}°, {restore_yaw}°)")
                gimbal.set_angles(restore_pitch, restore_yaw)
                time.sleep(1.0)

            # Mark as primed
            with self._lock:
                self._primed = water_detected
                self._last_prime_time = time.time()
                self._last_fire_time = time.time()

            result["status"] = "primed" if water_detected else "prime_uncertain"
            result["timestamp"] = time.strftime("%H:%M:%S")
            print(f"[Priming] Complete: {'✅ Water detected' if water_detected else '⚠️ Uncertain'}")

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            print(f"[Priming] Error: {e}")
        finally:
            with self._lock:
                self._priming_in_progress = False

        return result

    def _detect_water_flow(self, before: 'np.ndarray', after: 'np.ndarray') -> bool:
        """
        Detect water flow by comparing before/after frames.
        Water exiting the nozzle creates a visible change in the camera feed.
        """
        try:
            import cv2
            import numpy as np

            before_gray = cv2.cvtColor(before, cv2.COLOR_BGR2GRAY)
            after_gray = cv2.cvtColor(after, cv2.COLOR_BGR2GRAY)

            before_gray = cv2.GaussianBlur(before_gray, (5, 5), 0)
            after_gray = cv2.GaussianBlur(after_gray, (5, 5), 0)

            diff = cv2.absdiff(before_gray, after_gray)
            _, thresh = cv2.threshold(diff, 20, 255, cv2.THRESH_BINARY)

            # Count changed pixels
            changed_pixels = cv2.countNonZero(thresh)
            total_pixels = thresh.shape[0] * thresh.shape[1]
            change_pct = changed_pixels / total_pixels * 100

            print(f"[Priming] Frame diff: {changed_pixels} pixels changed ({change_pct:.1f}%)")

            # If more than 0.5% of frame changed, water is flowing
            return change_pct > 0.5

        except Exception as e:
            print(f"[Priming] Detection error: {e}")
            return False

    def mark_fired(self):
        """Call this after every fire command to track last fire time."""
        with self._lock:
            self._last_fire_time = time.time()

    def get_status(self) -> dict:
        """Return priming status for the API."""
        with self._lock:
            since_prime = time.time() - self._last_prime_time if self._last_prime_time else None
            since_fire = time.time() - self._last_fire_time if self._last_fire_time else None
            return {
                "primed": self._primed,
                "priming_in_progress": self._priming_in_progress,
                "since_prime_sec": round(since_prime, 1) if since_prime else None,
                "since_fire_sec": round(since_fire, 1) if since_fire else None,
                "settings": {
                    "prime_duration_ms": self.prime_duration_ms,
                    "keepalive_interval_min": self.keepalive_interval_min,
                    "keepalive_pulse_ms": self.keepalive_pulse_ms,
                    "auto_detect": self.auto_detect,
                    "keepalive_enabled": self.keepalive_enabled,
                }
            }

    def update_settings(self, settings: dict):
        """Update priming settings from the API."""
        if "prime_duration_ms" in settings:
            self.prime_duration_ms = max(500, min(int(settings["prime_duration_ms"]), 10000))
        if "keepalive_interval_min" in settings:
            self.keepalive_interval_min = max(1, min(int(settings["keepalive_interval_min"]), 60))
        if "keepalive_pulse_ms" in settings:
            self.keepalive_pulse_ms = max(50, min(int(settings["keepalive_pulse_ms"]), 1000))
        if "auto_detect" in settings:
            self.auto_detect = bool(settings["auto_detect"])
        if "keepalive_enabled" in settings:
            self.keepalive_enabled = bool(settings["keepalive_enabled"])
        print(f"[Priming] Settings updated: {self.prime_duration_ms}ms prime, "
              f"{self.keepalive_interval_min}min keepalive, auto_detect={self.auto_detect}")



# ============================================================================
# SOFTWARE ENDSTOPS (SAFE-001 §2, User Spec §4)
# Hardware mechanical limits are wider (±130° yaw, ±45° pitch), but software
# clamps to the values below to protect wiring through cable glands/service loops.
# ============================================================================
YAW_LIMIT = 80.0      # Max ±80° yaw (160° total sweep)
PITCH_LIMIT = 100.0    # Max ±100° pitch — wide enough for down-mount → forward

# Mount compensation: the camera/lidar/nozzle assembly points DOWN at pitch=0°
# due to the physical gimbal mount orientation (USB/UART ports = "front").
# Negative pitch = tilt toward forward/horizontal.
# PITCH_HOME tilts the payload so it faces FORWARD by default.
PITCH_HOME = 0.0       # degrees — neutral start. Use WASD to find forward-facing angle.
                       # Storm32 oscillates if commanded beyond its mechanical pitch limit.


class GimbalController:
    """
    Controls the Storm32 BGC board via Serial UART.

    Sends RC-override style commands to RC_PITCH and RC_YAW pins.
    Implements software endstops and the "Death Spiral" unwind prevention.

    HW-001 §3: Serial on /dev/ttyUSB0 / /dev/ttyACM0 @ 115200 baud.
    SAFE-001 §2: Yaw hard-limited to ±80°, Pitch to ±20° (software endstops).
    """

    # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    # CUSTOMIZE: Set to your actual serial port.
    # USB-to-Serial/Storm32 USB: /dev/ttyACM0 or /dev/ttyUSB0
    # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    SERIAL_PORT = "/dev/ttyACM0"
    BAUD_RATE = 115200

    # Storm32 serial command IDs (o323BGC protocol)
    CMD_SET_ANGLES = 0x11  # Set Camera Angles command

    def __init__(self):
        self._yaw = 0.0          # Current yaw angle (degrees)
        self._pitch = PITCH_HOME  # Current pitch angle — start at forward-facing home
        self._lock = threading.Lock()
        self._serial = None
        if SERIAL_AVAILABLE:
            import os
            import time as _t

            # Dynamic port detection: probe each port with GET_VERSION to find Storm32.
            # USB serial prioritized (ECO-2026-008: PWM/UART dead on Yahboom).
            # Retry loop: USB devices may not exist yet at boot — kernel needs
            # time to enumerate USB after power-on (~5-10s on Orin Nano).
            ports_to_try = ["/dev/ttyACM0", "/dev/ttyACM1", "/dev/ttyUSB0", "/dev/ttyTHS1", "/dev/ttyTHS0"]
            MAX_RETRIES = 10
            RETRY_DELAY = 1.0  # seconds between retries

            for attempt in range(1, MAX_RETRIES + 1):
                for p in ports_to_try:
                    try:
                        if not os.path.exists(p):
                            continue
                        candidate = serial.Serial(
                            port=p,
                            baudrate=self.BAUD_RATE,
                            timeout=0.5
                        )
                        # Probe: send GET_VERSION (cmd 0x01) and check for Storm32 response
                        candidate.reset_input_buffer()
                        candidate.write(bytes([0xFA, 0x00, 0x01, 0x00, 0x01]))
                        _t.sleep(0.5)
                        if candidate.in_waiting > 0:
                            resp = candidate.read(candidate.in_waiting)
                            if len(resp) >= 2 and resp[0] == 0xFB:
                                self._serial = candidate
                                self.SERIAL_PORT = p
                                print(f"[GimbalController] Storm32 detected on {p} (version probe OK, {len(resp)} bytes, attempt {attempt})")
                                break
                            else:
                                print(f"[GimbalController] {p}: unexpected response {resp.hex()[:20]}, skipping")
                                candidate.close()
                        else:
                            print(f"[GimbalController] {p}: no response to GET_VERSION probe, skipping")
                            candidate.close()
                    except Exception as e:
                        print(f"[GimbalController] Failed to probe {p}: {e}")

                if self._serial:
                    break  # Found the Storm32, stop retrying
                if attempt < MAX_RETRIES:
                    print(f"[GimbalController] No Storm32 found (attempt {attempt}/{MAX_RETRIES}), waiting {RETRY_DELAY}s for USB...")
                    _t.sleep(RETRY_DELAY)

            if not self._serial:
                print(f"[GimbalController] Serial FAILED on all ports after {MAX_RETRIES} attempts. Running in STUB mode.")
        else:
            print("[GimbalController] STUB MODE — no serial available.")

    def set_angles(self, pitch: float, yaw: float):
        """
        Command the gimbal to absolute pitch/yaw angles (in degrees).

        Applies software endstops before sending. Values are clamped, not rejected,
        so the gimbal always moves as close as possible to the requested position.

        Args:
            pitch: Target pitch angle (-20 to +20 degrees).
            yaw: Target yaw angle (-80 to +80 degrees).
        """
        with self._lock:
            # Clamp to software endstops (SAFE-001 §2)
            self._pitch = max(-PITCH_LIMIT, min(PITCH_LIMIT, pitch))
            self._yaw = max(-YAW_LIMIT, min(YAW_LIMIT, yaw))

            if self._serial and self._serial.is_open:
                self._send_storm32_command(self._pitch, self._yaw)
            else:
                print(f"[GimbalController] STUB: pitch={self._pitch:.1f}° yaw={self._yaw:.1f}°")

    def nudge(self, d_pitch: float = 0.0, d_yaw: float = 0.0):
        """
        Relative movement (for WASD manual control).
        Adds delta to current position and re-clamps.
        """
        self.set_angles(self._pitch + d_pitch, self._yaw + d_yaw)

    def center(self):
        """Return gimbal to home position (PITCH_HOME, 0).
        PITCH_HOME compensates for the downward-pointing mount so that
        'centered' means the camera/nozzle faces FORWARD."""
        self.set_angles(PITCH_HOME, 0.0)

    def _send_storm32_command(self, pitch_deg: float, yaw_deg: float):
        """
        Build and send a Storm32 o323BGC 'Set Camera Angles' packet.

        Packet format (o323BGC protocol, verified against ROS2 driver):
          Byte 0:       0xFA (start marker)
          Byte 1:       Data length (14 bytes)
          Byte 2:       Command ID (0x11 = CMD_SETANGLE)
          Bytes 3-6:    Pitch angle (float32, IEEE 754 little-endian, degrees)
          Bytes 7-10:   Roll angle (float32, always 0.0 for 2-axis)
          Bytes 11-14:  Yaw angle (float32, degrees)
          Bytes 15-16:  Flags (0x0000 = unlimited mode)
          Bytes 17-18:  CRC (2 bytes, board does not verify — set to 0x0000)
        """
        roll_deg = 0.0

        # Pack angles as float32 (4 bytes each) + 2-byte flags
        payload = struct.pack('<fffH',
                              pitch_deg,   # pitch (float32)
                              roll_deg,    # roll (float32, unused)
                              yaw_deg,     # yaw (float32)
                              0)           # flags (0 = unlimited)

        data_len = len(payload)  # 14 bytes (4+4+4+2)
        cmd_id = self.CMD_SET_ANGLES

        # Build full packet: header + payload + 2-byte CRC
        packet = bytes([0xFA, data_len, cmd_id]) + payload
        packet += bytes([0x00, 0x00])  # CRC — board does not check

        try:
            self._serial.write(packet)
            print(f"[GimbalController] Sent o323BGC packet: {packet.hex().upper()}")
        except Exception as e:
            print(f"[GimbalController] Serial write error: {e}")


    def get_status(self) -> dict:
        return {
            "pitch": round(self._pitch, 1),
            "yaw": round(self._yaw, 1),
            "pitch_home": PITCH_HOME,
            "connected": self._serial is not None and self._serial.is_open
        }

    def cleanup(self):
        """Center gimbal and close serial port."""
        print("[GimbalController] Centering gimbal and closing serial...")
        try:
            self.center()
            time.sleep(0.2)
            if self._serial and self._serial.is_open:
                self._serial.close()
        except Exception as e:
            print(f"[GimbalController] Cleanup error: {e}")


# ============================================================================
# SERVO TURRET CONTROLLER (PCA9685 + MG996R) — HW-001 §3 (planned)
# High-torque geared pan/tilt using MG996R metal-gear servos driven by
# a PCA9685 16-channel I2C PWM driver board.
#
# Replaces the Storm32 brushless gimbal for applications requiring
# mechanical holding torque (e.g., fighting water hose spring tension).
#
# I2C Bus 1 (c240000.i2c), PCA9685 at address 0x40.
# IMPORTANT: Yahboom carrier board has an onboard INA3221 power monitor
#   ALSO at 0x40 on Bus 1. This creates an address collision.
#   Solution: Write via 0x40 (both chips receive), verify via 0x71
#   (PCA9685 Sub Address 1 — only PCA9685 responds).
#   Software reset (General Call 0x06) required at startup to clear
#   stuck EXTCLK bit from previous address-collision writes.
# Wiring: PCA9685 SDA/SCL on Jetson IDC40P Pin 27/28 (Bus 1).
# Power: Dedicated 12V→5V 10A buck converter (isolated from Jetson 5V rail).
# ============================================================================

# PCA9685 servo channel assignments
SERVO_CH_YAW = 0     # Channel 0 = Pan (horizontal rotation)
SERVO_CH_PITCH = 1   # Channel 1 = Tilt (vertical rotation)

# MG996R servo pulse range (microseconds)
SERVO_MIN_PULSE = 500    # 0° position
SERVO_MAX_PULSE = 2500   # 180° position
SERVO_RANGE_DEG = 180.0  # Total mechanical range

# Servo endstops (degrees from center, where center = 90° servo = 0° turret)
SERVO_YAW_LIMIT = 80.0    # ±80° yaw (same as Storm32 for software compatibility)
SERVO_PITCH_LIMIT = 90.0  # ±90° pitch (full servo range)

# PCA9685 register map (NXP datasheet §7.3)
_PCA9685_MODE1     = 0x00
_PCA9685_PRESCALE  = 0xFE
_PCA9685_LED0_ON_L = 0x06  # Each channel is 4 registers: ON_L, ON_H, OFF_L, OFF_H


class ServoTurretController:
    """
    Controls a 2-axis geared pan/tilt turret via PCA9685 I2C servo driver.

    Uses smbus2 for direct I2C register access, bypassing Adafruit Blinka
    which maps to the wrong I2C bus on the Yahboom carrier board.

    Provides the SAME API as GimbalController so the rest of the system
    (app.py, dashboard, AI pipeline, tests) requires ZERO changes.

    Implements: SW-001 §2.2 (TurretAgent interface)
    Safety: SAFE-001 §2 (software endstops)

    Hardware:
        - PCA9685 on I2C Bus 1, address 0x40 (shared with INA3221)
        - Verify address: 0x71 (PCA9685 Sub Address 1, no collision)
        - Wiring: Jetson Pin 27 (SDA) / Pin 28 (SCL)
        - Channel 0: MG996R yaw servo (pan)
        - Channel 1: MG996R pitch servo (tilt)
        - Power: 12V→5V 10A buck converter (isolated from Jetson)
    """

    PCA9685_ADDRESS = 0x40   # Write address (INA3221 also here — collision)
    PCA9685_READ    = 0x71   # PCA9685 Sub Address 1 (read without INA3221)
    I2C_BUS = 1              # Bus 1 = c240000.i2c (Pin 27/28 on Yahboom)
    PWM_FREQ = 50            # 50 Hz standard servo frequency

    # Smooth interpolation parameters
    INTERP_RATE_HZ = 100     # PWM update rate for smooth motion
    INTERP_SPEED   = 120.0   # Max degrees/second travel speed
    INTERP_EPSILON = 0.15    # Degrees — close enough to stop interpolating

    def __init__(self):
        self._target_yaw = 0.0      # Where we WANT to be (set by API)
        self._target_pitch = PITCH_HOME
        self._current_yaw = 0.0     # Where we ARE (actual PWM output)
        self._current_pitch = PITCH_HOME
        self._yaw = 0.0             # Public state (matches target for API compat)
        self._pitch = PITCH_HOME
        self._lock = threading.Lock()
        self._bus = None
        self._interp_thread = None
        self._interp_stop = threading.Event()

        if I2C_AVAILABLE:
            try:
                self._bus = smbus2.SMBus(self.I2C_BUS)
                # Verify PCA9685 is present
                self._bus.read_byte_data(self.PCA9685_ADDRESS, _PCA9685_MODE1)

                # Initialize PCA9685
                self._init_pca9685()
                print(f"[ServoTurret] PCA9685 initialized on I2C bus {self.I2C_BUS}, "
                      f"address 0x{self.PCA9685_ADDRESS:02X} via smbus2")

                # Start smooth interpolation thread
                self._interp_thread = threading.Thread(
                    target=self._interpolation_loop, daemon=True,
                    name="servo-interp")
                self._interp_thread.start()

                # Center servos on startup (instant — no interpolation needed)
                self._set_servo_angle(SERVO_CH_YAW, 0.0)
                self._set_servo_angle(SERVO_CH_PITCH, PITCH_HOME)
                print(f"[ServoTurret] Centered. Smooth interpolation "
                      f"at {self.INTERP_RATE_HZ}Hz, {self.INTERP_SPEED}°/s")
            except Exception as e:
                print(f"[ServoTurret] PCA9685 init FAILED: {e}")
                print("[ServoTurret] Running in STUB mode.")
                self._bus = None
        else:
            print("[ServoTurret] STUB MODE — smbus2 not available.")

    def _interpolation_loop(self):
        """Background thread: smoothly moves servos toward target angles.

        Runs at INTERP_RATE_HZ, moving at most INTERP_SPEED degrees/second.
        Sleeps when current == target to avoid wasting CPU.
        """
        dt = 1.0 / self.INTERP_RATE_HZ
        max_step = self.INTERP_SPEED * dt  # Max degrees per tick

        while not self._interp_stop.is_set():
            with self._lock:
                ty, tp = self._target_yaw, self._target_pitch
                cy, cp = self._current_yaw, self._current_pitch

            dy = ty - cy
            dp = tp - cp

            # If already at target, sleep longer to save CPU
            if abs(dy) < self.INTERP_EPSILON and abs(dp) < self.INTERP_EPSILON:
                self._interp_stop.wait(timeout=0.05)
                continue

            # Move toward target, clamping step size for smooth motion
            if abs(dy) <= max_step:
                ny = ty
            else:
                ny = cy + max_step * (1 if dy > 0 else -1)

            if abs(dp) <= max_step:
                np_ = tp
            else:
                np_ = cp + max_step * (1 if dp > 0 else -1)

            # Write to hardware
            try:
                self._set_servo_angle(SERVO_CH_YAW, ny)
                self._set_servo_angle(SERVO_CH_PITCH, np_)
            except Exception:
                pass  # I2C errors handled silently in interpolation

            with self._lock:
                self._current_yaw = ny
                self._current_pitch = np_

            self._interp_stop.wait(timeout=dt)

    def _init_pca9685(self):
        """Initialize PCA9685: software reset, set 50Hz PWM, wake up.
        
        Uses dual-address pattern to handle INA3221 collision at 0x40:
        - Write via 0x40 (both PCA9685 and INA3221 receive)
        - Verify via 0x71 (PCA9685 Sub Address 1, no collision)
        
        Software reset clears EXTCLK bit that may be stuck from
        previous writes through the colliding address.
        """
        addr = self.PCA9685_ADDRESS
        read = self.PCA9685_READ

        # Software reset via General Call — clears stuck EXTCLK bit
        try:
            self._bus.write_byte(0x00, 0x06)
        except Exception:
            pass  # General call may NAK, that's OK
        time.sleep(0.05)

        # Sleep mode + enable sub-addresses for verification reads
        # MODE1: SLEEP=1, SUB1=1, SUB2=1, SUB3=1 = 0x1E
        self._bus.write_byte_data(addr, _PCA9685_MODE1, 0x1E)
        time.sleep(0.005)

        # Set prescaler for 50 Hz: prescale = round(25MHz / (4096 × freq)) - 1
        prescale = round(25000000.0 / (4096 * self.PWM_FREQ)) - 1
        self._bus.write_byte_data(addr, _PCA9685_PRESCALE, prescale)
        time.sleep(0.005)

        # Verify prescaler via sub-address (collision-free read)
        ps_verify = self._bus.read_byte_data(read, _PCA9685_PRESCALE)

        # Wake up: AI=1, SUB1=1, SUB2=1, SUB3=1 = 0x2E
        self._bus.write_byte_data(addr, _PCA9685_MODE1, 0x2E)
        time.sleep(0.005)

        # Verify EXTCLK is clear
        mode1 = self._bus.read_byte_data(read, _PCA9685_MODE1)
        extclk = (mode1 >> 6) & 1
        if extclk:
            print(f"[ServoTurret] WARNING: EXTCLK stuck! Power-cycle PCA9685.")

        print(f"[ServoTurret] PCA9685 prescaler={ps_verify} ({self.PWM_FREQ}Hz) "
              f"MODE1=0x{mode1:02X} EXTCLK={extclk}")

    def _set_pwm(self, channel: int, on: int, off: int):
        """Set raw PWM on/off ticks (0-4095) for a channel."""
        reg = _PCA9685_LED0_ON_L + 4 * channel
        self._bus.write_byte_data(self.PCA9685_ADDRESS, reg, on & 0xFF)
        self._bus.write_byte_data(self.PCA9685_ADDRESS, reg + 1, on >> 8)
        self._bus.write_byte_data(self.PCA9685_ADDRESS, reg + 2, off & 0xFF)
        self._bus.write_byte_data(self.PCA9685_ADDRESS, reg + 3, off >> 8)

    def _pulse_to_ticks(self, pulse_us: float) -> int:
        """Convert pulse width (microseconds) to PCA9685 tick count (0-4095).
        At 50Hz, one period = 20000μs, so 4096 ticks = 20000μs."""
        period_us = 1000000.0 / self.PWM_FREQ  # 20000μs at 50Hz
        return int(pulse_us / period_us * 4096)

    def _deg_to_pulse(self, angle_deg: float) -> float:
        """Convert turret angle (-90..+90) to servo pulse width (μs).
        Turret 0° = servo 90° = center pulse.
        Maps linearly across SERVO_MIN_PULSE..SERVO_MAX_PULSE."""
        servo_angle = max(0.0, min(180.0, angle_deg + 90.0))
        fraction = servo_angle / 180.0
        return SERVO_MIN_PULSE + fraction * (SERVO_MAX_PULSE - SERVO_MIN_PULSE)

    def _set_servo_angle(self, channel: int, turret_deg: float):
        """Set a servo channel to a turret angle (degrees from center)."""
        pulse_us = self._deg_to_pulse(turret_deg)
        ticks = self._pulse_to_ticks(pulse_us)
        self._set_pwm(channel, 0, ticks)

    def set_angles(self, pitch: float, yaw: float):
        """
        Command the turret to absolute pitch/yaw angles (in degrees).

        Sets the TARGET position — the interpolation thread smoothly moves
        the servos there at INTERP_SPEED degrees/second.

        Args:
            pitch: Target pitch angle (clamped to ±SERVO_PITCH_LIMIT).
            yaw: Target yaw angle (clamped to ±SERVO_YAW_LIMIT).
        """
        with self._lock:
            # Clamp to software endstops (SAFE-001 §2)
            self._pitch = max(-SERVO_PITCH_LIMIT, min(SERVO_PITCH_LIMIT, pitch))
            self._yaw = max(-SERVO_YAW_LIMIT, min(SERVO_YAW_LIMIT, yaw))
            self._target_yaw = self._yaw
            self._target_pitch = self._pitch

        if not self._bus:
            print(f"[ServoTurret] STUB: pitch={self._pitch:.1f}° yaw={self._yaw:.1f}°")

    def nudge(self, d_pitch: float = 0.0, d_yaw: float = 0.0):
        """
        Relative movement (for WASD manual control).
        Adds delta to current TARGET position and re-clamps.
        API-compatible with GimbalController.nudge().
        """
        with self._lock:
            new_pitch = self._target_pitch + d_pitch
            new_yaw = self._target_yaw + d_yaw
        self.set_angles(new_pitch, new_yaw)

    def center(self):
        """Return turret to home position (PITCH_HOME, 0).
        API-compatible with GimbalController.center()."""
        self.set_angles(PITCH_HOME, 0.0)

    def get_status(self) -> dict:
        with self._lock:
            return {
                "pitch": round(self._pitch, 1),
                "yaw": round(self._yaw, 1),
                "pitch_home": PITCH_HOME,
                "connected": self._bus is not None
            }

    def cleanup(self):
        """Stop interpolation thread, center turret, and close I2C bus."""
        print("[ServoTurret] Shutting down...")
        self._interp_stop.set()
        if self._interp_thread:
            self._interp_thread.join(timeout=1.0)
        try:
            if self._bus:
                # Direct center (no interpolation — thread is stopped)
                self._set_servo_angle(SERVO_CH_YAW, 0.0)
                self._set_servo_angle(SERVO_CH_PITCH, PITCH_HOME)
                time.sleep(0.3)
                self._bus.close()
        except Exception as e:
            print(f"[ServoTurret] Cleanup error: {e}")


def create_turret_controller():
    """
    Factory function: auto-detect available turret hardware.

    Priority:
      1. PCA9685 I2C servo driver on smbus2 Bus 1 (new geared turret)
      2. Storm32 BGC USB serial (legacy brushless gimbal)
      3. Stub mode (no hardware)

    Returns a controller with the standard API:
        set_angles(pitch, yaw), nudge(d_pitch, d_yaw),
        center(), get_status(), cleanup()
    """
    # Try PCA9685 first via smbus2 (proven on Yahboom carrier board)
    if I2C_AVAILABLE:
        # Yahboom carrier board has INA3221 power monitor at 0x40 — same as
        # PCA9685 default address. The kernel driver blocks userspace access.
        # Unbind it first so smbus2 can talk to the PCA9685.
        _unbind_ina3221()

        try:
            bus = smbus2.SMBus(1)  # Bus 1 = Pin 27/28 on Yahboom
            # Software reset to clear any stuck state
            try:
                bus.write_byte(0x00, 0x06)
            except Exception:
                pass
            time.sleep(0.05)
            # Enable sub-addresses so we can verify via 0x71
            bus.write_byte_data(0x40, _PCA9685_MODE1, 0x1F)
            time.sleep(0.01)
            # Verify PCA9685 via sub-address 0x71 (no INA3221 collision)
            prescale = bus.read_byte_data(0x71, _PCA9685_PRESCALE)
            bus.close()
            if prescale == 0x54:  # TI Manufacturer ID = INA3221 leaked
                print("[TurretFactory] 0x71 reads as INA3221 — no PCA9685")
            else:
                print(f"[TurretFactory] PCA9685 confirmed via sub-addr 0x71 "
                      f"(prescale=0x{prescale:02X}) — using ServoTurretController")
                return ServoTurretController()
        except Exception as e:
            print(f"[TurretFactory] PCA9685 probe failed: {e}")

    # Fall back to Storm32 BGC (legacy)
    print("[TurretFactory] Falling back to GimbalController (Storm32 BGC)")
    return GimbalController()


def _unbind_ina3221():
    """Unbind INA3221 kernel driver from I2C address 0x40 if present.
    The Yahboom carrier board has an INA3221 power monitor chip at 0x40
    which conflicts with the PCA9685 servo driver's default address."""
    import subprocess
    import os as _os
    driver_path = "/sys/bus/i2c/devices/1-0040/driver"
    if not _os.path.exists(driver_path):
        return  # No driver bound — 0x40 is free

    try:
        driver_name = _os.readlink(driver_path).split("/")[-1]
        print(f"[TurretFactory] Kernel driver '{driver_name}' is claiming 0x40 — unbinding...")
        result = subprocess.run(
            ["sudo", "-n", "sh", "-c", f"echo 1-0040 > /sys/bus/i2c/drivers/{driver_name}/unbind"],
            capture_output=True, timeout=5
        )
        if result.returncode == 0:
            print("[TurretFactory] INA3221 unbound successfully — 0x40 is now free")
        else:
            # Try with password via stdin as fallback
            result = subprocess.run(
                ["sudo", "-S", "sh", "-c", f"echo 1-0040 > /sys/bus/i2c/drivers/{driver_name}/unbind"],
                input=b"yahboom\n", capture_output=True, timeout=5
            )
            if result.returncode == 0:
                print("[TurretFactory] INA3221 unbound (via password) — 0x40 is now free")
            else:
                print(f"[TurretFactory] WARNING: Could not unbind {driver_name} from 0x40")
                print(f"[TurretFactory] Run manually: sudo sh -c 'echo 1-0040 > /sys/bus/i2c/drivers/{driver_name}/unbind'")
    except Exception as e:
        print(f"[TurretFactory] INA3221 unbind error: {e}")


# ============================================================================
# TF-LUNA LiDAR (I2C) — HW-001 §6, SW-001 §2.5
# Benewake TF-Luna: I2C Bus 1, default address 0x10
# Reads distance in cm, converts to meters.
# Mounted co-axial with Sniper camera on gimbal payload plate.
# ============================================================================

LIDAR_I2C_BUS = 7  # Yahboom 40-pin header Pin 3/5 = Bus 7 (c250000.i2c)
LIDAR_I2C_ADDR = 0x10
LIDAR_REG_DIST_LO = 0x00   # Distance low byte
LIDAR_REG_DIST_HI = 0x01   # Distance high byte
LIDAR_REG_AMP_LO = 0x02    # Signal amplitude (strength) low
LIDAR_REG_AMP_HI = 0x03    # Signal amplitude (strength) high


class LiDARController:
    """
    I2C driver for the Benewake TF-Luna LiDAR.

    HW-001 §6: I2C Bus 1, address 0x10, Jetson Pins 3 (SDA) & 5 (SCL).
    SW-001 §2.5: Background polling at ~100Hz, exposes read_distance().

    The TF-Luna returns distance in centimeters. We convert to meters.
    Signal strength (amplitude) is also captured for quality filtering.
    """

    def __init__(self):
        self._distance_cm = 0       # Raw distance in cm
        self._distance_m = 0.0      # Converted to meters
        self._signal_strength = 0   # Amplitude (higher = better signal)
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._bus = None

        if I2C_AVAILABLE:
            try:
                self._bus = smbus2.SMBus(LIDAR_I2C_BUS)
                # Test read to verify device is present
                self._bus.read_byte_data(LIDAR_I2C_ADDR, LIDAR_REG_DIST_LO)
                print(f"[LiDARController] TF-Luna found on I2C bus {LIDAR_I2C_BUS}, addr 0x{LIDAR_I2C_ADDR:02X}")
            except Exception as e:
                print(f"[LiDARController] I2C FAILED: {e}. Running in STUB mode.")
                self._bus = None
        else:
            print("[LiDARController] STUB MODE — smbus2 not available.")

        # Start background polling
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def _poll_loop(self):
        """Background thread: continuously reads LiDAR distance."""
        while self._running:
            if self._bus is not None:
                try:
                    # Read 4 bytes: dist_lo, dist_hi, amp_lo, amp_hi
                    data = self._bus.read_i2c_block_data(
                        LIDAR_I2C_ADDR, LIDAR_REG_DIST_LO, 4
                    )
                    dist_cm = data[0] | (data[1] << 8)
                    amplitude = data[2] | (data[3] << 8)

                    with self._lock:
                        self._distance_cm = dist_cm
                        self._distance_m = dist_cm / 100.0
                        self._signal_strength = amplitude
                except Exception:
                    pass  # Transient I2C errors are normal, skip
            else:
                # STUB: simulate a distance for dev testing
                import random
                with self._lock:
                    self._distance_cm = random.randint(150, 350)  # 1.5m - 3.5m
                    self._distance_m = self._distance_cm / 100.0
                    self._signal_strength = random.randint(500, 2000)

            time.sleep(0.01)  # ~100Hz polling

    def read_distance(self) -> float:
        """Return the latest LiDAR distance reading in meters."""
        with self._lock:
            return self._distance_m

    def get_status(self) -> dict:
        """Return full LiDAR telemetry as a dict."""
        with self._lock:
            return {
                "distance_m": round(self._distance_m, 2),
                "distance_cm": self._distance_cm,
                "signal_strength": self._signal_strength,
                "connected": self._bus is not None
            }

    def cleanup(self):
        """Stop polling and close I2C bus."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        if self._bus:
            try:
                self._bus.close()
            except Exception:
                pass
        print("[LiDARController] Stopped.")


# ============================================================================
# BALLISTIC OFFSET ENGINE — SW-001 §2.6, §4
#
# The turret is mounted OVERHEAD (8-10 feet / 2.4-3.0m above ground).
# It fires DOWNWARD. Gravity ASSISTS the shot — the water stream falls
# toward the target zone, so the pitch correction is small and negative.
#
# The LiDAR measures the "slant distance" to the background surface
# behind the target. We use this to compute how much the water stream
# will drop over that distance and adjust pitch accordingly.
# ============================================================================

# Calibration constants — tune these after field testing
WATER_EXIT_VELOCITY = 7.0   # m/s — measured at nozzle exit
GRAVITY = 9.81               # m/s²
def compute_ballistic_offset(pitch_deg: float, yaw_deg: float,
                               distance_m: float) -> tuple:
    """
    Apply linear drop correction for the OVERHEAD-mounted inverted turret.
    Since it fires downward, gravity accelerates the water. For distances > 3m,
    we apply a slight negative pitch offset (aiming closer to the horizon)
    to compensate for the drop.
    """
    if distance_m < 0.3 or distance_m > 8.0:
        return pitch_deg, yaw_deg, {
            "drop_offset_deg": 0.0,
            "distance_m": distance_m,
            "in_range": False
        }

    # Linear drop: dead-straight under 3m, then -0.5 deg per meter
    if distance_m <= 3.0:
        drop_offset_deg = 0.0
    else:
        drop_offset_deg = -0.5 * (distance_m - 3.0)

    corrected_pitch = pitch_deg + drop_offset_deg

    return corrected_pitch, yaw_deg, {
        "drop_offset_deg": round(drop_offset_deg, 2),
        "distance_m": round(distance_m, 2),
        "in_range": True
    }


# ============================================================================
# COORDINATE MATH
# ============================================================================

def pixel_to_angle(px: int, py: int,
                   frame_w: int = 1280, frame_h: int = 800,
                   fov_h: float = 110.0, fov_v: float = 75.0) -> tuple:
    """
    Convert a pixel coordinate (from a click on the video feed) to
    gimbal pitch/yaw angles in degrees.

    Maps the frame center to (0, 0) degrees. Pixels left of center
    produce negative yaw; pixels above center produce negative pitch.

    Args:
        px, py: Click coordinates in pixels.
        frame_w, frame_h: Resolution of the video feed.
        fov_h, fov_v: Field of view of the camera in degrees.

    Returns:
        (pitch_deg, yaw_deg) tuple.
    """
    # Normalize to [-0.5, +0.5] range
    norm_x = (px / frame_w) - 0.5   # -0.5=left, +0.5=right
    norm_y = (py / frame_h) - 0.5   # -0.5=top, +0.5=bottom

    yaw_deg = norm_x * fov_h         # Positive = right
    pitch_deg = norm_y * fov_v       # Positive = down (inverted gimbal geometry)

    return pitch_deg, yaw_deg


# ============================================================================
# PREDICTIVE LEAD ENGINE — SW-001 §2.7
#
# Three-stage pipeline executed for every fire decision:
#   1. pixel_to_angle()        → raw pitch/yaw
#   2. + velocity lead offsets → corrected for target movement during ToF
#   3. + linear drop           → final corrected pitch
#
# This function combines stages 2 and 3 (§2.7.2 + §2.7.3).
# ============================================================================

def compute_predictive_lead(raw_pitch: float, raw_yaw: float,
                            distance_m: float,
                            omega_pitch: float = 0.0,
                            omega_yaw: float = 0.0) -> tuple:
    """
    Apply velocity lead + Linear Drop Compensation to raw gimbal angles.

    SW-001 §2.7.2: Calculates Time-of-Flight, then applies the target's
    angular velocity over that window to predict where the target WILL BE
    when the water stream arrives.

    Linear Drop Compensation: Firing downward from the inverted dome.
    Under 3m, the stream is dead-straight. Over 3m, apply a slight
    negative pitch offset (aiming closer to horizon) to compensate for drop.

    Execution order:
      1. raw angles (input)
      2. + lead_pitch / lead_yaw  (velocity-corrected aim point)
      3. + drop_offset_deg        (compensate for stream gravity drop)
    """
    if distance_m < 0.3 or distance_m > 8.0:
        return raw_pitch, raw_yaw, {
            "in_range": False,
            "distance_m": distance_m,
            "tof_ms": 0.0,
            "lead_pitch_deg": 0.0,
            "lead_yaw_deg": 0.0,
            "drop_offset_deg": 0.0,
            "total_pitch_correction": 0.0,
            "total_yaw_correction": 0.0
        }

    v0 = WATER_EXIT_VELOCITY
    alpha_rad = math.radians(raw_pitch)

    # --- Stage 2: Time-of-Flight Lead (§2.7.2) ---
    cos_alpha = math.cos(alpha_rad)
    if abs(cos_alpha) < 0.01:
        cos_alpha = 0.01  # Prevent division by zero
    tof = distance_m / (v0 * cos_alpha)  # seconds

    # Predict where target will be after ToF
    lead_pitch = omega_pitch * tof  # degrees
    lead_yaw = omega_yaw * tof      # degrees

    # Apply lead to raw angles
    led_pitch = raw_pitch + lead_pitch
    led_yaw = raw_yaw + lead_yaw

    # --- Stage 3: Linear Drop Compensation ---
    if distance_m <= 3.0:
        drop_offset_deg = 0.0
    else:
        drop_offset_deg = -0.5 * (distance_m - 3.0)

    final_pitch = led_pitch + drop_offset_deg
    final_yaw = led_yaw

    return final_pitch, final_yaw, {
        "in_range": True,
        "distance_m": round(distance_m, 2),
        "tof_ms": round(tof * 1000, 1),
        "lead_pitch_deg": round(lead_pitch, 3),
        "lead_yaw_deg": round(lead_yaw, 3),
        "drop_offset_deg": round(drop_offset_deg, 2),
        "total_pitch_correction": round(lead_pitch + drop_offset_deg, 3),
        "total_yaw_correction": round(lead_yaw, 3)
    }


