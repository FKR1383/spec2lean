# Final Critique (PTX `shl.b32`) v1

Scope: FINAL_CRITIQUE for run `ptx-9.3-shl.b32-1fe9973c`, revision 29.

## Finding Counts
- **BLOCKER:** 0
- **MAJOR:** 0
- **MINOR:** 2
- **NOTE:** 0

## Source-faithfulness status
Overall, source-faithfulness is **mostly acceptable with explicit open questions carried forward**. No direct source-vs-interpretation contradiction is detected in the reviewed stack. Remaining state-affecting ambiguities are explicitly marked as open questions in source bundle/semsantics and traced to source gaps.

## Unresolved state-affecting gaps
1. **Clamp-width symbol `N`**: source text clamps to `N` but does not expand it in the captured shl subsection. Current implementation fixes this to `32`.
   - Evidence references: `PTX-9.3-SHL-006` (`Shift amounts greater than the register width N are clamped to N`), `PTX-9.3-SHL-007` (`.b32` family + matching size rule), `architecture/foundation-v5.md` `AMB-1`.
2. **Optional destination `_` applicability to `shl.b32`**: no explicit shl-subsection evidence for `_` destination with b32 form; bounded artifacts model destination as register only.
   - Evidence references: `PTX-9.3-SHL-010` (instruction grammar note), `PTX-9.3-SHL-003` (syntax `shl.type d, a, b;`), `PTX-9.3-SHL-007`.

## Findings

### MINOR SHL-FC-1
- **Severity:** MINOR
- **Affected artifact:** `candidates/ptx/9.3/units/shl-b32/semantics/semantics-v1.json` and `candidates/ptx/9.3/units/shl-b32/lean/ShlB32-v1.lean`
- **Location:** `semantics/semantics-v1.json` claim `PTX-SHL-SEM1-006`; `lean/ShlB32-v1.lean` definitions `clampShiftAmount` and `shlValue` (lines ~97–105)
- **Evidence references:** `PTX-9.3-SHL-006`, `PTX-9.3-SHL-007`, `architecture/foundation-v5.md` `AMB-1`
- **Description:** The bounded semantics and implementation choose concrete clamp width `32`, while source evidence for shl only states clamp-to-`N` and does not explicitly define `N` in this captured context.
- **Consequence:** State-affecting semantic default is fixed to `.b32` width without a hard inline proof from the cited section set. This is tracked as an open question, but it remains a modeling commitment with runtime impact.
- **Required owner for revision:** Semantic Extractor and Lean Formalizer
- **Human review required:** yes

### MINOR SHL-FC-2
- **Severity:** MINOR
- **Affected artifact:** `candidates/ptx/9.3/units/shl-b32/architecture/foundation-v5.md`, `candidates/ptx/9.3/units/shl-b32/semantics/semantics-v1.json`, `candidates/ptx/9.3/units/shl-b32/lean/ShlB32-v1.lean`
- **Location:** `architecture/foundation-v5.md` open questions `AMB-2`/`OP-4`; `semantics-v1.json` `AMB-2` note and `operands.notes`; Lean operand types in `SourceOperand`/`Destination`.
- **Evidence references:** `PTX-9.3-SHL-010`, `PTX-9.3-SHL-003`, `PTX-9.3-SHL-007`
- **Description:** The shl syntax is interpreted as destination/register-register-register only; source/form variance for `a` and especially `b` remains under-specified in source but is narrowed in the bounded Lean model.
- **Consequence:** Source-form flexibility (e.g., non-register sources if any exists in normative text) is intentionally not modeled, which is acceptable for boundedity only if explicitly accepted as a closed-world modeling choice.
- **Required owner for revision:** Spec Architect and Lean Formalizer
- **Human review required:** yes

## Theorem quality and proof strength
- No theorem weakening detected.
- The final theorem set (`4` declarations) is internally consistent with approved obligations in `theorems/obligations-v4.json`.
- No vacuity detected in `ShlB32_ShlB32Step_deterministic` (both `guardFalse` and `executed` constructors are live cases).

## Lean verification status
- `lean/Spec2Lean/PTX/ShlB32.lean`: **compile success** (`lean_check_file`, exitCode 0, warnings 0)
- `lean/Spec2Lean/PTX/ShlB32Proofs.lean`: **compile success** (`lean_check_file`, exitCode 0, warnings 21)
- `candidates/ptx/9.3/units/shl-b32/lean/ShlB32-v1.lean`: success
- `candidates/ptx/9.3/units/shl-b32/lean/ShlB32Proofs-v1.lean`: success

## Proof-bypass status
- No `sorry`, `admit`, new `axiom`, or `unsafe` declarations in final Lean artifacts reviewed.

## Readiness for human final approval
- **Not approved by this agent.**
- The unit is **eligible for explicit human final approval** pending resolution/acceptance of the two minor modeling questions above (especially open `N` definition and source-form narrowing), with no blocking technical defects.