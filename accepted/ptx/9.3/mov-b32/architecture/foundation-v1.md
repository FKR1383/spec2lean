# PTX mov.b32 Foundation Architecture v1 — DRAFT — NOT HUMAN APPROVED

## 1. Revision status and bounded scope

Status note (project metadata, not specification evidence): this artifact is a DRAFT architecture candidate produced for a future Gate A review. It is marked `DRAFT — NOT HUMAN APPROVED`. It has not been reviewed or approved by a human reviewer, it is not promoted to `accepted/`, and it does not claim that Gate A is ready.

- DESIGN CHOICE (D-0) — The bounded scope of this artifact is the language-wide foundations strictly required for the future formalization of PTX ISA 9.3 `mov.b32`: instruction representation, operand categories, bit-size scalar types, register/value representation, minimal machine state, state reads and destination updates, predication, execution-result representation, version/target-restriction representation, traceability, and candidate validation/proof-obligation families. Scope is a project design decision of this artifact, not an official-source fact.
- DESIGN CHOICE (D-0b) — This artifact describes architecture only. It does not define the instruction-level semantics of `mov.b32`, does not construct an instruction-level source bundle, and does not contain Lean code.
- DESIGN CHOICE (D-0c) — "mov.b32" in this artifact denotes the scalar value-copy form `mov.type d, a;` with instruction type `.b32` and with source operand `a` being a register variable or an immediate value, as described by the `mov` section 9.7.9.3 opening sentence "Set a register variable with the value of a register variable or an immediate value." The other source-operand categories of the same section (`sreg`, `avar`, `avar+imm`, `fname`, `kernel`) and the distinct vector pack/unpack form of section 9.7.9.4 are recorded as official source facts where required for completeness but are not modeled as commitments of the bounded base unit (see D-24, OQ-1, OQ-4).
- Metadata note (not specification evidence): the run metadata `runs/ptx-9.3-mov.b32-f910feea/run.json` designates unit `mov.b32` for this run, whereas the source manifest `documents/sources/nvidia/ptx/9.3/source-manifest.json` records `initial_formalization_unit` as `add.u32` (manifest lines 9-15). Per the orchestrator contract, run metadata is authoritative for the current run; the manifest's `add.u32` record predates this run and is a project-metadata discrepancy, not specification evidence.
- The unit identity `mov.b32` (instruction family `mov`, section 9.7.9.3, heading "Data Movement and Conversion Instructions: mov", HTML anchor `data-movement-and-conversion-instructions-mov`, with the same family and `.b32` type also appearing in section 9.7.9.4) is grounded in official-source facts recorded as SF-M1 and SF-M10 in Section 3.

## 2. Inputs and critique addressed

No prior `mov.b32` architecture artifact or critique exists under `candidates/ptx/9.3/units/mov-b32`; this is foundation-v1. Inputs used:

- `runs/ptx-9.3-mov.b32-f910feea/run.json` (run metadata; unit `mov.b32`; stage ARCHITECTURE; gates A-FINAL pending).
- `documents/sources/nvidia/ptx/9.3/source-manifest.json` and `documents/sources/nvidia/ptx/9.3/SHA256SUMS` (source identity and hashes).
- `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` (official PTX ISA 9.3 HTML; all source facts in Section 3 were read from this file via the restricted specification tools).
- `candidates/ptx/9.3/architecture/add-u32-foundation-v2.md` and `candidates/ptx/9.3/reviews/add-u32-foundation-v1-critic.md` were used as the structural template and for the lessons of findings F-1..F-10; those lessons were applied proactively (four-label taxonomy, register-chapter evidence read, uniform guard-false phrasing, relational non-vacuous obligations, verified anchors, negative-evidence labeling). There is no `mov.b32`-specific critic yet; the artifact must receive an independent critique before Gate A.

## 3. Official-source facts

Primary source: `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html`, official NVIDIA "Parallel Thread Execution ISA" version 9.3, SHA-256 `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`, 47,743 lines. Metadata sources: `source-manifest.json`, SHA-256 `622e6ce0d3114a909a62726530955993b5f2b98d2f60e45ae1ceb429512208f2`; `SHA256SUMS`, SHA-256 `e02f4feadfce614282d3d4774ed21dd87985202d4ea9ad84ead60c688a6c0ecd` (3 lines, records the HTML and PDF hashes). The manifest records a PDF artifact (`raw/ptx_isa_9.3.pdf`, SHA-256 `769cc12e363e7bb9cd311464f2a42edbdaf4c74ca18575de8c358e93223434fc`); the PDF was not read in this pass (A-1).

- SOURCE FACT (SF-M1) — Section 9.7.9.3 "Data Movement and Conversion Instructions: mov" exists at HTML anchor `data-movement-and-conversion-instructions-mov`, line 14999; its body spans lines 14999-15074.
- SOURCE FACT (SF-M2) — The scalar `mov` syntax forms are: `mov.type d, a;`, `mov.type d, sreg;`, `mov.type d, avar;`, `mov.type d, avar+imm;`, `mov.u32 d, fname;`, `mov.u64 d, fname;`, `mov.u32 d, kernel;`, `mov.u64 d, kernel;`, with `.type = { .pred, .b16, .b32, .b64, .u16, .u32, .u64, .s16, .s32, .s64, .f32, .f64 }` (lines 15008-15021). The `.b32` type specifier is therefore in the scalar `mov` type set.
- SOURCE FACT (SF-M3) — The `mov` description: "Set a register variable with the value of a register variable or an immediate value. Take the non-generic address of a variable in global, local, or shared state space." (lines 15004-15005); "Write register `d` with the value of `a`." (line 15025); "Operand `a` may be a register, special register, variable with optional offset in an addressable memory space, or function name." (lines 15026-15027).
- SOURCE FACT (SF-M4) — For variables declared in `.const`, `.global`, `.local`, and `.shared` state spaces, `mov` places the non-generic address of the variable into the destination register; the generic address may be produced by first taking the in-space address with `mov` and then converting with `cvta`, or directly with `cvta` (lines 15028-15034).
- SOURCE FACT (SF-M5) — The `mov` Semantics block states `d = a;`, `d = sreg;`, `d = &avar;`, `d = &avar+imm;` (lines 15039-15042). For the bounded base unit, only `d = a;` is in scope.
- SOURCE FACT (SF-M6) — `mov` Notes: "Although only predicate and bit-size types are required, we include the arithmetic types for the programmer's convenience: their use enhances program readability and allows additional type checking." (lines 15047-15049). This establishes that bit-size types such as `.b32` are among the types required by `mov`. Also: "When moving address of a kernel or a device function, only `.u32` or `.u64` instruction types are allowed. However, if a signed type is used, it is not treated as a compilation error. The compiler issues a warning in this case." (lines 15050-15052). This restriction concerns the out-of-scope `fname`/`kernel` forms only.
- SOURCE FACT (SF-M7) — `mov` PTX ISA Notes: "Introduced in PTX ISA version 1.0." (line 15055); "Taking the address of kernel entry functions requires PTX ISA version 3.1 or later." with kernel addresses intended only for CUDA Dynamic Parallelism system calls (lines 15056-15058). The kernel-address notes concern the out-of-scope `kernel` form.
- SOURCE FACT (SF-M8) — `mov` Target ISA Notes: "`mov.f64` requires `sm_13` or higher." (line 15060); "Taking the address of kernel entry functions requires `sm_35` or higher." (line 15061). No family-specific target restriction is stated for the scalar `mov.b32` register/immediate value-copy form in the read text (see A-8).
- SOURCE FACT (SF-M9) — `mov` Examples (lines 15064-15071): `mov.f32 d,a;`, `mov.u16 u,v;`, `mov.f32 k,0.1;` (immediate source), `mov.u32 ptr, A;`, `mov.u32 ptr, A[5];`, `mov.u32 ptr, A+20;`, `mov.u32 addr, myFunc;`, `mov.u64 kptr, main;`. The `mov.f32 k,0.1;` example grounds immediate-value sources.
- SOURCE FACT (SF-M10) — Section 9.7.9.4 "Data Movement and Conversion Instructions: mov" exists at HTML anchor `data-movement-and-conversion-instructions-mov-2`, line 15075; body spans lines 15075-15152. Its description is "Move vector-to-scalar (pack) or scalar-to-vector (unpack)." (line 15080); its syntax is `mov.type d, a;` with `.type = { .b16, .b32, .b64, .b128 }` (lines 15083-15085). This is a distinct instruction form from the scalar value-copy form and is out of the bounded base scope (D-0c, OQ-4).
- SOURCE FACT (SF-M11) — Vector-form Notes (section 9.7.9.4): the sink symbol `'_'` may be used for one or more elements of a vector destination provided at least one element is a scalar register (lines 15091-15092); "For bit-size types, `mov` may be used to pack vector elements into a scalar register or unpack sub-fields of a scalar register into a vector. Both the overall size of the vector and the size of the scalar must match the size of the instruction type." (lines 15093-15095); PTX ISA Notes "Introduced in PTX ISA version 1.0." and `.b128` support in 8.3 (lines 15136-15137); Target ISA Notes "Supported on all target architectures." and `.b128` requires `sm_70` or higher (lines 15139-15140). The "supported on all target architectures" sentence was read only in this vector section, not in the scalar section (A-8).
- SOURCE FACT (SF-M12) — Vector-form Examples (lines 15143-15149): `mov.b32 %r1,{a,b};`, `mov.b64 {lo,hi}, %x;`, `mov.b32 %r1,{x,y,z,w};`, `mov.b32 {r,g,b,a},%r1;`, `mov.b64 {%r1, _}, %x;`, `mov.b128 {%b1, %b2}, %y;`, `mov.b128 %y, {%b1, %b2};`. These are pack/unpack usages with vector `{...}` syntax and are out of the bounded base scope.
- SOURCE FACT (SF-M13) — Section 9.7.9 "Data Movement and Conversion Instructions" intro (anchor `data-movement-and-conversion-instructions`, line 14772): "These instructions copy data from place to place, and from state space to state space, possibly converting it from one format to another. `mov`, `ld`, `ldu`, and `st` operate on both scalar and vector types." (lines 14776-14780).
- SOURCE FACT (SF-M14) — Example usage in section 4.3 "Statements" (anchor `statements`, line 1652; example lines 1660-1666): `mov.b32 r1, %tid.x;` where `r1` is declared `.reg .b32 r1, r2;` (line 1660) and `%tid.x` is a special register. This grounds that `.b32`-typed registers are used with `mov` and that the `sreg` source category exists; the `sreg` category is out of the bounded base scope (D-0c).
- SOURCE FACT (SF-M15) — Section 9.7 "Instructions" intro (anchor `instructions`, line 8718): "All PTX instructions may be predicated. In the following descriptions, the optional guard predicate is omitted from the syntax." (lines 8722-8723).
- SOURCE FACT (SF-M16) — Section 9.3 "Predicated Execution" (anchor `predicated-execution`, line 7537): predicate registers are virtual and have `.pred` as the type specifier (lines 7541-7542); "All instructions have an optional *guard predicate* which controls conditional execution of the instruction"; syntax is prefix `@{!}p`, where `p` is a predicate variable, optionally negated; "Instructions without a guard predicate are executed unconditionally." (lines 7547-7550); predicates are most commonly set by `setp` (lines 7551-7552); examples `@p add.s32 j, j, 1;` (line 7562) and `@!p bra L1;` (line 7570).
- SOURCE FACT (SF-M17) — Section 9.2 "PTX Instructions" (anchor `ptx-instructions`, line 7513): "PTX instructions generally have from zero to four operands, plus an optional guard predicate appearing after an `@` symbol to the left of the `opcode`" (lines 7517-7518); "For instructions that create a result value, the `d` operand is the destination operand, while `a`, `b`, and `c` are source operands." (lines 7526-7527); "For some instructions the destination operand is optional. A *bit bucket* operand denoted with an underscore (`_`) may be used in place of a destination register." (lines 7534-7535).
- SOURCE FACT (SF-M18) — Section 5.2.1 "Fundamental Types" (anchor `fundamental-types`, line 3015): "the fundamental types reflect the native data types supported by the target architectures"; "A fundamental type specifies both a basic type and a size"; "Register variables are always of a fundamental type, and instructions operate on these types"; the same type-size specifiers are used for variable definitions and instruction typing (lines 3019-3022). Table 8 (anchor `fundamental-types-fundamental-type-specifiers`, line 3025) lists `.b8`, `.b16`, `.b32`, `.b64`, `.b128` under basic type "Bits (untyped)" (lines 3053-3054), and `.pred` under "Predicate" (lines 3057-3058).
- SOURCE FACT (SF-M19) — Type compatibility (section 5.2.1): "Operand types and sizes are checked against instruction types for compatibility."; "Two fundamental types are compatible if they have the same basic type and are the same size. Signed and unsigned integer types are compatible if they have the same size. The bit-size type is compatible with any fundamental type having the same size." (lines 3062-3066). For instruction type `.b32`, a register or immediate operand declared with any 32-bit fundamental type is therefore compatible under this rule (OQ-7).
- SOURCE FACT (SF-M20) — Section 5.1.1 "Register State Space" (anchor `register-state-space`, line 2613): "Registers (`.reg` state space) are fast storage locations." (line 2617); registers may be typed or untyped (lines 2621-2622); "aside from predicate registers which are 1-bit, scalar registers have a width of 8-, 16-, 32-, 64-, or 128-bits, and vector registers have a width of 16-, 32-, 64-, or 128-bits" (lines 2622-2624); "Registers differ from the other state spaces in that they are not fully addressable, i.e., it is not possible to refer to the address of a register." (lines 2626-2627); ABI/function-scope and legacy module-scope notes (lines 2627-2630).
- SOURCE FACT (SF-M21) — Section 5.1.2 "Special Register State Space" (anchor `special-register-state-space`, line 2633): "The special register (`.sreg`) state space holds predefined, platform-specific registers, such as grid, cluster, CTA, and thread parameters, clock counters, and performance monitoring registers. All special registers are predefined." (lines 2637-2639). This is the state space behind the out-of-scope `sreg` source category.
- SOURCE FACT (SF-M22) — Section 5.4 "Variables" (anchor `variables`, line 3741): "A variable declaration names the space in which the variable resides, its type and size, its name, an optional array size, an optional initializer, and an optional fixed address for the variable." (line 3755); "Predicate variables may only be declared in the register state space." (line 3755).
- SOURCE FACT (SF-M23) — Section 5.4.6 "Parameterized Variable Names" (anchor `parameterized-variable-names`, line 3933): `.reg .b32 %r<100>;` declares `%r0` through `%r99` (lines 3940-3943); the shorthand "may be used with any of the fundamental types and with any state space" (lines 3946-3947).
- SOURCE FACT (SF-M24) — Section 9.1 "Format and Semantics of Instruction Descriptions" (anchor `format-and-semantics-of-instruction-descriptions`, line 7505): "This section describes each PTX instruction. In addition to the name and the format of the instruction, the semantics are described, followed by some examples..." (lines 7509-7511).
- SOURCE FACT (SF-M25) — Predication exception: "`st.param` and `ld.param` instructions used for argument passing cannot be predicated." (lines 6260-6261). This exception does not mention `mov`.
- SOURCE FACT (SF-M26) — Section 5.2.2 "Restricted Use of Sub-Word Sizes" (anchor `restricted-use-of-sub-word-sizes`, line 3070): "The `.u8`, `.s8`, and `.b8` instruction types are restricted to `ld`, `st`, `add`, `sub`, `min`, `max`, `neg` and `cvt` instructions." (lines 3074-3075). `.b32` is not a restricted sub-word size; no `.b32`-specific restriction for `mov` was found in the sections read (negative evidence, A-9).
- Negative search result: a literal search for `@p mov` in the HTML returned 0 matches; this supports no claim about predication of `mov` — the general rule of SF-M15 governs (A-10). A literal search for `mov.b32` returned 25 matches; the matches read are the vector pack/unpack examples (SF-M12) and usage examples (SF-M14, and `mov.b32 p1, {h0, h1};` pack usages in SIMD examples near lines 12621-12950); no scalar `mov.b32 d, a;` register/immediate example was read in this pass, but the scalar form is grounded by SF-M2 (type list), SF-M3 (description), and SF-M5 (semantics `d = a;`).

## 4. Proposed minimal architecture

This section proposes the minimal architecture components required for the future formalization of `mov.b32`. No Lean code is written; each component states its source grounding and the proposed design.

- DESIGN CHOICE (D-1) — PTX instruction representation: a structured instruction form with fields: optional guard (`@{!}p`), mnemonic (`mov`), type specifier (`.b32`), destination operand, and a single source operand `a`. Grounding: SF-M2, SF-M15, SF-M16, SF-M17.
- DESIGN CHOICE (D-2) — Operand categories for the bounded base form: (a) destination register, (b) source register, (c) source constant immediate. A bit-bucket destination `_` is a candidate alternative destination form (see OQ-2). Grounding: SF-M3 (register or immediate value), SF-M9 (immediate example `mov.f32 k,0.1;`), SF-M17 (bit bucket), SF-M14 (`.b32` register use).
- DESIGN CHOICE (D-3) — Scalar type and width representation: a fundamental type is represented as a pair (basic type, size in bits); `.b32` maps to (Bits/Untyped, 32). A minimal type lattice is needed only up to the types that `mov.b32` and its operand-compatibility rule require. Grounding: SF-M18, SF-M19, SF-M20, SF-M6.
- DESIGN CHOICE (D-4) — Register/value representation: register variables always carry a fundamental type (SF-M18); values for `.b32` live in a fixed-width 32-bit untyped bit-value domain; a register file maps register names to values of their declared type. Predicate registers are 1-bit (SF-M20) and are mapped to a two-valued domain by design (D-13). Grounding: SF-M18, SF-M20, SF-M22, SF-M23.
- DESIGN CHOICE (D-5) — Minimal machine state: for the bounded base scalar `mov.b32`, the state contains only a value-register file and a predicate-register file. No memory state space, shared state, special-register state space, or function-address context is required by the bounded base form. Grounding: SF-M2 (base form `mov.type d, a;` has no memory/sreg operand), SF-M3 (destination is a register), SF-M20 (`.reg` state space); the `sreg`/`avar`/`fname`/`kernel` forms are out of scope (D-0c).
- DESIGN CHOICE (D-6) — State reads and destination update: the source value is read from a register or constant immediate; when the instruction executes, the destination register is updated with that value; when the complete guard expression evaluates false, the state is unchanged. Grounding: SF-M5 (`d = a;`), SF-M16, SF-M24; the guard-false consequence is an interpretation recorded in Section 12 (A-4) and Section 14 (OQ-3).
- DESIGN CHOICE (D-7) — Guard/predication architecture: the guard is an optional `.pred`-typed register reference, optionally negated (`@!p`); presence of a guard makes execution conditional; absence makes execution unconditional. Grounding: SF-M15, SF-M16, SF-M17.
- DESIGN CHOICE (D-8) — Execution-result / outcome representation: an instruction-local outcome type with at least two cases — "executed" (with updated state) and "guard false" (no state change). No error constructor is proposed yet because the official source read defines no exceptional behavior for the bounded base `mov.b32` form (see A-6).
- DESIGN CHOICE (D-9) — Version and target-restriction representation for the base `mov.b32` form: a record pairing a PTX ISA version bound ("introduced in" version) with a target requirement. For base `mov.b32`: introduced-in PTX ISA 1.0; target requirement "no family-specific restriction stated in the scalar section read" (see A-8). Grounding: SF-M7, SF-M8.
- DESIGN CHOICE (D-10) — Traceability representation: every semantic claim carries (document identity, specification version, section heading, HTML anchor, HTML line range, source SHA-256). Grounding: SF-M1 and the evidence index in Section 13.

## 5. Fact-to-design mapping

| Source fact | Design component |
|---|---|
| SF-M2, SF-M17 (syntax; operand format) | D-1 (instruction representation) |
| SF-M3, SF-M9, SF-M17, SF-M14 (register/immediate description; immediate example; bit bucket; `.b32` register use) | D-2 (operand categories) |
| SF-M18, SF-M19, SF-M20, SF-M6 (fundamental types; compatibility; register widths; bit-size types required by mov) | D-3 (scalar type/width) |
| SF-M18, SF-M20, SF-M22, SF-M23 (register variables of fundamental type; `.reg` state space; predicate 1-bit; naming) | D-4 (register/value representation) |
| SF-M2, SF-M3, SF-M20 (base form operands; destination register; `.reg` state space) | D-5 (minimal machine state) |
| SF-M5, SF-M16, SF-M24 (semantics `d = a;`; conditional execution; instruction description format) | D-6 (state reads and destination update) |
| SF-M15, SF-M16, SF-M17 (predicability; guard syntax; guard prefix; operand format) | D-7 (guard/predication) |
| Negative evidence in SF-M3/SF-M5 region (no exceptional behavior for base mov.b32; A-6) | D-8 (outcome representation) |
| SF-M7, SF-M8 (PTX ISA Notes; Target ISA Notes) | D-9 (version/target restriction representation) |
| SF-M1 and manifest metadata | D-10 (traceability representation) |
| SF-M20, SF-M22, SF-M23 (register state space; declaration; naming) | D-11, D-12, D-13, D-14, D-15 (register/value/state foundations) |
| SF-M3, SF-M9, SF-M17, SF-M2 (register/immediate sources; immediate example; bit bucket; two-operand syntax) | D-16, D-17, D-18 (operand architecture) |
| SF-M15, SF-M16, SF-M17 (guard syntax; guard prefix; examples) | D-19, D-20, D-21 (predication architecture) |
| SF-M7, SF-M8, SF-M11 (version and target notes; vector-section target note) | D-22, D-23, D-24 (version/target representation) |

### Dependency graph

The bounded base `mov.b32` unit depends on the following shared foundations, all grounded in Section 3:

- Type/width model (D-3) depends on SF-M18, SF-M19, SF-M20 (fundamental types, compatibility, register widths) and SF-M6 (bit-size types required by `mov`).
- Register/value model (D-4, D-11, D-12, D-13) depends on SF-M18, SF-M20, SF-M22, SF-M23 (typed register variables, `.reg` state space, predicate 1-bit, naming).
- Minimal state (D-5, D-14) depends on SF-M2, SF-M3, SF-M20 (base-form operand shape, register destination, `.reg` state space).
- Instruction representation (D-1) depends on SF-M2, SF-M15, SF-M16, SF-M17 (syntax, predicability, guard syntax, operand format).
- Operand architecture (D-16, D-17, D-18) depends on SF-M3, SF-M9, SF-M17, SF-M2.
- Predication architecture (D-19, D-20, D-21) depends on SF-M15, SF-M16, SF-M17, SF-M22.
- Version/target representation (D-22, D-23, D-24) depends on SF-M7, SF-M8, SF-M11.
- Validation/proof-obligation families (Section 11) depend on all of the above.
- Out-of-scope future dependencies (not commitments of this unit): special-register state space (SF-M21) for the `sreg` form; address/state-space semantics (SF-M4) and function-name/kernel-address semantics (SF-M6, SF-M7, SF-M8) for the `avar`/`fname`/`kernel` forms; vector register/pack-unpack semantics (SF-M10, SF-M11, SF-M12) for the 9.7.9.4 form.

## 6. Register, value, and state foundations

The register/value/state architecture is grounded in the official register and type sections read in this pass (Section 5.1.1 Register State Space; Section 5.2.1 Fundamental Types; Section 5.4 variable declaration; Section 5.4.6 Parameterized Variable Names).

- DESIGN CHOICE (D-11) — The value domain for `.b32` is proposed as a fixed-width 32-bit untyped bit-value domain (e.g., 32-bit bit vectors); the exact Lean representation is a Lean-mapping decision outside this artifact. This differs from an unsigned-integer domain because `.b32` is the "Bits (untyped)" basic type (SF-M18), and the `mov` Notes state that bit-size types are among the types required by `mov` (SF-M6).
- DESIGN CHOICE (D-12) — Registers are represented by names (identifiers) mapped to values, not by values alone, to support declaration typing and destination updates. Register references are by name rather than address because the official source states that registers are not fully addressable (SF-M20).
- DESIGN CHOICE (D-13) — Predicate register values are represented by a two-valued (boolean-like) domain, grounded in the official statement that predicate registers are 1-bit (SF-M20) and in the boolean-style use of predicates in `setp` examples (SF-M16). The exact encoding of "1-bit" into a Lean value domain is a Lean-mapping decision (see A-7, OQ-5).
- DESIGN CHOICE (D-14) — The minimal state for the bounded base `mov.b32` is the pair (value-register file, predicate-register file). No memory state space, special-register state space, or other state space is included because the bounded base form has no memory or special-register operands and its description writes only to a destination register (SF-M2, SF-M3). The official `.reg` state-space text (SF-M20) supports the register-file model, and the rule that predicate variables may only be declared in the register state space (SF-M22) supports placing predicate registers in the same overall register state space rather than a separate one.
- DESIGN CHOICE (D-15) — Compilation-level and ABI notes in the register section (register spilling, function-scope restriction, legacy module-scope handling, alignment for multi-word loads/stores; SF-M20) are not modeled in the instruction-local architecture for `mov.b32`. Whether any of these affect a future program-level semantics is an open question outside the bounded unit (OQ-6).

## 7. Operand architecture

- DESIGN CHOICE (D-16) — The bounded base `mov.b32` form has exactly two operands in the order `d, a` (SF-M2). The operand-position roles of section 9.2 (destination `d`; source `a`) apply (SF-M17).
- DESIGN CHOICE (D-17) — The source operand `a` may be a register variable or an immediate value, because the official text states that `mov` "Set[s] a register variable with the value of a register variable or an immediate value" (SF-M3) and the official example `mov.f32 k,0.1;` shows an immediate source (SF-M9). An immediate is modeled as a constant whose type is compatible with the instruction type under SF-M19 (OQ-8).
- DESIGN CHOICE (D-18) — The destination operand `d` is a register variable in the `.reg` state space (SF-M3, SF-M20), or the bit bucket `_` as a candidate alternative (SF-M17; applicability to the scalar form is an open question, OQ-2). When `d` is `_`, the result is discarded and no destination register is updated (candidate behavior; see OQ-2).

## 8. Predication architecture

Predication is expressed uniformly by evaluation of the complete guard expression. The complete guard expression is: "true" when no guard is present; the value of the predicate register `p` for `@p`; and the negation of the value of `p` for `@!p`.

- DESIGN CHOICE (D-19) — Guard evaluation rule: an instruction executes if and only if its complete guard expression evaluates true. Cases: no guard — the complete guard expression is true and the instruction executes unconditionally (SF-M16); `@p` — the complete guard expression evaluates to the value of predicate `p` (SF-M16); `@!p` — the complete guard expression evaluates to not (value of `p`) (SF-M16).
- DESIGN CHOICE (D-20) — No state update is proposed only when the complete guard expression evaluates false. This single rule covers `@p` (no update when `p` is false) and `@!p` (no update when `not p` is false, i.e., when `p` is true), and it is the only guard-false consequence used in this architecture (D-6, D-8, A-4, OQ-3).
- DESIGN CHOICE (D-21) — A guard refers to a `.pred`-typed predicate register variable in the register state space (SF-M16, SF-M22). The guard is written with an `@` prefix to the left of the opcode (SF-M16, SF-M17). The `ld.param`/`st.param` predication exception (SF-M25) does not mention `mov`.
- Predication is applicable to `mov`: "All PTX instructions may be predicated" (SF-M15). No `mov`-specific predication example was found in a literal search (A-10), and none is required because the general rule governs.

## 9. Version and target representation

For the bounded base unit, version and target representation covers only the base `mov.b32` value-copy facts.

- DESIGN CHOICE (D-22) — Version restrictions are represented as an "introduced-in" lower bound over PTX ISA versions. For base `mov.b32` the bound is PTX ISA 1.0 (SF-M7). The separate 3.1-or-later note for kernel entry-function addresses (SF-M7) concerns the out-of-scope `kernel` form only.
- DESIGN CHOICE (D-23) — Target restrictions are represented as a requirement predicate over target architectures. For the bounded base `mov.b32`, no family-specific target restriction is stated in the scalar section read (SF-M8); the recorded requirement is therefore "no family restriction stated" and is an assumption pending semantic-phase re-verification (A-8). A target-gating validation obligation (VAL-6) checks that the recorded requirement matches the official Target ISA Notes.
- DESIGN CHOICE (D-24) — The vector-section target note "Supported on all target architectures" (SF-M11) and the family-specific notes for `mov.f64` (`sm_13+`) and kernel addresses (`sm_35+`) (SF-M8) are recorded as source facts but are not treated as commitments for the bounded base `mov.b32` value-copy form without further evidence (A-8). The vector pack/unpack form itself is out of the bounded base scope (D-0c, OQ-4); its `.b128`/`sm_70` notes concern a future unit.

## 10. Meaningful validation and theorem-obligation families

This section distinguishes validation obligations (definitional well-formedness checks performed at parse/type-validation time) from proof obligations (theorems stated over a future execution relation). No Lean statements are given. The exact copy semantics `d = a;` (SF-M5) is recorded as a source fact but its Lean formalization is a semantic-phase matter (OQ-2 in the add.u32 sense is not applicable; the mov copy semantics is simpler, see OQ-9).

- DESIGN CHOICE (D-25) — The future execution semantics for `mov.b32` is designed to be represented as an execution relation between (state, instruction) and state, not merely as a function. Determinism and frame/locality obligations are stated as properties of that relation. This avoids theorem obligations that hold only because a total-function data structure was chosen.
- DESIGN CHOICE (D-26) — Validation obligations (VAL-1 through VAL-6 below) are definitional checks, not theorem obligations. They are run as part of parsing, typing, and gating validation; they are not proposed as proofs of semantic properties.

Validation obligations:

| ID | Obligation | Kind | Grounding | Non-vacuity note |
|---|---|---|---|---|
| VAL-1 | Type well-formedness: the instruction type specifier `.b32` is a valid bit-size fundamental type of 32-bit width. | validation | SF-M2, SF-M18, SF-M20 | Definitional check over the type representation; not a semantic theorem. |
| VAL-2 | Operand typing: operands `d` and `a` are type-compatible with instruction type `.b32` under the compatibility rules (bit-size type compatible with any fundamental type of the same size). | validation | SF-M19 | Definitional check over the operand-typing relation; exact formulation of the bit-size compatibility rule is an open question (OQ-7). |
| VAL-3 | Guard well-typedness: if a guard is present, it refers to a `.pred`-typed predicate register variable in the register state space. | validation | SF-M16, SF-M22 | Definitional check over the guard representation. |
| VAL-4 | Destination membership: the destination operand denotes a declared register variable, or is the bit bucket `_` (if adopted; OQ-2). | validation | SF-M22, SF-M17 | Definitional check over the destination representation. |
| VAL-5 | Version gating: the recorded introduced-in bound for base `mov.b32` matches the official PTX ISA Note (PTX ISA 1.0). | validation | SF-M7 | Conformance check that the model's version metadata derives from the official note; a derivation check, not a theorem about semantics. |
| VAL-6 | Target gating: the recorded target requirement for base `mov.b32` matches the official Target ISA Notes read (no family-specific restriction stated in the scalar section). | validation | SF-M8, A-8 | Conformance check on target metadata; the base form's target set is an assumption pending semantic-phase re-verification (A-8). |

Proof obligations (candidate families, stated over the future execution relation):

| ID | Obligation | Grounding | Non-vacuity note |
|---|---|---|---|
| PRF-1 | Determinism: for any well-formed state and well-typed instruction, the execution relation relates at most one resulting state. | A-3 (no nondeterminism evidenced) | Stated over a relation, so it does not hold merely by representing semantics as a function (D-25). |
| PRF-2 | Destination-only update / frame: when the instruction executes with a register destination, only the destination register may change; every other value register and every predicate register is unchanged. | SF-M3 (writes register `d` with the value of `a`), SF-M2 (single destination) | Meaningful locality/frame obligation over the execution relation; it rules out spurious updates and is not derivable from a functional state representation alone. |
| PRF-3 | Bit-bucket discard: when the destination is `_`, execution changes no value register. | SF-M17 (bit bucket; applicability OQ-2) | Meaningful frame obligation specific to the bit-bucket form, if adopted. |
| PRF-4 | Guard-false frame: when the complete guard expression evaluates false, the entire state is unchanged. | SF-M16, D-20 | Meaningful guard-behavior frame obligation covering both `@p` and `@!p` uniformly. |
| PRF-5 | Guard-behavior: the instruction executes if and only if the complete guard expression evaluates true; the no-guard, `@p`, and `@!p` cases satisfy the D-19 rule. | SF-M15, SF-M16 | Relates guard evaluation to the execution relation; the `@!p` case is stated without an erroneous "negated guard true means no-op" phrasing. |
| PRF-6 | Result-domain membership: when the instruction executes, the value written to the destination lies in the 32-bit bit-size value domain of `.b32`. | SF-M18, D-11 | Typing-soundness-style obligation over the execution relation; it does not assert which specific bits are written. |
| PRF-7 | Copy fidelity (candidate): when the instruction executes with a register source, the value written to the destination equals the value read from the source. | SF-M5 (`d = a;`) | Meaningful semantic property for a value-copy instruction; the exact formal statement is a semantic-phase matter (OQ-9). It is listed as a candidate family, not as a completed obligation. |

## 11. Assumptions

- ASSUMPTION (A-1) — The HTML document is authoritative for this unit; the manifest-recorded PDF was not read.
- ASSUMPTION (A-2) — Instruction-local semantics (a single instruction evaluated against a minimal state) is sufficient for the bounded base `mov.b32`; no program-counter, memory, or concurrency context is required for the architecture foundations.
- ASSUMPTION (A-3) — The bounded base `mov.b32` is deterministic; no nondeterminism is evidenced in the official source read. This is an assumption based on absence of evidence in the sections read, not a source fact; it must be re-verified in the semantic phase (PRF-1).
- ASSUMPTION (A-4) — The guard-false consequence "no state update" is the intended meaning of "controls conditional execution" (SF-M16), supported by the guard examples (SF-M16); this interpretation is pending human approval (OQ-3).
- ASSUMPTION (A-5) — "mov.b32" in this artifact denotes the scalar value-copy form with register/immediate source, per D-0c.
- ASSUMPTION (A-6) — The official source read defines no error, trap, or exceptional behavior for the bounded base `mov.b32` value-copy form; therefore the outcome representation (D-8) has no error constructor for this unit. This is an assumption based on absence of evidence in lines 14999-15074 and the sections read, not a source fact; the semantic phase must re-verify.
- ASSUMPTION (A-7) — The 1-bit predicate register (SF-M20) is mapped to a two-valued (boolean-like) value domain by design; the exact encoding is a Lean-mapping decision (D-13, OQ-5).
- ASSUMPTION (A-8) — No family-specific target restriction is stated for the scalar `mov.b32` register/immediate value-copy form in the official text read; the "Supported on all target architectures" sentence was read only in the vector section (SF-M11) and is not treated as establishing the scalar base form's target set without further evidence. This assumption must be re-verified in the semantic phase.
- ASSUMPTION (A-9) — Negative evidence: `.b32` is not among the sub-word sizes restricted by section 5.2.2 (SF-M26), and no `.b32`-specific restriction for `mov` was found in the sections read. This is an assumption based on absence of evidence, not a source fact.
- ASSUMPTION (A-10) — A literal search for `@p mov` returned zero matches; this negative result supports no claim about predication of `mov`, which is governed by the general rule of SF-M15. It also supports no document-wide claim about predication rubrics.

## 12. Ambiguities

- AMBIGUITY (AMB-1) — The unit `mov.b32` is ambiguous between two official instruction forms: the scalar value-copy form of section 9.7.9.3 (SF-M2, SF-M3, SF-M5) and the vector pack/unpack form of section 9.7.9.4 (SF-M10, SF-M11, SF-M12), both of which include `.b32` in their type sets. This artifact resolves the ambiguity for the bounded base unit as the scalar value-copy form (D-0c); the resolution is a design choice pending human approval and the vector form remains a candidate future unit (OQ-4).
- AMBIGUITY (AMB-2) — Within section 9.7.9.3, `mov.type d, a;` supports multiple source-operand categories (register/immediate, `sreg`, `avar`, `avar+imm`, `fname`, `kernel`; SF-M2, SF-M3). The bounded base unit adopts only the register/immediate category (D-0c); the remaining categories are recorded as source facts and deferred (OQ-1).
- AMBIGUITY (AMB-3) — Whether the bit-bucket `_` is a permitted destination for the scalar `mov.b32` value-copy form is not explicitly evidenced in the scalar section; the general 9.2 rule (SF-M17) and the vector-form sink usage (SF-M11) exist, but a scalar-form example was not read. This is an open question (OQ-2), not a resolved design commitment.

## 13. Open questions

- OPEN QUESTION (OQ-1) — Which future units will model the `sreg`, `avar`/`avar+imm`, `fname`, and `kernel` source categories of section 9.7.9.3, and what shared foundations (special-register state space SF-M21; address semantics SF-M4; function/kernel-address semantics SF-M6, SF-M7, SF-M8) will they require? These are out of the bounded base scope (D-0c).
- OPEN QUESTION (OQ-2) — Whether the bit bucket `_` is permitted as the destination of the scalar `mov.b32` value-copy form (AMB-3). The general 9.2 rule (SF-M17) exists, but no scalar `mov` `_` example was read; resolution is needed before PRF-3 is treated as faithful.
- OPEN QUESTION (OQ-3) — The exact consequence of a false guard predicate beyond the "controls conditional execution" wording (SF-M16) is interpreted here as "no state update" (A-4); this interpretation needs human approval before the guard-false obligations (PRF-4) are treated as faithful to the specification.
- OPEN QUESTION (OQ-4) — Whether the vector pack/unpack `mov.b32` form of section 9.7.9.4 (SF-M10, SF-M11, SF-M12) should be modeled as a separate later unit; the bounded task covers only the scalar value-copy form (D-0c, AMB-1).
- OPEN QUESTION (OQ-5) — The exact Lean encoding of the 1-bit predicate register value domain (D-13, A-7) is a Lean-mapping decision that must be made and human-approved in the Lean-mapping phase.
- OPEN QUESTION (OQ-6) — Whether compilation-level register notes (spilling, function-scope/ABI restriction, module-scope legacy handling; SF-M20) impose constraints that a future program-level semantics must model; they are excluded from the instruction-local architecture (D-15).
- OPEN QUESTION (OQ-7) — How the bit-size compatibility rule ("The bit-size type is compatible with any fundamental type having the same size", SF-M19) should be formulated for `mov.b32` operand typing: whether a register declared `.u32`, `.s32`, or `.f32` is an acceptable operand for instruction type `.b32`, and how immediate values are typed under the same rule. Resolution is deferred to the semantic-interpretation phase.
- OPEN QUESTION (OQ-8) — Whether an immediate source for `mov.b32` is a 32-bit constant literal and how immediate constants are typed and validated against the instruction type (SF-M9, SF-M19). Resolution is deferred to the semantic-interpretation phase.
- OPEN QUESTION (OQ-9) — The exact Lean statement of the copy-fidelity candidate obligation PRF-7 ("the value written equals the value read", grounded in SF-M5 `d = a;`) is a semantic-phase matter; the architecture records the candidate family only.

## 14. Evidence index with section headings, anchors, HTML line ranges, and source SHA-256

Source SHA-256 abbreviations: HTML = `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856` (ptx_isa_9.3.html); MANIFEST = `622e6ce0d3114a909a62726530955993b5f2b98d2f60e45ae1ceb429512208f2` (source-manifest.json); SUMS = `e02f4feadfce614282d3d4774ed21dd87985202d4ea9ad84ead60c688a6c0ecd` (SHA256SUMS).

| # | Section heading | Anchor | Lines | Source | SHA-256 | Status |
|---|---|---|---|---|---|---|
| E-1 | source-manifest.json (run/unit metadata; initial_formalization_unit = add.u32) | (n/a) | manifest lines 1-38 | manifest | MANIFEST | Read |
| E-2 | 9.7.9.3 Data Movement and Conversion Instructions: mov (heading/section extent) | `data-movement-and-conversion-instructions-mov` | 14999-15074 | HTML | HTML | Read |
| E-3 | 9.7.9.3 mov — Syntax | `data-movement-and-conversion-instructions-mov` | 15008-15021 | HTML | HTML | Read |
| E-4 | 9.7.9.3 mov — Description | `data-movement-and-conversion-instructions-mov` | 15004-15005, 15025-15027 | HTML | HTML | Read |
| E-5 | 9.7.9.3 mov — Address semantics | `data-movement-and-conversion-instructions-mov` | 15028-15034 | HTML | HTML | Read |
| E-6 | 9.7.9.3 mov — Semantics block (`d = a;` etc.) | `data-movement-and-conversion-instructions-mov` | 15039-15042 | HTML | HTML | Read |
| E-7 | 9.7.9.3 mov — Notes (bit-size types required; kernel/function type restriction) | `data-movement-and-conversion-instructions-mov` | 15047-15052 | HTML | HTML | Read |
| E-8 | 9.7.9.3 mov — PTX ISA Notes | `data-movement-and-conversion-instructions-mov` | 15055-15058 | HTML | HTML | Read |
| E-9 | 9.7.9.3 mov — Target ISA Notes | `data-movement-and-conversion-instructions-mov` | 15060-15061 | HTML | HTML | Read |
| E-10 | 9.7.9.3 mov — Examples | `data-movement-and-conversion-instructions-mov` | 15064-15071 | HTML | HTML | Read |
| E-11 | 9.7.9.4 Data Movement and Conversion Instructions: mov (vector pack/unpack; heading/section extent) | `data-movement-and-conversion-instructions-mov-2` | 15075-15152 | HTML | HTML | Read |
| E-12 | 9.7.9.4 mov — Description and sink `_` | `data-movement-and-conversion-instructions-mov-2` | 15080, 15089-15095 | HTML | HTML | Read |
| E-13 | 9.7.9.4 mov — Semantics (pack/unpack) | `data-movement-and-conversion-instructions-mov-2` | 15098-15132 | HTML | HTML | Read |
| E-14 | 9.7.9.4 mov — PTX ISA Notes / Target ISA Notes | `data-movement-and-conversion-instructions-mov-2` | 15136-15140 | HTML | HTML | Read |
| E-15 | 9.7.9.4 mov — Examples | `data-movement-and-conversion-instructions-mov-2` | 15143-15149 | HTML | HTML | Read |
| E-16 | 9.7.9 Data Movement and Conversion Instructions (intro) | `data-movement-and-conversion-instructions` | 14772-14812 | HTML | HTML | Read |
| E-17 | 4.3 Statements — example with `mov.b32 r1, %tid.x;` | `statements` | 1652-1668 | HTML | HTML | Read |
| E-18 | 9.7 Instructions (intro; predicability) | `instructions` | 8718-8723 | HTML | HTML | Read |
| E-19 | 9.3 Predicated Execution | `predicated-execution` | 7537-7574 | HTML | HTML | Read |
| E-20 | 9.2 PTX Instructions (operand format; bit bucket) | `ptx-instructions` | 7513-7536 | HTML | HTML | Read |
| E-21 | 5.2.1 Fundamental Types | `fundamental-types` | 3015-3068 | HTML | HTML | Read |
| E-22 | Table 8 Fundamental Type Specifiers | `fundamental-types-fundamental-type-specifiers` | 3025-3061 | HTML | HTML | Read |
| E-23 | 5.1.1 Register State Space | `register-state-space` | 2613-2631 | HTML | HTML | Read |
| E-24 | 5.1.2 Special Register State Space | `special-register-state-space` | 2633-2640 | HTML | HTML | Read |
| E-25 | 5.4 Variables (declaration rule; predicate-only-in-register) | `variables` | 3741-3756 | HTML | HTML | Read |
| E-26 | 5.4.6 Parameterized Variable Names | `parameterized-variable-names` | 3933-3949 | HTML | HTML | Read |
| E-27 | 9.1 Format and Semantics of Instruction Descriptions | `format-and-semantics-of-instruction-descriptions` | 7505-7512 | HTML | HTML | Read |
| E-28 | st.param/ld.param predication exception | (anchor not captured) | 6260-6261 | HTML | HTML | Read (snippet) |
| E-29 | 5.2.2 Restricted Use of Sub-Word Sizes | `restricted-use-of-sub-word-sizes` | 3070-3075 | HTML | HTML | Read |
| E-30 | SHA256SUMS (HTML/PDF hashes) | (n/a) | lines 1-3 | SUMS | SUMS | Read |
| E-31 | Literal search `@p mov` (0 matches) | (n/a) | (search) | HTML | HTML | Search (this pass) |
| E-32 | Literal search `mov.b32` (25 matches; samples read) | (multiple) | 1663, 12621-12950, 15143-15149 | HTML | HTML | Search (this pass) |

## 15. Finding-resolution notes (no prior critique)

No prior `mov.b32` architecture artifact or critique exists; there are no findings F-1..F-n for this artifact. The lessons of the add.u32 foundation v1 critique (`candidates/ptx/9.3/reviews/add-u32-foundation-v1-critic.md`) were applied proactively:

| add.u32 finding | Lesson applied in this artifact |
|---|---|
| F-1 (project status/scope mislabeled SOURCE FACT) | Section 1 separates project status and scope as metadata/DESIGN CHOICE; SOURCE FACT reserved for specification-grounded facts (SF-M1..SF-M26). |
| F-2 (fifth label OBSERVATION) | Only four labels are used: SOURCE FACT / DESIGN CHOICE / ASSUMPTION / OPEN QUESTION; negative evidence is labeled ASSUMPTION (A-9, A-10). |
| F-3 / F-9 (register chapter unread) | Register/value/state foundations grounded in official reads: SF-M20, SF-M21, SF-M22, SF-M23, SF-M18. |
| F-5 / F-6 (negated-guard phrasing) | Guard-false behavior stated uniformly via the complete guard expression (D-19, D-20, PRF-4, PRF-5); no "negated guard true means no-op" phrasing. |
| F-7 (vacuity risk) | Validation vs. proof obligations distinguished; proof obligations are relational and include frame/locality and guard-behavior families (D-25, D-26, Section 10). |
| F-8 (inaccurate checklist/anchors) | Anchors verified via the restricted spec tools and recorded in Section 14; Gate A checklist in Section 16 reflects actual state. |
| F-10 (phantom cross-references) | Cross-references only to sections and anchors actually present in this artifact. |

## 16. Gate A review checklist

Gate A is NOT ready. This artifact must receive an independent re-critique before it may be presented for human Gate A review. The following items are the checklist for that future review:

- [ ] The artifact is marked `DRAFT — NOT HUMAN APPROVED` and is not promoted to `accepted/`.
- [ ] Scope is bounded to language-wide foundations strictly required for future `mov.b32` formalization, with the scalar value-copy form as the bounded base interpretation (D-0, D-0c, AMB-1).
- [ ] Project status and bounded scope are classified as project design choices or metadata, not SOURCE FACT.
- [ ] Every architectural/semantic statement uses exactly one of SOURCE FACT / DESIGN CHOICE / ASSUMPTION / OPEN QUESTION; plain metadata notes are identified as such.
- [ ] Every SOURCE FACT is traceable to an official source entry in the evidence index (Section 14).
- [ ] Register/value/state architecture is grounded in official reads (SF-M18, SF-M20, SF-M21, SF-M22, SF-M23; Section 6).
- [ ] Operand architecture is grounded in the mov description, immediate example, and section 9.2 operand format (SF-M3, SF-M9, SF-M17; Section 7).
- [ ] Predication is expressed uniformly by evaluation of the complete guard expression for no-guard, `@p`, and `@!p`; no state update is proposed only when the complete guard expression evaluates false (D-19, D-20).
- [ ] Validation obligations and proof obligations are distinguished; proof obligations are relational, non-vacuous, and include frame/locality and guard-behavior families (Section 10).
- [ ] Version and target representation is limited to base `mov.b32` (PTX ISA 1.0; no family restriction stated), with the scalar-section vs. vector-section target-note distinction recorded (A-8; Section 9).
- [ ] Evidence anchors are verified: `data-movement-and-conversion-instructions-mov` (E-2), `data-movement-and-conversion-instructions-mov-2` (E-11), `instructions` (E-18), `predicated-execution` (E-19), `ptx-instructions` (E-20), `fundamental-types` (E-21), `register-state-space` (E-23), `special-register-state-space` (E-24), `variables` (E-25), `parameterized-variable-names` (E-26), `format-and-semantics-of-instruction-descriptions` (E-27), `restricted-use-of-sub-word-sizes` (E-29).
- [ ] Negative-evidence items are labeled ASSUMPTION or OPEN QUESTION and are flagged for semantic-phase re-verification (A-3, A-6, A-8, A-9, A-10).
- [ ] Ambiguities are explicitly recorded (AMB-1, AMB-2, AMB-3; Section 12).
- [ ] Unsupported or unread points are marked OPEN QUESTION rather than guessed (Section 13).
- [ ] No instruction-level semantics of `mov.b32` were extracted or defined beyond the recorded source-fact Semantics block `d = a;` (SF-M5); the copy-fidelity obligation is a candidate family only (PRF-7, OQ-9).
- [ ] No `mov.b32` source bundle was constructed, and no Lean code was written (D-0b).
- [ ] No other instruction form was modeled as a separate unit; the vector pack/unpack form and the `sreg`/`avar`/`fname`/`kernel` categories are explicitly out of scope (D-0c, OQ-1, OQ-4).
- [ ] Dependencies required before `mov.b32` formalization are represented in the design choices and dependency graph (Section 5) and validated in Section 10.

## 17. Explicit non-goals

- DESIGN CHOICE (D-27) — Not defining the exact Lean semantics of the `mov.b32` copy operation beyond the recorded source-fact Semantics block `d = a;` (SF-M5); the exact formal statement (including the candidate copy-fidelity obligation PRF-7) is deferred to the semantic phase (OQ-9).
- DESIGN CHOICE (D-28) — Not writing any Lean code or concrete Lean theorem statements.
- DESIGN CHOICE (D-29) — Not constructing a `mov.b32` instruction-level source bundle.
- DESIGN CHOICE (D-30) — Not modeling the vector pack/unpack `mov` form (section 9.7.9.4) or the `sreg`/`avar`/`avar+imm`/`fname`/`kernel` source categories of section 9.7.9.3 as units; their syntax, notes, and target restrictions are recorded as source facts (SF-M2, SF-M4, SF-M6, SF-M7, SF-M8, SF-M10, SF-M11, SF-M12, SF-M21) but are not architecture commitments of the bounded base unit.
- DESIGN CHOICE (D-31) — Not building a memory, state-space (beyond the register/predicate pair), address, special-register, function-name, or concurrency model for this unit.
- DESIGN CHOICE (D-32) — Not resolving within this artifact the deferred open questions OQ-1 (future source-category units), OQ-2 (scalar bit bucket), OQ-3 (guard-false interpretation), OQ-7/OQ-8 (bit-size compatibility and immediates), and OQ-9 (copy-fidelity statement); they are the property of the semantic phase and future units.
- DESIGN CHOICE (D-33) — Not approving Gate A; approval is a human decision, and Gate A remains not ready until this artifact receives an independent critique. Not promoting anything to `accepted/`.
