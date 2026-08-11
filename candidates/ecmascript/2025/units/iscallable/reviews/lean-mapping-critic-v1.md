# IsCallable — Lean Mapping Critique v1

## Review Scope
Independent critique of `candidates/ecmascript/2025/units/iscallable/lean/IsCallable-v1.lean` against the approved semantics artifact
`candidates/ecmascript/2025/units/iscallable/semantics/semantics-v1.json`.

## Findings

1. **Function-level mapping is faithful**
   - `def IsCallable` exactly matches the three-step AO control flow:
     - non-`Object` branch returns `false` (step 1),
     - object branch delegates to `hasCallInternalMethod` (step 2),
     - otherwise returns `false` (step 3).
   - Mapping references claim IDs that align with the approved semantic claims:
     `ECMASCRIPT-ISC-SEM-002`, `...-003`, `...-004`, `...-005`.

2. **Executable branch coverage and determinism**
   - All executable branches in the mapping are: `non-Object`, `Object ∧ hasCall`, `Object ∧ ¬hasCall`.
   - This is behaviorally complete over the declared Lean input type (`EcmaValue`) and deterministic with total `Bool` output.
   - There are no implicit branches that change completion or state.

3. **State model / effects**
   - `IsCallable` in Lean performs pure computations (`if`/pattern matching) over its input and writes no state.
   - This matches the approved semantics' read-only/no-update behavior.

4. **Predication/guard / error/completion behavior**
   - Guard (`isObject`) is represented explicitly by `isObject`.
   - No exception/throw/abort/completion path is introduced in Lean; no host/target condition is modeled, matching the semantics matrix.

5. **Representation and provenance consistency**
   - The lean carrier `EcmaObject` and `EcmaValue` are locally scoped and sufficiently abstract for this AO.
   - `hasCallInternalMethod` is a deterministic predicate and aligns with the semantics’ abstracted call-method test and `A-1` assumption (object-callability modeling is normalized to a predicate).
   - No new semantics were introduced beyond the approved claims.

## Disposition
- BLOCKER: 0
- MAJOR: 0
- MINOR: 0
- NOTE: 1

- Pre-gate revision status: NO
- Readiness: READY_FOR_HUMAN_GATE_C (do not approve Gate C.)
