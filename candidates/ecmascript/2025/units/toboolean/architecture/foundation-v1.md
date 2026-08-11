# ECMAScript ToBoolean Foundation Architecture v1 — DRAFT — NOT HUMAN APPROVED

## 1. Scope
- Unit: `ToBoolean` (`toboolean`)
- Source: ECMAScript 2025 specification HTML
- Bounded scope: abstract operation semantics only (no control flow, no completion wrapping, no other conversion operations).
- This is a fresh foundation artifact for this unit; no previously approved ECMAScript architecture exists in this repository.

## 2. Official source facts
Document identity: `documents/sources/ecmascript/2025/raw/specification.html`, SHA-256 `6a28f9423133ed7b7c59a40baf620c2740f12f0bc9c251042f2a85b9cc5ed713`, version `2025`.

- **SF-TOB-1 (evidence status: read)** — Section **7.1.2 ToBoolean** (`sec-toboolean`, lines 5133-5137):
  *Signature*: `ToBoolean(argument)` takes an ECMAScript language value and returns a **Boolean**.
  *Algorithm*: if `argument` is a Boolean, return it; if `argument` is one of `undefined`, `null`, `+0𝔽`, `-0𝔽`, `NaN`, `0ℤ`, or empty String, return `false`; step 3 is replaced in B.3.6.1; otherwise return `true`.
- **SF-TOB-2 (evidence status: read)** — Section **7.1 type definitions** (`sec-ecmascript-language-types`, line 1981): ECMAScript language value types are `Undefined, Null, Boolean, String, Symbol, Number, BigInt, Object`.
- **SF-TOB-3 (evidence status: read)** — Boolean type section (`sec-ecmascript-language-types-boolean-type`, line 1999): Boolean has exactly two values `true` and `false`.
- **SF-TOB-4 (evidence status: read)** — Number type section (`sec-ecmascript-language-types-number-type`, line 2733): Number has both `+0𝔽` and `-0𝔽` values; `NaN` is a Number value.
- **SF-TOB-5 (evidence status: read)** — String type section (`sec-ecmascript-language-types-string-type`, line 2004): String is finite sequence of 16-bit units; empty string is a defined zero-length string.
- **SF-TOB-6 (evidence status: read)** — BigInt type section (`sec-ecmascript-language-types-bigint-type`, line 2945): BigInt is an integer-based ECMAScript language type; operations use `0ℤ` notation.
- **SF-TOB-7 (evidence status: read)** — Object type section (`sec-object-type`, line 3087): object-typed values are one of the ECMAScript language types and are used in the `is Object` checks.
- **SF-TOB-8 (evidence status: read)** — Web-compat note (`sec-IsHTMLDDA-internal-slot-to-boolean`, line 52830): ToBoolean step 3 is replaced by: if `argument` is an Object and has internal slot `[[IsHTMLDDA]]`, return `false`.
- **SF-TOB-9 (evidence status: read)** — B.3.6 prose says objects with `[[IsHTMLDDA]]` are host-defined and behave like `undefined` in ToBoolean, and are generally only the web-browser `document.all` object.

## 3. Proposed Lean architecture
### 3.1 Core category assumptions
- Introduce a shared ECMAScript value category `ECMAScriptValue` with at least constructors for `Undefined`, `Null`, `Boolean`, `Number`, `BigInt`, `String`, and `Object` (plus other types as needed by the host language package).
- Introduce a shared `ToBoolean` result type as Lean `Bool` (truth-value only).
- Model number-like constructors/decoders with distinguished recognizers for:
  - `isPosZero : Number → Bool`
  - `isNegZero : Number → Bool`
  - `isNaN : Number → Bool`
- Model strings with a decidable emptiness predicate (`isEmptyString`).

### 3.2 Proposed function shape
- Define:
  ```lean
  def toBoolean (v : ECMAScriptValue) : Bool :=
    match v with
    | Boolean b => b
    | Undefined => false
    | Null => false
    | Number n => if n.isPosZero || n.isNegZero || n.isNaN then false else true
    | BigInt z => if z = 0 then false else true
    | String s => if s.isEmpty then false else true
    | Object o =>
        if o.hasIsHTMLDDA then false else true
    | _ => true
  ```
  (exact pattern matching names are design choices)

### 3.3 Design choices for this artifact
- **D-1** — Encode step 3 replacement from `B.3.6.1` in the object branch before final default return.
- **D-2** — Make total return type `Bool` (no completion/throw form) because section 7.1.2 specifies direct Boolean return.
- **D-3** — Treat unknown future object kinds via their concrete object field `hasIsHTMLDDA : Prop/Bool`; this keeps the web-compat branch explicit and host-extensible.
- **D-4** — Keep `ToBoolean` as an *independent abstract operation* (no implicit coercions to language syntax or operator semantics in this unit).

## 4. Fact-to-design mapping
- SF-TOB-1 → function signature, ordered case structure, final-default `true` branch.
- SF-TOB-3 → result codomain `Bool` and `Boolean`-identity behavior.
- SF-TOB-4, SF-TOB-6 → numeric and BigInt zero checks for falsy literals `+0𝔽`, `-0𝔽`, `NaN`, `0ℤ`.
- SF-TOB-5 → empty-string branch uses emptiness predicate.
- SF-TOB-7, SF-TOB-8 → object branch with `is Object` and `hasIsHTMLDDA` test.
- SF-TOB-9 → explicit host-defined compatibility note in architecture assumptions, not a proof obligation.

## 5. Dependency graph
- `ToBoolean` depends on:
  - `ECMAScriptValue` type taxonomy (SF-TOB-2)
  - Boolean/Number/String/BigInt/Object semantics predicates (SF-TOB-3,4,5,6,7)
  - Host extension mechanism for `[[IsHTMLDDA]]` (SF-TOB-8, SF-TOB-9)
- `ToBoolean` is used by many downstream abstract operations/runtimes (e.g., conditionals, logical operators), but these are *out-of-scope dependencies* for this bounded unit.

## 6. Assumptions
- **A-1** — The notation `0ℤ` is implemented as the BigInt zero value; this is a notation-level interpretation not expanded in the 7.1.2 clause text.
- **A-2** — The internal implementation of Number equality predicates (`+0𝔽`, `-0𝔽`, `NaN`) is imported from the numeric-value model used in this project.
- **A-3** — Object internal slots are represented in Lean as an explicit predicate/field on object values.
- **A-4** — No other hidden web-compatibility branches for ToBoolean exist beyond section B.3.6.1 replacement step.
- **A-5** — Only the abstract operation itself is modeled here; no completion machinery, execution context, host hooks, or operator short-circuit behavior is introduced in this foundation.

## 7. Ambiguities
- **AMB-1** — The clause text does not define numeric API details for testing `+0𝔽`/`-0𝔽`/`NaN`; the design depends on shared numeric infrastructure.
- **AMB-2** — `0ℤ` vs `0` notation ambiguity: exact parser/pretty-printer mapping for integral literals is a shared arithmetic-design question.
- **AMB-3** — Whether host objects with `[[IsHTMLDDA]]` are modeled solely by a boolean field or richer object metadata is not fixed by this unit.

## 8. Open questions
- **OQ-1** — Should `toBoolean` be defined in a pure namespace-local file (`ToBoolean.lean`) or in a shared conversion package for reuse by operators? (not decided yet)
- **OQ-2** — What exact `ECMAScriptValue` constructors are required at this stage (full language model vs. minimal subset)?
- **OQ-3** — Should `Object`-slot tests be proposition-valued (`o.hasIsHTMLDDA : Prop`) or boolean-valued (`Bool`) in the shared Lean base?

## 9. Candidate theorem-obligation families
- **TF-1 (totality)**: `toBoolean` terminates and returns a `Bool` for all `ECMAScriptValue`.
- **TF-2 (Boolean identity)**: if `v` is `Boolean b`, then `toBoolean v = b`.
- **TF-3 (falsy cases)**: `toBoolean` returns `false` on `Undefined`, `Null`, Number `+0𝔽`, Number `-0𝔽`, Number `NaN`, BigInt zero, and empty string.
- **TF-4 (web-compat)**: if `v` is an object with `hasIsHTMLDDA`, then `toBoolean v = false`.
- **TF-5 (truthy default)**: for all other values, `toBoolean v = true` (including non-falsy Numbers, non-empty strings, non-HTMLDDA objects, and symbols/functions depending on value model).
- **TF-6 (no-completion behavior)**: `toBoolean` is a pure function producing immediate Bool rather than a completion record.

## 10. Evidence index
- SF-TOB-1: `7.1.2 ToBoolean`, anchor `sec-toboolean`, lines 5133–5137.
- SF-TOB-2: `6.1 ECMAScript Language Types`, anchor `sec-ecmascript-language-types`, line 1981.
- SF-TOB-3: `6.1.3 The Boolean Type`, anchor `sec-ecmascript-language-types-boolean-type`, line 1999.
- SF-TOB-4: `6.1.6.1 The Number Type`, anchor `sec-ecmascript-language-types-number-type`, lines 2733–2762.
- SF-TOB-5: `6.1.4 The String Type`, anchor `sec-ecmascript-language-types-string-type`, lines 2004–2015.
- SF-TOB-6: `6.1.6.2 The BigInt Type`, anchor `sec-ecmascript-language-types-bigint-type`, lines 2945–2948.
- SF-TOB-7: `6.1.7 The Object Type`, anchor `sec-object-type`, lines 3087–3094.
- SF-TOB-8: `B.3.6.1 Changes to ToBoolean`, anchor `sec-IsHTMLDDA-internal-slot-to-boolean`, lines 52830–52834.
- SF-TOB-9: `B.3.6 The [[IsHTMLDDA]] Internal Slot`, anchor `sec-IsHTMLDDA-internal-slot`, lines 52820–52827.

## 11. Gate A review checklist
- [ ] Artifact marked `DRAFT — NOT HUMAN APPROVED` and not in `accepted/`.
- [ ] Scope is limited to `ToBoolean` abstract operation and its direct web-compat replacement.
- [ ] All source claims are labeled `SF-*` with explicit anchor/line evidence.
- [ ] Architecture distinguishes fact → design mapping clearly.
- [ ] Candidate theorem obligations are non-vacuous and test meaningful behavior.
- [ ] Ambiguities and open questions are explicitly listed.
- [ ] Dependency graph includes type and object-slot assumptions used by this unit.
