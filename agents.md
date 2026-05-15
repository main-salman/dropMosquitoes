# Software Modules (Agents)

The system is divided into four asynchronous agents communicating via thread-safe queues.

> **Spec Reference:** All agent implementations MUST conform to [SW-001](docs/specs/SW-001-software-spec.md).
> Any deviation from the spec requires updating the spec FIRST, then the code.

1. **ScoutAgent (`scout_vision.py`):**
   - Reads `/dev/video0` via GStreamer `nvarguscamerasrc sensor-id=0`.
   - Uses OpenCV Background Subtraction (MOG2).
   - Loads tuning parameters from `scout_config.json`.
   - Outputs `(x, y)` pixel coordinates of the highest-confidence moving blob.
   - **Mount: FIXED to IP67 enclosure (does NOT ride on gimbal).**
   
2. **TurretAgent (`gimbal_controller.py`):**
   - Translates Cartesian pixel coordinates into Pitch/Yaw degree commands.
   - Enforces the -130/+130 Yaw boundary.
   - Sends serial strings to the Storm32 via `/dev/ttyTHS0`.
   
3. **SniperAgent (`sniper_vision.py`):**
   - Reads `/dev/video1` via GStreamer `nvarguscamerasrc sensor-id=1`.
   - Runs YOLOv8 TensorRT engine for object classification.
   - Returns TRUE if `class == 'Mosquito'` AND `confidence > 0.80`.
   - **Mount: ON GIMBAL PAYLOAD (moves with turret).**
   
4. **TriggerAgent (`weapon_system.py`):**
   - If `target_locked == True` AND `human_in_frame == False`.
   - Actuates GPIO BCM 17 (IDC40P Terminal 11) `HIGH` for 600ms (Gravity Airburst pulse), then `LOW`.
   - **Safety: MUST comply with [SAFE-001](docs/specs/SAFE-001-safety-spec.md).**

---

## Spec-Driven Development Rules

1. **Spec Before Code:** No new agent or feature may be implemented without a corresponding spec in `docs/specs/`. Create or update the spec first, then implement.
2. **History Logging:** Every code change, architectural decision, or procurement action MUST be appended to `docs/HISTORY.md` with a `[CATEGORY]` tag and timestamp.
3. **Spec Traceability:** All code files should reference their governing spec in a docstring header (e.g., `# Implements: SW-001 §2.1`).