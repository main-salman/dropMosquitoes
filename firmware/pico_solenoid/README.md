# Pico W solenoid timer (Option B)

1. Hold **BOOTSEL**, plug USB into a PC/Jetson, copy MicroPython UF2 for **Pico W**.
2. Copy `main.py` to the Pico board root (Thonny, or `mpremote cp main.py :main.py`).
3. Plug Pico into the Jetson USB (data cable). Jetson app auto-detects `/dev/ttyACM*` / by-id.
4. Expect log: `[PicoSolenoid] Connected … — gate CLOSED.`

Protocol: `FIRE <ms>`, `OPEN`, `CLOSE`, `PING` @ 115200.
