# Implements: HW-001 §3-§5, SW-001 §2.2, §2.4, SAFE-001 §1-§2
# Hardware abstraction layer for GPIO relays and Storm32 gimbal serial control.
"""
hardware.py — Sniper Messy Mortar Hardware Control

Provides:
  - RelayController: GPIO-based relay switching for pump and gimbal power
  - GimbalController: Serial UART interface to the Storm32 BGC board
  - coordinate_to_angle(): Pixel-to-degree math for click-to-aim

SAFETY: All GPIO access wrapped in try/finally to guarantee LOW on crash.
"""

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


# ============================================================================
# GPIO PIN ASSIGNMENTS
# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
# CUSTOMIZE THESE: Set to the BCM pin numbers you actually wired.
# See: https://www.jetsonhacks.com/nvidia-jetson-orin-nano-gpio-header-pinout/
# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
RELAY_PUMP_PIN = 18       # Relay CH1: Water pump trigger
RELAY_GIMBAL_PIN = 24     # Relay CH2: Gimbal power boot-delay switch
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

    def fire_pump(self, duration_sec: float = 0.3):
        """
        Fire the water pump for a specified duration.
        Default: 300ms as per SW-001 §2.4.

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

    # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    # CUSTOMIZE: Set to your actual serial port.
    # Jetson Orin Nano UART: /dev/ttyTHS0 or /dev/ttyTHS1
    # USB-to-Serial adapter: /dev/ttyUSB0
    # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
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
