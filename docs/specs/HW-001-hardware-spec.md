# HW-001: Hardware Specification

**Status:** APPROVED  
**Version:** 5.0 (ECO-2026-004)  
**Last Updated:** 2026-06-12  
**Owner:** Salman

## 1. Compute Platform

- **Board:** Yahboom Jetson Orin Nano SUPER (8GB, SKU: RM-YAHB-03D)
- **OS:** JetPack 6.0 (Ubuntu 22.04)
- **Storage:** Pre-flashed 256GB NVMe SSD
- **Python:** 3.10+

## 2. Camera Interfaces (MIPI CSI-2)

| Role | Sensor | Resolution | FPS | Mount | MIPI Port | Extension |
|:-----|:-------|:-----------|:----|:------|:----------|:----------|
| Scout | Arducam NoIR IMX219 8MP | 1280×720 | 60 | FIXED to enclosure | Port 0 | CSI→HDMI kit |
| Sniper | Arducam NoIR IMX219 8MP | 1920×1080 | 30 | GIMBAL payload | Port 1 | CSI→HDMI kit |

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

The Scout uses the same IMX219 sensor family as the Sniper (NoIR variant — no IR-cut filter). This enables 24/7 operation: visible-light tracking during the day and 850nm IR-illuminated tracking at night. Both cameras are detected by the single `imx219-dual.dtbo` overlay with zero kernel modifications.

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
| **Solenoid MOSFET Gate** | Pin 13 | BCM 27 | Terminal 13 | GREEN | BCM 27 → IRLB8721 Gate (with 4.7kΩ pull-up to T17 — ECO-2026-004 Rev C) |
| **Logic +3.3V (Gate pull-up)** | Pin 17 | — | Terminal 17 | RED/WHT | +3.3V → 4.7kΩ → MOSFET Gate (same joint as GREEN wire — NOT a GPIO) |
| **LiDAR I2C SDA** | Pin 3 | BCM 2 | Terminal 3 | BLUE | TF-Luna data line |
| **LiDAR I2C SCL** | Pin 5 | BCM 3 | Terminal 5 | YELLOW | TF-Luna clock line |
| **LiDAR V+ (5V)** | Pin 4 | — | Terminal 4 | RED | TF-Luna 5V power |
| **LiDAR V- (GND)** | Pin 6 | — | Terminal 6 | BLACK | TF-Luna ground |
| **LiDAR CFG→GND** | Pin 9 | — | Terminal 9 | GREEN | TF-Luna Pin 5 CFG (shared with relay GND) |
| **UART TX** | Pin 8 | BCM 14 | Terminal 8 | GREEN | UART control to Gimbal RC-2/Yaw RX pin |
| **UART RX** | Pin 10 | BCM 15 | Terminal 10 | BLUE | UART control to Gimbal RC-0/Pitch TX pin |
| **UART GND** | Pin 14 | — | Terminal 14 | BLACK | Shared logic ground with Gimbal RC-GND |
| **Status Buzzer** | Pin 7 | BCM 4 | Terminal 7 | WHITE | Active Piezo Buzzer signal pin |

### 5.4 MOSFET Solenoid Switching Circuit (ECO-2026-004 Rev D)

> **⚠ NEW — Replaces relay-gated pump timing for fluid control.**
> The solenoid coil is switched by an IRLB8721 N-Channel MOSFET. **Gate drive:** BCM 27 (Pin 13 / PY.00) with a **4.7kΩ pull-up** from Terminal 17 (+3.3V) at the gate junction. Monk Makes Relay **CH2 is NOT used** for solenoid (pump CH1 only).
>
> **Rev D (software):** The gate is driven via **libgpiod** (`gpiochip0` line 122 / `PY.00`), **not** Jetson.GPIO. On the Yahboom carrier Jetson.GPIO only reaches ~1.6V on this SPI-function pad (below the MOSFET threshold → intermittent/no actuation); libgpiod drives a clean **3.3V push-pull** (bench-verified: gate 3.33V + click). `configure_push_pull()` still sets PADCTL `0x05` on PR.04 + PY.00 first so the pad is in GPIO mode before the line is requested. Install dep: `sudo apt-get install -y python3-libgpiod`.

```
Terminal 17 (+3.3V) ──[4.7kΩ]──┬──[optional 10kΩ to GND]── IRLB8721 Gate
                                 │
Jetson GPIO BCM 27 (Pin 13) ─────┘  (GREEN wire — pulls LOW to close valve)

+12V ──> [Solenoid Coil +] ──> [Solenoid Coil -] ──> IRLB8721 Drain
                    │                    │
                    └──[1N4007 Flyback]──┘  (Cathode to +12V, Anode to Drain)
                                                      │
                                            IRLB8721 Source ──> GND
```

**Component Notes:**
- **TO-220AB pinout (IRLB8721):** Face the printed label, pins pointing down — **G** (left), **D** (middle), **S** (right). The **metal mounting tab is internally tied to D** (same electrical node as the middle pin). Wire the solenoid (−) to the **middle pin only**; leave the tab unconnected or insulate it (~1 A solenoid coil does not need heatsinking).
- **4.7kΩ (472) pull-up:** One leg on **Gate** (same solder joint as GREEN from T13), other leg on **Terminal 17 (+3.3V)**. **Do NOT use 100kΩ (104)** — too weak. Remove any 104 pull-ups previously tried.
- **Optional 10kΩ (103) Gate→GND:** Parallel branch at Gate — keeps valve closed when GPIO floats at boot.
- **Do NOT connect T17 directly to Gate without the 4.7kΩ resistor** — T17 is always-on power; the resistor limits current if GPIO drives LOW.
- **1N4007 flyback diode** across solenoid coil: absorbs back-EMF (same as pump diode in §6.1)
- **Logic level:** IRLB8721 has R_DS(on) < 10mΩ at V_GS = 3.3V
- **Timing:** Direct MOSFET switching — sub-ms once gate reaches 3.3V (no relay in solenoid path)


## 6. Isolation & Safety Hardware

- **Relay:** Monk Makes Dual Relay Module (×2 boards ordered)
  - CH1: Pump On/Off control (GPIO 17 → continuous run mode with accumulator)
  - CH2: Reserved / Unused (solenoid via MOSFET — not relay)
- **Solenoid Valve:** GOODRIG 12V DC Direct-Acting NC, 1/4" FNPT (fluid gating, replaces relay-timed pump pulses)
- **MOSFET Switch:** IRLB8721PBF N-Channel (TO-220), 30V/62A, 3.3V logic compatible (gate via BCM 27 + 4.7kΩ pull-up to T17)
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
  R2 = 20 kΩ (to GND). Ratio 2/3: 0.5V→0.33V, 4.5V→3.0V — stays under the 3.3V rail.
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

- **PSI conversion:** `Vsig = Vtap × 30/20` (undo divider); `PSI = ((Vsig − 0.5) / 4.0) × 100`.
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
| Check Valve | Built into diaphragm pump (internal one-way valves prevent backflow) |
| Nozzle | Adjustable stream nozzle with 1/4" NPT thread + PTFE tape seal |
| Reservoir | Shallow Plastic Storage Tote (placed ABOVE enclosure for gravity-assisted feed) |
| Service Loop | 3" slack arc at gimbal entry (zip-tied at 2 anchors) |

### 8.1 System Topology (ECO-2026-004)

```
[Reservoir] ──> (1/4" Flex Line) ──> [Diaphragm Pump (continuous run)]
                                              │
                              (1/4" Flex Line) │
                                              ▼
                              [1/2" FNPT-to-1/4" Barb Adapter (uxcell)]
                                              │
                              [Swess 0.75L Accumulator Tank (125 PSI)]
                              [  Absorbs all pump pulsation → flat   ]
                              [  pressure line to solenoid            ]
                                              │
                              [1/2" FNPT-to-1/4" Barb Adapter (uxcell)]
                                              │
                              (1/4" Flex Line) │
                                              ▼
                              [1/4" MNPT-to-1/4" Barb Adapter (Kozelo)]
                                              │
                              [GOODRIG 12V Solenoid Valve (NC, 1/4" FNPT)]
                              [  Gated by IRLB8721 MOSFET via BCM 27 + 4.7kΩ pull-up ]
                                              │
                              [1/4" MNPT-to-1/4" Barb Adapter (Kozelo)]
                                              │
                              (1/4" Flex Line) │
                                              ▼
                              [Nozzle (on gimbal payload)]
```

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
2. **Pump → Accumulator** — pump outlet → 1/4" flex line → uxcell 1/2" FNPT adapter → accumulator port 1
3. **Accumulator → Turret** — accumulator port 2 → uxcell 1/2" FNPT adapter → 1/4" flex line → through PG9 cable gland → service loop → Kozelo 1/4" MNPT adapter → **solenoid inlet (ON TURRET)**
4. **Solenoid → Nozzle (DIRECT)** — solenoid outlet → Kozelo 1/4" MNPT adapter → **nozzle threads DIRECTLY into adapter** (zero dead volume, zero drip, 40 PSI at nozzle tip)
5. **Pump Power** — Relay CH1 supplies +12V for pump on/off (continuous run or software-managed duty cycle)
6. **Solenoid Power** — IRLB8721 MOSFET switches solenoid coil (−) to GND. BCM 27 (with 4.7kΩ pull-up from T17) drives MOSFET gate. 12V/GND wires routed from enclosure to turret alongside silicone line.

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
