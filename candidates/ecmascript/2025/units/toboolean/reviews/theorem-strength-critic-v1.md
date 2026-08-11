# Theorem Strength Critique v1

Validated obligation artifact: `candidates/ecmascript/2025/units/toboolean/theorems/obligations-v1.json`
Complete declaration count reviewed: 5
Declaration names reviewed:
- toBoolean_boolean_identity
- toBoolean_falsy_primitive_cases
- toBoolean_object_isHTMLDDA_falsey_branch
- toBoolean_truthy_default_branch
- toBoolean_is_total_function

## Counts
- `BLOCKER: 0`
- `MAJOR: 2`
- `MINOR: 0`
- `NOTE: 0`

## Pre-gate revision status
- REVISE (THEOREM_GENERATION)

## Findings

1. **MAJOR-1: under-strong default-branch theorem**
`toBoolean_truthy_default_branch` is labeled as the "default truthy branch" obligation but proves only a small set of sample witnesses (`true`, `nonZero 1`, `bigInt 1`, `"x"`, one symbol, one object). It does not establish the branch-intent stated in the obligation ("all" non-falsy/default values) and therefore does not cover constructor classes like other non-zero numbers or additional string/object cases.

2. **MAJOR-2: vacuous totality claim over Bool codomain**
`toBoolean_is_total_function` states `ToBoolean argument = true ∨ ToBoolean argument = false` for all `argument : EcmaValue`. Because `ToBoolean` is already defined/typed as `Bool`, this is a tautological totality check and does not provide additional semantic/non-vacuity evidence. A minimal Lean probe reduces it to a case split on `ToBoolean argument` with no dependence on `argument`.

