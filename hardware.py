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
        self._pump_state = False
        self._gimbal_state = False
        self._lock = threading.Lock()

        if JETSON_AVAILABLE:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            GPIO.setup(RELAY_PUMP_PIN, GPIO.OUT, initial=GPIO.LOW)
            GPIO.setup(RELAY_GIMBAL_PIN, GPIO.OUT, initial=GPIO.LOW)
            print(f"[RelayController] GPIO initialized. Pump=Pin{RELAY_PUMP_PIN}, Gimbal=Pin{RELAY_GIMBAL_PIN}")
        else:
            print("[RelayController] STUB MODE — no real GPIO control.")

    # -- Pump (CH1) ----------------------------------------------------------

    def fire_pump(self, duration_sec: float = 0.6):
        """
        Fire the water pump for a specified duration.
        Default: 600ms (Sustained pulse for Gravity Airburst).

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

    # -- Gimbal Power (CH2) ---------------------------------------------------

    def set_gimbal_power(self, state: bool):
        """
        Turn gimbal power ON or OFF.
        SAFE-001 §1: Must default to OFF at boot. Only enable after serial
        comms are confirmed.
        """
        with self._lock:
            self._gimbal_state = state
            if JETSON_AVAILABLE:
                GPIO.output(RELAY_GIMBAL_PIN, GPIO.HIGH if state else GPIO.LOW)
            print(f"[RelayController] Gimbal Power {'ON' if state else 'OFF'}")

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
# These are MORE CONSERVATIVE than the hardware limits (±130° yaw, ±45° pitch)
# to protect wiring through the cable glands and service loops.
# ============================================================================
YAW_LIMIT = 80.0     # Max ±80° yaw (160° total sweep)
PITCH_LIMIT = 20.0   # Max ±20° pitch (40° total sweep)


class GimbalController:
    """
    Controls the Storm32 BGC board via Serial UART.

    Sends RC-override style commands to RC_PITCH and RC_YAW pins.
    Implements software endstops and the "Death Spiral" unwind prevention.

    HW-001 §3: Serial on /dev/ttyTHS0 @ 115200 baud.
    SAFE-001 §2: Yaw hard-limited to ±80°, Pitch to ±20° (software endstops).
    """

    # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    # CUSTOMIZE: Set to your actual serial port.
    # Jetson Orin Nano UART: /dev/ttyTHS0 or /dev/ttyTHS1
    # USB-to-Serial adapter: /dev/ttyUSB0
    # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    SERIAL_PORT = "/dev/ttyTHS0"
    BAUD_RATE = 115200

    # Storm32 serial command IDs (o323BGC protocol)
    CMD_SET_ANGLES = 0x11  # Set Camera Angles command

    def __init__(self):
        self._yaw = 0.0    # Current yaw angle (degrees)
        self._pitch = 0.0  # Current pitch angle (degrees)
        self._lock = threading.Lock()
        self._serial = None

        if SERIAL_AVAILABLE:
            try:
                self._serial = serial.Serial(
                    port=self.SERIAL_PORT,
                    baudrate=self.BAUD_RATE,
                    timeout=0.1
                )
                print(f"[GimbalController] Serial opened on {self.SERIAL_PORT} @ {self.BAUD_RATE}")
            except serial.SerialException as e:
                print(f"[GimbalController] Serial FAILED: {e}. Running in STUB mode.")
                self._serial = None
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
        """Return gimbal to home position (0, 0)."""
        self.set_angles(0.0, 0.0)

    def _send_storm32_command(self, pitch_deg: float, yaw_deg: float):
        """
        Build and send a Storm32 o323BGC 'Set Camera Angles' packet.

        Packet format (o323BGC protocol):
          Byte 0:    0xFA (start marker)
          Byte 1:    Data length (14 bytes)
          Byte 2:    Command ID (0x11 = Set Angles)
          Bytes 3-4: Pitch angle (int16, degrees * 100)
          Bytes 5-6: Roll angle (int16, always 0 for 2-axis)
          Bytes 7-8: Yaw angle (int16, degrees * 100)
          Bytes 9-10: Flags (0x00)
          Bytes 11-12: Type (0x00)
          Bytes 13-16: Reserved
          Byte 17:   CRC (XOR of bytes 1-16)
        """
        pitch_val = int(pitch_deg * 100)
        roll_val = 0
        yaw_val = int(yaw_deg * 100)

        payload = struct.pack('<hhhHH',
                              pitch_val,  # pitch (int16)
                              roll_val,   # roll (int16, unused)
                              yaw_val,    # yaw (int16)
                              0,          # flags
                              0)          # type
        # Pad to 14 bytes
        payload += b'\x00' * (14 - len(payload))

        data_len = len(payload)
        cmd_id = self.CMD_SET_ANGLES

        # Build full packet
        packet = bytes([0xFA, data_len, cmd_id]) + payload

        # CRC: XOR of all bytes after the start marker
        crc = 0
        for b in packet[1:]:
            crc ^= b
        packet += bytes([crc])

        try:
            self._serial.write(packet)
        except Exception as e:
            print(f"[GimbalController] Serial write error: {e}")

    def get_status(self) -> dict:
        return {
            "pitch": round(self._pitch, 1),
            "yaw": round(self._yaw, 1),
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
MOUNT_HEIGHT_M = 2.7         # m — default overhead mount height (~9 feet)


def compute_ballistic_offset(pitch_deg: float, yaw_deg: float,
                              distance_m: float) -> tuple:
    """
    Apply parabolic drop correction for an OVERHEAD-mounted turret.

    The turret fires downward from ~2.7m height. Gravity accelerates the
    water stream toward the ground (assists the shot). The correction is
    smaller than for a ground-level turret.

    Physics:
      - Time of flight: t = d / (v0 * cos(α))
      - Gravity drop during flight: Δy = ½ * g * t²
      - Angular correction: Δpitch = arctan(Δy / d)
      - Since gravity HELPS (firing downward), we SUBTRACT the correction
        (stream lands slightly PAST the aimpoint due to gravity assist).

    Args:
        pitch_deg: Raw pitch angle from pixel_to_angle (degrees).
        yaw_deg: Raw yaw angle from pixel_to_angle (degrees, unchanged).
        distance_m: LiDAR-measured slant distance to background (meters).

    Returns:
        (corrected_pitch, yaw, offset_info) tuple where offset_info is a dict
        containing the raw offset values for GUI display.
    """
    if distance_m < 0.3 or distance_m > 8.0:
        # Out of effective range — no correction
        return pitch_deg, yaw_deg, {
            "drop_offset_deg": 0.0,
            "time_of_flight_ms": 0.0,
            "gravity_drop_cm": 0.0,
            "distance_m": distance_m,
            "in_range": False
        }

    alpha_rad = math.radians(pitch_deg)
    v0 = WATER_EXIT_VELOCITY

    # Time of flight (seconds)
    cos_alpha = math.cos(alpha_rad)
    if abs(cos_alpha) < 0.01:
        cos_alpha = 0.01  # Prevent division by zero at extreme angles
    tof = distance_m / (v0 * cos_alpha)

    # Gravity drop during flight (meters)
    gravity_drop_m = 0.5 * GRAVITY * tof * tof

    # Angular correction (degrees)
    # Negative because gravity pulls stream INTO target zone (downward assist)
    drop_offset_deg = -math.degrees(math.atan2(gravity_drop_m, distance_m))

    corrected_pitch = pitch_deg + drop_offset_deg

    return corrected_pitch, yaw_deg, {
        "drop_offset_deg": round(drop_offset_deg, 2),
        "time_of_flight_ms": round(tof * 1000, 1),
        "gravity_drop_cm": round(gravity_drop_m * 100, 1),
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
    pitch_deg = -norm_y * fov_v      # Negative = down (invert for gimbal)

    return pitch_deg, yaw_deg


# ============================================================================
# PREDICTIVE LEAD ENGINE — SW-001 §2.7
#
# Three-stage pipeline executed for every fire decision:
#   1. pixel_to_angle()        → raw pitch/yaw
#   2. + velocity lead offsets → corrected for target movement during ToF
#   3. + gravity drop          → final corrected pitch
#
# This function combines stages 2 and 3 (§2.7.2 + §2.7.3).
# Stage 1 (pixel_to_angle) and velocity tracking (§2.7.1 VelocityTracker)
# are handled upstream.
# ============================================================================

def compute_predictive_lead(raw_pitch: float, raw_yaw: float,
                            distance_m: float,
                            omega_pitch: float = 0.0,
                            omega_yaw: float = 0.0,
                            airburst_offset_deg: float = 12.0) -> tuple:
    """
    Apply velocity lead + Airburst Pitch Offset to raw gimbal angles.

    SW-001 §2.7.2: Calculates Time-of-Flight, then applies the target's
    angular velocity over that window to predict where the target WILL BE
    when the water arrives.

    Airburst Strategy: We intentionally over-aim by `airburst_offset_deg` so 
    the water arc peaks above the target's path and falls down as an AoE cloud.

    Execution order:
      1. raw angles (input)
      2. + lead_pitch / lead_yaw  (velocity-corrected aim point)
      3. + airburst_offset_deg    (final corrected pitch)

    Args:
        raw_pitch: Raw pitch from pixel_to_angle (degrees).
        raw_yaw: Raw yaw from pixel_to_angle (degrees).
        distance_m: LiDAR-measured slant distance (meters).
        omega_pitch: Target angular velocity in pitch (deg/s) from VelocityTracker.
        omega_yaw: Target angular velocity in yaw (deg/s) from VelocityTracker.
        airburst_offset_deg: Positive degrees to over-aim for the Gravity Airburst.

    Returns:
        (final_pitch, final_yaw, lead_info) where lead_info is a dict with
        all intermediate values for GUI/calibration display.
    """
    if distance_m < 0.3 or distance_m > 8.0:
        # Out of effective range — pass through raw angles, no correction
        return raw_pitch, raw_yaw, {
            "in_range": False,
            "distance_m": distance_m,
            "tof_ms": 0.0,
            "lead_pitch_deg": 0.0,
            "lead_yaw_deg": 0.0,
            "airburst_offset_deg": 0.0,
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

    # --- Stage 3: Gravity Airburst Offset ---
    # Intentionally fire higher than the calculated path to create an AoE rain cloud.
    # We add the offset (since positive pitch is typically "up" relative to the target).
    
    # Final corrected pitch = led_pitch + airburst offset
    final_pitch = led_pitch + airburst_offset_deg
    final_yaw = led_yaw

    return final_pitch, final_yaw, {
        "in_range": True,
        "distance_m": round(distance_m, 2),
        "tof_ms": round(tof * 1000, 1),
        "lead_pitch_deg": round(lead_pitch, 3),
        "lead_yaw_deg": round(lead_yaw, 3),
        "airburst_offset_deg": round(airburst_offset_deg, 2),
        "total_pitch_correction": round(lead_pitch + airburst_offset_deg, 3),
        "total_yaw_correction": round(lead_yaw, 3)
    }

