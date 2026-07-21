#!/usr/bin/env python3
"""
Early boot: PADCTL push-pull + drive PR.05 (module SIG) LOW as soon as possible.

With Rev J Channel B jumpered, module 12V is always present. Orin boot firmware
drives PR.05 HIGH until userspace claims it — FETs heat. This script shortens the
userspace portion of that window. It cannot cover the firmware window before the
kernel; use a series MODULE 12V switch for full boot safety (HW-001 §5.5).

Releases the line before exit so app.py / RelayController can claim it.
"""
# Implements: HW-001 §5.5, SAFE-001 §1
from __future__ import annotations

import struct
import sys


def _pinmux() -> None:
    import mmap

    with open("/dev/mem", "r+b") as f:
        mem = mmap.mmap(f.fileno(), 0x10000, offset=0x02430000)
        for offset in (0x98, 0x90, 0xD030):  # PR.04, PR.05, PY.00
            mem[offset : offset + 4] = struct.pack("<I", 0x05)
        mem.close()


def main() -> int:
    try:
        _pinmux()
        print("[claim_sig_low] PADCTL 0x05 on PR.04/PR.05/PY.00", flush=True)
    except Exception as e:
        print(f"[claim_sig_low] PADCTL failed: {e}", flush=True)

    try:
        import gpiod
    except ImportError:
        print("[claim_sig_low] gpiod missing — skip line claim", flush=True)
        return 0

    line = None
    try:
        try:
            line = gpiod.find_line("PR.05")
        except Exception:
            line = None
        if line is None:
            line = gpiod.Chip("gpiochip0").get_line(113)
        line.request(
            consumer="boot-sig-safe",
            type=gpiod.LINE_REQ_DIR_OUT,
            default_vals=[0],
        )
        line.set_value(0)
        print("[claim_sig_low] PR.05 driven LOW (boot heat window shortened)", flush=True)
    except Exception as e:
        print(f"[claim_sig_low] PR.05 claim failed: {e}", flush=True)
        return 0
    finally:
        if line is not None:
            try:
                line.set_value(0)
                line.release()
            except Exception:
                pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
