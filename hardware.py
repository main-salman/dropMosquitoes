# Implements: HW-001 §3-§6, SW-001 §2.2, §2.4-§2.7, SAFE-001 §1-§2
# Hardware abstraction layer for GPIO relays, Storm32 gimbal, TF-Luna LiDAR,
# overhead ballistic offset math, and predictive lead engine.
"""
hardware.py — Sniper Messy Mortar Hardware Control

Provides:
  - RelayController: GPIO-based relay switching for pump and gimbal power
  - GimbalController: Serial UART interface to the Storm32 BGC board
  - LiDARController: I2C interface to Benewake TF-Luna distance sensor
  - pixel_to_angle(): Pixel-to-degree math for click-to-aim
  - compute_ballistic_offset(): Overhead parabolic drop correction

SAFETY: All GPIO access wrapped in try/finally to guarantee LOW on crash.
"""

import math
import time
import struct
import threading

# ============================================================================
# HARDWARE STUB MODE
# When running on a dev machine (not a Jetson), we use stubs so the Flask
# server can still start and the GUI can be tested without real hardware.
# ============================================================================
try:
    import Jetson.GPIO as GPIO
    JETSON_AVAILABLE = True
except ImportError:
    JETSON_AVAILABLE = False
    print("[hardware] WARNING: Jetson.GPIO not found. Running in STUB mode.")

# ECO-2026-004 Rev O: solenoid production path = Pico W USB CDC → GP15 → IRLB8721
# (pico_solenoid.py). Legacy Rev E path: PR.05 (T36) → dual-MOS module SIG.
# Why: PY.00 is a weak SPI-function pad on the Yahboom carrier — even via libgpiod
# it only sources ~1.9V into the dual-MOSFET module's internal pull-down, below the
# 3.3V trigger threshold (module never switched). PR.05 is the sister pad of the
# proven-good pump pad PR.04 (same GPIO port) and drives a clean push-pull 3.3V.
try:
    import gpiod
    LIBGPIOD_AVAILABLE = True
except ImportError:
    LIBGPIOD_AVAILABLE = False
    print("[hardware] WARNING: python3-libgpiod not found. Solenoid will be stubbed.")

try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    print("[hardware] WARNING: pyserial not found. Gimbal commands will be no-ops.")

# PADCTL GPIO output value for Orin Nano (TRM: SFIO=0, E_INPUT=0, TRISTATE=0, PUPD=NONE).
# Clearing only bit 4 leaves internal pull-down + tristate — reads ~1.5V instead of 3.3V.
_PADCTL_GPIO_OUTPUT = 0x05
_PADCTL_REGS = (
    ("PR.04", 0x98),    # BCM 17 / Pin 11 / Terminal 11 — pump relay
    ("PR.05", 0x90),    # BCM 16 / Pin 36 / Terminal 36 — solenoid trigger (module SIG)
    ("PQ.05", 0x68),    # BCM 5 / Pin 29 / Terminal 29 — Relay CH2 (solenoid 12V interlock, Rev L)
)
# reg_addr (Jetson.GPIO): PR.04=0x2430098, PR.05=0x2430090 → offsets from base 0x02430000.
# Both pads boot tristated; without the 0x05 PADCTL write the pin outputs 0V even
# though libgpiod requests it as OUTPUT.


def configure_push_pull(only: tuple = None) -> bool:
    """
    ECO-2026-004: Force selected pads into GPIO push-pull via PADCTL writes.
    On Yahboom Orin Nano these pads boot tristated — GPIO HIGH can read 0V
    until 0x05 is written.

    Must run as root (/dev/mem).

    IMPORTANT: Do NOT rewrite PR.05 (solenoid SIG) on every pump toggle.
    Re-mmapping PR.05 while libgpiod owns it can glitch SIG high → MOSFET
    module turns on / runs hot. Pump path only touches PR.04; full set is
    for controller init only. (2026-07-19 keep-alive coincident fault.)
    """
    try:
        import mmap
        import struct

        regs = _PADCTL_REGS
        if only is not None:
            want = set(only)
            regs = tuple(r for r in _PADCTL_REGS if r[0] in want)
            if not regs:
                return False

        with open("/dev/mem", "r+b") as f:
            mem = mmap.mmap(f.fileno(), 0x10000, offset=0x02430000)
            results = []
            for name, offset in regs:
                old = struct.unpack("<I", mem[offset:offset + 4])[0]
                mem[offset:offset + 4] = struct.pack("<I", _PADCTL_GPIO_OUTPUT)
                new = struct.unpack("<I", mem[offset:offset + 4])[0]
                results.append(f"{name}={hex(old)}→{hex(new)}")
            mem.close()

        print(f"[PADMUX] GPIO output mode: {', '.join(results)}")
        return True
    except Exception as e:
        print(f"[PADMUX] WARNING: Could not force Push-Pull mode (needs root): {e}")
        return False


def configure_pwm_pinmux():
    """
    ECO-2026-008: Configure pinmux for PWM output on BCM 12 (Pin 32) and BCM 13 (Pin 33).
    These pins drive the Storm32 RC-0 (Pitch) and RC-2 (Yaw) inputs via hardware PWM.
    Without this, the pins are locked to INPUT mode and no PWM signal reaches the wires.
    Uses direct /dev/mem writes (same approach as configure_push_pull).
    Needs root privileges.
    """
    try:
        import mmap
        import struct
        with open("/dev/mem", "r+b") as f:
            # BCM 12 (Pin 32, PWM0) at register 0x2434080 → write 0x5 (output)
            mem1 = mmap.mmap(f.fileno(), 0x10000, offset=0x2430000)
            mem1[0x4080:0x4084] = struct.pack("<I", 0x5)
            mem1.close()

            # BCM 13 (Pin 33, PWM2) at register 0x2434040 → write 0x4 (output)
            mem2 = mmap.mmap(f.fileno(), 0x10000, offset=0x2430000)
            mem2[0x4040:0x4044] = struct.pack("<I", 0x4)
            mem2.close()

        print("[PADMUX] PWM pinmux configured: BCM12=0x5 (output), BCM13=0x4 (output)")
    except Exception as e:
        print(f"[PADMUX] WARNING: Could not configure PWM pinmux: {e}")


try:
    import smbus2
    I2C_AVAILABLE = True
except ImportError:
    I2C_AVAILABLE = False
    print("[hardware] WARNING: smbus2 not found. LiDAR will be stubbed.")


# ============================================================================
# GPIO PIN ASSIGNMENTS — ECO-2026-004
# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
# ROUTING: Jetson GPIO Header → 40-pin F/F Ribbon Cable → IDC40P Terminal Block
# All wiring connects to screw terminals on the IDC40P breakout, NOT the Jetson.
# Terminal numbers match physical pin numbers 1:1.
# See: https://www.jetsonhacks.com/nvidia-jetson-orin-nano-gpio-header-pinout/
# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
RELAY_PUMP_PIN = 17       # BCM 17 = Pin 11 → IDC40P Terminal 11 → Relay CH1 (R385 Pump) [Jetson.GPIO]
RELAY_SOL12V_PIN = 5      # BCM 5 = Pin 29 → IDC40P Terminal 29 → Relay CH2 IN (legacy module 12V)
SOLENOID_PIN = 16         # BCM 16 = Pin 36 (legacy module SIG; unused when solenoid_driver=pico)

# Legacy solenoid trigger (dual-MOSFET module SIG) — libgpiod when solenoid_driver=legacy_module.
SOLENOID_GPIOCHIP = "gpiochip0"
SOLENOID_LINE_NAME = "PR.05"   # BCM 16 / Pin 36 / Terminal 36 — resolved by pad name
SOLENOID_LINE_OFFSET = 113     # Fallback line offset if name lookup fails

# Production (Rev O): settings.accumulator.solenoid_driver = "pico" (default).
# Legacy fallback: "legacy_module" = T36 SIG + T29/CH2 dual-MOS path.
SOLENOID_DRIVER_PICO = "pico"
SOLENOID_DRIVER_LEGACY = "legacy_module"
# =======================================================================================================

try:
    from pico_solenoid import PicoSolenoid
except ImportError:
    PicoSolenoid = None
    print("[hardware] pico_solenoid import failed — Pico driver unavailable.")


class _LibGpiodSolenoid:
    """
    libgpiod-backed push-pull output, requested once and held for the
    controller's lifetime. Used for both the solenoid trigger (PR.05 → module
    SIG; low = valve CLOSED, high = valve OPEN, microsecond-precise pulses for
    AccumulatorManager.fire()) and the Rev H 12V boot interlock (PY.00 →
    Relay CH2 IN gating the module's DC IN+).

    Requires PADCTL GPIO mode (configure_push_pull) to run first — otherwise
    the tristated pad outputs 0V even though libgpiod requests the line as
    OUTPUT.
    """

    def __init__(self, line_name=SOLENOID_LINE_NAME, line_offset=SOLENOID_LINE_OFFSET,
                 consumer="sentry-solenoid", label="Solenoid"):
        self._line = None
        self._label = label
        if not LIBGPIOD_AVAILABLE:
            print(f"[{label}] libgpiod unavailable — STUB mode.")
            return
        try:
            line = None
            try:
                line = gpiod.find_line(line_name)
            except Exception:
                line = None
            if line is None:
                line = gpiod.Chip(SOLENOID_GPIOCHIP).get_line(line_offset)
            line.request(consumer=consumer,
                         type=gpiod.LINE_REQ_DIR_OUT, default_vals=[0])
            self._line = line
            print(f"[{label}] libgpiod line acquired ({line_name}) — LOW.")
        except Exception as e:
            print(f"[{label}] libgpiod init failed ({e}) — STUB mode.")
            self._line = None

    @property
    def available(self) -> bool:
        return self._line is not None

    def set(self, state: bool):
        if self._line is not None:
            self._line.set_value(1 if state else 0)

    def get(self):
        """Read back driven line value (0/1), or None if unavailable."""
        if self._line is None:
            return None
        try:
            return int(self._line.get_value())
        except Exception:
            return None

    def release(self):
        if self._line is not None:
            try:
                self._line.set_value(0)
                self._line.release()
            except Exception:
                pass
            self._line = None


class _JetsonGpioOut:
    """Jetson.GPIO output (used for pump + Relay CH2)."""

    def __init__(self, bcm_pin: int, label: str = "GPIO"):
        self._pin = int(bcm_pin)
        self._label = label
        self._ok = False
        if JETSON_AVAILABLE:
            try:
                GPIO.setup(self._pin, GPIO.OUT, initial=GPIO.LOW)
                self._ok = True
                print(f"[{label}] Jetson.GPIO BCM{self._pin} ready — LOW.")
            except Exception as e:
                print(f"[{label}] Jetson.GPIO BCM{self._pin} init failed: {e}")

    @property
    def available(self) -> bool:
        return self._ok

    def set(self, state: bool):
        if self._ok:
            GPIO.output(self._pin, GPIO.HIGH if state else GPIO.LOW)

    def get(self):
        if not self._ok:
            return None
        try:
            return int(GPIO.input(self._pin))
        except Exception:
            return None

    def release(self):
        if self._ok:
            try:
                GPIO.output(self._pin, GPIO.LOW)
            except Exception:
                pass
            self._ok = False


class RelayController:
    """
    Controls the R385 pump (Monk Makes Relay CH1) and GOODRIG 12V solenoid.

    ECO-2026-004 Rev O (production): Pico W USB CDC → GP15 → IRLB8721
    (`solenoid_driver=pico`, default). Pump unchanged on BCM 17 / T11.

    Legacy (`solenoid_driver=legacy_module`): T36/PR.05 → dual-MOS SIG + optional
    Relay CH2 (T29) module-12V interlock.

    SAFE-001 §1: Solenoid MUST initialize CLOSED.
    SAFE-001 §2: recover / cleanup guarantee closed on crash.
    """

    # Solid-state Relay CH2 settle before asserting SIG (legacy path only).
    _SOL12V_SETTLE_SEC = 0.080

    def __init__(self, solenoid_driver: str = SOLENOID_DRIVER_PICO,
                 pico_port: str = "", pico_baud: int = 115200):
        global JETSON_AVAILABLE
        self._pump_state = False
        self._solenoid_state = False
        self._module_power_hold = False  # ARMED CH2 hold (legacy only)
        self._module_12v_hardwired = False
        self._pulse_busy = False
        self._lock = threading.Lock()
        self._pico = None
        driver = (solenoid_driver or SOLENOID_DRIVER_PICO).strip().lower()
        if driver not in (SOLENOID_DRIVER_PICO, SOLENOID_DRIVER_LEGACY):
            driver = SOLENOID_DRIVER_PICO
        self._solenoid_driver = driver

        configure_push_pull()

        if JETSON_AVAILABLE:
            try:
                GPIO.setmode(GPIO.BCM)
                GPIO.setwarnings(False)
                GPIO.setup(RELAY_PUMP_PIN, GPIO.OUT, initial=GPIO.LOW)
                print(f"[RelayController] Pump GPIO initialized (BCM{RELAY_PUMP_PIN}).")
            except OSError as e:
                print(f"[RelayController] Pump GPIO init failed ({e}); pump in STUB mode.")
                JETSON_AVAILABLE = False
            except Exception as e:
                print(f"[RelayController] Unexpected pump GPIO error: {e}; pump in STUB mode.")
                JETSON_AVAILABLE = False
        else:
            print("[RelayController] STUB MODE — no real pump GPIO control.")

        self._solenoid = _LibGpiodSolenoid()
        self._solenoid.set(False)
        self._sol_12v = _JetsonGpioOut(RELAY_SOL12V_PIN, label="Sol12V")
        self._sol_12v_state = False

        if self._solenoid_driver == SOLENOID_DRIVER_PICO:
            if PicoSolenoid is None:
                print("[RelayController] Pico driver missing — solenoid STUB (CLOSED).")
            else:
                self._pico = PicoSolenoid(port=pico_port or "", baud=int(pico_baud or 115200))
            self._force_solenoid_safe()
            print("[RelayController] Solenoid driver = PICO (USB CDC → GP15 → IRLB8721).")
        else:
            self._force_solenoid_safe()
            self._solenoid.set(False)
            if not self._module_12v_hardwired:
                self._boot_warm_module_12v()
                print("[RelayController] Solenoid driver = LEGACY_MODULE "
                      f"(SIG T36 + CH2 BCM{RELAY_SOL12V_PIN}/T29).")
            else:
                print("[RelayController] Module 12V HARDWIRED mode — CH2 GPIO idle.")

        self._idle_stop = threading.Event()
        self._idle_thread = threading.Thread(
            target=self._idle_sig_watchdog, daemon=True, name="solenoid-idle-watchdog")
        self._idle_thread.start()

    @property
    def using_pico(self) -> bool:
        return self._solenoid_driver == SOLENOID_DRIVER_PICO

    def set_solenoid_driver(self, driver: str, pico_port: str = None, pico_baud: int = None):
        """Switch pico ↔ legacy_module at runtime (settings apply)."""
        driver = (driver or SOLENOID_DRIVER_PICO).strip().lower()
        if driver not in (SOLENOID_DRIVER_PICO, SOLENOID_DRIVER_LEGACY):
            driver = SOLENOID_DRIVER_PICO
        with self._lock:
            prev = self._solenoid_driver
            same = (prev == driver and driver == SOLENOID_DRIVER_PICO
                    and self._pico is not None and self._pico.available
                    and pico_port is None and pico_baud is None)
            if same:
                return
            self._force_solenoid_safe()
            self._solenoid_driver = driver
            if driver == SOLENOID_DRIVER_PICO:
                if self._pico is not None and pico_port is None and pico_baud is None:
                    self._pico.connect()
                else:
                    if self._pico is not None:
                        self._pico.close()
                    if PicoSolenoid is not None:
                        self._pico = PicoSolenoid(
                            port="" if pico_port is None else str(pico_port),
                            baud=int(115200 if pico_baud is None else pico_baud),
                        )
            else:
                if self._pico is not None:
                    self._pico.close()
                    self._pico = None
                self._solenoid.set(False)
            print(f"[RelayController] Solenoid driver {prev} → {driver}")

    def set_module_12v_hardwired(self, hardwired: bool):
        """
        Legacy module path only. When True: do not drive Relay CH2.
        Ignored for valve control when solenoid_driver=pico.
        """
        with self._lock:
            self._module_12v_hardwired = bool(hardwired)
            self._module_power_hold = False
            if self.using_pico:
                if self._pico is not None:
                    self._pico.set_open(False)
                self._solenoid_state = False
                print("[RelayController] module_12v_hardwired ignored (pico driver)")
                return
            self._solenoid.set(False)
            self._solenoid_state = False
            self._sol_12v.set(False)
            self._sol_12v_state = False
            mode = "HARDWIRED (SIG-only)" if self._module_12v_hardwired else "Relay CH2 gated"
            print(f"[RelayController] Module 12V mode → {mode}")

    def _boot_warm_module_12v(self):
        """Brief CH2 ON with SIG LOW after boot — wakes SSR/module caps."""
        if self._module_12v_hardwired:
            return
        with self._lock:
            try:
                self._solenoid.set(False)
                self._solenoid_state = False
                self._drive_module_12v_on(settle=False)
                time.sleep(0.15)
            finally:
                self._force_solenoid_safe()
                self._solenoid.set(False)
        print("[RelayController] Boot warm: CH2 pulsed 150ms (SIG LOW).")

    def _idle_sig_watchdog(self):
        """
        Periodic hygiene. Pico path: ensure CLOSE if idle. Legacy: SIG/CH2.
        """
        while not self._idle_stop.wait(0.5):
            with self._lock:
                if self._solenoid_state or self._pulse_busy:
                    continue
                if self.using_pico:
                    # Drop stale USB handles after unplug; reconnect when Pico returns.
                    if self._pico is not None:
                        self._pico.health_check()
                    continue
                rb = self._solenoid.get()
                if rb == 1:
                    self._solenoid.set(False)
                    self._solenoid_state = False
                    print("[RelayController] IDLE WATCHDOG: cleared stuck SIG HIGH")
                if self._module_12v_hardwired:
                    continue
                if self._module_power_hold:
                    prev = self._sol_12v.get()
                    self._drive_module_12v_on(settle=False)
                    now = self._sol_12v.get()
                    if prev == 0 or now == 0:
                        print(f"[RelayController] HOLD RE-ASSERT CH2 "
                              f"(readback was {prev} → {now})")
                    continue
                if self._sol_12v_state:
                    print("[RelayController] IDLE WATCHDOG: CH2 was ON while idle — cutting 12V")
                    self._sol_12v.set(False)
                    self._sol_12v_state = False

    def _drive_module_12v_on(self, settle: bool = False):
        """
        Drive CH2 HIGH unless hardwired. Caller MUST hold self._lock.
        """
        if self._module_12v_hardwired:
            self._sol_12v_state = True  # logical "powered" for status
            return
        # Refresh PQ.05 padmux occasionally — do NOT touch PR.05 here
        if settle:
            configure_push_pull(only=("PQ.05",))
        self._sol_12v.set(True)
        self._sol_12v_state = True
        if settle:
            time.sleep(self._SOL12V_SETTLE_SEC)

    def _assert_sig_low(self):
        """Drive SIG LOW only if not already commanded closed. Caller holds lock."""
        if self._solenoid_state or self._solenoid.get() == 1:
            self._solenoid.set(False)
            self._solenoid_state = False
            return True
        return False

    # -- Legacy pre-pressurization (DEPRECATED by AccumulatorManager) ---------
    # Kept for backward compatibility; AccumulatorManager.fire() is preferred.
    stabilize_ms = 50
    settle_ms = 80
    pre_pressurize = False  # Disabled by default — accumulator handles this now

    def fire_pump(self, duration_sec: float = 0.025):
        """
        LEGACY: Fire the water pump relay for a specified duration.
        In ECO-2026-004, use AccumulatorManager.fire() instead — it pulses
        the solenoid while the accumulator provides stored pressure.

        This method is still used internally by AccumulatorManager for
        charging the accumulator tank (pump on, solenoid closed).

        Args:
            duration_sec: Pulse length in seconds (0.001 to 5.0).
        """
        duration_sec = max(0.001, min(duration_sec, 5.0))  # Allow longer for charging

        if self.pre_pressurize:
            print(f"[RelayController] FIRE! Stabilize {self.stabilize_ms}ms → "
                  f"settle {self.settle_ms}ms → pulse {duration_sec*1000:.0f}ms")
        else:
            print(f"[RelayController] Pump ON for {duration_sec:.3f}s")

        def _pulse():
            with self._lock:
                try:
                    if self.pre_pressurize and self.stabilize_ms > 0:
                        self._set_pump(True)
                        time.sleep(self.stabilize_ms / 1000.0)
                        self._set_pump(False)
                        time.sleep(self.settle_ms / 1000.0)

                    self._set_pump(True)
                    time.sleep(duration_sec)
                finally:
                    self._set_pump(False)

        threading.Thread(target=_pulse, daemon=True).start()

    def set_pump(self, state: bool):
        """Manual pump toggle (for the GUI override switches)."""
        with self._lock:
            self._set_pump(state)

    def _set_pump(self, state: bool):
        """Caller should hold self._lock (via set_pump)."""
        self._pump_state = state
        if JETSON_AVAILABLE:
            # Do NOT rewrite PADCTL on every pump edge — mmap/write of the
            # padctl region was correlated with SIG glitches and lost clicks
            # after a few auto-cal shots. Pinmux is set once at init/recover.
            GPIO.output(RELAY_PUMP_PIN, GPIO.HIGH if state else GPIO.LOW)
        # Charge safety only: if starting pump with valve commanded CLOSED,
        # clear a stuck SIG HIGH. Never close an intentional open (DRAIN PIPE
        # keeps solenoid OPEN + pump ON — closing SIG here caused multi-click
        # chatter and left the drain path wrong).
        if (not self.using_pico and state and not self._solenoid_state
                and not self._pulse_busy):
            if self._solenoid.get() == 1:
                self._solenoid.set(False)
                print("[RelayController] Pump start: cleared stuck SIG HIGH")
        # Pump edges can EMI-glitch PQ.05; re-drive CH2 while ARMED hold is on.
        if (not self.using_pico and self._module_power_hold
                and not self._module_12v_hardwired):
            self._drive_module_12v_on(settle=False)
        print(f"[RelayController] Pump {'ON' if state else 'OFF'}")

    # -- Solenoid Control (ECO-2026-004) --------------------------------------

    def _force_solenoid_safe(self):
        """Valve CLOSED + clear holds. Caller holds lock (or init)."""
        if self.using_pico and self._pico is not None:
            self._pico.set_open(False)
        else:
            self._solenoid.set(False)
            self._sol_12v.set(False)
            self._sol_12v_state = False
        self._solenoid_state = False
        self._module_power_hold = False

    def set_module_power_hold(self, hold: bool):
        """
        ARMED-session power for legacy module CH2. No-op in pico mode
        (coil 12V is always available; Pico only pulses the gate).
        """
        with self._lock:
            if self.using_pico:
                self._module_power_hold = False
                if hold:
                    if self._pico is not None:
                        self._pico.set_open(False)
                    self._solenoid_state = False
                    print("[RelayController] Pico mode ARMED — gate stays CLOSED between shots")
                else:
                    if self._pico is not None:
                        self._pico.set_open(False)
                    self._solenoid_state = False
                    print("[RelayController] Pico mode DISARMED — gate CLOSED")
                return
            self._module_power_hold = bool(hold) and not self._module_12v_hardwired
            if hold:
                self._solenoid.set(False)
                self._solenoid_state = False
                if self._module_12v_hardwired:
                    self._sol_12v_state = True
                    print("[RelayController] Module 12V HARDWIRED — ARMED (SIG-only pulses)")
                else:
                    self._drive_module_12v_on(settle=True)
                    rb = self._sol_12v.get()
                    print("[RelayController] Module 12V HOLD ON (ARMED session — SIG-only pulses)"
                          f" ch2_readback={rb}")
            else:
                self._solenoid.set(False)
                self._solenoid_state = False
                self._sol_12v.set(False)
                self._sol_12v_state = False
                print("[RelayController] Module 12V HOLD OFF")

    def set_solenoid(self, state: bool):
        """
        Open or close the solenoid valve.
        Always takes the relay lock (safe vs idle watchdog).
        """
        with self._lock:
            self._set_solenoid(state)

    def _set_solenoid(self, state: bool):
        """Caller MUST hold self._lock."""
        if self.using_pico:
            ok = True
            if self._pico is not None:
                ok = self._pico.set_open(bool(state))
            self._solenoid_state = bool(state) and ok
            print(f"[RelayController] Solenoid {'OPEN' if self._solenoid_state else 'CLOSED'} "
                  f"(Pico GP15) ok={ok}")
            return

        if state:
            need_settle = (
                not self._module_12v_hardwired
                and (not self._sol_12v_state or not self._module_power_hold)
            )
            if not self._module_12v_hardwired:
                self._solenoid.set(False)
                self._solenoid_state = False
            self._drive_module_12v_on(settle=need_settle)
            self._solenoid.set(True)
            self._solenoid_state = True
            if self._module_12v_hardwired:
                power = "hardwired"
            elif self._module_power_hold:
                power = "hold"
            else:
                power = "pulse-power"
            print(f"[RelayController] Solenoid OPEN (SIG HIGH, 12V={power}"
                  f", ch2_rb={self._sol_12v.get()})")
        else:
            if not self._solenoid_state and self._solenoid.get() != 1:
                if self._module_power_hold and not self._module_12v_hardwired:
                    self._drive_module_12v_on(settle=False)
                return
            self._solenoid.set(False)
            self._solenoid_state = False
            if self._module_12v_hardwired:
                print("[RelayController] Solenoid CLOSED (SIG LOW, 12V=hardwired)")
            elif self._module_power_hold:
                self._drive_module_12v_on(settle=False)
                print("[RelayController] Solenoid CLOSED (SIG LOW, CH2 hold ON"
                      f", ch2_rb={self._sol_12v.get()})")
            else:
                self._sol_12v.set(False)
                self._sol_12v_state = False
                print("[RelayController] Solenoid CLOSED (SIG LOW, CH2 OFF)")

    def pulse_solenoid(self, duration_sec: float = 0.025) -> dict:
        """
        Synchronous solenoid pulse under the relay lock.
        Pico path: FIRE <ms> timed on the Pico. Legacy: OPEN + sleep + CLOSE.
        """
        duration_sec = max(0.001, min(float(duration_sec), 2.0))
        t0 = time.time()
        ch2_held = False
        ch2_rb = None
        ch2_rb_after = None
        hardwired = False
        pico_ok = None
        with self._lock:
            if self._pulse_busy:
                print("[RelayController] SOLENOID PULSE rejected — busy")
                return {
                    "status": "busy",
                    "error": "solenoid pulse already in progress",
                    "duration_ms": round(duration_sec * 1000.0, 1),
                    "elapsed_ms": 0.0,
                    "solenoid_state": self._solenoid_state,
                    "solenoid_12v": self._sol_12v_state,
                    "ch2_held": False,
                    "module_12v_hardwired": self._module_12v_hardwired,
                    "solenoid_driver": self._solenoid_driver,
                }
            self._pulse_busy = True
            hardwired = self._module_12v_hardwired
            try:
                if self.using_pico:
                    ms = max(1, int(round(duration_sec * 1000.0)))
                    pico_ok = bool(self._pico and self._pico.fire_ms(ms))
                    self._solenoid_state = False
                    if not pico_ok:
                        print("[RelayController] SOLENOID PULSE Pico FIRE failed — "
                              f"{getattr(self._pico, 'last_error', None)}")
                else:
                    self._set_solenoid(True)
                    ch2_rb = self._sol_12v.get()
                    ch2_held = bool(self._module_power_hold) or hardwired
                    time.sleep(duration_sec)
            finally:
                if not self.using_pico:
                    self._set_solenoid(False)
                    time.sleep(0.04)
                    ch2_rb_after = self._sol_12v.get()
                elif self._pico is not None:
                    self._pico.set_open(False)
                    self._solenoid_state = False
                self._pulse_busy = False
        elapsed_ms = (time.time() - t0) * 1000.0
        status = "complete"
        if self.using_pico and pico_ok is False:
            status = "error"
        print(f"[RelayController] SOLENOID PULSE done: cmd={duration_sec*1000:.1f}ms "
              f"elapsed={elapsed_ms:.1f}ms driver={self._solenoid_driver} "
              f"pico_ok={pico_ok} hardwired={hardwired} ch2_held={ch2_held} "
              f"ch2_rb={ch2_rb}/{ch2_rb_after}")
        return {
            "status": status,
            "duration_ms": round(duration_sec * 1000.0, 1),
            "elapsed_ms": round(elapsed_ms, 1),
            "solenoid_state": self._solenoid_state,
            "solenoid_12v": True if self.using_pico else self._sol_12v_state,
            "ch2_held": ch2_held,
            "ch2_readback": ch2_rb,
            "ch2_readback_after": ch2_rb_after,
            "module_power_hold": self._module_power_hold,
            "module_12v_hardwired": hardwired,
            "solenoid_driver": self._solenoid_driver,
            "pico_ok": pico_ok,
            "pico": self._pico.status() if self._pico else None,
        }

    def recover_solenoid(self, re_pinmux: bool = False) -> dict:
        """
        Force valve CLOSED + clear session hold.
        Legacy: SIG LOW + CH2 OFF. Pico: CLOSE over USB.
        """
        with self._lock:
            if re_pinmux and not self.using_pico:
                configure_push_pull(only=("PR.05", "PQ.05"))
            self._force_solenoid_safe()
            if not self.using_pico:
                self._solenoid.set(False)
            print("[RelayController] Solenoid drive recovered "
                  f"(driver={self._solenoid_driver}"
                  f"{', pinmux rewritten' if re_pinmux and not self.using_pico else ''})")
            return {
                "solenoid": False,
                "solenoid_12v": False if not self.using_pico else True,
                "re_pinmux": bool(re_pinmux) and not self.using_pico,
                "solenoid_driver": self._solenoid_driver,
                "pico": self._pico.status() if self._pico else None,
            }

    def fire_solenoid(self, duration_sec: float = 0.025):
        """
        Async wrapper around pulse_solenoid() for legacy non-blocking callers.
        Prefer pulse_solenoid() for fire paths that need a guaranteed pulse.
        """
        duration_sec = max(0.001, min(duration_sec, 2.0))
        print(f"[RelayController] SOLENOID PULSE (async): {duration_sec*1000:.1f}ms")

        def _pulse():
            self.pulse_solenoid(duration_sec)

        threading.Thread(target=_pulse, daemon=True, name="solenoid-pulse").start()

    def drain_line(self, duration_sec: float = 15.0) -> dict:
        """
        Maintenance: solenoid OPEN + pump ON for duration_sec to flush the line.
        Holds the relay lock so the idle watchdog cannot cut mid-drain.
        Always ends with pump OFF and solenoid CLOSED.
        """
        duration_sec = max(1.0, min(float(duration_sec), 30.0))
        t0 = time.time()
        print(f"[RelayController] 🚰 DRAIN LINE: solenoid OPEN + pump ON for "
              f"{duration_sec:.1f}s")
        with self._lock:
            self._pulse_busy = True  # block click-test / watchdog during drain
            try:
                self._set_solenoid(True)
                # Direct pump GPIO — do not use paths that can touch SIG
                self._pump_state = True
                if JETSON_AVAILABLE:
                    GPIO.output(RELAY_PUMP_PIN, GPIO.HIGH)
                print("[RelayController] Pump ON (drain — valve stays OPEN)")
                time.sleep(duration_sec)
            finally:
                self._pump_state = False
                if JETSON_AVAILABLE:
                    GPIO.output(RELAY_PUMP_PIN, GPIO.LOW)
                print("[RelayController] Pump OFF")
                self._set_solenoid(False)
                self._pulse_busy = False
        elapsed = time.time() - t0
        print(f"[RelayController] 🚰 DRAIN complete in {elapsed:.1f}s — safe idle")
        return {
            "status": "complete",
            "duration_sec": round(duration_sec, 1),
            "elapsed_sec": round(elapsed, 1),
            "pump": self._pump_state,
            "solenoid": self._solenoid_state,
        }

    def set_solenoid_power(self, state: bool):
        """
        Manual override for Relay CH2 (module 12V). Ignored when hardwired.
        """
        with self._lock:
            self._solenoid.set(False)
            self._solenoid_state = False
            if self._module_12v_hardwired:
                print("[RelayController] Solenoid 12V override ignored (hardwired mode)")
                return
            self._sol_12v.set(bool(state))
            self._sol_12v_state = bool(state)
            print(f"[RelayController] Solenoid 12V (Relay CH2) {'ON' if state else 'OFF'}")

    def hold_ch2(self, seconds: float = 5.0) -> dict:
        """
        Drive Relay CH2 IN (BCM 5 / T29) HIGH for measurement — SIG stays LOW.
        Use to watch Monk Makes Channel B LED and meter Terminal 29 (~3.3V).
        Holds pulse_busy so the idle watchdog cannot cut CH2 mid-hold.
        """
        seconds = max(1.0, min(float(seconds), 30.0))
        if self._module_12v_hardwired:
            return {
                "status": "skipped",
                "error": "module_12v_hardwired=True — CH2 GPIO idle; jumper load or disable hardwired",
                "module_12v_hardwired": True,
            }
        with self._lock:
            self._pulse_busy = True
            self._solenoid.set(False)
            self._solenoid_state = False
            configure_push_pull(only=("PQ.05",))
            self._sol_12v.set(True)
            self._sol_12v_state = True
            rb = self._sol_12v.get()
            print(f"[RelayController] CH2 HOLD ON {seconds:.0f}s "
                  f"(SIG LOW, pin=BCM{RELAY_SOL12V_PIN}/T29, ch2_rb={rb})")
        try:
            time.sleep(seconds)
        finally:
            with self._lock:
                self._sol_12v.set(False)
                self._sol_12v_state = False
                rb_after = self._sol_12v.get()
                self._pulse_busy = False
                print(f"[RelayController] CH2 HOLD OFF (ch2_rb_after={rb_after})")
        return {
            "status": "complete",
            "held_sec": seconds,
            "ch2_readback": rb,
            "ch2_readback_after": rb_after,
            "pin": f"BCM{RELAY_SOL12V_PIN}/T29",
            "sig_held": False,
        }

    def hold_sig(self, seconds: float = 5.0) -> dict:
        """
        Drive module SIG HIGH for measurement — CH2 stays OFF (no module 12V).
        MOSFET SIG LED can light without coil power; safer than set_solenoid().
        """
        seconds = max(1.0, min(float(seconds), 30.0))
        with self._lock:
            self._pulse_busy = True
            self._sol_12v.set(False)
            self._sol_12v_state = False
            self._module_power_hold = False
            self._solenoid.set(True)
            self._solenoid_state = True
            print(f"[RelayController] SIG HOLD ON {seconds:.0f}s (CH2 OFF)")
        try:
            time.sleep(seconds)
        finally:
            with self._lock:
                self._solenoid.set(False)
                self._solenoid_state = False
                self._pulse_busy = False
                print("[RelayController] SIG HOLD OFF")
        return {
            "status": "complete",
            "held_sec": seconds,
            "solenoid_state": False,
            "ch2_off": True,
            "backend": "libgpiod" if self._solenoid.available else "stub",
            "module_12v_hardwired": self._module_12v_hardwired,
        }

    # -- Backward compatibility -----------------------------------------------

    def set_gimbal_power(self, state: bool):
        """
        DEPRECATED: Gimbal relay removed in ECO-2026-004.
        Servos powered via dedicated 5V 10A buck converter.
        Kept as no-op for backward compatibility with app.py calls.
        """
        print(f"[RelayController] set_gimbal_power() deprecated — servos always powered.")

    # -- Status ---------------------------------------------------------------

    def get_status(self) -> dict:
        pico_st = self._pico.status() if self._pico else None
        return {
            "pump": self._pump_state,
            "solenoid": self._solenoid_state,
            "solenoid_12v": True if self.using_pico else self._sol_12v_state,
            "module_power_hold": self._module_power_hold,
            "module_12v_hardwired": self._module_12v_hardwired,
            "solenoid_driver": self._solenoid_driver,
            "pico": pico_st,
            "pico_available": bool(pico_st and pico_st.get("available")),
            "ch2_readback": None if self.using_pico else (
                self._sol_12v.get() if hasattr(self, "_sol_12v") else None),
            "sig_readback": None if self.using_pico else (
                self._solenoid.get() if hasattr(self, "_solenoid") else None),
            "gimbal_power": True  # Always on (backward compat)
        }

    # -- Cleanup --------------------------------------------------------------

    def cleanup(self):
        """Ensure pump OFF, solenoid CLOSED, then release GPIO / Pico."""
        print("[RelayController] Cleaning up GPIO...")
        try:
            if hasattr(self, "_idle_stop"):
                self._idle_stop.set()
            self._force_solenoid_safe()
            if self._pico is not None:
                self._pico.close()
            self._sol_12v.release()
            self._solenoid.release()
            if JETSON_AVAILABLE:
                GPIO.output(RELAY_PUMP_PIN, GPIO.LOW)
                GPIO.cleanup()
        except Exception as e:
            print(f"[RelayController] Cleanup error: {e}")


# ============================================================================
# ACCUMULATOR MANAGER — ECO-2026-004
# Implements: HW-001 §8, SW-001 §2.4
#
# Charge-on-demand strategy for R385 micro-diaphragm pump + 0.75L Swess
# accumulator + GOODRIG 12V solenoid (MOSFET-gated).
#
# The R385 pump CANNOT deadhead (run continuously against closed valve).
# It has no built-in pressure switch and will overheat/burn out.
#
# Strategy (SW-001 §2.7):
#   1. ARM:   Pump until target_psi (or timed fallback) → pump OFF → hold pressure
#   2. FIRE:  Pulse solenoid MOSFET → pump stays OFF → accumulator provides pressure
#   3. TOPUP: Charge-per-shot (or every N shots / T sec) back to target_psi
#   4. DISARM: Everything OFF, solenoid closed, pump cold
# ============================================================================

class AccumulatorManager:
    """
    Manages the R385 pump + 0.75L Swess accumulator + GOODRIG solenoid.

    Contract (SW-001 §2.7):
      - Pump only charges (solenoid CLOSED) until TARGET_PSI
      - Shots are solenoid-only; pump OFF for the whole open pulse
      - Every shot waits for pressure ready, then recharges before return
      - Maintain loop (ARMED only) polls every PRESSURE_POLL_SEC, no hysteresis
      - Sensor fault while armed → disarm + alarm

    State machine: IDLE → CHARGING → ARMED → FIRING → ARMED → ...
    """

    # -- Configurable charge parameters (tunable via settings.json §2.11) ------
    TARGET_PSI = 15.0            # Closed-loop charge + maintain (field start)
    MAINTAIN_HYSTERESIS_PSI = 0.0  # No hysteresis — recharge if PSI < target
    PRESSURE_POLL_SEC = 60.0     # Maintain loop poll interval while ARMED
    INITIAL_CHARGE_SEC = 3.0     # Timed fallback when first arming (sensor absent)
    TOPUP_CHARGE_SEC = 1.0       # Timed fallback for top-up (sensor absent)
    TOPUP_INTERVAL_SHOTS = 10    # Legacy burst counter (pressure path always recharge-after-shot)
    MAX_PUMP_RUN_SEC = 8.0       # Absolute max pump run time (deadhead protection)
    DEFAULT_PULSE_SEC = 0.010    # Standard solenoid pulse (shared live + auto-cal)
    CHARGE_PER_SHOT = True       # Always recharge after shot when pressure-gated

    # States
    STATE_IDLE = "idle"
    STATE_CHARGING = "charging"
    STATE_ARMED = "armed"
    STATE_FIRING = "firing"

    def __init__(self, relay: RelayController, pressure=None, on_alarm=None):
        """
        Args:
            relay: RelayController instance (manages GPIO for pump + solenoid)
            pressure: optional PressureSensor for closed-loop charge-to-PSI
            on_alarm: optional callable(reason: str) for sensor-fault alarm
        """
        self._relay = relay
        self._pressure = pressure
        self._on_alarm = on_alarm
        self._state = self.STATE_IDLE
        self._shot_count = 0           # Shots since last charge/top-up
        self._total_shots = 0          # Total shots since arming
        self._armed = False
        self._last_charge_time = 0.0
        self._last_fire_time = 0.0
        self._arm_time = 0.0
        self._last_psi = None
        self._alarm = False
        self._alarm_reason = ""
        self._pressure_gated = False   # True once we successfully used live PSI
        self._lock = threading.Lock()
        self._maintain_thread = None
        print("[AccumulatorManager] Initialized (IDLE state)")

    def _read_psi(self):
        """Latest PSI from the pressure sensor, or None if unavailable."""
        if self._pressure is None:
            return None
        try:
            return self._pressure.read_psi()
        except Exception:
            return None

    def _pressure_connected(self) -> bool:
        if self._pressure is None:
            return False
        try:
            return bool(self._pressure.get_status().get("connected"))
        except Exception:
            return False

    def _charge(self, timed_fallback_sec: float, label: str) -> dict:
        """
        Charge the accumulator with solenoid CLOSED.

        Prefer closed-loop: pump until PSI >= TARGET_PSI (or MAX_PUMP_RUN_SEC).
        If the pressure sensor is disconnected, fall back to a timed burst.
        Always turns the pump OFF before returning.
        """
        self._relay.set_solenoid(False)
        time.sleep(0.05)

        timeout = min(max(timed_fallback_sec, 0.5), self.MAX_PUMP_RUN_SEC)
        psi_before = self._read_psi()
        use_pressure = self._pressure_connected() and psi_before is not None

        if use_pressure and psi_before >= self.TARGET_PSI:
            self._last_psi = psi_before
            print(f"[AccumulatorManager] {label}: already at {psi_before:.1f} PSI "
                  f"(target {self.TARGET_PSI:.1f}) — skip pump")
            return {
                "charge_sec": 0.0,
                "psi": round(psi_before, 1),
                "target_psi": self.TARGET_PSI,
                "charge_mode": "already_at_target",
                "reached_target": True,
            }

        mode = "pressure" if use_pressure else "timed"
        target_note = (f"to {self.TARGET_PSI:.1f} PSI (timeout {timeout:.1f}s)"
                       if use_pressure else f"for {timeout:.1f}s (no pressure sensor)")
        print(f"[AccumulatorManager] {label}: charging {target_note}...")

        start = time.time()
        reached = False
        psi = psi_before
        self._relay.set_pump(True)
        try:
            if use_pressure:
                while (time.time() - start) < timeout:
                    psi = self._read_psi()
                    if psi is not None and psi >= self.TARGET_PSI:
                        reached = True
                        break
                    time.sleep(0.05)
            else:
                time.sleep(timeout)
                reached = True  # timed path has no PSI criterion
        finally:
            self._relay.set_pump(False)

        time.sleep(0.1)  # brief settle before final reading
        psi = self._read_psi()
        if psi is not None:
            self._last_psi = psi
            if psi >= self.TARGET_PSI:
                reached = True

        elapsed = round(time.time() - start, 2)
        result = {
            "charge_sec": elapsed,
            "psi": round(psi, 1) if psi is not None else None,
            "target_psi": self.TARGET_PSI,
            "charge_mode": mode,
            "reached_target": bool(reached) if use_pressure else None,
        }
        psi_str = f"{psi:.1f} PSI" if psi is not None else "PSI n/a"
        print(f"[AccumulatorManager] {label}: done in {elapsed:.2f}s → {psi_str} "
              f"(mode={mode}, reached={result['reached_target']})")
        return result

    def arm(self) -> dict:
        """
        Charge the accumulator and enter the ARMED state.

        Sequence:
        1. Ensure solenoid is CLOSED (valve shut)
        2. Pump until TARGET_PSI (or timed fallback if no sensor)
        3. Turn pump OFF
        4. System is now passively holding pressure — ready to fire

        Returns:
            dict with arm status, charge duration, PSI, timestamp
        """
        with self._lock:
            if self._state == self.STATE_CHARGING:
                return {"status": "already_charging"}
            self._state = self.STATE_CHARGING

        result = {"status": "arming"}

        try:
            self.clear_alarm()
            # Prefer closed-loop to TARGET; timed fallback only if sensor absent
            charge_budget = (self.MAX_PUMP_RUN_SEC if self._pressure_connected()
                             else self.INITIAL_CHARGE_SEC)
            charge = self._charge(charge_budget, "⚡ ARMING")
            result.update(charge)

            if self._pressure_connected() and not charge.get("reached_target"):
                with self._lock:
                    self._state = self.STATE_IDLE
                    self._armed = False
                result["status"] = "pressure_not_ready"
                result["error"] = (f"Arm refused — PSI did not reach "
                                   f"{self.TARGET_PSI:.1f} within {charge_budget:.1f}s")
                print(f"[AccumulatorManager] ❌ ARM REFUSED: {result['error']}")
                return result

            with self._lock:
                self._state = self.STATE_ARMED
                self._armed = True
                self._shot_count = 0
                self._total_shots = 0
                self._last_charge_time = time.time()
                self._arm_time = time.time()
                if self._pressure_connected() and charge.get("psi") is not None:
                    self._pressure_gated = True

            # Keep MOSFET module 12V ON for the whole ARMED session — pulse SIG
            # only. Per-shot CH2 SSR cycling was killing clicks after ~3 fires.
            self._relay.set_module_power_hold(True)

            self._start_pressure_maintain()

            result["status"] = "armed"
            result["timestamp"] = time.strftime("%H:%M:%S")
            psi = result.get("psi")
            psi_note = f"{psi:.1f} PSI" if psi is not None else f"target {self.TARGET_PSI:.1f} PSI"
            print(f"[AccumulatorManager] ✅ ARMED — accumulator at {psi_note}, ready to fire")

        except Exception as e:
            self._relay.set_pump(False)
            self._relay.set_solenoid(False)
            with self._lock:
                self._state = self.STATE_IDLE
                self._armed = False
            result["status"] = "error"
            result["error"] = str(e)
            print(f"[AccumulatorManager] ❌ ARM ERROR: {e}")

        try:
            from activity_log import log_event
            log_event("ARM", status=result.get("status"), psi=result.get("psi"),
                      target=self.TARGET_PSI, reached=result.get("reached_target"))
        except Exception:
            pass
        return result

    def disarm(self, reason: str = "") -> dict:
        """
        Disarm the system: pump OFF, solenoid CLOSED, reset all state.

        Returns:
            dict with disarm status and shot statistics
        """
        self._relay.set_pump(False)
        # Drop ARMED-session CH2 hold, then full safe idle (no PR.05 remap)
        try:
            self._relay.set_module_power_hold(False)
            self._relay.recover_solenoid(re_pinmux=False)
        except Exception as e:
            print(f"[AccumulatorManager] recover_solenoid: {e}")
            try:
                self._relay.set_solenoid(False)
            except Exception:
                pass

        with self._lock:
            total = self._total_shots
            self._state = self.STATE_IDLE
            self._armed = False
            self._shot_count = 0
            self._total_shots = 0
            self._pressure_gated = False

        note = f" ({reason})" if reason else ""
        print(f"[AccumulatorManager] 🔒 DISARMED{note} — total shots fired: {total}")
        try:
            from activity_log import log_event
            log_event("DISARM", reason=reason or "operator", total_shots=total)
        except Exception:
            pass
        return {
            "status": "disarmed",
            "total_shots_fired": total,
            "reason": reason or None,
            "timestamp": time.strftime("%H:%M:%S")
        }

    def clear_alarm(self):
        """Clear sticky sensor-fault alarm (operator acknowledge)."""
        with self._lock:
            self._alarm = False
            self._alarm_reason = ""

    def _fail_sensor(self, reason: str) -> dict:
        """Disarm + alarm on pressure sensor fault (SW-001 §2.7)."""
        print(f"[AccumulatorManager] 🚨 SENSOR FAULT: {reason}")
        with self._lock:
            self._alarm = True
            self._alarm_reason = reason
        result = self.disarm(reason=f"sensor_fault: {reason}")
        result["status"] = "sensor_fault"
        result["alarm"] = True
        result["error"] = reason
        if self._on_alarm:
            try:
                self._on_alarm(reason)
            except Exception as e:
                print(f"[AccumulatorManager] alarm callback error: {e}")
        return result

    def _ensure_pressure_ready(self, label: str = "ready") -> dict:
        """
        Block until PSI >= TARGET_PSI (charge if needed).
        Returns {"ok": True, ...} or {"ok": False, "status": ..., "error": ...}.
        """
        if not self._pressure_connected():
            if self._pressure_gated:
                return self._fail_sensor("pressure sensor disconnected")
            # Bench/stub: timed charge once, then treat as ready
            charge = self._charge(self.INITIAL_CHARGE_SEC, f"⚡ {label} (timed)")
            return {"ok": True, "charge": charge, "mode": "timed"}

        psi = self._read_psi()
        if psi is None:
            if self._pressure_gated:
                return self._fail_sensor("pressure reading unavailable")
            charge = self._charge(self.INITIAL_CHARGE_SEC, f"⚡ {label} (timed)")
            return {"ok": True, "charge": charge, "mode": "timed"}

        self._pressure_gated = True
        if psi >= self.TARGET_PSI:
            self._last_psi = psi
            return {"ok": True, "psi": psi, "charge": None, "mode": "already_ready"}

        with self._lock:
            if self._state == self.STATE_CHARGING:
                return {"ok": False, "status": "charging",
                        "error": "Already charging"}
            self._state = self.STATE_CHARGING

        try:
            charge = self._charge(self.MAX_PUMP_RUN_SEC, f"⚡ {label}")
            reached = bool(charge.get("reached_target"))
            with self._lock:
                self._state = self.STATE_ARMED if self._armed else self.STATE_IDLE
                if reached:
                    self._shot_count = 0
                    self._last_charge_time = time.time()
            if not reached:
                return {
                    "ok": False,
                    "status": "pressure_not_ready",
                    "error": f"PSI did not reach {self.TARGET_PSI:.1f} within "
                             f"{self.MAX_PUMP_RUN_SEC:.1f}s",
                    "charge": charge,
                }
            return {"ok": True, "psi": charge.get("psi"), "charge": charge, "mode": "charged"}
        except Exception as e:
            self._relay.set_pump(False)
            with self._lock:
                self._state = self.STATE_ARMED if self._armed else self.STATE_IDLE
            return {"ok": False, "status": "error", "error": str(e)}

    def fire(self, duration_sec: float = None) -> dict:
        """
        Pressure-gated solenoid shot (SW-001 §2.7).

        1. Wait until PSI >= TARGET_PSI (pump if needed; solenoid closed)
        2. Ensure pump OFF — no overlap with valve open
        3. Solenoid pulse only (standard pulse by default)
        4. Recharge back to TARGET_PSI before returning (next shot waits)
        """
        if duration_sec is None:
            duration_sec = self.DEFAULT_PULSE_SEC

        with self._lock:
            if not self._armed:
                return {"status": "not_armed", "error": "System must be armed first"}
            if self._state == self.STATE_CHARGING:
                return {"status": "charging", "error": "Cannot fire while charging"}
            if self._state == self.STATE_FIRING:
                return {"status": "busy", "error": "Already firing"}

        duration_sec = max(0.001, min(duration_sec, 2.0))

        try:
            # Gate: charge to target BEFORE claiming FIRING (pump, valve closed)
            ready = self._ensure_pressure_ready("pre-shot")
            if not ready.get("ok"):
                return {
                    "status": ready.get("status", "pressure_not_ready"),
                    "error": ready.get("error", "Pressure not ready"),
                    "alarm": ready.get("alarm", False),
                    "charge": ready.get("charge"),
                }

            with self._lock:
                if not self._armed:
                    return {"status": "not_armed", "error": "Disarmed during pre-charge"}
                if self._state == self.STATE_FIRING:
                    return {"status": "busy", "error": "Already firing"}
                self._state = self.STATE_FIRING

            # Hard guarantee: pump OFF before valve opens (no overlap)
            self._relay.set_pump(False)
            time.sleep(0.02)

            psi_before = self._read_psi()
            if self._pressure_gated and (not self._pressure_connected() or psi_before is None):
                return self._fail_sensor("lost pressure before solenoid open")

            print(f"[AccumulatorManager] 🔫 FIRE! Solenoid-only pulse: "
                  f"{duration_sec*1000:.1f}ms (shot #{self._total_shots + 1}"
                  f"{f', {psi_before:.1f} PSI' if psi_before is not None else ''})")
            # Locked pulse — idle watchdog cannot cut CH2 mid-open
            pulse = self._relay.pulse_solenoid(duration_sec)

            with self._lock:
                self._shot_count += 1
                self._total_shots += 1
                self._last_fire_time = time.time()
                shot_num = self._total_shots
                self._state = self.STATE_ARMED

            psi_after = self._read_psi()
            try:
                from activity_log import log_event
                log_event(
                    "FIRE",
                    shot=shot_num,
                    pulse_ms=pulse.get("duration_ms"),
                    elapsed_ms=pulse.get("elapsed_ms"),
                    ch2_held=pulse.get("ch2_held"),
                    ch2_rb=pulse.get("ch2_readback"),
                    ch2_rb_after=pulse.get("ch2_readback_after"),
                    hardwired=pulse.get("module_12v_hardwired"),
                    psi_before=round(psi_before, 1) if psi_before is not None else None,
                    psi_after=round(psi_after, 1) if psi_after is not None else None,
                    target=self.TARGET_PSI,
                )
            except Exception:
                pass

            if self._pressure_gated and (not self._pressure_connected() or psi_after is None):
                fault = self._fail_sensor("lost pressure after shot")
                fault["shot_number"] = shot_num
                fault["psi_before"] = round(psi_before, 1) if psi_before is not None else None
                return fault

            # Post-shot: always restore target before next shot may proceed
            recharge = self._ensure_pressure_ready("post-shot")
            if not recharge.get("ok") and recharge.get("status") == "sensor_fault":
                recharge["shot_number"] = shot_num
                return recharge

            return {
                "status": "fired",
                "duration_ms": pulse.get("duration_ms", duration_sec * 1000),
                "elapsed_ms": pulse.get("elapsed_ms"),
                "shot_number": shot_num,
                "psi_before": round(psi_before, 1) if psi_before is not None else None,
                "psi_after": round(psi_after, 1) if psi_after is not None else None,
                "psi_ready": recharge.get("psi"),
                "recharge_ok": bool(recharge.get("ok")),
                "target_psi": self.TARGET_PSI,
                "pump_during_shot": False,
            }

        except Exception as e:
            self._relay.set_pump(False)
            self._relay.set_solenoid(False)
            with self._lock:
                self._state = self.STATE_ARMED if self._armed else self.STATE_IDLE
            print(f"[AccumulatorManager] ❌ FIRE ERROR: {e}")
            try:
                from activity_log import log_event
                log_event("FIRE_ERROR", error=str(e))
            except Exception:
                pass
            return {"status": "error", "error": str(e)}

    def fire_blocking(self, duration_sec: float = None) -> dict:
        """
        Same as fire() but runs in a background thread to not block Flask.
        Returns immediately with the shot queued.
        """
        if duration_sec is None:
            duration_sec = self.DEFAULT_PULSE_SEC

        with self._lock:
            if not self._armed:
                return {"status": "not_armed", "error": "System must be armed first"}

        def _do_fire():
            self.fire(duration_sec)

        threading.Thread(target=_do_fire, daemon=True, name="accum-fire").start()
        return {"status": "queued", "duration_ms": duration_sec * 1000}

    def _topup(self):
        """
        Recharge the accumulator to TARGET_PSI (or timed fallback).
        Solenoid stays closed during charging.
        """
        with self._lock:
            if self._state in (self.STATE_CHARGING, self.STATE_FIRING):
                return
            if not self._armed:
                return
            self._state = self.STATE_CHARGING
            after_shots = self._shot_count

        try:
            self._charge(self.MAX_PUMP_RUN_SEC if self._pressure_connected()
                         else self.TOPUP_CHARGE_SEC,
                         f"🔄 TOP-UP (after {after_shots} shots)")

            with self._lock:
                self._shot_count = 0
                self._last_charge_time = time.time()
                self._state = self.STATE_ARMED if self._armed else self.STATE_IDLE

            print("[AccumulatorManager] ✅ TOP-UP complete — pressure restored")

        except Exception as e:
            self._relay.set_pump(False)
            self._relay.set_solenoid(False)
            with self._lock:
                self._state = self.STATE_ARMED if self._armed else self.STATE_IDLE
            print(f"[AccumulatorManager] ❌ TOP-UP ERROR: {e}")

    def _start_pressure_maintain(self):
        """
        While ARMED only: every PRESSURE_POLL_SEC, recharge if PSI < TARGET
        (no hysteresis). Sensor loss → disarm + alarm.
        """
        def _maintain_loop():
            print(f"[AccumulatorManager] Pressure maintain ON — hold "
                  f"{self.TARGET_PSI:.1f} PSI, poll every {self.PRESSURE_POLL_SEC:.0f}s "
                  f"(hysteresis={self.MAINTAIN_HYSTERESIS_PSI:.1f})")
            while self._armed:
                # Sleep in small slices so disarm is responsive
                deadline = time.time() + max(1.0, float(self.PRESSURE_POLL_SEC))
                while self._armed and time.time() < deadline:
                    time.sleep(0.25)
                if not self._armed:
                    break
                with self._lock:
                    if self._state in (self.STATE_CHARGING, self.STATE_FIRING):
                        continue
                if not self._pressure_connected():
                    if self._pressure_gated:
                        self._fail_sensor("pressure sensor disconnected (maintain)")
                    break
                psi = self._read_psi()
                if psi is None:
                    if self._pressure_gated:
                        self._fail_sensor("pressure reading unavailable (maintain)")
                    break
                self._pressure_gated = True
                floor = self.TARGET_PSI - max(0.0, self.MAINTAIN_HYSTERESIS_PSI)
                if psi < floor:
                    print(f"[AccumulatorManager] 📉 PSI {psi:.1f} < {floor:.1f} — maintain recharge")
                    self._topup()
            print("[AccumulatorManager] Pressure maintain OFF")

        self._maintain_thread = threading.Thread(
            target=_maintain_loop, daemon=True, name="accum-pressure-maintain")
        self._maintain_thread.start()

    def get_status(self) -> dict:
        """Return comprehensive accumulator status for the API."""
        with self._lock:
            since_charge = time.time() - self._last_charge_time if self._last_charge_time else None
            since_fire = time.time() - self._last_fire_time if self._last_fire_time else None
            armed_duration = time.time() - self._arm_time if self._arm_time and self._armed else None

            psi = self._read_psi()
            if psi is not None:
                self._last_psi = psi

            return {
                "state": self._state,
                "armed": self._armed,
                "shot_count": self._shot_count,
                "total_shots": self._total_shots,
                "shots_until_topup": max(0, self.TOPUP_INTERVAL_SHOTS - self._shot_count),
                "since_charge_sec": round(since_charge, 1) if since_charge else None,
                "since_fire_sec": round(since_fire, 1) if since_fire else None,
                "armed_duration_sec": round(armed_duration, 1) if armed_duration else None,
                "psi": round(self._last_psi, 1) if self._last_psi is not None else None,
                "pressure_connected": self._pressure_connected(),
                "pressure_gated": self._pressure_gated,
                "alarm": self._alarm,
                "alarm_reason": self._alarm_reason or None,
                "config": {
                    "target_psi": self.TARGET_PSI,
                    "maintain_hysteresis_psi": self.MAINTAIN_HYSTERESIS_PSI,
                    "pressure_poll_sec": self.PRESSURE_POLL_SEC,
                    "initial_charge_sec": self.INITIAL_CHARGE_SEC,
                    "topup_charge_sec": self.TOPUP_CHARGE_SEC,
                    "topup_interval_shots": self.TOPUP_INTERVAL_SHOTS,
                    "default_pulse_ms": self.DEFAULT_PULSE_SEC * 1000,
                    "charge_per_shot": True,
                    "max_pump_run_sec": self.MAX_PUMP_RUN_SEC,
                }
            }

    def update_config(self, config: dict):
        """Update charge/fire configuration at runtime."""
        if "target_psi" in config:
            self.TARGET_PSI = max(1.0, min(float(config["target_psi"]), 40.0))
        if "maintain_hysteresis_psi" in config:
            # Allow 0 (no hysteresis) per SW-001 §2.7
            self.MAINTAIN_HYSTERESIS_PSI = max(0.0, min(float(config["maintain_hysteresis_psi"]), 10.0))
        if "pressure_poll_sec" in config:
            self.PRESSURE_POLL_SEC = max(5.0, min(float(config["pressure_poll_sec"]), 300.0))
        if "initial_charge_sec" in config:
            self.INITIAL_CHARGE_SEC = max(0.5, min(float(config["initial_charge_sec"]), 10.0))
        if "topup_charge_sec" in config:
            self.TOPUP_CHARGE_SEC = max(0.5, min(float(config["topup_charge_sec"]), 5.0))
        if "topup_interval_shots" in config:
            self.TOPUP_INTERVAL_SHOTS = max(1, min(int(config["topup_interval_shots"]), 50))
        if "default_pulse_ms" in config:
            self.DEFAULT_PULSE_SEC = max(0.001, min(float(config["default_pulse_ms"]) / 1000.0, 2.0))
        if "max_pump_run_sec" in config:
            self.MAX_PUMP_RUN_SEC = max(1.0, min(float(config["max_pump_run_sec"]), 30.0))
        if "charge_per_shot" in config:
            # Pressure-gated path always recharges after shot; keep flag True
            self.CHARGE_PER_SHOT = True
        print(f"[AccumulatorManager] Config updated: target={self.TARGET_PSI:.1f} PSI, "
              f"poll={self.PRESSURE_POLL_SEC:.0f}s, hyst={self.MAINTAIN_HYSTERESIS_PSI:.1f}, "
              f"pulse={self.DEFAULT_PULSE_SEC*1000:.1f}ms, max_pump={self.MAX_PUMP_RUN_SEC:.1f}s")

    def cleanup(self):
        """Emergency shutdown: everything OFF."""
        self._armed = False
        self._relay.set_pump(False)
        self._relay.set_solenoid(False)
        try:
            self._relay.recover_solenoid(re_pinmux=False)
        except Exception:
            pass
        print("[AccumulatorManager] Emergency cleanup — all OFF")


# ============================================================================
# PRIMING SYSTEM — Ensures water line is filled before firing
# ============================================================================

class PrimingSystem:
    """
    Manages water line priming to ensure water reaches the nozzle before
    the first shot.

    Features:
    - Pre-fire priming: Before any fire command, checks if primed.
      If not, aims nozzle straight down, pumps for configured duration,
      optionally auto-detects water flow via camera frame differencing.

    Timed pump keep-alive (old 5‑min pulse) is REMOVED — pressure maintain
    while ARMED is handled by AccumulatorManager (SW-001 §2.7).

    Settings (configurable via GUI):
    - prime_duration_ms: How long to pump for priming (default 3000ms)
    - auto_detect: Whether to use camera to confirm water flow
    """

    # Pitch angle that points the nozzle straight down
    PRIME_PITCH = 90.0  # Max downward pitch
    PRIME_YAW = 0.0     # Center yaw
    IDLE_REPRIME_SEC = 600.0  # Re-prime if no fire for this long

    def __init__(self, relay: RelayController):
        self._relay = relay
        self._lock = threading.Lock()

        # State
        self._primed = False
        self._priming_in_progress = False
        self._last_prime_time = 0.0
        self._last_fire_time = 0.0

        # Settings (defaults)
        self.prime_duration_ms = 3000      # 3 seconds default
        self.auto_detect = True            # Use camera to confirm

    def start_keepalive(self, gimbal=None):
        """Deprecated no-op — pressure maintain lives in AccumulatorManager."""
        print("[Priming] Timed keep-alive removed — use Accumulator Target PSI maintain")

    def stop_keepalive(self):
        """Deprecated no-op."""
        pass

    def needs_priming(self) -> bool:
        """Check if the system needs priming before firing."""
        with self._lock:
            if not self._primed:
                return True
            since_last = time.time() - self._last_fire_time
            if since_last > self.IDLE_REPRIME_SEC:
                self._primed = False
                return True
            return False

    def prime(self, gimbal=None, camera=None) -> dict:
        """
        Run the priming sequence:
        1. Aim nozzle straight down
        2. Pump for configured duration
        3. (Optional) Auto-detect water via camera
        4. Mark as primed

        Args:
            gimbal: ServoTurretController to aim the nozzle down
            camera: Sniper CameraStream for auto-detection (optional)

        Returns:
            dict with priming results
        """
        with self._lock:
            if self._priming_in_progress:
                return {"status": "already_priming"}
            self._priming_in_progress = True

        result = {"status": "priming", "duration_ms": self.prime_duration_ms}

        try:
            # Step 1: Aim straight down
            if gimbal:
                print(f"[Priming] Aiming nozzle down ({self.PRIME_PITCH}°, {self.PRIME_YAW}°)")
                # Save current position to restore later
                current_status = gimbal.get_status()
                restore_pitch = current_status.get("pitch", 0)
                restore_yaw = current_status.get("yaw", 0)

                gimbal.set_angles(self.PRIME_PITCH, self.PRIME_YAW)
                time.sleep(1.5)  # Let servo settle
                result["aimed_down"] = True

            # Step 2: Capture 'before' frame for auto-detection
            before_frame = None
            if self.auto_detect and camera:
                before_frame = camera.get_frame()
                if before_frame is not None:
                    before_frame = before_frame.copy()

            # Step 3: Pump for the configured duration
            duration_sec = self.prime_duration_ms / 1000.0
            print(f"[Priming] Pumping for {self.prime_duration_ms}ms...")
            self._relay.set_pump(True)
            time.sleep(duration_sec)
            self._relay.set_pump(False)
            result["pumped_sec"] = duration_sec

            # Step 4: Auto-detect water flow
            water_detected = False
            if self.auto_detect and camera and before_frame is not None:
                time.sleep(0.3)  # Brief settle
                after_frame = camera.get_frame()
                if after_frame is not None:
                    water_detected = self._detect_water_flow(before_frame, after_frame)
                    result["water_detected"] = water_detected

            if not self.auto_detect:
                water_detected = True  # Assume success without detection
                result["water_detected"] = "assumed"

            # Step 5: Restore gimbal position
            if gimbal:
                print(f"[Priming] Restoring gimbal to ({restore_pitch}°, {restore_yaw}°)")
                gimbal.set_angles(restore_pitch, restore_yaw)
                time.sleep(1.0)

            # Mark as primed
            with self._lock:
                self._primed = water_detected
                self._last_prime_time = time.time()
                self._last_fire_time = time.time()

            result["status"] = "primed" if water_detected else "prime_uncertain"
            result["timestamp"] = time.strftime("%H:%M:%S")
            print(f"[Priming] Complete: {'✅ Water detected' if water_detected else '⚠️ Uncertain'}")

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            print(f"[Priming] Error: {e}")
        finally:
            with self._lock:
                self._priming_in_progress = False

        return result

    def _detect_water_flow(self, before: 'np.ndarray', after: 'np.ndarray') -> bool:
        """
        Detect water flow by comparing before/after frames.
        Water exiting the nozzle creates a visible change in the camera feed.
        """
        try:
            import cv2
            import numpy as np

            before_gray = cv2.cvtColor(before, cv2.COLOR_BGR2GRAY)
            after_gray = cv2.cvtColor(after, cv2.COLOR_BGR2GRAY)

            before_gray = cv2.GaussianBlur(before_gray, (5, 5), 0)
            after_gray = cv2.GaussianBlur(after_gray, (5, 5), 0)

            diff = cv2.absdiff(before_gray, after_gray)
            _, thresh = cv2.threshold(diff, 20, 255, cv2.THRESH_BINARY)

            # Count changed pixels
            changed_pixels = cv2.countNonZero(thresh)
            total_pixels = thresh.shape[0] * thresh.shape[1]
            change_pct = changed_pixels / total_pixels * 100

            print(f"[Priming] Frame diff: {changed_pixels} pixels changed ({change_pct:.1f}%)")

            # If more than 0.5% of frame changed, water is flowing
            return change_pct > 0.5

        except Exception as e:
            print(f"[Priming] Detection error: {e}")
            return False

    def mark_fired(self):
        """Call this after every fire command to track last fire time."""
        with self._lock:
            self._last_fire_time = time.time()

    def get_status(self) -> dict:
        """Return priming status for the API."""
        with self._lock:
            since_prime = time.time() - self._last_prime_time if self._last_prime_time else None
            since_fire = time.time() - self._last_fire_time if self._last_fire_time else None
            return {
                "primed": self._primed,
                "priming_in_progress": self._priming_in_progress,
                "since_prime_sec": round(since_prime, 1) if since_prime else None,
                "since_fire_sec": round(since_fire, 1) if since_fire else None,
                "settings": {
                    "prime_duration_ms": self.prime_duration_ms,
                    "auto_detect": self.auto_detect,
                    "keepalive_enabled": False,  # removed; pressure maintain in AccumulatorManager
                }
            }

    def update_settings(self, settings: dict):
        """Update priming settings from the API."""
        if "prime_duration_ms" in settings:
            self.prime_duration_ms = max(500, min(int(settings["prime_duration_ms"]), 10000))
        if "auto_detect" in settings:
            self.auto_detect = bool(settings["auto_detect"])
        # keepalive_* keys ignored (deprecated)
        print(f"[Priming] Settings updated: {self.prime_duration_ms}ms prime, "
              f"auto_detect={self.auto_detect}")



# ============================================================================
# SOFTWARE ENDSTOPS (SAFE-001 §2, User Spec §4)
# Hardware mechanical limits are wider (±130° yaw, ±45° pitch), but software
# clamps to the values below to protect wiring through cable glands/service loops.
# ============================================================================
YAW_LIMIT = 80.0      # Max ±80° yaw (160° total sweep)
PITCH_LIMIT = 100.0    # Max ±100° pitch — wide enough for down-mount → forward

# Mount compensation: the camera/lidar/nozzle assembly points DOWN at pitch=0°
# due to the physical gimbal mount orientation (USB/UART ports = "front").
# Negative pitch = tilt toward forward/horizontal.
# PITCH_HOME tilts the payload so it faces FORWARD by default.
PITCH_HOME = 0.0       # degrees — neutral start. Use WASD to find forward-facing angle.
                       # Storm32 oscillates if commanded beyond its mechanical pitch limit.


class GimbalController:
    """
    Controls the Storm32 BGC board via Serial UART.

    Sends RC-override style commands to RC_PITCH and RC_YAW pins.
    Implements software endstops and the "Death Spiral" unwind prevention.

    HW-001 §3: Serial on /dev/ttyUSB0 / /dev/ttyACM0 @ 115200 baud.
    SAFE-001 §2: Yaw hard-limited to ±80°, Pitch to ±20° (software endstops).
    """

    # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    # CUSTOMIZE: Set to your actual serial port.
    # USB-to-Serial/Storm32 USB: /dev/ttyACM0 or /dev/ttyUSB0
    # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    SERIAL_PORT = "/dev/ttyACM0"
    BAUD_RATE = 115200

    # Storm32 serial command IDs (o323BGC protocol)
    CMD_SET_ANGLES = 0x11  # Set Camera Angles command

    def __init__(self):
        self._yaw = 0.0          # Current yaw angle (degrees)
        self._pitch = PITCH_HOME  # Current pitch angle — start at forward-facing home
        self._lock = threading.Lock()
        self._serial = None
        if SERIAL_AVAILABLE:
            import os
            import time as _t

            # Dynamic port detection: probe each port with GET_VERSION to find Storm32.
            # USB serial prioritized (ECO-2026-008: PWM/UART dead on Yahboom).
            # Retry loop: USB devices may not exist yet at boot — kernel needs
            # time to enumerate USB after power-on (~5-10s on Orin Nano).
            ports_to_try = ["/dev/ttyACM0", "/dev/ttyACM1", "/dev/ttyUSB0", "/dev/ttyTHS1", "/dev/ttyTHS0"]
            MAX_RETRIES = 10
            RETRY_DELAY = 1.0  # seconds between retries

            for attempt in range(1, MAX_RETRIES + 1):
                for p in ports_to_try:
                    try:
                        if not os.path.exists(p):
                            continue
                        candidate = serial.Serial(
                            port=p,
                            baudrate=self.BAUD_RATE,
                            timeout=0.5
                        )
                        # Probe: send GET_VERSION (cmd 0x01) and check for Storm32 response
                        candidate.reset_input_buffer()
                        candidate.write(bytes([0xFA, 0x00, 0x01, 0x00, 0x01]))
                        _t.sleep(0.5)
                        if candidate.in_waiting > 0:
                            resp = candidate.read(candidate.in_waiting)
                            if len(resp) >= 2 and resp[0] == 0xFB:
                                self._serial = candidate
                                self.SERIAL_PORT = p
                                print(f"[GimbalController] Storm32 detected on {p} (version probe OK, {len(resp)} bytes, attempt {attempt})")
                                break
                            else:
                                print(f"[GimbalController] {p}: unexpected response {resp.hex()[:20]}, skipping")
                                candidate.close()
                        else:
                            print(f"[GimbalController] {p}: no response to GET_VERSION probe, skipping")
                            candidate.close()
                    except Exception as e:
                        print(f"[GimbalController] Failed to probe {p}: {e}")

                if self._serial:
                    break  # Found the Storm32, stop retrying
                if attempt < MAX_RETRIES:
                    print(f"[GimbalController] No Storm32 found (attempt {attempt}/{MAX_RETRIES}), waiting {RETRY_DELAY}s for USB...")
                    _t.sleep(RETRY_DELAY)

            if not self._serial:
                print(f"[GimbalController] Serial FAILED on all ports after {MAX_RETRIES} attempts. Running in STUB mode.")
        else:
            print("[GimbalController] STUB MODE — no serial available.")

    def set_angles(self, pitch: float, yaw: float):
        """
        Command the gimbal to absolute pitch/yaw angles (in degrees).

        Applies software endstops before sending. Values are clamped, not rejected,
        so the gimbal always moves as close as possible to the requested position.

        Args:
            pitch: Target pitch angle (-20 to +20 degrees).
            yaw: Target yaw angle (-80 to +80 degrees).
        """
        with self._lock:
            # Clamp to software endstops (SAFE-001 §2)
            self._pitch = max(-PITCH_LIMIT, min(PITCH_LIMIT, pitch))
            self._yaw = max(-YAW_LIMIT, min(YAW_LIMIT, yaw))

            if self._serial and self._serial.is_open:
                self._send_storm32_command(self._pitch, self._yaw)
            else:
                print(f"[GimbalController] STUB: pitch={self._pitch:.1f}° yaw={self._yaw:.1f}°")

    def nudge(self, d_pitch: float = 0.0, d_yaw: float = 0.0):
        """
        Relative movement (for WASD manual control).
        Adds delta to current position and re-clamps.
        """
        self.set_angles(self._pitch + d_pitch, self._yaw + d_yaw)

    def center(self):
        """Return gimbal to home position (PITCH_HOME, 0).
        PITCH_HOME compensates for the downward-pointing mount so that
        'centered' means the camera/nozzle faces FORWARD."""
        self.set_angles(PITCH_HOME, 0.0)

    def _send_storm32_command(self, pitch_deg: float, yaw_deg: float):
        """
        Build and send a Storm32 o323BGC 'Set Camera Angles' packet.

        Packet format (o323BGC protocol, verified against ROS2 driver):
          Byte 0:       0xFA (start marker)
          Byte 1:       Data length (14 bytes)
          Byte 2:       Command ID (0x11 = CMD_SETANGLE)
          Bytes 3-6:    Pitch angle (float32, IEEE 754 little-endian, degrees)
          Bytes 7-10:   Roll angle (float32, always 0.0 for 2-axis)
          Bytes 11-14:  Yaw angle (float32, degrees)
          Bytes 15-16:  Flags (0x0000 = unlimited mode)
          Bytes 17-18:  CRC (2 bytes, board does not verify — set to 0x0000)
        """
        roll_deg = 0.0

        # Pack angles as float32 (4 bytes each) + 2-byte flags
        payload = struct.pack('<fffH',
                              pitch_deg,   # pitch (float32)
                              roll_deg,    # roll (float32, unused)
                              yaw_deg,     # yaw (float32)
                              0)           # flags (0 = unlimited)

        data_len = len(payload)  # 14 bytes (4+4+4+2)
        cmd_id = self.CMD_SET_ANGLES

        # Build full packet: header + payload + 2-byte CRC
        packet = bytes([0xFA, data_len, cmd_id]) + payload
        packet += bytes([0x00, 0x00])  # CRC — board does not check

        try:
            self._serial.write(packet)
            print(f"[GimbalController] Sent o323BGC packet: {packet.hex().upper()}")
        except Exception as e:
            print(f"[GimbalController] Serial write error: {e}")


    def get_status(self) -> dict:
        return {
            "pitch": round(self._pitch, 1),
            "yaw": round(self._yaw, 1),
            "pitch_home": PITCH_HOME,
            "connected": self._serial is not None and self._serial.is_open
        }

    def cleanup(self):
        """Center gimbal and close serial port."""
        print("[GimbalController] Centering gimbal and closing serial...")
        try:
            self.center()
            time.sleep(0.2)
            if self._serial and self._serial.is_open:
                self._serial.close()
        except Exception as e:
            print(f"[GimbalController] Cleanup error: {e}")


# ============================================================================
# SERVO TURRET CONTROLLER (PCA9685 + MG996R) — HW-001 §3 (planned)
# High-torque geared pan/tilt using MG996R metal-gear servos driven by
# a PCA9685 16-channel I2C PWM driver board.
#
# Replaces the Storm32 brushless gimbal for applications requiring
# mechanical holding torque (e.g., fighting water hose spring tension).
#
# I2C Bus 1 (c240000.i2c), PCA9685 at address 0x40.
# IMPORTANT: Yahboom carrier board has an onboard INA3221 power monitor
#   ALSO at 0x40 on Bus 1. This creates an address collision.
#   Solution: Write via 0x40 (both chips receive), verify via 0x71
#   (PCA9685 Sub Address 1 — only PCA9685 responds).
#   Software reset (General Call 0x06) required at startup to clear
#   stuck EXTCLK bit from previous address-collision writes.
# Wiring: PCA9685 SDA/SCL on Jetson IDC40P Pin 27/28 (Bus 1).
# Power: Dedicated 12V→5V 10A buck converter (isolated from Jetson 5V rail).
# ============================================================================

# PCA9685 servo channel assignments
SERVO_CH_YAW = 0     # Channel 0 = Pan (horizontal rotation)
SERVO_CH_PITCH = 1   # Channel 1 = Tilt (vertical rotation)

# MG996R servo pulse range (microseconds)
SERVO_MIN_PULSE = 500    # 0° position
SERVO_MAX_PULSE = 2500   # 180° position
SERVO_RANGE_DEG = 180.0  # Total mechanical range

# Servo endstops (degrees from center, where center = 90° servo = 0° turret)
SERVO_YAW_LIMIT = 80.0    # ±80° yaw (same as Storm32 for software compatibility)
SERVO_PITCH_LIMIT = 90.0  # ±90° pitch (full servo range)

# PCA9685 register map (NXP datasheet §7.3)
_PCA9685_MODE1     = 0x00
_PCA9685_PRESCALE  = 0xFE
_PCA9685_LED0_ON_L = 0x06  # Each channel is 4 registers: ON_L, ON_H, OFF_L, OFF_H


class ServoTurretController:
    """
    Controls a 2-axis geared pan/tilt turret via PCA9685 I2C servo driver.

    Uses smbus2 for direct I2C register access, bypassing Adafruit Blinka
    which maps to the wrong I2C bus on the Yahboom carrier board.

    Provides the SAME API as GimbalController so the rest of the system
    (app.py, dashboard, AI pipeline, tests) requires ZERO changes.

    Implements: SW-001 §2.2 (TurretAgent interface)
    Safety: SAFE-001 §2 (software endstops)

    Hardware:
        - PCA9685 on I2C Bus 1, address 0x40 (shared with INA3221)
        - Verify address: 0x71 (PCA9685 Sub Address 1, no collision)
        - Wiring: Jetson Pin 27 (SDA) / Pin 28 (SCL)
        - Channel 0: MG996R yaw servo (pan)
        - Channel 1: MG996R pitch servo (tilt)
        - Power: 12V→5V 10A buck converter (isolated from Jetson)
    """

    PCA9685_ADDRESS = 0x40   # Write address (INA3221 also here — collision)
    PCA9685_READ    = 0x71   # PCA9685 Sub Address 1 (read without INA3221)
    I2C_BUS = 1              # Bus 1 = c240000.i2c (Pin 27/28 on Yahboom)
    PWM_FREQ = 50            # 50 Hz standard servo frequency

    # Smooth interpolation parameters
    INTERP_RATE_HZ = 100     # PWM update rate for smooth motion
    INTERP_SPEED   = 120.0   # Max degrees/second travel speed
    INTERP_EPSILON = 0.15    # Degrees — close enough to stop interpolating

    def __init__(self):
        self._target_yaw = 0.0      # Where we WANT to be (set by API)
        self._target_pitch = PITCH_HOME
        self._current_yaw = 0.0     # Where we ARE (actual PWM output)
        self._current_pitch = PITCH_HOME
        self._yaw = 0.0             # Public state (matches target for API compat)
        self._pitch = PITCH_HOME
        self._lock = threading.Lock()
        self._bus = None
        self._interp_thread = None
        self._interp_stop = threading.Event()

        if I2C_AVAILABLE:
            try:
                self._bus = smbus2.SMBus(self.I2C_BUS)
                # Verify PCA9685 is present
                self._bus.read_byte_data(self.PCA9685_ADDRESS, _PCA9685_MODE1)

                # Initialize PCA9685
                self._init_pca9685()
                print(f"[ServoTurret] PCA9685 initialized on I2C bus {self.I2C_BUS}, "
                      f"address 0x{self.PCA9685_ADDRESS:02X} via smbus2")

                # Start smooth interpolation thread
                self._interp_thread = threading.Thread(
                    target=self._interpolation_loop, daemon=True,
                    name="servo-interp")
                self._interp_thread.start()

                # Center servos on startup (instant — no interpolation needed)
                self._set_servo_angle(SERVO_CH_YAW, 0.0)
                self._set_servo_angle(SERVO_CH_PITCH, PITCH_HOME)
                print(f"[ServoTurret] Centered. Smooth interpolation "
                      f"at {self.INTERP_RATE_HZ}Hz, {self.INTERP_SPEED}°/s")
            except Exception as e:
                print(f"[ServoTurret] PCA9685 init FAILED: {e}")
                print("[ServoTurret] Running in STUB mode.")
                self._bus = None
        else:
            print("[ServoTurret] STUB MODE — smbus2 not available.")

    def _interpolation_loop(self):
        """Background thread: smoothly moves servos toward target angles.

        Runs at INTERP_RATE_HZ, moving at most INTERP_SPEED degrees/second.
        Sleeps when current == target to avoid wasting CPU.
        """
        dt = 1.0 / self.INTERP_RATE_HZ
        max_step = self.INTERP_SPEED * dt  # Max degrees per tick

        while not self._interp_stop.is_set():
            with self._lock:
                ty, tp = self._target_yaw, self._target_pitch
                cy, cp = self._current_yaw, self._current_pitch

            dy = ty - cy
            dp = tp - cp

            # If already at target, sleep longer to save CPU
            if abs(dy) < self.INTERP_EPSILON and abs(dp) < self.INTERP_EPSILON:
                self._interp_stop.wait(timeout=0.05)
                continue

            # Move toward target, clamping step size for smooth motion
            if abs(dy) <= max_step:
                ny = ty
            else:
                ny = cy + max_step * (1 if dy > 0 else -1)

            if abs(dp) <= max_step:
                np_ = tp
            else:
                np_ = cp + max_step * (1 if dp > 0 else -1)

            # Write to hardware
            try:
                self._set_servo_angle(SERVO_CH_YAW, ny)
                self._set_servo_angle(SERVO_CH_PITCH, np_)
            except Exception:
                pass  # I2C errors handled silently in interpolation

            with self._lock:
                self._current_yaw = ny
                self._current_pitch = np_

            self._interp_stop.wait(timeout=dt)

    def _init_pca9685(self):
        """Initialize PCA9685: software reset, set 50Hz PWM, wake up.
        
        Uses dual-address pattern to handle INA3221 collision at 0x40:
        - Write via 0x40 (both PCA9685 and INA3221 receive)
        - Verify via 0x71 (PCA9685 Sub Address 1, no collision)
        
        Software reset clears EXTCLK bit that may be stuck from
        previous writes through the colliding address.
        """
        addr = self.PCA9685_ADDRESS
        read = self.PCA9685_READ

        # Software reset via General Call — clears stuck EXTCLK bit
        try:
            self._bus.write_byte(0x00, 0x06)
        except Exception:
            pass  # General call may NAK, that's OK
        time.sleep(0.05)

        # Sleep mode + enable sub-addresses for verification reads
        # MODE1: SLEEP=1, SUB1=1, SUB2=1, SUB3=1 = 0x1E
        self._bus.write_byte_data(addr, _PCA9685_MODE1, 0x1E)
        time.sleep(0.005)

        # Set prescaler for 50 Hz: prescale = round(25MHz / (4096 × freq)) - 1
        prescale = round(25000000.0 / (4096 * self.PWM_FREQ)) - 1
        self._bus.write_byte_data(addr, _PCA9685_PRESCALE, prescale)
        time.sleep(0.005)

        # Verify prescaler via sub-address (collision-free read)
        ps_verify = self._bus.read_byte_data(read, _PCA9685_PRESCALE)

        # Wake up: AI=1, SUB1=1, SUB2=1, SUB3=1 = 0x2E
        self._bus.write_byte_data(addr, _PCA9685_MODE1, 0x2E)
        time.sleep(0.005)

        # Verify EXTCLK is clear
        mode1 = self._bus.read_byte_data(read, _PCA9685_MODE1)
        extclk = (mode1 >> 6) & 1
        if extclk:
            print(f"[ServoTurret] WARNING: EXTCLK stuck! Power-cycle PCA9685.")

        print(f"[ServoTurret] PCA9685 prescaler={ps_verify} ({self.PWM_FREQ}Hz) "
              f"MODE1=0x{mode1:02X} EXTCLK={extclk}")

    def _set_pwm(self, channel: int, on: int, off: int):
        """Set raw PWM on/off ticks (0-4095) for a channel."""
        reg = _PCA9685_LED0_ON_L + 4 * channel
        self._bus.write_byte_data(self.PCA9685_ADDRESS, reg, on & 0xFF)
        self._bus.write_byte_data(self.PCA9685_ADDRESS, reg + 1, on >> 8)
        self._bus.write_byte_data(self.PCA9685_ADDRESS, reg + 2, off & 0xFF)
        self._bus.write_byte_data(self.PCA9685_ADDRESS, reg + 3, off >> 8)

    def _pulse_to_ticks(self, pulse_us: float) -> int:
        """Convert pulse width (microseconds) to PCA9685 tick count (0-4095).
        At 50Hz, one period = 20000μs, so 4096 ticks = 20000μs."""
        period_us = 1000000.0 / self.PWM_FREQ  # 20000μs at 50Hz
        return int(pulse_us / period_us * 4096)

    def _deg_to_pulse(self, angle_deg: float) -> float:
        """Convert turret angle (-90..+90) to servo pulse width (μs).
        Turret 0° = servo 90° = center pulse.
        Maps linearly across SERVO_MIN_PULSE..SERVO_MAX_PULSE."""
        servo_angle = max(0.0, min(180.0, angle_deg + 90.0))
        fraction = servo_angle / 180.0
        return SERVO_MIN_PULSE + fraction * (SERVO_MAX_PULSE - SERVO_MIN_PULSE)

    def _set_servo_angle(self, channel: int, turret_deg: float):
        """Set a servo channel to a turret angle (degrees from center)."""
        pulse_us = self._deg_to_pulse(turret_deg)
        ticks = self._pulse_to_ticks(pulse_us)
        self._set_pwm(channel, 0, ticks)

    def set_angles(self, pitch: float, yaw: float):
        """
        Command the turret to absolute pitch/yaw angles (in degrees).

        Sets the TARGET position — the interpolation thread smoothly moves
        the servos there at INTERP_SPEED degrees/second.

        Args:
            pitch: Target pitch angle (clamped to ±SERVO_PITCH_LIMIT).
            yaw: Target yaw angle (clamped to ±SERVO_YAW_LIMIT).
        """
        with self._lock:
            # Clamp to software endstops (SAFE-001 §2)
            self._pitch = max(-SERVO_PITCH_LIMIT, min(SERVO_PITCH_LIMIT, pitch))
            self._yaw = max(-SERVO_YAW_LIMIT, min(SERVO_YAW_LIMIT, yaw))
            self._target_yaw = self._yaw
            self._target_pitch = self._pitch

        if not self._bus:
            print(f"[ServoTurret] STUB: pitch={self._pitch:.1f}° yaw={self._yaw:.1f}°")

    def nudge(self, d_pitch: float = 0.0, d_yaw: float = 0.0):
        """
        Relative movement (for WASD manual control).
        Adds delta to current TARGET position and re-clamps.
        API-compatible with GimbalController.nudge().
        """
        with self._lock:
            new_pitch = self._target_pitch + d_pitch
            new_yaw = self._target_yaw + d_yaw
        self.set_angles(new_pitch, new_yaw)

    def center(self):
        """Return turret to home position (PITCH_HOME, 0).
        API-compatible with GimbalController.center()."""
        self.set_angles(PITCH_HOME, 0.0)

    def get_status(self) -> dict:
        with self._lock:
            return {
                "pitch": round(self._pitch, 1),
                "yaw": round(self._yaw, 1),
                "pitch_home": PITCH_HOME,
                "connected": self._bus is not None
            }

    def cleanup(self):
        """Stop interpolation thread, center turret, and close I2C bus."""
        print("[ServoTurret] Shutting down...")
        self._interp_stop.set()
        if self._interp_thread:
            self._interp_thread.join(timeout=1.0)
        try:
            if self._bus:
                # Direct center (no interpolation — thread is stopped)
                self._set_servo_angle(SERVO_CH_YAW, 0.0)
                self._set_servo_angle(SERVO_CH_PITCH, PITCH_HOME)
                time.sleep(0.3)
                self._bus.close()
        except Exception as e:
            print(f"[ServoTurret] Cleanup error: {e}")


def create_turret_controller():
    """
    Factory function: auto-detect available turret hardware.

    Priority:
      1. PCA9685 I2C servo driver on smbus2 Bus 1 (new geared turret)
      2. Storm32 BGC USB serial (legacy brushless gimbal)
      3. Stub mode (no hardware)

    Returns a controller with the standard API:
        set_angles(pitch, yaw), nudge(d_pitch, d_yaw),
        center(), get_status(), cleanup()
    """
    # Try PCA9685 first via smbus2 (proven on Yahboom carrier board)
    if I2C_AVAILABLE:
        # Yahboom carrier board has INA3221 power monitor at 0x40 — same as
        # PCA9685 default address. The kernel driver blocks userspace access.
        # Unbind it first so smbus2 can talk to the PCA9685.
        _unbind_ina3221()

        try:
            bus = smbus2.SMBus(1)  # Bus 1 = Pin 27/28 on Yahboom
            # Software reset to clear any stuck state
            try:
                bus.write_byte(0x00, 0x06)
            except Exception:
                pass
            time.sleep(0.05)
            # Enable sub-addresses so we can verify via 0x71
            bus.write_byte_data(0x40, _PCA9685_MODE1, 0x1F)
            time.sleep(0.01)
            # Verify PCA9685 via sub-address 0x71 (no INA3221 collision)
            prescale = bus.read_byte_data(0x71, _PCA9685_PRESCALE)
            bus.close()
            if prescale == 0x54:  # TI Manufacturer ID = INA3221 leaked
                print("[TurretFactory] 0x71 reads as INA3221 — no PCA9685")
            else:
                print(f"[TurretFactory] PCA9685 confirmed via sub-addr 0x71 "
                      f"(prescale=0x{prescale:02X}) — using ServoTurretController")
                return ServoTurretController()
        except Exception as e:
            print(f"[TurretFactory] PCA9685 probe failed: {e}")

    # Fall back to Storm32 BGC (legacy)
    print("[TurretFactory] Falling back to GimbalController (Storm32 BGC)")
    return GimbalController()


def _unbind_ina3221():
    """Unbind INA3221 kernel driver from I2C address 0x40 if present.
    The Yahboom carrier board has an INA3221 power monitor chip at 0x40
    which conflicts with the PCA9685 servo driver's default address."""
    import subprocess
    import os as _os
    driver_path = "/sys/bus/i2c/devices/1-0040/driver"
    if not _os.path.exists(driver_path):
        return  # No driver bound — 0x40 is free

    try:
        driver_name = _os.readlink(driver_path).split("/")[-1]
        print(f"[TurretFactory] Kernel driver '{driver_name}' is claiming 0x40 — unbinding...")
        result = subprocess.run(
            ["sudo", "-n", "sh", "-c", f"echo 1-0040 > /sys/bus/i2c/drivers/{driver_name}/unbind"],
            capture_output=True, timeout=5
        )
        if result.returncode == 0:
            print("[TurretFactory] INA3221 unbound successfully — 0x40 is now free")
        else:
            # Try with password via stdin as fallback
            result = subprocess.run(
                ["sudo", "-S", "sh", "-c", f"echo 1-0040 > /sys/bus/i2c/drivers/{driver_name}/unbind"],
                input=b"yahboom\n", capture_output=True, timeout=5
            )
            if result.returncode == 0:
                print("[TurretFactory] INA3221 unbound (via password) — 0x40 is now free")
            else:
                print(f"[TurretFactory] WARNING: Could not unbind {driver_name} from 0x40")
                print(f"[TurretFactory] Run manually: sudo sh -c 'echo 1-0040 > /sys/bus/i2c/drivers/{driver_name}/unbind'")
    except Exception as e:
        print(f"[TurretFactory] INA3221 unbind error: {e}")


# ============================================================================
# TF-LUNA LiDAR (I2C) — HW-001 §6, SW-001 §2.5
# Benewake TF-Luna: I2C Bus 1, default address 0x10
# Reads distance in cm, converts to meters.
# Mounted co-axial with Sniper camera on gimbal payload plate.
# ============================================================================

LIDAR_I2C_BUS = 7  # Yahboom 40-pin header Pin 3/5 = Bus 7 (c250000.i2c)
LIDAR_I2C_ADDR = 0x10
LIDAR_REG_DIST_LO = 0x00   # Distance low byte
LIDAR_REG_DIST_HI = 0x01   # Distance high byte
LIDAR_REG_AMP_LO = 0x02    # Signal amplitude (strength) low
LIDAR_REG_AMP_HI = 0x03    # Signal amplitude (strength) high


class LiDARController:
    """
    I2C driver for the Benewake TF-Luna LiDAR.

    HW-001 §6: I2C Bus 1, address 0x10, Jetson Pins 3 (SDA) & 5 (SCL).
    SW-001 §2.5: Background polling at ~100Hz, exposes read_distance().

    The TF-Luna returns distance in centimeters. We convert to meters.
    Signal strength (amplitude) is also captured for quality filtering.
    """

    def __init__(self):
        self._distance_cm = 0       # Raw distance in cm
        self._distance_m = 0.0      # Converted to meters
        self._signal_strength = 0   # Amplitude (higher = better signal)
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._bus = None

        if I2C_AVAILABLE:
            try:
                self._bus = smbus2.SMBus(LIDAR_I2C_BUS)
                # Test read to verify device is present
                self._bus.read_byte_data(LIDAR_I2C_ADDR, LIDAR_REG_DIST_LO)
                print(f"[LiDARController] TF-Luna found on I2C bus {LIDAR_I2C_BUS}, addr 0x{LIDAR_I2C_ADDR:02X}")
            except Exception as e:
                print(f"[LiDARController] I2C FAILED: {e}. Running in STUB mode.")
                self._bus = None
        else:
            print("[LiDARController] STUB MODE — smbus2 not available.")

        # Start background polling
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def _poll_loop(self):
        """Background thread: continuously reads LiDAR distance."""
        while self._running:
            if self._bus is not None:
                try:
                    # Read 4 bytes: dist_lo, dist_hi, amp_lo, amp_hi
                    data = self._bus.read_i2c_block_data(
                        LIDAR_I2C_ADDR, LIDAR_REG_DIST_LO, 4
                    )
                    dist_cm = data[0] | (data[1] << 8)
                    amplitude = data[2] | (data[3] << 8)

                    with self._lock:
                        self._distance_cm = dist_cm
                        self._distance_m = dist_cm / 100.0
                        self._signal_strength = amplitude
                except Exception:
                    pass  # Transient I2C errors are normal, skip
            else:
                # STUB: simulate a distance for dev testing
                import random
                with self._lock:
                    self._distance_cm = random.randint(150, 350)  # 1.5m - 3.5m
                    self._distance_m = self._distance_cm / 100.0
                    self._signal_strength = random.randint(500, 2000)

            time.sleep(0.01)  # ~100Hz polling

    def read_distance(self) -> float:
        """Return the latest LiDAR distance reading in meters."""
        with self._lock:
            return self._distance_m

    def get_status(self) -> dict:
        """Return full LiDAR telemetry as a dict."""
        with self._lock:
            return {
                "distance_m": round(self._distance_m, 2),
                "distance_cm": self._distance_cm,
                "signal_strength": self._signal_strength,
                "connected": self._bus is not None
            }

    def cleanup(self):
        """Stop polling and close I2C bus."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        if self._bus:
            try:
                self._bus.close()
            except Exception:
                pass
        print("[LiDARController] Stopped.")


# ============================================================================
# ADS1115 PRESSURE SENSOR (I2C) — HW-001 §7.1, SW-001 §2.9
# ECO-004 pressure loop: AUTEX 0-100 PSI transducer -> 10k/22k divider -> A0.
# See diagrams/eco004_ads1115_pressure.drawio.
#
# BUS: Must use Bus 1 (c240000.i2c, Pin 27/28) — NOT the LiDAR's Bus 7. Per the
# ECO-2026-009 DTB investigation, header Pin 3/5 map to I2C Gen8 (c250000.i2c),
# which is DISABLED in the Yahboom device tree. Bus 1 is the only enabled header
# bus and already hosts the PCA9685 servo driver + INA3221 (both 0x40). The
# ADS1115 sits at 0x48 -> unique address, no conflict (I2C is multi-drop).
# ============================================================================

PRESSURE_I2C_BUS = 1               # Bus 1 (c240000.i2c, Pin 27/28) — only enabled header bus
PRESSURE_ADS1115_ADDR = 0x48       # ADDR pin tied to GND (unique vs PCA9685/INA3221 @ 0x40)
ADS1115_REG_CONVERSION = 0x00
ADS1115_REG_CONFIG = 0x01
# Config: OS=1 (start), MUX=100 (A0 single-ended), PGA=001 (+/-4.096V),
# MODE=1 (single-shot), DR=100 (128 SPS), COMP_QUE=11 (disabled) -> 0xC383.
ADS1115_CONFIG_A0_SINGLE = 0xC383
ADS1115_FSR_VOLTS = 4.096          # Full-scale range for PGA=001
ADS1115_CONV_DELAY_SEC = 0.010     # ~8ms at 128 SPS + margin

# Voltage divider on transducer SIG -> A0 (keeps 4.5V max under the 3.3V rail).
# 10k/22k: ratio 0.6875 -> 4.5V maps to ~3.09V (headroom under 3.3V VDD). If you
# change the physical resistors, update these so the PSI math stays accurate.
PRESSURE_DIVIDER_R1 = 10000.0      # Series resistor from SIG to tap node (ohms)
PRESSURE_DIVIDER_R2 = 22000.0      # Tap node to GND (ohms)
# AUTEX transducer transfer function (ratiometric 5V part).
PRESSURE_V_AT_0PSI = 0.5           # Sensor output volts at 0 PSI
PRESSURE_V_AT_FULL = 4.5           # Sensor output volts at full scale
PRESSURE_FULL_PSI = 100.0          # Full-scale pressure


class PressureSensor:
    """
    I2C driver for the accumulator pressure transducer via an ADS1115 ADC.

    HW-001 §7.1: ADS1115 @ 0x48 on the shared LiDAR I2C bus, single-ended A0.
    SW-001 §2.9: background sampling at ~5Hz, exposes read_psi()/get_status().

    Conversion chain (single-shot, PGA +/-4.096V):
        Vtap = raw * 4.096 / 32768
        Vsig = Vtap * (R1 + R2) / R2          # undo the 10k/22k divider
        PSI  = ((Vsig - 0.5) / 4.0) * 100     # AUTEX 0.5-4.5V -> 0-100 PSI

    No-mock rule (project policy): if the ADS1115 or smbus2 is unavailable the
    sensor reports connected=False and psi=None. It NEVER fabricates readings.
    """

    def __init__(self):
        self._psi = None
        self._volts = None          # Reconstructed transducer volts (pre-divider)
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._bus = None

        if I2C_AVAILABLE:
            try:
                self._bus = smbus2.SMBus(PRESSURE_I2C_BUS)
                # Verify the ADS1115 acknowledges on the bus
                self._bus.read_i2c_block_data(PRESSURE_ADS1115_ADDR, ADS1115_REG_CONFIG, 2)
                print(f"[PressureSensor] ADS1115 found on I2C bus {PRESSURE_I2C_BUS}, "
                      f"addr 0x{PRESSURE_ADS1115_ADDR:02X}")
            except Exception as e:
                print(f"[PressureSensor] ADS1115 not detected ({e}). "
                      f"Reporting disconnected (no synthetic data).")
                self._bus = None
        else:
            print("[PressureSensor] smbus2 unavailable — reporting disconnected (no synthetic data).")

        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True,
                                        name="pressure-poll")
        self._thread.start()

    def _read_raw_a0(self) -> int:
        """Trigger a single-shot A0 conversion and return the signed 16-bit count."""
        cfg = [(ADS1115_CONFIG_A0_SINGLE >> 8) & 0xFF, ADS1115_CONFIG_A0_SINGLE & 0xFF]
        self._bus.write_i2c_block_data(PRESSURE_ADS1115_ADDR, ADS1115_REG_CONFIG, cfg)
        time.sleep(ADS1115_CONV_DELAY_SEC)
        data = self._bus.read_i2c_block_data(PRESSURE_ADS1115_ADDR, ADS1115_REG_CONVERSION, 2)
        raw = (data[0] << 8) | data[1]
        if raw > 0x7FFF:
            raw -= 0x10000
        return raw

    @staticmethod
    def _counts_to_psi(raw: int) -> tuple:
        """Convert a signed ADC count to (psi, transducer_volts)."""
        v_tap = raw * ADS1115_FSR_VOLTS / 32768.0
        v_sig = v_tap * (PRESSURE_DIVIDER_R1 + PRESSURE_DIVIDER_R2) / PRESSURE_DIVIDER_R2
        span_v = PRESSURE_V_AT_FULL - PRESSURE_V_AT_0PSI
        psi = ((v_sig - PRESSURE_V_AT_0PSI) / span_v) * PRESSURE_FULL_PSI
        psi = max(0.0, min(psi, PRESSURE_FULL_PSI))
        return psi, v_sig

    def _poll_loop(self):
        """Background thread: sample A0 at ~5Hz. Skips when no ADC is present."""
        while self._running:
            if self._bus is not None:
                try:
                    raw = self._read_raw_a0()
                    psi, v_sig = self._counts_to_psi(raw)
                    with self._lock:
                        self._psi = psi
                        self._volts = v_sig
                except Exception:
                    pass  # Transient I2C errors are normal; keep last good value
            time.sleep(0.2)  # ~5Hz

    def read_psi(self):
        """Return the latest pressure in PSI (float), or None if disconnected."""
        with self._lock:
            return self._psi

    def get_status(self) -> dict:
        """Return pressure telemetry as a dict."""
        with self._lock:
            return {
                "psi": round(self._psi, 1) if self._psi is not None else None,
                "volts": round(self._volts, 3) if self._volts is not None else None,
                "connected": self._bus is not None,
            }

    def cleanup(self):
        """Stop polling and close I2C bus."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        if self._bus:
            try:
                self._bus.close()
            except Exception:
                pass
        print("[PressureSensor] Stopped.")


# ============================================================================
# BALLISTIC OFFSET ENGINE — SW-001 §2.6, §4
#
# The turret is mounted OVERHEAD (8-10 feet / 2.4-3.0m above ground).
# It fires DOWNWARD. Gravity ASSISTS the shot — the water stream falls
# toward the target zone, so the pitch correction is small and negative.
#
# The LiDAR measures the "slant distance" to the background surface
# behind the target. We use this to compute how much the water stream
# will drop over that distance and adjust pitch accordingly.
# ============================================================================

# Ballistic constants — tune after field testing at the hunt setpoint PSI.
# Full parabolic gravity is NOT used yet; drop is a linear heuristic (§2.6.3).
# Exit velocity scales roughly with √(PSI); REF is the factory hunt setpoint.
WATER_EXIT_VELOCITY = 7.0   # m/s estimate at REF_EXIT_PSI (tune with trajectory stills)
REF_EXIT_PSI = 15.0
GRAVITY = 9.81               # m/s² (reserved; linear drop heuristic below)


def exit_velocity_for_psi(psi: float | None) -> float:
    """Scale nominal exit velocity with √(psi/REF)."""
    if psi is None or psi <= 0:
        return WATER_EXIT_VELOCITY
    return WATER_EXIT_VELOCITY * math.sqrt(float(psi) / REF_EXIT_PSI)


def compute_ballistic_offset(pitch_deg: float, yaw_deg: float,
                               distance_m: float) -> tuple:
    """
    Apply linear drop correction for the OVERHEAD-mounted inverted turret.
    Since it fires downward, gravity accelerates the water. For distances > 3m,
    we apply a slight negative pitch offset (aiming closer to the horizon)
    to compensate for the drop.
    """
    if distance_m < 0.3 or distance_m > 8.0:
        return pitch_deg, yaw_deg, {
            "drop_offset_deg": 0.0,
            "distance_m": distance_m,
            "in_range": False
        }

    # Linear drop: dead-straight under 3m, then -0.5 deg per meter
    if distance_m <= 3.0:
        drop_offset_deg = 0.0
    else:
        drop_offset_deg = -0.5 * (distance_m - 3.0)

    corrected_pitch = pitch_deg + drop_offset_deg

    return corrected_pitch, yaw_deg, {
        "drop_offset_deg": round(drop_offset_deg, 2),
        "distance_m": round(distance_m, 2),
        "in_range": True
    }


# ============================================================================
# COORDINATE MATH
# ============================================================================

def pixel_to_angle(px: int, py: int,
                   frame_w: int = 1280, frame_h: int = 800,
                   fov_h: float = 110.0, fov_v: float = 75.0) -> tuple:
    """
    Convert a pixel coordinate (from a click on the video feed) to
    gimbal pitch/yaw angles in degrees.

    Maps the frame center to (0, 0) degrees. Pixels left of center
    produce negative yaw; pixels above center produce negative pitch.

    Args:
        px, py: Click coordinates in pixels.
        frame_w, frame_h: Resolution of the video feed.
        fov_h, fov_v: Field of view of the camera in degrees.

    Returns:
        (pitch_deg, yaw_deg) tuple.
    """
    # Normalize to [-0.5, +0.5] range
    norm_x = (px / frame_w) - 0.5   # -0.5=left, +0.5=right
    norm_y = (py / frame_h) - 0.5   # -0.5=top, +0.5=bottom

    yaw_deg = norm_x * fov_h         # Positive = right
    pitch_deg = norm_y * fov_v       # Positive = down (inverted gimbal geometry)

    return pitch_deg, yaw_deg


# ============================================================================
# PREDICTIVE LEAD ENGINE — SW-001 §2.7
#
# Three-stage pipeline executed for every fire decision:
#   1. pixel_to_angle()        → raw pitch/yaw
#   2. + velocity lead offsets → corrected for target movement during ToF
#   3. + linear drop           → final corrected pitch
#
# This function combines stages 2 and 3 (§2.7.2 + §2.7.3).
# ============================================================================

def compute_predictive_lead(raw_pitch: float, raw_yaw: float,
                            distance_m: float,
                            omega_pitch: float = 0.0,
                            omega_yaw: float = 0.0,
                            psi: float | None = None) -> tuple:
    """
    Apply velocity lead + Linear Drop Compensation to raw gimbal angles.

    Flight path (partial): assumes constant angular velocity (Scout/tracker ω)
    over Time-of-Flight — not full insect maneuver/acceleration prediction.

    Gravity (partial): linear drop heuristic over 3 m, NOT full parabolic
    integration of GRAVITY. Exit velocity scales with √(psi/REF) when psi given.

    Execution order:
      1. raw angles (input)
      2. + lead_pitch / lead_yaw  (velocity-corrected aim point)
      3. + drop_offset_deg        (compensate for stream gravity drop)
    """
    if distance_m < 0.3 or distance_m > 8.0:
        return raw_pitch, raw_yaw, {
            "in_range": False,
            "distance_m": distance_m,
            "tof_ms": 0.0,
            "lead_pitch_deg": 0.0,
            "lead_yaw_deg": 0.0,
            "drop_offset_deg": 0.0,
            "total_pitch_correction": 0.0,
            "total_yaw_correction": 0.0,
            "exit_velocity_m_s": WATER_EXIT_VELOCITY,
        }

    v0 = exit_velocity_for_psi(psi)
    alpha_rad = math.radians(raw_pitch)

    # --- Stage 2: Time-of-Flight Lead (§2.6.2) ---
    cos_alpha = math.cos(alpha_rad)
    if abs(cos_alpha) < 0.01:
        cos_alpha = 0.01  # Prevent division by zero
    tof = distance_m / (v0 * cos_alpha)  # seconds

    # Predict where target will be after ToF
    lead_pitch = omega_pitch * tof  # degrees
    lead_yaw = omega_yaw * tof      # degrees

    # Apply lead to raw angles
    led_pitch = raw_pitch + lead_pitch
    led_yaw = raw_yaw + lead_yaw

    # --- Stage 3: Linear Drop Compensation (heuristic, not full gravity) ---
    if distance_m <= 3.0:
        drop_offset_deg = 0.0
    else:
        drop_offset_deg = -0.5 * (distance_m - 3.0)

    final_pitch = led_pitch + drop_offset_deg
    final_yaw = led_yaw

    return final_pitch, final_yaw, {
        "in_range": True,
        "distance_m": round(distance_m, 2),
        "tof_ms": round(tof * 1000, 1),
        "lead_pitch_deg": round(lead_pitch, 3),
        "lead_yaw_deg": round(lead_yaw, 3),
        "drop_offset_deg": round(drop_offset_deg, 2),
        "total_pitch_correction": round(lead_pitch + drop_offset_deg, 3),
        "total_yaw_correction": round(lead_yaw, 3),
        "exit_velocity_m_s": round(v0, 2),
        "psi": psi,
    }


