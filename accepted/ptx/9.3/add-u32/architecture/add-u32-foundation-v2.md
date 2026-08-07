# PTX add.u32 Foundation Architecture v2 — DRAFT — NOT HUMAN APPROVED

## 1. Revision status and bounded scope

Status note (project metadata, not specification evidence): this artifact is a DRAFT architecture candidate produced for a future Gate A review. It is marked `DRAFT — NOT HUMAN APPROVED`. It has not been reviewed or approved by a human reviewer, it is not promoted to `accepted/`, and it does not claim that Gate A is ready.

- DESIGN CHOICE (D-0) — The bounded scope of this artifact is the language-wide foundations strictly required for the future formalization of PTX ISA 9.3 `add.u32`: instruction representation, operand categories, scalar integer types, register/value representation, minimal machine state, state reads and destination updates, predication, execution-result representation, version/target-restriction representation, traceability, and candidate validation/proof-obligation families. Scope is a project design decision of this artifact, not an official-source fact.
- DESIGN CHOICE (D-0b) — This artifact describes architecture only. It does not define the arithmetic semantics of `add.u32`, does not construct an instruction-level source bundle, and does not contain Lean code.
- DESIGN CHOICE (D-0c) — "add.u32" in this artifact denotes the scalar, non-saturating, unsigned 32-bit form of the `add` instruction. Saturating and packed sub-word forms (`add.sat.u32`, `add.u16x2`, etc.) are identified as official source facts where required for completeness but are not modeled as units in the bounded base architecture; architecture commitments concerning only those future forms are deliberately excluded (see D-24, OQ-1).
- The unit identity `add.u32` (instruction family `add`, section 9.7.1.1, heading "Integer Arithmetic Instructions: add", HTML anchor `integer-arithmetic-instructions-add`) is the only item in this section that is an official-source fact; it is recorded as SF-1 in Section 3.

## 2. Inputs and critique addressed

This revision addresses the independent critique `candidates/ptx/9.3/reviews/add-u32-foundation-v1-critic.md` (SHA-256 `7f52da1f4aee741edc3f063c00c7d6cb294d4d6ef6e591d21276d5c283821db7`), which reviewed v1 `candidates/ptx/9.3/architecture/add-u32-foundation-v1.md` (SHA-256 `5696d3f470bc55b20c76f34dd10eaf43e329691f1f0e861c3a74aef2efc6ac00`). Both v1 and the critic artifact are preserved unchanged.

- SOURCE FACT (SF-1) — Manifest unit identity: the initial formalization unit is `add.u32`; instruction family `add`; section number 9.7.1.1; section heading "Integer Arithmetic Instructions: add"; html anchor `integer-arithmetic-instructions-add` (source-manifest.json lines 9-15).
- The critique findings F-1 through F-10 are each addressed explicitly; see the finding-resolution matrix in Section 14. The missing evidence identified by F-3, F-8, and F-9 was obtained from the official PTX ISA 9.3 HTML using the restricted specification tools (register chapter sections 5.1.1, 5.4, 5.4.6; section 9.1 and 9.2 operand-format text; predication examples; target-family literal occurrences).

## 3. Official-source facts

Primary source: `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html`, official NVIDIA "Parallel Thread Execution ISA" version 9.3, SHA-256 `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`, 47,743 lines. Metadata source: `documents/sources/nvidia/ptx/9.3/source-manifest.json`, SHA-256 `622e6ce0d3114a909a62726530955993b5f2b98d2f60e45ae1ceb429512208f2`, 38 lines. The manifest records a PDF artifact (`raw/ptx_isa_9.3.pdf`, SHA-256 `769cc12e363e7bb9cd311464f2a42edbdaf4c74ca18575de8c358e93223434fc`); the PDF was not read in this pass.

- SOURCE FACT (SF-2) — Section 9.7.1.1 "Integer Arithmetic Instructions: add" exists at HTML anchor `integer-arithmetic-instructions-add`, lines 8757-8760, followed by its body through line 8842.
- SOURCE FACT (SF-3) — The `add` syntax is `add.type1 d, a, b;` and `add{.sat}.type2 d, a, b;`, where `.type1 = { .u16, .u64, .s16, .s64 }` and `.type2 = { .u32, .u16x2, .u8x4, .s32, .s16x2, .s8x4 }` (lines 8763-8774).
- SOURCE FACT (SF-4) — The `add` meaning is stated as "Add two values." (line 8762) and "Performs addition and writes the resulting value into a destination register." (line 8776).
- SOURCE FACT (SF-5) — Operand typing: "Operands `d`, `a` and `b` have the same type as the instruction type." For the packed instruction types `.u16x2`, `.s16x2`, `.u8x4`, `.s8x4`, operands `d`, `a`, `b` have type `.b32` (lines 8783-8784).
- SOURCE FACT (SF-6) — The `.sat` modifier "limits result to `MININT..MAXINT` (no overflow) for the size and signedness of the operation" and "Applies only to `.u32`, `.s32`, `.u16x2`, `.s16x2`, `.u8x4`, `.s8x4` types" (lines 8813-8819). This concerns only future saturating forms and is out of the bounded base scope.
- SOURCE FACT (SF-7) — PTX ISA Notes: "Introduced in PTX ISA version 1.0." for base `add`; `add.sat.u32` introduced in PTX ISA version 9.2 (lines 8821-8825).
- SOURCE FACT (SF-8) — Target ISA Notes: base `add` is "Supported on all target architectures."; `add.sat.u32` and the other listed packed/sat forms are "supported on following family-specific architectures: `sm_120f` or higher in the same family" (lines 8826-8833). The family-specific note concerns only future saturating/packed forms.
- SOURCE FACT (SF-9) — The `add` Examples block includes the predicated form `@p add.u32 x,y,z;` (lines 8834-8841).
- SOURCE FACT (SF-10) — Section 9.7 "Instructions" intro (anchor `instructions`, line 8718): "All PTX instructions may be predicated. In the following descriptions, the optional guard predicate is omitted from the syntax." (lines 8722-8723).
- SOURCE FACT (SF-11) — Section 9.3 "Predicated Execution" (anchor `predicated-execution`, lines 7537-7550): predicate registers are virtual and have `.pred` as the type specifier; "All instructions have an optional *guard predicate* which controls conditional execution of the instruction"; the syntax is to prefix an instruction with `@{!}p`, where `p` is a predicate variable, optionally negated; "Instructions without a guard predicate are executed unconditionally."
- SOURCE FACT (SF-12) — "Predicates are most commonly set as the result of a comparison performed by the `setp` instruction" (lines 7551-7552).
- SOURCE FACT (SF-13) — Predication exception: "`st.param` and `ld.param` instructions used for argument passing cannot be predicated" (line 6261). This exception does not mention `add`.
- SOURCE FACT (SF-14) — Section 5.2.1 "Fundamental Types" (anchor `fundamental-types`, lines 3015-3022): "the fundamental types reflect the native data types supported by the target architectures"; "A fundamental type specifies both a basic type and a size"; "Register variables are always of a fundamental type, and instructions operate on these types"; "The same type-size specifiers are used for both variable definitions and for typing instructions." Table 8 "Fundamental Type Specifiers" (anchor `fundamental-types-fundamental-type-specifiers`, lines 3025-3061) lists `.u8`, `.u16`, `.u32`, `.u64` under "Unsigned integer", and also lists signed integer, floating-point, bits (untyped), and predicate basic types.
- SOURCE FACT (SF-15) — Type compatibility: "Operand types and sizes are checked against instruction types for compatibility."; "Two fundamental types are compatible if they have the same basic type and are the same size. Signed and unsigned integer types are compatible if they have the same size. The bit-size type is compatible with any fundamental type having the same size." (lines 3062-3066).
- SOURCE FACT (SF-16) — Section 9.2 "PTX Instructions" (anchor `ptx-instructions`, line 7513): "For some instructions the destination operand is optional. A *bit bucket* operand denoted with an underscore (`_`) may be used in place of a destination register." (lines 7534-7535).
- SOURCE FACT (SF-17) — Example usage evidence: `add.u32 %r, %r, 4;` appears in an example with `.reg .u32 %r;` and `.reg .pred %p;` declarations (line 2902; enclosing section heading not captured, example occurs just before section 5.1.7).
- SOURCE FACT (SF-18) — Example usage evidence: `add.u32 %res, %ptr, %inc;` appears inside a `.func` body with `.reg .u32` formal parameters (line 6172; enclosing section heading not captured).
- SOURCE FACT (SF-19) — Section 9.2 "PTX Instructions" operand format: "PTX instructions generally have from zero to four operands, plus an optional guard predicate appearing after an `@` symbol to the left of the `opcode`" (lines 7517-7518); "For instructions that create a result value, the `d` operand is the destination operand, while `a`, `b`, and `c` are source operands." (lines 7526-7527).
- SOURCE FACT (SF-20) — Section 9.7.1 "Integer Arithmetic Instructions" intro: "Integer arithmetic instructions operate on the integer types in register and constant immediate forms." (lines 8728-8729). This establishes that the integer arithmetic instruction family, which includes `add`, permits register and constant immediate source forms.
- SOURCE FACT (SF-21) — Section 5.1.1 "Register State Space" (anchor `register-state-space`, lines 2613-2631): "Registers (`.reg` state space) are fast storage locations." (line 2617); "Registers may be typed (signed integer, unsigned integer, floating point, predicate) or untyped." (lines 2621-2622); "aside from predicate registers which are 1-bit, scalar registers have a width of 8-, 16-, 32-, 64-, or 128-bits, and vector registers have a width of 16-, 32-, 64-, or 128-bits" (lines 2622-2624); "Registers differ from the other state spaces in that they are not fully addressable, i.e., it is not possible to refer to the address of a register." (lines 2626-2627); register variables are restricted to function scope under the ABI and module-scoped `.reg` variables trigger legacy handling (lines 2627-2630); registers may have alignment boundaries required by multi-word loads and stores (lines 2630-2631).
- SOURCE FACT (SF-22) — Section 5.4 "Variables" declaration rule (snippet at line 3755): "the declaration names the space in which the variable resides, its type and size, its name, an optional array size, an optional initializer, and an optional fixed address for the variable." and "Predicate variables may only be declared in the register state space." (exact subsection anchor not captured in this pass).
- SOURCE FACT (SF-23) — Section 5.4.6 "Parameterized Variable Names" (anchor `parameterized-variable-names`, lines 3933-3948): PTX supports virtual registers and a syntax for creating sets of variables with a common prefix string appended with integer suffixes, e.g., `.reg .b32 %r<100>;` declares `%r0`, `%r1`, ..., `%r99`; "This shorthand syntax may be used with any of the fundamental types and with any state space" (lines 3946-3948).
- SOURCE FACT (SF-24) — Predication examples in section 9.3 (anchor `predicated-execution`, lines 7553-7574): `@p add.s32 j, j, 1; // if i < n, add 1 to j` (line 7562) and `@!p bra L1; // if False, branch over` (line 7570). The second example shows the negated guard executing when the underlying predicate is false.
- SOURCE FACT (SF-25) — A literal search for `sm_120f` in the HTML returned 57 matches, e.g., line 8832 (add Target ISA Notes), line 8901 (sub), line 17681 (target-requirement list with a rename note to `sm_110f` from PTX ISA version 9.0). No formal definition of "same family" was found in the matches read; this concept concerns only future saturating/packed forms.

## 4. Proposed minimal architecture

This section proposes the minimal architecture components required for the future formalization of `add.u32`. No Lean code is written; each component states its source grounding and the proposed design.

- DESIGN CHOICE (D-1) — PTX instruction representation: a structured instruction form with fields: optional guard (`@{!}p`), mnemonic (`add`), type specifier (`.u32`), optional modifier set (empty for the base form), destination operand, and source operand list (`a`, `b`). Grounding: SF-3, SF-10, SF-11, SF-19.
- DESIGN CHOICE (D-2) — Operand categories: for `add.u32` the minimal categories are (a) destination register, (b) source register, (c) source constant immediate. A bit-bucket destination `_` is an alternative destination form. Grounding: SF-5 (d, a, b same type as instruction), SF-20 (register and constant immediate forms), SF-17 (immediate source `4`), SF-18 (register sources), SF-16 (bit bucket).
- DESIGN CHOICE (D-3) — Scalar integer type and width representation: a fundamental type is represented as a pair (basic type, size in bits); `.u32` maps to (UnsignedInteger, 32). A minimal type lattice is needed only up to the types that `add.u32` and its operand-typing rule require. Grounding: SF-14, SF-15, SF-21 (scalar register widths).
- DESIGN CHOICE (D-4) — Register/value representation: register variables always carry a fundamental type (SF-14); values for `.u32` live in a fixed-width 32-bit unsigned value domain; a register file maps register names to values of their declared type. Predicate registers are 1-bit (SF-21) and are mapped to a two-valued domain by design (D-13). Grounding: SF-14, SF-21, SF-22, SF-23.
- DESIGN CHOICE (D-5) — Minimal machine state: for scalar `add.u32`, the state contains only a value-register file and a predicate-register file. No memory state space, shared state, or special registers are required by the `add.u32` syntax or description. Grounding: SF-3 (no memory operand), SF-4 (destination is a register), SF-21 (registers are the `.reg` state space).
- DESIGN CHOICE (D-6) — State reads and destination update: source operand values are read from the state (registers) or from constant immediates; when the instruction executes, the destination register is updated with the resulting value; when the complete guard expression evaluates false, the state is unchanged. Grounding: SF-4, SF-11, SF-24; the guard-false consequence is an interpretation recorded in Section 11 (A-4) and Section 12 (OQ-3).
- DESIGN CHOICE (D-7) — Guard/predication architecture: the guard is an optional `.pred`-typed register reference, optionally negated (`@!p`); presence of a guard makes execution conditional; absence makes execution unconditional. Grounding: SF-10, SF-11, SF-19, SF-24.
- DESIGN CHOICE (D-8) — Execution-result / outcome representation: an instruction-local outcome type with at least two cases — "executed" (with updated state) and "guard false" (no state change). No error constructor is proposed yet because the official source read defines no exceptional behavior for base `add` (see A-6).
- DESIGN CHOICE (D-9) — Version and target-restriction representation for base `add.u32`: a record pairing a PTX ISA version bound ("introduced in" version) with a target requirement. For `add.u32`: introduced-in PTX ISA 1.0; target requirement "all target architectures". Grounding: SF-7, SF-8.
- DESIGN CHOICE (D-10) — Traceability representation: every semantic claim carries (document identity, specification version, section heading, HTML anchor, HTML line range, source SHA-256). Grounding: SF-1 and the evidence index in Section 13.

## 5. Fact-to-design mapping

| Source fact | Design component |
|---|---|
| SF-3, SF-19 (syntax; operand format) | D-1 (instruction representation) |
| SF-5, SF-16, SF-17, SF-18, SF-20 (typing; bit bucket; examples; register/constant forms) | D-2 (operand categories) |
| SF-14, SF-15, SF-21 (fundamental types; compatibility; register widths) | D-3 (scalar integer type/width) |
| SF-14, SF-21, SF-22, SF-23 (register variables of fundamental type; `.reg` state space; predicate 1-bit; naming) | D-4 (register/value representation) |
| SF-3, SF-4, SF-21 (no memory operands; destination register; `.reg` state space) | D-5 (minimal machine state) |
| SF-4, SF-11, SF-24 (writes result to destination; conditional execution; guard examples) | D-6 (state reads and destination update) |
| SF-10, SF-11, SF-19, SF-24 (predicability; guard syntax; guard prefix; examples) | D-7 (guard/predication) |
| Negative evidence in SF-4/SF-11 region (no exceptional behavior in add section; A-6) | D-8 (outcome representation) |
| SF-7, SF-8 (PTX ISA Notes; Target ISA Notes) | D-9 (version/target restriction representation) |
| SF-1 and manifest metadata | D-10 (traceability representation) |
| SF-21, SF-22, SF-23 (register state space; declaration; naming) | D-11, D-12, D-13, D-14, D-15 (register/value/state foundations) |
| SF-20, SF-3 (register/constant immediate forms; exact three-operand syntax) | D-16, D-17, D-18 (operand architecture) |
| SF-11, SF-19, SF-24 (guard syntax; guard prefix; examples) | D-19, D-20, D-21 (predication architecture) |
| SF-7, SF-8 (version and target notes) | D-22, D-23, D-24 (version/target representation) |

## 6. Register, value, and state foundations

The register/value/state architecture is grounded in the official register sections read in this revision (Section 5.1.1 Register State Space; Section 5.4 variable declaration; Section 5.4.6 Parameterized Variable Names).

- DESIGN CHOICE (D-11) — The value domain for `.u32` is proposed as a fixed-width 32-bit unsigned domain (e.g., finite naturals of width 32 or 32-bit bit vectors); the exact Lean representation is a Lean-mapping decision outside this artifact.
- DESIGN CHOICE (D-12) — Registers are represented by names (identifiers) mapped to values, not by values alone, to support declaration typing and destination updates. Register references are by name rather than address because the official source states that registers are not fully addressable (SF-21).
- DESIGN CHOICE (D-13) — Predicate register values are represented by a two-valued (boolean-like) domain, grounded in the official statement that predicate registers are 1-bit (SF-21) and in the boolean-style use of predicates in `setp` examples (SF-12, SF-24). The exact encoding of "1-bit" into a Lean value domain is a Lean-mapping decision (see A-7, OQ-5).
- DESIGN CHOICE (D-14) — The minimal state for base `add.u32` is the pair (value-register file, predicate-register file). No memory state space, special-register state space, or other state space is included because `add.u32` has no memory operands and its description writes only to a destination register (SF-3, SF-4). The official `.reg` state-space text (SF-21) supports the register-file model, and the rule that predicate variables may only be declared in the register state space (SF-22) supports placing predicate registers in the same overall register state space rather than a separate one.
- DESIGN CHOICE (D-15) — Compilation-level and ABI notes in the register section (register spilling, function-scope restriction, legacy module-scope handling, alignment for multi-word loads/stores; SF-21) are not modeled in the instruction-local architecture for `add.u32`. Whether any of these affect a future program-level semantics is an open question outside the bounded unit.

## 7. Operand architecture

- DESIGN CHOICE (D-16) — The base `add.u32` form has exactly three operands in the order `d, a, b` (SF-3). The operand-position roles of section 9.2 (destination `d`; sources `a`, `b`) apply (SF-19).
- DESIGN CHOICE (D-17) — Source operands `a` and `b` may be register variables or constant immediates, because the official text states that integer arithmetic instructions operate "in register and constant immediate forms" (SF-20) and the official example `add.u32 %r, %r, 4;` shows an immediate source (SF-17). An immediate is modeled as a constant whose type is compatible with the instruction type under SF-15.
- DESIGN CHOICE (D-18) — The destination operand `d` is a register variable in the `.reg` state space (SF-4, SF-21), or the bit bucket `_` (SF-16). When `d` is `_`, the result is discarded and no destination register is updated.

## 8. Predication architecture

Predication is expressed uniformly by evaluation of the complete guard expression. The complete guard expression is: "true" when no guard is present; the value of the predicate register `p` for `@p`; and the negation of the value of `p` for `@!p`.

- DESIGN CHOICE (D-19) — Guard evaluation rule: an instruction executes if and only if its complete guard expression evaluates true. Cases: no guard — the complete guard expression is true and the instruction executes unconditionally (SF-11); `@p` — the complete guard expression evaluates to the value of predicate `p` (SF-11); `@!p` — the complete guard expression evaluates to not (value of `p`) (SF-11, SF-24).
- DESIGN CHOICE (D-20) — No state update is proposed only when the complete guard expression evaluates false. This single rule covers `@p` (no update when `p` is false) and `@!p` (no update when `not p` is false, i.e., when `p` is true), and it is the only guard-false consequence used in this architecture (D-6, D-8, A-4, OQ-3).
- DESIGN CHOICE (D-21) — A guard refers to a `.pred`-typed predicate register variable in the register state space (SF-11, SF-22). The guard is written with an `@` prefix to the left of the opcode (SF-11, SF-19). The `ld.param`/`st.param` predication exception (SF-13) does not apply to `add`.
- Predication is applicable to `add`: "All PTX instructions may be predicated" (SF-10) and the `add` section itself shows `@p add.u32 x,y,z;` (SF-9) and the sibling example `@p add.s32 j, j, 1;` (SF-24).

## 9. Version and target representation

For the bounded base unit, version and target representation covers only the base `add.u32` facts.

- DESIGN CHOICE (D-22) — Version restrictions are represented as an "introduced-in" lower bound over PTX ISA versions. For `add.u32` the bound is PTX ISA 1.0 (SF-7). The separate 9.2 introduction of `add.sat.u32` is a source fact (SF-7) that concerns a future unit only.
- DESIGN CHOICE (D-23) — Target restrictions are represented as a requirement predicate over target architectures. For base `add.u32` the requirement is "all target architectures" (SF-8). A target-gating validation obligation (VAL-6) checks that the recorded requirement matches the official Target ISA Notes.
- DESIGN CHOICE (D-24) — The family-specific target notes for future saturating/packed forms (`sm_120f` or higher in the same family; SF-8, SF-25) are recorded as source facts but are not modeled as architecture commitments in this bounded base artifact. They concern only forms outside the bounded unit; their formal meaning is deferred to the future unit that models those forms (OQ-1). No "same family" formal model is introduced here.

## 10. Meaningful validation and theorem-obligation families

This section distinguishes validation obligations (definitional well-formedness checks performed at parse/type-validation time) from proof obligations (theorems stated over a future execution relation). No Lean statements are given. Arithmetic properties of `add.u32` (including overflow/wrap behavior) are deliberately out of scope (OQ-2).

- DESIGN CHOICE (D-25) — The future execution semantics for `add.u32` is designed to be represented as an execution relation between (state, instruction) and state, not merely as a function. Determinism and frame/locality obligations are stated as properties of that relation. This avoids theorem obligations that hold only because a total-function data structure was chosen.
- DESIGN CHOICE (D-26) — Validation obligations (VAL-1 through VAL-6 below) are definitional checks, not theorem obligations. They are run as part of parsing, typing, and gating validation; they are not proposed as proofs of semantic properties.

Validation obligations:

| ID | Obligation | Kind | Grounding | Non-vacuity note |
|---|---|---|---|---|
| VAL-1 | Type well-formedness: the instruction type specifier `.u32` is a valid unsigned-integer fundamental type of 32-bit width. | validation | SF-3, SF-14, SF-21 | Definitional check over the type representation; not a semantic theorem. |
| VAL-2 | Operand typing: operands `d`, `a`, `b` are type-compatible with the instruction type under the compatibility rules. | validation | SF-5, SF-15 | Definitional check over the operand-typing relation. |
| VAL-3 | Guard well-typedness: if a guard is present, it refers to a `.pred`-typed predicate register variable in the register state space. | validation | SF-11, SF-22 | Definitional check over the guard representation. |
| VAL-4 | Destination membership: the destination operand denotes a declared register variable, or is the bit bucket `_`. | validation | SF-22, SF-16 | Definitional check over the destination representation. |
| VAL-5 | Version gating: the recorded introduced-in bound for `add.u32` matches the official PTX ISA Note (PTX ISA 1.0). | validation | SF-7 | Conformance check that the model's version metadata derives from the official note; it is a derivation check, not a theorem about semantics. |
| VAL-6 | Target gating: the recorded target requirement for `add.u32` matches the official Target ISA Note ("all target architectures"). | validation | SF-8 | Conformance check on target metadata; near-trivial by design because the base form has no family restriction, and the family-restriction machinery is explicitly out of scope (D-24). |

Proof obligations (candidate families, stated over the future execution relation):

| ID | Obligation | Grounding | Non-vacuity note |
|---|---|---|---|
| PRF-1 | Determinism: for any well-formed state and well-typed instruction, the execution relation relates at most one resulting state. | A-3 (no nondeterminism evidenced) | Stated over a relation, so it does not hold merely by representing semantics as a function (D-25). |
| PRF-2 | Destination-only update / frame: when the instruction executes with a register destination, only the destination register may change; every other value register and every predicate register is unchanged. | SF-4 (writes result into destination register), SF-3 (no other destinations) | Meaningful locality/frame obligation over the execution relation; it rules out spurious updates and is not derivable from a functional state representation alone. |
| PRF-3 | Bit-bucket discard: when the destination is `_`, execution changes no value register. | SF-16 | Meaningful frame obligation specific to the bit-bucket form. |
| PRF-4 | Guard-false frame: when the complete guard expression evaluates false, the entire state is unchanged. | SF-11, SF-24, D-20 | Meaningful guard-behavior frame obligation covering both `@p` and `@!p` uniformly. |
| PRF-5 | Guard-behavior: the instruction executes if and only if the complete guard expression evaluates true; the no-guard, `@p`, and `@!p` cases satisfy the D-19 rule. | SF-10, SF-11, SF-24 | Relates guard evaluation to the execution relation; the `@!p` case is stated without the erroneous "negated guard true means no-op" phrasing (F-5). |
| PRF-6 | Result-domain membership: when the instruction executes, the value written to the destination lies in the 32-bit unsigned value domain of `.u32`. | SF-14, D-11 | Typing-soundness-style obligation over the execution relation; it does not assert which arithmetic value is written. |

## 11. Assumptions

- ASSUMPTION (A-1) — The HTML document is authoritative for this unit; the manifest-recorded PDF was not read.
- ASSUMPTION (A-2) — Instruction-local semantics (a single instruction evaluated against a minimal state) is sufficient for `add.u32`; no program-counter, memory, or concurrency context is required for the architecture foundations.
- ASSUMPTION (A-3) — `add.u32` is deterministic; no nondeterminism is evidenced in the official source read. This is an assumption based on absence of evidence in the sections read, not a source fact; it must be re-verified in the semantic phase (PRF-1).
- ASSUMPTION (A-4) — The guard-false consequence "no state update" is the intended meaning of "controls conditional execution" (SF-11), supported by the guard examples (SF-24); this interpretation is pending human approval (OQ-3).
- ASSUMPTION (A-5) — "add.u32" denotes the scalar, non-saturating, unsigned 32-bit form only in this artifact.
- ASSUMPTION (A-6) — The official source read defines no error, trap, or exceptional behavior for base `add`; therefore the outcome representation (D-8) has no error constructor for this unit. This is an assumption based on absence of evidence in lines 8757-8842 and the sections read, not a source fact; the semantic phase must re-verify.
- ASSUMPTION (A-7) — The 1-bit predicate register (SF-21) is mapped to a two-valued (boolean-like) value domain by design; the exact encoding is a Lean-mapping decision (D-13, OQ-5).
- ASSUMPTION (A-8) — A literal search for the string "Target ISA Version" in the HTML returned zero matches; this negative result supports no document-wide claim about version/target rubrics. Within the `add` section read, version and target information appears under the "PTX ISA Notes" and "Target ISA Notes" rubrics (SF-7, SF-8).

## 12. Open questions

- OPEN QUESTION (OQ-1) — The formal meaning of "`sm_120f` or higher in the same family" (SF-8, SF-25) is not defined in the official text read. This concerns only future saturating/packed forms and is deferred to the future unit that models them; it is not needed for base `add.u32` (D-24).
- OPEN QUESTION (OQ-2) — The overflow behavior of non-saturating `add.u32` (wrapping vs. otherwise) is not stated in the source read. Resolution is deferred to the semantic-interpretation phase and is deliberately excluded from this architecture artifact (D-27).
- OPEN QUESTION (OQ-3) — The exact consequence of a false guard predicate beyond the "controls conditional execution" wording (SF-11) is interpreted here as "no state update" (A-4); this interpretation needs human approval before the guard-false obligations (PRF-4) are treated as faithful to the specification.
- OPEN QUESTION (OQ-4) — Whether future saturating forms such as `add.sat.u32` should be modeled within the same unit as `add.u32` or as a separate later unit; the bounded task covers only the base `add.u32` form.
- OPEN QUESTION (OQ-5) — The exact Lean encoding of the 1-bit predicate register value domain (D-13, A-7) is a Lean-mapping decision that must be made and human-approved in the Lean-mapping phase.
- OPEN QUESTION (OQ-6) — Whether compilation-level register notes (spilling, function-scope/ABI restriction, module-scope legacy handling; SF-21) impose constraints that a future program-level semantics must model; they are excluded from the instruction-local architecture (D-15).

## 13. Evidence index with section headings, anchors, HTML line ranges, and source SHA-256

Source SHA-256 abbreviations: HTML = `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856` (ptx_isa_9.3.html); MANIFEST = `622e6ce0d3114a909a62726530955993b5f2b98d2f60e45ae1ceb429512208f2` (source-manifest.json).

| # | Section heading | Anchor | Lines | Source | SHA-256 | Status |
|---|---|---|---|---|---|---|
| E-1 | source-manifest.json (initial formalization unit) | (n/a) | manifest lines 9-15 | manifest | MANIFEST | Read |
| E-2 | 9.7.1.1 Integer Arithmetic Instructions: add | `integer-arithmetic-instructions-add` | 8757-8760 | HTML | HTML | Read |
| E-3 | 9.7.1.1 add — Syntax | `integer-arithmetic-instructions-add` | 8763-8774 | HTML | HTML | Read |
| E-4 | 9.7.1.1 add — Description | `integer-arithmetic-instructions-add` | 8762, 8775-8776 | HTML | HTML | Read |
| E-5 | 9.7.1.1 add — Operand types | `integer-arithmetic-instructions-add` | 8783-8784 | HTML | HTML | Read |
| E-6 | 9.7.1.1 add — Semantics block (existence only) | `integer-arithmetic-instructions-add` | 8785-8811 | HTML | HTML | Read (content not extracted per task boundary) |
| E-7 | 9.7.1.1 add — Notes (.sat) | `integer-arithmetic-instructions-add` | 8812-8820 | HTML | HTML | Read |
| E-8 | 9.7.1.1 add — PTX ISA Notes | `integer-arithmetic-instructions-add` | 8821-8825 | HTML | HTML | Read |
| E-9 | 9.7.1.1 add — Target ISA Notes | `integer-arithmetic-instructions-add` | 8826-8833 | HTML | HTML | Read |
| E-10 | 9.7.1.1 add — Examples | `integer-arithmetic-instructions-add` | 8834-8841 | HTML | HTML | Read |
| E-11 | 9.7 Instructions (intro) | `instructions` | 8718-8723 | HTML | HTML | Read (anchor verified at line 8718) |
| E-12 | 9.3 Predicated Execution | `predicated-execution` | 7537-7552 | HTML | HTML | Read |
| E-13 | 9.3 Predicated Execution (setp note) | `predicated-execution` | 7551-7552 | HTML | HTML | Read |
| E-14 | Predication exception (ld.param/st.param) | (anchor not captured) | 6261 | HTML | HTML | Read (snippet) |
| E-15 | 5.2.1 Fundamental Types | `fundamental-types` | 3015-3022 | HTML | HTML | Read |
| E-16 | Table 8 Fundamental Type Specifiers | `fundamental-types-fundamental-type-specifiers` | 3025-3061 | HTML | HTML | Read |
| E-17 | 5.2.1 Fundamental Types — compatibility | `fundamental-types` | 3062-3066 | HTML | HTML | Read |
| E-18 | 9.2 PTX Instructions (operand format; bit bucket) | `ptx-instructions` | 7513-7536 | HTML | HTML | Read (anchor verified at line 7513; bit bucket text at 7534-7535) |
| E-19 | State-space example with `add.u32 %r, %r, 4;` | (heading not captured; precedes `shared-state-space`) | 2902 | HTML | HTML | Read (snippet) |
| E-20 | Function example with `add.u32 %res, %ptr, %inc;` | (heading not captured) | 6172 | HTML | HTML | Read (snippet) |
| E-21 | source-manifest.json artifacts (PDF metadata) | (n/a) | manifest lines 16-31 | manifest | MANIFEST | Read |
| E-22 | 5.1.1 Register State Space | `register-state-space` | 2613-2631 | HTML | HTML | Read (this revision) |
| E-23 | 5.4 Variables — declaration rule; predicate variables only in register state space | (subsection anchor not captured) | 3755 | HTML | HTML | Read (snippet; this revision) |
| E-24 | 5.4.6 Parameterized Variable Names | `parameterized-variable-names` | 3933-3948 | HTML | HTML | Read (this revision) |
| E-25 | 9.1 Format and Semantics of Instruction Descriptions (intro) | `format-and-semantics-of-instruction-descriptions` | 7505-7512 | HTML | HTML | Read (this revision) |
| E-26 | 9.3 Predication examples (`@p add.s32`; `@!p bra`) | `predicated-execution` | 7553-7574 | HTML | HTML | Read (this revision) |
| E-27 | Literal occurrences of `sm_120f` (57 matches; no formal "same family" definition found in matches read) | (multiple) | 8832, 8901, 9340, 9419, 9500, 17681, ... | HTML | HTML | Read via literal search (this revision) |

## 14. Finding-resolution matrix for F-1 through F-10

| ID | Severity (v1) | Status | Resolution in v2 |
|---|---|---|---|
| F-1 | BLOCKER | RESOLVED | Section 1 no longer labels project status or bounded scope as SOURCE FACT. Status is a plain project-metadata note; bounded scope and scope exclusions are DESIGN CHOICE (D-0, D-0b, D-0c). SOURCE FACT is retained only for manifest-grounded unit identity (SF-1 in Section 3). |
| F-2 | MAJOR | RESOLVED | The OBSERVATION label is removed. Negative-evidence content is re-expressed as ASSUMPTION (A-6: no error behavior for base add; A-8: zero-match search) and OPEN QUESTION (OQ-3). Every architectural/semantic statement now uses exactly one of SOURCE FACT / DESIGN CHOICE / ASSUMPTION / OPEN QUESTION; the Gate A checklist four-label item is updated accordingly (Section 15). |
| F-3 | MAJOR | RESOLVED | The register chapter evidence was read in this revision: Section 5.1.1 Register State Space (SF-21), Section 5.4 variable declaration (SF-22), Section 5.4.6 Parameterized Variable Names (SF-23). D-4, D-5, and D-12 are now grounded in official text and are stated as design choices over that evidence (Section 6). Residual encoding/compilation questions remain as OPEN QUESTION (OQ-5, OQ-6) rather than guesses. |
| F-4 | MINOR | RESOLVED | Negative-evidence items are labeled ASSUMPTION (A-3 determinism, A-6 no-error, A-8 zero-match search) with explicit semantic-phase re-verification requirements. The document-wide generalization about version/target rubrics is removed; A-8 confines the claim to the add section and the negative search result. |
| F-5 | MAJOR | RESOLVED | The erroneous negated-guard wording is deleted. Guard-false obligations are stated uniformly via the complete guard expression (D-19, D-20, PRF-4, PRF-5): no state update is proposed only when the complete guard expression evaluates false; `@!p` executes when not p is true. No "negated guard true means no-op" phrasing remains. |
| F-6 | MINOR | RESOLVED | D-6 and A-4 now phrase the no-op condition as "when the complete guard expression evaluates false", covering both `@p` and `@!p`; OQ-3 records the pending human approval of the interpretation. |
| F-7 | MAJOR | RESOLVED | Section 10 replaces the vacuous family with (a) validation obligations (VAL-1..VAL-6, definitional checks, not theorems; D-26) and (b) proof obligations over a future execution relation (PRF-1..PRF-6): determinism over a relation (PRF-1), destination-only update/frame (PRF-2), bit-bucket discard (PRF-3), guard-false frame (PRF-4), guard-behavior (PRF-5), result-domain membership (PRF-6). D-25 ensures obligations do not follow only from a chosen data structure. Unsupported arithmetic properties remain out of scope (OQ-2, D-27). |
| F-8 | MAJOR | RESOLVED | Gate A checklist items are corrected: the four-label item is now scoped to architectural/semantic statements with plain metadata notes identified as such; the register-gap item is replaced by a register-evidence-complete item. E-11 anchor verified as `instructions` (line 8718); E-18 anchor verified as `ptx-instructions` (line 7513, bit bucket text 7534-7535); E-25 adds the verified section 9.1 anchor. |
| F-9 | MAJOR | PARTIALLY_RESOLVED | The missing evidence reads were performed: section 9.1/9.2 operand format (SF-19, E-18, E-25) and the register/constant immediate rule (SF-20, resolving the immediate-operand question that was OQ-1 in v1); the register chapter (SF-21, SF-22, SF-23, resolving the register-model evidence gap); the sm-family text occurrences (SF-25), which are removed from the base architecture (D-24) because they concern only future saturating/packed forms. Two items remain open by design: the exact no-op consequence of a false guard needs a human-approved interpretation (OQ-3), and the formal meaning of "same family" is deferred to the future saturating-form unit (OQ-1). |
| F-10 | MINOR | RESOLVED | The phantom cross-reference to "sub, mul, etc. in Section 3" is removed. Section 16 (non-goals) no longer references nonexistent content; the only mentions of other instruction forms are the official syntax facts (SF-3, SF-6, SF-25) and the explicit statement that they are not modeled. |

## 15. Gate A review checklist

Gate A is NOT ready. This artifact must receive an independent re-critique before it may be presented for human Gate A review. The following items are the checklist for that future review:

- [ ] The artifact is marked `DRAFT — NOT HUMAN APPROVED` and is not promoted to `accepted/`.
- [ ] Scope is bounded to language-wide foundations strictly required for future `add.u32` formalization (D-0).
- [ ] Project status and bounded scope are classified as project design choices or metadata, not SOURCE FACT (F-1).
- [ ] Every architectural/semantic statement uses exactly one of SOURCE FACT / DESIGN CHOICE / ASSUMPTION / OPEN QUESTION; plain metadata notes are identified as such (F-2).
- [ ] Every SOURCE FACT is traceable to an official source entry in the evidence index (Section 13).
- [ ] Register/value/state architecture is grounded in official register sections read in this revision (SF-21, SF-22, SF-23; Section 6) (F-3).
- [ ] Operand architecture is grounded in the section 9.1/9.2 operand-format text and the register/constant immediate rule (SF-19, SF-20; Section 7) (F-9).
- [ ] Predication is expressed uniformly by evaluation of the complete guard expression for no-guard, `@p`, and `@!p`; no state update is proposed only when the complete guard expression evaluates false (D-19, D-20) (F-5, F-6).
- [ ] Validation obligations and proof obligations are distinguished; proof obligations are relational, non-vacuous, and include frame/locality and guard-behavior families (Section 10) (F-7).
- [ ] Version and target representation is limited to base `add.u32` (PTX ISA 1.0; all target architectures); saturating/packed family concepts are excluded or deferred (Section 9) (F-9).
- [ ] Evidence anchors are verified: `instructions` (E-11), `ptx-instructions` (E-18), `register-state-space` (E-22), `parameterized-variable-names` (E-24), `format-and-semantics-of-instruction-descriptions` (E-25) (F-8).
- [ ] Negative-evidence items are labeled ASSUMPTION or OPEN QUESTION and are flagged for semantic-phase re-verification (A-3, A-6, A-8) (F-4).
- [ ] Unsupported or unread points are marked OPEN QUESTION rather than guessed (Section 12).
- [ ] No instruction-level arithmetic semantics of `add.u32` were extracted or defined (D-27).
- [ ] No `add.u32` source bundle was constructed, and no Lean code was written (D-28, D-29).
- [ ] No other instruction was modeled as a separate unit; saturating/packed forms are explicitly out of scope (D-30, OQ-4).
- [ ] Dependencies required before `add.u32` formalization are represented in the design choices and validated in Section 10.

## 16. Explicit non-goals

- DESIGN CHOICE (D-27) — Not defining the arithmetic semantics of `add.u32`, including overflow/wrap behavior (deferred to the semantic phase; OQ-2).
- DESIGN CHOICE (D-28) — Not writing any Lean code or concrete Lean theorem statements.
- DESIGN CHOICE (D-29) — Not constructing an `add.u32` instruction-level source bundle.
- DESIGN CHOICE (D-30) — Not modeling saturating or packed `add` forms (`add.sat.u32`, `add.u16x2`, etc.) as units; their syntax, notes, and target-family restrictions are recorded as source facts (SF-3, SF-6, SF-8, SF-25) but are not architecture commitments of the bounded base unit.
- DESIGN CHOICE (D-31) — Not building a memory, state-space, or concurrency model for this unit.
- DESIGN CHOICE (D-32) — Not resolving within this artifact the deferred open questions OQ-1 (same-family meaning) and OQ-2 (overflow behavior); they are the property of future units and the semantic phase.
- DESIGN CHOICE (D-33) — Not approving Gate A; approval is a human decision, and Gate A remains not ready until this artifact receives an independent re-critique. Not promoting anything to `accepted/`.
