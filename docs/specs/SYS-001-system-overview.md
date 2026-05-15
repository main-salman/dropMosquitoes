# SYS-001: System Overview Specification

**Status:** APPROVED  
**Version:** 2.0  
**Last Updated:** 2026-05-15  
**Owner:** Salman

## 1. Purpose

The "Sniper Messy Mortar" is an autonomous, AI-driven mosquito sentry turret. It detects flying insects via a fixed wide-angle camera, classifies them with a gimbal-mounted sniper camera running YOLOv8 on TensorRT, and fires a 600ms high-pressure mist cloud via the "Gravity Airburst" strategy — intentionally over-aiming to create a wide area-of-effect rain cloud above the target.

## 2. System Architecture

An asyncio orchestrator (`main.py`) coordinates four modular agents on an NVIDIA Jetson Orin Nano SUPER:

| Agent | File | Role |
|:------|:-----|:-----|
| ScoutAgent | `scout_vision.py` | Motion detection via OV9281 (120FPS, FIXED to enclosure) |
| TurretAgent | `gimbal_controller.py` | Translates pixel coords → Storm32 pitch/yaw serial commands |
| SniperAgent | `sniper_vision.py` | YOLOv8 TensorRT classification (>80% confidence gate) |
| TriggerAgent | `weapon_system.py` | GPIO BCM 17 relay trigger (600ms Airburst pulse) with safety interlocks |

Supporting modules:
| Module | File | Role |
|:-------|:-----|:-----|
| IR Controller | `ir_controller.py` | Dusk/dawn automated IR illuminator control |
| Calibration | `phantom_ping.py` | Interactive airburst offset calibration tool |
| Telemetry | `main.py` | Structured JSONL engagement logging (`engagements.jsonl`) |

## 3. Physical Topology

- **Scout Camera (OV9281):** FIXED to enclosure lid — does NOT move
- **Sniper Camera (IMX219 NoIR):** Mounted on Storm32 gimbal payload — MOVES
- **Orbit Nozzle:** Mounted on gimbal payload adjacent to sniper — MOVES
- **IP67 Enclosure:** Houses Jetson, Wagos, Relay, CSI TX boards
- **Water Reservoir:** Shallow tote at base with submerged pump

## 4. References

- [HW-001: Hardware Specification](./HW-001-hardware-spec.md)
- [SW-001: Software Specification](./SW-001-software-spec.md)
- [SAFE-001: Safety Specification](./SAFE-001-safety-spec.md)
- [TEST-001: Test Plan](./TEST-001-test-plan.md)
- [Dataset Strategy](../DATASET_STRATEGY.md)
