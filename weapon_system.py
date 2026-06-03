# Implements: SW-001 §2.4 — TriggerAgent & SAFE-001 §2
import time
import threading

try:
    import Jetson.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    print("[WeaponSystem] WARNING: Jetson.GPIO not available. Running in Stub Mode.")


class WeaponSystem:
    """
    Trigger control for the 12V DC Diaphragm Pump.
    Controls the MonkMakes relay via Jetson.GPIO BCM 17 (IDC40P Terminal 11).

    ECO-2026-003: Diaphragm pump replaces submersible. ~100ms mechanical
    spin-up before water exits nozzle. Fire command should be issued
    EARLY while gimbal is still settling for "Stream and Sweep" effect.

    SAFE-001 §2: Relay defaults to LOW at boot. Fire requires explicit call.
    """

    # Pump spin-up time — diaphragm motor needs ~100ms before water exits nozzle
    PUMP_SPINUP_MS = 100

    def __init__(self, relay_pin=17, arc_compensation_deg=12.0):
        self.relay_pin = relay_pin
        self.arc_compensation_deg = arc_compensation_deg
        self._firing = False
        self._fire_thread = None
        self._fire_lock = threading.Lock()

        if GPIO_AVAILABLE:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.relay_pin, GPIO.OUT)
            GPIO.output(self.relay_pin, GPIO.LOW)
            try:
                from hardware import configure_push_pull
                configure_push_pull()
            except ImportError:
                pass
            print(f"[WeaponSystem] Initialized on Pin {self.relay_pin} and forced to Push-Pull")


    @property
    def is_firing(self) -> bool:
        """True if the pump relay is currently energized."""
        return self._firing

    def fire(self, duration_sec: float = 0.4):
        """
        Blocking fire — set relay HIGH for duration, then LOW.
        Use fire_sweep() for non-blocking "Stream and Sweep" mode.
        """
        print(f"[WeaponSystem] 🔥 FIRE! Pin {self.relay_pin} HIGH for {duration_sec}s")
        if GPIO_AVAILABLE:
            GPIO.output(self.relay_pin, GPIO.HIGH)
            self._firing = True
            time.sleep(duration_sec)
            GPIO.output(self.relay_pin, GPIO.LOW)
            self._firing = False
        else:
            self._firing = True
            time.sleep(duration_sec)
            self._firing = False
        print("[WeaponSystem] Cease fire.")

    def fire_sweep(self, duration_sec: float = 0.4):
        """
        Non-blocking fire — starts the pump in a background thread.
        Returns immediately so the gimbal can continue tracking/sweeping
        while the pump is running. The pump auto-stops after duration_sec.

        This is the "Stream and Sweep" mode: the pump creates a moving
        wall of water as the gimbal sweeps across the target's flight path.
        """
        with self._fire_lock:
            if self._firing:
                return  # Already firing — don't stack

        self._fire_thread = threading.Thread(
            target=self._sweep_worker,
            args=(duration_sec,),
            daemon=True
        )
        self._fire_thread.start()

    def _sweep_worker(self, duration_sec: float):
        """Background thread: energize relay for duration, then auto-stop."""
        with self._fire_lock:
            if self._firing:
                return
            self._firing = True

        print(f"[WeaponSystem] 🔥 SWEEP FIRE! Pin {self.relay_pin} HIGH for {duration_sec}s")
        try:
            if GPIO_AVAILABLE:
                GPIO.output(self.relay_pin, GPIO.HIGH)
            time.sleep(duration_sec)
        finally:
            if GPIO_AVAILABLE:
                GPIO.output(self.relay_pin, GPIO.LOW)
            self._firing = False
            print(f"[WeaponSystem] Sweep complete. Stream duration: {duration_sec*1000:.0f}ms.")

    def cease_fire(self):
        """Emergency stop — immediately set relay LOW regardless of timer."""
        if GPIO_AVAILABLE:
            GPIO.output(self.relay_pin, GPIO.LOW)
        self._firing = False
        print("[WeaponSystem] ⛔ EMERGENCY CEASE FIRE.")

    def get_arc_compensation(self) -> float:
        """Return the pitch offset (degrees) that compensates for stream arc over distance."""
        return self.arc_compensation_deg

    def cleanup(self):
        self.cease_fire()
        if GPIO_AVAILABLE:
            GPIO.cleanup()
            print("[WeaponSystem] Cleaned up GPIO.")
