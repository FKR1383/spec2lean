# Architecture Critique: `or.b32` (Review v4)

## 1) Status
- Reviewed artifact: `candidates/ptx/9.3/units/or-b32/architecture/foundation-v4.md`
- Stage: `ARCHITECTURE_CRITIQUE`
- Required source: `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html`
- Review decision: **SUCCESS**
- Next human stage: **Gate A readiness**

## 2) Findings

### ARC-401 (NOTE)
- **Affected artifact:** `candidates/ptx/9.3/units/or-b32/architecture/foundation-v4.md`
- **Location:** `Section 6 / assumptions A-3, AM-1` lines 79-83
- **Evidence references:**
  - `logic-and-shift-instructions-or` lines 14298–14321
  - `source-operands` lines 5331–5334
- **Description:**
  Immediate support remains an explicit design restriction (only for `srcB`) backed by an example and bounded by `A-3`; this is appropriate, but still not normatively grounded as a full per-position operand rule from a single specification subsection.
- **Consequence:**
  The implementation must keep this as a project design assumption and avoid claiming it as full PTX semantics outside this bounded unit.
- **Required owner for revision:** Spec Architect + Gate A reviewers
- **Human review required:** yes

### ARC-402 (NOTE)
- **Affected artifact:** `candidates/ptx/9.3/units/or-b32/architecture/foundation-v4.md`
- **Location:** `Section 7 / AM-2` lines 84-85
- **Evidence references:**
  - `predicated-execution` lines 7547–7550
- **Description:**
  Guard-false behavior is correctly modeled by assumption `A-1`, but the formal “disabled = unchanged state” clause is an inferred operational choice (not explicitly spelled out in the cited lines).
- **Consequence:**
  Lean mapping should treat this as an explicit local semantics choice, not a proven normative consequence.
- **Required owner for revision:** Spec Architect + Lean mapping reviewer
- **Human review required:** yes

## 3) Overall recommendation
No MAJOR blocking defects were found in v4 relative to this bounded evidence slice. The architecture is **ready for Human Gate A**, with the above two notes to be carried forward as explicit assumptions/non-proof obligations.
