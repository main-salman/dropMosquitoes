# Implements: SW-001 §2.2 — TurretAgent
import serial
import threading
import asyncio
import time


class GimbalController:
    """
    Hardware interface for the Storm32 Gimbal.
    Uses Serial UART to command pitch and yaw.

    Serial writes are dispatched via a background thread so the
    async orchestrator loop never blocks on UART I/O.
    """
    def __init__(self, port="/dev/ttyTHS0", baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.pitch = 0.0
        self.yaw = 0.0
        self._write_lock = threading.Lock()

        # Endstops — Storm32 mechanical limits
        self.PITCH_LIMIT = 20.0
        self.YAW_LIMIT = 80.0

        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            print(f"[GimbalController] Connected on {self.port}")
        except Exception as e:
            print(f"[GimbalController] WARNING: Could not connect to {self.port}: {e}")

    def aim(self, pitch: float, yaw: float):
        """
        Command the gimbal to specific angles (synchronous).
        Angles are clamped to safe mechanical limits.
        """
        self.pitch = max(-self.PITCH_LIMIT, min(self.PITCH_LIMIT, pitch))
        self.yaw = max(-self.YAW_LIMIT, min(self.YAW_LIMIT, yaw))

        cmd_str = f"$CMD,{self.pitch:.2f},{self.yaw:.2f}*\n"

        with self._write_lock:
            if self.ser and self.ser.is_open:
                self.ser.write(cmd_str.encode('utf-8'))
                print(f"[GimbalController] Moved to Pitch: {self.pitch:.2f}, Yaw: {self.yaw:.2f}")
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
