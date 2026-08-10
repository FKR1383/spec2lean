# Independent Semantic Critique — xor-b16 semantics-v1

## 1. Reviewed artifact

- `candidates/ptx/9.3/units/xor-b16/semantics/semantics-v1.json` (status: READY_FOR_CRITIQUE)
- Inputs used: `candidates/ptx/9.3/units/xor-b16/source-bundles/source-bundle-v1.json`, `candidates/ptx/9.3/units/xor-b16/architecture/foundation-v1.md`, `runs/ptx-9.3-xor.b16-67bf3e37/run.json`.
- This critique does **not** approve Gate B.

## 2. Verdict

**SUCCESS** for Gate B handoff (non-blocking findings only).

## 3. Findings

| ID | Severity | Affected artifact | Location | Evidence refs | Description | Consequence | Required owner | Human review required |
|----|----------|------------------|----------|---------------|-------------|-------------|----------------|----------------------|
| SEM-1 | MINOR | `candidates/ptx/9.3/units/xor-b16/semantics/semantics-v1.json` | `state_reads` entries (lines 98-101) and `operands.sources` (lines 71-74); also `open_questions` OQ-1/OQ-3 | `XOR16_EXAMPLE_B16`, `XOR16_EXAMPLE_B32`, `SF-19`, `SF-1` | The semantics model records unconditional state reads of both sources (`a` and `b`) and defines `d := a ^ b`, while same artifact separately flags immediate-operand uncertainty (OQ-1/OQ-3). If `b` is indeed immediate in some legal encodings, this overstates state behavior by treating immediate use as a register read. | Later Lean semantics/proofs may impose unnecessary preconditions or incorrect state assumptions about register dependence; this can misstate frame and dependence obligations. | Semantic Extractor / Lean Formalizer | Yes |
| SEM-2 | NOTE | `candidates/ptx/9.3/units/xor-b16/semantics/semantics-v1.json` | `guard_semantics.false_guard_consequence` (lines 88-90) | `SF-9`, shared context `control-flow-instructions-at` (`threads with a False guard predicate do nothing`) | The artifact marks false-guard behavior as `open_question` despite an explicit normative statement in shared context that false predicate causes no action. | The semantics is underspecified in a way that may hinder deterministic executable behavior and invites unnecessary assumptions in downstream formalization. | Semantic Extractor / Gate B | Yes |

## 4. Disposition

- BLOCKER: 0
- MAJOR: 0
- MINOR: 1
- NOTE: 1
- Pre-gate revision required: **No** (non-blocking findings only)

## 5. Readiness for Human Gate B

No BLOCKER/MAJOR defects identified in this semantic interpretation file. Route to Gate B with the above non-blocking clarifications for follow-up during human review.
