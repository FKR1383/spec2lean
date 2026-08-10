# Architecture Critique — and.b16 (v2)

## Findings

### F-ARC-v2-1 (NOTE)
- **Severity:** NOTE
- **Affected artifact:** `candidates/ptx/9.3/units/and-b16/architecture/foundation-v2.md`
- **Location:** `A-B1` / scope of instruction operands (`D-B2`, lines 31–33)
- **Evidence references:**
  - PTX `and` syntax and notes: `and.type d, a, b;` and operand size rule (`documents/.../ptx_isa_9.3.html`, anchor `logic-and-shift-instructions-and`, lines 14262-14278).
  - `and.b32` example with immediate in source operand (`ptx_isa_9.3.html`, line 14285-14286).
- **Description:** `foundation-v2` consistently narrows operands to register refs only. This is acceptable for this bounded run, but there is no direct bounded evidence that `.b16` forbids immediate operands. The restriction is therefore an extra design limitation, not source-derivable.
- **Consequence:** If later stages later widen semantics to include immediate operands for `and.b16`, proof and parser artifacts based on this architecture will need re-alignment. If the subset strategy is intended to stay strict, this should remain an explicit, documented precondition rather than inferred from source.
- **Required owner for revision:** Spec Architect (Gate A artifact owner)
- **Human review required:** Yes

## Disposition
- **BLOCKER:** 0
- **MAJOR:** 0
- **MINOR:** 0
- **NOTE:** 1
- **Pre-gate revision required:** No

## Gate readiness
Architecture v2 resolves the v1 blocking findings (`D-B2` immediate support and `_` destination inconsistency). No remaining blocker/major issues were identified that would force a Gate A rollback.
