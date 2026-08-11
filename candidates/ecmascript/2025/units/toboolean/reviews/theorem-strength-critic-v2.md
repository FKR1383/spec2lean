# Theorem Strength Critique v2

Validated obligation artifact: `candidates/ecmascript/2025/units/toboolean/theorems/obligations-v2.json`
Complete declaration count reviewed: 5
Declaration names reviewed:
- toBoolean_boolean_identity
- toBoolean_falsy_primitive_cases
- toBoolean_object_isHTMLDDA_falsey_branch
- toBoolean_truthy_default_branch
- toBoolean_false_iff_falsy_cases

## Counts
- `BLOCKER: 0`
- `MAJOR: 1`
- `MINOR: 0`
- `NOTE: 0`

## Pre-gate revision status
- REVISE (THEOREM_GENERATION)

## Findings

1. **MAJOR-1: missing falsy boolean-false case in iff characterization**

`toBoolean_false_iff_falsy_cases` omits `EcmaValue.boolean EcmaBoolean.false` from the right-hand side, but definition/semantics require `ToBoolean (EcmaValue.boolean EcmaBoolean.false) = false` (by `toBooleanBool`).

Minimal Lean counterexample (from `ToBoolean` definition):
- take `argument := EcmaValue.boolean EcmaBoolean.false`.
- `ToBoolean argument = false` reduces to `toBooleanBool EcmaBoolean.false = false`.
- right side of the equivalence is false, since it has no boolean constructor branch and no existential matches.

Therefore the theorem as stated is false and over-prunes the falsy partition.
