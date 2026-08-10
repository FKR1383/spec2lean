# Architecture Critique (PTX `shl.b32`) v5

Scope reviewed: `candidates/ptx/9.3/units/shl-b32/architecture/foundation-v4.md` against PTX 9.3 source evidence and prior review state.

## Overall verdict
No stage-blocking blockers were identified. The artifact is substantially cleaner than prior revisions and mostly bounded. One non-blocking modeling refinement is still needed before Gate A.

## Finding ARC5-1
- **Severity:** MINOR
- **Affected artifact:** `architecture/foundation-v4.md`
- **Location:** `D-5`, `D-O2` (lines 53, 98), and supporting evidence index entries `SF-INS-SHL-1`.
- **Evidence references:**
  - SF-SHL-1 (`logic-and-shift-instructions-shl`, lines 14705–14720): defines syntax/typing relation but does **not** specify source-operand form classes for `a`/`dst` beyond size/type constraints.
- **Description:**
  The architecture hard-codes `dst` and `srcA` to scalar `.reg`-declared registers with compatibility checks, while explicitly leaving `srcB` open. The same parsing uncertainty exists for `srcA` if `shl` permits a non-register source form in full grammar, but that uncertainty is not recorded as an ambiguity or assumption. This is a source-coverage mismatch (unified register-only claim for one source with no explicit backing in bounded evidence).
- **Consequence:**
  Potential under-approximation of legal operand forms for this bounded unit; validator/preconditions may reject additional source forms and proof families may become accidentally narrow.
- **Required owner for revision:** Spec Architect (and Lean Formalizer at stage boundary).
- **Human review required:** yes

## Finding ARC5-2
- **Severity:** NOTE
- **Affected artifact:** `architecture/foundation-v4.md`
- **Location:** `D-9`, `D-P1/D-P2`, and `OQ-3` (lines 63, 104–106, 135).
- **Evidence references:**
  - SF-PRED-1 (`predicated-execution`, lines 7547–7549): optional guard syntax/intent.
  - SF-PRED-2 (`instructions`, lines 8722–8723): all instructions may be predicated.
  - SF-PRED-3 (`control-flow-instructions-at`, lines 21838–21839): explicit "false predicate do nothing" wording for `@` form.
- **Description:**
  Guard-false no-op behavior in this architecture is justified in part by control-flow-specific section wording. That section is not itself the generic predication definition for all instructions, so the mapping should be explicitly labeled as an assumption/interpretation (not as a direct consequence).
- **Consequence:**
  Avoids over-claiming a normative consequence from a sibling section and keeps predication proof obligations traceable to the intended interpretation.
- **Required owner for revision:** Spec Architect.
- **Human review required:** no

## Gate A readiness
The architecture is close to Gate-A-ready. It is suitable for human review, but with the above non-blocking refinement request, this run should remain in `REVISE` state for a follow-up Architecture revision.