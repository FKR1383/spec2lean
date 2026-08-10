# Architecture Critique — and.b16

## Findings

### F-ARC-1 (MAJOR)
- **Severity:** MAJOR
- **Affected artifact:** `candidates/ptx/9.3/units/and-b16/architecture/foundation-v1.md`
- **Location:** `D-B2` (lines 36–39)
- **Evidence references:**
  - `and` section example only shows an immediate in the third operand position: `and.b32 sign,fpvalue,0x80000000` (source lines 14285–14286).
  - General syntax is `and.type d, a, b;` (source lines 14263–14266).
  - No source text in the bounded section states that `a` may be immediate.
- **Description:** The architecture asserts "optional constant-immediate source(s)" without evidence for immediate in first source position.
- **Consequence:** Lean parsing/typing may accept instruction forms not grounded in evidence (`and.b16 d, 0x1, x`) and later semantic obligations may be proved for unsupported syntax.
- **Required owner for revision:** Spec Architect (Gate A artifact owner)
- **Human review required:** Yes

### F-ARC-2 (MAJOR)
- **Severity:** MAJOR
- **Affected artifact:** `candidates/ptx/9.3/units/and-b16/architecture/foundation-v1.md`
- **Location:** `D-B3` and `PRF-4` (lines 38 and 91)
- **Evidence references:**
  - PTX instruction format section: "For instructions that create a result value, the `d` operand is the destination ..." and "For some instructions the destination operand is optional. A bit bucket `_` may be used..." (source lines 7526–7535).
  - No explicit per-instruction `and.b16` restriction is introduced that forbids `_`; only an OPEN QUESTION (`OQ-B2`) notes uncertainty.
- **Description:** The architecture simultaneously restricts bounded syntax to explicit `d,a,b` (`D-B3`) and later requires proof obligations for bit-bucket discard (`PRF-4`).
- **Consequence:** Inconsistent commitment in this stage leaves `and.b16` operand shape underspecified and can cause architecture-to-proof traceability failure.
- **Required owner for revision:** Spec Architect (Gate A artifact owner)
- **Human review required:** Yes

## Disposition
- BLOCKER: 0
- MAJOR: 2
- MINOR: 0
- NOTE: 0
- Pre-gate revision required: **YES**

## Routing recommendation
- Stage: `ARCHITECTURE`
- Next orchestrator stage: `REVISE`
