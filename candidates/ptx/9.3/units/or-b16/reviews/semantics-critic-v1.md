# Semantic Critique v1 — `or.b16` (run ptx-9.3-or.b16-ab7bd730)

## Scope
- Required inputs reviewed:
  - `source-bundles/source-bundle-v1.json` (`PTX-9.3-ORB16-001` … `PTX-9.3-ORB16-016`)
  - `semantics/semantics-v2.json`

## Findings

### NOTE-SB-001
- **Severity:** NOTE
- **Affected artifact:** `candidates/ptx/9.3/units/or-b16/semantics/semantics-v2.json`
- **Location:** line 1 (JSON header; `architecture_reference` block)
- **Evidence refs:**
  - `candidates/ptx/9.3/units/or-b16/semantics/semantics-v2.json` (line 1)
  - `candidates/ptx/9.3/units/or-b16/architecture/foundation-v1.md:1`
- **Description:**
  The semantic interpretation cites a draft architecture artifact as its reference and records `sha256: null` with `status_note: "Draft architecture; auto-advanced gate context with no human-approved assumption import."`.
  This weakens reproducibility and makes it harder to verify exactly which architectural assumptions were in force during extraction.
- **Consequence:**
  A reviewer cannot deterministically replay this semantic artifact against an immutable architecture snapshot without recomputing provenance from scratch.
- **Required owner for revision:** Semantic Extractor (to re-emit stable architecture hash/reference)
- **Human review required:** No

### NOTE-SB-002
- **Severity:** NOTE
- **Affected artifact:** `candidates/ptx/9.3/units/or-b16/semantics/semantics-v2.json`
- **Location:** line 1 (JSON header; `construct_metadata` and `source_bundle_references`)
- **Evidence refs:**
  - `PTX-9.3-ORB16-003` (or section syntax)
  - `PTX-9.3-ORB16-013`, `PTX-9.3-ORB16-014` (explicit predicate false-do-nothing behavior)
  - `candidates/ptx/9.3/units/or-b16/source-bundles/source-bundle-v1.json`
- **Description:**
  The artifact is syntactically valid but remains minified, which hides claim boundaries and makes it harder to audit the complete per-claim evidence mapping in the semantic stage.
- **Consequence:**
  Increased review friction and reduced auditability for semantic traceability checks.
- **Required owner for revision:** Semantic Extractor
- **Human review required:** No

## Disposition
- **BLOCKER:** 0
- **MAJOR:** 0
- **MINOR:** 0
- **NOTE:** 2

### Pre-gate decision
- **Revision required before next human gate?** No (non-blocking review observations only).
