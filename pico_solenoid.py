# Implements: HW-001 §5.4 Rev O, SW-001 §2.7
"""
pico_solenoid.py — Jetson USB CDC client for Pico W solenoid timer.

Protocol (115200 8N1, newline-terminated):
  FIRE <ms>  → Pico pulses GP15 for ms; reply OK FIRE <ms>
  OPEN       → GP15 HIGH; reply OK OPEN
  CLOSE      → GP15 LOW;  reply OK CLOSE
  PING       → reply PONG

Auto-detects /dev/serial/by-id/*Pico* (or *2e8a*), else /dev/ttyACM*.
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
        self.connect()

    @property
    def available(self) -> bool:
        return self._ser is not None and getattr(self._ser, "is_open", False)

    @property
    def port(self) -> Optional[str]:
        return self._port_used

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    def connect(self) -> bool:
        with self._lock:
            return self._connect_locked()

    def _connect_locked(self) -> bool:
        self._close_locked()
        if not SERIAL_AVAILABLE:
            self._last_error = "pyserial not installed"
            print("[PicoSolenoid] STUB — pyserial missing.")
            return False
        path = find_pico_port(self._port_pref)
        if not path:
            self._last_error = "no Pico serial port found"
            print("[PicoSolenoid] STUB — no Pico on USB (expected /dev/ttyACM* or by-id).")
            return False
        try:
            # Resolve by-id → real device for logging, but open the by-id path
            # so renumbering ACM0→ACM1 does not break a held handle as badly.
            self._ser = serial.Serial(
                path, self._baud, timeout=DEFAULT_TIMEOUT_S, write_timeout=DEFAULT_TIMEOUT_S
            )
            time.sleep(0.05)
            self._ser.reset_input_buffer()
            self._ser.reset_output_buffer()
            self._port_used = path
            # SAFE-001: ensure valve closed after open. Do NOT soft-reset (Ctrl-D)
            # here — that can renumber ttyACM and drop the link mid-session.
            ok = self._cmd_locked("CLOSE", expect_prefix="OK CLOSE")
            if not ok:
                # One retry after brief pause (firmware still booting)
                time.sleep(0.5)
                self._ser.reset_input_buffer()
                ok = self._cmd_locked("CLOSE", expect_prefix="OK CLOSE")
            if ok:
                self._last_error = None
                print(f"[PicoSolenoid] Connected {path} @ {self._baud} — gate CLOSED.")
                return True
            self._last_error = "CLOSE handshake failed (flash firmware/pico_solenoid/main.py?)"
            print(f"[PicoSolenoid] {self._last_error}")
            self._close_locked()
            return False
        except Exception as e:
            self._last_error = str(e)
            print(f"[PicoSolenoid] open failed ({e}) — STUB.")
            self._close_locked()
            return False

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
                # Skip MicroPython banners / echoes
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
            # Mark link dead so next call reconnects
            try:
                self._ser.close()
            except Exception:
                pass
            self._ser = None
            return False

    def _ensure_locked(self) -> bool:
        if self.available:
            return True
        return self._connect_locked()

    def ping(self) -> bool:
        with self._lock:
            if not self._ensure_locked():
                return False
            ok = self._cmd_locked("PING", expect_prefix="PONG")
            if not ok:
                if self._connect_locked():
                    ok = self._cmd_locked("PING", expect_prefix="PONG")
            return ok

    def set_open(self, open_: bool) -> bool:
        with self._lock:
            if not self._ensure_locked():
                return False
            cmd = "OPEN" if open_ else "CLOSE"
            expect = "OK OPEN" if open_ else "OK CLOSE"
            ok = self._cmd_locked(cmd, expect_prefix=expect)
            if not ok:
                if self._connect_locked():
                    ok = self._cmd_locked(cmd, expect_prefix=expect)
            return ok

    def fire_ms(self, ms: int) -> bool:
        """Pulse GP15 for ms on the Pico (precise timer)."""
        ms = max(1, min(int(ms), 2000))
        with self._lock:
            if not self._ensure_locked():
                return False
            timeout_s = max(DEFAULT_TIMEOUT_S, ms / 1000.0 + 0.5)
            ok = self._cmd_locked(f"FIRE {ms}", expect_prefix="OK FIRE", timeout_s=timeout_s)
            if not ok:
                # USB renumber / transient I/O — reconnect once and retry
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
