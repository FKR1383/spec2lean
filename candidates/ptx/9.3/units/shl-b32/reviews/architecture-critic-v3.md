# Architecture Critique (PTX `shl.b32`) v3

Scope reviewed: `candidates/ptx/9.3/units/shl-b32/architecture/foundation-v2.md` against PTX 9.3 evidence.

## Finding ARC-1
- **Severity:** MAJOR
- **Affected artifact:** `architecture/foundation-v2.md`
- **Location:** `D-6` (line 49), `D-8` (line 86), `D-P2` and `PRF-3`-related assumptions (lines 44, 79, 85)
- **Evidence references:**
  - SF-SHL-1 / `logic-and-shift-instructions-shl` (PTX HTML, lines 14697–14730)
- **Description:**
  The architecture includes bit-bucket `_` as a live destination option (`dst` is register-or-`_`) and defines behavior for it, but the `shl` unit syntax shown in sources is `shl.type d, a, b;` with required `d`. The generic optional-destination clause is only stated as applying to *some* instructions, and no source evidence is provided tying that to `shl` specifically in this artifact.
- **Consequence:**
  This is a parser/API and execution semantic commitment that may permit an instruction form not justified by the `shl` entry, causing false positives in typing/validation and mismatched Lean definitions.
- **Required owner for revision:** Spec Architect
- **Human review required:** yes

## Finding ARC-2
- **Severity:** MAJOR
- **Affected artifact:** `architecture/foundation-v2.md`
- **Location:** `D-5` (line 46), `D-10` (line 46), `D-11` (line 54), `ASS-4`/`ASS-4b` (lines 117,121)
- **Evidence references:**
  - SF-SHL-3 (`logic-and-shift-instructions-shl`, lines 14711–14712)
  - SF-SHL-4 (`logic-and-shift-instructions-shl`, lines 14713–14715)
  - SF-SHL-5 (`logic-and-shift-instructions-shl`, lines 14718–14720)
- **Description:**
  The design/assumptions harden the shift result model to a fixed `.b32` bit-domain and a masking/clamping strategy not explicitly specified by these clauses. The source only states `d = a << b` and that shift counts > N are clamped to N; it does not normatively specify full destination-domain reduction semantics, modulo behavior, or numeric encoding policy.
- **Consequence:**
  Risk of over-constrained Lean semantics and theorem statements that are stronger than PTX text permits (especially for out-of-range values and representation-level behavior).
- **Required owner for revision:** Spec Architect + Lean Formalizer
- **Human review required:** yes

## Finding ARC-3
- **Severity:** MINOR
- **Affected artifact:** `architecture/foundation-v2.md`
- **Location:** `D-3` and `D-4` (lines 39, 46), fact-to-design mappings `SF-SHL-4`/`VAL-1` family mapping (line 52)
- **Evidence references:**
  - SF-SHL-2 (`logic-and-shift-instructions-shl`, lines 14697–14730)
- **Description:**
  The architecture states a unit-bounded `.b32` run while simultaneously treating family-level metadata for `.b16/.b32/.b64` as active design context; some obligations still refer to active-type membership and family-level typing in a way that can be read as requiring family-type processing for this single-unit unit.
- **Consequence:**
  Could induce unnecessary ambiguity in later validation/theorem obligations between per-unit and family constraints, especially for parser and typing checks.
- **Required owner for revision:** Spec Architect
- **Human review required:** yes

## Overall judgment
Substantive architecture issues remain. Revision required before Gate A readiness. The main blockers are unsupported optional-destination support and overcommitted fixed-width shift-domain behavior relative to explicit PTX prose.
