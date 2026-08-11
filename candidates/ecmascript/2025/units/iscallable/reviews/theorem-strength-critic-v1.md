# IsCallable — Theorem Strength Critique v1

Validated obligation artifact: `candidates/ecmascript/2025/units/iscallable/theorems/obligations-v1.json`
Complete declaration count reviewed: 5
Declaration names reviewed:
- isCallable_non_object_false
- isCallable_object_with_call_true
- isCallable_object_without_call_false
- isCallable_equivalent_branch_predicate
- isCallable_is_boolean

## Review Scope

Independent review of theorem-strength and non-vacuity for the 5 complete declarations in `theorem_obligations[].lean_statement_sketch`.

## Findings

1. **Declaration completeness / coverage**
   - All five declarations are complete theorem statements with names and arities matching the supplied obligation contract.
   - No placeholders, truncations, or duplicate names were found.
   - The set covers the non-object branch, both object sub-branches, and the branch-equivalence characterization.

2. **Branch-strength check**
   - `isCallable_non_object_false` has the expected guard premise (`isObject = false`) and aligns with the `IsCallable` non-object branch.
   - `isCallable_object_with_call_true` and `isCallable_object_without_call_false` use the object predicate `o.hasCall` directly, matching the intended normalized `[[Call]]` branch split.
   - `isCallable_equivalent_branch_predicate` is the expected characterization over `isObject` and `hasCallInternalMethod`; no missing premise is apparent.

3. **Non-vacuity note**
   - `isCallable_is_boolean` is true for any `Bool`-valued function by construction (`IsCallable argument = true ∨ IsCallable argument = false`), so it is tautological and does not add semantic discriminating power beyond total codomain typing.

## Disposition
- BLOCKER: 0
- MAJOR: 0
- MINOR: 1
- NOTE: 0

- Pre-gate revision status: NO
- Readiness: READY_FOR_THEOREM_STRENGTH_APPROVAL