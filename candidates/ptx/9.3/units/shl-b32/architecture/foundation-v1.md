# PTX `shl.b32` Foundation Architecture v1 — DRAFT (UNAPPROVED)

## 1) Scope

- **DESIGN CHOICE (SC-1):** This artifact targets the PTX ISA 9.3 instruction unit `shl.b32` in section 9.7.8.8 (`shl` instruction family), and is a language-wide architecture foundation for future formalization of that single unit.
- **DESIGN CHOICE (SC-2):** The bounded scope includes: instruction form and operands, source/destination typing requirements, predicate guards, minimal register/state model, execution-result representation, version/target metadata, and candidate theorem families.
- **DESIGN CHOICE (SC-3):** This artifact is architectural only. It does not define Lean code, parsing, or proofs.
- **DESIGN CHOICE (SC-4):** Scope excludes control flow, memory safety, barriers/synchronization, whole-program semantics, exceptions, and modules outside the `shl.b32` instruction form.
- **DESIGN CHOICE (SC-5):** This artifact is **not** a claim that `shl.b32` is ready for Gate A review.

## 2) Official source facts

Primary source identity and evidence hashes:
- `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` (PTX ISA 9.3, SHA-256 `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`)
- `documents/sources/nvidia/ptx/9.3/source-manifest.json` (metadata, SHA-256 `622e6ce0d3114a909a62726530955993b5f2b98d2f60e45ae1ceb429512208f2`)
- `documents/sources/nvidia/ptx/9.3/SHA256SUMS` (hash index, SHA-256 `e02f4feadfce614282d3d4774ed21dd87985202d4ea9ad84ead60c688a6c0ecd`)

Source facts grounded directly from the HTML sections:

- **SF-SHL-1 (direct):** Section `logic-and-shift-instructions` (anchor `logic-and-shift-instructions`, line 14238-14244): logic/shift instructions are “fundamentally untyped,” perform bit-wise operations on same-size operands.
- **SF-SHL-2 (direct):** Section `logic-and-shift-instructions-shl` (anchor `logic-and-shift-instructions-shl`, lines 14697-14708): heading/section number 9.7.8.8 and grammar `shl.type d, a, b;` with `.type = { .b16, .b32, .b64 }`.
- **SF-SHL-3 (direct):** Same section, lines 14711-14712: description of `shl` as “Shift a left by the amount specified by unsigned 32-bit value in b.”
- **SF-SHL-4 (direct):** Same section, lines 14713-14715: semantics `d = a << b;`.
- **SF-SHL-5 (direct):** Same section, lines 14718-14720: shift amounts greater than register width `N` are clamped to `N`; destination and first source sizes must match but not necessarily type; operand `b` must be 32-bit regardless of instruction type.
- **SF-SHL-6 (direct):** Same section, lines 14721-14724: PTX ISA notes “Introduced in PTX ISA version 1.0.” and target notes “Supported on all target architectures.”
- **SF-SHL-7 (direct):** Same section, lines 14725-14727: example `shl.b32 q,a,2;` (bound instruction form with `.b32` and immediate literal `2` as third operand).
- **SF-SHL-8 (direct):** PTX 9.7 `instructions` heading (`instructions`, line 8722): all PTX instructions may be predicated and optional guard omitted from syntax.
- **SF-SHL-9 (direct):** PTX instructions section (`ptx-instructions`, line 7517-7527): optional guard at left of opcode and role of operands where `d` is destination and `a,b,c` are sources.
- **SF-SHL-10 (direct):** Predicated execution (`predicated-execution`, line 7547-7550): optional guard predicate `@{!}p`, most commonly set by `setp`, unguarded instructions execute unconditionally.
- **SF-SHL-11 (direct):** Predicated execution (`predicated-execution`, line 7541-7542): predicate registers are virtual and use `.pred` type, declared as `.reg .pred`.
- **SF-SHL-12 (direct):** Fundamental types (`fundamental-types`, line 3019-3022): register variables are of fundamental types and instructions operate on these types; type specifiers are shared by declarations and instructions.
- **SF-SHL-13 (direct):** Fundamental type table (`fundamental-types-fundamental-type-specifiers`, line 3053-3055 and 3057-3058): `.b32` is in Bits (untyped); `.pred` exists as predicate type.
- **SF-SHL-14 (direct):** Compatibility rule (`fundamental-types`, line 3062-3066): same basic type and size are compatible; `.b32` is compatible with any fundamental type of same size due bit-size type rule.
- **SF-SHL-15 (direct):** Register state space (`register-state-space`, lines 2617-2624): register files are typed/untyped; aside from 1-bit predicates, scalar registers are 8/16/32/64/128 bits, and registers are not fully addressable.
- **SF-SHL-16 (direct):** Variables (`variables`, lines 3751-3755): declarations name space/type/name and predicate variables may only be declared in register state space.
- **SF-SHL-17 (direct):** Parameterized variable names (`parameterized-variable-names`, lines 3940-3944): `.reg .b32 %r<100>;` notation demonstrates `.b32` register declarations.
- **SF-SHL-18 (direct):** Format-and-semantics preface (`format-and-semantics-of-instruction-descriptions`, lines 7509-7511): instruction entries specify name/format + semantics + examples.
- **SF-SHL-19 (direct):** Restricted sub-word use (`restricted-use-of-sub-word-sizes`, line 3074): only `.u8/.s8/.b8` are restricted to specific instructions, so `.b32` is not among those restrictions.
- **SF-SHL-20 (direct/limited):** `logic-and-shift-instructions-shr` (`logic-and-shift-instructions-shr`, lines 14755-14758): shows nearby `shr` symmetry notes that bit-size types included for symmetry with `shl`; indicates family note context.

## 3) Proposed Lean architecture (design choices)

- **DESIGN CHOICE (D-1):** Represent `shl.b32` instruction as a structured node with fields `{guard? , dst , srcA , srcB}` and mnemonic tag `shl.b32`; this aligns with generic instruction format and optional guard.
- **DESIGN CHOICE (D-2):** Treat bounded source category as exactly three operands: destination `d`, source `a` (shifted value), source `b` (shift amount).
- **DESIGN CHOICE (D-3):** Bound the active instruction type for this unit to `.b32` and require active-type membership in `{.b16,.b32,.b64}` at the family level.
- **DESIGN CHOICE (D-4):** Use an architecture-wide type model with basic type+bit-width; map `.b32` to width 32 untyped-bit value domain for this unit (32-bit bitvector-like domain).
- **DESIGN CHOICE (D-5):** Source operand `a` is from a register variable in `.reg` state space, with 32-bit size compatibility per `shl` size rule.
- **DESIGN CHOICE (D-5b):** Source operand `b` is constrained by unit semantics to be a 32-bit value and used as unsigned shift amount; whether `b` is required to be register-only or allows immediate is not fixed by unit syntax and is left as an implementation-design decision with an open question (OQ-B1). The example with literal `2` is retained as evidence for non-register form support.
- **DESIGN CHOICE (D-6):** `dst` is a register destination or bit-bucket `_` where family syntax allows optional destination omission.
- **DESIGN CHOICE (D-7):** Machine state for this unit is a pair of maps: `valueRegs` (for scalar value registers) and `predRegs` (for predicate registers), plus optional name/type metadata for validation.
- **DESIGN CHOICE (D-8):** Guard evaluation follows PTX optional guard syntax: no guard = true, `@p` = `p`, `@!p` = not `p`.
- **DESIGN CHOICE (D-9):** On guard-false evaluation, state remains unchanged and no destination write occurs (assumption from the “controls conditional execution” wording).
- **DESIGN CHOICE (D-10):** Execution-result representation is a relation from pre-state and instruction to either no-step/update/no-write or an updated state, with an optional malformed-input `stuck` for impossible or unvalidated input.
- **DESIGN CHOICE (D-11):** On guarded-true execution, `d` is updated with the abstract value of `a << b`, where shift amount is clamped to register width `N` and masked to 32-bit behavior is applied to `b` per source facts.
- **DESIGN CHOICE (D-12):** Version/target metadata record for this unit is `(introducedIn=1.0, target=all)` with provenance from PTX notes.
- **DESIGN CHOICE (D-13):** The architecture explicitly records unresolved items (e.g., immediate typing and guard-false semantics proof status) rather than asserting unresolved behavior.

## 4) Fact-to-design mapping

| Source fact | Design component |
|---|---|
| SF-SHL-2, SF-SHL-8, SF-SHL-9 | D-1, D-2 |
| SF-SHL-3, SF-SHL-4 | D-11 |
| SF-SHL-5, SF-SHL-14, SF-SHL-19, SF-SHL-13 | D-3, D-4, D-5 |
| SF-SHL-10, SF-SHL-11, SF-SHL-9 | D-8, D-9 |
| SF-SHL-6, SF-SHL-7 | D-12 |
| SF-SHL-13, SF-SHL-15, SF-SHL-16, SF-SHL-17 | D-4, D-7 |
| SF-SHL-14, SF-SHL-20 | D-1, D-10, D-11 |
| SF-SHL-6, SF-SHL-20 | D-13 |

## 5) Dependency graph

- Instruction/family dependencies: SF-SHL-2, SF-SHL-3, SF-SHL-4, SF-SHL-5, SF-SHL-6, SF-SHL-7 → D-1, D-2, D-3, D-11, D-12, D-7.
- Typing/value dependencies: SF-SHL-12, SF-SHL-13, SF-SHL-14, SF-SHL-19, SF-SHL-15, SF-SHL-16, SF-SHL-17 → D-3, D-4, D-5, D-7.
- Predication dependencies: SF-SHL-8, SF-SHL-9, SF-SHL-10, SF-SHL-11 → D-8, D-9.
- Execution semantics dependencies: SF-SHL-4, SF-SHL-5, D-8, D-11 → proof obligations in Section 10.

## 6) Register, value, and state foundations

- **DESIGN CHOICE (D-14):** Registers are named storage locations with declared `.reg` types; not addressable by value semantics (no address-taking). This matches register-state-space text.
- **DESIGN CHOICE (D-15):** Value domain for `.b32` in this unit is fixed-width 32-bit value representation; exact Lean representation (bitvector/algebraic) is deferred to Lean mapping.
- **DESIGN CHOICE (D-16):** Predicate values are represented as a two-valued domain over `.pred` declarations (bool-like model), tied to source statements that predicates are virtual and declared with `.reg .pred`.
- **DESIGN CHOICE (D-17):** Out-of-scope state spaces (global/shared/local/special/surface addressing/stateful parameter-space) are not part of this bounded state because bounded `shl.b32` uses register operands and optional predicates only.

## 7) Operand architecture

- **DESIGN CHOICE (D-18):** Operand positions are fixed to `d, a, b` for `shl.b32` by syntax block.
- **DESIGN CHOICE (D-19):** Destination `d` is scalar destination register (or `_` as candidate alternative).
- **DESIGN CHOICE (D-20):** Source `a` is a register-compatible value to be shifted.
- **DESIGN CHOICE (D-21):** Source `b` is shift amount in unsigned 32-bit domain. Immediate-vs-register admissibility of `b` is marked unresolved (OQ-B1) because syntax is source-neutral and only examples expose immediate usage.
- **DESIGN CHOICE (D-22):** Family-level type set for this formalization is restricted to `.b32` as requested run unit.

## 8) Predication architecture

- **DESIGN CHOICE (D-23):** Predicate syntax is optional prefix `@p`/`@!p` to opcode and is attached to the instruction regardless of arity.
- **DESIGN CHOICE (D-24):** Guardless form is interpreted as unconditional execution.
- **DESIGN CHOICE (D-25):** Complete guard condition computes to a boolean from predicate-register lookup.
- **DESIGN CHOICE (D-26):** Guard false yields no observable state change; this includes no destination update. This interpretation remains a candidate architecture interpretation (not yet independently proven against all PTX operational detail).
- **DESIGN CHOICE (D-27):** No predicate-specific predication exception for `shl` is modeled, since only `ld.param`/`st.param` predication exceptions are read in the current unit pass.

## 9) Version and target representation

- **DESIGN CHOICE (D-28):** Represent metadata as `(ptxIntroduced = 1.0, targetSupported = all architectures)` for bounded `shl.b32` from SF-SHL-6.
- **DESIGN CHOICE (D-29):** Record this metadata as checked obligations (not executable semantics), with explicit provenance to the section’s PTX notes.

## 10) Candidate theorem-obligation families

Validation obligations (structural/type checks):

- **VAL-1 (definitional):** Instruction kind is `shl` with active type `.b32` in bounded unit scope. Grounding: SF-SHL-2, SF-SHL-3.
- **VAL-2 (definitional):** Operand position/arity is exactly 3 (`d,a,b`) and optional destination bit-bucket behavior aligns with `ptx-instructions` generic format. Grounding: SF-SHL-2, SF-SHL-9.
- **VAL-3 (definitional):** Destination and first source values are 32-bit compatible (size compatibility under SF-SHL-14 + bit-size rule; size equality enforced with `N=32`). Grounding: SF-SHL-5, SF-SHL-13, SF-SHL-14.
- **VAL-4 (definitional):** `b` is a 32-bit value compatible with instruction-family requirement. Grounding: SF-SHL-3, SF-SHL-5.
- **VAL-5 (definitional):** Guard, when present, refers to `.pred`-typed predicate register in `.reg` state. Grounding: SF-SHL-10, SF-SHL-11, SF-SHL-16.
- **VAL-6 (definitional):** Unit metadata matches section PTX ISA/Target Notes (introduced 1.0, all architectures). Grounding: SF-SHL-6.

Proof obligations (candidate theorem families over future execution relation):

- **PRF-1 (determinism):** For well-formed/well-typed `shl.b32` state, execution relation is deterministic.
- **PRF-2 (frame/locality):** On execution with register destination, only `d` may change; every other value register and every predicate register remains unchanged.
- **PRF-3 (bit-bucket):** If destination is `_`, no value register is updated on guarded-true execution.
- **PRF-4 (guard-behavior):** Instruction executes iff complete guard evaluates true; unguarded means always true; `@!p` inverts predicate value.
- **PRF-5 (shift semantics fidelity):** On execution, destination receives value corresponding to `d = a << b`, with `b` treated as unsigned amount and clamped to width `N` (N=32 for `.b32` here), and preserved 32-bit domain result.
- **PRF-6 (type consistency):** The result of execution is a valid `.b32`-domain value and can be stored in destination’s type according to the compatibility rule.

## 11) Assumptions

- **ASS-1:** Guard-false behavior is interpreted as no-op (state unchanged) from the “controls conditional execution” wording; this is an interpretation required for architecture execution modeling.
- **ASS-2:** The token `2` in the `shl.b32 q,a,2;` example is an immediate constant for operand `b`, but the unit-specific grammar does not normatively enumerate immediate categories. Operand-`b` admissibility between register/immediate forms remains an architecture question.
- **ASS-3:** Shift result truncation/wrapping behavior beyond the textual “clamped amount” rule is modeled with a fixed 32-bit shift result domain for `.b32`; exact Lean numeric operation encoding is deferred.
- **ASS-4:** No malformed-state exception mechanism is specified for bounded unit text; `stuck` is a modeling placeholder for validation failure, not sourced as machine fault behavior.
- **ASS-5:** `.b8/.s8/.b8` restrictions in SF-SHL-19 are interpreted as non-restrictive for `.b32` because `.b32` is absent from that restriction list.

## 12) Ambiguities

- **AMB-1:** Operand `b` category ambiguity: immediate vs. register-only is not explicitly fixed in the `shl` syntax line; only an example uses immediate literal `2`.
- **AMB-2:** Whether `@!p` and `@p` effects are exactly “no effect when false” versus other side effects is not explicitly formalized in the guard paragraph; only “controls conditional execution” language is explicit.
- **AMB-3:** The exact formal semantics of shift on out-of-range shift values with `b >= 32` is stated as “clamped to N”, but exact computation strategy and whether hardware applies a strict numeric clamp versus masking is open for Lean modeling details.
- **AMB-4:** The bounded scope excludes other `shf.*` instructions and `.b16/.b64` forms; if later needed, they may need separate units.

## 13) Open questions

- **OQ-B1:** Confirm source-category admissibility for `b` in `shl.b32`: register-only, immediate-only, or both across all parser forms.
- **OQ-B2:** Is bit-bucket destination `_` explicitly legal for scalar `shl` in all contexts, or only in selected instruction families despite generic `ptx-instructions` rule?
- **OQ-B3:** What exact numeric domain/lattice should represent bitwise left shift for proof obligations (modulo arithmetic vs truncated bitwise semantics) for the bounded architecture?
- **OQ-B4:** Should guard-false be modeled as strict identity of full machine state including all register metadata, or only value store equality?
- **OQ-B5:** Any future requirement to treat `shl` as a pure arithmetic vs bit-level operation for typing of non-bit types in conjunction with compatibility rule (SF-SHL-14)?

## 14) Evidence index

| ID | Section heading | Anchor | Lines | Source | SHA-256 | Status |
|---|---|---|---|---|---|---|
| E-1 | source-manifest (project metadata) | n/a | lines 1-38 | source-manifest.json | MANIFEST | read |
| E-2 | Source hashes | n/a | lines 1-3 | SHA256SUMS | SUMS | read |
| E-3 | Logic and Shift Instructions | `logic-and-shift-instructions` | 14238-14244 | HTML | HTML | read |
| E-4 | Logic and Shift Instructions: shl | `logic-and-shift-instructions-shl` | 14697-14730 | HTML | HTML | read |
| E-5 | All PTX instructions may be predicated | `instructions` | 8722-8723 | HTML | HTML | read |
| E-6 | PTX instruction format and operands | `ptx-instructions` | 7517-7535 | HTML | HTML | read |
| E-7 | Predicated execution | `predicated-execution` | 7541-7552 | HTML | HTML | read |
| E-8 | Format and semantics preface | `format-and-semantics-of-instruction-descriptions` | 7509-7511 | HTML | HTML | read |
| E-9 | Fundamental types | `fundamental-types` | 3019-3066 | HTML | HTML | read |
| E-10 | register state space | `register-state-space` | 2617-2640 | HTML | HTML | read |
| E-11 | variable declarations | `variables` | 3751-3755 | HTML | HTML | read |
| E-12 | parameterized names (.b32 example) | `parameterized-variable-names` | 3940-3944 | HTML | HTML | read |
| E-13 | Restricted sub-word sizes | `restricted-use-of-sub-word-sizes` | 3070-3078 | HTML | HTML | read |

Source SHA abbreviations: HTML=`e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`; MANIFEST=`622e6ce0d3114a909a62726530955993b5f2b98d2f60e45ae1ceb429512208f2`; SUMS=`e02f4feadfce614282d3d4774ed21dd87985202d4ea9ad84ead60c688a6c0ecd`.

## 15) Gate A review checklist

- [ ] Artifact is marked DRAFT and explicitly not human approved.
- [ ] Scope is bounded to `shl.b32` only; no unrelated instructions (`shf.*`, `shr.*`, `and/or/xor`) formalized here.
- [ ] Official source facts are identified and traceable to anchors + lines in Section 14.
- [ ] All claims are explicitly labeled as SOURCE FACT / DESIGN CHOICE / ASSUMPTION / AMBIGUITY / OPEN QUESTION.
- [ ] Proposed architecture includes instruction syntax, operands, typing, state, predication, execution-result shape, and version/target metadata.
- [ ] Proof obligations are relational/non-vacuous and distinct from validation checks.
- [ ] Dependency mapping from source facts to design is complete and consistent.
- [ ] Ambiguities (`b` operand category, `_` destination scope, out-of-range-shift behavior detail) are explicit and unresolved.
- [ ] No Lean code, no theorems, and no axioms are introduced in this architecture stage.
- [ ] Ready for independent architecture critique before Gate A review.