# Hardware & Environment Specification

## System
- **Board:** NVIDIA Jetson Orin Nano Super (16GB)
- **OS:** JetPack 6.0 (Ubuntu 22.04)
- **Python:** Python 3.10+

## Camera Interfaces (MIPI CSI-2)
- **Scout Camera (OV9281):** `/dev/video0` (1280x800 @ 120 FPS via GStreamer).
- **Sniper Camera (IMX477):** `/dev/video1` (Downscaled to 1920x1080 @ 60 FPS via GStreamer).

## Pinout & Comms
- **Trigger Switch (Opto-Isolated Relay):** Jetson GPIO Pin 18 (3.3V logic).
- **Turret Comms (Storm32):** `/dev/ttyTHS0` (Jetson UART). Baud rate: 115200.

## Physics Constraints (The "Mortar" Setup)
- **Effective Range:** 1.0 to 5.0 Meters
- **Water Exit Velocity:** ~7 m/s (Submersible pump with variable spool-up)
- **Pump Run Time (The Shot):** 300 milliseconds constant pulse.
- **Trajectory:** Parabolic. The turret must pitch upward to account for gravity drop over distance.
- **Wind Calibration:** "Phantom Ping" method. System fires a test shot, tracks the visual droplet drift in the Scout camera, and updates an offset variable.