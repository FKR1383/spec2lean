# ECMAScript IsCallable Foundation Architecture v1 — DRAFT — NOT HUMAN APPROVED

## 1. Scope
- Unit: `IsCallable` (`iscallable`)
- Source: ECMAScript 2025 specification, `documents/sources/ecmascript/2025/raw/specification.html` (SHA-256 `6a28f9423133ed7b7c59a40baf620c2740f12f0bc9c251042f2a85b9cc5ed713`), version `2025`
- Bounded task: formalize only the abstract operation **IsCallable** in isolation; no `Call`, `Construct`, completion-record plumbing, or runtime execution machinery is introduced here.
- No previously human-approved ECMAScript architecture exists to reuse as shared package for this unit.

## 2. Official source facts
- **SF-ISC-1 (evidence status: read):** Section **7.2.3 IsCallable** (`sec-iscallable`, lines 5790–5794) defines:
  - `IsCallable(argument)` takes an `ECMAScript language value` and returns a `Boolean`.
  - Step 1: if `argument` is not an Object, return `false`.
  - Step 2: if `argument` has a `[[Call]]` internal method, return `true`.
  - Step 3: return `false`.
  - This section states purpose as “determines if argument is a callable function with a [[Call]] internal method.”
- **SF-ISC-2 (evidence status: read):** Section **6.1.7 Object Type** (`sec-object-type`, lines 3087–3104) defines “is an Object” and characterizes Object as the object type used by algorithms in later clauses.
- **SF-ISC-3 (evidence status: read):** Section **6.1 ECMAScript Language Types** (`sec-ecmascript-language-types`, lines 1981–1987) enumerates language types, including `Object` and `Object` as an ECMAScript language type.
- **SF-ISC-4 (evidence status: read):** Section **6.1.7.2 Object Internal Methods and Internal Slots** (`sec-object-internal-methods-and-internal-slots`, around lines 3243–3291) states that object behavior is by internal methods, and objects may have `[[Call]]`; an ordinary object uses one of the specified `[[Call]]` algorithms when it has such a method.
- **SF-ISC-5 (evidence status: read):** Section **7.2.2 IsArray** (`sec-isarray`, line 5784 onward) uses the same “If argument is not an Object …” and internal-method-style branching style, confirming the common pattern used by this group of abstract operations and supporting interpretation of IsCallable's guard form as a pure type test.

## 3. Proposed Lean architecture
### 3.1 Core categories and interfaces
- Introduce `namespace Spec2Lean.ECMAScript.IsCallable`.
- Introduce/assume an existing shared ECMAScript value category:
  - `ECMAScriptValue` (or equivalent shared alias) with constructor/predicate for `Object`-typed values.
- Introduce predicate(s):
  - `isObject : ECMAScriptValue → Bool` (or equivalent)
  - `hasCallInternalMethod : ECMAScriptValue → Bool` (or for object subtype only)
- Define a pure function:
  - `def isCallable (argument : ECMAScriptValue) : Bool := ...`

### 3.2 Suggested definition shape
```lean
/-- ECMAScript abstract operation IsCallable -/
 def isCallable (argument : ECMAScriptValue) : Bool :=
   if h : isObject argument then
     hasCallInternalMethod argument
   else
     false
```
Alternative equivalent form using match on value constructor is also acceptable, but must preserve exact branch ordering from SF-ISC-1.

### 3.3 Design choices for this artifact
- **D-1 (required):** Keep `IsCallable` a total, pure `Bool` function with no completion record.
- **D-2:** Model “has a [[Call]] internal method” as an explicit predicate on objects (`hasCallInternalMethod`) rather than deriving from a finite object constructor; this preserves polymorphism of exotic and ordinary objects.
- **D-3:** Treat `isObject` as an externalized language-type classification from the shared value model; do not hardcode which concrete object constructors are callable inside this unit.

## 4. Fact-to-design mapping
- SF-ISC-1 → `isCallable : ECMAScriptValue → Bool`, non-completion API shape.
- SF-ISC-1 step 1 → branch condition `if isObject argument then ... else false`.
- SF-ISC-1 step 2 → `hasCallInternalMethod` predicate for call capability and immediate `true` branch.
- SF-ISC-1 step 3 + step flow → fallback return `false`.
- SF-ISC-2 + SF-ISC-3 → domain type and object guard interpretation.
- SF-ISC-4 → predicate-oriented handling of internal methods and explicit non-exhaustive callability.

## 5. Dependency graph
- `isCallable` depends on:
  - shared `ECMAScriptValue`/type taxonomy (`Object` included), and object test predicate
  - shared object metadata/internals abstraction exposing `hasCallInternalMethod`
- `isCallable` is used by:
  - `OrdinaryHasInstance`, function-call sites (`apply`, `call`, `bind`), accessors, and other operations that gate by callability (all used by this unit only as downstream dependencies, not defined here).

## 6. Assumptions
- **A-1:** The project-wide shared Lean model has a total decidable object-type classification for values.
- **A-2:** The shared object model exposes (or can expose in a host-independent way) whether an object has a `[[Call]]` internal method.
- **A-3:** The predicate `hasCallInternalMethod` is defined at the proper abstraction level for this unit (does not depend on later invocation semantics).
- **A-4:** No completion wrapping is required for this AO because the source text defines it as returning a Boolean directly.

## 7. Ambiguities
- **AMB-1:** The source does not enumerate all object kinds with/without `[[Call]]`; this is intentionally abstracted to `hasCallInternalMethod`.
- **AMB-2:** Whether `hasCallInternalMethod` is a field, typeclass property, or theorem is open at the architecture level and depends on shared value representation.
- **AMB-3:** The exact placement of this definition within existing module boundaries (separate `IsCallable.lean` vs shared conversion module) is undecided.

## 8. Open questions
- **OQ-1:** Should `isObject` be a direct inductive constructor predicate on `ECMAScriptValue` or a separate typeclass-style coercion layer from a shared object representation?
- **OQ-2:** Should `hasCallInternalMethod` live in this file or be imported from a shared `InternalMethod` abstraction used by other AOs like `IsConstructor`?
- **OQ-3:** Is there an existing notation policy (`Bool` vs `Prop`) for internal-method existence predicates that should be aligned across units?

## 9. Candidate theorem-obligation families
- **TF-1 (totality):** `isCallable` is defined for all `ECMAScriptValue` and returns `Bool`.
- **TF-2 (non-object falsity):** If `isObject argument = false`, then `isCallable argument = false`.
- **TF-3 (call-method truth):** If `isObject argument = true` and `hasCallInternalMethod argument = true`, then `isCallable argument = true`.
- **TF-4 (default falsity):** If `isObject argument = true` and `hasCallInternalMethod argument = false`, then `isCallable argument = false`.
- **TF-5 (consistency):** `isCallable` matches the 3-step textual structure exactly (guard → call-check → false).

## 10. Evidence index
- SF-ISC-1: `sec-iscallable`, lines 5790–5794.
- SF-ISC-2: `sec-object-type`, lines 3087–3090.
- SF-ISC-3: `sec-ecmascript-language-types`, lines 1982–1987.
- SF-ISC-4: `sec-object-internal-methods-and-internal-slots`, lines 3243–3291.
- SF-ISC-5: `sec-isarray`, lines 5784–5787 (comparative abstract-op style).

## 11. Gate A review checklist
- [ ] Artifact marked `DRAFT — NOT HUMAN APPROVED` and stored under `candidates/` only.
- [ ] Scope limited to `IsCallable` (no unrelated unit semantics).
- [ ] All source claims are explicitly labeled `SF-*` with evidence status.
- [ ] Fact-to-design mapping table is complete and explicit.
- [ ] Proposed Lean shape does not weaken or alter branch order/return values from the source.
- [ ] Assumptions, ambiguities, and open questions are explicitly separated.
- [ ] Candidate theorem obligations are non-vacuous and unit-specific.
- [ ] Evidence index includes section anchor/line granularity and source identity/version.
