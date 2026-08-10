# Theorem-Strength Critique (PTX `shl.b32`) v1

Scope reviewed: `theorems/obligations-v3.json` against approved semantics and Lean mapping.

## Overall verdict
The theorem set is not yet ready for theorem-strength approval.

### Finding STRG-1
- **Severity:** MAJOR
- **Affected artifact:** `candidates/ptx/9.3/units/shl-b32/theorems/obligations-v3.json`
- **Location:** `theorem_obligations[1]` (`PTX-SHL-THM-302`) line 155 (`lean_statement_sketch` and `proof_strategy_hint`)
- **Evidence references:**
  - `obligations-v3.json` PTX-SHL-THM-302 statement/sketch/intent (lines 150-162)
  - Lean relation/function definitions: `execShlB32` and `ShlB32Step` in `lean/ShlB32-v1.lean` lines 119-137
  - Semantic claim PTX-SHL-SEM1-008 (guard false path is no-op)
- **Description:**
  `ShlB32_execShlB32_iff_step` is named/intented as a full correspondence theorem for function/relational semantics (including `executed`, `guardFalse`, and `none` branches), but the actual Lean statement only says
  `execShlB32 s i = some (ExecOutcome.executed s') ↔ ShlB32Step s i s'`.
  This is not equivalent: when `evalGuard` is false and `s' = s`, RHS is true via `ShlB32Step.guardFalse` while LHS is false.
- **Consequence:**
  The obligation is internally inconsistent with PTX predication semantics and cannot be proved as stated for all `s'`; proof generation would either fail or force an incorrect interpretation of the theorem.
- **Required owner for revision:** Lean Formalizer (theorem-generation) + Proof Engineer
- **Human review required:** no

## Recommendation
Revise this entry into explicit, branch-correct obligations, e.g. separate lemmas for:
1) executed outcomes equivalence under `some (ExecOutcome.executed s')`,
2) guard-false equivalence to `s' = s`, and
3) none/partial-completeness (no step exists).
