# IsCallable — Semantic Critique v1

## Review Scope
Independent critique of `candidates/ecmascript/2025/units/iscallable/semantics/semantics-v1.json` against source bundle
`ecmascript-2025-iscallable-source-bundle-v1` and architecture draft.

## Findings

1. **Evidence alignment check passed**
   - All `SOURCE_FACT` claims in semantics-v1 reference fragment IDs from the source bundle (`ECMASCRIPT-2025-ISC-001` … `ECMASCRIPT-2025-ISC-007`) and align to the quoted clause lines in the bundle.
   - Core claims 002/003/004/005 exactly match the three steps of §7.2.3:
     - non-Object → `false`
     - `[[Call]]` present → `true`
     - otherwise `false`

2. **Branch/order fidelity**
   - Branch ordering in `semantic_pseudocode` is faithful to source: Object-type guard first, then call-internal-method check, then fallthrough `false`.
   - Output remains `Boolean` with no completion value wrappers.

3. **Compact behavior matrix**

| Argument category | Guard / check | Returned value | Error/throw | State effect | Host variation |
|---|---|---:|---|---|---|
| Non-Object ECMAScript language value (Undefined/Null/Boolean/String/Symbol/Number/BigInt) | `Is not an Object` | `false` | none | read-only observation only | none |
| Object with `[[Call]]` internal method | `is Object` then `has [[Call]]` | `true` | none | read-only observation only | none |
| Object without `[[Call]]` internal method | `is Object` then no `[[Call]]` | `false` | none | read-only observation only | none |
| Out-of-domain value (not an ECMAScript language value) | not representable from declared input type | no source-defined branch | none | none | none |

4. **Exceptions / UB / implementation-defined behavior**
   - No exceptional completion, undefined behavior, or implementation-defined behavior is stated in this AO definition; this is consistent with the source text and correctly marked as `not_explicitly_stated` in this bounded interpretation.

5. **State and determinism**
   - No writes are required by the AO text; determinism is total over the declared input domain (Boolean output).

6. **Open questions / design dependency checks**
   - `open_questions` is correctly scoped: precise object-subtype set with `[[Call]]` is external to this AO and must come from shared object/internal-method infrastructure.
   - `assumptions` entry `A-1` is an explicit local modeling assumption; it should be carried into Lean mapping stage as a dependency assumption, not a source fact.

## Disposition
- BLOCKER: 0
- MAJOR: 0
- MINOR: 0
- NOTE: 1

- Pre-gate revision status: NO
- Readiness: READY_FOR_HUMAN_GATE_B (do not approve; semantics interpretation is consistent and non-blocking issues only)
