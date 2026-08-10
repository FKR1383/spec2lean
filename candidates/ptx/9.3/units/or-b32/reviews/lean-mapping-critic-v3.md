# Lean Mapping Critique: `or.b32` (v3)

- **Artifact under review:** `candidates/ptx/9.3/units/or-b32/lean/OrB32-v7.lean`
- **Semantics reference:** `candidates/ptx/9.3/units/or-b32/semantics/semantics-v1.json`
- **Architecture reference:** `candidates/ptx/9.3/units/or-b32/architecture/foundation-v4.md`
- **Source bundle:** `candidates/ptx/9.3/units/or-b32/source-bundles/source-bundle-v2.json`
- **Status:** `lean_check_file` success (`sha256 95b108dc4a2a62b9f3346cfadcca41a409b9715950d21df59a975558200a899b`, exit code 0)

## Traceability/Fidelity assessment

- Operand ordering in `OrB32Instruction` is `guard, d, a, b`, matching PTX `or.type d, a, b;` order from semantics `operands.order = "d, a, b"` and claim `PTX-OR-SEM1-004`.
- `.b32` bounded form is used with `Source1.reg` only and `Source2.reg | imm`, matching approved restriction from `PRE-3` + `ASS-OR-1` and architecture `D-3`/`D-2`.
- Destination supports `reg` and `bitBucket`, with bit-bucket modeled as no-op sink and register update via `updateDestination` only on `Destination.reg`; this corresponds to architecture `D-2`/`D-6` and semantics ambiguity `AMB-OR-2`.
- State reads are present for source operands and predicate (`readSource1`, `readSource2`, `evalGuard`), and writes occur only in destination register via `updateDestination`, matching semantics claims `PTX-OR-SEM1-005`.
- Predication is implemented as optional guard forms (`none`, `atPos`, `atNeg`) with false guard producing `ExecOutcome.notExecuted`, aligned to claim `PTX-OR-SEM1-006` and guard texts in the source bundle.
- Core execution computes `orValue` and updates only when predicate is true and both sources are available (`execOrB32` lines 120–127).
- Malformed state handling is partial (`Option.none`) for missing predicate/source; this remains the same mapping decision as prior review and is consistent with open question `OQ-OR-2` / `PTX-OR-SEM1-008` (no explicit malformed-behavior text).

## Findings

No blocking semantic or traceability defects identified in `OrB32-v7.lean` relative to approved `semantics-v1.json` and `foundation-v4.md`.

## Recommendation

Lean mapping is **ready for Human Gate C** review.
