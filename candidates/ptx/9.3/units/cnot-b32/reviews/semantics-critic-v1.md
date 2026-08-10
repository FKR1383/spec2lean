# Independent Semantic Critique — cnot.b32 semantics-v1

## 1) Reviewed artifact
- `candidates/ptx/9.3/units/cnot-b32/semantics/semantics-v1.json`
- Source bundle: `candidates/ptx/9.3/units/cnot-b32/source-bundles/source-bundle-v1.json`

## 2) Overall verdict
**NOT READY for Gate B (REVISION REQUIRED).**

The semantics draft is generally aligned with the retrieved cnot prose, but contains multiple broken/incorrect source traceability links that make key claims unverifiable.

## 3) Findings

### Finding F-SEM-001
- **Severity:** MAJOR
- **Affected artifact:** `candidates/ptx/9.3/units/cnot-b32/semantics/semantics-v1.json`
- **Location:** lines 68–71, 90–91, 191–193
- **Evidence references:** `PTX-9.3-CNOT-019` (repeated)
- **Description:** The semantic interpretation repeatedly cites fragment `PTX-9.3-CNOT-019`, but this fragment id is not present in the source-bundle (`PTX-9.3-CNOT-001` through `-018` only).
- **Consequence:** Guard-false behavior and execution/write claims that rely on this evidence cannot be audited to official text; this is a traceability break and weakens proof obligations built from this claim set.
- **Required owner for revision:** Semantic Extractor
- **Human review required:** Yes

### Finding F-SEM-002
- **Severity:** MAJOR
- **Affected artifact:** `candidates/ptx/9.3/units/cnot-b32/semantics/semantics-v1.json`
- **Location:** line 71
- **Evidence references:** `PTX-9.3-CNOT-016`
- **Description:** `PTX-9.3-CNOT-016` is quoted as evidence for guard-false semantics/no-op behavior, but that fragment states `Supported on all target architectures` and does not describe predication or state-update rules.
- **Consequence:** The no-op-on-false-guard state-writes claim is insufficiently evidenced and may be incorrectly justified.
- **Required owner for revision:** Semantic Extractor
- **Human review required:** Yes

### Finding F-SEM-003
- **Severity:** MINOR
- **Affected artifact:** `candidates/ptx/9.3/units/cnot-b32/semantics/semantics-v1.json`
- **Location:** `open_questions` entry `OQ-2` (lines 139–143) and `semantic_claims` entry `PTX-CNOT-SEM1-006` (line 191)
- **Evidence references:** `PTX-9.3-CNOT-016`
- **Description:** The same unrelated target-support fragment is reused to support bit-bucket uncertainty and write-behavior claims. This is a traceability hygiene issue, not a semantic proof by itself.
- **Consequence:** Open questions/claims are not grounded in the intended evidence; reviewers cannot verify whether the uncertainty is necessary or spurious.
- **Required owner for revision:** Semantic Extractor
- **Human review required:** No (unless semantic-interpretation direction is changed)

## 4) Routing
- Route to **SEMANTIC_EXTRACTION** for corrected artifact revision (replace invalid fragment references and re-anchor guard-false/no-op claims).
- Do not approve Gate B.
