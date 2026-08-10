# Lean Mapping Critique: `or.b32` (v1)

- **Artifact**: `candidates/ptx/9.3/units/or-b32/lean/OrB32-v5.lean`
- **Semantics reference**: `candidates/ptx/9.3/units/or-b32/semantics/semantics-v1.json`
- **Architecture reference**: `candidates/ptx/9.3/units/or-b32/architecture/foundation-v4.md`
- **Source bundle**: `candidates/ptx/9.3/units/or-b32/source-bundles/source-bundle-v2.json`
- **Status**: Lean file checked successfully by `lean_check_file` (success: true)

## Traceability and fidelity check

Mapped constructs in `OrB32-v5.lean` align with Gate-B semantics:

- Operand order and roles (`d, a, b`) are preserved.
- Bounded form `.b32` is enforced in this unit model.
- `src1` is register-only; `src2` is register-or-immediate.
- Destination supports register or `_` bit-bucket.
- Predicate guard forms `@p` / `@!p` are represented as `none / atPos / atNeg`.
- Guard-false no-op behavior is modeled, and bitwise-or execution is `d = a | b`.
- Missing runtime references are modeled as partial failure (`Option.none`) for guarded/malformed execution.

Relevant evidence IDs used by the candidate comments/semantic alignment include:
`PTX-OR-SEM1-001` through `PTX-OR-SEM1-008` (semantics), especially `SEM1-003`, `SEM1-004`, `SEM1-005`, `SEM1-006`, `SEM1-007`, `SEM1-008`.

## Findings

No semantic mismatches or traceability defects were identified between approved semantics and `OrB32-v5.lean`.

## Recommendation

`lean-mapping-critic-v1` is complete; ready to proceed to **WAITING_GATE_C** for human review.
