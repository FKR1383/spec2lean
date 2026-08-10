# PTX `or.b32` Foundation Architecture v3 — DRAFT (UNAPPROVED)

## 1) Scope

- DESIGN CHOICE (S-1): Architecture-only artifact for bounded formalization of PTX instruction unit `or.b32` under PTX ISA 9.3.
- DESIGN CHOICE (S-2): Covers instruction syntax/operands, predicate guarding, type-width constraints, state abstraction needed for single-step local execution.
- DESIGN CHOICE (S-3): Excludes parsing of full PTX modules, control-flow instructions, memory model, and runtime/thread scheduling.
- DESIGN CHOICE (S-4): No Lean code/theorems are introduced here; this artifact is for Gate A review only.

## 2) Official source facts

Evidence sources (official, 9.3):
- `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` (SHA-256 `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`)
- `documents/sources/nvidia/ptx/9.3/source-manifest.json`

### Source facts for `or` family and unit

- SF-OR-1 (status: direct): Section **9.7.8.2**, anchor `logic-and-shift-instructions-or`, lines 14290–14320: syntax is `or.type d, a, b;` with `.type = { .pred, .b16, .b32, .b64 };` description is bitwise OR; semantics `d = a | b;`; notes say operands must match in size but not necessarily type; PTX notes “Introduced in PTX ISA version 1.0”; target notes “Supported on all target architectures”; examples include `or.b32  mask mask,0x00010001` and `or.pred  p,q,r;`.
- SF-OR-2 (status: direct): Section **9.7.8**, anchor `logic-and-shift-instructions`, lines 14240–14243: logic/shift instructions are fundamentally untyped, bit-wise on operands of any type with the same size; `and`, `or`, `xor`, `not` also operate on predicates.

### Source facts for PTX instruction format and guarding

- SF-INST-1 (status: direct): Section **9.2**, anchor `ptx-instructions`, lines 7517–7524: optional guard `@p` in syntax; up to four operands forms, and for result instructions `d` is destination, `a,b,c` are sources.
- SF-INST-2 (status: direct): Section **9.2**, lines 7528–7535: some instructions have optional destination; `_` can replace a destination register as bit bucket.
- SF-INST-3 (status: direct): Section **9.3**, anchor `predicated-execution`, lines 7541–7550: predicate type `.pred`; all instructions have optional guard `@{!}p`; omitted guard means unguarded execution.
- SF-INST-4 (status: direct): Section **9.7**, anchor `instructions`, lines 8722–8723: “All PTX instructions may be predicated.” and optional guard omitted from syntax.
- SF-INST-5 (status: direct): Section **9.7.13.2**, anchor `control-flow-instructions-at`, lines 21834–21840: predicated execution semantics state threads with False guard “do nothing.”

### Source facts for types and state space

- SF-TYPE-1 (status: direct): Section **5.2.1**, anchor `fundamental-types`, lines 3021–3022 and table context 3037–3066: same type-size specifiers used for instruction typing; operand compatibility is checked; compatible types: same basic/same size, signed/unsigned same size, bit-size compatible with any fundamental same size.
- SF-TYPE-2 (status: direct): Same section lines 3053–3058 and 2617–2624: includes `.b32` and `.pred` fundamental kinds; registers are 8/16/32/64/128-bit scalar types and predicate registers are 1-bit.
- SF-STATE-1 (status: direct): Section **5.4**, anchor `variables`, lines 3751–3755: variable declaration names state space, type, name; predicates may only be declared in register state space.
- SF-STATE-2 (status: direct): Section **5.1.1**, anchor `register-state-space`, lines 2617–2624: `.reg` is fast storage and registers are not fully addressable.
- SF-STATE-3 (status: direct): Section **5.4.6**, anchor `parameterized-variable-names`, lines 3939–3944: `.reg .b32 %r<100>;` declares many registers.

## 3) Proposed Lean architecture (bounded to `or.b32`)

- D-1 — Instruction shape: `OrB32` has fields:
  - optional `guard : Option Guard` where `none | some pos(p) | some neg(p)`;
  - `dst : OrB32Dst` and `src1`, `src2 : OrB32Operand`.
- D-2 — Destination namespace: `OrB32Dst := RegisterRef | BitBucket`.
  - D-2 note: bit-bucket support is **candidate** (inherited from SF-INST-2, not explicitly enumerated for `or.b32` in SF-OR-1; see Open Question OQ-1).
- D-3 — Operand model: `OrB32Operand := RegisterRef | Immediate` (bounded to declared names/constants), source references must resolve in state to 32-bit values.
- D-4 — Type/width constraints (unit-specific): active variant is `b32`-suffixed, so destination type is `.b32` and all operands must be size-compatible at 32 bits.
  - D-4-COMPAT: allowing any compatible 32-bit fundamental type for sources is a design option only if derived by SF-TYPE-1 compatibility with bit-size `.b32`; this is out-of-scope for this unit to finalize by itself and may be enforced by shared unit-wide typing later.
- D-5 — State model for bounded execution: `State := RegFile × PredFile` (predicates separate by declaration restriction); no memory/thread/frame state in this bounded phase.
- D-6 — State typing discipline: register names are in `.reg` space; predicate names must be in `.pred` declarations (SF-STATE-1) to appear as predicate operands.
- D-7 — Guarded execution relation: `exec : State → OrB32 → ExecResult State` with outcomes
  - `executed` when guard is true and operands are well-typed/available;
  - `notExecuted` when complete guard is false;
  - `stuck` for malformed input not representable by bounded well-formedness relation.
- D-8 — Guard semantics:
  - no guard → true;
  - `@p` → value of predicate `p`;
  - `@!p` → negation of predicate `p`.
  - false guard behavior: `notExecuted` (no state update), consistent with SF-INST-5.
- D-9 — Metadata: record `(introduced = 1.0, target = all)` for this bounded unit only (from SF-OR-1).

## 4) Fact-to-design mapping

- SF-OR-1, SF-INST-1 → D-1, D-3, D-4
- SF-INST-2 → D-2
- SF-OR-1 → D-4 (unit suffix); SF-TYPE-1, SF-TYPE-2 → D-4, D-6
- SF-STATE-1, SF-STATE-2, SF-STATE-3 → D-5, D-6
- SF-INST-1, SF-INST-3, SF-INST-4, SF-INST-5 → D-7, D-8
- SF-OR-1 (notes/metadata) → D-9

## 5) Dependency graph

1. **State-space/type layer**: SF-TYPE-1, SF-TYPE-2, SF-STATE-1, SF-STATE-2, SF-STATE-3 → D-4, D-5, D-6.
2. **Instruction shape layer**: SF-INST-1 → D-1; SF-INST-2 → D-2.
3. **Predication layer**: SF-INST-3, SF-INST-4, SF-INST-5 → D-7, D-8.
4. **Execution layer**: SF-OR-1 + layer 1–3 deps → D-7.
5. **Metadata layer**: SF-OR-1 → D-9.

## 6) Assumptions

- ASS-1: The bounded architecture models only the named variant `or.b32`; other variants (e.g., `or.pred`, `or.b16`, `or.b64`) are out-of-scope unit splits.
- ASS-2: A non-Boolean predicate value model is not specified in this unit; bounded execution assumes 2-valued predicates for guard control.
- ASS-3: `stuck` is used only for malformed references; well-formed instruction artifacts are expected to reject these before single-step semantics.
- ASS-4 (non-sourced design assumption): No global memory or control-flow state is modeled for this unit; `or.b32` is treated as local compute-only in bounded scope.
- ASS-5: The no-guard/false-guard no-update behavior is inherited from general predication semantics, not restated in SF-OR-1.

## 7) Ambiguities

- AMB-1: Whether `_` is actually admissible for `or.b32` is unresolved from explicit per-instruction text (SF-INST-2 is generic).
- AMB-2: Exact immediate literal typing and canonical width inference for `or.b32 mask, mask, 0x00010001` is not explicit in SF-OR-1.
- AMB-3: Whether bounded architecture should normalize source operand compatibility for this unit to “exact `.b32` only” versus “any 32-bit compatible fundamental type” requires an explicit design decision in shared typing phase.
- AMB-4: Predicate values in other PTX contexts (possible undefined predicate states) are not specified in this bounded instruction section.

## 8) Open questions

- OQ-1: Confirm explicit canonical rule whether bit bucket `_` is allowed for `or.b32` specifically (not only by generic wording).
- OQ-2: Confirm literal typing for immediate operands in bounded examples (size derivation vs parser-literal kind).
- OQ-3: Decide whether source typing for `or.b32` should be minimal exact `.b32` or full same-size compatibility via SF-TYPE-1/SF-OR-2.
- OQ-4: Decide if `or.b32` execution should report additional failure modes (e.g., invalid/missing declaration) within `exec` or keep such inputs out of well-formed domain.

## 9) Candidate theorem-obligation families

### Validation obligations

- VAL-1: Well-formed shape: exactly one optional guard, one destination, two sources for `or.b32`.
- VAL-2: Guard is syntactically either absent or `@p`/`@!p` where `p` is a predicate reference.
- VAL-3: Destination is either `.reg` reference or `_` (if allowed by decision on OQ-1).
- VAL-4: Operands in `or.b32` are 32-bit-size-compatible (and, by AMB-3 decision, either strict `.b32`-only or compatibility-based).
- VAL-5: Unit metadata fields match SF-OR-1 intro/target note.

### Proof obligations (non-vacuous)

- PRF-1: Guard-totality — if complete guard is false, execution is `notExecuted` and state is unchanged.
- PRF-2: Determinism — for well-formed well-typed `or.b32`, `exec` is deterministic.
- PRF-3: Destination locality — successful execution updates only destination register (or no update if `_`).
- PRF-4: Bitwise result — for successful execution, destination bit pattern equals `a | b` at operand width.
- PRF-5: Version/target fidelity — metadata used by architecture matches SF-OR-1.

## 10) Evidence index

- `documents/sources/nvidia/ptx/9.3/source-manifest.json` (specification_version: 9.3)
- `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html`, lines:
  - 14290–14320 (`logic-and-shift-instructions-or`)
  - 14236–14243 (`logic-and-shift-instructions`)
  - 7513–7535 (`ptx-instructions`)
  - 7537–7541 (`predicated-execution`)
  - 8722–8723 (`instructions`)
  - 21834–21840 (`control-flow-instructions-at`)
  - 3007–3022, 3030–3066 (`fundamental-types`)
  - 2613–2624 (`register-state-space`)
  - 3751–3755 (`variables`)
  - 3939–3944 (`parameterized-variable-names`)
- Evidence status: all facts listed above are directly visible in cited lines unless marked “design assumption” (ASS/AMB/OQ).

## 11) Gate A review checklist draft

- [ ] Bounded scope is clearly limited to `or.b32`.
- [ ] Source facts, design choices, assumptions, ambiguities, and open questions are explicitly labeled.
- [ ] Each SOURCE FACT has section/anchor/line evidence and status.
- [ ] Proposed architecture separates syntax, typing, state, predication, execution relation, and metadata.
- [ ] Guard semantics cover absent guard, positive guard, negated guard, and false-guard no-op.
- [ ] Validation and proof obligations are stated and non-vacuous.
- [ ] No Lean code/theorems/axioms are introduced.
- [ ] Major semantic drift concerns are addressed (e.g., no admission of `.pred` as active type for `or.b32`).
- [ ] Open questions and ambiguities are explicit and unresolved.
- [ ] Artifact remains clearly draft/unapproved.
