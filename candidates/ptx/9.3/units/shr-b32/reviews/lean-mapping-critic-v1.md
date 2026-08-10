# LEAN MAPPING CRITIQUE — `shr.b32` (PTX 9.3)

Scope: mapping of `candidates/ptx/9.3/units/shr-b32/lean/ShrB32-v1.lean` against
`candidates/ptx/9.3/units/shr-b32/semantics/semantics-v1.json` and
`candidates/ptx/9.3/units/shr-b32/architecture/foundation-v1.md`.

## Findings

### Finding SHR-LMAP-001 — MAJOR
- **Severity:** MAJOR
- **Affected artifact:** `lean/ShrB32-v1.lean`
- **Exact location:**
  - `execShrB32` and its outcome type (`lines 139-147`)
  - `ShrB32Step` relation (`lines 149-159`)
- **Evidence references:**
  - `semantics-v1.json` execution behavior and preconditions: lines 127-153, 156-160, 177-189, 214-224 (stated exceptional/undefined behavior is open; malformed preconditions are discussed)
  - `architecture/foundation-v1.md` line 53 (`execution relation shape: executed, skipped, and stuck`)
- **Description:**
  `execShrB32` returns `none` when the guard register or any source read is missing
  (e.g., undeclared register/immediate lookup failure), and the inductive relation
  `ShrB32Step` has only `guardFalse`/`executed` constructors. There is no
  explicit relation constructor or outcome for the malformed/decode-invalid path.
- **Consequence:**
  The Lean semantics under-approximates the intended state relation by dropping the
  malformed case instead of representing it explicitly as `stuck`/`invalid`. This
  weakens traceability to the semantic architecture and can make later theorem
  statements either vacuously true or miss required obligations about error/stuck
  behavior.
- **Required owner for revision:** Lean Formalizer (Gate C candidate)
- **Human review required:** no

## Disposition
- **BLOCKER:** 0
- **MAJOR:** 1
- **MINOR:** 0
- **NOTE:** 0

Pre-gate revision required: **YES**

## Stage status
Not ready for Gate C without fixing MAJOR issues.