# Independent Lean-Mapping Critique — xor-b16 Lean mapping v1

## 1. Reviewed artifact

- `candidates/ptx/9.3/units/xor-b16/lean/XorB16-v1.lean`
- Inputs used:
  - `candidates/ptx/9.3/units/xor-b16/semantics/semantics-v1.json` (approved)
  - `candidates/ptx/9.3/units/xor-b16/source-bundles/source-bundle-v1.json`
  - `candidates/ptx/9.3/units/xor-b16/architecture/foundation-v1.md`

## 2. Verdict

**REVISE**: Lean mapping is not fully faithful to the approved semantic scope.

## 3. Findings

| ID | Severity | Affected artifact | Location | Evidence refs | Description | Consequence | Required owner | Human review required |
|----|----------|------------------|----------|---------------|-------------|-------------|----------------|----------------------|
| LMC-1 | MAJOR | `candidates/ptx/9.3/units/xor-b16/lean/XorB16-v1.lean` | `SourceOperand` definition, lines 54-56 | `XOR16_EXAMPLE_B16`, `SF-1`, `PTX-XORB16-SEM-007`, `PTX-XORB16-SEM-005` | The bounded Lean model defines `SourceOperand` as register-only (`SourceOperand.reg`) and has no constructor for immediates. This excludes instruction instances like `xor.b16 d,x,0x0001` (explicitly present in the section examples) from the formal model. The approved semantic artifact leaves immediate support unresolved (`PTX-XORB16-SEM-007`), but did not close it as impossible; therefore this formalization introduces an unapproved narrowing of the instruction surface area and can make semantics and any future theorems vacuous for immediate-form encodings. | Immediate-form executions in the bounded unit cannot be expressed or reasoned about in the Lean state-transition model. If later correctness obligations quantify over `XorB16Instruction`, they only cover a strict subset of legal-looking forms and risk unsoundness-by-omission. | Lean Formalizer | Yes |

| ID | Severity | Affected artifact | Location | Evidence refs | Description | Consequence | Required owner | Human review required |
|----|----------|------------------|----------|---------------|-------------|-------------|----------------|----------------------|
| LMC-2 | MINOR | `candidates/ptx/9.3/units/xor-b16/lean/XorB16-v1.lean` | `Destination` definition, lines 61-64 | `PTX-XORB16-SEM-008`, `SF-10` | `Destination.bitBucket` is included and update semantics are total for it, but legality for `.b16` in this bounded slice is explicitly an open question in the approved semantics (`PTX-XORB16-SEM-008`). This means the formalizer has made a design choice without linking it to a supported claim in the artifact body. | The Lean model may admit states that are not grounded in an approved semantic claim, potentially obscuring whether behavior for underscore destination is intended or merely speculative. | Lean Formalizer | Yes |

## 4. Disposition

- BLOCKER: 0
- MAJOR: 1
- MINOR: 1
- NOTE: 0
- Pre-gate revision required: **Yes**
- Human Gate C should not be approved until revision.

## 5. Readiness for next stage

Do not mark ready for human Gate C. Revision is required on Lean formalization to represent approved semantic scope (especially source-operand forms) and to keep open questions explicit rather than silently made concrete.