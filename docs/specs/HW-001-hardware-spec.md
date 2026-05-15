# HW-001: Hardware Specification

**Status:** APPROVED  
**Version:** 4.0 (ECO-2026-002)  
**Last Updated:** 2026-05-15  
**Owner:** Salman

## 1. Compute Platform

- **Board:** Yahboom Jetson Orin Nano SUPER (8GB, SKU: RM-YAHB-03D)
- **OS:** JetPack 6.0 (Ubuntu 22.04)
- **Storage:** Pre-flashed 256GB NVMe SSD
- **Python:** 3.10+

## 2. Camera Interfaces (MIPI CSI-2)

| Role | Sensor | Resolution | FPS | Mount | MIPI Port | Extension |
|:-----|:-------|:-----------|:----|:------|:----------|:----------|
| Scout | OV9281 1MP Global Shutter | 1280×800 | 120 | FIXED to enclosure | Port 0 | CSI→HDMI kit |
| Sniper | Arducam NoIR IMX219 8MP | 1920×1080 | 60 | GIMBAL payload | Port 1 | CSI→HDMI kit |

**Camera Extension Chain:** Camera → 15-pin FPC → RX Board → HDMI Cable → TX Board → 15-pin FPC → 15→22 Adapter → Jetson MIPI Port

## 3. Gimbal

- **Model:** Storm32 2-Axis Pre-Assembled (CNC Metal)
- **Yaw Range:** ±130° (hard-limited in software)
- **Pitch Range:** ±45°
- **Comms:** Jetson UART TX/RX → Storm32 RC_PITCH / RC_YAW pins
- **Serial:** `/dev/ttyTHS0` @ 115200 baud

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
| 4 | Relay CH1 Common (→ Pump +12V via NO contact) |
| 5 | Relay CH2 Common (→ Gimbal +12V via NO contact) |

### Wago GND Port Map

| Port | Destination |
|:-----|:------------|
| 1 | INPUT from WH-02 BLACK wire |
| 2 | Yahboom Jetson GND |
| 3 | Univivi IR Illuminator GND |
| 4 | Velleman Pump GND (direct return) |
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
| **Relay CH1 (Pump)** | Pin 11 | BCM 17 | Terminal 11 | YELLOW | Trigger line → CH1 (Water Pump) |
| **Relay CH2 (Gimbal)** | Pin 13 | BCM 27 | Terminal 13 | ORANGE | Trigger line → CH2 (Storm32 Power) |
| **LiDAR I2C SDA** | Pin 3 | BCM 2 | Terminal 3 | BLUE | TF-Luna data line |
| **LiDAR I2C SCL** | Pin 5 | BCM 3 | Terminal 5 | YELLOW | TF-Luna clock line |
| **LiDAR V+ (5V)** | Pin 4 | — | Terminal 4 | RED | TF-Luna 5V power |
| **LiDAR V- (GND)** | Pin 6 | — | Terminal 6 | BLACK | TF-Luna ground |
| **LiDAR CFG→GND** | Pin 9 | — | Terminal 9 | GREEN | TF-Luna Pin 5 CFG (shared with relay GND) |
| **UART TX** | Pin 8 | BCM 14 | Terminal 8 | GREEN | Storm32 RC_PITCH |
| **UART RX** | Pin 10 | BCM 15 | Terminal 10 | BLUE | Storm32 RC_YAW |
| **UART GND** | Pin 14 | — | Terminal 14 | BLACK | Storm32 signal ground |

## 6. Isolation & Safety Hardware

- **Relay:** Monk Makes Dual Relay Module (×2 boards ordered)
  - CH1: Pump trigger (GPIO 17 → 3.3V control → NO closes → Pump gets +12V)
  - CH2: Gimbal boot delay (GPIO 27 → holds gimbal off until Jetson boots)
- **IR Illumination:** Univivi 8-LED 850nm (IP67, 90° wide angle, fixed to post)

### 6.1 Critical Electrical Safety — Flyback Diode (ECO-2026-001)

> **⚠ MANDATORY HARDWARE PATCH — DO NOT SKIP**

The 12V Velleman water pump is an **inductive load**. When the relay's solid-state MOSFET turns the pump OFF, the collapsing magnetic field in the pump's motor coil generates a high-voltage **flyback spike** that vastly exceeds the relay's 16V maximum tolerance. **Without protection, this spike WILL destroy the relay's internal MOSFETs within days of operation.**

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

## 8. Fluid System

| Component | Spec |
|:----------|:-----|
| Pump | Velleman 12V Submersible (submerged in reservoir) |
| Tubing | Feelers 1/4" ID × 3/8" OD Silicone (26.25ft spool) |
| Check Valve | Feelers 1/4" PVDF Inline (prevents gravity siphon) |
| Nozzle | Orbit 66190 Flex-Mist Adjustable (narrow stream pattern) |
| Reservoir | Shallow Plastic Storage Tote |
| Service Loop | 3" slack arc at gimbal entry (zip-tied at 2 anchors) |

## 9. Enclosure & Weatherproofing

- **Shell:** Joinfworld IP67 ABS Box (11.4" × 7.5" × 5.5")
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
- **Watchdog:** systemd watchdog set to 60s — restarts automatically on crash
- **Logs:** `journalctl -u sentry -f`

## 12. Bill of Materials

See [parts.csv](../../parts.csv) for the complete, URL-verified procurement list.
