# Theorem-Strength Critique: shr.b32 (v1)

## Findings

- **ID:** TS-SHR-001
- **Severity:** MAJOR
- **Affected Artifact:** `candidates/ptx/9.3/units/shr-b32/theorems/obligations-v1.json`
- **Location:** `PTX-SHR-THM-002` (lines 177-193) and executable semantics in `candidates/ptx/9.3/units/shr-b32/lean/ShrB32-v2.lean` (lines 153-160).
- **Evidence References:** `PTX-SHR-SEM1-011`, `PTX-SHR-SEM1-012`, `PTX-9.3-SHR-011`, `PTX-9.3-SHR-012`; runtime definition `execShrB32`.
- **Description:** `PTX-SHR-THM-002` includes an equivalence claim `execShrB32_none_iff_no_step : execShrB32 s i = none ↔ ¬∃ s', ShrB32Step s i s'`.
  In the current Lean mapping, `execShrB32` **always returns `some`** (branches: `malformed`, `guardFalse`, or `executed`) and the relation `ShrB32Step` also always has at least one constructor for every instruction/state. So the theorem as written is not a meaningful executable/relational contract: it proves a vacuous dead-branch fact (`some`-producing, step-available always) rather than a true correspondence of error/`none` behavior.
- **Consequence:** This weakens theorem strength and can mask semantic mismatch: the proof obligation does not validate partial-execution behavior and may be satisfied trivially while giving a false sense of recovery semantics coverage.
- **Required Owner:** Proof Engineer
- **Human Review Required:** yes

## Disposition

- BLOCKER: 0
- MAJOR: 1
- MINOR: 0
- NOTE: 0

Pre-gate revision required: **YES**

## Recommendation

For this unit, either (a) remove/rework the `none`-equivalence sub-theorem to match the explicit `malformed` result contract (`some`-valued executable relation with total option result), or (b) adjust the executable model if `none` is intended to represent malformed directly.
