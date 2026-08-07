# PTX add.u32 Foundation Architecture — DRAFT — NOT HUMAN APPROVED

## 1. Status and bounded scope

- STATUS: SOURCE FACT — This artifact is a DRAFT architecture candidate produced for Gate A review. It is marked `DRAFT — NOT HUMAN APPROVED`. It has not been reviewed or approved by a human reviewer and is not promoted to `accepted/`.
- SOURCE FACT — The initial formalization unit of the Spec2Lean project is PTX ISA 9.3 `add.u32` (source-manifest.json, `initial_formalization_unit` = `add.u32`, `instruction_family` = `add`, section 9.7.1.1).
- SOURCE FACT — The bounded scope of this artifact is the language-wide foundations strictly required for the future formalization of `add.u32`: instruction representation, operand categories, scalar integer types, register/value representation, minimal machine state, state reads and destination updates, predication, execution-result representation, version/target-restriction representation, traceability, and candidate theorem-obligation families.
- DESIGN CHOICE — This artifact describes architecture only. It does not define the arithmetic semantics of `add.u32`, does not construct an instruction-level source bundle, and does not contain Lean code.
- DESIGN CHOICE — "add.u32" in this artifact denotes the scalar, non-saturating, unsigned 32-bit form of the `add` instruction. Saturating and packed sub-word forms (`add.sat.u32`, `add.u16x2`, etc.) are identified as source facts but are not modeled as separate units here.
- ASSUMPTION — The PTX ISA 9.3 HTML document is treated as the authoritative reading source for this unit; the PDF artifact is recorded in the manifest but was not read in this pass.

## 2. Source documents used

- SOURCE FACT — Primary source: `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html`, official NVIDIA "Parallel Thread Execution ISA" version 9.3, SHA-256 `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`, 47,743 lines.
- SOURCE FACT — Metadata source: `documents/sources/nvidia/ptx/9.3/source-manifest.json`, SHA-256 `622e6ce0d3114a909a62726530955993b5f2b98d2f60e45ae1ceb429512208f2`, lines 1–39, which records publisher NVIDIA, specification version 9.3, source classification "official", retrieval timestamp, and the initial formalization unit.
- SOURCE FACT — The manifest records a PDF artifact (`raw/ptx_isa_9.3.pdf`, SHA-256 `769cc12e363e7bb9cd311464f2a42edbdaf4c74ca18575de8c358e93223434fc`). The PDF was not read in this pass.
- ASSUMPTION — No other specification source was consulted. All evidence below comes from the two documents listed in this section.

## 3. Explicit official-source facts

- SOURCE FACT (SF-1) — Manifest unit identity: the initial formalization unit is `add.u32`; instruction family `add`; section number 9.7.1.1; section heading "Integer Arithmetic Instructions: add"; html anchor `integer-arithmetic-instructions-add` (source-manifest.json lines 9–15).
- SOURCE FACT (SF-2) — Section 9.7.1.1 "Integer Arithmetic Instructions: add" exists at HTML anchor `integer-arithmetic-instructions-add`, lines 8757–8760, immediately followed by its body through line 8842.
- SOURCE FACT (SF-3) — The `add` syntax is `add.type1 d, a, b;` and `add{.sat}.type2 d, a, b;`, where `.type1 = { .u16, .u64, .s16, .s64 }` and `.type2 = { .u32, .u16x2, .u8x4, .s32, .s16x2, .s8x4 }` (HTML lines 8763–8774).
- SOURCE FACT (SF-4) — The `add` meaning is stated as "Add two values." (line 8762) and "Performs addition and writes the resulting value into a destination register." (line 8776).
- SOURCE FACT (SF-5) — Operand typing: "Operands `d`, `a` and `b` have the same type as the instruction type." For the packed instruction types `.u16x2`, `.s16x2`, `.u8x4`, `.s8x4`, operands `d`, `a`, `b` have type `.b32` (lines 8783–8784).
- SOURCE FACT (SF-6) — The `.sat` modifier "limits result to `MININT..MAXINT` (no overflow) for the size and signedness of the operation" and "Applies only to `.u32`, `.s32`, `.u16x2`, `.s16x2`, `.u8x4`, `.s8x4` types" (lines 8813–8819).
- SOURCE FACT (SF-7) — PTX ISA Notes: "Introduced in PTX ISA version 1.0."; `add.sat.u32` introduced in PTX ISA version 9.2 (lines 8821–8825).
- SOURCE FACT (SF-8) — Target ISA Notes: base `add` is "Supported on all target architectures."; `add.sat.u32` (with the other listed packed/sat forms) is "supported on following family-specific architectures: `sm_120f` or higher in the same family" (lines 8826–8833).
- SOURCE FACT (SF-9) — The `add` Examples block includes the predicated form `@p add.u32 x,y,z;` (lines 8834–8841).
- SOURCE FACT (SF-10) — Section 9.7 "Instructions" intro (line 8722): "All PTX instructions may be predicated. In the following descriptions, the optional guard predicate is omitted from the syntax."
- SOURCE FACT (SF-11) — Section 9.3 "Predicated Execution" (anchor `predicated-execution`, lines 7537–7550): predicate registers are virtual and have `.pred` as the type specifier; "All instructions have an optional *guard predicate* which controls conditional execution of the instruction"; the syntax is to prefix an instruction with `@{!}p`, where `p` is a predicate variable, optionally negated; "Instructions without a guard predicate are executed unconditionally."
- SOURCE FACT (SF-12) — "Predicates are most commonly set as the result of a comparison performed by the `setp` instruction" (lines 7551–7552).
- SOURCE FACT (SF-13) — Predication exception: "`st.param` and `ld.param` instructions used for argument passing cannot be predicated" (line 6261). This exception does not mention `add`.
- SOURCE FACT (SF-14) — Section 5.2.1 "Fundamental Types" (anchor `fundamental-types`, lines 3015–3022): "the fundamental types reflect the native data types supported by the target architectures"; "A fundamental type specifies both a basic type and a size"; "Register variables are always of a fundamental type, and instructions operate on these types"; "The same type-size specifiers are used for both variable definitions and for typing instructions." Table 8 "Fundamental Type Specifiers" (anchor `fundamental-types-fundamental-type-specifiers`, lines 3025–3061) lists `.u8`, `.u16`, `.u32`, `.u64` under "Unsigned integer", and also lists signed integer, floating-point, bits (untyped), and predicate basic types.
- SOURCE FACT (SF-15) — Type compatibility: "Operand types and sizes are checked against instruction types for compatibility."; "Two fundamental types are compatible if they have the same basic type and are the same size. Signed and unsigned integer types are compatible if they have the same size. The bit-size type is compatible with any fundamental type having the same size." (lines 3062–3065).
- SOURCE FACT (SF-16) — Section 9.2 "PTX Instructions" (bit-bucket sentence, line 7535): "A *bit bucket* operand denoted with an underscore (`_`) may be used in place of a destination register."
- SOURCE FACT (SF-17) — Example usage evidence: `add.u32 %r, %r, 4;` appears in an example with `.reg .u32 %r;` and `.reg .pred %p;` declarations (line 2902; enclosing section heading not captured in this pass, example occurs just before section 5.1.7).
- SOURCE FACT (SF-18) — Example usage evidence: `add.u32 %res, %ptr, %inc;` appears inside a `.func` body with `.reg .u32` formal parameters (line 6172; enclosing section heading not captured in this pass).
- OBSERVATION (negative evidence, not a source fact) — In the portion of section 9.7.1.1 read (lines 8757–8842), no exceptional behavior, trap, error status, or undefined behavior is stated for `add`. The section contains a "Semantics" pseudocode block (lines 8785–8811) whose arithmetic content is deliberately not extracted here per the task boundary.
- OBSERVATION (negative evidence, not a source fact) — A search for the literal "Target ISA Version" returned zero matches in the HTML; version/target information is expressed per instruction via "PTX ISA Notes" and "Target ISA Notes" rubrics.

## 4. Proposed minimal Lean architecture

This section proposes the minimal architecture components required for the future formalization of `add.u32`. No Lean code is written; each component states its source grounding and the proposed design.

- DESIGN CHOICE (D-1) — PTX instruction representation: a structured instruction form with fields: optional guard (`@{!}p`), mnemonic (`add`), type specifier (`.u32`), optional modifier set (e.g., `{.sat}`), destination operand, and source operand list (`a`, `b`). Grounding: SF-3, SF-10, SF-11, SF-16.
- DESIGN CHOICE (D-2) — Operand categories: for `add.u32` the minimal categories are (a) destination register, (b) source register, (c) source immediate/constant. A bit-bucket destination `_` is an alternative destination form. Grounding: SF-5 (d, a, b same type as instruction), SF-17 (immediate source `4`), SF-18 (register sources), SF-16 (bit bucket).
- DESIGN CHOICE (D-3) — Scalar integer type and width representation: a fundamental type is represented as a pair (basic type, size in bits); `.u32` maps to (UnsignedInteger, 32). A minimal type lattice is needed only up to the types that `add.u32` and its operand-typing rule require. Grounding: SF-14, SF-15.
- DESIGN CHOICE (D-4) — Register/value representation: register variables always carry a fundamental type (SF-14); values for `.u32` live in a fixed-width 32-bit unsigned value domain; a register file maps register names to values of their declared type. Predicate registers are boolean-valued (SF-11).
- DESIGN CHOICE (D-5) — Minimal machine state: for scalar `add.u32`, the state contains only a value-register file and a predicate-register file. No memory state space, shared state, or special registers are required by the `add.u32` syntax or description. Grounding: SF-3 (no memory operand), SF-4 (destination is a register).
- DESIGN CHOICE (D-6) — State reads and destination update: source operand values are read from the state (registers) or from immediate constants; when the instruction executes, the destination register is updated with the resulting value; when the instruction does not execute (guard false), the state is unchanged. Grounding: SF-4, SF-11; the guard-false consequence is an interpretation recorded in Section 10 and flagged in OQ-5.
- DESIGN CHOICE (D-7) — Guard/predication architecture: the guard is an optional `.pred`-typed register reference, optionally negated (`@!p`); presence of a guard makes execution conditional; absence makes execution unconditional. Grounding: SF-10, SF-11.
- DESIGN CHOICE (D-8) — Execution-result / failure representation: an instruction-local result type with at least two cases — "executed" (with updated state) and "guard false" (no state change). No error constructor is proposed yet because the official source read defines no exceptional behavior for `add` (see Section 8).
- DESIGN CHOICE (D-9) — Version and target-restriction representation: a record pairing a PTX ISA version bound ("introduced in" version) with a target requirement. For `add.u32`: introduced-in PTX ISA 1.0; target requirement "all target architectures". For `add.sat.u32` (future unit): introduced-in 9.2; target requirement `sm_120f` family-or-higher. Grounding: SF-7, SF-8.
- DESIGN CHOICE (D-10) — Traceability representation: every semantic claim carries (document identity, specification version, section heading, HTML anchor, HTML line range, source SHA-256). Grounding: SF-1 and the evidence index in Section 12.

## 5. Fact-to-design mapping

- SOURCE FACT → DESIGN: SF-3 (add syntax) → D-1 (instruction representation).
- SOURCE FACT → DESIGN: SF-5, SF-16, SF-17, SF-18 (operand typing, bit bucket, example operands) → D-2 (operand categories).
- SOURCE FACT → DESIGN: SF-14, SF-15 (fundamental types, compatibility) → D-3 (scalar integer type/width).
- SOURCE FACT → DESIGN: SF-14, SF-11 (register variables of fundamental type, virtual `.pred` registers) → D-4 (register/value representation).
- SOURCE FACT → DESIGN: SF-3, SF-4 (no memory operands; destination register) → D-5 (minimal machine state).
- SOURCE FACT → DESIGN: SF-4, SF-11 (writes result to destination register; conditional execution) → D-6 (state reads and destination update).
- SOURCE FACT → DESIGN: SF-10, SF-11 (all instructions predicable; guard syntax) → D-7 (guard/predication).
- SOURCE FACT → DESIGN: negative observation (no exceptional behavior in add section) → D-8 (execution-result representation).
- SOURCE FACT → DESIGN: SF-7, SF-8 (PTX ISA Notes, Target ISA Notes) → D-9 (version/target restriction representation).
- SOURCE FACT → DESIGN: SF-1 and manifest metadata → D-10 (traceability representation).

## 6. Dependencies required before add.u32 formalization

The following language-wide dependencies must exist before the `add.u32` semantic unit can be formalized:

- SOURCE FACT — A fundamental-type representation including at least unsigned 32-bit (`.u32`) and the type-compatibility relation (SF-14, SF-15).
- SOURCE FACT — A value domain for fixed-width 32-bit unsigned values (SF-14).
- SOURCE FACT — A register model: register names, `.reg` declarations of fundamental type, and a value-register file (SF-14, SF-17, SF-18).
- SOURCE FACT — A predicate-register model and guard syntax `@{!}p` (SF-11).
- DESIGN CHOICE — A minimal instruction AST (guard, mnemonic, type specifier, modifiers, destination, sources) per D-1.
- DESIGN CHOICE — An operand-category model (destination register, source register, source immediate, bit bucket) per D-2.
- DESIGN CHOICE — A version/target restriction model per D-9.
- DESIGN CHOICE — An execution-result type per D-8.
- DESIGN CHOICE — A traceability convention per D-10.
- OPEN QUESTION — The register chapter of the PTX ISA (registers naming grammar and `.reg` state-space rules) was not read in this pass; its contents may be required before register modeling can be confirmed (see OQ-4).

## 7. Predication applicability

- SOURCE FACT — Predication is applicable to `add`: "All PTX instructions may be predicated" (SF-10, line 8722).
- SOURCE FACT — The `add` section itself shows the predicated example `@p add.u32 x,y,z;` (SF-9).
- SOURCE FACT — The guard syntax and conditional-execution rule are defined in section 9.3: optional guard predicate `@{!}p`; instructions without a guard are executed unconditionally (SF-11).
- DESIGN CHOICE — Therefore the architecture must include a guard field on the instruction representation (D-7) and a guard-false state-unchanged behavior (D-6).
- ASSUMPTION — For `add.u32`, the guard is a `.pred`-typed register reference; no other predication forms are needed for this unit.
- OPEN QUESTION — The precise guard-false consequence ("conditional execution" wording) is interpreted here as "no state update"; the official text does not spell out the no-op in the excerpt read (see OQ-5).

## 8. Error, undefined-behavior, version, and target-restriction representation

- ASSUMPTION (errors) — The official source read defines no error, trap, or exceptional behavior for base `add`; therefore the execution-result type (D-8) has no error constructor for this unit. This is an assumption based on absence of evidence in lines 8757–8842, not a source fact; the semantic phase must re-verify.
- OPEN QUESTION (undefined behavior) — The official source read does not state the overflow behavior of the non-saturating `add.u32` (whether the 32-bit result wraps modulo 2^32 or is otherwise defined). Per the task boundary, the arithmetic semantics of `add.u32` are not resolved in this architecture artifact; the overflow behavior question is deferred to the semantic-interpretation phase (see OQ-3).
- SOURCE FACT (version) — PTX ISA version notes for `add`: introduced in PTX ISA 1.0; `add.sat.u32` introduced in PTX ISA 9.2 (SF-7).
- SOURCE FACT (target restriction) — Target ISA notes for `add`: base `add` supported on all target architectures; `add.sat.u32` requires `sm_120f` or higher in the same family (SF-8).
- DESIGN CHOICE (representation) — Version restrictions are represented as a "introduced-in" lower bound; target restrictions are represented as an enumerated target requirement (all targets, or a specific `sm_XX` family-or-higher) per D-9.
- OPEN QUESTION — The phrase "`sm_120f` or higher in the same family" has no formal model in the official text; its intended meaning for target-requirement evaluation needs a human-approved interpretation before it can be formalized (see OQ-2).

## 9. Candidate theorem-obligation families

These are candidate families of theorem obligations for the `add.u32` unit. They are architecture-level families only; no Lean statements are given.

- DESIGN CHOICE (TO-1) — Type well-formedness: the instruction type specifier `.u32` is a valid fundamental type of the required width.
- DESIGN CHOICE (TO-2) — Operand typing: operands `d`, `a`, `b` are type-compatible with the instruction type under the compatibility rules of SF-15.
- DESIGN CHOICE (TO-3) — Guard well-typedness: if a guard is present, it refers to a `.pred`-typed predicate register (SF-11).
- DESIGN CHOICE (TO-4) — Destination membership: the destination operand denotes a register in the value-register file (or is the bit bucket `_`).
- DESIGN CHOICE (TO-5) — State totality: the updated state is a total function over the register domain.
- DESIGN CHOICE (TO-6) — Guard-false no-op: when the guard predicate evaluates false (or negated guard true), the state is unchanged.
- DESIGN CHOICE (TO-7) — Result-domain membership: the resulting value is in the 32-bit unsigned value domain of the `.u32` type.
- DESIGN CHOICE (TO-8) — Determinism: from a given state and instruction, the resulting state is unique (no nondeterminism is evidenced for `add`).
- DESIGN CHOICE (TO-9) — Version gating: `add.u32` is valid only for PTX ISA versions at or after the introduced-in bound (SF-7).
- DESIGN CHOICE (TO-10) — Target gating: `add.u32` is valid only on permitted target architectures (SF-8).
- DESIGN CHOICE (TO-11) — Bit-bucket discard: when the destination is `_`, the result is discarded and no destination register is updated (SF-16).

## 10. Assumptions and formalization design choices

- ASSUMPTION (A-1) — The HTML document is authoritative for this unit; the manifest-recorded PDF was not read.
- ASSUMPTION (A-2) — Instruction-local semantics (a single instruction evaluated against a minimal state) is sufficient for `add.u32`; no program-counter, memory, or concurrency context is required for the architecture foundations.
- ASSUMPTION (A-3) — `add.u32` is deterministic; no nondeterminism is evidenced in the official source read.
- ASSUMPTION (A-4) — The guard-false consequence "no state update" is the intended meaning of "controls conditional execution" (SF-11); this is an interpretation pending human approval (OQ-5).
- ASSUMPTION (A-5) — "add.u32" denotes the scalar, non-saturating, unsigned 32-bit form only in this artifact.
- DESIGN CHOICE (D-11) — The value domain for `.u32` is proposed as a fixed-width 32-bit unsigned domain (e.g., finite naturals of width 32 or 32-bit bit vectors); the exact Lean representation is a Lean-mapping decision outside this artifact.
- DESIGN CHOICE (D-12) — Registers are represented by names (identifiers) mapped to values, not by values alone, to support declaration typing and destination updates.
- DESIGN CHOICE (D-13) — Traceability fields are part of every semantic claim, per D-10, using the SHA-256 values recorded in Section 2.
- DESIGN CHOICE (D-14) — The type-lattice is kept minimal: only the fundamental types and compatibility rules needed by `add.u32` (SF-14, SF-15) are in scope; full type coverage is out of scope.

## 11. Ambiguities and open questions

- OPEN QUESTION (OQ-1) — Whether source operands of `add.u32` may be immediates: the example `add.u32 %r, %r, 4;` (SF-17) shows an immediate source, but the formal operand-grammar conventions of section 9.1 ("Format and Semantics of Instruction Descriptions") were not read in this pass. The operand-category model (D-2) includes immediates provisionally.
- OPEN QUESTION (OQ-2) — The meaning of "`sm_120f` or higher in the same family" for `add.sat.u32` target restriction (SF-8) is not formally defined in the excerpt; it needs a human-approved interpretation before any target-gating obligation (TO-10) can be stated for saturating forms.
- OPEN QUESTION (OQ-3) — The overflow behavior of non-saturating `add.u32` (wrapping vs. otherwise) is not stated in the source excerpt; resolution is deferred to the semantic-interpretation phase and is deliberately excluded from this architecture artifact.
- OPEN QUESTION (OQ-4) — The PTX ISA register chapter (register naming grammar, `.reg` state-space rules) was not read in this pass; register-model facts currently rest on example evidence (SF-17, SF-18) and the fundamental-type rule (SF-14). A dedicated source read is required before register modeling is confirmed.
- OPEN QUESTION (OQ-5) — The exact consequence of a false guard predicate ("conditional execution" wording, SF-11) is interpreted as "no state update" (A-4); this interpretation needs human approval.
- OPEN QUESTION (OQ-6) — Whether `add.sat.u32` should be modeled within the same unit as `add.u32` or as a separate later unit; the bounded task covers only the base `add.u32` form.

## 12. Evidence index with section headings, anchors, HTML line ranges, and source SHA-256

Source SHA-256 abbreviations: HTML = `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856` (ptx_isa_9.3.html); MANIFEST = `622e6ce0d3114a909a62726530955993b5f2b98d2f60e45ae1ceb429512208f2` (source-manifest.json).

| # | Section heading | Anchor | HTML lines | Source | SHA-256 | Status |
|---|---|---|---|---|---|---|
| E-1 | source-manifest.json (initial formalization unit) | (n/a) | manifest lines 9–15 | manifest | MANIFEST | Read |
| E-2 | 9.7.1.1 Integer Arithmetic Instructions: add | `integer-arithmetic-instructions-add` | 8757–8760 | HTML | HTML | Read |
| E-3 | 9.7.1.1 add — Syntax | `integer-arithmetic-instructions-add` | 8763–8774 | HTML | HTML | Read |
| E-4 | 9.7.1.1 add — Description | `integer-arithmetic-instructions-add` | 8762, 8775–8776 | HTML | HTML | Read |
| E-5 | 9.7.1.1 add — Operand types | `integer-arithmetic-instructions-add` | 8783–8784 | HTML | HTML | Read |
| E-6 | 9.7.1.1 add — Semantics block (existence only) | `integer-arithmetic-instructions-add` | 8785–8811 | HTML | HTML | Read (content not extracted per task boundary) |
| E-7 | 9.7.1.1 add — Notes (.sat) | `integer-arithmetic-instructions-add` | 8812–8820 | HTML | HTML | Read |
| E-8 | 9.7.1.1 add — PTX ISA Notes | `integer-arithmetic-instructions-add` | 8821–8825 | HTML | HTML | Read |
| E-9 | 9.7.1.1 add — Target ISA Notes | `integer-arithmetic-instructions-add` | 8826–8833 | HTML | HTML | Read |
| E-10 | 9.7.1.1 add — Examples | `integer-arithmetic-instructions-add` | 8834–8841 | HTML | HTML | Read |
| E-11 | 9.7 Instructions (intro) | (heading "Instructions"; anchor not captured) | 8722 | HTML | HTML | Read |
| E-12 | 9.3 Predicated Execution | `predicated-execution` | 7537–7550 | HTML | HTML | Read |
| E-13 | 9.3 Predicated Execution (setp note) | `predicated-execution` | 7551–7552 | HTML | HTML | Read |
| E-14 | Predication exception (ld.param/st.param) | (anchor not captured) | 6261 | HTML | HTML | Read (snippet) |
| E-15 | 5.2.1 Fundamental Types | `fundamental-types` | 3015–3022 | HTML | HTML | Read |
| E-16 | Table 8 Fundamental Type Specifiers | `fundamental-types-fundamental-type-specifiers` | 3025–3061 | HTML | HTML | Read |
| E-17 | 5.2.1 Fundamental Types — compatibility | `fundamental-types` | 3062–3065 | HTML | HTML | Read |
| E-18 | 9.2 PTX Instructions — bit bucket | `ptx-instructions` (from TOC) | 7535 | HTML | HTML | Read |
| E-19 | State-space example with `.reg .u32 %r;` and `add.u32 %r, %r, 4;` | (heading not captured; precedes `shared-state-space`) | 2902 | HTML | HTML | Read (snippet) |
| E-20 | Function example with `add.u32 %res, %ptr, %inc;` | (heading not captured) | 6172 | HTML | HTML | Read (snippet) |
| E-21 | source-manifest.json artifacts (PDF metadata) | (n/a) | manifest lines 16–31 | manifest | MANIFEST | Read |
| E-22 | Register chapter (naming, `.reg` state-space rules) | (not captured) | (not read) | HTML | HTML | NOT READ — evidence gap |

## 13. Gate A review checklist

The following items must be verified by the human Gate A reviewer before the architecture can be considered for approval:

- [ ] The artifact is marked `DRAFT — NOT HUMAN APPROVED` and is not promoted to `accepted/`.
- [ ] Scope is bounded to language-wide foundations strictly required for future `add.u32` formalization.
- [ ] Every SOURCE FACT is traceable to an official source entry in the evidence index (Section 12).
- [ ] No instruction-level arithmetic semantics of `add.u32` were extracted or defined.
- [ ] No `add.u32` source bundle was constructed.
- [ ] No Lean code was written.
- [ ] No other instruction was modeled as a separate unit.
- [ ] All statements are labeled SOURCE FACT / DESIGN CHOICE / ASSUMPTION / OPEN QUESTION.
- [ ] Evidence gaps (E-22 register chapter) and open questions (OQ-1..OQ-6) are documented rather than guessed.
- [ ] Predication applicability to `add` is established from official text (SF-10, SF-11) and included in the architecture (D-7).
- [ ] Version and target-restriction representation is grounded in PTX ISA Notes and Target ISA Notes (SF-7, SF-8).
- [ ] Candidate theorem-obligation families are present and identified as candidate families only.
- [ ] Dependencies required before `add.u32` formalization are listed (Section 6).
- [ ] Unsupported or unread points are marked unresolved or as open questions.

## 14. Explicit non-goals

- DESIGN CHOICE — Not defining the arithmetic semantics of `add.u32` (including overflow/wrap behavior; see OQ-3).
- DESIGN CHOICE — Not writing any Lean code or Lean theorem statements.
- DESIGN CHOICE — Not constructing an `add.u32` instruction-level source bundle.
- DESIGN CHOICE — Not modeling any instruction other than the foundations for `add.u32` (mentions of `sub`, `mul`, etc. in Section 3 are source-list facts only, not models).
- DESIGN CHOICE — Not building a memory, state-space, or concurrency model for this unit.
- DESIGN CHOICE — Not resolving the register-chapter evidence gap (E-22) within this artifact.
- DESIGN CHOICE — Not approving Gate A; approval is a human decision outside this artifact.
- DESIGN CHOICE — Not promoting anything to `accepted/`.
