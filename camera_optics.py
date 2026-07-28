# Implements: HW-001 §2 / SW-001 — Camera IR-cut optical profiles
"""
camera_optics.py — As-built Scout vs Sniper IR filter awareness.

parts.csv:
  - Scout  ("The New Scout"): Arducam NoIR IMX219 — NO IR-cut (permanent night-capable)
  - Sniper ("The Verifier"): Arducam IMX219 NoIR w/ Motorized IR-Cut Filter

Software does not drive the Sniper IR-cut actuator (board auto/LDR or unwired
control). This module records the optical roles so status/UI/hunt are accurate.
"""

from __future__ import annotations

from typing import Any


# Canonical as-built profiles (parts.csv + HW-001)
SCOUT_OPTICS = {
    "role": "scout",
    "part": "Arducam NoIR IMX219 8MP (The New Scout)",
    "sensor": "IMX219",
    "mip_port": 0,
    "ir_cut": "none",
    "ir_cut_control": "n/a",
    "daylight_look": "pink/magenta cast from solar IR (OK for MOG2 grayscale)",
    "night_with_850nm_ir": True,
    "note": "Permanent NoIR — no IR-cut filter. Always IR-sensitive.",
}

SNIPER_OPTICS = {
    "role": "sniper",
    "part": "Arducam IMX219 NoIR w/ Motorized IR-Cut (The Verifier)",
    "pcb": "UC-350 Rev.C",
    "sensor": "IMX219",
    "mip_port": 1,
    "ir_cut": "motorized",
    "ir_cut_control": "mode_a_ldr_auto",  # Chosen as-built 2026-07-28 — no Jetson wires
    "back_pads": "GND IR SCL SDA FSTROBE GP0 GND 3V3",
    "daylight_look": "true color when IR-cut IN; IR-pass when OUT",
    "night_with_850nm_ir": True,
    "software_drives_ircut": False,
    "ldr_present": True,
    "ldr_verified": True,
    "mode_b_deferred": "BCM 22 / T15 IR+GND umbilical — only if LDR later fails",
    "diagram": "diagrams/wire_13_sniper_ircut.drawio",
    "note": (
        "UC-350 Mode A: LDR auto day/night (verified working). "
        "IR-cut motor is local (IR+GND pads → white 2-pin). "
        "CSI→HDMI is video only. No GPIO IR-cut driver."
    ),
}


def get_camera_optics_status() -> dict[str, Any]:
    return {
        "scout": dict(SCOUT_OPTICS),
        "sniper": dict(SNIPER_OPTICS),
        "illuminator": "Univivi 850nm hardwired always-on (see /api/status ir)",
        "summary": (
            "Scout=permanent NoIR; Sniper=UC-350 Mode A LDR auto (verified); "
            "850nm IR on with system power."
        ),
    }
