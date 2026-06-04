# ADR-002: Migration from Storm32 Brushless Gimbal to Geared Servo Turret

**Date:** 2026-06-04  
**Status:** ACCEPTED  
**Supersedes:** Original Storm32 BGC gimbal architecture (HW-001 §3, SW-001 §2.2)

---

## Context and Problem Statement

The system's turret — responsible for aiming the camera, LiDAR, and water nozzle at
detected mosquitoes — was originally built around a Storm32 BGC 2-axis brushless
drone gimbal. Over the course of field testing and iterative hardware development, this
gimbal proved fundamentally unsuitable for the application. Three cascading failures
drove the decision to replace it entirely with a geared servo-based pan-tilt mechanism.

### Failure 1: Lack of Mechanical Holding Torque

Brushless drone gimbal motors operate as direct-drive actuators with zero mechanical
gear reduction. They rely entirely on active PID control to maintain position — there
is no physical locking mechanism. When the water pump fires, the flexible silicone
hose (1/4" ID, running from the enclosure down to the turret-mounted nozzle) exerts
a continuous spring-back force on the turret payload. The Storm32's brushless motors
could not overcome this lateral load without entering a violent oscillation cycle:
the PID controller would overshoot trying to fight the hose tension, then overshoot
again in the opposite direction, creating a feedback loop that made accurate aiming
impossible during active firing.

### Failure 2: PID Instability with Non-Standard Payload

The Storm32 was factory-tuned for lightweight camera payloads (GoPro-class, ~150g)
with low moments of inertia. Our payload — an IMX219 camera, TF-Luna LiDAR module,
brass water nozzle, and mounting hardware, oriented perpendicular to the original
design axis — introduced a completely different mass distribution. Extensive PID
tuning was attempted both via the o323BGC serial protocol (binary SET_PARAMETER
commands) and the Storm32 BGC GUI tool (which failed to connect via Windows USB).

A systematic tuning procedure was conducted:
- Safe baseline established: P=100, I=0, D=100 (all axes) — stable, no oscillation
- P swept from 100→500 on each axis independently — no oscillation observed
- Adding I=500 and D=200 immediately reintroduced jerkiness
- Root cause identified: the factory integral gains (Pitch I=4000, Roll I=4800,
  Yaw I=1400) caused integral windup where accumulated positional error produced
  aggressive overcorrection loops

The gimbal was only stable at P=400, I=0, D=100 — meaning it had no integral
position hold capability, making it unable to resist external forces (wind, hose
tension) or maintain a commanded angle over time.

### Failure 3: Electrical Short Circuit and Ground Loop

During an earlier integration phase, a direct short circuit through the shared
USB/UART ground path between the Storm32 and the Jetson Orin Nano melted wiring
and caused a power brownout on the Jetson controller. The Storm32's motor drivers
draw significant current during stall conditions, and the shared ground return path
through the USB cable allowed motor stall current to flow back through the Jetson's
USB controller. Additionally, the Yahboom carrier board's hardware UART and PWM pins
were found to be non-functional (documented as ECO-2026-008), forcing all Storm32
communication through USB serial — the same bus carrying the problematic ground loop.

---

## Decision

Replace the Storm32 BGC brushless gimbal with a **geared MG996R servo pan-tilt
system** driven by a **PCA9685 I2C PWM driver** with **electrically isolated power
delivery** via a dedicated 12V-to-5V 10A buck converter.

### Why Geared Servos Solve All Three Failures

1. **Holding Torque:** MG996R servos provide 10-13 kg·cm of torque through metal
   gear reduction. The internal gears are *mechanically self-locking* — the servo
   holds position by physical friction in the gear train, not by active electronic
   control. This eliminates oscillation under hose tension entirely.

2. **No PID Tuning Required:** Hobby servos are position-controlled via PWM pulse
   width. The internal feedback loop (potentiometer + H-bridge) is factory-sealed
   and does not require user tuning. Commanded angle = actual angle, with ~1-2°
   accuracy. The complex PID instability problem simply does not exist.

3. **Electrical Isolation:** The servo power (5V, up to 10A) is provided by a
   dedicated buck converter wired directly to the 12V distribution bus. The servos
   share zero power conductors with the Jetson. Only three wires connect to the
   Jetson: I2C SDA, I2C SCL, and a single GND reference for signal return. This
   architecture makes motor stall current physically unable to reach the Jetson's
   USB or power rails.

---

## New Hardware Architecture

### Bill of Materials (New Parts)

| Component | Part | Purpose |
|---|---|---|
| Servo Driver | SunFounder PCA9685 16-Ch I2C | Hardware PWM generation (Yahboom GPIO PWM dead) |
| Power | DWEII 12V→5V 10A Buck Converter | Isolated servo power, short-circuit protected |
| Actuators | Aideepen MG996R Metal Gear Servos (x2) | Pan (yaw) + tilt (pitch) axes |
| Frame | Bolsen 2-DOF Aluminum Pan-Tilt Bracket | Rigid cage with ball bearings |

### Wiring Topology

```
12V PSU ──┬── Wago ──┬── Jetson Orin Nano (barrel jack)
          │          ├── Water Pump (via relay)
          │          └── Buck Converter IN (12V)
          │
          └── Buck Converter OUT (5V/10A)
                 ├── Red → MG996R Yaw servo
                 ├── Red → MG996R Pitch servo
                 ├── GND → servo GND (both)
                 └── GND ──jumper──→ Jetson GND pin (signal reference)

Jetson I2C Bus 1 ── SDA/SCL ──→ PCA9685 (addr 0x40)
                                  ├── Ch0 → Yaw servo signal
                                  └── Ch1 → Pitch servo signal
```

---

## Software Changes

### What Changed

A new `ServoTurretController` class was added to `hardware.py` with the **identical
API** as the existing `GimbalController`:
- `set_angles(pitch, yaw)` — absolute positioning with software endstops
- `nudge(d_pitch, d_yaw)` — relative movement for WASD manual control
- `center()` — return to home position
- `get_status()` — returns pitch, yaw, connected state
- `cleanup()` — centers turret on shutdown

A `create_turret_controller()` factory function auto-detects available hardware:
1. Probes I2C bus for PCA9685 at address 0x40 → uses `ServoTurretController`
2. Falls back to Storm32 USB serial probe → uses `GimbalController`
3. No hardware found → stub mode

### What Did NOT Change

- `app.py` — no modifications needed (uses controller API)
- `templates/index.html` — dashboard WASD controls unchanged
- `gimbal_controller.py` — legacy agent module, unchanged
- `scout_vision.py` / `sniper_vision.py` — unaffected
- `weapon_system.py` — unaffected
- All safety checks (SAFE-001 §2 software endstops) — preserved in new controller

---

## Trade-offs Accepted

| Aspect | Storm32 (old) | MG996R (new) | Impact |
|---|---|---|---|
| Speed (60°) | ~50ms | ~150ms | 3× slower; acceptable for overhead tracking |
| Stabilization | IMU-based active | None (open-loop) | Not needed for fixed mount |
| Pitch range | ±100° | ±90° | 10° less; sufficient for downward-facing mount |
| Precision | Sub-degree | ±1-2° | Adequate for spray pattern coverage |
| Weight | ~200g | ~350g | Heavier but on a fixed post, not a drone |
| Holding torque | 0 (active only) | 10-13 kg·cm | **Fundamental improvement** |

---

## Verification Plan

When hardware arrives:
1. I2C scan confirms PCA9685 at 0x40 alongside TF-Luna at 0x10
2. Servo sweep test on both axes (0°→180°→0°)
3. WASD dashboard controls move turret smoothly
4. Water pump fire test — turret holds position under hose tension
5. No Jetson brownout during servo stall conditions
