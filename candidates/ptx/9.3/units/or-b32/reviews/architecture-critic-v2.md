# Architecture Critique: `or.b32` (Review v2)

## Review Result
**Decision:** **REVISE**

## Findings

### ARC-101 (MAJOR)
- **Affected artifact:** `candidates/ptx/9.3/units/or-b32/architecture/foundation-v2.md`
- **Location:** `Section 6` (`D-6`) lines 64-72, plus `Section 11` (`AM-3`) line 107
- **Evidence references:**
  - PTX `or` section (`logic-and-shift-instructions-or`, lines 14290–14323)
  - No source line for trap/error/exception or “failed typing returns error” behavior in `or` section.
- **Description:**
  The transition design explicitly chooses `MachineState → MachineState ⊕ Error` and a runtime “type/operand validation” phase that can return an error, but no official `or` or PTX core text is cited that defines an error outcome or invalid-instruction dynamic faulting for this instruction.
- **Consequence:**
  This imports an unsupported semantic branch into the bounded architecture and can leak into later theorems/proofs (e.g., proving impossible error cases or conditioning correctness on an extra `Error` constructor not specified by the source).
- **Required owner for revision:** Spec Architect (with Gate A reviewers)
- **Human review required:** yes

### ARC-102 (MAJOR)
- **Affected artifact:** `candidates/ptx/9.3/units/or-b32/architecture/foundation-v2.md`
- **Location:** `Section 4` line 40, `Section 3` line 4, `Section 6` line 42, `Section 10` lines 109–114, and open question `OQ-1`
- **Evidence references:**
  - PTX syntax for this unit: `or.type d, a, b;` with `.type = { .pred, .b16, .b32, .b64 }` (lines 14298–14301)
  - Source/manifests identify the unit in this run as `or.b32`.
- **Description:**
  The artifact is nominally scoped to `or.b32` yet its proposed type/operand model admits `.pred/.b16/.b64` and ambiguous family-polymorphism (`D-3`, `D-6` mentions width-8/16/32/64 polymorphic path). This mixes bounded-unit scope with family-wide semantics.
- **Consequence:**
  Lean artifacts may formalize a broader family than the bounded run, causing theorem obligations (and potential counterexamples) that are not aligned to `or.b32`, and weakening unit traceability.
- **Required owner for revision:** Spec Architect
- **Human review required:** yes

### ARC-103 (MAJOR)
- **Affected artifact:** `candidates/ptx/9.3/units/or-b32/architecture/foundation-v2.md`
- **Location:** `Section 3` line 37, `Section 2` line 9 and `Section 8` line 104, `Section 11` line 105
- **Evidence references:**
  - Source-operands text says ALU operands are variables in `.reg` (`source-operands`, lines 5331–5333)
  - Integer constants are permitted in PTX instructions generally and converted at use (`integer-constants`, lines 2070, 2071, 2082-2083)
  - `or` example includes one immediate form (`or.b32 mask, mask, 0x00010001`, lines 14219–14220)
- **Description:**
  Immediate operands for `or.b32` are modeled as a required operand class (`D-2`) without an explicit per-instruction normative clause that resolves the `.reg`-vs-immediate tension. The candidate marks this only as an ambiguity/assumption, but the core D-2 design still presents immediates as a first-class supported form.
- **Consequence:**
  Semantics may be over-permissive for this bounded unit and hide an unresolved parsing/typing precondition.
- **Required owner for revision:** Spec Architect
- **Human review required:** yes

## Overall recommendation
The architecture candidate is not yet Gate A ready. Resolve the above by:
1) removing or explicitly parameterizing any unsupported error outcome for bounded semantics,
2) making unit scope concrete (`or.b32` only) or explicitly re-scoping the artifact to the full `or` family,
3) demoting immediate support to an explicit assumption with a precise precondition/validation rule for this unit.
