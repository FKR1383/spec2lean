# Theorem-Strength Critique: `or.b32` (v1)

## Artifact under review
- `candidates/ptx/9.3/units/or-b32/theorems/obligations-v2.json`
- Inputs reviewed: semantic obligations and statement sketches only. No candidate theorem/declaration file for proofs exists yet under `candidates/ptx/9.3/units/or-b32/lean/` (only definitional declarations are present in `OrB32-v7.lean`).

## Findings

### Finding TS-OR-B32-001
- **Severity:** MAJOR
- **Affected artifact:** `candidates/ptx/9.3/units/or-b32/theorems/obligations-v2.json`
- **Location:** line 215
- **Evidence references:** obligations-v2 `PTX-OR-THM-105`, `lean/OrB32-v7.lean`
- **Description:** The hypothesis is written `hb : readSource2 s i b = some vb` (using bare `b`) instead of the instruction field `i.b`.
- **Consequence:** Theorem statement skeleton is malformed/ill-typed as written; any generator that auto-translates this JSON into Lean will fail or silently infer a wrong free variable.
- **Required owner:** Theorem Engineer (Theorem-generation pass)
- **Human review required:** yes

### Finding TS-OR-B32-002
- **Severity:** MINOR
- **Affected artifact:** `candidates/ptx/9.3/units/or-b32/theorems/obligations-v2.json`
- **Location:** line 196
- **Evidence references:** obligations-v2 (`PTX-OR-THM-104` semantic_claim_ids), `semantics/semantics-v1.json` (claims 001–008)
- **Description:** `semantic_claim_ids` include `PTX-OR-SEM1-013`, which does not exist in `semantics-v1.json` (claim IDs stop at `PTX-OR-SEM1-008`).
- **Consequence:** Traceability for `OrB32Step_bitBucket_noop` is not verifiable and weakens proof-strength auditing, since the referenced evidence is not recoverable.
- **Required owner:** Theorem Engineer (Theorem-strength cleanup)
- **Human review required:** no

## Overall assessment
The theorem-obligation set is directionally aligned with `or.b32` semantics, but the two issues above block safe progression to proof generation. Theorems should be corrected and re-issued before moving forward.
