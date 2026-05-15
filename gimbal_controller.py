# Implements: SW-001 §2.2 — TurretAgent
import serial
import time

class GimbalController:
    """
    Hardware interface for the Storm32 Gimbal.
    Uses Serial UART to command pitch and yaw.
    """
    def __init__(self, port="/dev/ttyTHS0", baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.pitch = 0.0
        self.yaw = 0.0
        
        # Endstops
        self.PITCH_LIMIT = 20.0
        self.YAW_LIMIT = 80.0

        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            print(f"[GimbalController] Connected on {self.port}")
        except Exception as e:
            print(f"[GimbalController] WARNING: Could not connect to {self.port}: {e}")

    def aim(self, pitch: float, yaw: float):
        """
        Command the gimbal to specific angles.
        Angles are clamped to safe mechanical limits.
        """
        # Clamp angles
        self.pitch = max(-self.PITCH_LIMIT, min(self.PITCH_LIMIT, pitch))
        self.yaw = max(-self.YAW_LIMIT, min(self.YAW_LIMIT, yaw))
        
        # Build Storm32 RC command string (simplified for example)
        # Format: $CMD,pitch,yaw*
        cmd_str = f"$CMD,{self.pitch:.2f},{self.yaw:.2f}*\n"
        
        if self.ser and self.ser.is_open:
            self.ser.write(cmd_str.encode('utf-8'))
            print(f"[GimbalController] Moved to Pitch: {self.pitch:.2f}, Yaw: {self.yaw:.2f}")
        else:
            # Stub mode
            print(f"[GimbalController] STUB - Moved to Pitch: {self.pitch:.2f}, Yaw: {self.yaw:.2f}")

    def get_status(self):
        return {"pitch": self.pitch, "yaw": self.yaw, "connected": self.ser is not None}

    def cleanup(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
