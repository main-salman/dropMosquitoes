# Implements: SW-001 §2.4 — TriggerAgent & SAFE-001 §2
import time

try:
    import Jetson.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    print("[WeaponSystem] WARNING: Jetson.GPIO not available. Running in Stub Mode.")

class WeaponSystem:
    """
    Trigger control and ballistics.
    Controls the MonkMakes relay via Jetson.GPIO Pin 18.
    """
    def __init__(self, relay_pin=18, airburst_offset_deg=12.0):
        self.relay_pin = relay_pin
        self.airburst_offset_deg = airburst_offset_deg
        
        if GPIO_AVAILABLE:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.relay_pin, GPIO.OUT)
            GPIO.output(self.relay_pin, GPIO.LOW)
            print(f"[WeaponSystem] Initialized on Pin {self.relay_pin}")

    def fire(self, duration_sec: float = 0.6):
        """
        Fire the water pump for a sustained pulse.
        Default 600ms for Gravity Airburst wide cloud generation.
        """
        print(f"[WeaponSystem] 🔥 FIRE! Pin {self.relay_pin} HIGH for {duration_sec}s")
        if GPIO_AVAILABLE:
            GPIO.output(self.relay_pin, GPIO.HIGH)
            time.sleep(duration_sec)
            GPIO.output(self.relay_pin, GPIO.LOW)
        else:
            # Stub mode
            time.sleep(duration_sec)
        print("[WeaponSystem] Cease fire.")

    def get_airburst_offset(self) -> float:
        return self.airburst_offset_deg

    def cleanup(self):
        if GPIO_AVAILABLE:
            GPIO.output(self.relay_pin, GPIO.LOW)
            GPIO.cleanup()
            print("[WeaponSystem] Cleaned up GPIO.")
