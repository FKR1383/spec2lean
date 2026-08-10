# Theorem-Strength Critique: shr.b32 (v2)

## Findings

- **ID:** TS-SHR-002
- **Severity:** MAJOR
- **Affected Artifact:** `candidates/ptx/9.3/units/shr-b32/theorems/obligations-v2.json` (obligation `PTX-SHR-THM-002`)
- **Exact Location:** `obligations-v2.json` lines 179-193; `lean/ShrB32-v2.lean` lines 173-177
- **Evidence References:** `PTX-SHR-SEM1-011`, `PTX-SHR-SEM1-012`, `PTX-SHR-SEM1-013`, `PTX-SHR-SEM1-014`, `PTX-SHR-SEM1-015`
- **Description:** `PTX-SHR-THM-002` is intended as full executable/relational synchronization, but the reverse direction only asserts `∃ o, execShrB32 s i = some o` from `ShrB32Step s i s'` and does not constrain `o` to the constructor that was taken. This is too weak: with current relation definition, `ShrB32Step.malformed` is admitted whenever any source is missing regardless of guard, while `execShrB32` gives `guardFalse` on `evalGuard = some false` before source reads. The theorem can therefore be satisfied by choosing an arbitrary matching outcome and does not rule out constructor-level correspondence gaps.
- **Consequence:** The step/exec correspondence proof obligations do not actually prevent or detect mismatches between malformed and false-guard behaviors; they can be fulfilled while execution-relational alignment is semantically over-permissive.
- **Required Owner for Revision:** Proof Engineer
- **Human Review Required:** yes

## Disposition

- BLOCKER: 0
- MAJOR: 1
- MINOR: 0
- NOTE: 0

Pre-gate revision required: **YES**

## Recommendation

Strengthen the correspondence theorem to map each constructor explicitly, e.g.,
- malformed-step implies `execShrB32 s i = some (ExecOutcome.malformed s)` and guards are not false,
- guard-false-step implies `execShrB32 s i = some (ExecOutcome.guardFalse s)`,
- executed-step implies `execShrB32 s i = some (ExecOutcome.executed s')`,
so that constructor-level behavior is bijectively synchronized.