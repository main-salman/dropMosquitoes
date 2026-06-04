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


    # -- Pump (CH1) ----------------------------------------------------------

    def fire_pump(self, duration_sec: float = 0.4):
        """
        Fire the water pump for a specified duration.
        Default: 400ms (Stream-and-Sweep with 12V diaphragm pump).

        Args:
            duration_sec: Pulse length in seconds (0.05 to 2.0).
        """
        duration_sec = max(0.05, min(duration_sec, 2.0))  # Clamp to safe range
        print(f"[RelayController] FIRE! Pump ON for {duration_sec:.2f}s")

        def _pulse():
            with self._lock:
                try:
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
# TF-LUNA LiDAR (I2C) — HW-001 §6, SW-001 §2.5
# Benewake TF-Luna: I2C Bus 1, default address 0x10
# Reads distance in cm, converts to meters.
# Mounted co-axial with Sniper camera on gimbal payload plate.
# ============================================================================

LIDAR_I2C_BUS = 1
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


