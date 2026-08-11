# ToBoolean Lean Mapping Critique v1

## Decision
- **Outcome classification:** MINOR/NOTE-only findings
- **Pre-gate revision required:** No (no unresolved BLOCKER/MAJOR)
- **Recommended gate transition:** WAITING_GATE_C

## Counts
- `BLOCKER: 0`
- `MAJOR: 0`
- `MINOR: 1`
- `NOTE: 1`

## 1) Branch-complete mapping check vs approved semantics

| Step / semantic case | Lean mapping | Branch behavior | State | Error | Host/target | Coverage
|---|---|---|---|---|---|---|
| Boolean `b` | `EcmaValue.boolean b => toBooleanBool b` | returns corresponding bool | reads argument tag/payload | none | none | matches `ECMASCRIPT-TOB-SEM-002` |
| `Undefined` | `EcmaValue.undefined => false` | false | reads value tag | none | none | matches `ECMASCRIPT-TOB-SEM-003` |
| `Null` | `EcmaValue.null => false` | false | reads value tag | none | none | matches `ECMASCRIPT-TOB-SEM-003` |
| Number falsy (`+0`,`-0`,`NaN`) | `EcmaValue.number n` + `numberIsFalsy` | false iff constructor is falsy class | reads number payload | none | none | matches `ECMASCRIPT-TOB-SEM-003` |
| Number others | `EcmaValue.number n` + predicate false | true | reads number payload | none | none | matches step-4 default |
| BigInt zero | `EcmaValue.bigInt z` with `z=0` | false | reads bigint payload | none | none | matches `ECMASCRIPT-TOB-SEM-003` |
| BigInt others | `EcmaValue.bigInt z` with `z≠0` | true | reads bigint payload | none | none | matches `ECMASCRIPT-TOB-SEM-005` |
| Empty string | `EcmaValue.string s` with `s.isEmpty` | false | reads string payload | none | none | matches `ECMASCRIPT-TOB-SEM-003` |
| Non-empty string | `EcmaValue.string s` with `¬isEmpty` | true | reads string payload | none | none | matches step-4 default |
| Symbol | `EcmaValue.symbol _ => true` | true | reads value tag | none | none | matches branch-completeness default |
| Object with `hasIsHTMLDDA` | `EcmaValue.object o` + `if o.hasIsHTMLDDA` | false | reads object slot | none | host-defined slot availability only | matches `B.3.6.1` replacement |
| Object without slot | `EcmaValue.object o` + else | true | reads object payload | none | host-defined slot only | matches `ECMASCRIPT-TOB-SEM-005` |

No completion/throw states, no state writes, and no guard/no-op ambiguity appears in this formalization.

## 2) Findings

- **MINOR-1:** The local numeric constructor `EcmaNumber.nonZero : Int → EcmaNumber` does not enforce a nonzero invariant, so `EcmaNumber.nonZero 0` is representable and would map to `true` for 0; this is a model-invariant gap (can be accepted if invariant is part of higher-level object contract).
- **NOTE-1:** The mapping returns Lean `Bool` via `EcmaBoolean`-to-`Bool` conversion function, consistent with the unit architecture, but it is therefore not a one-to-one embedding of the local `EcmaBoolean` constructor in the public API.
