# Architecture Critique (PTX `shl.b32`) v4

Scope reviewed: `candidates/ptx/9.3/units/shl-b32/architecture/foundation-v3.md` against PTX 9.3 source evidence.

## Overall verdict
No new semantic architecture defects were identified that block progression to Gate A. The remaining ambiguities from source are explicitly marked as unresolved assumptions/questions.

## Finding ARC4-1
- **Severity:** MINOR
- **Affected artifact:** `architecture/foundation-v3.md`
- **Location:** `D-5`, `D-11`, `Section 10` (`PRF-4`, `PRF-5`)
- **Evidence references:**
  - SF-SHL-1 (`logic-and-shift-instructions-shl`, lines 14705–14715)
  - SF-SHL-2 (`logic-and-shift-instructions-shl`, lines 14718–14720)
- **Description:**
  The architecture models `b` as a 32-bit operand but leaves register/immediate categorization unresolved, and additionally includes proof-family language about `dst` result-width compatibility. These are coherent, but the proof-family wording should avoid implying a fixed concrete bit-level operator before Lean mapping, because the source only constrains clamping and size compatibility (not full numeric representation).
- **Consequence:**
  Risk of downstream over-committing to a Lean numeric representation if proof obligations are copied verbatim without the stated abstract-operator guardrail.
- **Required owner for revision:** Spec Architect (and Lean Formalizer at stage boundary)
- **Human review required:** yes

## Finding ARC4-2
- **Severity:** NOTE
- **Affected artifact:** `architecture/foundation-v3.md`
- **Location:** `OQ-5` (Section 11), `D-O1/D-O2`
- **Evidence references:**
  - SF-SHL-1 (`logic-and-shift-instructions-shl`, lines 14705–14729)
- **Description:**
  Family-level `.b16/.b32/.b64` context is intentionally retained as metadata-only context, which is acceptable for this unit, but should be consistently called out in parser/declaration constraints to avoid accidental family-wide parsing in later shared infra.
- **Consequence:**
  Possible future parser/type-check mismatch if family-level forms are accidentally enabled for this bounded unit.
- **Required owner for revision:** Spec Architect
- **Human review required:** no

## Gate A readiness
The artifact is materially ready for Human Gate A review; findings are non-blocking, and no unsourced commitments to unsupported PTX behavior remain.