# Implements: HW-001 §4 / SW-001 — IR illumination awareness
"""
ir_controller.py — IR illuminator status + optional future GPIO control.

PRODUCTION (as-built):
  Univivi 8-LED 850nm illuminator is hard-wired always-on via Wago +12V Port 3
  (HW-001). It is ON whenever the system 12V rail is powered. NoIR Scout/Sniper
  cameras use that light passively — no software gate required.

  Live dashboard (`app.py`) reports this via get_illumination_status() so operators
  and hunt logic know IR is present and powered-with-system.

FUTURE:
  Route +12V through a MOSFET on IR_PIN for dusk/dawn software control, then set
  HARDWIRED_ALWAYS_ON = False and wire IRController into app.py scheduling.
"""

from __future__ import annotations

import threading
from datetime import datetime
from timeutil import now as now_et
from typing import Any

try:
    import Jetson.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False

# As-built: illuminator tied to system 12V (not GPIO-switched)
HARDWIRED_ALWAYS_ON = True
WAVELENGTH_NM = 850
PART = "Univivi IR Illuminator 8-LED 850nm (IP67, 90°)"
POWER_TAP = "Wago +12V Port 3"

# Future MOSFET gate (unused while HARDWIRED_ALWAYS_ON)
IR_PIN = 22  # BCM 22 = Physical Pin 15
DUSK_HOUR = 20
DAWN_HOUR = 6


def get_illumination_status() -> dict[str, Any]:
    """Canonical IR status for /api/status and operators."""
    return {
        "present": True,
        "part": PART,
        "wavelength_nm": WAVELENGTH_NM,
        "power_tap": POWER_TAP,
        "hardwired_always_on": HARDWIRED_ALWAYS_ON,
        "on_when_system_powered": HARDWIRED_ALWAYS_ON,
        "software_control": not HARDWIRED_ALWAYS_ON,
        "ir_on": True if HARDWIRED_ALWAYS_ON else None,
        "cameras": "Scout=permanent NoIR; Sniper=UC-350 Mode A LDR auto (verified)",
        "note": (
            "IR illuminator ON with system 12V. Scout always IR-sensitive; "
            "Sniper IR-cut is LDR auto on module (Mode A — leave as-is)."
        ),
    }


class IRController:
    """
    Optional GPIO controller for a future switched illuminator.
    When HARDWIRED_ALWAYS_ON, on/off are no-ops; status reflects always-on.
    """

    def __init__(self, pin=IR_PIN, auto_schedule=False):
        self.pin = pin
        self.auto_schedule = auto_schedule and not HARDWIRED_ALWAYS_ON
        self.is_on = HARDWIRED_ALWAYS_ON
        self._scheduler_running = False
        self._scheduler_thread = None

        if HARDWIRED_ALWAYS_ON:
            print(f"[IRController] As-built: {PART} hardwired always-on ({POWER_TAP})")
            return

        if GPIO_AVAILABLE:
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.pin, GPIO.OUT, initial=GPIO.LOW)
            print(f"[IRController] GPIO control on BCM {self.pin}")
        if self.auto_schedule:
            self.start_scheduler()

    def on(self):
        if HARDWIRED_ALWAYS_ON:
            self.is_on = True
            return
        if GPIO_AVAILABLE:
            GPIO.output(self.pin, GPIO.HIGH)
        self.is_on = True
        print("[IRController] IR LEDs ON")

    def off(self):
        if HARDWIRED_ALWAYS_ON:
            self.is_on = True  # cannot turn off in as-built wiring
            print("[IRController] IR hardwired — off() ignored (stays on with 12V)")
            return
        if GPIO_AVAILABLE:
            GPIO.output(self.pin, GPIO.LOW)
        self.is_on = False
        print("[IRController] IR LEDs OFF")

    def toggle(self):
        if HARDWIRED_ALWAYS_ON:
            return
        if self.is_on:
            self.off()
        else:
            self.on()

    def _is_nighttime(self) -> bool:
        hour = now_et().hour
        if DUSK_HOUR > DAWN_HOUR:
            return hour >= DUSK_HOUR or hour < DAWN_HOUR
        return DUSK_HOUR <= hour < DAWN_HOUR

    def start_scheduler(self):
        if HARDWIRED_ALWAYS_ON or self._scheduler_running:
            return
        self._scheduler_running = True
        self._scheduler_thread = threading.Thread(
            target=self._schedule_loop, daemon=True)
        self._scheduler_thread.start()

    def _schedule_loop(self):
        while self._scheduler_running:
            should = self._is_nighttime()
            if should and not self.is_on:
                self.on()
            elif not should and self.is_on:
                self.off()
            import time
            time.sleep(60)

    def stop_scheduler(self):
        self._scheduler_running = False
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=2)

    def get_status(self) -> dict:
        st = get_illumination_status()
        st["ir_on"] = self.is_on
        st["pin"] = self.pin
        st["auto_schedule"] = self.auto_schedule
        st["is_nighttime"] = self._is_nighttime()
        return st

    def cleanup(self):
        self.stop_scheduler()
        if not HARDWIRED_ALWAYS_ON and GPIO_AVAILABLE:
            self.off()
            GPIO.cleanup(self.pin)
