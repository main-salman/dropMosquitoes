# SAFE-001: Safety Specification

**Status:** APPROVED  
**Version:** 1.1  
**Last Updated:** 2026-05-15  
**Owner:** Salman

## 1. Hardware Safety

| Hazard | Mitigation | Spec Reference |
|:-------|:-----------|:---------------|
| 12V back-EMF from pump | Monk Makes relay provides opto-isolation between Jetson 3.3V GPIO and 12V motor circuit | HW-001 §5 |
| Gimbal boot instability | Gimbal is directly powered via 2A fuse and boots independently of the Jetson. | HW-001 §5 |
| Solenoid MOSFET hot / stuck ON | **Rev M hardwired CH2 jumper:** module 12V always on → boot PR.05 HIGH heats FETs. Operator: series MODULE 12V switch OFF until dashboard up. Software: `claim_sig_low.py` + idle SIG watchdog. Long-term: buffer GPIO→IN B to restore gating. | HW-001 §5.5 |
| Ground loops & 5V clash | Direct USB-A to Mini-USB cable is strictly forbidden during live operation. Communication runs over isolated 3-wire UART (TX, RX, GND) with no 5V power wire. | HW-001 §3 |
| Water siphon on downward pitch | Feelers 1/4" spring check valve inline prevents gravity drain | HW-001 §6 |
| Dew/rain infiltration | IP67 enclosure + silicone-sealed cable glands + Park Mode | HW-001 §7 |
| Cable snap during rotation | 3" service loop + FPC strain relief anchors with zip ties | HW-001 §6 |

## 2. Software Safety

| Hazard | Mitigation | Spec Reference |
|:-------|:-----------|:---------------|
| Firing at large insects (moths) | Bounding box area threshold filter | SW-001 §3 |
| GPIO stuck HIGH on crash | `try/finally` on pump/solenoid paths; cleanup cuts SIG then CH2 | SW-001 §4 |
| MOSFET module powered while idle | Gated mode: CH2 OFF at idle. Hardwired mode: rely on SIG LOW watchdog; do not leave system powered unattended with water pressure if SIG LED stuck on | HW-001 §5.5 |
| Continuous 360° rotation | Yaw hard-limited to ±80°; pitch to ±20° (software endstops) | SW-001 §3 |

> **Note:** Human/pet detection interlock has been **intentionally removed**. The system fires water only — being sprayed is preferable to mosquito bites. YOLO classification is used solely for target identification, not as a fire inhibitor.

## 3. Operational Safety

- System must be powered via 12V DC brick only — no mains AC wiring inside enclosure
- All cable glands must be sealed with silicone adhesive before outdoor deployment
- Conformal coating (MG Chemicals 422B) on all exposed PCBs — NOT on lenses or Jetson fan *(add to BOM if not already purchased)*
- IR illuminators mounted to fixed post — NOT on gimbal (prevents weight/vibration issues)
- Reservoir must have a debris screen / mesh lid to prevent pump clogging

