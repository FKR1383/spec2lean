# PTX and.b16 Foundation Architecture v1 — DRAFT — NOT HUMAN APPROVED

## 1. Scope

- Bounded unit: `and.b16` for PTX ISA 9.3.
- This artifact is **architecture-only** for Gate A: instruction shape, operands, typing constraints, predication, minimal state, and validation/proof families.
- It is a delta specialized from `and` family facts (`and.b16` shares opcode and family behavior with `and.b32`, but this artifact scopes only the `.b16` instruction form and its immediate obligations).
- No Lean formalization, semantics proof scripts, or executable implementation are included.

## 2. Official source facts

Primary source: `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` (PTX ISA version 9.3, SHA-256 `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`).

- SOURCE FACT (SF-B1) — Instruction-family section exists at anchor `logic-and-shift-instructions-and`, line 14256.
- SOURCE FACT (SF-B2) — The `and` syntax is `and.type d, a, b;` with `.type = { .pred, .b16, .b32, .b64 }` (lines 14262-14266).
- SOURCE FACT (SF-B3) — `and` description: “Bitwise AND.” and “Compute the bit-wise and operation for the bits in `a` and `b`.” (lines 14261, 14270).
- SOURCE FACT (SF-B4) — `and` semantics uses `d = a & b;` (line 14273).
- SOURCE FACT (SF-B5) — Notes: “The size of the operands must match, but not necessarily the type.” and “Allowed types include predicate registers.” (lines 14277-14278).
- SOURCE FACT (SF-B6) — PTX ISA Notes: introduced in PTX ISA version 1.0 (line 14280).
- SOURCE FACT (SF-B7) — Target ISA Notes: supported on all target architectures (line 14282).
- SOURCE FACT (SF-B8) — Family intro (anchor `logic-and-shift-instructions`): logic/shift instructions are fundamentally untyped bit-wise ops and `and/or/xor/not` also operate on predicates (lines 14240-14243).
- SOURCE FACT (SF-B9) — Instruction descriptions and operands: PTX instructions generally have zero to four operands plus optional guard prefix `@` (lines 7517-7518, 7518 in anchor `ptx-instructions`).
- SOURCE FACT (SF-B10) — In 9.2 operand terminology: destination is `d`, sources are `a`, `b`, `c`; bit-bucket `_` may be used for optional destination instructions (lines 7526-7535, anchor `ptx-instructions`).
- SOURCE FACT (SF-B11) — Predicated execution: all instructions may be predicated; predicate register variables use `.pred`; optional guard syntax is `@p` or `@!p`; no guard means unconditional execution (lines 7547-7550, anchor `predicated-execution`).
- SOURCE FACT (SF-B12) — Fundamental types: `.b16` is a bit-size fundamental type, and section 5.2.1 gives size/basic-type typing model (lines 3019-3026 and 3053-3055, anchors `fundamental-types` and `fundamental-types-fundamental-type-specifiers`).
- SOURCE FACT (SF-B13) — Compatibility rule: same-size types can be used together; bit-size types are compatible with any fundamental type of same size (lines 3062-3066, anchor `fundamental-types`).
- SOURCE FACT (SF-B14) — Register state space is `.reg`, registers are typed and untyped, scalar widths include 8/16/32/64/128, and registers are not fully addressable (lines 2617-2627, anchor `register-state-space`).
- SOURCE FACT (SF-B15) — Predicate variables may only be declared in register state space (line 3755, anchor `variables`).

Negative-search evidence used as boundaries (same source, same run):
- SOURCE FACT (SF-B16) — Literal search for `and.b16` in this source returned zero matches (searched all text for `and.b16`).
- SOURCE FACT (SF-B17) — Literal search for `and.b32` returns matches for instruction `.b32` examples and unrelated instructions containing the token `.and.b32` in section names (`lop3`, `multimem`, `red`), so those are not direct `.b16` evidence.

## 3. Proposed Lean architecture

- DESIGN CHOICE (D-B1) — Model `and.b16` as: optional guard, opcode `and`, type `.b16`, destination `d`, source operands `a`,`b`.
- DESIGN CHOICE (D-B2) — Operand categories: register source/ destination with typed names, plus optional constant-immediate source(s).
- DESIGN CHOICE (D-B3) — Restrict source domain for bounded unit to `and`-family semantics only: three-operand form `d,a,b` and one-bit predicate guard.
- DESIGN CHOICE (D-B4) — Use a `Bits16`-like untyped 16-bit value domain for `.b16` values (not signed/unsigned arithmetic domain).
- DESIGN CHOICE (D-B5) — Minimal machine state includes at least: register file (including `.pred`-typed predicate registers) and a mapping from names to typed values.
- DESIGN CHOICE (D-B6) — Operand-size/type conformance is enforced by validation, based on family note “size must match, not necessarily type” and general compatibility rule.
- DESIGN CHOICE (D-B7) — Execution relation is conditional on complete guard; false guard yields unchanged state; true guard performs destination update.
- DESIGN CHOICE (D-B8) — No memory/special-register side effects are required in this bounded architecture.
- DESIGN CHOICE (D-B9) — Version/target metadata for bounded form: introduced-in=1.0, target=all architectures.

### Proposed outcome model

- DESIGN CHOICE (D-B10) — Execution outcome is relation-based with at least:
  - `executed`: destination updated with bitwise-and result, and
  - `guardFalse`: state unchanged.

## 4. Fact-to-design mapping

| Source facts | Design consequences |
|---|---|
| SF-B2 | D-B1 |
| SF-B5, SF-B8, SF-B13, SF-B12 | D-B2, D-B6 |
| SF-B4 | D-B1, D-B10 |
| SF-B11 | D-B7 |
| SF-B3, SF-B4 | D-B10 |
| SF-B14, SF-B15 | D-B5 |
| SF-B6, SF-B7 | D-B9 |
| SF-B9, SF-B10 | D-B3 |

## 5. Dependency graph

- D-B1 depends on SF-B2 and SF-B3.
- D-B2 depends on SF-B9, SF-B10, SF-B12, SF-B15.
- D-B4 depends on SF-B12, SF-B8, SF-B14.
- D-B6 depends on SF-B5, SF-B13.
- D-B7 depends on SF-B11.
- D-B10 depends on SF-B4 and SF-B11.

## 6. Assumptions

- ASSUMPTION (A-B1) — The `.pred` variant and `.b64` variant of `and` are out-of-scope; this artifact covers only `.b16` form.
- ASSUMPTION (A-B2) — `@`-guarded `and.b16` is applicable by global PTX predication rule despite no `and.b16`-specific textual example being present.
- ASSUMPTION (A-B3) — No exceptional error behavior for the bounded form is modeled here; no error/trap language appears in the instruction block.

## 7. Ambiguities / Open questions

- OPEN QUESTION (OQ-B1) — Whether source operand `a` may be an immediate in `and.b16` (SF-B2 gives family syntax; examples for this family in SF-B5/B16 do not show this).
- OPEN QUESTION (OQ-B2) — Whether bit-bucket `_` destination is legal for `and.b16`; SF-B10 allows bit bucket generally, while SF-B2 has no `and`-specific `_` example.
- OPEN QUESTION (OQ-B3) — Whether immediate typing for `.b16` in `and` follows family size compatibility for all immediate forms, or has additional canonicalization.

## 8. Candidate theorem-obligation families

- PRF-1 (Determinism): for well-typed state + instruction, `and.b16` execution relation yields at most one successor state.
- PRF-2 (Guard-completion): execution occurs iff guard evaluates true for no guard / `@p` / `@!p` cases.
- PRF-3 (Frame/no-alias): only destination register may change when destination is explicit register (non-`_`).
- PRF-4 (Bit-bucket discard): if `_` is adopted as destination form and instruction executes, register state is unchanged.
- PRF-5 (Result type): computed written result is a 16-bit value for `.b16`.
- PRF-6 (Bitwise fidelity): executed result satisfies source semantics `d = a & b;` over 16-bit bitwise domain.
- PRF-7 (Version/target compliance): model metadata for form matches introduction/version and target notes.

## 9. Evidence index

| ID | Section heading | Anchor | Lines | Source | Hash |
|---|---|---|---:|---|---|
| E-B1 | Logic and Shift Instructions: and | `logic-and-shift-instructions-and` | 14256-14289 | `ptx_isa_9.3.html` | e2095c4a |
| E-B2 | Logic and Shift Instructions | `logic-and-shift-instructions` | 14236-14255 | `ptx_isa_9.3.html` | e2095c4a |
| E-B3 | PTX Instructions | `ptx-instructions` | 7513-7536 | `ptx_isa_9.3.html` | e2095c4a |
| E-B4 | Predicated Execution | `predicated-execution` | 7537-7550 | `ptx_isa_9.3.html` | e2095c4a |
| E-B5 | Fundamental Types | `fundamental-types` | 3015-3068 | `ptx_isa_9.3.html` | e2095c4a |
| E-B6 | Fundamental Type Specifiers table | `fundamental-types-fundamental-type-specifiers` | 3025-3061 | `ptx_isa_9.3.html` | e2095c4a |
| E-B7 | Register State Space | `register-state-space` | 2613-2631 | `ptx_isa_9.3.html` | e2095c4a |
| E-B8 | Variables | `variables` | 3741-3755 | `ptx_isa_9.3.html` | e2095c4a |
| E-B9 | Search result `and.b16` | (no anchor) | n/a | `ptx_isa_9.3.html` | e2095c4a |

## 10. Fact-to-design mapping / checklist section

- Design-to-evidence traceability: each `SOURCE FACT` above is linked in Section 9; each `DESIGN CHOICE` references at least one source fact.
- Gate A checklist:
  - [x] Scope is bounded to `and.b16`.
  - [x] Source facts are separated from design assumptions.
  - [x] Ambiguities are explicit as OPEN QUESTION.
  - [x] Traceability index is present.
  - [x] No Lean code or proof text is introduced in this artifact.
