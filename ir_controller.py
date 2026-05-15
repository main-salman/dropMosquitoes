# Implements: HW-001 — IR Illuminator Control
"""
ir_controller.py — IR Illuminator Control

NOTE ON CURRENT HARDWARE:
  The IR illuminators are currently hard-wired always-on via Wago +12V Port 3
  (see HW-001 §4). This module is pre-built for a future upgrade where IR LEDs
  are routed through a MOSFET or a spare relay channel for software control.

  Until then, this module runs in "always-on stub" mode — it tracks the schedule
  state internally but the physical LEDs stay on regardless.

  To enable GPIO control: wire the IR illuminator's +12V through a MOSFET
  gate connected to the pin below, and update HW-001 accordingly.

Supports:
  - Manual ON/OFF toggle (when wired through MOSFET)
  - Scheduled dusk/dawn automation (via system time)
"""

import time
import threading
from datetime import datetime

try:
    import Jetson.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    print("[IRController] WARNING: Jetson.GPIO not available. Running in Stub Mode.")

# BCM pin for IR illuminator MOSFET gate
IR_PIN = 22  # BCM 22 = Physical Pin 15 — update per your wiring

# Default schedule (24h format)
DUSK_HOUR = 20   # 8:00 PM — turn IR ON
DAWN_HOUR = 6    # 6:00 AM — turn IR OFF


class IRController:
    """Controls IR illuminator LEDs for night vision."""
    
    def __init__(self, pin=IR_PIN, auto_schedule=True):
        self.pin = pin
        self.is_on = False
        self.auto_schedule = auto_schedule
        self._scheduler_running = False
        self._scheduler_thread = None
        
        if GPIO_AVAILABLE:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.pin, GPIO.OUT, initial=GPIO.LOW)
            print(f"[IRController] Initialized on BCM Pin {self.pin}")
        
        if auto_schedule:
            self.start_scheduler()
    
    def on(self):
        """Turn IR illuminators ON."""
        if GPIO_AVAILABLE:
            GPIO.output(self.pin, GPIO.HIGH)
        self.is_on = True
        print("[IRController] IR LEDs ON 🔴")
    
    def off(self):
        """Turn IR illuminators OFF."""
        if GPIO_AVAILABLE:
            GPIO.output(self.pin, GPIO.LOW)
        self.is_on = False
        print("[IRController] IR LEDs OFF")
    
    def toggle(self):
        """Toggle IR illuminators."""
        if self.is_on:
            self.off()
        else:
            self.on()
    
    def _is_nighttime(self) -> bool:
        """Check if current time is between dusk and dawn."""
        hour = datetime.now().hour
        if DUSK_HOUR > DAWN_HOUR:
            # Normal case: dusk 20:00, dawn 06:00
            return hour >= DUSK_HOUR or hour < DAWN_HOUR
        else:
            # Edge case: dusk 02:00, dawn 22:00
            return DUSK_HOUR <= hour < DAWN_HOUR
    
    def start_scheduler(self):
        """Start background thread for dusk/dawn automation."""
        if self._scheduler_running:
            return
        self._scheduler_running = True
        self._scheduler_thread = threading.Thread(target=self._schedule_loop, daemon=True)
        self._scheduler_thread.start()
        print(f"[IRController] Auto-schedule active: ON at {DUSK_HOUR}:00, OFF at {DAWN_HOUR}:00")
    
    def _schedule_loop(self):
        """Check every 60s if IR should be on or off based on time."""
        while self._scheduler_running:
            should_be_on = self._is_nighttime()
            if should_be_on and not self.is_on:
                print("[IRController] Dusk detected — enabling IR.")
                self.on()
            elif not should_be_on and self.is_on:
                print("[IRController] Dawn detected — disabling IR.")
                self.off()
            time.sleep(60)  # Check every minute
    
    def stop_scheduler(self):
        """Stop the background scheduler."""
        self._scheduler_running = False
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=2)
    
    def get_status(self) -> dict:
        return {
            "ir_on": self.is_on,
            "pin": self.pin,
            "auto_schedule": self.auto_schedule,
            "is_nighttime": self._is_nighttime(),
            "dusk_hour": DUSK_HOUR,
            "dawn_hour": DAWN_HOUR
        }
    
    def cleanup(self):
        """Safe shutdown."""
        self.stop_scheduler()
        self.off()
        if GPIO_AVAILABLE:
            GPIO.cleanup(self.pin)
        print("[IRController] Cleaned up.")
