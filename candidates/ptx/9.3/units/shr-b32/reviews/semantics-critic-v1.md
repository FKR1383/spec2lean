# SEMANTIC CRITIQUE — shr.b32 (PTX 9.3)

Scope: `candidates/ptx/9.3/units/shr-b32/semantics/semantics-v1.json`

## Findings

### Finding SHRS-SEM-001 — MINOR
- **Severity:** MINOR
- **Affected artifact:** `semantics/semantics-v1.json`
- **Exact location:** lines 195–199 (`behavior.shift_amount_rule`) and 251–275 (`open_questions` around OQ-3)
- **Evidence references:** source-bundle fragments `PTX-9.3-SHR-006` ("Shift amounts greater than register width N are clamped to N"), `PTX-9.3-SHR-012` (bits types)
- **Description:** The bounded behavior explicitly hard-codes clamping to `32` (`"clamped by width 32 for shr.b32"`) while the official text states clamp to register width `N` without defining `N` in this section. `N` is treated as resolved via open architecture context rather than proven from the captured shr evidence.
- **Consequence:** This is a soundness gap in traceability for the bound: proof obligations that rely on exact bit-count clipping need either an explicit upstream definition of `N` for this bounded form or a tighter statement that `N` is an unresolved assumption.
- **Required owner for revision:** Semantic Extractor
- **Human review required:** no

### Finding SHRS-SEM-002 — NOTE
- **Severity:** NOTE
- **Affected artifact:** `semantics/semantics-v1.json`
- **Exact location:** lines 73–80 (`operands.notes`), 257–263 (`open_questions` OQ-1), 177–189 (`state_writes`)
- **Evidence references:** source-bundle fragments `PTX-9.3-SHR-010`, `PTX-9.3-SHR-011`, and `PTX-9.3-SHR-003`
- **Description:** Destination `_` is kept as an open question, which is appropriate, but the interpretation currently models `false`-guard behavior as no change to "entire bounded state" and does not tie this to whether declaration metadata is included in the state model for this unit.
- **Consequence:** Potential state-model drift: if the architecture state includes declaration/predicate metadata, this needs to be explicitly fixed as unchanged on skip, or skip semantics may become under- or over-approximated in downstream proofs.
- **Required owner for revision:** Semantic Extractor (with Architecture alignment)
- **Human review required:** no

## Disposition
- BLOCKER: 0
- MAJOR: 0
- MINOR: 1
- NOTE: 1

Pre-gate revision required: **NO**

## Stage status
Ready for Human Gate B review (non-blocking findings only).
