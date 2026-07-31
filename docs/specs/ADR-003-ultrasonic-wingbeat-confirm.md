# ADR-003: Ultrasonic / wingbeat confirm (LeSonar2 lessons)

**Date:** 2026-07-31  
**Status:** PROPOSED (software techniques adopted now; hardware optional later)  
**References:** [tornyol/lesonar2](https://github.com/tornyol/lesonar2) (AGPL-3.0),
[tornyol.com](https://tornyol.com/), Supercon 2024 talk (Toussaint)

---

## Context

Tornyol’s LeSonar2 is a 40 kHz ultrasonic **phased-array** sensor (380× TDK T3902
PDM mics, 32× piezos, Artix-7 A100T, FT601 USB3) claiming ~50 FPS, ≤8 m range,
~180×180° FOV, with **micro-Doppler wingbeat** signatures to tell mosquito vs
wasp/fly/bee. Dev kit ~$1100. Design files are open under **AGPL-3.0**.

Bug Sniper is a **fixed water turret** with Jetson vision (Scout MOG2 + Sniper
YOLO) and TF-Luna LiDAR. We want their *detection ideas*, not a second product
and **not** a copy of AGPL firmware into this PolyForm codebase.

---

## Decision

1. **Adopt the sensing *pipeline* pattern**, not the drone kill effector:
   `wide cue → range/angle localize → species/class confirm → engage`.
2. **Apply immediately (no new BOM):** LiDAR **engage range gate** (sonar
   “range bin” lesson) + keep multi-frame YOLO streak + binary insect fire.
3. **Optional later hardware:** LeSonar2 kit (or smaller DIY ultrasonic) as a
   **confirm** channel aimed with the turret — fire only if wingbeat looks
   mosquito-like. Host bridge written by us; do **not** vendor AGPL sources.
4. **Do not** replace Scout/Sniper with sonar as the sole sensor. Tornyol chose
   sonar because a 40 g drone can’t carry cameras; we already have Jetson CSI.

---

## Techniques to steal (mapped to Bug Sniper)

| LeSonar / talk idea | Bug Sniper application |
|---------------------|-------------------------|
| Active CF pulse + listen for echo | Future: 40 kHz TX when Sniper locked; FFT micro-Doppler on RX |
| Micro-Doppler wingbeat (~hundreds Hz modulation) | Confirm mosquito vs foliage/bee before solenoid |
| Receive beamforming (angle from array FFT) | We use **gimbal aim + Sniper FOV** instead of 380 mics |
| Range-resolved energyscape (2D slice at distance) | **LiDAR `min/max_engage_m`** — refuse fire outside kill cone |
| Narrow 5° beam for precise targeting | Narrower Sniper lens (optics parallel) |
| Multi-frame persistence | Already: `min_verify_frames` |
| Passive mode (listen only) | Optional ambient wingbeat mic near payload (short range) |
| Dark / IR-independent sensing | Sonar works in dark — complements night when IR wash fails |

---

## Cost reality

- **$1100 kit** ≠ “cheap HC-SR04.” BOM includes FPGA, USB3 bridge, 380 MEMS,
  fab/assembly. Early TX-only beamforming demos were ~$100; **maxed RX array**
  is the product.
- Cloning Gerbers yourself still means parts + PCB + FPGA tools + months of DSP.
- For Bug Sniper ROI: kit is justified **after** Step A–D (pixels + `insect.engine`)
  if vision FPs remain; not before.

---

## License constraint

LeSonar2 is **AGPL-3.0**. Do not copy `lesonar2_firmware` / `lesonar2_software`
into this repo. If we buy a kit, treat it as a USB device and write an original
host client under our license. Link out to their GitHub for study.

---

## Consequences

- Spec SW-001: `hunt.min_engage_m` / `hunt.max_engage_m` (LiDAR gate).
- Spec SW-001 § future: optional `wingbeat_confirm` interface (stub settings only
  until hardware exists).
- Next-steps HTML documents buy/DIY ladder and fusion order.
- Hunt loop rejects fire when LiDAR distance outside engage window (when reading).
