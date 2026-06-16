# Spec-Driven Development (SDD) Enforcement Rules

## Overview

These spec-driven development rules are cross-cutting constraints that apply across applicable AI-DLC phases for the dropMosquitoes sentry turret project. They formalize the project's existing "spec before code" philosophy as defined in [agents.md](agents.md) and enforce it as blocking AIDLC rules.

The project maintains formal specifications in `docs/specs/` covering software architecture (SW-001), hardware configuration (HW-001), safety interlocks (SAFE-001), test plans (TEST-001), operations (OPS-001), and system overview (SYS-001). These specs are the single source of truth — code must conform to specs, and specs must be updated before code changes.

**Enforcement**: At each applicable stage, the model MUST verify compliance with these rules before presenting the stage completion message to the user.

### Blocking SDD Finding Behavior

A **blocking SDD finding** means:
1. The finding MUST be listed in the stage completion message under an "SDD Findings" section with the SDD rule ID and description
2. The stage MUST NOT present the "Continue to Next Stage" option until all blocking findings are resolved
3. The model MUST present only the "Request Changes" option with a clear explanation of what needs to change
4. The finding MUST be logged in `aidlc-docs/audit.md` with the SDD rule ID, description, and stage context

If an SDD rule is not applicable to the current project or unit (e.g., SDD-06 when no physical actuation is being changed), mark it as **N/A** in the compliance summary — this is not a blocking finding.

### Default Enforcement

All rules in this document are **blocking** by default. If any rule's verification criteria are not met, it is a blocking SDD finding — follow the blocking finding behavior defined above.

### Partial Enforcement Mode

If the user selected **Partial** enforcement during opt-in, only rules SDD-01, SDD-02, and SDD-05 are enforced. All other rules are treated as advisory (non-blocking). Log the enforcement mode in `aidlc-docs/aidlc-state.md` under `## Extension Configuration`.

### Verification Criteria Format

Verification items in this document are plain bullet points describing compliance checks. Each item should be evaluated as compliant or non-compliant during review.

---

## Rule SDD-01: Spec Before Code

**Rule**: No new agent, feature, or architectural change may be implemented without a corresponding specification in `docs/specs/`. The spec MUST be created or updated FIRST, then the code.

During the AI-DLC Inception phase:
- The model MUST check which specs are affected by the proposed change
- If no spec exists for the affected area, the model MUST create a new spec before proceeding to Construction
- If an existing spec conflicts with the proposed change, the model MUST update the spec first and present the update for user approval

The project's specification inventory:

| Spec ID | Title | Governs |
|---------|-------|---------|
| SW-001 | Software Specification | Agent architecture, orchestration, physics model |
| HW-001 | Hardware Specification | Jetson, cameras, gimbal, pump, wiring |
| HW-002 | Scandinavian Canopy | Enclosure and mounting |
| SAFE-001 | Safety Specification | Safety interlocks, fail-safes, boundaries |
| TEST-001 | Test Plan | 6-layer test hierarchy, test scripts |
| OPS-001 | Operations Guide | Deployment, maintenance, troubleshooting |
| SYS-001 | System Overview | High-level system architecture |
| ADR-002 | Geared Turret Migration | Architectural decision record |

**Verification**:
- Every new feature or agent has a spec in `docs/specs/` created or updated before code changes
- Spec updates include version increment, updated timestamp, and change description
- Code changes reference the governing spec in commit messages or PR descriptions
- No code files are generated during Construction without a corresponding approved spec

---

## Rule SDD-02: History Logging

**Rule**: Every code change, architectural decision, or procurement action MUST be appended to `docs/HISTORY.md` with a `[CATEGORY]` tag and timestamp. This is a mandatory audit trail for the project.

Valid category tags:

| Tag | Usage |
|-----|-------|
| `[ARCHITECTURE]` | Architectural decisions, design changes |
| `[SOFTWARE]` | Code changes, refactors, new features |
| `[HARDWARE]` | Hardware changes, wiring, components |
| `[SAFETY]` | Safety-related changes or decisions |
| `[TEST]` | Test results, test plan updates |
| `[PROCUREMENT]` | Parts ordered, received, or replaced |
| `[CALIBRATION]` | Calibration runs, tuning changes |
| `[OPERATIONS]` | Deployment, maintenance, operational changes |
| `[BUG]` | Bug discoveries and fixes |

Format:
```
- **[CATEGORY]** YYYY-MM-DD: Description of change — rationale and impact
```

**Verification**:
- `docs/HISTORY.md` is updated in the same commit as the code change
- Entries use a valid `[CATEGORY]` tag from the table above
- Entries include a date/timestamp
- Entries provide sufficient context to understand the change without reading the code diff
- No code-only commits without a corresponding HISTORY.md entry

---

## Rule SDD-03: Spec Traceability

**Rule**: All code files MUST reference their governing spec in a docstring header. This creates a traceable link from implementation to specification.

Format:
```python
# Implements: SW-001 §2.1
```

or for multi-spec files:
```python
# Implements: SW-001 §2.4, SAFE-001 §2
```

The spec reference MUST include the spec ID and the specific section number(s) that the file implements.

**Verification**:
- Every Python source file (excluding `__init__.py`, test files, and utility scripts) has a spec traceability header
- The spec ID and section number in the header exist in the referenced spec document
- New code files include the spec reference before any other code
- Changes to a file's scope update the spec reference to include new section numbers

---

## Rule SDD-04: Spec Review Gate

**Rule**: During the AI-DLC Inception phase (specifically Requirements Analysis and Application Design), the model MUST verify that all existing specs in `docs/specs/` are current and consistent with the proposed changes before proceeding to the Construction phase.

The spec review gate includes:
1. **Consistency check**: No contradictions between specs (e.g., SW-001 pin assignments vs HW-001 wiring)
2. **Currency check**: Specs reflect the current state of the codebase (no stale references)
3. **Impact analysis**: Identify which specs are affected by the proposed change
4. **Gap analysis**: Identify if any new spec is needed for the proposed change

If inconsistencies are found, the model MUST:
- List all inconsistencies with spec IDs and section numbers
- Propose spec updates to resolve the inconsistencies
- Present the updates for user approval before proceeding

**Verification**:
- All affected specs are identified during Inception
- Inconsistencies between specs are documented and resolved
- New specs are created for areas not covered by existing specs
- Spec review findings are logged in `aidlc-docs/audit.md`

---

## Rule SDD-05: No Dummy Data

**Rule**: NEVER create dummy data (dummy videos, generated images, fake datasets, synthetic test data that mimics real sensor output) for testing or training purposes. If sample data is needed, the model MUST prompt the user to provide real data.

This rule applies to:
- Camera test footage (Scout and Sniper cameras)
- YOLO training datasets
- Calibration data (distance measurements, angle readings)
- Sensor readings (LiDAR, IMU)
- Any data that would be used to validate the system's real-world behavior

Acceptable synthetic data:
- Numerical test vectors for pure math functions (e.g., known angle calculations)
- Mock GPIO pin states for unit tests (see TDD-05 mock boundary rules)
- Hardcoded API responses for Flask smoke tests

**Verification**:
- No image files, video files, or dataset files are generated by the model
- No synthetic sensor data is created to simulate camera, LiDAR, or IMU output
- When real data is needed, the model explicitly requests it from the user
- Math test vectors are clearly labeled as synthetic numerical inputs, not sensor data

---

## Rule SDD-06: Safety Spec Compliance

**Rule**: Any change affecting physical actuation (GPIO, pump, gimbal motion, relay control) MUST demonstrate compliance with [SAFE-001](docs/specs/SAFE-001-safety-spec.md) safety specification. This is a **hard gate** for any Construction phase work touching safety-critical code.

Safety-critical code paths governed by SAFE-001:
- GPIO BCM 17 relay control (weapon_system.py)
- Gimbal boundary enforcement (gimbal_controller.py — ±80° yaw, ±20° pitch)
- Large-object rejection heuristic (sniper_vision.py)
- Emergency stop / cease_fire (weapon_system.py)
- Crash recovery — GPIO cleanup in try/finally blocks
- Death spiral prevention — yaw unwinding logic

Compliance demonstration MUST include:
1. Explicit reference to SAFE-001 section numbers
2. Explanation of how the change maintains or improves safety invariants
3. Identification of any new failure modes introduced
4. Updated safety tests per TDD-03

**Verification**:
- Changes to safety-critical files reference SAFE-001 sections
- New failure modes are documented in the safety spec
- Safety invariants are preserved (relay defaults LOW, boundaries enforced, cleanup on crash)
- No safety interlock is weakened or bypassed without explicit user approval and spec update
- Changes to safety code trigger TDD-03 (safety test gate) enforcement
