# Lean Mapping Critique — `or.b16` (Run ptx-9.3-or.b16-ab7bd730)

## Findings

### FM-LM-001
- **Severity:** MAJOR
- **Affected artifact:** `candidates/ptx/9.3/units/or-b16/lean/OrB16-v1.lean`
- **Location:** lines 65-68 (`Destination`/`bitBucket`) and 121-124 (`updateDestination`)
- **Evidence refs:** `candidates/ptx/9.3/units/or-b16/semantics/semantics-v2.json` IDs `OQ-ORB16-03`, `DD-ORB16-002`
- **Description:** The Lean model admits a concrete `Destination.bitBucket` variant and defines a semantics for `@_`-dest behavior (no-op), but the approved semantic artifact marks destination `_` support for `or.b16` as unresolved. `DD-ORB16-002` explicitly states bit-bucket is not asserted for this bounded unit.
- **Consequence:** This introduces behavior not justified by approved semantics and can invalidate any theorem that assumes the modeled syntax/behavior is faithful to the bounded interpretation.
- **Required owner for revision:** Lean Formalizer
- **Human review required:** Yes

### FM-LM-002
- **Severity:** MAJOR
- **Affected artifact:** `candidates/ptx/9.3/units/or-b16/lean/OrB16-v1.lean`
- **Location:** lines 59-62 (`SourceB.imm`) and 111-113 (`evalSourceB`)
- **Evidence refs:** `candidates/ptx/9.3/units/or-b16/semantics/semantics-v2.json` IDs `OQ-ORB16-02`
- **Description:** The mapping permits immediate value as second source operand for all `or.b16` instances (`SourceB.imm`) and evaluates it as a fully valid source. The approved semantics leaves immediate-permitting for `a/b` unresolved (`OQ-ORB16-01/02`), so this is an unsupported extension rather than a traceable interpretation.
- **Consequence:** Execution relation may accept programs that are not justified by the approved semantics, reducing fidelity and potentially strengthening downstream theorems incorrectly.
- **Required owner for revision:** Lean Formalizer
- **Human review required:** Yes

### FM-LM-003
- **Severity:** NOTE
- **Affected artifact:** `candidates/ptx/9.3/units/or-b16/lean/OrB16-v1.lean`
- **Location:** lines 8-20 ("approved semantic claim IDs")
- **Evidence refs:** `candidates/ptx/9.3/units/or-b16/semantics/semantics-v2.json`
- **Description:** Traceability metadata in the file header advertises semantic claim IDs `SF-ORB16-011` but the approved semantic artifact’s `source_facts` set only includes `SF-ORB16-001`..`SF-ORB16-010`; `SF-ORB16-011` is not present there.
- **Consequence:** Automated traceability checks may falsely assume claim coverage that is not present, obscuring auditability of the mapping.
- **Required owner for revision:** Lean Formalizer
- **Human review required:** Yes

## Disposition
- BLOCKER: 0
- MAJOR: 2
- MINOR: 0
- NOTE: 1

**Pre-gate revision required:** Yes

Because unresolved MAJOR findings exist, stage disposition is **REVISE** (next stage: `LEAN_FORMALIZATION`).
