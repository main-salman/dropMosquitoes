# SAFE-001: Safety Specification

**Status:** APPROVED  
**Version:** 1.0  
**Last Updated:** 2026-05-14  
**Owner:** Salman

## 1. Hardware Safety

| Hazard | Mitigation | Spec Reference |
|:-------|:-----------|:---------------|
| 12V back-EMF from pump | Monk Makes relay provides opto-isolation between Jetson 3.3V GPIO and 12V motor circuit | HW-001 §5 |
| Gimbal boot instability | Relay CH2 holds gimbal power OFF for 15s until Jetson IMU init completes | HW-001 §5 |
| Water siphon on downward pitch | Feelers 1/4" spring check valve inline prevents gravity drain | HW-001 §6 |
| Dew/rain infiltration | IP67 enclosure + silicone-sealed cable glands + Park Mode | HW-001 §7 |
| Cable snap during rotation | 3" service loop + FPC strain relief anchors with zip ties | HW-001 §6 |

## 2. Software Safety

| Hazard | Mitigation | Spec Reference |
|:-------|:-----------|:---------------|
| Firing at humans/pets | `person`, `dog`, `cat` confidence > 0.45 → `is_safe_to_fire = False` | SW-001 §3 |
| Firing at large insects (moths) | Bounding box area threshold filter | SW-001 §3 |
| GPIO stuck HIGH on crash | `try/finally` block on every GPIO 18 access | SW-001 §3 |
| Continuous 360° rotation | Yaw hard-limited to ±130°; rapid unwind at 180° boundary | SW-001 §3 |
| Rain damage to optics | Raindrop sensor triggers "Park Mode" (aims lenses down) | HW-001 §7 |

## 3. Operational Safety

- System must be powered via 12V DC brick only — no mains AC wiring inside enclosure
- All cable glands must be sealed with silicone adhesive before outdoor deployment
- Conformal coating (MG Chemicals 422B) on all exposed PCBs — NOT on lenses or Jetson fan
- IR illuminators mounted to fixed post — NOT on gimbal (prevents weight/vibration issues)
