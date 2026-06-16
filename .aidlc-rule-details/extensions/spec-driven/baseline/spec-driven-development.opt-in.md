# Spec-Driven Development — Opt-In

**Extension**: Spec-Driven Development Enforcement

## Opt-In Prompt

The following question is automatically included in the Requirements Analysis clarifying questions when this extension is loaded:

```markdown
## Question: Spec-Driven Development Extension
Should spec-driven development (SDD) rules be enforced for this project?

A) Yes — enforce all SDD rules as blocking constraints (recommended for this project which maintains formal specs in docs/specs/ and requires spec-before-code workflow)
B) Partial — enforce only SDD-01 (spec before code), SDD-02 (history logging), and SDD-05 (no dummy data) as blocking; treat other rules as advisory
C) No — do not enforce SDD rules

[Answer]: Select one option (A, B, or C)
```

## Extension Details

- **Rule File**: `spec-driven-development.md` (same directory)
- **Category**: Spec-Driven Development
- **Applicable Phases**: Inception (Requirements Analysis, Application Design), Construction (all stages)
- **Rule Count**: 6 rules (SDD-01 through SDD-06)
- **Partial Mode**: Enforces SDD-01, SDD-02, SDD-05 only

## When to Recommend

Recommend **Full enforcement (A)** when:
- The project maintains formal specifications in `docs/specs/`
- The project has safety-critical components (SAFE-001)
- The project requires audit trail via `docs/HISTORY.md`
- Changes affect multiple subsystems (camera, gimbal, pump, AI)

Recommend **Partial enforcement (B)** when:
- Making cosmetic or documentation-only changes
- Updating existing features within the scope of current specs
- Rapid iteration where spec updates can be batched
