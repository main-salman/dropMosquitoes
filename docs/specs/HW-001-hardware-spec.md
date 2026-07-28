# HW-001: Hardware Specification

**Status:** APPROVED  
**Version:** 5.1  
**Last Updated:** 2026-07-28  
**Owner:** Salman

## 1. Compute Platform

- **Board:** Yahboom Jetson Orin Nano SUPER (8GB, SKU: RM-YAHB-03D)
- **OS:** JetPack 6.0 (Ubuntu 22.04)
- **Storage:** Pre-flashed 256GB NVMe SSD
- **Python:** 3.10+

## 2. Camera Interfaces (MIPI CSI-2)

| Role | Sensor | Resolution | FPS | Mount | MIPI Port | IR filter |
|:-----|:-------|:-----------|:----|:------|:----------|:----------|
| Scout | Arducam NoIR IMX219 8MP (“The New Scout”) | 1280×720 | 60 | FIXED to enclosure | Port 0 | **None** (permanent NoIR) |
| Sniper | Arducam IMX219 w/ Motorized IR-Cut (“The Verifier”), PCB **UC-350 Rev.C** | 1280×720 | 30–60 | GIMBAL payload | Port 1 | **Mode A LDR auto** (verified); local IR+GND→actuator; Mode B deferred |

**Camera Extension Chain:** Camera → 15-pin FPC → TX Board → HDMI Cable → RX Board → 15-pin FPC → 15→22 Adapter → Jetson MIPI Port

### 2.1 Vision Subsystem Physical Topology — Sniper Camera (IMX219)

> ⚠ **CRITICAL:** The Sniper camera chain spans a **moving gimbal** and a **static enclosure**. Incorrect cable routing or a stiff HDMI cable will stall the Storm32 motors and destroy the FPC ribbon cables.

**Zone A — Moving Payload (Gimbal Carriage):**
- IMX219 Sniper Camera mounted to payload plate
- 2-inch 15-pin FPC ribbon cable (short — stays on the plate)
- CSI→HDMI **Transmitter (TX) Board** — bolted to payload plate
- *Rule:* Camera + TX Board move **together** with the gimbal. No slack needed.

**Zone B — The Umbilical (Bridges Movement Axes):**
- **Ultra-Thin / Super-Flexible FPV HDMI Cable** — plugs into TX Board on gimbal
- Routes down the pole with a service loop to absorb pan/tilt movement
- *Rule:* This cable MUST be lightweight, ribbon-like, and offer **zero mechanical resistance** to the brushless gimbal motors. Standard monitor HDMI cables are PROHIBITED — they will stall the Storm32.

**Zone C — Static Base (Inside IP67 Enclosure):**
- FPV HDMI cable enters enclosure through **PG11 cable gland**
- Plugs into HDMI→CSI **Receiver (RX) Board** — mounted near Jetson
- 15-pin FPC → 15→22 pin adapter → Jetson MIPI **Port 1**
- *Rule:* RX Board is static. Standard ribbon cables are fine here.

### 2.2 Scout Camera (Arducam NoIR IMX219 8MP) — Simplified Chain

The Scout uses an IMX219 **permanent NoIR** module (no IR-cut filter). Daylight
may look pink/magenta; MOG2 is grayscale so that is fine. Night tracking uses
the always-on 850nm illuminator. The Sniper uses an IMX219 with a **motorized
IR-cut** (“The Verifier” in parts.csv): daytime color when the cut is in,
IR-pass at night when out.

**IR-cut connectivity (chosen 2026-07-28):** Sniper is **UC-350 Rev.C**,
**Mode A — LDR auto** (verified working; leave as-is). No Jetson IR-cut wires.
Back pads: `GND · IR · SCL · SDA · FSTROBE · GP0 · GND · 3V3`. Red/black join
**IR+GND** to the white 2-pin → IR-cut actuator (local). CSI→HDMI is video only.
Mode B (IR+GND → BCM 22 / T15) is deferred unless LDR later fails — see
`diagrams/wire_13_sniper_ircut.drawio`. Software does not drive the filter
(`camera_optics.py` → `software_drives_ircut=false`).
Both cameras use `imx219-dual.dtbo` with CSI→HDMI extension chains.

The Scout camera is **fixed to the enclosure** (no gimbal movement), so it uses the same CSI→HDMI kit but with a standard HDMI cable between TX/RX boards. Both boards are inside the enclosure.

## 3. Gimbal

- **Model:** Storm32 2-Axis Pre-Assembled (CNC Metal)
- **Yaw Range:** ±130° mechanical (software endstop: ±80° — see SW-001 §4)
- **Pitch Range:** ±45° mechanical (software endstop: ±20°)
- **Comms:** Jetson GPIO BREAKOUT (Pins 8 TX, 10 RX, 14 GND) → 3-Wire UART (no power wire) → Storm32 RC Pins (outer row: GND, RC-0/Pitch TX, RC-2/Yaw RX). USB data cable must be completely disconnected during live operation.
- **Serial:** `/dev/ttyTHS1` or `/dev/ttyTHS0` (auto-detected) @ 115200 baud (with `/dev/ttyACM0`/`/dev/ttyUSB0` as fallback).




## 4. Power Infrastructure (12V Star Topology)

| Source | Component |
|:-------|:----------|
| AC Mains | 12V 10A (120W) DC Power Brick |
| DC Entry | Lynxmotion WH-02 Pigtail Harness |
| Distribution | 2× Wago 221-415 (5-Port): one +12V, one GND |

### Wago +12V Port Map

| Port | Destination |
|:-----|:------------|
| 1 | INPUT from WH-02 RED wire |
| 2 | Yahboom Jetson (barrel jack) |
| 3 | Univivi IR Illuminator (direct, always-on) |
| 4 | Diaphragm Pump +12V (continuous run via pressure switch or software control) |
| 5 | Gimbal +12V (direct connection via 2A inline fuse) |
| — | *Add 2nd Wago 221-415 if needed for solenoid +12V (from MOSFET drain)* |

### Wago GND Port Map

| Port | Destination |
|:-----|:------------|
| 1 | INPUT from WH-02 BLACK wire |
| 2 | Yahboom Jetson GND |
| 3 | Univivi IR Illuminator GND |
| 4 | Diaphragm Pump GND (direct return) |
| 5 | Storm32 Gimbal GND (direct return) |

## 5. GPIO Routing — ECO-2026-002: External Terminal Block Hub

> **⚠ ARCHITECTURAL CHANGE** — All GPIO signals now exit the Yahboom case via a 40-pin ribbon cable to an external IDC40P screw terminal breakout board. No jumper wires are inserted into the Jetson header directly.

### 5.1 New Components

| Component | Purpose |
|:----------|:--------|
| 40-Pin F/F IDC Ribbon Cable (0.3m, 2.54mm) | Connects Jetson GPIO header to terminal block inside Yahboom case |
| IDC40P 40-Pin Male Header Terminal Block | External breakout with screw terminals for all device wiring |

### 5.2 System Isolation Rules (Assembly Sequence)

1. **Rule 1 — The Exit:** Connect the female end of the 40-pin ribbon cable to the Jetson GPIO header *inside* the Yahboom aluminum case. Fold the cable flat and route it out through the pre-cut chassis side slot *before* closing the Yahboom lid.
2. **Rule 2 — The Hub:** Connect the other female end of the ribbon cable to the IDC40P breakout board's male header. Mount the IDC40P board inside the IP67 enclosure (not the Yahboom case). All device wiring (LiDAR, relays) connects **only** to the screw terminals on this breakout — never to the Jetson header.
3. **Rule 3 — Isolation Boundary:** The Yahboom case is sealed shut with only the ribbon cable and DC power entering/exiting. All field-wiring changes happen at the terminal block.

### 5.3 Definitive GPIO-to-Terminal Mapping

> Terminal numbers on the IDC40P breakout match physical Jetson pin numbers 1:1.

| Function | Jetson Pin | BCM | IDC40P Terminal | Wire Color | Connection Point |
|:---------|:-----------|:----|:----------------|:-----------|:-----------------|
| **Relay V+ (5V)** | Pin 2 | — | Terminal 2 | RED | Monk Makes relay power input |
| **Relay V- (GND)** | Pin 9 | — | Terminal 9 | BLACK | Monk Makes relay ground |
| **Relay CH1 (Pump)** | Pin 11 | BCM 17 | Terminal 11 | YELLOW | Trigger line → Relay IN A (Pump On/Off — continuous run mode) |
| **Solenoid Trigger (SIG)** | Pin 36 | BCM 16 | Terminal 36 | GREEN | PR.05 → MOSFET module SIG (+10kΩ pull-down to GND — ECO-2026-004 Rev E/F) |
| **Relay CH2 (Solenoid 12V interlock)** | Pin 29 | BCM 5 | Terminal 29 | GREEN | PQ.05 → Relay CH2 IN — gates module DC IN+ (ECO-2026-004 Rev L, §5.5) |
| **LiDAR I2C SDA** | Pin 3 | BCM 2 | Terminal 3 | BLUE | TF-Luna data line |
| **LiDAR I2C SCL** | Pin 5 | BCM 3 | Terminal 5 | YELLOW | TF-Luna clock line |
| **LiDAR V+ (5V)** | Pin 4 | — | Terminal 4 | RED | TF-Luna 5V power |
| **LiDAR V- (GND)** | Pin 6 | — | Terminal 6 | BLACK | TF-Luna ground |
| **LiDAR CFG→GND** | Pin 9 | — | Terminal 9 | GREEN | TF-Luna Pin 5 CFG (shared with relay GND) |
| **UART TX** | Pin 8 | BCM 14 | Terminal 8 | GREEN | UART control to Gimbal RC-2/Yaw RX pin |
| **UART RX** | Pin 10 | BCM 15 | Terminal 10 | BLUE | UART control to Gimbal RC-0/Pitch TX pin |
| **UART GND** | Pin 14 | — | Terminal 14 | BLACK | Shared logic ground with Gimbal RC-GND |
| **Status Buzzer** | Pin 7 | BCM 4 | Terminal 7 | WHITE | Active Piezo Buzzer signal pin |

### 5.4 Solenoid Switching — Option B Pico + IRLB8721 (ECO-2026-004 Rev O) — PRODUCTION

> **Production path (2026-07-24).** Jetson USB serial → **Raspberry Pi Pico W** → precise
> GPIO pulse (target **5 ms**) → **IRLB8721** low-side switch → GOODRIG solenoid.
> **Drops** the dual-MOSFET module, Jetson SIG (T36), and Relay CH2 module-12V interlock
> for the valve. Pump stays on Monk Makes **CH1** (T11). WiFi on the Pico is unused.
> Wiring guide: `diagrams/eco004_mosfet_module_option.drawio`.

```
Jetson USB-A ── Micro-B ── Pico W (5V + CDC serial "FIRE")
Pico GP15 ──[220 Ω]── IRLB8721 Gate ──[10 kΩ]── GND
Pico GND ─────────────────────────────── common GND bus
+12V ──[3A fuse]── solenoid (+) RED
solenoid (−) BLUE ── IRLB8721 Drain
IRLB8721 Source ── GND bus
1N5408 across coil: band/cathode → solenoid (+); anode → solenoid (−)
```

**Component Notes:**
- **1N5408 (3A) flyback is MANDATORY** across the coil only (not on the Pico, not on CH1).
- **IRLB8721 TO-220** pinout (front/label toward you, tab behind): **G · D · S** left→right.
- **Gate network:** ~220 Ω series (Pico GP15 → Gate) + **10 kΩ Gate→GND** (keeps FET off if Pico reboots).
- **Common GND required:** Pico GND pin (or USB GND) must share the 12V PSU / Jetson GND bus.
- **Do NOT** use 2N3904/2N2222 to switch the 2A coil — those are logic-only.
- **Pre-install FET check** (part out of circuit, gate shorted to source first): see diagram Ω table.

**USB CDC protocol (Jetson ↔ Pico, 115200 8N1):**
| Host → Pico | Pico action | Reply |
|---|---|---|
| `FIRE <ms>` | GP15 HIGH for ms (1–2000), then LOW | `OK FIRE <ms>` |
| `OPEN` | GP15 HIGH | `OK OPEN` |
| `CLOSE` | GP15 LOW | `OK CLOSE` |
| `PING` | none | `PONG` |

Firmware: `firmware/pico_solenoid/main.py` (MicroPython). Host driver: `pico_solenoid.py`.

### 5.4b Legacy — Dual-MOSFET Trigger Module (ECO-2026-004 Rev G) — SUPERSEDED by §5.4

> **Superseded by Option B (§5.4 Rev O).** Kept for history / rollback.
> The solenoid coil was switched by a **D4184-class dual-MOSFET trigger module**
> (DC 5–36V, 15A, trigger 3.3–20V). **SIG drive:** BCM 16 (Pin 36 / **PR.05** /
> Terminal 36, GREEN) via **libgpiod** + PADCTL. **10kΩ SIG→GND** pull-down.

```
T36 (BCM 16 / PR.05, GREEN) ──┬── module SIG
                              [10kΩ]
                               GND

+12V ──[3A fuse]──[Relay CH2 §5.5]── module DC IN+       module DC IN− ── GND bus
module OUT+ ── solenoid (+) RED      module OUT− ── solenoid (−) BLUE
1N5408 flyback across the coil, band (cathode) → (+) side
```

**Component Notes:**
- **1N5408 (3A) flyback is MANDATORY** — the 2A coil kills the module without it (two modules lost).
- **3A inline fuse** in the +12V feed: a shorted output FET blows the fuse instead of browning out the shared rail.
- **VCC header pin is LED-only** — leave open.
- **SIG LED meaning:** the module's indicator lights when **SIG is HIGH** (logic
  trigger), independent of whether DC IN has 12V. With Rev I pulse-power (CH2 OFF
  at idle), a lit LED + cold module means “SIG stuck/high but load unpowered” —
  uncomfortable but thermally safe. Boot firmware drives PR.05 HIGH until
  `RelayController` claims it; expect the LED during early boot. Idle watchdog
  re-asserts SIG LOW every 1s while not firing.
- Failure signature of a dead module: **OUT+ ↔ OUT− ≈ 9Ω** (healthy = open).

### 5.5 Legacy — Relay CH2 Module 12V Interlock (ECO-2026-004 Rev H–N) — SUPERSEDED by §5.4

> **Superseded by Option B (§5.4 Rev O).** CH2 is no longer required for the solenoid valve.
> Keep Monk Makes **CH1** for the pump. Leave CH2 disconnected / unused after Option B cutover.
>
> **Historical problem (boot):** The Orin Nano boot firmware actively DRIVES PR.05 HIGH during the boot
> window (before `app.py` claims the line). A driven pin defeats any pull-down → the MOSFET
> module turns on if it has 12V. Software cannot close this window.
>
> **Problem (runtime, Rev I):** Leaving module 12V latched ON for the whole `app.py` session
> means any later SIG glitch (PADCTL remux, unclean SIGKILL, pinmux fight) turns the dual-MOSFET
> module on and it runs hot — observed after ~10–12 minutes with no operator input.
>
> **Fix:** The module's **+12V feed is gated through Monk Makes Dual Relay channel B** ("CH2",
> free since the gimbal moved to its own 5V buck). The board is **solid-state** (2A/16V max,
> 1.5A continuous, silent — no click): a 3-pin header (**IN A · IN B · GND**, 4mA @ 3.3V,
> **no Vcc pin**) plus a 4-screw block where each channel is a plain 2-terminal switch
> (**no COM/NO**; screws are interchangeable).
> Wiring: `+12V bus → 3A fuse → screw B①`, `screw B② → module DC IN+`, header `GND → GND bus`
> (already present if the pump input shares the board).
> **IN B GPIO drive abandoned on Yahboom (Rev M):** T13/PY.00, T22/PY.01, and
> T29/PQ.05 all report software HIGH (`ch2_rb=1`) but **never light Channel B LED**
> / never close the SSR. Pump CH1 (T11/PR.04 → IN A) still works — the board is fine;
> CH2 input current demand exceeds what these pads source into IN B.
>
> **Requirement — fully automated (no post-boot operator switch):**
> Power the Jetson on/off only. Module 12V must gate itself via Relay CH2 under
> software control. A manual series MODULE 12V switch is **interim-only**, not
> the production operating mode.
>
> **Software / wiring policy (Rev N — gated production):**
> 1. **Build 2N3904 emitter follower** (see `diagrams/eco004_mosfet_module_option.drawio`):
>    `T29 → 1kΩ → Base`, `T17(+3.3V) → Collector`, `Emitter → IN B` + `10kΩ → GND`.
>    Remove any Channel B load jumper.
> 2. `settings.accumulator.module_12v_hardwired = false` → software opens/closes CH2.
> 3. Boot: CH2 open → module unpowered while firmware drives SIG HIGH (FETs cold).
>    Runtime: app closes CH2 when armed/firing; opens at idle.
>
> **Interim (no buffer yet — Rev M):** jumper B①–B② + `hardwired=true` + optional
> series switch for boot heat. Replace with Rev N buffer ASAP so the switch goes away.


## 6. Isolation & Safety Hardware

- **Relay:** Monk Makes Dual Relay Module (×2 boards ordered)
  - CH1: Pump On/Off control (GPIO 17 → continuous run mode with accumulator)
  - CH2: unused after Option B (§5.4 Rev O); formerly module 12V interlock (§5.5 legacy)
- **Solenoid Valve:** GOODRIG 12V DC Direct-Acting NC, 1/4" FNPT (fluid gating, replaces relay-timed pump pulses)
- **MOSFET Switch (production):** IRLB8721PBF low-side, gate from Pico W GP15 (§5.4 Rev O)
- **Pulse timer:** Raspberry Pi Pico W (USB CDC from Jetson; WiFi unused)
- **IR Illumination:** Univivi 8-LED 850nm (IP67, 90° wide angle, fixed to post)

### 6.1 Critical Electrical Safety — Flyback Diode (ECO-2026-001)

> **⚠ MANDATORY HARDWARE PATCH — DO NOT SKIP**

The 12V diaphragm pump is an **inductive load**. When the relay's solid-state MOSFET turns the pump OFF, the collapsing magnetic field in the pump's motor coil generates a high-voltage **flyback spike** that vastly exceeds the relay's 16V maximum tolerance. **Without protection, this spike WILL destroy the relay's internal MOSFETs within days of operation.**

#### Component
- **Part:** 1N4007 General Purpose Rectifier Diode (1000V / 1A)
- **Cost:** ~$0.10 (sold in 100-packs)
- **Purpose:** Inductive load isolation / freewheeling diode

#### Wiring Configuration
The diode must be wired **in parallel** with the 12V pump, in **reverse-bias** (blocks normal current flow, only conducts the reverse-polarity flyback spike):

| Diode Lead | Marking | Connects To |
|:-----------|:--------|:------------|
| **Cathode** (K) | Striped / banded end | Pump **Positive** (+12V) wire |
| **Anode** (A) | Plain / unmarked end | Pump **Negative** (GND) wire |

#### Placement Options (choose one)
1. **Direct solder:** Solder the diode legs directly across the pump motor's input terminals (most reliable, shortest path).
2. **Wago insertion:** Insert the diode legs into the same Wago lever-nut ports that carry the pump's +12V and GND leads.

## 7. Distance Sensor (LiDAR)

- **Model:** Benewake TF-Luna (Single-Point ToF LiDAR)
- **Interface:** I2C (Bus 1)
- **Address:** `0x10` (default)
- **Power:** 5V (from IDC40P Terminal 4)
- **I2C Logic Level:** 3.3V LVTTL — **directly compatible** with Jetson GPIO. No level shifter needed.
- **Wiring:** All connections via IDC40P screw terminals (see §5.3 mapping table)

| TF-Luna Pin | Function | IDC40P Terminal |
|:------------|:---------|:----------------|
| 1 (VCC) | Power | Terminal 4 (5V) |
| 2 (SDA) | I2C Data | Terminal 3 (SDA) |
| 3 (SCL) | I2C Clock | Terminal 5 (SCL) |
| 4 (GND) | Ground | Terminal 6 (GND) |
| **5 (CFG)** | **Mode Select** | **Terminal 9 (GND) — CRITICAL** |

> ⚠ **Pin 5 (CFG) MUST be connected to GND** before power-on to enable I2C mode.
> If left floating, the sensor defaults to UART mode and will not respond on the I2C bus.

- **Range:** 0.2m – 8.0m (±2cm accuracy)
- **Update Rate:** 250 Hz (I2C mode)
- **Purpose:** "Background Proxy" — pings the surface behind a detected target to get Z-axis distance for parabolic ballistic offset calculation
- **Mounting:** Co-axial with Sniper camera on gimbal payload plate

## 7.1 Pressure Sensor (ADS1115 ADC + Transducer) — ECO-004 Pressure Loop

Closed-loop accumulator pressure measurement so charge setpoints can replace
timed-only charging. Full wiring: `diagrams/eco004_ads1115_pressure.drawio`.

- **ADC:** ADS1115 (16-bit, 4-ch, I2C, PGA). Address `0x48` (ADDR→GND).
- **Transducer:** AUTEX 0–100 PSI, 1/8"-27 NPT, 5V excitation, **0.5–4.5V** ratiometric output.

> ⚠ **BUS CHOICE — use Pin 27/28 (I2C Bus 1), NOT Pin 3/5.** Per the ECO-2026-009
> DTB investigation (HISTORY 2026-06-09), the header's **Pin 3/5 map to I2C Gen8
> (`c250000.i2c`), which is DISABLED in the Yahboom device tree** — that controller
> is electrically dead. The only enabled header bus is **Bus 1 (`c240000.i2c`) on
> Pin 27 (SDA) / Pin 28 (SCL)**, already used by the PCA9685 servo driver and the
> Yahboom onboard INA3221 (both `0x40`). The ADS1115 joins Bus 1 at `0x48`.

- **Bus:** I2C Bus 1 (Pin 27 SDA / Pin 28 SCL). Devices on Bus 1: PCA9685 `0x40`,
  INA3221 `0x40`, ADS1115 `0x48` — **no address conflict** (I2C is multi-drop).

> ⚠ **Power the ADS1115 from 3.3V, NOT 5V.** The module's onboard SDA/SCL
> pull-ups tie to VDD; at 5V they would over-voltage the Jetson's 3.3V I2C
> lines. The transducer itself still needs 5V excitation (Terminal 4).

- **Voltage divider (transducer SIG → ADS1115 A0):** R1 = 10 kΩ (series from SIG),
  R2 = 22 kΩ (to GND). Ratio 0.6875: 0.5V→0.34V, 4.5V→3.09V — stays under the 3.3V rail.
  (22 kΩ is a common on-hand value; 20 kΩ works too. Whatever is fitted must match the firmware constants.)
- **PGA:** ±4.096V FSR so the divided signal never clips.

| Signal | From | To |
|:-------|:-----|:---|
| ADS1115 VDD | Jetson 3.3V (Pin 1 or Pin 17) | ADS1115 VDD |
| ADS1115 GND | Terminal 6 / Pin 9 (GND) | ADS1115 GND |
| ADS1115 SCL | **Pin 28 (I2C1 SCL)** | ADS1115 SCL |
| ADS1115 SDA | **Pin 27 (I2C1 SDA)** | ADS1115 SDA |
| ADS1115 ADDR | ADS1115 GND | (sets addr `0x48`) |
| Transducer +5V | Terminal 4 (5V) | transducer red |
| Transducer GND | Terminal 6 (GND) | transducer black |
| Transducer SIG | transducer signal | R1 → divider node → ADS1115 A0; R2 node → GND |

- **PSI conversion:** `Vsig = Vtap × (R1+R2)/R2 = Vtap × 32/22` (undo divider); `PSI = ((Vsig − 0.5) / 4.0) × 100`.
- **Mounting:** Transducer screws into the 1/8" NPT brass tee on the accumulator/solenoid pressure line.

## 8. Fluid System

> ⚠ **ECO-2026-004:** Constant-Pressure Accumulator + Solenoid Gate architecture.
> Previous direct relay-gated diaphragm pump timing was fundamentally unreliable at sub-10ms pulses
> due to sinusoidal cam pulsation, silicone tube elastic slingshot effect, and mechanical relay jitter.
> See HISTORY.md 2026-06-12 for full root cause analysis.

### 8.0 Components

| Component | Spec |
|:----------|:-----|
| Pump | 12V DC Diaphragm Pump, 60 PSI, self-priming. **Runs continuously** (or pressure-switched). Feeds accumulator tank. |
| Accumulator | **Swess 0.75L Mini Pressure Tank**, 125 PSI max, dual 1/2" MNPT ports. Absorbs pump pulsation → flat pressure line. |
| Solenoid Valve | **GOODRIG 12V DC Direct-Acting NC**, 1/4" FNPT. Gates fluid at nozzle. Sub-ms response via MOSFET. |
| MOSFET Switch | **IRLB8721PBF** N-Channel TO-220, 30V/62A. Coil via Drain; gate via BCM 27 + 4.7kΩ pull-up (T17). |
| Tubing | Feelers 1/4" ID × 3/8" OD Silicone (26.25ft spool) |
| Barb Adapters | **Kozelo** 1/4" Barb × 1/4" MNPT (×2) — solenoid I/O. **uxcell** 1/4" Barb × 1/2" FNPT (×2) — accumulator I/O. |
| Check Valve | **Feelers 1/4" inline one-way** (installed) between **pump outlet and accumulator**. Arrow toward tank. Pump-internal valves alone do **not** hold PSI when pump is OFF. |
| Pressure tee | Brass 1/8" NPT tee + AUTEX 0–100 PSI transducer on accumulator→solenoid line (ADS1115). |
| Nozzle | Adjustable stream nozzle with 1/4" NPT thread + PTFE tape seal |
| Reservoir | Shallow Plastic Storage Tote (placed ABOVE enclosure for gravity-assisted feed) |
| Service Loop | 3" slack arc at gimbal entry (zip-tied at 2 anchors) |

### 8.1 System Topology (ECO-2026-004)

```
[Reservoir] ──> (1/4" Flex) ──> [Diaphragm Pump (charge)]
                                      │
                      (1/4" Flex)     │
                                      ▼
                      [Feelers 1/4" CHECK VALVE]  ← arrow toward accumulator
                                      │             (holds PSI when pump OFF)
                                      ▼
                      [uxcell 1/2" FNPT ← 1/4" barb]
                                      │
                      [Swess 0.75L Accumulator]
                                      │
                      [uxcell] ──> [brass tee + AUTEX transducer]
                                      │
                      (1/4" Flex to turret)
                                      ▼
                      [Kozelo] → [GOODRIG NC solenoid] → [Nozzle DIRECT]
                      Solenoid gated by Pico W → IRLB8721 (HW-001 §5.4 Rev O)
```

> **Do not** install a check valve between accumulator and solenoid — that path must remain free for the shot.

### 8.2 Physical Stacking (Top to Bottom)

The chassis is a vertically condensed dome enclosure with the gimbal mounted INVERTED (hanging from the bottom baseplate):

```
┌─────────────────────────┐
│   Water Reservoir       │ ← Ground level or elevated shelf
│   (intake tube drops in)│
├─────────────────────────┤
│   Diaphragm Pump        │ ← Runs continuously, feeds accumulator
├─────────────────────────┤
│   Accumulator Tank      │ ← Swess 0.75L — absorbs pulsation
├─────────────────────────┤
│   Solenoid Valve        │ ← GOODRIG NC — MOSFET-gated, sub-ms
├─────────────────────────┤
│   IP67 Dome Enclosure   │ ← Baseplate at top, dome hanging down. Jetson inside.
├─────────────────────────┤
│   Gimbal + Sniper Cam   │ ← Hanging INVERTED from enclosure baseplate
│   + Nozzle + LiDAR      │   (Lowest point, firing downward)
└─────────────────────────┘
```

### 8.3 Fluid Routing

> ⚠ **CRITICAL: Solenoid valve is mounted ON the servo turret payload**, directly connected to the nozzle
> with ZERO tubing between them. Any flexible tubing after the solenoid creates "dead volume" that
> absorbs the 10ms pulse energy, defeating the entire accumulator upgrade.

1. **Inlet** — silicone tubing drops into reservoir → runs to pump inlet barb
2. **Pump → Check valve → Accumulator** — pump outlet → 1/4" flex → **Feelers one-way check valve (arrow → tank)** → uxcell 1/2" FNPT adapter → accumulator port 1. External check is **mandatory** — pump internals bleed when OFF.
3. **Accumulator → Pressure tee → Turret** — accumulator port 2 → uxcell → brass tee + AUTEX transducer → 1/4" flex → PG9 / service loop → Kozelo → **solenoid inlet (ON TURRET)**
4. **Solenoid → Nozzle (DIRECT)** — solenoid outlet → Kozelo → **nozzle threads DIRECTLY into adapter** (zero dead volume)
5. **Pump Power** — Relay CH1 supplies +12V for pump on/off (software-managed charge bursts)
6. **Solenoid Power** — Pico W USB CDC → GP15 → IRLB8721 low-side (HW-001 §5.4 Rev O); 1N5408 across coil

### 8.4 Turret Payload Weight Budget

| Component | Weight |
|:----------|:-------|
| IMX219 Sniper Camera | ~30g |
| GOODRIG Solenoid + brass fittings | ~200g |
| Kozelo adapters ×2 | ~30g |
| Nozzle | ~15g |
| **Total** | **~275g** |

MG996R stall torque = 11 kg·cm at 6V → payload is **2.5% of capacity**.
Mount solenoid **near the pivot center** to minimize rotational inertia.

### 8.5 Fallback (If Servos Struggle)

If MG996R servos overheat or overshoot with the solenoid on-turret, replace the silicone tubing
between accumulator and turret with **rigid PTFE (Teflon) or nylon tubing** and move the solenoid
off-turret. Rigid tubing does not expand under pressure, preserving pulse integrity. However,
rigid tubing restricts turret movement range — use solenoid-on-turret first.

## 9. Enclosure & Weatherproofing

- **Shell:** Vertically condensed IP67 Dome Enclosure
- **Orientation:** Inverted "Hanging Dome" configuration
- **Cable Glands:** PG9 (×2), PG11 (×1), PG13.5 (×1)
- **Sealant:** Silicone adhesive on all gland threads
- **Internal Mounting:** M3 standoffs (15mm) on grid plate

## 10. Network Access

The Jetson is sealed inside an IP67 enclosure 8-10ft overhead. Remote access is **mandatory**.

- **WiFi:** Yahboom carrier board has onboard WiFi. Connect to local 2.4GHz network.
- **Static IP:** Assign a static IP via `nmcli` or `/etc/netplan/` so the dashboard URL is predictable.
- **Dashboard URL:** `http://<jetson-ip>:8000` (Flask server)
- **SSH:** `ssh jetson@<jetson-ip>` — enable via `sudo systemctl enable ssh`
- **Fallback:** If WiFi fails, connect Ethernet cable to the Jetson's RJ45 port (requires cable routed through a PG13.5 cable gland).

## 11. Auto-Start on Boot

The turret must start automatically on power-up without manual SSH intervention.

- **Service File:** `sentry.service` (systemd unit, included in repo)
- **Install:** `sudo cp sentry.service /etc/systemd/system/ && sudo systemctl enable sentry`
- **Watchdog:** systemd watchdog set to 60s. The orchestrator daemon (`main.py`) pings systemd via the `sd_notify` protocol over `NOTIFY_SOCKET` every 15s to satisfy the watchdog timer and prevent premature termination.
- **Logs:** `journalctl -u sentry -f`

## 12. Bill of Materials

See [parts.csv](../../parts.csv) for the complete, URL-verified procurement list.

### 12.1 ECO-2026-004 — Accumulator + Solenoid Upgrade Parts

| Part | Qty | Price (CAD) | Source | Thread Spec | Purpose |
|:-----|:----|:------------|:-------|:------------|:--------|
| Swess 0.75L Accumulator Tank | 1 | $49.99 | Amazon.ca | 2× 1/2" MNPT | Pressure dampening |
| GOODRIG 12V DC Solenoid Valve (NC, Direct-Acting) | 1 | $12.99 | Amazon.ca | 1/4" FNPT | Fluid gating |
| IRLB8721PBF N-Channel MOSFET (TO-220) | 5 | $8.99 | Amazon.ca | — | Solenoid switching (3.3V logic) |
| Kozelo 1/4" Barb × 1/4" MNPT Brass Adapter | 2 | $9.19 | Amazon.ca | 1/4" NPT | Solenoid ↔ flex line |
| uxcell 1/4" Barb × 1/2" FNPT Brass Adapter | 2 | $17.59 | Amazon.ca | 1/2" NPT | Accumulator ↔ flex line |
| 1N4007 Flyback Diode | 1 | ~$0.10 | — | — | Solenoid back-EMF protection |
| 4.7kΩ Resistor | 1 | ~$0.05 | — | — | MOSFET gate pull-up (T17 → Gate) — **472** |
| 10kΩ Resistor | 1 | ~$0.05 | — | — | Optional MOSFET gate pull-down (Gate → GND) — **103** |
| **Total** | | **$98.75** | | | |
