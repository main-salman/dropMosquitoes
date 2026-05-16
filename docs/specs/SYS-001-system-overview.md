# SYS-001: System Overview Specification

**Status:** APPROVED  
**Version:** 3.0  
**Last Updated:** 2026-05-15  
**Owner:** Salman

## 1. Purpose

The "Sniper Messy Mortar" is an autonomous, AI-driven mosquito sentry turret. It detects flying insects via a fixed wide-angle camera, classifies them with a gimbal-mounted sniper camera running YOLOv8 on TensorRT, and fires a 400ms high-pressure mist sweep via the "Stream and Sweep" strategy — the pump fires while the gimbal sweeps along the target's predicted flight path, creating a moving wall of water.

## 2. System Architecture

An asyncio orchestrator (`main.py`) coordinates four modular agents on an NVIDIA Jetson Orin Nano SUPER:

| Agent | File | Role |
|:------|:-----|:-----|
| ScoutAgent | `scout_vision.py` | Motion detection via OV9281 (120FPS, FIXED to enclosure) |
| TurretAgent | `gimbal_controller.py` | Translates pixel coords → Storm32 pitch/yaw serial commands |
| SniperAgent | `sniper_vision.py` | YOLOv8 TensorRT classification (>80% confidence gate) |
| TriggerAgent | `weapon_system.py` | GPIO BCM 17 relay trigger (400ms Stream-and-Sweep) with safety interlocks |

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
- **12V Diaphragm Pump:** Surface-mounted on bracket adjacent to enclosure (NOT submerged)
- **IP67 Enclosure:** Houses Jetson, Wagos, Relay, CSI TX boards
- **Water Reservoir:** Shallow tote at base with intake tube (pump self-primes)

## 4. References

- [HW-001: Hardware Specification](./HW-001-hardware-spec.md)
- [SW-001: Software Specification](./SW-001-software-spec.md)
- [SAFE-001: Safety Specification](./SAFE-001-safety-spec.md)
- [TEST-001: Test Plan](./TEST-001-test-plan.md)
- [Dataset Strategy](../DATASET_STRATEGY.md)
