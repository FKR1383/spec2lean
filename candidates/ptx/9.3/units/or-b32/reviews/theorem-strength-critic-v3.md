# Theorem-Strength Critique: `or.b32` (v3)

## Artifact under review
- `candidates/ptx/9.3/units/or-b32/theorems/obligations-v4.json`
- Inputs reviewed: `theorems/obligations-v4.json`, `lean/OrB32-v7.lean`, `semantics/semantics-v1.json` (for semantic claim traceability context).

## Findings

No theorem-strength, non-vacuity, or over-claim issues were identified.

## Review notes

- The theorem set is now decomposed into one declaration per obligation (no combined or multi-clause `lean_statement_sketch` declarations).
- Correspondence properties are now semantically aligned and non-weak:
  - executed outcome soundness,
  - false-guard notExecuted characterization,
  - relation-to-function completeness,
  - none/absence-of-step equivalence.
- Determinism is only stated over `OrB32Step` relation constructors (not as an over-strengthened total-function theorem).
- Frame lemmas are concrete, with explicit hypotheses (`Destination.reg` inequality or `evalGuard ... = some false`) preventing vacuous blanket claims.
- All theorem hypotheses/conclusions appear to be meaningful relative to the bounded Lean model and do not introduce unsound extra preconditions.

### Non-vacuity checks

- `PTX-OR-THM-401`: Nontrivial uniqueness claim over potentially distinct post-states (executed/notExecuted).
- `PTX-OR-THM-402` and `PTX-OR-THM-403`: Distinguish both function outcome branches and connect each to relation shape.
- `PTX-OR-THM-404` and `PTX-OR-THM-405`: Cover completeness/absence behavior for partial execution.
- `PTX-OR-THM-406` and `PTX-OR-THM-407`: State concrete state-preservation properties tied to predication and destination/bitwise write semantics.
- `PTX-OR-THM-408`: Restricts unchanged-value-register frame property to non-destination registers.

## Overall assessment

The obligations are ready for human theorem-strength approval.
