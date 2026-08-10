# Architecture Critique (PTX `shr.b32`) v1

Scope reviewed: `candidates/ptx/9.3/units/shr-b32/architecture/foundation-v1.md` against PTX 9.3 official evidence.

## Overall verdict
No blocking issues were found in this architecture revision. The artifact is materially traceable to PTX source and suitably bounded for `shr.b32`. It is suitable to proceed to human Gate A review.

## Finding ARC-SHR-ARCH-1
- **Severity:** NOTE
- **Affected artifact:** `architecture/foundation-v1.md`
- **Location:** `Section 9 (Proposed Lean architecture)`, `D-9` and `Section 10 (Candidate theorem-obligation families)`, `PRF-4`
- **Evidence references:**
  - `logic-and-shift-instructions-shr` (lines 14746-14758): signed- vs unsigned-fill wording is tied to the active `shr.type` family members.
- **Description:**
  The bounded artifact fixes the active unit to `.b32`, but PRF-4 also states fill behavior for signed and unsigned families (`.s16/.s32/.s64` and others). This over-describes `shr.b32` and can unintentionally force downstream proofs to reason about behaviors that are syntactically unavailable for this bounded construct.
- **Consequence:**
  Not blocking for this stage, but it weakens traceability of obligations to the bounded constructor if later treated literally. Prefer to restrict PRF-4 semantics to the bounded active family (`.b32`) and isolate signed-family behavior to family-wide variants.
- **Required owner for revision:** Spec Architect
- **Human review required:** no

## Finding ARC-SHR-ARCH-2
- **Severity:** NOTE
- **Affected artifact:** `architecture/foundation-v1.md`
- **Location:** `Section 4 (Proposed Lean architecture)`, `D-4`; `Section 10`, `PRF-2`
- **Evidence references:**
  - `ptx-instructions` (lines 7534-7535): optional destination `_` exists as a generic instruction rule.
- **Description:**
  D-4 says destination is required, while PRF-2 already includes a branch for no-destination behavior if `_` is adopted. This mixes current bounded commitment with a future extension in a single theorem family without an explicit conditional guard.
- **Consequence:**
  Non-blocking design drift; theorem families should either keep `_`-destination behavior explicitly conditional on an approved parsing rule extension, or keep PRF-2 restricted to the required-destination variant.
- **Required owner for revision:** Spec Architect and Spec Architect reviewer coordination
- **Human review required:** no

## Disposition
- **BLOCKER:** 0
- **MAJOR:** 0
- **MINOR:** 0
- **NOTE:** 2

Pre-gate revision required: **No**.

**Human gate readiness:** proceed to `WAITING_GATE_A` (architectural review ready; do not self-approve Gate A).