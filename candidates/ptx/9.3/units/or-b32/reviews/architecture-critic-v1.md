# Architecture Critique: or.b32 (Review v1)

## Review Result
**Decision:** **REVISE**

The architecture candidate is useful but currently has normative-scope issues that must be addressed before Gate A review.

## Findings

### ARC-001 (MAJOR)
- **Severity:** MAJOR
- **Affected artifact:** `candidates/ptx/9.3/units/or-b32/architecture/foundation-v1.md`
- **Location:** lines 25-26, 87-88, 59-60
- **Evidence references:**
  - SF-1 (`logic-and-shift-instructions-or`, lines 14298-14303): instruction syntax is `or.type d, a, b;` and explicitly lists `.type = { .pred, .b16, .b32, .b64 }`.
  - Current unit in run metadata: `or.b32`.
- **Description:**
  The architecture mixes two conflicting commitments: it claims unit scope is restricted to `or.b32` (OpenQ `unit scope restricted to b32`) while the core AST/type model includes `.pred/.b16/.b32/.b64` as direct architectural alternatives. This blurs bounded-unit scope with family-wide polymorphism and does not concretely state which semantics are being formalized for this unit.
- **Consequence:**
  The resulting formalization artifacts may encode an instruction behavior broader than the bounded unit and produce theorem obligations not aligned with `or.b32`, risking semantic drift and over-approximation.
- **Required owner for revision:** Spec Architect (and Gate A reviewers)
- **Human review required:** yes

### ARC-002 (MAJOR)
- **Severity:** MAJOR
- **Affected artifact:** `candidates/ptx/9.3/units/or-b32/architecture/foundation-v1.md`
- **Location:** lines 30-33, AM-1, A-3
- **Evidence references:**
  - SF-1 (`logic-and-shift-instructions-or`, lines 14298-14323): only demonstrates one immediate form in a single example (`or.b32  mask mask,0x00010001`) and does not normatively specify immediate-operand admissibility/shape/sign/width for general `or` in this unit.
  - SF-2 (`ptx-instructions`, lines 7517-7525): lists operand arity but does not define register-vs-immediate grammar for every opcode.
- **Description:**
  The candidate elevates immediate operands for this unit to a required operand category without a normative rule; this is not fully traceable as a source fact and remains an assumption.
- **Consequence:**
  Proofs may silently depend on immediate-support assumptions that are not required by PTX for this bound unit, causing under-specified/over-permissive semantics.
- **Required owner for revision:** Spec Architect
- **Human review required:** yes

## Overall recommendation
Revise architecture to resolve the scope/polymorphism contradiction (`or.b32` only vs family-wide types) and either:
1) formally restrict this artifact to `.b32` only with explicit rationale, or
2) make the artifact explicitly family-generic and re-scope obligations/tests for `or.b32` accordingly;
and either cite or isolate immediate-support as a clearly marked assumption with required precondition handling in the instruction model.