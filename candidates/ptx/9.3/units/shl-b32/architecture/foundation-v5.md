# PTX `shl.b32` Foundation Architecture v5 — DRAFT (UNAPPROVED)

## 1) Scope

- **SCOPE-1:** Bounded architecture foundation for language construct `shl.b32` in PTX 9.3.
- **SCOPE-2:** Covers syntax/operands, typing/compatibility, declarations, predicate/state-space model, predication and conditional semantics, machine state abstraction, metadata, dependencies, and theorem-obligation families.
- **SCOPE-3:** **Excluded:** inter-instruction sequencing, control-flow graph, barriers/synchronization, memory model beyond `.reg` and `.pred`, exceptions, concurrency, and full numeric runtime representation details.
- **SCOPE-4:** Stage-only architecture artifact. No Lean code, proofs, or parser implementation.

## 2) Official source facts

- **Documents**:
  - `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` (SHA-256 `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`)
  - `documents/sources/nvidia/ptx/9.3/source-manifest.json` (SHA-256 `622e6ce0d3114a909a62726530955993b5f2b98d2f60e45ae1ceb429512208f2`)
  - `documents/sources/nvidia/ptx/9.3/SHA256SUMS` (SHA-256 `e02f4feadfce614282d3d4774ed21dd87985202d4ea9ad84ead60c688a6c0ecd`)

### Source-backed fact inventory

- **SF-SHL-1 (source-backed):** `logic-and-shift-instructions-shl` (anchor, lines 14697–14730): syntax is `shl.type d, a, b; .type = { .b16, .b32, .b32 }`; semantics `d = a << b`; notes state:
  - shift amounts `> N` are clamped to `N`;
  - destination and first source sizes match;
  - `b` is 32-bit regardless of type;
  - introduced in 1.0; supported on all architectures; example `shl.b32 q,a,2;`.
- **SF-INS-1 (source-backed):** `ptx-instructions` (anchor, lines 7513–7527, 7534–7535): instructions have optional guard predicate; up to four operands and destination/source role naming (`d` as destination for result-producing ops; `a,b,c` as sources); optional destination `_` is mentioned for some instructions.
- **SF-PRED-1 (source-backed):** `predicated-execution` (anchor, lines 7547–7550): predicate registers are `.pred`; syntax `@{!}p` optional; unguarded means unconditional.
- **SF-PRED-2 (source-backed):** `predicated-execution` + declaration context (lines 7541–7544): `.pred` registers may be declared (`.reg .pred p, q, r;`).
- **SF-PRED-3 (source-backed):** `control-flow-instructions-at` (anchor, lines 21828–21839): predicated execution described as “threads with a False guard predicate do nothing”.
- **SF-TYPE-1 (source-backed):** `fundamental-types` and its table (lines 3020–3065): PTX fundamental types include `.b16/.b32/.b64`; type checking uses operand/type compatibility by basic type+size; bit-size types are fundamental.
- **SF-REG-1 (source-backed):** `register-state-space` (lines 2617–2624): `.reg` is register state space; registers may be typed; scalar widths include 8/16/32/64/128; predicates are 1-bit; registers are not fully addressable.
- **SF-DECL-1 (source-backed):** `variables` (lines 3751–3755): every variable has state-space and type; predicates may only be declared in register space.
- **SF-DECL-2 (source-backed):** `parameterized-variable-names` (lines 3940–3944): examples of `.reg .b32` variable families.
- **SF-SUBWORD-1 (source-backed):** `restricted-use-of-sub-word-sizes` (lines 3074–3075): `.u8/.s8/.b8` restricted list; used only as a negative compatibility clue that `.b32` is not in that restricted list.
- **SF-GEN-1 (source-backed):** `instructions` (lines 8722–8723): all PTX instructions may be predicated; optional guard omitted from per-op syntax in section descriptions.

### Evidence status

All facts above are **directly** grounded in the cited sections/anchors from PTX 9.3 HTML (with line spans as indicated).

## 3) Proposed Lean architecture (design choices)

- **D1:** Define bounded instruction node for this unit as `shl` with fields `ty`, `guard`, `dst`, `srcA`, `srcB`.
- **D2:** Active architecture constrains `ty = .b32` for this bounded unit.
- **D3:** Operand arity/order fixed to 3 (`d, a, b`).
- **D4:** `dst` and `srcA` are treated as value-operands in the execution state domain; `dst` is an updatable storage location (not immediate) and `srcA` is read-only in this relation.
- **D5:** `srcB` is constrained to be a 32-bit valued operand and is a shift-count argument; exact source-form class (`register | immediate | constant-expression`) is left abstract (open input slot) due lack of explicit per-construct source-form proof.
- **D6:** Declared operands are validated against bounded declaration metadata with compatibility checks: `dst`/`srcA` size-match; `srcB` 32-bit value requirement.
- **D7:** Predication model:
  - no guard -> true;
  - `@p` -> value of predicate `p`;
  - `@!p` -> negation.
- **D8:** Execution relation is single-step with outcomes `{executed, skipped, stuck}`:
  - `executed` when guard true and validation succeeds;
  - `skipped` when guard false;
  - `stuck` when state/declaration preconditions missing.
- **D9:** In `executed`, resulting value for `dst` follows abstract `Shl` relation over bounded width 32: `dstVal = a << clamp(b,32)` with source-specified “unsigned 32-bit `b`” and clamp requirement; concrete bit-level semantics deferred to Lean mapping layer.
- **D10:** Core state model:
  - `regFile : name ↦ value` for value registers;
  - `predFile : predName ↦ Bool` for predicate state;
  - `declMeta : name ↦ declaration metadata` as optional typing support.
- **D11:** Execution side effect in `executed` is update to at most one destination register plus no predicate-file change; `skipped` is non-mutating in bounded model.
- **D12:** Metadata record: `{unit="shl.b32", introduced=1.0, target=all_architectures, specVersion=9.3}` for governance, non-semantic.

## 4) Fact-to-design mapping

- SF-SHL-1 → D1, D2, D3, D4, D5, D6, D9, D12
- SF-INS-1 → D1, D3, D7, D8
- SF-INS-1 (optional `_`) + SF-SHL-1 syntax → D4 constrained as **open question** for `_` in this unit
- SF-PRED-1 + SF-GEN-1 → D7, D8
- SF-PRED-3 → D8, D11 (as an assumption-backed interpretation)
- SF-PRED-2 + SF-DECL-1 → D7
- SF-TYPE-1 + SF-SUBWORD-1 + SF-REG-1 + SF-DECL-1/2 → D6, D10, D12

## 5) Dependency graph

- **Instruction grammar:** SF-SHL-1, SF-INS-1 → D1, D2, D3.
- **Typing/compatibility:** SF-SHL-1, SF-TYPE-1, SF-DECL-1, SF-SUBWORD-1 → D6.
- **Predication:** SF-PRED-1, SF-PRED-2, SF-GEN-1 → D7, D8.
- **No-op/skip interpretation:** SF-PRED-3 → D8/D11 (assumption-labeled).
- **State/model:** SF-REG-1, SF-DECL-1, SF-DECL-2 → D10.
- **Metadata:** SF-SHL-1/ PTX notes + manifest metadata → D12.

## 6) Register, value, and state foundations

- **RS-1:** Value storage is modeled as finite maps of declarations to runtime values in bounded context.
- **RS-2:** Register space is the only value storage space in scope (`.reg`), with scalar register widths including 32-bit; predicate storage modeled separately.
- **RS-3:** Predicates are 1-bit logical values and kept in `predFile`.
- **RS-4:** Registers are modeled as non-addressable storage names, consistent with PTX register-space description.
- **RS-5:** State equality for `skipped` is equality over all tracked components in this bounded model (`regFile`, `predFile`, and `declMeta` if present).

## 7) Operand architecture

- **OP-1:** Operand vector is exactly 3 positions.
- **OP-2:** `d` is destination role; `a,b` are source roles by PTX-instruction convention.
- **OP-3:** `d` and `a` are bounded by size compatibility constraints; they are not accepted as immediate form in this architecture (destination is always updatable location in state).
- **OP-4:** `srcB` is 32-bit counted by source text; source representation remains parameterized/abstract.
- **OP-5:** No memory address operands, vector masks, or non-scalar operand classes for this unit.

## 8) Predication architecture

- **P-1:** guard may be absent, `@p`, or `@!p`.
- **P-2:** guard evaluation uses predicate lookup plus negation for `@!p`.
- **P-3:** guard false transitions to `skipped` (no write). This matches the dedicated predicated execution “false does nothing” statement in the control-flow section by explicit design assumption, not as a direct specialization claim.
- **P-4:** predicate operands are constrained to declared `.pred` names.

## 9) Version and target representation

- **V-1:** unit metadata constants: `unit="shl.b32"`, `introduced=1.0`, `target="all architectures"`, `specVersion=9.3`.
- **V-2:** metadata is non-operational for this architecture stage.

## 10) Candidate theorem-obligation families

### Validation obligations

- **VAL-1:** Syntax/arity is exactly `shl.b32 d, a, b;` in bounded construction.
- **VAL-2:** `dst` and `srcA` satisfy bounded size compatibility.
- **VAL-3:** `srcB` satisfies 32-bit requirement.
- **VAL-4:** Guard target exists as declared `.pred` when present.
- **VAL-5:** Active-type metadata for this unit is `.b32` and `b32` type metadata is fixed.

### Semantic obligations

- **PRF-1:** For validated inputs, operational result (`executed/skipped/stuck`) is deterministic.
- **PRF-2:** Guard-true branch performs one-shot `executed` update; guard-false branch performs `skipped`.
- **PRF-3:** `executed` may update only destination register and preserves predicate state.
- **PRF-4:** Executed destination satisfies the `shl` relation with unsigned count interpretation and clamp-to-N behavior (`N=32`).
- **PRF-5:** `stuck` captures malformed declaration/typing preconditions (no PTX fault model asserted).

## 11) Assumptions, ambiguities, open questions

### Assumptions

- **ASS-1:** “False predicate do nothing” semantics for skip behavior is used as an interpretation for all predicated instructions, not only the control-flow `@` section where text appears.
- **ASS-2:** Destination is an updatable location in local `regFile` state; this supports `executed` write semantics but is not directly restated as source-level operand grammar for `shl`.
- **ASS-3:** Source/implementation will encode bounded 32-bit shift arithmetic via an abstract operator to avoid over-committing on wrap/truncation edge cases beyond source constraints.

### Ambiguities

- **AMB-1:** Whether `shl` specifically allows bit-bucket `_` destination remains unresolved (generic `_` note exists, but unit syntax line does not explicitly mention it).
- **AMB-2:** Exact source-form classes for `a`/`b` (register/immediate/constant-expression) are not fully specified in the `shl` section.
- **AMB-3:** Whether skip should freeze metadata bookkeeping fields (`declMeta`) or only runtime maps is unresolved at architecture scope.

### Open questions

- **OQ-1:** Can `_` destination be normatively admitted for `shl` in a narrower parse rule despite being absent in the local syntax line?
- **OQ-2:** Should `srcA` be constrained to declared register storage directly from PTX grammar, or remain a generic read source operand in this bounded formalization?
- **OQ-3:** Is additional precision needed for 32-bit width semantics for `shl` (e.g., wrap behavior) before semantic mapping?

## 12) Evidence index

| ID | Source | Anchor/section | Lines | Status |
|---|---|---|---:|---|
| E-SHL-1 | PTX HTML 9.3 | `logic-and-shift-instructions-shl` / Syntax/Semantics/Notes | 14697–14730 | read |
| E-INS-1 | PTX HTML 9.3 | `ptx-instructions` / PTX Instructions | 7513–7527 | read |
| E-INS-2 | PTX HTML 9.3 | `ptx-instructions` / Optional destination note | 7534–7535 | read |
| E-PRED-1 | PTX HTML 9.3 | `predicated-execution` / Predicated Execution | 7547–7550 | read |
| E-PRED-2 | PTX HTML 9.3 | `predicated-execution` / Pred predicate declaration | 7541–7544 | read |
| E-PRED-3 | PTX HTML 9.3 | `instructions` / all instructions predicated | 8722–8723 | read |
| E-PRED-4 | PTX HTML 9.3 | `control-flow-instructions-at` / false predicate behavior | 21828–21839 | read |
| E-TYPE-1 | PTX HTML 9.3 | `fundamental-types` | 3020–3065 | read |
| E-REG-1 | PTX HTML 9.3 | `register-state-space` | 2617–2624 | read |
| E-DECL-1 | PTX HTML 9.3 | `variables` | 3751–3755 | read |
| E-DECL-2 | PTX HTML 9.3 | `parameterized-variable-names` | 3940–3944 | read |
| E-SUBWORD-1 | PTX HTML 9.3 | `restricted-use-of-sub-word-sizes` | 3074–3075 | read |
| E-META-1 | source manifest | `documents/sources/nvidia/ptx/9.3/source-manifest.json` | lines 1–38 | read |
| E-HASH-1 | checksum | `documents/sources/nvidia/ptx/9.3/SHA256SUMS` | lines 1–2 | read |

- Source identity SHA summary: HTML `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`; manifest `622e6ce0d3114a909a62726530955993b5f2b98d2f60e45ae1ceb429512208f2`; sums `e02f4feadfce614282d3d4774ed21dd87985202d4ea9ad84ead60c688a6c0ecd`.

## 13) Gate A review checklist

- [ ] Artifact is explicitly marked DRAFT and non-approved.
- [ ] Scope is bounded to `shl.b32` and excludes out-of-scope execution subsystems.
- [ ] All claims are traceable to official-source anchor/line evidence or explicitly tagged assumptions.
- [ ] Source facts and design choices are separated.
- [ ] Assumptions, ambiguities, and open questions are explicitly listed.
- [ ] Architecture includes instruction syntax, operand roles, typing, state, predication, metadata, and theorem families.
- [ ] No source claim is inferred without explicit unsupported assumption tag.
- [ ] `_` destination support is not asserted unless source-backed.
- [ ] Shift semantics include only sourced constraints (left shift + clamp-to-N + unsigned count wording).
- [ ] Family-level `.b16/.b32/.b64` is bounded to active `.b32` for this run.
