# Theorem-Strength Critique: `or.b32` (v4)

## Artifact under review
- `candidates/ptx/9.3/units/or-b32/theorems/obligations-v5.json`

## Inputs reviewed
- `theorems/obligations-v5.json` (theorem obligations and `lean_statement_sketch`es)
- `lean/OrB32-v7.lean` (for mapping scope)
- `semantics/semantics-v1.json` (for semantic claim context)
- `reviews/theorem-strength-critic-v3.md` (for prior comparison)

## Findings

No theorem-strength, non-vacuity, or over-claim findings were identified in `obligations-v5.json`.

## Non-vacuity/strength observations

- **Determinism** (`PTX-OR-THM-401`) is stated for the executable relation `OrB32Step` and is non-vacuous because it requires two explicit transition hypotheses; it does not collapse into a trivial total-function theorem.
- **Function/relation correspondence** obligations are split into separate theorem targets (executed soundness, notExecuted iff false-guard, step-to-function completeness, and function-none iff no step), avoiding the earlier combined/under-specified shape.
- **Frame and predication lemmas** (`PTX-OR-THM-406`…`409`) are concrete and conditioned appropriately (false-guard, predicate preservation, non-destination register, bit-bucket no-op), and do not assert stronger-than-supported universal postconditions.
- **Restore check from prior human rejection** is present: the bit-bucket no-op theorem is a separate declaration (`PTX-OR-THM-409`) with design dependencies `D-2`, `D-6`, `AMB-OR-2`, as required for this bounded unit.

## Evidence references for quick traceability

- Theorem set location: `theorems/obligations-v5.json` lines 145–368.
- Added bit-bucket obligation: `PTX-OR-THM-409` lines 340–367.
- Determinism and correspondence properties: lines 146–267.
- Frame/locality properties: lines 269–362.

## Overall assessment

The nine obligations in `obligations-v5.json` remain theorem-strong and non-vacuous under the approved semantics and mapping. Marking this artifact set as ready for human theorem-strength approval review.
