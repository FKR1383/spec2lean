# PTX `shr.b32` Foundation Architecture v1 — DRAFT (UNAPPROVED)

## 1) Scope

- **SCOPE-1:** Bounded architecture for language construct `shr.b32` in PTX 9.3.
- **SCOPE-2:** Covers source-backed syntax/operands, typing/compatibility, declaration/state prerequisites, predication, single-instruction execution shape, version/target metadata, and candidate theorem-obligation families.
- **SCOPE-3:** Excludes full parsing pipeline, threading model, memory spaces beyond `.reg`/`.pred`, exceptions/fault taxonomy, and concurrency.
- **SCOPE-4:** This is an architecture artifact only; no Lean code, proofs, or source bundle construction.

## 2) Official source facts

- **Document identity:** `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` (PTX ISA 9.3, SHA-256 `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`), plus manifest `documents/sources/nvidia/ptx/9.3/source-manifest.json` (SHA-256 `622e6ce0d3114a909a62726530955993b5f2b98d2f60e45ae1ceb429512208f2`) and checksum list `documents/sources/nvidia/ptx/9.3/SHA256SUMS` (SHA-256 `e02f4feadfce614282d3d4774ed21dd87985202d4ea9ad84ead60c688a6c0ecd`).

### Source-backed facts for `shr`

- **SF-SHR-1 (logic-and-shift section):** `logic-and-shift-instructions-shr` (heading 9.7.8.9) has syntax `shr.type d, a, b;` with `.type = { .b16, .b32, .b64, .u16, .u32, .u64, .s16, .s32, .s64 }` (lines 14735-14744).
- **SF-SHR-2 (semantics contract):** Description is “Shift `a` right by amount specified by unsigned 32-bit value in `b`; signed shifts fill with sign bit, unsigned and untyped fill with `0`.” (lines 14746-14748).
- **SF-SHR-3 (semantics notation):** Semantics block `d = a >> b;` (lines 14749-14752).
- **SF-SHR-4 (shift amount rule):** “Shift amounts greater than register width `N` are clamped to `N`.” (lines 14754-14755).
- **SF-SHR-5 (operand-width rule):** “Sizes of destination and first source must match, but not necessarily type. `b` must be 32-bit regardless of instruction type.” (lines 14756-14757).
- **SF-SHR-6 (type note):** “Bit-size types are included for symmetry with `shl`.” (line 14758).
- **SF-SHR-7 (metadata):** PTX ISA Notes: introduced in 1.0; Target ISA Notes: supported on all target architectures (lines 14759-14763).
- **SF-SHR-8 (example):** Example includes `shr.b16  k,i,j;` etc. and demonstrates unit syntax family presence with immediate/binary forms (lines 14763-14769).
- **SF-INS-1 (instruction format):** PTX instructions generally have zero to four operands and optional guard after `@`; for result-producing instructions roles are `d`=destination, `a,b,c`=sources (lines 7517-7527).
- **SF-INS-2:** Destination may be optional via underscore bit-bucket in some instructions (lines 7534-7535).
- **SF-PRED-1 (predicated execution):** Predicate declaration and optional guard syntax `@{!}p`; unguarded instructions execute unconditionally (lines 7541-7550).
- **SF-PRED-2:** `instructions` section: “All PTX instructions may be predicated. In the following descriptions, the optional guard predicate is omitted from the syntax.” (lines 8722-8723).
- **SF-PRED-3:** Control-flow predication description: “Threads with a False guard predicate do nothing.” (lines 21838-21839).
- **SF-TYPE-1:** Fundamental types are basic type + size; register variables and instruction typing share type specifiers (lines 3019-3022).
- **SF-TYPE-2:** `.b32` appears in table of bits, and `.s32/.u32` appear in signed/unsigned tables (lines 3042-3047, 3053-3055).
- **SF-TYPE-3:** Type compatibility includes same type/size compatibility and signed/unsigned same-size compatibility; bit-size compatible with any fundamental type of same size (lines 3062-3066).
- **SF-REG-1:** `.reg` stores typed/untype variables; scalar widths include 8/16/32/64/128 bits; registers are not fully addressable (lines 2617-2624, 2626-2627).
- **SF-DECL-1:** Variable declarations name state space, type, name; predicates may be declared only in register space (lines 3751-3755).
- **SF-DECL-2:** Parameterized names (e.g., `.reg .b32 %r<100>;`) are supported (lines 3940-3944).
- **SF-SUBWORD-1:** `.u8/.s8/.b8` are restricted; no `.b32` restriction there (lines 3074-3075).

### Evidence status

All above are direct extraction from official PTX 9.3 HTML/PDF-manifest metadata; no semantic inference is treated as a source fact.

## 3) Proposed Lean architecture (design choices)

- **D-1:** Define a bounded instruction constructor for `shr.b32` with fields: `guard : Option Guard`, `dst`, `srcA`, `srcB`, where types are concrete bounded operand descriptors and static type parameter is fixed to `.b32`.
- **D-2:** Constrain active unit arity/order to three operands `d, a, b`.
- **D-3:** Require active-width rule for bounded unit: destination and first source are 32-bit compatible by size; source `b` is 32-bit.
- **D-4:** In this bounded artifact, destination is required (not optional) unless bit-bucket support is adopted for future refinement; no source-specific syntax line explicitly names `_` here.
- **D-5:** `dst`/`srcA` are value operands in `.reg` storage (not special memory address values for this bounded form).
- **D-6:** Source `srcB` is a source operand validated as 32-bit value; its concrete source-form (register/immediate/constant-expression class) is represented by a bounded operand category with openness preserved where not explicitly stated in `shr` syntax.
- **D-7:** Predication model follows complete-guard evaluation:
  - no guard → `true`;
  - `@p` → value of predicate `p`;
  - `@!p` → negation of `p`.
- **D-8:** Execution relation shape: `executed` (with destination update), `skipped` (no state change), and `stuck` when malformed declarations/typing preconditions hold.
- **D-9:** On `executed`, destination update uses abstract `Shr` relation on 32-bit domain with clamp-by-N semantics (`N = 32`), and signedness-sensitive fill behavior as an explicit design parameter of operation family:
  - signed types (`.s16/.s32/.s64`) sign-fill;
  - unsigned/bit-size types fill with 0.
- **D-10:** Machine state for bounded semantics contains `regFile : name ↦ value`, `predFile : predName ↦ Bool`, and optional declaration metadata for validation.
- **D-11:** Version/target metadata for the bounded unit is `(instruction="shr.b32", introduced=1.0, target=all_architectures, specVersion=9.3)`.

## 4) Fact-to-design mapping

- SF-SHR-1 ⇒ D-1, D-2, D-3, D-11.
- SF-SHR-2, SF-SHR-3, SF-SHR-4 ⇒ D-9, D-8.
- SF-SHR-5 ⇒ D-3.
- SF-INS-1 ⇒ D-1, D-2, D-7, D-8.
- SF-INS-2 ⇒ D-4 (as open design option).
- SF-PRED-1, SF-PRED-2 ⇒ D-7, D-8.
- SF-PRED-3 ⇒ D-8 and D-10 (stuck/skip interpretation).
- SF-TYPE-1, SF-TYPE-2, SF-TYPE-3, SF-SUBWORD-1 ⇒ D-3, D-10.
- SF-REG-1, SF-DECL-1, SF-DECL-2 ⇒ D-5, D-10.

## 5) Dependency graph

- **Instruction syntax/operands:** SF-SHR-1, SF-INS-1.
- **Typing/compatibility:** SF-SHR-5, SF-TYPE-1/2/3, SF-SUBWORD-1.
- **Predication:** SF-PRED-1, SF-PRED-2, SF-PRED-3.
- **State model:** SF-REG-1, SF-DECL-1/2.
- **Shift semantics/meta:** SF-SHR-2/3/4, SF-SHR-6, SF-SHR-7.

## 6) Register, value, and state foundations

- **RS-1:** Values are represented in bounded maps from declared names to values, not by raw storage.
- **RS-2:** Register storage includes declaration metadata from `.reg` domain; predicates are one-bit conceptually but represented as boolean-like in this model.
- **RS-3:** The state model tracks only bounded components needed by `shr.b32`.
- **RS-4:** For `executed`, only register write side effects plus same-state predicates are modeled.

## 7) Operand architecture

- **OP-1:** Operand slots are exactly `d, a, b`.
- **OP-2:** `d` and `a` require declared register-compatible value locations (`.reg` names).
- **OP-3:** `b` must be 32-bit, independent of `.b32` active instruction type.
- **OP-4:** Operand class for `d`/`a` may be parameterized to permit signed/unsigned/bit-size 32-bit-typed sources under compatibility checks; exact parser classes (register/immediate/mixed) remain open where not explicit.
- **OP-5:** No vector/memory address/special-register operands in this bounded form.

## 8) Predication architecture

- **P-1:** Guards are optional `@p`/`@!p` forms where `p` is `.pred`.
- **P-2:** Guard false branches are modeled as `skipped` and leave bounded state unchanged.
- **P-3:** This uses SF-PRED-3’s do-nothing interpretation as a cross-instruction behavioral assumption for bounded semantics.

## 9) Version and target representation

- **V-1:** Bound metadata for this artifact: `introduced = 1.0`, `targets = all` (from SF-SHR-7).
- **V-2:** Version/target metadata is non-executable and governance-only for stage architecture.

## 10) Candidate theorem-obligation families

### Validation obligations

- **VAL-1 (syntax):** `shr.b32` has arity 3 and mnemonic/type match.
- **VAL-2 (typing):** `dst` and `srcA` are 32-bit compatible and `srcB` is 32-bit.
- **VAL-3 (compatibility):** Destination predicate guard, if present, resolves to declared `.pred` variable in register-space.
- **VAL-4 (type metadata):** Active unit metadata equals `.b32`, introduced 1.0, target = all.

### Semantic obligations

- **PRF-1:** For well-typed inputs, execution relation is deterministic.
- **PRF-2:** `executed` updates only destination (or no destination if `_` is adopted), leaving other registers/predicates unchanged.
- **PRF-3:** `skipped` is no-op over bounded state.
- **PRF-4:** Executed destination matches abstract right-shift with clamp and sign/zero fill behavior consistent with active type class.
- **PRF-5:** `stuck` arises only from malformed declarations/typing and no source-defined exceptional behavior is assumed for this bounded form.

## 11) Assumptions

- **ASS-1:** “Threads with False guard predicate do nothing” from control-flow section applies as the false-guard behavior for all instructions, including `shr.b32`.
- **ASS-2:** Concrete representation of predicates as `Bool` and of bit/word values is a Lean-mapping decision.
- **ASS-3:** No runtime exception/undefined behavior is surfaced for the bounded `shr.b32` family in PTX 9.3 instructions text.
- **ASS-4:** Bit-bucket `_` destination admissibility for `shr` remains unresolved from local `shr` syntax; only generic `ptx-instructions` rule is available.
- **ASS-5:** Bound state includes only map updates and not module/ABI register-lifetime constraints.

## 12) Ambiguities

- **AMB-1:** Whether `shr.b32` in PTX 9.3 should allow `_` destination by grammar binding, despite generic mention only.
- **AMB-2:** Exact concrete Lean representation of `srcB` (register vs immediate classes) is not specified in local `shr` syntax beyond 32-bit width requirement.
- **AMB-3:** Whether the bounded model should treat a validated `.b32` family form as permitting `srcA`/`dst` from other 32-bit fundamental types or only `.b32` by declaration policy.

## 13) Open questions

- **OQ-1:** Resolve and document whether `_` is admissible for `shr` specifically.
- **OQ-2:** Resolve final `srcB` source categories and immediate-form typing rules under `shr` parsing.
- **OQ-3:** Settle the exact theorem about clamp behavior at edge cases (e.g., `b > 32`) in Lean mapping.
- **OQ-4:** Decide whether skip behavior is required to preserve declaration metadata maps as part of state equality.

## 14) Evidence index

| ID | Document | Section/anchor | Lines | Status |
|---|---|---|---:|---|
| E-1 | source manifest | `source-manifest.json` | lines 1-38 | read |
| E-2 | PTX HTML 9.3 | `logic-and-shift-instructions-shr` | 14731-14770 | read |
| E-3 | PTX HTML 9.3 | `logic-and-shift-instructions-shr` | 14735-14744 | read |
| E-4 | PTX HTML 9.3 | `logic-and-shift-instructions-shr` | 14746-14752 | read |
| E-5 | PTX HTML 9.3 | `logic-and-shift-instructions-shr` | 14754-14758 | read |
| E-6 | PTX HTML 9.3 | `logic-and-shift-instructions-shr` | 14759-14763 | read |
| E-7 | PTX HTML 9.3 | `ptx-instructions` | 7517-7536 | read |
| E-8 | PTX HTML 9.3 | `predicated-execution` | 7537-7550 | read |
| E-9 | PTX HTML 9.3 | `instructions` | 8722-8723 | read |
| E-10 | PTX HTML 9.3 | `control-flow-instructions-at` | 21838-21839 | read |
| E-11 | PTX HTML 9.3 | `fundamental-types` | 3019-3066 | read |
| E-12 | PTX HTML 9.3 | `register-state-space` | 2617-2627 | read |
| E-13 | PTX HTML 9.3 | `variables` | 3751-3755 | read |
| E-14 | PTX HTML 9.3 | `parameterized-variable-names` | 3940-3944 | read |
| E-15 | PTX HTML 9.3 | `restricted-use-of-sub-word-sizes` | 3074-3075 | read |
| E-16 | PTX artifacts | `documents/sources/nvidia/ptx/9.3/SHA256SUMS` | lines 1-2 | read |

## 15) Gate A review checklist

- [ ] Artifact is explicitly marked DRAFT and non-human-approved.
- [ ] Scope is bounded to `shr.b32`.
- [ ] Source facts are separated from design assumptions/choices.
- [ ] Each source claim has line-anchored evidence.
- [ ] Predication/guard false behavior is stated as assumption-backed model mapping (not over-inferred).
- [ ] Operand arity/roles and 32-bit rules (`b` 32-bit, clamp, matching sizes) are reflected in the design.
- [ ] Candidate theorem obligations are split into validation/proof families and are relational/non-vacuous.
- [ ] Assumptions, ambiguities, and open questions are explicit.
- [ ] No unrelated architecture (memory, full program model, exception model) is introduced.
