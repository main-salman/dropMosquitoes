# Test-Driven Development (TDD) — Opt-In

**Extension**: Test-Driven Development Enforcement

## Opt-In Prompt

The following question is automatically included in the Requirements Analysis clarifying questions when this extension is loaded:

```markdown
## Question: Test-Driven Development Extension
Should test-driven development (TDD) rules be enforced for this project?

A) Yes — enforce all TDD rules as blocking constraints (recommended for this safety-critical embedded system with 6-layer test hierarchy)
B) Partial — enforce only TDD-01 (test-first mandate), TDD-03 (safety test gate), and TDD-06 (test results logging) as blocking; treat other rules as advisory
C) No — do not enforce TDD rules

[Answer]: Select one option (A, B, or C)
```

## Extension Details

- **Rule File**: `tdd-enforcement.md` (same directory)
- **Category**: Testing
- **Applicable Phases**: Construction (Code Generation, Build and Test)
- **Rule Count**: 6 rules (TDD-01 through TDD-06)
- **Partial Mode**: Enforces TDD-01, TDD-03, TDD-06 only

## When to Recommend

Recommend **Full enforcement (A)** when:
- The project involves safety-critical hardware actuation (GPIO, pumps, gimbal)
- The project has an existing test plan specification (TEST-001)
- The project uses embedded hardware with distinct failure modes per subsystem

Recommend **Partial enforcement (B)** when:
- Making minor changes that don't affect safety-critical paths
- Rapid prototyping phase where full test coverage is impractical
- Changes are limited to UI/Flask routes (Layer 0 only)
