# Independent Semantic Critique — and.b16 (semantics-v2)

## Scope
- Reviewed artifact: `candidates/ptx/9.3/units/and-b16/semantics/semantics-v2.json` (interpretation_id `ptx-9.3-and-b16-semantics-v2`, stage `SEMANTIC_CRITIQUE`, status `READY_FOR_CRITIQUE`).
- This review is independent and does **not** approve Human Gate B.
- Evidence consulted: `candidates/ptx/9.3/units/and-b16/source-bundles/source-bundle-v4.json` and official PTX 9.3 source anchors (`logic-and-shift-instructions-and`, `predicated-execution`, `9.7.13.2 @`, `ptx-instructions`).

## Findings

### F-AND16-SC-1 (MINOR)
- **Severity:** MINOR
- **Affected artifact:** `candidates/ptx/9.3/units/and-b16/semantics/semantics-v2.json`
- **Location:** `state_reads` + `operands`/`state_writes` sections (lines around 213–252)
- **Evidence references:** `PTX-9.3-AND16-004` (operand size/nottype rule), `PTX-9.3-AND16-005` (general instruction-form context), `PTX-9.3-AND16-010` (`.b16` appears in `.type` set and compatibility rule mentions size-based matching).
- **Description:** The extractor leaves `.b16` immediate-source legality and bit-bucket destination applicability as unresolved `OPEN_QUESTION`s, but several state-effect statements are still stated as unconditional register state reads/writes (e.g., read source a/b unconditionally and write destination register d). If imm-source support were later admitted, at least some operand reads would not involve register-state reads as written here.
- **Consequence:** The artifact over-asserts a register-state read/write profile without conditioning on the unresolved operand-form questions.
- **Required owner for revision:** Semantic Extractor
- **Human review required:** No

### F-AND16-SC-2 (NOTE)
- **Severity:** NOTE
- **Affected artifact:** `candidates/ptx/9.3/units/and-b16/semantics/semantics-v2.json`
- **Location:** `source_bundle_references[0].bundle_of` metadata line 23
- **Evidence references:** `source_bundle_references` path/IDs only (`source-bundle-v4.json`)
- **Description:** Metadata notes `bundle_of: "source-bundle-v3"` while the artifact text states it is built from `source-bundle-v4`; this is traceability bookkeeping noise, not a semantic mismatch.
- **Consequence:** Minor auditability inconvenience only.
- **Required owner for revision:** Semantic Extractor
- **Human review required:** No

## Disposition
- **BLOCKER:** 0
- **MAJOR:** 0
- **MINOR:** 1
- **NOTE:** 1
- **Pre-gate revision required:** No

## Gate readiness
No blocking or major issues identified in the current semantics-v2. The artifact is suitable for Human Gate B presentation, with minor caveat above about unconditional state-read/write wording under unresolved operand-form gaps.
