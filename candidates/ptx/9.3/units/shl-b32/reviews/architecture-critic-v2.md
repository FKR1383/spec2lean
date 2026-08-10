# Architecture Critique (PTX `shl.b32`) v2

Scope reviewed: `candidates/ptx/9.3/units/shl-b32/architecture/foundation-v1.md` against PTX 9.3 source evidence.

## Finding F-ARC-1
- **Severity:** MAJOR
- **Affected artifact:** `architecture/foundation-v1.md`
- **Location:** `D-6` (line 49), `VAL-2`/`PRF-3` (lines 111-113, 121), and `OQ-B2` (line 144)
- **Evidence references:**
  - SF-SHL-2 (`logic-and-shift-instructions-shl`, lines 14705-14708)
  - Generic PTX operand format (`ptx-instructions`, lines 7517-7525, 7534)
- **Description:**
  The architecture states destination can be a bit-bucket `_` and adds a bit-bucket execution theorem (`PRF-3`) for `shl.b32`. However, the `shl` syntax is shown as `shl.type d, a, b;` (no `_` form), and the only source for optional destination is the generic statement "For some instructions" (not instruction-specific). This means optional destination is treated as a guaranteed feature of `shl` without evidence.
- **Consequence:**
  Could formalize behavior that may be non-applicable to `shl`, causing an incorrect parser/API contract and false theorem obligations.
- **Required owner for revision:** Spec Architect
- **Human review required:** yes

## Finding F-ARC-2
- **Severity:** MAJOR
- **Affected artifact:** `architecture/foundation-v1.md`
- **Location:** `D-11` and `ASS-3` (lines 54, 130)
- **Evidence references:**
  - SF-SHL-3, SF-SHL-4, SF-SHL-5 (`logic-and-shift-instructions-shl`, lines 14711-14720)
- **Description:**
  The design introduces additional shift modeling detail (`"b treated as unsigned amount", "clamped to N", and explicit fixed-32-bit result behavior/bit-domain) as if fully normative, but the source only states `d = a << b` and that `b` is a 32-bit value. There is no explicit statement in the cited evidence about result-domain wrap/bitvector-lift strategy in this instruction entry.
- **Consequence:**
  Risks semantic overcommitment in Lean mapping/theorems (e.g., stronger invariants than supported by spec text), especially around out-of-range shift and value-domain reduction behavior.
- **Required owner for revision:** Spec Architect + Language Architect
- **Human review required:** yes

## Finding F-ARC-3
- **Severity:** MINOR
- **Affected artifact:** `architecture/foundation-v1.md`
- **Location:** `D-4`/`D-3` and `D-3`/`D-22` consistency (lines 46, 45, 92)
- **Evidence references:**
  - SF-SHL-2 (`logic-and-shift-instructions-shl`, lines 14705-14707)
  - run target scope (`ShlB32` unit)
- **Description:**
  The artifact simultaneously says the bounded run is `shl.b32` while also encoding family typing set `{.b16,.b32,.b64}` as an active active-type set. This is potentially internally inconsistent unless clearly split into "family-level normalization" versus "unit-level enabled subtype".
- **Consequence:**
  Can lead to ambiguous parser/family constraints in later Lean architecture and mismatched obligations between unit and family.
- **Required owner for revision:** Spec Architect
- **Human review required:** yes

## Overall judgment
Substantive architecture issues remain. Revision required before Gate A readiness, specifically to resolve instruction-specific destination semantics and to align shift-domain claims strictly to sourced PTX text while documenting any intended modeling extension as explicit assumptions.
