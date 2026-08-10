# Semantic Critique: `or.b32` (Review v2)

## 1) Status
- Artifact reviewed: `candidates/ptx/9.3/units/or-b32/semantics/semantics-v2.json`
- Source bundle reviewed: `candidates/ptx/9.3/units/or-b32/source-bundles/source-bundle-v1.json`
- Stage: `SEMANTIC_CRITIQUE`
- Review decision: **REVISE**
- Next human stage: **WAITING_GATE_B** (after revision)

## 2) Findings

### SEM-101 (MAJOR)
- **Severity:** MAJOR
- **Affected artifact:** `candidates/ptx/9.3/units/or-b32/semantics/semantics-v2.json`
- **Location:** `operands.b.legal_forms` (lines 40-41), `open_questions` / `design_dependencies` (lines 85-88, 98-102)
- **Evidence references:**
  - Source bundle fragment `PTX-9.3-OR-001` (logic-and-shift-instructions-or)
  - Source bundle known_evidence_gaps `GAP-OR-1`
- **Description:** `operands.b.legal_forms` admits `[register, immediate]` as a normative operand role, but the bundled source does not provide a general immediate-operand grammar; it only contains one example `or.b32 mask mask,0x00010001`. The artifact treats this as an established source interpretation (`DERIVED_INTERPRETATION`) while leaving no matching open question for b, only for a. This conflates an illustrative example with a full operand-form rule.
- **Consequence:** Downstream Lean semantics may incorrectly accept/reject programs because parser-legal immediates are encoded as full semantics rather than as an explicit bounded parsing assumption. This reduces traceability and can silently overstate the ISA contract for `or.b32`.
- **Required owner for revision:** Semantic Extractor (coordination with Spec Architect re `OQ-1` scoping)
- **Human review required:** yes

### SEM-102 (MAJOR)
- **Severity:** MAJOR
- **Affected artifact:** `candidates/ptx/9.3/units/or-b32/semantics/semantics-v2.json`
- **Location:** `design_dependencies` entry `DD-TRANSITION` (lines 85-88)
- **Evidence references:**
  - `design_dependencies.DD-TRANSITION.evidence_fragment_ids` is empty in `semantics-v2.json`
  - Source bundle fragments `PTX-9.3-OR-SHARED-003` and `PTX-9.3-OR-001`
- **Description:** The transition design dependency states that unresolved state/typing cases are modeled as undefined (`Option.none`) but provides no evidence IDs or explicit source-based rationale for this partiality choice. This behavior is a formalization strategy, not a source-backed normative claim, yet is not marked as a design assumption/justified dependency boundary in a traceable way.
- **Consequence:** Semantic strength is weakened/shifted without a stable audit trail, enabling Lean artifacts to import an arbitrary partiality policy that may be stronger or weaker than the bounded model commitment.
- **Required owner for revision:** Semantic Extractor
- **Human review required:** yes
