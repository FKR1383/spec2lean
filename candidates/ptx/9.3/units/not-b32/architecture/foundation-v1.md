# PTX not.b32 Foundation Architecture v1 — DRAFT — NOT HUMAN APPROVED

## 1. Revision status and bounded scope

Status note (project metadata, not specification evidence): this artifact is a DRAFT architecture candidate produced for a future Gate A review. It is marked `DRAFT — NOT HUMAN APPROVED`. It has not been reviewed or approved by a human reviewer, it is not promoted to `accepted/`, and it does not claim that Gate A is ready.

- DESIGN CHOICE (D-0) — The bounded scope of this artifact is the language-wide foundations strictly required for the future formalization of PTX ISA 9.3 `not.b32`: instruction representation, operand categories, bit-size scalar types, register/value representation, minimal machine state, state reads and destination updates, predication, execution-result representation, version/target-restriction representation, traceability, and candidate validation/proof-obligation families. Scope is a project design decision of this artifact, not an official-source fact.
- DESIGN CHOICE (D-0b) — This artifact describes architecture only. It does not define the instruction-level bit-complement semantics of `not.b32`, does not construct an instruction-level source bundle, and does not contain Lean code.
- DESIGN CHOICE (D-0c) — "not.b32" in this artifact denotes the scalar 32-bit bit-size form `not.type d, a;` with instruction type `.b32` of the `not` instruction of section 9.7.8.4. The other instruction types of the same section (`.pred`, `.b16`, `.b64`) are recorded as official source facts where required for completeness but are not modeled as commitments of the bounded base unit (see D-24, OQ-4).
- The unit identity `not.b32` (instruction family `not`, section 9.7.8.4, heading "Logic and Shift Instructions: not", HTML anchor `logic-and-shift-instructions-not`) is grounded in official-source facts recorded as SF-N1, SF-N2, and SF-N3 in Section 3.
- Metadata note (not specification evidence): the run metadata `runs/ptx-9.3-not.b32-c454d1bc/run.json` designates unit `not.b32` for this run and stage ARCHITECTURE, whereas the source manifest `documents/sources/nvidia/ptx/9.3/source-manifest.json` records `initial_formalization_unit` as `add.u32` (manifest lines 9-15). Per the orchestrator contract, run metadata is authoritative for the current run; the manifest's `add.u32` record predates this run and is a project-metadata discrepancy, not specification evidence.

## 2. Inputs and critique addressed

No prior `not.b32` architecture artifact or critique exists under `candidates/ptx/9.3/units/not-b32`; this is foundation-v1. Inputs used:

- `runs/ptx-9.3-not.b32-c454d1bc/run.json` (run metadata; unit `not.b32`; stage ARCHITECTURE; gates A-FINAL pending).
- `documents/sources/nvidia/ptx/9.3/source-manifest.json` and `documents/sources/nvidia/ptx/9.3/SHA256SUMS` (source identity and hashes).
- `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` (official PTX ISA 9.3 HTML; all source facts in Section 3 were read from this file via the restricted specification tools).
- `accepted/ptx/9.3/mov-b32/architecture/foundation-v1.md` was used as the structural template and for the lessons of its critique (`candidates/ptx/9.3/units/mov-b32/reviews/architecture-critic-v1.md`, findings F-1..F-5) and the earlier add.u32 critique (`candidates/ptx/9.3/reviews/add-u32-foundation-v1-critic.md`, findings F-1..F-10). Those lessons were applied proactively: four-label taxonomy, register-chapter evidence read, uniform guard-false phrasing, relational non-vacuous obligations, verified anchors, negative-evidence labeling, and the vacuity note on result-domain membership (PRF-6). There is no `not.b32`-specific critic yet; the artifact must receive an independent critique before Gate A.

## 3. Official-source facts

Primary source: `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html`, official NVIDIA "Parallel Thread Execution ISA" version 9.3, SHA-256 `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`, 47,743 lines. Metadata sources: `source-manifest.json`, SHA-256 `622e6ce0d3114a909a62726530955993b5f2b98d2f60e45ae1ceb429512208f2`; `SHA256SUMS`, SHA-256 `e02f4feadfce614282d3d4774ed21dd87985202d4ea9ad84ead60c688a6c0ecd` (3 lines, records the HTML and PDF hashes). The manifest records a PDF artifact (`raw/ptx_isa_9.3.pdf`, SHA-256 `769cc12e363e7bb9cd311464f2a42edbdaf4c74ca18575de8c358e93223434fc`); the PDF was not read in this pass (A-1).

- SOURCE FACT (SF-N1) — Section 9.7.8.4 "Logic and Shift Instructions: not" exists at HTML anchor `logic-and-shift-instructions-not`, line 14358; its body spans lines 14358-14391.
- SOURCE FACT (SF-N2) — The `not` syntax is `not.type d, a;` with `.type = { .pred, .b16, .b32, .b64 }` (lines 14366-14369). The `.b32` type specifier is therefore in the `not` type set.
- SOURCE FACT (SF-N3) — The `not` description is "Bitwise negation; one's complement." (line 14363) and "Invert the bits in `a`." (line 14372).
- SOURCE FACT (SF-N4) — The `not` Semantics block states `d = ~a;` (lines 14374-14377).
- SOURCE FACT (SF-N5) — The `not` Notes state: "The size of the operands must match, but not necessarily the type." (line 14379) and "Allowed types include predicates." (line 14380). The first note is the operand-typing rule for the family: for instruction type `.b32`, operand sizes must be 32 bits but operand basic types need not equal the instruction type (see SF-N9, SF-N15, OQ-7).
- SOURCE FACT (SF-N6) — `not` PTX ISA Notes: "Introduced in PTX ISA version 1.0." (line 14382).
- SOURCE FACT (SF-N7) — `not` Target ISA Notes: "Supported on all target architectures." (line 14384).
- SOURCE FACT (SF-N8) — `not` Examples: `not.b32 mask,mask;` and `not.pred p,q;` (lines 14387-14388). The `.b32` example uses two register operands (both named `mask`), showing that the destination and source may be the same register; the `.pred` example shows the predicate form of the same instruction.
- SOURCE FACT (SF-N9) — Section 9.7.8 "Logic and Shift Instructions" intro (anchor `logic-and-shift-instructions`, line 14236): "The logic and shift instructions are fundamentally untyped, performing bit-wise operations on operands of any type, provided the operands are of the same size. This permits bit-wise operations on floating point values without having to define a union to access the bits. Instructions `and`, `or`, `xor`, and `not` also operate on predicates." (lines 14240-14243). The logical shift instruction list includes `and`, `or`, `xor`, `not`, `cnot`, `lop3`, `shf`, `shl`, `shr` (lines 14244-14255). This establishes that the family is untyped at the bit level and that `not` is one of the four family members that also operate on predicates.
- SOURCE FACT (SF-N10) — Sibling-family immediate-constant usage: the `or` section (anchor `logic-and-shift-instructions-or`, lines 14291-14323) shows the example `or.b32 mask mask,0x00010001` (line 14319; note the official example text is `or.b32 mask mask,0x00010001`, without a comma between the two `mask` tokens as printed); the `xor` section (anchor `logic-and-shift-instructions-xor`, lines 14324-14357) shows the example `xor.b16 d,x,0x0001;` (line 14354). These sibling examples show immediate constants in the same logic/shift family; the `not` section itself does not show an immediate example (see AMB-2, OQ-1).
- SOURCE FACT (SF-N11) — Section 9.7 "Instructions" intro (anchor `instructions`, line 8718): "All PTX instructions may be predicated. In the following descriptions, the optional guard predicate is omitted from the syntax." (lines 8722-8723).
- SOURCE FACT (SF-N12) — Section 9.3 "Predicated Execution" (anchor `predicated-execution`, line 7537): predicate registers are virtual and have `.pred` as the type specifier (lines 7541-7542); "All instructions have an optional *guard predicate* which controls conditional execution of the instruction"; the syntax is to prefix an instruction with `@{!}p`, where `p` is a predicate variable, optionally negated; "Instructions without a guard predicate are executed unconditionally." (lines 7547-7550); "Predicates are most commonly set as the result of a comparison performed by the `setp` instruction." (lines 7551-7552); examples `@p add.s32 j, j, 1;` (line 7562) and `@!p bra L1;` (line 7570).
- SOURCE FACT (SF-N13) — Section 9.2 "PTX Instructions" (anchor `ptx-instructions`, line 7513): "PTX instructions generally have from zero to four operands, plus an optional guard predicate appearing after an `@` symbol to the left of the `opcode`" (lines 7517-7518); "For instructions that create a result value, the `d` operand is the destination operand, while `a`, `b`, and `c` are source operands." (lines 7526-7527); "For some instructions the destination operand is optional. A *bit bucket* operand denoted with an underscore (`_`) may be used in place of a destination register." (lines 7534-7535).
- SOURCE FACT (SF-N14) — Section 5.2.1 "Fundamental Types" (anchor `fundamental-types`, line 3015): "the fundamental types reflect the native data types supported by the target architectures"; "A fundamental type specifies both a basic type and a size"; "Register variables are always of a fundamental type, and instructions operate on these types"; "The same type-size specifiers are used for both variable definitions and for typing instructions" (lines 3019-3022). Table 8 (anchor `fundamental-types-fundamental-type-specifiers`, line 3025) lists `.b8`, `.b16`, `.b32`, `.b64`, `.b128` under basic type "Bits (untyped)" (lines 3053-3054), and `.pred` under "Predicate" (lines 3057-3058).
- SOURCE FACT (SF-N15) — Type compatibility (section 5.2.1): "Operand types and sizes are checked against instruction types for compatibility."; "Two fundamental types are compatible if they have the same basic type and are the same size. Signed and unsigned integer types are compatible if they have the same size. The bit-size type is compatible with any fundamental type having the same size." (lines 3062-3066). For instruction type `.b32`, an operand declared with any 32-bit fundamental type is therefore size-compatible under this rule; combined with SF-N5 ("size must match, but not necessarily the type"), operand typing for `not.b32` is size-based, not basic-type-based (OQ-7).
- SOURCE FACT (SF-N16) — Section 5.1.1 "Register State Space" (anchor `register-state-space`, line 2613): "Registers (`.reg` state space) are fast storage locations." (line 2617); "Registers may be typed (signed integer, unsigned integer, floating point, predicate) or untyped." (lines 2621-2622); "aside from predicate registers which are 1-bit, scalar registers have a width of 8-, 16-, 32-, 64-, or 128-bits, and vector registers have a width of 16-, 32-, 64-, or 128-bits" (lines 2622-2624); "Registers differ from the other state spaces in that they are not fully addressable, i.e., it is not possible to refer to the address of a register." (lines 2626-2627); ABI/function-scope and legacy module-scope notes (lines 2627-2630); alignment boundaries for multi-word loads and stores (lines 2630-2631).
- SOURCE FACT (SF-N17) — Section 5.1.2 "Special Register State Space" (anchor `special-register-state-space`, line 2633): "The special register (`.sreg`) state space holds predefined, platform-specific registers, such as grid, cluster, CTA, and thread parameters, clock counters, and performance monitoring registers. All special registers are predefined." (lines 2637-2639). This state space is not required by the base `not.b32` form.
- SOURCE FACT (SF-N18) — Section 5.4 "Variables" (anchor `variables`, line 3741): "A variable declaration names the space in which the variable resides, its type and size, its name, an optional array size, an optional initializer, and an optional fixed address for the variable." (lines 3753-3754); "Predicate variables may only be declared in the register state space." (line 3755).
- SOURCE FACT (SF-N19) — Section 5.4.6 "Parameterized Variable Names" (anchor `parameterized-variable-names`, line 3933): `.reg .b32 %r<100>;` declares `%r0` through `%r99` (lines 3940-3943); the shorthand "may be used with any of the fundamental types and with any state space" (lines 3946-3947).
- SOURCE FACT (SF-N20) — Section 9.1 "Format and Semantics of Instruction Descriptions" (anchor `format-and-semantics-of-instruction-descriptions`, line 7505): "This section describes each PTX instruction. In addition to the name and the format of the instruction, the semantics are described, followed by some examples..." (lines 7509-7511).
- SOURCE FACT (SF-N21) — Predication exception: "`st.param` and `ld.param` instructions used for argument passing cannot be predicated." (lines 6260-6261). This exception does not mention `not`.
- SOURCE FACT (SF-N22) — Section 5.2.2 "Restricted Use of Sub-Word Sizes" (anchor `restricted-use-of-sub-word-sizes`, line 3070): "The `.u8`, `.s8`, and `.b8` instruction types are restricted to `ld`, `st`, `add`, `sub`, `min`, `max`, `neg` and `cvt` instructions." (lines 3074-3075). `.b32` is not a restricted sub-word size; no `.b32`-specific restriction for `not` was found in the sections read (negative evidence, A-8).
- Negative search results: a literal search for `@p not` returned 0 matches; this supports no claim about predication of `not`, which is governed by the general rule of SF-N11 (A-9). Literal searches for `not.b64`, `not.b16`, and `not.b32 %` returned 0 matches; `not.pred` returned 1 match (the example at line 14388); `not.b32` returned 2 matches (the example at line 14387 and the `cnot.b32 d,a;` example at line 14420, which is a different instruction). The zero-match searches support no claims beyond the recorded facts (A-9).

## 4. Proposed minimal architecture

This section proposes the minimal architecture components required for the future formalization of `not.b32`. No Lean code is written; each component states its source grounding and the proposed design.

- DESIGN CHOICE (D-1) — PTX instruction representation: a structured instruction form with fields: optional guard (`@{!}p`), mnemonic (`not`), type specifier (`.b32`), destination operand, and a single source operand `a`. Grounding: SF-N2, SF-N11, SF-N12, SF-N13.
- DESIGN CHOICE (D-2) — Operand categories for the bounded base form: (a) destination register, (b) source register, (c) source constant immediate (candidate; see AMB-2, OQ-1). A bit-bucket destination `_` is a candidate alternative destination form (see OQ-2). Grounding: SF-N2 (two-operand syntax), SF-N8 (register operands), SF-N10 (sibling immediate examples), SF-N13 (bit bucket).
- DESIGN CHOICE (D-3) — Scalar type and width representation: a fundamental type is represented as a pair (basic type, size in bits); `.b32` maps to (Bits/Untyped, 32). A minimal type lattice is needed only up to the types that `not.b32` and its operand-compatibility rule require. Grounding: SF-N14, SF-N15, SF-N16, SF-N5.
- DESIGN CHOICE (D-4) — Register/value representation: register variables always carry a fundamental type (SF-N14); values for `.b32` live in a fixed-width 32-bit untyped bit-value domain; a register file maps register names to values of their declared type. Predicate registers are 1-bit (SF-N16) and are mapped to a two-valued domain by design (D-13). Grounding: SF-N14, SF-N16, SF-N18, SF-N19.
- DESIGN CHOICE (D-5) — Minimal machine state: for the bounded base scalar `not.b32`, the state contains only a value-register file and a predicate-register file. No memory state space, shared state, or special-register state space is required by the bounded base form. Grounding: SF-N2 (base form `not.type d, a;` has no memory/sreg operand), SF-N3 (destination is a register), SF-N16 (`.reg` state space).
- DESIGN CHOICE (D-6) — State reads and destination update: the source value is read from a register or constant immediate; when the instruction executes, the destination register is updated with the bitwise complement of the source value (candidate semantic content recorded as SF-N4 `d = ~a;`); when the complete guard expression evaluates false, the state is unchanged. Grounding: SF-N4, SF-N12, SF-N20; the guard-false consequence is an interpretation recorded in Section 11 (A-4) and Section 13 (OQ-3).
- DESIGN CHOICE (D-7) — Guard/predication architecture: the guard is an optional `.pred`-typed register reference, optionally negated (`@!p`); presence of a guard makes execution conditional; absence makes execution unconditional. Grounding: SF-N11, SF-N12, SF-N13.
- DESIGN CHOICE (D-8) — Execution-result / outcome representation: an instruction-local outcome type with at least two cases — "executed" (with updated state) and "guard false" (no state change). No error constructor is proposed yet because the official source read defines no exceptional behavior for the bounded base `not.b32` form (see A-6).
- DESIGN CHOICE (D-9) — Version and target-restriction representation for the base `not.b32` form: a record pairing a PTX ISA version bound ("introduced in" version) with a target requirement. For base `not.b32`: introduced-in PTX ISA 1.0; target requirement "all target architectures". Grounding: SF-N6, SF-N7.
- DESIGN CHOICE (D-10) — Traceability representation: every semantic claim carries (document identity, specification version, section heading, HTML anchor, HTML line range, source SHA-256). Grounding: SF-N1 and the evidence index in Section 14.

## 5. Fact-to-design mapping

| Source fact | Design component |
|---|---|
| SF-N2, SF-N13 (syntax; operand format) | D-1 (instruction representation) |
| SF-N2, SF-N8, SF-N10, SF-N13 (two-operand syntax; register operands; sibling immediate examples; bit bucket) | D-2 (operand categories) |
| SF-N14, SF-N15, SF-N16, SF-N5 (fundamental types; compatibility; register widths; family size-matching note) | D-3 (scalar type/width) |
| SF-N14, SF-N16, SF-N18, SF-N19 (register variables of fundamental type; `.reg` state space; predicate 1-bit; naming) | D-4 (register/value representation) |
| SF-N2, SF-N3, SF-N16 (base form operands; destination register; `.reg` state space) | D-5 (minimal machine state) |
| SF-N4, SF-N12, SF-N20 (semantics `d = ~a;`; conditional execution; instruction description format) | D-6 (state reads and destination update) |
| SF-N11, SF-N12, SF-N13 (predicability; guard syntax; guard prefix; operand format) | D-7 (guard/predication) |
| Negative evidence in SF-N3/SF-N4 region (no exceptional behavior for base not.b32; A-6) | D-8 (outcome representation) |
| SF-N6, SF-N7 (PTX ISA Notes; Target ISA Notes) | D-9 (version/target restriction representation) |
| SF-N1 and manifest metadata | D-10 (traceability representation) |
| SF-N16, SF-N18, SF-N19 (register state space; declaration; naming) | D-11, D-12, D-13, D-14, D-15 (register/value/state foundations) |
| SF-N2, SF-N8, SF-N10, SF-N13 (two-operand syntax; register operands; sibling immediates; bit bucket) | D-16, D-17, D-18 (operand architecture) |
| SF-N11, SF-N12, SF-N13 (guard syntax; guard prefix; examples) | D-19, D-20, D-21 (predication architecture) |
| SF-N6, SF-N7, SF-N9 (version and target notes; family intro) | D-22, D-23, D-24 (version/target representation) |

### Dependency graph

The bounded base `not.b32` unit depends on the following shared foundations, all grounded in Section 3:

- Type/width model (D-3) depends on SF-N14, SF-N15, SF-N16 (fundamental types, compatibility, register widths) and SF-N5 (family size-matching rule).
- Register/value model (D-4, D-11, D-12, D-13) depends on SF-N14, SF-N16, SF-N18, SF-N19 (typed register variables, `.reg` state space, predicate 1-bit, naming).
- Minimal state (D-5, D-14) depends on SF-N2, SF-N3, SF-N16 (base-form operand shape, register destination, `.reg` state space).
- Instruction representation (D-1) depends on SF-N2, SF-N11, SF-N12, SF-N13 (syntax, predicability, guard syntax, operand format).
- Operand architecture (D-16, D-17, D-18) depends on SF-N2, SF-N8, SF-N10, SF-N13.
- Predication architecture (D-19, D-20, D-21) depends on SF-N11, SF-N12, SF-N13, SF-N18.
- Version/target representation (D-22, D-23, D-24) depends on SF-N6, SF-N7, SF-N9.
- Validation/proof-obligation families (Section 10) depend on all of the above.
- Out-of-scope future dependencies (not commitments of this unit): the predicate form `not.pred` and the `.b16`/`.b64` forms (SF-N2, SF-N8, SF-N9) for future units; special-register state space (SF-N17) is not needed by the base form; no memory/address semantics are required.

## 6. Register, value, and state foundations

The register/value/state architecture is grounded in the official register and type sections read in this pass (Section 5.1.1 Register State Space; Section 5.2.1 Fundamental Types; Section 5.4 variable declaration; Section 5.4.6 Parameterized Variable Names).

- DESIGN CHOICE (D-11) — The value domain for `.b32` is proposed as a fixed-width 32-bit untyped bit-value domain (e.g., 32-bit bit vectors); the exact Lean representation is a Lean-mapping decision outside this artifact. This differs from an unsigned-integer domain because `.b32` is the "Bits (untyped)" basic type (SF-N14) and the logic/shift family is described as "fundamentally untyped, performing bit-wise operations" (SF-N9).
- DESIGN CHOICE (D-12) — Registers are represented by names (identifiers) mapped to values, not by values alone, to support declaration typing and destination updates. Register references are by name rather than address because the official source states that registers are not fully addressable (SF-N16).
- DESIGN CHOICE (D-13) — Predicate register values are represented by a two-valued (boolean-like) domain, grounded in the official statement that predicate registers are 1-bit (SF-N16) and in the boolean-style use of predicates in `setp` examples (SF-N12). The exact encoding of "1-bit" into a Lean value domain is a Lean-mapping decision (see A-7, OQ-5).
- DESIGN CHOICE (D-14) — The minimal state for the bounded base `not.b32` is the pair (value-register file, predicate-register file). No memory state space, special-register state space, or other state space is included because the bounded base form has no memory or special-register operands and its description writes only to a destination register (SF-N2, SF-N3). The official `.reg` state-space text (SF-N16) supports the register-file model, and the rule that predicate variables may only be declared in the register state space (SF-N18) supports placing predicate registers in the same overall register state space rather than a separate one.
- DESIGN CHOICE (D-15) — Compilation-level and ABI notes in the register section (register spilling, function-scope restriction, legacy module-scope handling, alignment for multi-word loads/stores; SF-N16) are not modeled in the instruction-local architecture for `not.b32`. Whether any of these affect a future program-level semantics is an open question outside the bounded unit (OQ-6).

## 7. Operand architecture

- DESIGN CHOICE (D-16) — The bounded base `not.b32` form has exactly two operands in the order `d, a` (SF-N2). The operand-position roles of section 9.2 (destination `d`; source `a`) apply (SF-N13). The official example `not.b32 mask,mask;` (SF-N8) shows the destination and source may be the same register.
- DESIGN CHOICE (D-17) — The source operand `a` may be a register variable, because the official example `not.b32 mask,mask;` uses register operands (SF-N8) and the description "Invert the bits in `a`" is satisfied by a register source (SF-N3). Whether `a` may also be a constant immediate is not explicitly evidenced in the `not` section itself; sibling family examples (`or.b32 ...0x00010001`, `xor.b16 d,x,0x0001;`, SF-N10) show immediates in the same family. An immediate is therefore a candidate source category pending semantic-phase confirmation (AMB-2, OQ-1). If adopted, an immediate is modeled as a constant whose size is compatible with the instruction type under SF-N15.
- DESIGN CHOICE (D-18) — The destination operand `d` is a register variable in the `.reg` state space (SF-N3, SF-N16), or the bit bucket `_` as a candidate alternative (SF-N13; applicability to `not` is an open question, OQ-2). When `d` is `_`, the result is discarded and no destination register is updated (candidate behavior; see OQ-2).

## 8. Predication architecture

Predication is expressed uniformly by evaluation of the complete guard expression. The complete guard expression is: "true" when no guard is present; the value of the predicate register `p` for `@p`; and the negation of the value of `p` for `@!p`.

- DESIGN CHOICE (D-19) — Guard evaluation rule: an instruction executes if and only if its complete guard expression evaluates true. Cases: no guard — the complete guard expression is true and the instruction executes unconditionally (SF-N12); `@p` — the complete guard expression evaluates to the value of predicate `p` (SF-N12); `@!p` — the complete guard expression evaluates to not (value of `p`) (SF-N12).
- DESIGN CHOICE (D-20) — No state update is proposed only when the complete guard expression evaluates false. This single rule covers `@p` (no update when `p` is false) and `@!p` (no update when `not p` is false, i.e., when `p` is true), and it is the only guard-false consequence used in this architecture (D-6, D-8, A-4, OQ-3).
- DESIGN CHOICE (D-21) — A guard refers to a `.pred`-typed predicate register variable in the register state space (SF-N12, SF-N18). The guard is written with an `@` prefix to the left of the opcode (SF-N12, SF-N13). The `st.param`/`ld.param` predication exception (SF-N21) does not mention `not`.
- Predication is applicable to `not`: "All PTX instructions may be predicated" (SF-N11). No `not`-specific predication example was found in a literal search (A-9), and none is required because the general rule governs.

## 9. Version and target representation

For the bounded base unit, version and target representation covers only the base `not.b32` facts.

- DESIGN CHOICE (D-22) — Version restrictions are represented as an "introduced-in" lower bound over PTX ISA versions. For base `not.b32` the bound is PTX ISA 1.0 (SF-N6).
- DESIGN CHOICE (D-23) — Target restrictions are represented as a requirement predicate over target architectures. For base `not.b32` the requirement is "all target architectures" (SF-N7). A target-gating validation obligation (VAL-6) checks that the recorded requirement matches the official Target ISA Notes.
- DESIGN CHOICE (D-24) — The family intro (SF-N9) states that `and`, `or`, `xor`, and `not` also operate on predicates, and the sibling `or`/`xor` sections carry the same "Introduced in PTX ISA version 1.0" and "Supported on all target architectures" notes (SF-N10). These are recorded as source facts but are not treated as additional commitments for the bounded base `not.b32` beyond its own notes; the predicate form and sibling instructions are out of the bounded base scope (D-0c, OQ-4).

## 10. Meaningful validation and theorem-obligation families

This section distinguishes validation obligations (definitional well-formedness checks performed at parse/type-validation time) from proof obligations (theorems stated over a future execution relation). No Lean statements are given. The exact bit-complement semantics `d = ~a;` (SF-N4) is recorded as a source fact but its Lean formalization is a semantic-phase matter (OQ-8).

- DESIGN CHOICE (D-25) — The future execution semantics for `not.b32` is designed to be represented as an execution relation between (state, instruction) and state, not merely as a function. Determinism and frame/locality obligations are stated as properties of that relation. This avoids theorem obligations that hold only because a total-function data structure was chosen.
- DESIGN CHOICE (D-26) — Validation obligations (VAL-1 through VAL-6 below) are definitional checks, not theorem obligations. They are run as part of parsing, typing, and gating validation; they are not proposed as proofs of semantic properties.

Validation obligations:

| ID | Obligation | Kind | Grounding | Non-vacuity note |
|---|---|---|---|---|
| VAL-1 | Type well-formedness: the instruction type specifier `.b32` is a valid bit-size fundamental type of 32-bit width. | validation | SF-N2, SF-N14, SF-N16 | Definitional check over the type representation; not a semantic theorem. |
| VAL-2 | Operand typing: operands `d` and `a` are size-compatible with instruction type `.b32` (32-bit operands), consistent with the family rule "the size of the operands must match, but not necessarily the type" and the bit-size compatibility rule. | validation | SF-N5, SF-N15 | Definitional check over the operand-typing relation; the exact formulation of the size-based compatibility rule is an open question (OQ-7). |
| VAL-3 | Guard well-typedness: if a guard is present, it refers to a `.pred`-typed predicate register variable in the register state space. | validation | SF-N12, SF-N18 | Definitional check over the guard representation. |
| VAL-4 | Destination membership: the destination operand denotes a declared register variable, or is the bit bucket `_` (if adopted; OQ-2). | validation | SF-N18, SF-N13 | Definitional check over the destination representation. |
| VAL-5 | Version gating: the recorded introduced-in bound for base `not.b32` matches the official PTX ISA Note (PTX ISA 1.0). | validation | SF-N6 | Conformance check that the model's version metadata derives from the official note; a derivation check, not a theorem about semantics. |
| VAL-6 | Target gating: the recorded target requirement for base `not.b32` matches the official Target ISA Note ("all target architectures"). | validation | SF-N7 | Conformance check on target metadata; near-trivial by design because the base form has no family restriction. |

Proof obligations (candidate families, stated over the future execution relation):

| ID | Obligation | Grounding | Non-vacuity note |
|---|---|---|---|
| PRF-1 | Determinism: for any well-formed state and well-typed instruction, the execution relation relates at most one resulting state. | A-3 (no nondeterminism evidenced) | Stated over a relation, so it does not hold merely by representing semantics as a function (D-25). |
| PRF-2 | Destination-only update / frame: when the instruction executes with a register destination, only the destination register may change; every other value register and every predicate register is unchanged. | SF-N3 (writes the inverted bits of `a` to `d`), SF-N2 (single destination) | Meaningful locality/frame obligation over the execution relation; it rules out spurious updates and is not derivable from a functional state representation alone. |
| PRF-3 | Bit-bucket discard: when the destination is `_`, execution changes no value register. | SF-N13 (bit bucket; applicability OQ-2) | Meaningful frame obligation specific to the bit-bucket form, if adopted. |
| PRF-4 | Guard-false frame: when the complete guard expression evaluates false, the entire state is unchanged. | SF-N12, D-20 | Meaningful guard-behavior frame obligation covering both `@p` and `@!p` uniformly. |
| PRF-5 | Guard-behavior: the instruction executes if and only if the complete guard expression evaluates true; the no-guard, `@p`, and `@!p` cases satisfy the D-19 rule. | SF-N11, SF-N12 | Relates guard evaluation to the execution relation; the `@!p` case is stated without an erroneous "negated guard true means no-op" phrasing. |
| PRF-6 | Result-domain membership: when the instruction executes, the value written to the destination lies in the 32-bit bit-size value domain of `.b32`. | SF-N14, D-11 | Typing-soundness-style obligation over the execution relation; it does not assert which bits are written. Vacuity risk noted: under a typed register-file representation, membership may hold definitionally; this obligation may need reclassification in the semantic phase (A-10). |
| PRF-7 | Bit-complement fidelity (candidate): when the instruction executes with a register source, the value written to the destination equals the bitwise complement of the value read from the source. | SF-N4 (`d = ~a;`) | Meaningful semantic property for a bitwise-negation instruction; the exact formal statement (including the representation of bitwise complement over the 32-bit bit-value domain) is a semantic-phase matter (OQ-8). It is listed as a candidate family, not as a completed obligation. |

## 11. Assumptions

- ASSUMPTION (A-1) — The HTML document is authoritative for this unit; the manifest-recorded PDF was not read.
- ASSUMPTION (A-2) — Instruction-local semantics (a single instruction evaluated against a minimal state) is sufficient for the bounded base `not.b32`; no program-counter, memory, or concurrency context is required for the architecture foundations.
- ASSUMPTION (A-3) — The bounded base `not.b32` is deterministic; no nondeterminism is evidenced in the official source read. This is an assumption based on absence of evidence in the sections read, not a source fact; it must be re-verified in the semantic phase (PRF-1).
- ASSUMPTION (A-4) — The guard-false consequence "no state update" is the intended meaning of "controls conditional execution" (SF-N12), supported by the guard examples (SF-N12); this interpretation is pending human approval (OQ-3).
- ASSUMPTION (A-5) — "not.b32" in this artifact denotes the scalar 32-bit bit-size form of the `not` instruction, per D-0c.
- ASSUMPTION (A-6) — The official source read defines no error, trap, or exceptional behavior for the bounded base `not.b32` form; therefore the outcome representation (D-8) has no error constructor for this unit. This is an assumption based on absence of evidence in lines 14358-14391 and the sections read, not a source fact; the semantic phase must re-verify.
- ASSUMPTION (A-7) — The 1-bit predicate register (SF-N16) is mapped to a two-valued (boolean-like) value domain by design; the exact encoding is a Lean-mapping decision (D-13, OQ-5).
- ASSUMPTION (A-8) — Negative evidence: `.b32` is not among the sub-word sizes restricted by section 5.2.2 (SF-N22), and no `.b32`-specific restriction for `not` was found in the sections read. This is an assumption based on absence of evidence, not a source fact.
- ASSUMPTION (A-9) — Literal searches for `@p not`, `not.b64`, `not.b16`, and `not.b32 %` returned zero matches each. These negative results support no claims about predication of `not` (governed by the general rule of SF-N11) and no claims about the existence of other `not` forms beyond the official section text.
- ASSUMPTION (A-10) — PRF-6 (result-domain membership) may be definitionally vacuous under the proposed typed register-file representation (D-4, D-11), following the mov.b32 critique lesson (F-3). This is an assumption about the eventual Lean representation, not a source fact; the semantic phase must decide whether to reclassify PRF-6 as a validation-style well-formedness obligation.

## 12. Ambiguities

- AMBIGUITY (AMB-1) — The unit `not.b32` is one type instance of the `not` instruction of section 9.7.8.4, whose type set is `{ .pred, .b16, .b32, .b64 }` (SF-N2). This artifact bounds the base unit to `.b32` (D-0c); the `.pred`, `.b16`, and `.b64` forms remain candidate future units (OQ-4).
- AMBIGUITY (AMB-2) — Whether the source operand `a` of `not.b32` may be a constant immediate is not explicitly evidenced in the `not` section: its description and examples use register operands only (SF-N3, SF-N8). Sibling family examples (`or.b32 ...0x00010001`, `xor.b16 d,x,0x0001;`) show immediates in the same family (SF-N10). The resolution for the bounded base unit is deferred (OQ-1).
- AMBIGUITY (AMB-3) — Whether the bit-bucket `_` is a permitted destination for the scalar `not.b32` form is not explicitly evidenced in the `not` section; the general 9.2 rule (SF-N13) exists, but a `not`-specific example was not read. This is an open question (OQ-2), not a resolved design commitment.

## 13. Open questions

- OPEN QUESTION (OQ-1) — Whether the source operand `a` of `not.b32` may be a constant immediate (AMB-2). The `not` section does not state it explicitly; sibling family examples show immediates (SF-N10). Resolution is deferred to the semantic-interpretation phase; VAL-2 and D-17 must be revisited accordingly.
- OPEN QUESTION (OQ-2) — Whether the bit bucket `_` is permitted as the destination of the scalar `not.b32` form (AMB-3). The general 9.2 rule (SF-N13) exists, but no `not` `_` example was read; resolution is needed before PRF-3 is treated as faithful.
- OPEN QUESTION (OQ-3) — The exact consequence of a false guard predicate beyond the "controls conditional execution" wording (SF-N12) is interpreted here as "no state update" (A-4); this interpretation needs human approval before the guard-false obligations (PRF-4) are treated as faithful to the specification.
- OPEN QUESTION (OQ-4) — Whether the `.pred`, `.b16`, and `.b64` forms of `not` (and the sibling family instructions `and`, `or`, `xor`) should be modeled as separate later units; the bounded task covers only the `.b32` scalar form (D-0c, AMB-1).
- OPEN QUESTION (OQ-5) — The exact Lean encoding of the 1-bit predicate register value domain (D-13, A-7) is a Lean-mapping decision that must be made and human-approved in the Lean-mapping phase.
- OPEN QUESTION (OQ-6) — Whether compilation-level register notes (spilling, function-scope/ABI restriction, module-scope legacy handling; SF-N16) impose constraints that a future program-level semantics must model; they are excluded from the instruction-local architecture (D-15).
- OPEN QUESTION (OQ-7) — How the family operand-typing rule "The size of the operands must match, but not necessarily the type" (SF-N5) should be formulated for `not.b32` together with the bit-size compatibility rule (SF-N15): whether a register declared `.u32`, `.s32`, or `.f32` is an acceptable operand for instruction type `.b32`, and how immediate values (if adopted) are typed under the same rules. Resolution is deferred to the semantic-interpretation phase.
- OPEN QUESTION (OQ-8) — The exact Lean statement of the bit-complement fidelity candidate obligation PRF-7 ("the value written equals the bitwise complement of the value read", grounded in SF-N4 `d = ~a;`), including the representation of bitwise complement over the 32-bit bit-value domain, is a semantic-phase matter; the architecture records the candidate family only.

## 14. Evidence index with section headings, anchors, HTML line ranges, and source SHA-256

Source SHA-256 abbreviations: HTML = `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856` (ptx_isa_9.3.html); MANIFEST = `622e6ce0d3114a909a62726530955993b5f2b98d2f60e45ae1ceb429512208f2` (source-manifest.json); SUMS = `e02f4feadfce614282d3d4774ed21dd87985202d4ea9ad84ead60c688a6c0ecd` (SHA256SUMS).

| # | Section heading | Anchor | Lines | Source | SHA-256 | Status |
|---|---|---|---|---|---|---|
| E-1 | source-manifest.json (run/unit metadata; initial_formalization_unit = add.u32) | (n/a) | manifest lines 1-38 | manifest | MANIFEST | Read |
| E-2 | 9.7.8.4 Logic and Shift Instructions: not (heading/section extent) | `logic-and-shift-instructions-not` | 14358-14391 | HTML | HTML | Read |
| E-3 | 9.7.8.4 not — Syntax | `logic-and-shift-instructions-not` | 14366-14369 | HTML | HTML | Read |
| E-4 | 9.7.8.4 not — Description | `logic-and-shift-instructions-not` | 14363, 14371-14372 | HTML | HTML | Read |
| E-5 | 9.7.8.4 not — Semantics block (`d = ~a;`) | `logic-and-shift-instructions-not` | 14374-14377 | HTML | HTML | Read |
| E-6 | 9.7.8.4 not — Notes (size matching; predicates) | `logic-and-shift-instructions-not` | 14378-14380 | HTML | HTML | Read |
| E-7 | 9.7.8.4 not — PTX ISA Notes | `logic-and-shift-instructions-not` | 14381-14382 | HTML | HTML | Read |
| E-8 | 9.7.8.4 not — Target ISA Notes | `logic-and-shift-instructions-not` | 14383-14384 | HTML | HTML | Read |
| E-9 | 9.7.8.4 not — Examples | `logic-and-shift-instructions-not` | 14385-14390 | HTML | HTML | Read |
| E-10 | 9.7.8 Logic and Shift Instructions (intro; family is untyped; `not` operates on predicates) | `logic-and-shift-instructions` | 14236-14255 | HTML | HTML | Read |
| E-11 | 9.7.8.2 or — immediate example `or.b32 mask mask,0x00010001` | `logic-and-shift-instructions-or` | 14291-14323 | HTML | HTML | Read |
| E-12 | 9.7.8.3 xor — immediate example `xor.b16 d,x,0x0001;` | `logic-and-shift-instructions-xor` | 14324-14357 | HTML | HTML | Read |
| E-13 | 9.7 Instructions (intro; predicability) | `instructions` | 8718-8723 | HTML | HTML | Read |
| E-14 | 9.3 Predicated Execution | `predicated-execution` | 7537-7574 | HTML | HTML | Read |
| E-15 | 9.2 PTX Instructions (operand format; bit bucket) | `ptx-instructions` | 7513-7536 | HTML | HTML | Read |
| E-16 | 5.2.1 Fundamental Types | `fundamental-types` | 3015-3068 | HTML | HTML | Read |
| E-17 | Table 8 Fundamental Type Specifiers | `fundamental-types-fundamental-type-specifiers` | 3025-3061 | HTML | HTML | Read |
| E-18 | 5.1.1 Register State Space | `register-state-space` | 2613-2631 | HTML | HTML | Read |
| E-19 | 5.1.2 Special Register State Space | `special-register-state-space` | 2633-2640 | HTML | HTML | Read |
| E-20 | 5.4 Variables (declaration rule; predicate-only-in-register) | `variables` | 3741-3755 | HTML | HTML | Read |
| E-21 | 5.4.6 Parameterized Variable Names | `parameterized-variable-names` | 3933-3947 | HTML | HTML | Read |
| E-22 | 9.1 Format and Semantics of Instruction Descriptions | `format-and-semantics-of-instruction-descriptions` | 7505-7512 | HTML | HTML | Read |
| E-23 | st.param/ld.param predication exception | (anchor not captured) | 6260-6261 | HTML | HTML | Read (snippet) |
| E-24 | 5.2.2 Restricted Use of Sub-Word Sizes | `restricted-use-of-sub-word-sizes` | 3070-3076 | HTML | HTML | Read |
| E-25 | SHA256SUMS (HTML/PDF hashes) | (n/a) | lines 1-3 | SUMS | SUMS | Read |
| E-26 | Literal searches: `@p not` (0), `not.b64` (0), `not.b16` (0), `not.b32 %` (0), `not.pred` (1, line 14388), `not.b32` (2, lines 14387, 14420) | (n/a) | (search) | HTML | HTML | Search (this pass) |

## 15. Finding-resolution notes (no prior critique)

No prior `not.b32` architecture artifact or critique exists; there are no findings F-1..F-n for this artifact. The lessons of the add.u32 foundation v1 critique (`candidates/ptx/9.3/reviews/add-u32-foundation-v1-critic.md`) and the mov.b32 foundation v1 critique (`candidates/ptx/9.3/units/mov-b32/reviews/architecture-critic-v1.md`) were applied proactively:

| add.u32 / mov.b32 finding | Lesson applied in this artifact |
|---|---|
| add F-1 (project status/scope mislabeled SOURCE FACT) | Section 1 separates project status and scope as metadata/DESIGN CHOICE; SOURCE FACT reserved for specification-grounded facts (SF-N1..SF-N22). |
| add F-2 (fifth label OBSERVATION) | Only four labels are used: SOURCE FACT / DESIGN CHOICE / ASSUMPTION / OPEN QUESTION; negative evidence is labeled ASSUMPTION (A-8, A-9). |
| add F-3 / F-9 (register chapter unread) | Register/value/state foundations grounded in official reads: SF-N14, SF-N16, SF-N17, SF-N18, SF-N19. |
| add F-5 / F-6 (negated-guard phrasing) | Guard-false behavior stated uniformly via the complete guard expression (D-19, D-20, PRF-4, PRF-5); no "negated guard true means no-op" phrasing. |
| add F-7 (vacuity risk) | Validation vs. proof obligations distinguished; proof obligations are relational and include frame/locality and guard-behavior families (D-25, D-26, Section 10). |
| mov F-3 (PRF-6 vacuity risk) | PRF-6 result-domain membership records the vacuity risk explicitly (A-10) and defers reclassification to the semantic phase. |
| add F-8 (inaccurate checklist/anchors) | Anchors verified via the restricted spec tools and recorded in Section 14; Gate A checklist in Section 16 reflects actual state. |
| add F-10 (phantom cross-references) | Cross-references only to sections and anchors actually present in this artifact. |
| mov F-1/F-2 (evidence-index precision) | Evidence index line ranges and line attributions were checked against the actual reads (Section 14). |

## 16. Gate A review checklist

Gate A is NOT ready. This artifact must receive an independent re-critique before it may be presented for human Gate A review. The following items are the checklist for that future review:

- [ ] The artifact is marked `DRAFT — NOT HUMAN APPROVED` and is not promoted to `accepted/`.
- [ ] Scope is bounded to language-wide foundations strictly required for future `not.b32` formalization, with the scalar `.b32` form as the bounded base interpretation (D-0, D-0c, AMB-1).
- [ ] Project status and bounded scope are classified as project design choices or metadata, not SOURCE FACT.
- [ ] Every architectural/semantic statement uses exactly one of SOURCE FACT / DESIGN CHOICE / ASSUMPTION / OPEN QUESTION; plain metadata notes are identified as such.
- [ ] Every SOURCE FACT is traceable to an official source entry in the evidence index (Section 14).
- [ ] Register/value/state architecture is grounded in official reads (SF-N14, SF-N16, SF-N17, SF-N18, SF-N19; Section 6).
- [ ] Operand architecture is grounded in the `not` syntax/description/examples and section 9.2 operand format (SF-N2, SF-N3, SF-N8, SF-N13; Section 7).
- [ ] Predication is expressed uniformly by evaluation of the complete guard expression for no-guard, `@p`, and `@!p`; no state update is proposed only when the complete guard expression evaluates false (D-19, D-20).
- [ ] Validation obligations and proof obligations are distinguished; proof obligations are relational, non-vacuous, and include frame/locality and guard-behavior families; the PRF-6 vacuity risk is recorded (Section 10).
- [ ] Version and target representation is limited to base `not.b32` (PTX ISA 1.0; all target architectures) (Section 9).
- [ ] Evidence anchors are verified: `logic-and-shift-instructions-not` (E-2), `logic-and-shift-instructions` (E-10), `logic-and-shift-instructions-or` (E-11), `logic-and-shift-instructions-xor` (E-12), `instructions` (E-13), `predicated-execution` (E-14), `ptx-instructions` (E-15), `fundamental-types` (E-16), `register-state-space` (E-18), `special-register-state-space` (E-19), `variables` (E-20), `parameterized-variable-names` (E-21), `format-and-semantics-of-instruction-descriptions` (E-22), `restricted-use-of-sub-word-sizes` (E-24).
- [ ] Negative-evidence items are labeled ASSUMPTION or OPEN QUESTION and are flagged for semantic-phase re-verification (A-3, A-6, A-8, A-9, A-10).
- [ ] Ambiguities are explicitly recorded (AMB-1, AMB-2, AMB-3; Section 12).
- [ ] Unsupported or unread points are marked OPEN QUESTION rather than guessed (Section 13).
- [ ] No instruction-level semantics of `not.b32` were extracted or defined beyond the recorded source-fact Semantics block `d = ~a;` (SF-N4); the bit-complement fidelity obligation is a candidate family only (PRF-7, OQ-8).
- [ ] No `not.b32` source bundle was constructed, and no Lean code was written (D-0b).
- [ ] No other instruction form was modeled as a separate unit; the `.pred`/`.b16`/`.b64` forms and sibling family instructions are explicitly out of scope (D-0c, OQ-4).
- [ ] Dependencies required before `not.b32` formalization are represented in the design choices and dependency graph (Section 5) and validated in Section 10.

## 17. Explicit non-goals

- DESIGN CHOICE (D-27) — Not defining the exact Lean semantics of the `not.b32` bitwise-complement operation beyond the recorded source-fact Semantics block `d = ~a;` (SF-N4); the exact formal statement (including the candidate bit-complement fidelity obligation PRF-7) is deferred to the semantic phase (OQ-8).
- DESIGN CHOICE (D-28) — Not writing any Lean code or concrete Lean theorem statements.
- DESIGN CHOICE (D-29) — Not constructing a `not.b32` instruction-level source bundle.
- DESIGN CHOICE (D-30) — Not modeling the `.pred`, `.b16`, or `.b64` forms of `not` or the sibling logic/shift instructions (`and`, `or`, `xor`, `cnot`, `lop3`, `shf`, `shl`, `shr`) as units; their existence and family-level notes are recorded as source facts (SF-N2, SF-N8, SF-N9, SF-N10) but are not architecture commitments of the bounded base unit.
- DESIGN CHOICE (D-31) — Not building a memory, state-space, or concurrency model for this unit.
- DESIGN CHOICE (D-32) — Not resolving within this artifact the deferred open questions OQ-1 (immediate source), OQ-2 (bit bucket), OQ-7 (operand-typing formulation), and OQ-8 (exact Lean statement of PRF-7); they are the property of the semantic phase and future units.
- DESIGN CHOICE (D-33) — Not approving Gate A; approval is a human decision, and Gate A remains not ready until this artifact receives an independent re-critique. Not promoting anything to `accepted/`.
