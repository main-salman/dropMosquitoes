# Test-Driven Development (TDD) Enforcement Rules

## Overview

These TDD rules are cross-cutting constraints that apply across applicable AI-DLC phases for the dropMosquitoes sentry turret project. They enforce test-first development practices aligned with the project's 6-layer test hierarchy defined in [TEST-001](docs/specs/TEST-001-test-plan.md).

The project tests embedded systems combining computer vision, serial robotics, fluid dynamics, and edge AI — each with distinct failure modes. These rules ensure every code change is accompanied by appropriate tests from the correct layer.

**Enforcement**: At each applicable stage, the model MUST verify compliance with these rules before presenting the stage completion message to the user.

### Blocking TDD Finding Behavior

A **blocking TDD finding** means:
1. The finding MUST be listed in the stage completion message under a "TDD Findings" section with the TDD rule ID and description
2. The stage MUST NOT present the "Continue to Next Stage" option until all blocking findings are resolved
3. The model MUST present only the "Request Changes" option with a clear explanation of what needs to change
4. The finding MUST be logged in `aidlc-docs/audit.md` with the TDD rule ID, description, and stage context

If a TDD rule is not applicable to the current project or unit (e.g., TDD-03 when no safety-related code is being changed), mark it as **N/A** in the compliance summary — this is not a blocking finding.

### Default Enforcement

All rules in this document are **blocking** by default. If any rule's verification criteria are not met, it is a blocking TDD finding — follow the blocking finding behavior defined above.

### Partial Enforcement Mode

If the user selected **Partial** enforcement during opt-in, only rules TDD-01, TDD-03, and TDD-06 are enforced. All other rules are treated as advisory (non-blocking). Log the enforcement mode in `aidlc-docs/aidlc-state.md` under `## Extension Configuration`.

### Verification Criteria Format

Verification items in this document are plain bullet points describing compliance checks. Each item should be evaluated as compliant or non-compliant during review.

---

## Rule TDD-01: Test-First Mandate

**Rule**: Tests MUST be written before or concurrently with implementation code. No unit of work ships without corresponding tests. During the Construction phase's Code Generation stage, the model MUST:
- Generate test files before or alongside source files
- Ensure every public function/method has at least one test
- Ensure every error path has at least one negative test
- Verify tests run and pass before presenting stage completion

The test-first mandate applies to all code changes, whether new features, refactors, or bug fixes.

**Verification**:
- Every new source file has a corresponding test file in `tests/`
- Test files are generated before or in the same stage as source files
- Public functions have at least one positive test case
- Error handling paths have at least one negative test case
- All tests pass when run with `python -m pytest tests/` (or the project's test runner)

---

## Rule TDD-02: Layer-Appropriate Testing

**Rule**: Every code change MUST include tests from the correct layer as defined in [TEST-001](docs/specs/TEST-001-test-plan.md). The test layer hierarchy is:

| Layer | Scope | Where | Example |
|-------|-------|-------|---------|
| Layer 0 | Smoke Tests | Dev Machine (no hardware) | API routes, Flask server, math functions |
| Layer 1 | Hardware Unit Tests | Jetson (one subsystem) | Camera, GPIO relay, serial, TensorRT |
| Layer 2 | Integration Tests | Jetson (multiple subsystems) | Dual camera, camera+serial, GPIO+serial |
| Layer 3 | Safety Tests | Jetson (CRITICAL) | Kill switch, power loss, large-object rejection |
| Layer 4 | Calibration & Accuracy | Jetson + environment | Pump pressure, linear drop, phantom ping |
| Layer 5 | Environmental & Endurance | Outdoor deployment | Humidity, heat, wind, multi-night runs |

The model MUST identify which layer(s) a code change affects and require tests at the appropriate layer(s).

**Verification**:
- Logic-only changes (math, API, Flask) include Layer 0 tests
- Hardware-touching changes include Layer 1 tests (or document why hardware tests must be deferred)
- Multi-subsystem changes include Layer 2 integration tests
- Safety-affecting changes include Layer 3 tests (blocking — see TDD-03)
- Test file names follow the convention `tests/test_*.py`

---

## Rule TDD-03: Safety Test Gate

**Rule**: Any change touching `weapon_system.py`, GPIO control, pump actuation, gimbal boundary enforcement, or any code governed by [SAFE-001](docs/specs/SAFE-001-safety-spec.md) safety interlocks MUST include Layer 3 safety tests that pass before the stage can proceed. This is a **hard gate** — no exceptions.

Safety-critical code paths include:
- GPIO BCM 17 relay control (pump firing)
- `fire()`, `fire_sweep()`, `cease_fire()` methods
- Yaw/pitch boundary enforcement (±80° yaw, ±20° pitch)
- Large-object rejection heuristic
- Kill switch / crash recovery (try/finally GPIO LOW)
- Death spiral prevention

**Verification**:
- Changes to `weapon_system.py` include updated `tests/test_safety.py` tests
- Changes to gimbal boundaries include `tests/test_accuracy.py` endstop tests
- GPIO fail-safe behavior is tested (relay goes LOW on crash/exception)
- Boundary enforcement is tested at and beyond limits (±80° yaw, ±20° pitch)
- Safety tests explicitly reference SAFE-001 section numbers in test docstrings

---

## Rule TDD-04: Regression Prevention

**Rule**: Every bug fix MUST include a regression test that:
1. Reproduces the bug condition (test fails before the fix)
2. Passes after the fix is applied
3. Is clearly marked with a comment referencing the bug (e.g., `# Regression: fixes issue where gimbal overshot boundary`)

This ensures bugs do not silently reappear in future changes.

**Verification**:
- Bug fix commits include a new test case or test modification
- The regression test is documented with a comment explaining the original bug
- The regression test targets the specific failure mode, not just the happy path
- The test is placed in the appropriate layer file per TDD-02

---

## Rule TDD-05: Mock Boundary Enforcement

**Rule**: Tests MUST mock **only** at hardware boundaries — the interface between software and physical hardware. Business logic, physics calculations, coordinate transforms, and data processing MUST be tested with real values, not mocks.

Acceptable mock targets (hardware boundaries):
- `Jetson.GPIO` — GPIO pin state
- Serial UART communication (`serial.Serial`)
- GStreamer camera pipeline (`cv2.VideoCapture` with GStreamer)
- TensorRT inference engine loading
- I2C bus communication (LiDAR)

NOT acceptable to mock:
- `pixel_to_angle()` coordinate transforms
- Predictive lead calculations (`compute_predictive_lead()`)
- Linear drop compensation math
- MOG2 background subtraction parameters
- Flask API route logic
- Any pure function or business logic

**Verification**:
- Mock usage is limited to hardware interface classes/functions
- Physics calculations (`pixel_to_angle`, `compute_predictive_lead`, drop compensation) are tested with real numeric values
- Coordinate transform tests cover boundary values (center pixel, corners, edges)
- No mocks are used for pure functions or data transformations

---

## Rule TDD-06: Test Results Logging

**Rule**: All test execution results MUST be logged in `docs/HISTORY.md` with the `[TEST]` category tag per TEST-001 §4. The log entry MUST include:
- Test ID(s) from TEST-001 (e.g., T0.1, T3.1, T4.2)
- PASSED or FAILED status
- Brief description of what was validated
- Timestamp

Example entries:
```
- **[TEST]** T3.1 Kill switch PASSED — GPIO confirmed LOW after SIGKILL
- **[TEST]** T4.2 Linear drop LUT FAILED — 4m target miss by 25cm, adjusting pitch offset
```

**Verification**:
- `docs/HISTORY.md` is updated with test results after each test execution
- Entries use the `[TEST]` category tag
- Entries include TEST-001 test IDs where applicable
- Both PASSED and FAILED results are logged (no suppression of failures)
