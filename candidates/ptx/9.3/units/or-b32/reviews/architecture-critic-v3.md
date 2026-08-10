# Architecture Critique: `or.b32` (Review v3)

## 1) Status
- Reviewed artifact: `candidates/ptx/9.3/units/or-b32/architecture/foundation-v3.md`
- Stage: `ARCHITECTURE_CRITIQUE`
- Required source: `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html`
- Review decision: **REVISE**

## 2) Findings

### ARC-201 (MAJOR)
- **Affected artifact:** `candidates/ptx/9.3/units/or-b32/architecture/foundation-v3.md`
- **Location:** `Section 3, D-2 OrSource` lines 36-40; `Section 11 AM-1` lines 114-115
- **Evidence references:**
  - `logic-and-shift-instructions-or` lines 14298–14301 (`or.type d, a, b;`), 14319 (`or.b32  mask mask,0x00010001`)
  - `source-operands` lines 5331–5334 (`ALU operands ... must all be in variables declared in .reg`)
  - `integer-constants` lines 2078–2083
- **Description:**
  The architecture models both source operands as `OrSource` with a constructor for immediate (`srcImm`) on **either** `src1` or `src2`, but no evidence in the bounded source slice establishes immediate support for the first source position `a`. The only in-section `or.b32` example shows the immediate at the third operand position, and the instruction-operands normative text still requires ALU source variables in `.reg`.
  The artifact resolves this tension only as an ambiguity (`AM-1`) and assumption (`A-3`) but does not constrain position in the core constructor/theorems (or at least records it as a future question).
- **Consequence:**
  The bounded architecture permits extra program forms (e.g., immediate in position `a`) that may be outside the supported PTX operand discipline, creating unsound parser/typing obligations and weakening subsequent theorem fidelity.
- **Required owner for revision:** Spec Architect (with Gate A reviewers)
- **Human review required:** yes

### ARC-202 (NOTE)
- **Affected artifact:** `candidates/ptx/9.3/units/or-b32/architecture/foundation-v3.md`
- **Location:** `Section 10 D-6` lines 76-77
- **Evidence references:**
  - `logic-and-shift-instructions-or` (syntax/semantics) and `source-operands` / `integer-constants`
- **Description:**
  The architecture correctly avoids introducing an `Error` outcome, but the phrase “No explicit Error constructor is introduced...” is stated as part of the transition design without classifying this as an explicit assumption (it appears in assumptions list as A-2). This is a traceability/readability concern only; it is not blocking if Gate A is explicit about whether the “no-error” behavior is normative vs. assumed.
- **Consequence:**
  Mild risk of proof-stage drift if architects later treat absence of error as normative fact without explicit assumption.
- **Required owner for revision:** Spec Architect
- **Human review required:** no

## 3) Overall recommendation
Substantive revision required. Fixing `ARC-201` is required before this architecture can be marked ready for human Gate A.
