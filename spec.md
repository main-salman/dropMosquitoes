# Hardware & Environment Specification

## System
- **Board:** NVIDIA Jetson Orin Nano SUPER (8GB)
- **OS:** JetPack 6.0 (Ubuntu 22.04)
- **Python:** Python 3.10+

## Camera Interfaces (MIPI CSI-2)
- **Scout Camera (OV9281):** `/dev/video0` (1280x800 @ 120 FPS via GStreamer).
- **Sniper Camera (IMX219 NoIR):** `/dev/video1` (1920x1080 @ 30 FPS via GStreamer).

## Pinout & Comms
- **Pump Relay (Monk Makes CH1):** Jetson GPIO BCM 17 (IDC40P Terminal 11, 3.3V logic).
- **Gimbal Relay (Monk Makes CH2):** Jetson GPIO BCM 27 (IDC40P Terminal 13).
- **Status Buzzer:** Jetson GPIO BCM 4 (IDC40P Terminal 7).
- **Turret Comms (Storm32):** `/dev/ttyTHS0` (Jetson UART). Baud rate: 115200.

## Fluid System (ECO-2026-003)
- **Pump:** 12V DC Diaphragm Pump (60 PSI, self-priming). Surface-mounted adjacent to enclosure.
- **Pump Spin-Up:** ~100ms mechanical delay before water exits nozzle.
- **Firing Mode:** "Stream and Sweep" — 400ms total (pump fires while gimbal sweeps along predicted flight path).

## Physics Constraints
- **Effective Range:** 1.0 to 5.0 Meters
- **Water Exit Velocity:** ~7 m/s (Diaphragm pump at 60 PSI through Orbit nozzle)
- **Sweep Duration:** 400ms (100ms spin-up + 300ms active spray)
- **Trajectory:** Parabolic. The turret must pitch upward to account for gravity drop over distance.
- **Airburst Offset:** Default +12° above calculated target pitch (tunable 0°–30° via dashboard).
- **Wind Calibration:** "Phantom Ping" method. System fires a test shot, tracks the visual droplet drift in the Scout camera, and updates an offset variable.