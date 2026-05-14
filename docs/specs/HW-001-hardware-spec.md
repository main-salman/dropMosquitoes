# HW-001: Hardware Specification

**Status:** APPROVED  
**Version:** 2.0  
**Last Updated:** 2026-05-14  
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

## 5. Isolation & Safety Hardware

- **Relay:** Monk Makes Dual Relay Module (×2 boards ordered)
  - CH1: Pump trigger (GPIO → 3.3V control → NO closes → Pump gets +12V)
  - CH2: Gimbal boot delay (holds gimbal off until Jetson boots)
- **IR Illumination:** Univivi 8-LED 850nm (IP67, 90° wide angle, fixed to post)

## 6. Fluid System

| Component | Spec |
|:----------|:-----|
| Pump | Velleman 12V Submersible (submerged in reservoir) |
| Tubing | Feelers 1/4" ID × 3/8" OD Silicone (26.25ft spool) |
| Check Valve | Feelers 1/4" PVDF Inline (prevents gravity siphon) |
| Nozzle | Orbit 66190 Flex-Mist Adjustable (narrow stream pattern) |
| Reservoir | Shallow Plastic Storage Tote |
| Service Loop | 3" slack arc at gimbal entry (zip-tied at 2 anchors) |

## 7. Enclosure & Weatherproofing

- **Shell:** Joinfworld IP67 ABS Box (11.4" × 7.5" × 5.5")
- **Cable Glands:** PG9 (×2), PG11 (×1), PG13.5 (×1)
- **Sealant:** Silicone adhesive on all gland threads
- **Internal Mounting:** M3 standoffs (15mm) on grid plate

## 8. Bill of Materials

See [parts.csv](../../parts.csv) for the complete, URL-verified procurement list.
