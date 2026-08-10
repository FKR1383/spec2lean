# PTX and.b16 Foundation Architecture v2 — DRAFT — NOT HUMAN APPROVED

## 1. Scope

- Bounded unit: `and.b16` for PTX ISA 9.3.
- This artifact is **Gate A architecture only** for unit-specific syntax/type/operational shape, state footprint, predication model, and candidate Lean proof families.
- No Lean code, proofs, or implementation details are introduced.

## 2. Official source facts

Primary source: `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` (PTX ISA 9.3), SHA-256 `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`.

- SOURCE FACT (SF-B1) — `and` section exists at anchor `logic-and-shift-instructions-and`, lines 14256-14289.
- SOURCE FACT (SF-B2) — Syntax is `and.type d, a, b;` with `.type = { .pred, .b16, .b32, .b64 };` (lines 14264-14266).
- SOURCE FACT (SF-B3) — Semantics text says `d = a & b;` (line 14273).
- SOURCE FACT (SF-B4) — Notes say operand size must match and operand types may differ; predicate registers are allowed (lines 14277-14278).
- SOURCE FACT (SF-B5) — PTX ISA Notes: introduced in version 1.0 (line 14280).
- SOURCE FACT (SF-B6) — Target ISA Notes: supported on all target architectures (line 14282).
- SOURCE FACT (SF-B7) — Predication intro: all instructions may be predicated; optional guard syntax `@p` / `@!p`; no guard means unconditional (lines 7547-7550, anchor `predicated-execution`).
- SOURCE FACT (SF-B8) — General PTX instruction form in section 9.2: operands `d,a,b,c` and optional guard; for result-producing instructions `d` is destination and `a,b,c` sources (lines 7526-7527, anchor `ptx-instructions`).
- SOURCE FACT (SF-B9) — General PTX instruction form note that some instructions have optional destination operand and `_` may replace it (lines 7534-7535, anchor `ptx-instructions`).
- SOURCE FACT (SF-B10) — Fundamental types table includes `.b16` under basic type Bits with 16-bit width (anchor `fundamental-types-fundamental-type-specifiers`, lines 3025-3029 and 3053-3055).
- SOURCE FACT (SF-B11) — Type compatibility rule: same-size rule with bit-size types compatible with any fundamental type of equal size (lines 3062-3066, anchor `fundamental-types`).
- SOURCE FACT (SF-B12) — Register state space is typed/untypeable, with register widths and non-addressability constraints (lines 2617-2627, anchor `register-state-space`).
- SOURCE FACT (SF-B13) — Predicate variables may only be declared in register state space (line 3755, anchor `variables`).
- SOURCE FACT (SF-B14) — Negative-search support: no literal `and.b16` token in this section beyond heading context in official artifact (search result in previous pass); only `.b32` examples are shown in this section’s `and` examples.

## 3. Proposed Lean architecture

- DESIGN CHOICE (D-B1) — Model `and.b16` as: optional guard, opcode `and`, explicit type `.b16`, destination `d`, source operands `a`,`b`.
- DESIGN CHOICE (D-B2) — Restrict bounded operand categories to **register references only** for `d,a,b` in this artifact.
- DESIGN CHOICE (D-B3) — Preserve explicit three-operand bounded shape `d,a,b` and do **not** require bit-bucket `_` support for `and.b16` in this bounded architecture.
- DESIGN CHOICE (D-B4) — `d` and sources must be register variables of compatible size with `.b16`’s 16-bit requirement; basic-type matching is not required per instruction notes.
- DESIGN CHOICE (D-B5) — Destination write semantics is bitwise-and of source values in same-width 16-bit untyped bit domain (`Bits16`-like), with no memory side effects.
- DESIGN CHOICE (D-B6) — Predication follows complete-guard semantics: execute only when guard is true (`true`/`p`/`¬p`); false guard leaves state unchanged.
- DESIGN CHOICE (D-B7) — Minimal state model includes register-state only: `.reg` registers + predicate registers mapping.
- DESIGN CHOICE (D-B8) — Instruction metadata records PTX introduction version and target coverage.

## 4. Fact-to-design mapping

| Source facts | Design consequences |
|---|---|
| SF-B2 | D-B1, D-B3 |
| SF-B3, SF-B4 | D-B4, D-B5 |
| SF-B7 | D-B6 |
| SF-B8 | D-B1 |
| SF-B10, SF-B11 | D-B4 |
| SF-B12, SF-B13 | D-B7 |
| SF-B5, SF-B6 | D-B8 |
| SF-B9 | OQ-B2, D-B3 (negative design decision) |

## 5. Dependency graph

- D-B1 and D-B6 depend on SF-B7.
- D-B2 and D-B4 depend on SF-B2, SF-B4, SF-B10, SF-B11.
- D-B3 depends on SF-B2 and SF-B8.
- D-B5 depends on SF-B3 and SF-B4.
- D-B7 depends on SF-B12 and SF-B13.
- D-B8 depends on SF-B5 and SF-B6.

## 6. Assumptions

- ASSUMPTION (A-B1) — The bounded form excludes immediate operands for both source positions (`a`,`b`) until direct and.b16 evidence is provided.
- ASSUMPTION (A-B2) — The bounded form does not adopt bit-bucket `_` destination support despite generic optional-destination mention, to keep commitments aligned with the explicit `and` syntax shown in-bounds.
- ASSUMPTION (A-B3) — No exceptional/error/abort behavior is modeled for this scalar instruction form.
- ASSUMPTION (A-B4) — 16-bit bitwise operation is interpreted over untyped 16-bit bit-vectors; concrete Lean representation is a Lean mapping decision.

## 7. Ambiguities / Open questions

- OPEN QUESTION (OQ-B1) — Whether source operand `a` can be an immediate (the explicit source-position imm is only evidenced for `.b32` examples and not for `.b16`).
- OPEN QUESTION (OQ-B2) — Whether `and.b16` is one of the instructions for which `_` destination is legal under the generic 9.2 optional-destination rule.
- OPEN QUESTION (OQ-B3) — Exact immediate typing/canonicalization if immediate sources are admitted for `.b16` in later bounded expansion.

## 8. Candidate theorem-obligation families

- PRF-1 (Determinism): for well-typed/validated instruction and state, execution relation yields at most one successor state.
- PRF-2 (Guard completion): execution occurs iff complete guard evaluates true; false guard leaves state unchanged.
- PRF-3 (Frame/locality): if executed with explicit register destination `d`, only `d` may change.
- PRF-4 (Result domain): executed destination result belongs to 16-bit value domain of `.b16`.
- PRF-5 (Bitwise fidelity): if executed, destination is `a & b` as specified in the semantic clause.
- PRF-6 (Version/target compliance): metadata records introduction >= 1.0 and target coverage = all architectures.

## 9. Evidence index

| ID | Section heading | Anchor | Lines | Source | Hash |
|---|---|---|---:|---|---|
| E-B1 | Logic and Shift Instructions: and | `logic-and-shift-instructions-and` | 14256-14289 | `ptx_isa_9.3.html` | e2095c4a |
| E-B2 | PTX Instructions | `ptx-instructions` | 7513-7536 | `ptx_isa_9.3.html` | e2095c4a |
| E-B3 | Predicated Execution | `predicated-execution` | 7537-7550 | `ptx_isa_9.3.html` | e2095c4a |
| E-B4 | Fundamental Types | `fundamental-types` | 3062-3066 | `ptx_isa_9.3.html` | e2095c4a |
| E-B5 | Fundamental Type Specifiers | `fundamental-types-fundamental-type-specifiers` | 3025-3061 | `ptx_isa_9.3.html` | e2095c4a |
| E-B6 | Register State Space | `register-state-space` | 2613-2627 | `ptx_isa_9.3.html` | e2095c4a |
| E-B7 | Variables | `variables` | 3755 | `ptx_isa_9.3.html` | e2095c4a |

## 10. Gate A review checklist

- [x] Scope is explicitly bounded to `and.b16`.
- [x] Source facts are separated from design assumptions.
- [x] Open questions are explicit and unresolved.
- [x] Fact-to-design mapping is present.
- [x] Evidence index includes document/anchor/lines/hash.
- [x] Candidate theorem-obligation families are listed.
- [x] No Lean code or proof text included.
