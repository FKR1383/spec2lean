# PTX `shl.b32` Foundation Architecture v2 — DRAFT (UNAPPROVED)

## 1) Scope

- **DESIGN CHOICE (SC-1):** Language-wide architecture is bounded to the PTX ISA 9.3 instruction unit `shl.b32`.
- **DESIGN CHOICE (SC-2):** Includes instruction form, operands, typing, predicate guards, minimal register/predicate state, execution relation, and version/target metadata for `shl.b32`.
- **DESIGN CHOICE (SC-3):** Excludes control-flow instructions, memory/surface state spaces, scheduling, synchronization, and whole-program semantics.
- **DESIGN CHOICE (SC-4):** No Lean code, parser implementation, theorem statements, or proofs are introduced in this stage.

## 2) Official source facts

Source identity and hashes:
- PTX ISA HTML: `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` (SHA-256 `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`).
- Source manifest: `documents/sources/nvidia/ptx/9.3/source-manifest.json` (SHA-256 `622e6ce0d3114a909a62726530955993b5f2b98d2f60e45ae1ceb429512208f2`).
- Hash index: `documents/sources/nvidia/ptx/9.3/SHA256SUMS` (SHA-256 `e02f4feadfce614282d3d4774ed21dd87985202d4ea9ad84ead60c688a6c0ecd`).

- **SF-SHL-1 (direct):** `logic-and-shift-instructions-shl` (PTX 9.3, lines 14697–14730): grammar `shl.type d, a, b;` with `.type = { .b16, .b32, .b64 }`.
- **SF-SHL-2 (direct):** same section (lines 14711–14712): `Shift a left, zero-fill on right` and `Shift a left by the amount specified by unsigned 32-bit value in b`.
- **SF-SHL-3 (direct):** same section (lines 14714–14715): semantics `d = a << b;`.
- **SF-SHL-4 (direct):** same section (lines 14718–14720): shift amounts greater than register width `N` are clamped to `N`; destination and first source sizes must match; `b` must be 32-bit regardless of instruction type.
- **SF-SHL-5 (direct):** same section (lines 14721–14724): PTX notes `Introduced in PTX ISA version 1.0` and `Supported on all target architectures`.
- **SF-SHL-6 (direct):** same section (lines 14726–14727): example `shl.b32  q,a,2;`.

- **SF-PTX-1 (direct):** `ptx-instructions` (lines 7517–7527): generic PTX operand forms, destination/source role (`d` destination, `a,b,c` sources).
- **SF-PTX-2 (direct):** same section (lines 7534–7535): for some instructions destination may be optional and `_` may substitute destination.
- **SF-PRED-1 (direct):** `predicated-execution` (lines 7541–7550): all instructions have optional guard predicate `@{!}p`; instructions without guard execute unconditionally.

- **SF-TYPE-1 (direct):** `fundamental-types` (lines 3019–3024): register variables are fundamental types and instruction type specifiers are shared between declarations and instruction typing.
- **SF-TYPE-2 (direct):** `fundamental-types-fundamental-type-specifiers` (lines 3040–3060): includes `.pred`, `.b16`, `.b32`, `.b64`, and compatibility rules (same basic type + size; signed/unsigned with same size; bit-size compatible with any fundamental of same size).
- **SF-REG-1 (direct):** `register-state-space` (lines 2617–2624): registers are non-addressable scalar storage with widths 8/16/32/64/128 bits (predicates are 1-bit).
- **SF-DECL-1 (direct):** `variables` (lines 3751–3755): variable declaration includes state space + type; predicate variables may only be declared in register state space.
- **SF-DECL-2 (direct):** `parameterized-variable-names` (lines 3940–3944): example `.reg .b32 %r<100>;`.
- **SF-PRED-2 (direct):** `control-flow-instructions-at` (lines 21838–21839): `@p` executes for `True`, `False` threads “do nothing.”

## 3) Proposed Lean architecture (design choices)

- **D-1:** Model one instruction constructor/tag `shl.b32` with fields `{guard?, dst, srcA, srcB}`.
- **D-2:** Bind instruction arity and ordering to exactly `d, a, b` as shown in unit syntax.
- **D-3:** For this bounded architecture, constrain active unit type to `.b32` only (unit scope), while preserving family metadata `.b16/.b32/.b64` as reference only.
- **D-4:** Restrict `dst` and source `a` to register operands for this unit.
- **D-5:** Model `b` as an operand that may be register or immediate value in the bounded architecture, with 32-bit value requirement; this is a design-level interpretation flagged as open because syntax alone in `shl` unit text does not enumerate categories.
- **D-6:** Define a minimal machine state as `State := { regs : RegFile, preds : PredFile }` where `RegFile`/`PredFile` are finite maps from declared names to values.
- **D-7:** Model predicate space separately from value register space, with predicate declarations restricted to register space by design invariant.
- **D-8:** Guard evaluation: absent guard = `true`; `@p` = predicate value; `@!p` = boolean negation.
- **D-9:** Execution relation returns either `executed` (update), `skipped` (guard-false / do-nothing), or `stuck` (malformed declarations/typing mismatch not representable as well-formed state).
- **D-10:** On `executed`, update `d` with a `shl` core operation constrained by source facts: operands are shifted-left with `b` interpreted as unsigned, with shift amount policy constrained by clamping to `N` as an explicit semantic parameter.
- **D-11:** Do not assume destination can be `_` for `shl.b32` in this stage (unit text uses required `d`); keep underscore as a family-level optional syntax question.
- **D-12:** Record metadata `(introducedIn = 1.0, target = all)` from SF-SHL-5.

## 4) Fact-to-design mapping

- SF-SHL-1, SF-PTX-1, D-2, D-3, D-6, D-9
- SF-SHL-2, SF-SHL-3, D-10
- SF-SHL-4, SF-SHL-3, SF-TYPE-2, D-4, D-10
- SF-SHL-5, D-12
- SF-SHL-1 (example context), D-5
- SF-PTX-2, AMB-1, D-11
- SF-PRED-1, SF-PRED-2, SF-TYPE-1, SF-DECL-1, D-6, D-7, D-8, D-9
- SF-TYPE-1, SF-TYPE-2, SF-REG-1, SF-DECL-1, D-6, D-7

## 5) Dependency graph

- **Type/operand foundation:** SF-TYPE-1, SF-TYPE-2, SF-DECL-1, SF-REG-1, SF-DECL-2, SF-PTX-1 ⇒ D-1, D-2, D-4, D-6, D-7.
- **Instruction semantics:** SF-SHL-1, SF-SHL-2, SF-SHL-3, SF-SHL-4, SF-SHL-6 ⇒ D-1, D-2, D-5, D-10.
- **Predication:** SF-PRED-1, SF-PRED-2, SF-PTX-1 ⇒ D-8, D-9.
- **Metadata/versioning:** SF-SHL-5 ⇒ D-12.

## 6) Register, value, and state foundations

- **D-S1:** Registers are typed storage in `.reg` space and not addressable via register value (`register-state-space`).
- **D-S2:** Runtime value domains for this unit are size-aware; `.b32` operation uses 32-bit-sized registers/sources by unit restriction (`D-3`, `D-4`).
- **D-S3:** Predicate runtime values are a separate bool-like domain for `.pred` names; this is a bounded architecture choice.
- **D-S4:** State equality for unchanged behavior is total over both register and predicate maps.

## 7) Operand architecture

- **D-O1:** `dst` and `srcA` are register variables.
- **D-O2:** `dst` is required in this architecture revision for `shl.b32` (no `_` in unit-normalized syntax).
- **D-O3:** `srcB` is 32-bit-valued and can be register or immediate via `D-5` interpretation.
- **D-O4:** No memory address operands are in scope.

## 8) Predication architecture

- **D-P1:** Attach optional guard to instruction node.
- **D-P2:** For bounded semantics, evaluation of guard determines `executed` vs `skipped`.
- **D-P3:** `skipped` is modeled as no-state-change and no destination write.
- **D-P4:** Predicate source names for guards are expected to be declared as predicate variables in `.reg` state.

## 9) Version and target representation

- **D-M1:** Unit metadata in architecture record:
  - `introducedIn`: `1.0`
  - `target`: `all architectures`
  - `unit`: `shl.b32`

## 10) Candidate theorem-obligation families

Validation obligations:

- **VAL-1 (definitional):** Instruction tag is `shl` with active unit `.b32` and exactly 3 operands.
- **VAL-2 (definitional):** `dst` and `srcA` are register names declared in `.reg` space.
- **VAL-3 (definitional):** `srcB` is width-32-compatible and source-typed for shift amount requirement.
- **VAL-4 (definitional):** `srcB` and `srcA` compatibility satisfies SF-SHL-4 and SF-TYPE-2.
- **VAL-5 (definitional):** Optional guard, when present, references a declared predicate.
- **VAL-6 (meta):** Metadata fields equal source-specified values.

Proof families:

- **PRF-1 (non-vacuous):** Guard false leads to `skipped` (or equivalent no-effect branch).
- **PRF-2:** For well-formed and well-typed `shl.b32`, execution is deterministic.
- **PRF-3:** `executed` update changes at most one value register (`dst`) and does not change predicate registers.
- **PRF-4:** For `executed`, `dst` equals `srcA` shifted by `srcB` under the declared shift amount policy with clamped amount rule.
- **PRF-5:** The shift result remains in width-32-compatible representation required by unit restriction.

## 11) Assumptions

- **ASS-1:** Destination `_` support for `shl.b32` is not asserted as mandatory in this unit because unit syntax does not explicitly specify it as allowed.
- **ASS-2:** The bounded architecture models `srcB` as register-or-immediate since `shl` syntax is register-formal but immediate usage appears in example.
- **ASS-3:** Guard-false behavior as full no-op (including predicate state) is adopted from `control-flow-instructions-at` semantics wording.
- **ASS-4:** Shift-domain edge behavior beyond `clamped to N` (e.g., bit-level implementation details for exact fixed-width arithmetic) is represented as a semantic parameter in Lean mapping.
- **ASS-4b:** `stuck` is an internal partiality/error outcome for malformed declarations/typing rather than a sourced machine fault model.

## 12) Ambiguities

- **AMB-1:** Whether `shl.b32` explicitly and always permits `_` destination for this mnemonic is not explicit in the `shl` unit section.
- **AMB-2:** Exact operator and operand-category grammar for `srcB` (register-only vs immediate-plus-register) is not fully specified in unit text.
- **AMB-3:** Exact mechanism of clamped shift amount and resulting value-lane behavior at width boundaries is not fully elaborated in text.
- **AMB-4:** Whether non-register declarations can contribute to `srcB` in this bounded phase is undecided.

## 13) Open questions

- **OQ-1:** Is `_` destination semantically permitted by `shl` in PTX parser semantics, or only by selected instruction subsets?
- **OQ-2:** What is the definitive source text for `shl.b32` operand category of `b` (immediate and/or register)?
- **OQ-3:** What exact Lean encoding should witness “clamped” shift amount and the resulting bit-width semantics while staying faithful to `d = a << b`?
- **OQ-4:** Should the execution relation return only `executed/skipped` (total for valid state) rather than include `stuck`? (Currently `stuck` is a bounded-modeling placeholder.)

## 14) Evidence index

| ID | Document | Section / anchor | Lines | Status |
|---|---|---|---|---|
| E-1 | PTX HTML | `logic-and-shift-instructions-shl` | 14697–14730 | direct |
| E-2 | PTX HTML | `ptx-instructions` | 7517–7535 | direct |
| E-3 | PTX HTML | `predicated-execution` | 7541–7550 | direct |
| E-4 | PTX HTML | `control-flow-instructions-at` | 21838–21839 | direct |
| E-5 | PTX HTML | `fundamental-types` | 3019–3024, 3062–3066 | direct |
| E-6 | PTX HTML | `fundamental-types-fundamental-type-specifiers` | 3040–3060 | direct |
| E-7 | PTX HTML | `register-state-space` | 2617–2624 | direct |
| E-8 | PTX HTML | `variables` | 3751–3755 | direct |
| E-9 | PTX HTML | `parameterized-variable-names` | 3940–3944 | direct |
| E-10 | PTX HTML | `source-manifest.json` | n/a | metadata |

Source SHA summary: HTML=`e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`; MANIFEST=`622e6ce0d3114a909a62726530955993b5f2b98d2f60e45ae1ceb429512208f2`; SUMS=`e02f4feadfce614282d3d4774ed21dd87985202d4ea9ad84ead60c688a6c0ecd`.

## 15) Gate A review checklist

- [ ] Scope is bounded to `shl.b32` and explicitly does not include other instructions.
- [ ] Source facts are sourced with document identity, version, section/anchor, and line span.
- [ ] Source claims are separated from design choices/assumptions/ambiguities/open questions.
- [ ] Architecture includes syntax/operands, predicate guarding, typing, state, execution shape, and metadata.
- [ ] Fact-to-design mapping and dependency graph are present.
- [ ] Major assumptions (underscore destination, `b` operand category, shift-domain details) are explicit and unresolved.
- [ ] The architecture avoids unsupported unit-level commitments on `_` and over-specified shift behavior.
- [ ] No theorem declarations, axioms, or Lean code are introduced.
