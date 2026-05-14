# SYS-001: System Overview Specification

**Status:** APPROVED  
**Version:** 1.0  
**Last Updated:** 2026-05-14  
**Owner:** Salman

## 1. Purpose

The "Sniper Messy Mortar" is an autonomous, AI-driven mosquito sentry turret. It detects flying insects via a fixed wide-angle camera, classifies them with a gimbal-mounted sniper camera running YOLOv8 on TensorRT, and fires a 300ms water slug via a relay-triggered submersible pump.

## 2. System Architecture

Four asynchronous Python agents communicate via thread-safe queues on an NVIDIA Jetson Orin Nano SUPER:

| Agent | File | Role |
|:------|:-----|:-----|
| ScoutAgent | `scout_vision.py` | Motion detection via OV9281 (120FPS, FIXED to enclosure) |
| TurretAgent | `gimbal_control.py` | Translates pixel coords → Storm32 pitch/yaw serial commands |
| SniperAgent | `sniper_logic.py` | YOLOv8 TensorRT classification + parabolic intercept calc |
| TriggerAgent | `weapons_hot.py` | GPIO 18 relay trigger (300ms pulse) with safety interlocks |

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
