# Semantic Critique (PTX `shl.b32`) v1

## Status

- Reviewed artifact: `candidates/ptx/9.3/units/shl-b32/semantics/semantics-v1.json` (interpretation_id `ptx-9.3-shl-b32-semantics-v1`).
- Inputs: `candidates/ptx/9.3/units/shl-b32/source-bundles/source-bundle-v1.json`, `candidates/ptx/9.3/units/shl-b32/architecture/foundation-v5.md`, and PTX 9.3 source evidence fragments `PTX-9.3-SHL-001..014`.
- This review does not edit the artifact and does not approve Gate B.

## Overall verdict

**Suitable for Human Gate B presentation (no blocking findings).**

The semantic interpretation is broadly faithful to the bounded evidence: operand order and roles (`d, a, b`), `shl.type` scoping, bits-left-zero-fill behavior, predication forms, and target/version notes align with sources. Predication behavior is correctly labeled as interpretation from shared predication sections.

## Findings table

| ID | Severity | Location | Summary |
|----|----------|----------|---------|
| None | — | — | No substantive blockers found. |

## Residual note

| ID | Severity | Affected artifact | Location | Evidence refs | Description | Consequence | Required owner | Human review |
|----|----------|-------------------|----------|---------------|-------------|----------------|--------------|
| SHL-SC-N1 | NOTE | `semantics/semantics-v1.json` | Source provenance sections (syntax/typing/scope) | `PTX-9.3-SHL-013`, `PTX-9.3-SHL-014` | The semantics file references predication behavior from control-flow/general predication sections rather than the `shl` subsection itself. This is already explicitly documented as interpretation in the file and is not a source-inference error. | Low risk; requires only reviewer awareness that predication is cross-section behavior. | Semantic Extractor | No |

## Gate B readiness

Ready for human Gate B review (do not interpret this as gate approval).