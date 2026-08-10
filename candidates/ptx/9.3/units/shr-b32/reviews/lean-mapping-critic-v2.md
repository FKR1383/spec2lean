# LEAN MAPPING CRITIQUE — `shr.b32` (PTX 9.3)

Scope: comparison of
- Lean mapping: `candidates/ptx/9.3/units/shr-b32/lean/ShrB32-v2.lean`
- Semantic interpretation: `candidates/ptx/9.3/units/shr-b32/semantics/semantics-v1.json`
- Architecture: `candidates/ptx/9.3/units/shr-b32/architecture/foundation-v1.md`

## Findings

### Finding SHR-LMAP-002 — NOTE
- **Severity:** NOTE
- **Affected artifact:** `lean/ShrB32-v2.lean`
- **Exact location:** header comments, lines 10-30
- **Evidence references:** `semantics-v1.json` (status `READY_FOR_CRITIQUE`), `architecture/foundation-v1.md` header ("UNAPPROVED")
- **Description:** The Lean file labels the imported semantics/claims as already “Approved semantic claim IDs” and “Approved semantic claims,” but this run’s semantics and architecture artifacts are not human-approved (they are draft/ready-for-critique states). This does not alter behavior but misstates proof provenance.
- **Consequence:** Traceability wording may create a false sense of human approval in downstream Gate C handoff.
- **Required owner for revision:** Lean Formalizer
- **Whether human review is required:** yes

## Disposition
- **BLOCKER:** 0
- **MAJOR:** 0
- **MINOR:** 0
- **NOTE:** 1

Pre-gate revision required: **NO** (non-blocking evidence quality issue only).

## Stage status
Ready for human Gate C review with no blocking defects.
