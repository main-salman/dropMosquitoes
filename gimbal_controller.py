# Implements: SW-001 §2.2 — TurretAgent
import serial
import struct
import threading
import asyncio
import time


class GimbalController:
    """
    Hardware interface for the Storm32 Gimbal.
    Uses USB Serial to command pitch and yaw via the binary o323BGC protocol.

    Serial writes are dispatched via a background thread so the
    async orchestrator loop never blocks on UART I/O.
    """
    def __init__(self, port=None, baudrate=115200):
        self.baudrate = baudrate
        self.ser = None
        self.pitch = 0.0
        self.yaw = 0.0
        self._write_lock = threading.Lock()

        # Endstops — Storm32 mechanical limits
        self.PITCH_LIMIT = 20.0
        self.YAW_LIMIT = 80.0

        # Dynamic port detection: probe each port with GET_VERSION to find Storm32.
        ports_to_try = []
        if port is not None:
            ports_to_try.append(port)
        ports_to_try.extend(["/dev/ttyACM0", "/dev/ttyACM1", "/dev/ttyUSB0", "/dev/ttyTHS1", "/dev/ttyTHS0"])

        self.port = None
        for p in ports_to_try:
            try:
                import os
                if not os.path.exists(p):
                    continue
                candidate = serial.Serial(p, self.baudrate, timeout=1)
                # Probe: send GET_VERSION (cmd 0x01) and check for response
                import time as _t
                candidate.reset_input_buffer()
                candidate.write(bytes([0xFA, 0x00, 0x01, 0x00, 0x01]))
                _t.sleep(0.5)
                if candidate.in_waiting > 0:
                    resp = candidate.read(candidate.in_waiting)
                    if len(resp) >= 2 and resp[0] == 0xFB:
                        self.ser = candidate
                        self.port = p
                        print(f"[GimbalController] Storm32 detected on {p} (version probe OK, {len(resp)} bytes)")
                        break
                    else:
                        print(f"[GimbalController] {p}: unexpected response {resp.hex()[:20]}, skipping")
                        candidate.close()
                else:
                    print(f"[GimbalController] {p}: no response to GET_VERSION probe, skipping")
                    candidate.close()
            except Exception as e:
                print(f"[GimbalController] Failed to probe {p}: {e}")

        if not self.ser:
            self.port = port or "/dev/ttyACM0"
            print(f"[GimbalController] WARNING: Could not connect to any serial port. Running in STUB mode on {self.port}")

    def aim(self, pitch: float, yaw: float):
        """
        Command the gimbal to specific angles (synchronous).
        Angles are clamped to safe mechanical limits.
        """
        self.pitch = max(-self.PITCH_LIMIT, min(self.PITCH_LIMIT, pitch))
        self.yaw = max(-self.YAW_LIMIT, min(self.YAW_LIMIT, yaw))

        roll_deg = 0.0
        # Pack angles as float32 (4 bytes each) + 2-byte flags
        payload = struct.pack('<fffH',
                              self.pitch,   # pitch (float32)
                              roll_deg,     # roll (float32, unused)
                              self.yaw,     # yaw (float32)
                              0)            # flags (0 = unlimited)

        data_len = len(payload)  # 14 bytes (4+4+4+2)
        cmd_id = 0x11  # CMD_SET_ANGLES

        # Build full packet: header + payload + 2-byte CRC (0x00 0x00)
        packet = bytes([0xFA, data_len, cmd_id]) + payload
        packet += bytes([0x00, 0x00])  # CRC — board does not check

        with self._write_lock:
            if self.ser and self.ser.is_open:
                self.ser.write(packet)
                print(f"[GimbalController] Moved (binary o323BGC float32) to Pitch: {self.pitch:.2f}, Yaw: {self.yaw:.2f}")
            else:
                print(f"[GimbalController] STUB — Pitch: {self.pitch:.2f}, Yaw: {self.yaw:.2f}")

    async def aim_async(self, pitch: float, yaw: float):
        """
        Non-blocking aim — dispatches serial write to executor thread
        so the asyncio event loop is never stalled by UART I/O.
        """
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.aim, pitch, yaw)

    def sweep(self, start_pitch: float, start_yaw: float,
              end_pitch: float, end_yaw: float,
              steps: int = 5, step_delay: float = 0.04, downward_bias_deg: float = 0.5):
        """
        Execute a linear sweep from (start) to (end) in `steps` increments.
        Each step waits `step_delay` seconds. Total sweep time ≈ steps × step_delay.
        Adds a small downward_bias_deg to the end_pitch to ensure a downward slope.

        Used during Stream-and-Sweep: the gimbal sweeps across the predicted
        flight path while the pump is spraying, creating a wall of water.
        """
        # Apply bias to the final pitch
        adjusted_end_pitch = end_pitch + downward_bias_deg

        for i in range(steps + 1):
            t = i / steps  # 0.0 → 1.0
            p = start_pitch + (adjusted_end_pitch - start_pitch) * t
            y = start_yaw + (end_yaw - start_yaw) * t
            self.aim(p, y)
            if i < steps:
                time.sleep(step_delay)

    async def sweep_async(self, start_pitch: float, start_yaw: float,
                          end_pitch: float, end_yaw: float,
                          steps: int = 5, step_delay: float = 0.04, downward_bias_deg: float = 0.5):
        """Non-blocking sweep dispatched to executor thread."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, self.sweep,
            start_pitch, start_yaw, end_pitch, end_yaw, steps, step_delay, downward_bias_deg
        )

    def get_status(self):
        return {"pitch": self.pitch, "yaw": self.yaw, "connected": self.ser is not None}

    def cleanup(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
