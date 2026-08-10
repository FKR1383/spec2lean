# Theorem-Strength Critique (PTX `shl.b32`) v2

Scope reviewed: `theorems/obligations-v4.json` against approved semantics and Lean mapping (`lean/ShlB32-v1.lean`).

## Overall verdict
Adequate. No additional theorem-strength blockers found. The obligation set now appears branch-safe, non-conflating guard-false, executed, and none outcomes.

## Findings

### Findings: none

- `PTX-SHL-THM-401` is a valid determinism claim for the `ShlB32Step` relation and is non-vacuous in principle (both `executed` and `guardFalse` constructors exist in the bounded relation).
- `PTX-SHL-THM-402` correctly restricts correspondence to the executed function branch and avoids the previous false-guard mismatch.
- `PTX-SHL-THM-403` and `PTX-SHL-THM-404` jointly partition the non-executed cases (`guardFalse` vs `none`) and give appropriate inverse directions.

## Routing
Set is suitable for human theorem-strength approval review.

- **Required owner for revision:** none
- **Human review required:** yes
