# SYS-001: System Overview Specification

**Status:** APPROVED  
**Version:** 3.0  
**Last Updated:** 2026-05-15  
**Owner:** Salman

## 1. Purpose

The "Sniper Messy Mortar" is an autonomous, AI-driven mosquito sentry turret. It detects flying insects via a fixed wide-angle camera, classifies them with a gimbal-mounted sniper camera running YOLOv8 on TensorRT, and fires a 400ms high-pressure direct water stream sweep via the "Stream and Sweep" strategy — the pump fires while the gimbal sweeps along the target's predicted flight path, creating a moving wall of water.

## 2. System Architecture

An asyncio orchestrator (`main.py`) coordinates four modular agents on an NVIDIA Jetson Orin Nano SUPER:

| Agent | File | Role |
|:------|:-----|:-----|
| ScoutAgent | `scout_vision.py` | Motion detection via IMX219 NoIR (60FPS, FIXED to enclosure) |
| TurretAgent | `gimbal_controller.py` | Translates pixel coords → Storm32 pitch/yaw serial commands |
| SniperAgent | `sniper_vision.py` | YOLOv8 TensorRT classification (>80% confidence gate) |
| TriggerAgent | `weapon_system.py` | GPIO BCM 17 relay trigger (400ms Stream-and-Sweep) with safety interlocks |

Supporting modules:
| Module | File | Role |
|:-------|:-----|:-----|
| IR Controller | `ir_controller.py` | Dusk/dawn automated IR illuminator control |
| Calibration | `phantom_ping.py` | Interactive linear drop calibration tool |
| Telemetry | `main.py` | Structured JSONL engagement logging (`engagements.jsonl`) |

## 3. Physical Topology

- **Scout Camera (IMX219 NoIR):** FIXED to enclosure baseplate (does NOT move on gimbal)
- **Sniper Camera (IMX219 NoIR):** Mounted on INVERTED Storm32 gimbal payload (looks downward)
- **Orbit Nozzle:** Mounted on gimbal payload adjacent to sniper (fires downward)
- **12V Diaphragm Pump:** Surface-mounted on bracket above enclosure
- **IP67 Enclosure:** Inverted hanging dome. Houses Jetson, Wagos, Relay, CSI RX boards
- **Water Reservoir:** Located at ground level or on elevated shelf

## 4. References

- [HW-001: Hardware Specification](./HW-001-hardware-spec.md)
- [SW-001: Software Specification](./SW-001-software-spec.md)
- [SAFE-001: Safety Specification](./SAFE-001-safety-spec.md)
- [TEST-001: Test Plan](./TEST-001-test-plan.md)
- [Dataset Strategy](../DATASET_STRATEGY.md)
