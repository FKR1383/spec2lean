# Architecture Critique: `or.b32` (Review v5)

## 1) Status
- Reviewed artifact: `candidates/ptx/9.3/units/or-b32/architecture/foundation-v5.md`
- Stage: `ARCHITECTURE_CRITIQUE`
- Required source: `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html`
- Review decision: **SUCCESS** (ready to queue Gate A as informational)
- Next human stage: **WAITING_GATE_A**

## 2) Findings

### ARC-501 (NOTE)
- **Severity:** NOTE
- **Affected artifact:** `candidates/ptx/9.3/units/or-b32/architecture/foundation-v5.md`
- **Location:** `Section 3 / D-1`, `Section 6 / A-1` (lines 35-39, 82-89)
- **Evidence references:**
  - `logic-and-shift-instructions-or` lines 14298–14321 (example `or.b32  mask mask,0x00010001`)
  - `source-operands` lines 5331–5334 (`ALU operands must all be in .reg`)
- **Description:** The bounded architecture models `srcB` as `RegRef | IntConst` (constant allowed) while admitting this as a bounded choice, but the source text also states ALU sources must be `.reg` variables.
- **Consequence:** This does not make the bounded model wrong for this run, but it is an unresolved interpretive narrowing: downstream Lean artifacts must treat immediate acceptance as an explicit bounded design choice (not normative PTX semantics for the general `or` family).
- **Required owner for revision:** Spec Architect; Lean mapping must preserve this bounded assumption.
- **Human review required:** yes

### ARC-502 (NOTE)
- **Severity:** NOTE
- **Affected artifact:** `candidates/ptx/9.3/units/or-b32/architecture/foundation-v5.md`
- **Location:** `Section 3 / D-5`, `Section 10 / TF-7` (lines 57-60, 96-103)
- **Evidence references:**
  - `predicated-execution` lines 7547–7550
  - `control-flow-instructions-at` lines 21838–21841 ("Threads with a False guard predicate do nothing")
- **Description:** `execOrB32` sets guard-false transition to unchanged state as a derived assumption (`DF-1`), which is reasonable for this bounded execution model, but the PTX passages do not formalize the exact local state relation for this family in the same location.
- **Consequence:** Keep this as a local architectural assumption and prevent this from being interpreted as a stronger global “all false-guard behavior is definitionally proven” claim.
- **Required owner for revision:** Spec Architect + Gate A reviewers
- **Human review required:** yes

## 3) Overall recommendation
No blocking defects were identified in `foundation-v5` relative to the declared scope. The file is acceptable to forward for **Human Gate A** with the above two non-blocking semantic-narrowing notes carried forward.
