# Implements: OPS-001 §8.2 — Status Indicator
"""
status_indicator.py — Audible/Visual Status Feedback

Controls a piezo buzzer on a GPIO pin to signal system state to nearby humans.

Hardware: Active Piezo Buzzer (3.3V) connected to BCM 4 (IDC40P Terminal 7).
An "active" buzzer contains its own oscillator — you just supply HIGH and it beeps.

Patterns:
  - System boot:      2 short beeps (beep-beep)
  - Human detected:   1 long beep (beeeeep)
  - Engagement fired: 3 rapid beeps (beep-beep-beep)
  - System shutdown:  1 descending tone (beeeep... beep)
  - Error/fault:      5 rapid beeps
"""

import time
import threading

try:
    import Jetson.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    print("[StatusIndicator] WARNING: Jetson.GPIO not available. Running in Stub Mode.")

# BCM 4 = Physical Pin 7 = IDC40P Terminal 7
BUZZER_PIN = 4


class StatusIndicator:
    """Audible feedback via piezo buzzer."""
    
    def __init__(self, pin=BUZZER_PIN):
        self.pin = pin
        
        if GPIO_AVAILABLE:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.pin, GPIO.OUT, initial=GPIO.LOW)
            print(f"[StatusIndicator] Initialized on BCM Pin {self.pin}")
    
    def _beep(self, on_sec: float, off_sec: float = 0.1):
        """Single beep: HIGH for on_sec, then LOW for off_sec."""
        if GPIO_AVAILABLE:
            GPIO.output(self.pin, GPIO.HIGH)
            time.sleep(on_sec)
            GPIO.output(self.pin, GPIO.LOW)
            time.sleep(off_sec)
        else:
            # Stub: print representation
            dots = int(on_sec * 20)
            print(f"[StatusIndicator] 🔊 {'•' * max(1, dots)}")
            time.sleep(on_sec + off_sec)
    
    def _play_pattern(self, pattern: list):
        """Play a pattern in a background thread so it doesn't block."""
        def _play():
            for on_sec, off_sec in pattern:
                self._beep(on_sec, off_sec)
        
        t = threading.Thread(target=_play, daemon=True)
        t.start()
    
    def boot(self):
        """System started — 2 short beeps."""
        self._play_pattern([(0.1, 0.1), (0.1, 0.0)])
    
    def human_detected(self):
        """Human presence detected — 1 long beep."""
        self._play_pattern([(0.5, 0.0)])
    
    def engagement(self):
        """Target engaged (fired) — 3 rapid beeps."""
        self._play_pattern([(0.05, 0.05), (0.05, 0.05), (0.05, 0.0)])
    
    def shutdown(self):
        """System shutting down — long then short."""
        self._play_pattern([(0.3, 0.15), (0.1, 0.0)])
    
    def error(self):
        """Fault detected — 5 rapid beeps."""
        self._play_pattern([(0.05, 0.05)] * 5)
    
    def cleanup(self):
        if GPIO_AVAILABLE:
            GPIO.output(self.pin, GPIO.LOW)
            GPIO.cleanup(self.pin)
        print("[StatusIndicator] Cleaned up.")
