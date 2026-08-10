# PTX xor.b16 Foundation Architecture v1 — DRAFT — NOT HUMAN APPROVED

## 1. Scope and run context

- Bound to the bounded unit **`xor.b16`** (PTX ISA 9.3) at syntax `xor.type d, a, b;` with `.type = .b16` (section 9.7.8.3).
- This artifact is **architecture only**: syntax, operand taxonomy, register/value/state model, predication model, version/target metadata, validation/obligation families, and dependencies.
- No Lean code, source bundle, or proofs are introduced.
- This is a **revision artifact** for an active run and is not to be considered human-approved.

## 2. Official source facts

Primary source: `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` (PTX ISA 9.3), SHA-256 `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`.

- SOURCE FACT (SF-1) — Section 9.7.8.3, “Logic and Shift Instructions: xor” (`logic-and-shift-instructions-xor`), line span 14324–14357, defines opcode shape `xor.type d, a, b;` and type alternatives `.pred`, `.b16`, `.b32`, `.b64` (lines 14332–14334).
- SOURCE FACT (SF-2) — Same section, line span 14338–14341, defines description/semantics for this opcode: bitwise XOR, `d = a ^ b;`.
- SOURCE FACT (SF-3) — Same section, lines 14345–14346, states same-size operands are required but not necessarily same type, and predicate types are allowed.
- SOURCE FACT (SF-4) — Same section, line 14348, PTX ISA note: introduced in PTX ISA version 1.0.
- SOURCE FACT (SF-5) — Same section, line 14350, Target ISA note: supported on all target architectures.
- SOURCE FACT (SF-6) — Same section, example span 14353–14354: `xor.b32 d,q,r;` and `xor.b16 d,x,0x0001;`.
- SOURCE FACT (SF-7) — Section 9.7.8 intro (`logic-and-shift-instructions`), lines 14240–14243: the family is fundamentally untyped at bit level and includes `and/or/xor/not` as predicate-capable.
- SOURCE FACT (SF-8) — Section 9.7 intro (`instructions`), lines 8722–8723: all PTX instructions may be predicated and optional guard is omitted in section syntax.
- SOURCE FACT (SF-9) — Section 9.3 (`predicated-execution`), lines 7547–7550: optional `@{!}p` guard predicate controls conditional execution; instructions without guard execute unconditionally.
- SOURCE FACT (SF-10) — Section 9.2 (`ptx-instructions`), lines 7517–7527 and 7534–7535: standard operand positions (`d`,`a`,`b`) for result-producing ops and optional bit-bucket `_` destination.
- SOURCE FACT (SF-11) — Section 5.2.1 (`fundamental-types`), lines 3019–3066: types are (basic type,size) and type-size specifiers are shared by declarations/typing.
- SOURCE FACT (SF-12) — Table 8 (`fundamental-types-fundamental-type-specifiers`), lines 3053–3058: `.b16` and `.pred` are formal specifiers.
- SOURCE FACT (SF-13) — Same section, lines 3022 and 3062–3066: instructions’ operands are checked for compatibility; bit-size types match any type of same size.
- SOURCE FACT (SF-14) — Section 5.1.1 (`register-state-space`), lines 2617–2624: `.reg` registers are fast storage, scalar widths include 16 bits, predicate registers are 1-bit.
- SOURCE FACT (SF-15) — Section 5.1.1 also says registers are not fully addressable and notable ABI/spill notes are present (2617–2631).
- SOURCE FACT (SF-16) — Section 5.4 (`variables`), lines 3753–3755: declarations name state space + type + name (+array etc.), and predicate variables may only be declared in register space.
- SOURCE FACT (SF-17) — Section 5.4.6 (`parameterized-variable-names`), lines 3940–3947: parameterized register naming may be used across fundamental types and state spaces (including register families).
- SOURCE FACT (SF-18) — Section 5.2.2 (`restricted-use-of-sub-word-sizes`), lines 3074–3076: only `.u8/.s8/.b8` are restricted; no `.b16` restriction is listed there.
- SOURCE FACT (SF-19) — Literal search in the official source finds exactly one `xor.b16` occurrence at line 14354 in this unit section; `@p xor` appears zero times.
- SOURCE FACT (SF-20) — Literal search in the same source also shows `redux.sync.xor.b32 dst, src, mask;` (line 23754), a different instruction family, not the `xor` logic opcode section.

## 3. Proposed Lean architecture (design delta from shared logic/shift foundations)

- DESIGN CHOICE (D-1) — Instruction node `XorB16`: optional guard (`none | pred p | not pred p`), opcode `xor`, type `.b16`, destination operand, and two source operands `(a, b)`.
- DESIGN CHOICE (D-2) — Operand categories for bounded form: destination may be a register or `_`; source `a` may be register; source `b` may be register or immediate (supported by `xor.b16 ... 0x0001`).
- DESIGN CHOICE (D-3) — Type/width representation: fundamental type is `(basic type, width)`; `.b16` is modeled as 16-bit bits-untyped.
- DESIGN CHOICE (D-4) — Register/value representation: registers are by name and typed by fundamental type; values for `.b16` are 16-bit bit-pattern values.
- DESIGN CHOICE (D-5) — State shape: bounded machine state is `(regFile, predFile)` over registers and predicate registers only.
- DESIGN CHOICE (D-6) — Execution result shape: at minimum (`executed state`, `notExecuted state`), where `executed` performs the destination write candidate described by D-7, and `notExecuted` leaves state unchanged.
- DESIGN CHOICE (D-7) — Destination-update rule (candidate): for regular destination register, write the bitwise XOR of resolved source values; for `_`, discard the result.
- DESIGN CHOICE (D-8) — Predication interpretation: execute iff complete guard holds (`true` if absent, `p` for `@p`, `¬p` for `@!p`); false guard yields no state update by architectural design choice (pending approval, see OQ-1).
- DESIGN CHOICE (D-9) — Version/target metadata for this bounded unit: introduced-in = PTX ISA 1.0; target set = all architectures.
- DESIGN CHOICE (D-10) — Traceability metadata is stored per claim as `(document, version, section heading, anchor, line span, SHA-256)`.

## 4. Fact-to-design mapping

- SF-1, SF-10 -> D-1, D-2
- SF-2 -> D-7
- SF-3 -> D-2, D-3, VAL-2
- SF-4, SF-5 -> D-9, VAL-5, VAL-6
- SF-6 -> D-2, OQ-2
- SF-7 -> D-4, D-3
- SF-8, SF-9, SF-10 -> D-8
- SF-11, SF-12, SF-13 -> D-3, D-4
- SF-14, SF-15, SF-16, SF-17 -> D-4, D-5
- SF-18, SF-19, SF-20 -> OQ and negative-evidence labels

## 5. Dependency graph

- Type/width and operand typing (D-3, VAL-2) depends on SF-3, SF-11, SF-12, SF-13.
- Instruction representation and predication (D-1, D-8) depends on SF-1, SF-8, SF-9, SF-10.
- Operand categories (D-2) depends on SF-1, SF-6, SF-10.
- Register/value/state foundations (D-4, D-5) depends on SF-11, SF-12, SF-14, SF-15, SF-16.
- Version/target metadata (D-9, VAL-5, VAL-6) depends on SF-4, SF-5.
- Cross-instruction exclusions and negatives (OQ-2/OQ-3) depends on SF-19, SF-20.

## 6. Assumptions

- ASSUMPTION (A-1) — HTML source is authoritative for this run; PDF source in manifest is not read.
- ASSUMPTION (A-2) — Instruction-local state transition over `(regFile, predFile)` is sufficient for this bounded unit.
- ASSUMPTION (A-3) — A false complete guard corresponds to “no state update.”
- ASSUMPTION (A-4) — `.b16` may be represented as a fixed 16-bit value domain and predicate values as a 2-valued domain in Lean.
- ASSUMPTION (A-5) — No explicit error/exception behavior for bounded `xor.b16` is modeled (bounded architecture choice).

## 7. Open questions

- OPEN QUESTION (OQ-1) — Whether `xor.b16` source `a` can be an immediate constant is not directly shown in section examples; only source `b` immediate is shown (`xor.b16 d,x,0x0001`).
- OPEN QUESTION (OQ-2) — Whether `d` may use bit-bucket `_` for this exact bounded form is supported by generic PTX syntax, but no `xor.b16`-specific example was read.
- OPEN QUESTION (OQ-3) — Exact immediate-typing/casting policy for `xor.b16` is unresolved (how immediate width is constrained to 16 bits).

## 8. Candidate theorem-obligation families

Validation obligations (definitional/pre-execution checks):

- VAL-1 — `.b16` is a valid known type specifier for the `xor` family (SF-1, SF-12).
- VAL-2 — Operand shape: exactly 2 sources + one destination and optional guard consistent with `d,a,b` format (SF-1, SF-10).
- VAL-3 — Operand-size typing: operands are 16-bit compatible under SF-3 and compatibility rule (SF-3, SF-11, SF-13).
- VAL-4 — If a guard is present, it references a declared predicate in register state (SF-9, SF-16).
- VAL-5 — `_` destination (if adopted) is structurally well-typed per generic optional-destination rule (SF-10).
- VAL-6 — Version and target metadata match official notes (SF-4, SF-5).

Candidate semantic theorem families (staged for later semantics phase):

- PRF-1 — Determinism of the one-step execution relation.
- PRF-2 — Correct XOR write: executed state writes value equal to `a ^ b` for register sources (SF-2).
- PRF-3 — Guard-behavior equivalence: execute iff complete guard evaluates true, including `@p` and `@!p`.
- PRF-4 — Guard-false frame: state unchanged when complete guard is false.
- PRF-5 — Destination locality: only `d` may change on write case; all other registers unchanged.
- PRF-6 — Result-domain membership in 16-bit `.b16` domain on successful execution.

## 9. Evidence index

- E-1 — `documents/sources/nvidia/ptx/9.3/source-manifest.json` (source identity, run metadata).
- E-2 — `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html`, anchor `logic-and-shift-instructions-xor`, lines 14324–14357.
- E-3 — same source, same section lines 14332–14334 (`.type` syntax includes `.b16`).
- E-4 — same source, same section lines 14338–14346 (description/notes).
- E-5 — same source, same section lines 14348–14350 (ISA/target notes).
- E-6 — same source, same section lines 14353–14354 (examples).
- E-7 — same source, same section 14240–14243 (`logic-and-shift-instructions`).
- E-8 — same source, anchor `instructions`, lines 8718–8723.
- E-9 — same source, anchor `predicated-execution`, lines 7537–7550.
- E-10 — same source, anchor `ptx-instructions`, lines 7517–7536.
- E-11 — same source, anchor `fundamental-types`, lines 3019–3066.
- E-12 — same source, anchor `fundamental-types-fundamental-type-specifiers`, lines 3053–3058.
- E-13 — same source, anchor `register-state-space`, lines 2613–2631.
- E-14 — same source, anchor `variables`, lines 3741–3755.
- E-15 — same source, anchor `restricted-use-of-sub-word-sizes`, lines 3070–3076.
- E-16 — `grep` evidence: `xor.b16` occurs at line 14354; `@p xor` zero matches; `redux.sync.xor.b32` at 23754.

## 10. Gate A review checklist

- [ ] Scope is bounded to instruction form `xor.b16` only.
- [ ] Source facts are separated from DESIGN CHOICE / ASSUMPTION / OPEN QUESTION labels.
- [ ] Every source statement includes anchor/lines/source hash traceability in Section 9.
- [ ] Predication/guard model is uniform across absent guard, `@p`, and `@!p`.
- [ ] Operand typing and state shape are minimal and instruction-local.
- [ ] Validation and theorem obligations are listed separately and are non-vacuous.
- [ ] `redux.sync.xor.b32` is excluded as separate instruction family.
- [ ] No Lean code or proofs introduced in this stage.
