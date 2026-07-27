# Implements: HW-001 §5.4 Rev O, SW-001 §2.7
"""
pico_solenoid.py — Jetson USB CDC client for Pico W solenoid timer.

Protocol (115200 8N1, newline-terminated):
  FIRE <ms>  → Pico pulses GP15 for ms; reply OK FIRE <ms>
  OPEN       → GP15 HIGH; reply OK OPEN
  CLOSE      → GP15 LOW;  reply OK CLOSE
  PING       → reply PONG

Auto-detects /dev/serial/by-id/*MicroPython* (or *Pico* / *2e8a*), else ttyACM*.
Survives USB unplug/replug: drops stale handles when the by-id path vanishes
and reconnects on the next FIRE / idle health check.
"""

from __future__ import annotations

import glob
import os
import threading
import time
from typing import Optional

try:
    import serial
    from serial.tools import list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    serial = None
    list_ports = None
    SERIAL_AVAILABLE = False


DEFAULT_BAUD = 115200
DEFAULT_TIMEOUT_S = 1.5
STUB_LOG_INTERVAL_S = 15.0


def find_pico_port(preferred: str = "") -> Optional[str]:
    """Return a serial device path for the Pico / MicroPython CDC, or None."""
    if preferred and os.path.exists(preferred):
        return preferred

    # Prefer stable by-id symlinks (survives ttyACM0→ACM1 renumber).
    # Stock MicroPython names the device "MicroPython_Board...", not "Pico".
    by_id = sorted(
        glob.glob("/dev/serial/by-id/*MicroPython*")
        + glob.glob("/dev/serial/by-id/*micropython*")
        + glob.glob("/dev/serial/by-id/*Pico*")
        + glob.glob("/dev/serial/by-id/*pico*")
        + glob.glob("/dev/serial/by-id/*2e8a*")
        + glob.glob("/dev/serial/by-id/*Raspberry*")
    )
    if by_id:
        return by_id[0]

    if SERIAL_AVAILABLE and list_ports is not None:
        for p in list_ports.comports():
            blob = f"{p.description} {p.manufacturer} {p.product} {p.hwid}".lower()
            if any(k in blob for k in ("pico", "2e8a", "micropython", "raspberry pi")):
                return p.device

    for path in sorted(glob.glob("/dev/ttyACM*")):
        return path
    return None


class PicoSolenoid:
    """Thread-safe USB CDC driver for firmware/pico_solenoid/main.py."""

    def __init__(self, port: str = "", baud: int = DEFAULT_BAUD):
        self._port_pref = port or ""
        self._baud = int(baud)
        self._ser = None
        self._lock = threading.Lock()
        self._port_used = None
        self._last_error = None
        self._last_stub_log = 0.0
        self._was_missing = False
        self.connect()

    @property
    def available(self) -> bool:
        """True only if handle is open AND the device node still exists."""
        if self._ser is None or not getattr(self._ser, "is_open", False):
            return False
        if self._port_used and not os.path.exists(self._port_used):
            return False
        return True

    @property
    def port(self) -> Optional[str]:
        return self._port_used

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    def connect(self) -> bool:
        with self._lock:
            return self._connect_locked()

    def _drop_stale_locked(self):
        """Close handle if USB node disappeared (unplug) without waiting for I/O error."""
        if self._ser is None:
            return
        if self._port_used and not os.path.exists(self._port_used):
            try:
                self._ser.close()
            except Exception:
                pass
            self._ser = None
            self._port_used = None
            self._last_error = "USB device removed"
            self._was_missing = True

    def _connect_locked(self) -> bool:
        self._drop_stale_locked()
        if self.available:
            return True
        self._close_locked()
        if not SERIAL_AVAILABLE:
            self._last_error = "pyserial not installed"
            self._log_stub("pyserial missing")
            return False
        path = find_pico_port(self._port_pref)
        if not path:
            self._last_error = "no Pico serial port found"
            self._was_missing = True
            self._log_stub("no Pico on USB (expected MicroPython by-id / ttyACM*)")
            return False
        try:
            self._ser = serial.Serial(
                path, self._baud, timeout=DEFAULT_TIMEOUT_S, write_timeout=DEFAULT_TIMEOUT_S
            )
            time.sleep(0.08)
            self._ser.reset_input_buffer()
            self._ser.reset_output_buffer()
            self._port_used = path
            # SAFE-001: CLOSE after open. No Ctrl-D soft-reset (renumbers ACM).
            ok = self._cmd_locked("CLOSE", expect_prefix="OK CLOSE")
            if not ok:
                time.sleep(0.5)
                try:
                    self._ser.reset_input_buffer()
                except Exception:
                    pass
                ok = self._cmd_locked("CLOSE", expect_prefix="OK CLOSE")
            if ok:
                self._last_error = None
                tag = "reconnected after USB reseat" if self._was_missing else "Connected"
                print(f"[PicoSolenoid] {tag} {path} @ {self._baud} — gate CLOSED.")
                self._was_missing = False
                return True
            self._last_error = "CLOSE handshake failed (flash firmware/pico_solenoid/main.py?)"
            print(f"[PicoSolenoid] {self._last_error}")
            self._close_locked()
            self._was_missing = True
            return False
        except Exception as e:
            self._last_error = str(e)
            self._log_stub(f"open failed ({e})")
            self._close_locked()
            self._was_missing = True
            return False

    def _log_stub(self, msg: str):
        now = time.time()
        if now - self._last_stub_log >= STUB_LOG_INTERVAL_S:
            print(f"[PicoSolenoid] STUB — {msg}")
            self._last_stub_log = now

    def close(self):
        with self._lock:
            if self.available:
                try:
                    self._cmd_locked("CLOSE", expect_prefix="OK CLOSE")
                except Exception:
                    pass
            self._close_locked()

    def _close_locked(self):
        if self._ser is not None:
            try:
                self._ser.close()
            except Exception:
                pass
        self._ser = None
        self._port_used = None

    def _cmd_locked(self, cmd: str, expect_prefix: str = "", timeout_s: float = None) -> bool:
        self._drop_stale_locked()
        if self._ser is None or not self._ser.is_open:
            return False
        timeout_s = DEFAULT_TIMEOUT_S if timeout_s is None else timeout_s
        try:
            self._ser.reset_input_buffer()
            self._ser.write((cmd.strip() + "\n").encode("ascii"))
            self._ser.flush()
            deadline = time.time() + timeout_s
            while time.time() < deadline:
                line = self._ser.readline().decode("ascii", errors="ignore").strip()
                if not line:
                    continue
                if line == cmd.strip() or line.startswith(">>>"):
                    continue
                if expect_prefix:
                    if line.upper().startswith(expect_prefix.upper()):
                        return True
                    if line.upper().startswith("ERR"):
                        self._last_error = line
                        return False
                else:
                    return True
            self._last_error = f"timeout waiting for reply to {cmd!r}"
            return False
        except Exception as e:
            self._last_error = str(e)
            self._was_missing = True
            try:
                self._ser.close()
            except Exception:
                pass
            self._ser = None
            self._port_used = None
            return False

    def _ensure_locked(self) -> bool:
        self._drop_stale_locked()
        if self.available:
            return True
        return self._connect_locked()

    def health_check(self) -> bool:
        """
        Idle-path probe: drop stale USB handles and reconnect if the Pico is back.
        Returns True if a live link is available after the check.
        """
        with self._lock:
            self._drop_stale_locked()
            if self.available:
                # Cheap liveness: device node still present (already checked).
                return True
            return self._connect_locked()

    def ping(self) -> bool:
        with self._lock:
            if not self._ensure_locked():
                return False
            ok = self._cmd_locked("PING", expect_prefix="PONG")
            if not ok and self._connect_locked():
                ok = self._cmd_locked("PING", expect_prefix="PONG")
            return ok

    def set_open(self, open_: bool) -> bool:
        with self._lock:
            if not self._ensure_locked():
                return False
            cmd = "OPEN" if open_ else "CLOSE"
            expect = "OK OPEN" if open_ else "OK CLOSE"
            ok = self._cmd_locked(cmd, expect_prefix=expect)
            if not ok and self._connect_locked():
                ok = self._cmd_locked(cmd, expect_prefix=expect)
            return ok

    def fire_ms(self, ms: int) -> bool:
        """Pulse GP15 for ms on the Pico (precise timer). Reconnects after USB reseat."""
        ms = max(1, min(int(ms), 2000))
        with self._lock:
            if not self._ensure_locked():
                # Device may appear a moment after plug — brief retry
                time.sleep(0.3)
                if not self._connect_locked():
                    return False
            timeout_s = max(DEFAULT_TIMEOUT_S, ms / 1000.0 + 0.5)
            ok = self._cmd_locked(f"FIRE {ms}", expect_prefix="OK FIRE", timeout_s=timeout_s)
            if not ok:
                time.sleep(0.2)
                if self._connect_locked():
                    ok = self._cmd_locked(
                        f"FIRE {ms}", expect_prefix="OK FIRE", timeout_s=timeout_s
                    )
            return ok

    def status(self) -> dict:
        return {
            "available": self.available,
            "port": self._port_used,
            "baud": self._baud,
            "last_error": self._last_error,
            "backend": "pico_cdc",
        }
