# Engineering Review: Geared Pan-Tilt Turret Migration

## Verdict: ✅ APPROVED with 3 flags

The architecture is mechanically and electrically sound. The servo approach solves both the torque problem (hose tension) and the electrical isolation problem (ground loop) cleanly. Three items need attention before implementation.

---

## ✅ What's Good

### Mechanical
- **MG996R torque (10-13 kg·cm)** is roughly **10× what's needed** for camera + LiDAR + nozzle (~200g payload). Massive margin for fighting hose tension.
- **Metal gears** won't strip under stall — critical for the hose-fighting scenario.
- **Ball bearing on tilt bracket** correctly offloads radial stress from the servo output shaft.
- **Rigid aluminum cage** eliminates the flex/slop that amplified the Storm32 PID oscillation.
- **Bolted metal horns** (not the press-fit plastic ones) will hold position under vibration.

### Electrical
- **10A buck converter for 5A max draw** = 2× headroom. Correct sizing.
- **Full servo power isolation** from Jetson 5V rail eliminates brownout risk entirely.
- **Common ground tie** is correctly specified — PWM won't work without it.
- **12V Wago distribution** reuses existing infrastructure (HW-001 §3).

### The Core Win
Servos are **inherently self-locking** — the internal gear reduction holds position mechanically even at rest. The Storm32's brushless motors had zero holding torque (they rely on active PID to maintain position). This single property eliminates the oscillation problem entirely.

---

## ⚠️ FLAG 1: PWM Pins Are Dead on Your Yahboom Board

> [!CAUTION]
> **ECO-2026-008 (from your own project history):** The Yahboom carrier board for the Orin Nano has non-functional PWM/UART output on the 40-pin header. This was documented when you tried to drive the Storm32 via hardware UART — the pins exist but produce no output.

**Impact:** Direct GPIO PWM from the Jetson header to the servos **will likely not work** on your specific board.

**Fix:** Use a **PCA9685 I2C servo driver board** (~$3-5). This is actually the better approach anyway:

| Approach | Pros | Cons |
|---|---|---|
| Direct GPIO PWM | No extra hardware | Dead on Yahboom, jitter from Linux kernel scheduling |
| **PCA9685 I2C** ✅ | Hardware PWM (no jitter), 16 channels, works via I2C which IS functional on Yahboom | Extra board, I2C bus shared with TF-Luna LiDAR |

The PCA9685 generates rock-solid hardware PWM at 50Hz independently of the CPU. I2C Bus 1 is confirmed working (it's how we talk to the TF-Luna LiDAR already). Different I2C addresses so no conflict:
- TF-Luna: `0x10`
- PCA9685: `0x40` (default)

**Recommendation:** Add a PCA9685 to the BOM. Wire: Jetson I2C SDA/SCL → PCA9685 → servo signal wires.

---

## ⚠️ FLAG 2: MG996R Speed vs. Mosquito Tracking

> [!IMPORTANT]
> MG996R speed is **~0.15 sec/60°** (at 6V). Full sweep (180°) takes **~0.45 seconds**.

For manual aiming (WASD dashboard) this is fine. For **AI-driven mosquito tracking** where the ScoutAgent detects a blob and the TurretAgent needs to whip to the coordinate, this introduces ~200-400ms of mechanical latency on top of the vision pipeline latency.

**Is this acceptable?** Likely yes for your use case — mosquitoes within the 8-10ft overhead zone aren't moving at high angular velocity relative to the camera. But worth noting:

| System | Speed (60°) | Tracking Latency |
|---|---|---|
| Storm32 brushless | ~50ms | Near-instant |
| MG996R servo | ~150ms | 3× slower |
| DS3218 (25kg, upgrade option) | ~120ms | Slight improvement |

If tracking speed becomes an issue later, the DS3218 servo is a drop-in upgrade (same form factor, higher torque, slightly faster, runs at 6.8V from the same buck converter).

---

## ⚠️ FLAG 3: Servo Range is 180° (Not Continuous)

The MG996R is a **180° positional servo**, which maps to:
- **Yaw:** ±90° from center (vs. ±80° on Storm32) — **slightly better**, fine
- **Pitch:** ±90° from center (vs. ±100° on Storm32) — **20° less range**

For your overhead mount pointing downward, the usable pitch range is probably -90° (straight down) to about +45° (angled toward horizontal). This should be sufficient.

> [!NOTE]
> If you ever need continuous rotation on Yaw (360° scanning), you'd swap the pan servo for an MG996R **continuous rotation** variant. Same footprint, different internal electronics.

---

## Software Changes Required

The `GimbalController` class in [hardware.py](file:///Users/salman/Documents/dropMosquitoes/hardware.py) needs to be rewritten. The change is straightforward:

### What Changes
| Component | Storm32 (old) | MG996R/PCA9685 (new) |
|---|---|---|
| Protocol | Binary serial `0xFA` packets | I2C → PCA9685 PWM register writes |
| Angle → Signal | `float32` degrees in packet | Degrees → pulse width (500-2500μs) |
| Port | `/dev/ttyACM0` USB serial | I2C Bus 1, address `0x40` |
| Feedback | Storm32 reports actual angles | None (open-loop, commanded = actual) |
| Library | `pyserial` | `adafruit-circuitpython-pca9685` + `adafruit-circuitpython-servokit` |

### What Stays the Same
- `set_angles(pitch, yaw)` API — identical interface to the rest of the system
- `nudge(d_pitch, d_yaw)` — same
- `center()` — same
- Software endstops (SAFE-001 §2) — same clamping logic
- All dashboard UI — unchanged, WASD still calls `/api/gimbal/nudge`
- All AI pipeline (ScoutAgent → TurretAgent) — unchanged

### Simplified Code Shape
```python
from adafruit_servokit import ServoKit

kit = ServoKit(channels=16, address=0x40)
# Channel 0 = Yaw servo, Channel 1 = Pitch servo

def set_angles(pitch_deg, yaw_deg):
    # Map degrees to servo angle (0-180)
    kit.servo[0].angle = yaw_deg + 90    # -90..+90 → 0..180
    kit.servo[1].angle = pitch_deg + 90  # -90..+90 → 0..180
```

---

## Updated Wiring Diagram

```
12V PSU ──┬── Wago ──┬── Jetson Orin Nano (barrel jack)
          │          ├── Water Pump (via relay)
          │          └── Buck Converter IN (12V)
          │
          └── Buck Converter OUT (5V/10A)
                 ├── Red → MG996R Yaw (Red)
                 ├── Red → MG996R Pitch (Red)
                 ├── GND → MG996R Yaw (Brown)
                 ├── GND → MG996R Pitch (Brown)
                 └── GND ──jumper──→ Jetson GND pin
                 
Jetson I2C Bus 1 ─── SDA/SCL ──→ PCA9685 board
                                      ├── Ch0 Signal → MG996R Yaw (Orange)
                                      └── Ch1 Signal → MG996R Pitch (Orange)

Jetson I2C Bus 1 ─── SDA/SCL ──→ TF-Luna LiDAR (addr 0x10)
                                  (shared bus, different address)
```

---

## Recommended BOM Addition

| Part | Purpose | Approx Cost |
|---|---|---|
| PCA9685 16-Channel I2C Servo Driver | Hardware PWM generation (bypasses dead Yahboom GPIO) | $3-5 |

Everything else in your BOM is correct and sufficient.
