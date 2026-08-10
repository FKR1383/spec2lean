# PTX 9.3 `or.b32` Foundation Architecture v3

## 1) Scope
- Bounded architecture for **formalizing one instruction unit**: `or.b32`.
- Focus is only on a single-instruction, single-thread/state transition.
- Excludes: whole-program execution, threading model, scheduling, barriers/synchronization, memory ordering beyond what is needed for one ALU instruction, and ABI/module linkage.

## 2) Official source facts
| ID | Document identity | Spec version | Section heading | Anchor | Lines | Evidence (quoted/paraphrased) | Status |
|---|---|---:|---|---|---:|---|---|
| SF-1 | `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` | 9.3 | Logic and Shift Instructions: `or` | `logic-and-shift-instructions-or` | 14290–14323 | Syntax `or.type d, a, b;`, `.type = { .pred, .b16, .b32, .b64 }`; semantics `d = a | b`; note “The size of the operands must match, but not necessarily the type.”; note “Allowed types include predicate registers.”; notes “Supported on all target architectures.” and “Introduced in PTX ISA version 1.0.”; examples include `or.b32  mask, mask,0x00010001` and `or.pred  p,q,r`. | Official HTML |
| SF-2 | `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` | 9.3 | PTX Instructions | `ptx-instructions` | 7513–7536 | Instructions use optional guard predicate form `@p`; may have 0–4 operands; for result instructions, `d` is destination and `a,b,c` are source operands; destination may be omitted via `_` bit-bucket for some instructions. | Official HTML |
| SF-3 | `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` | 9.3 | Predicated Execution | `predicated-execution` | 7537–7550 | “All instructions have an optional guard predicate ... controls conditional execution”; syntax `@{!}p`; instructions without guard execute unconditionally. | Official HTML |
| SF-4 | `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` | 9.3 | Predicated Execution examples | `predicated-execution` | 7561–7570 | Example `@p add.s32 j, j, 1;` demonstrates conditional execution semantics in practice. | Official HTML |
| SF-5 | `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` | 9.3 | Fundamental Types | `fundamental-types` | 3019–3023, 3062–3066 | Fundamental type combines basic type and size; register vars are of fundamental type; operands checked for compatibility; bit-size types same-size compatible with other types; signed/unsigned compatible same size. | Official HTML |
| SF-6 | `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` | 9.3 | Register State Space | `register-state-space` | 2617–2627 | Registers are in `.reg`; scalar widths include 8/16/32/64/128; predicate regs are 1-bit; registers not fully addressable. | Official HTML |
| SF-7 | `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` | 9.3 | Variable Declarations | `variable-declarations` | 3751–3756 | Variables live in a state space, have type, name; predicate variables may only be in register space. | Official HTML |
| SF-8 | `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` | 9.3 | Operand Type Information | `operand-type-information` | 5320–5325 | Every operand has known type; must be compatible with instruction type; no automatic conversion except compatible operands are “silently cast” to instruction type. | Official HTML |
| SF-9 | `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` | 9.3 | Source Operands | `source-operands` | 5331–5334 | PTX describes load-store machine; ALU source operands “must all be in variables declared in `.reg` register state space.” | Official HTML |
| SF-10 | `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` | 9.3 | Integer Constants | `integer-constants` | 2078–2083 | Integer constants are 64-bit `.s64`/`.u64`, and when used in instructions are converted to the appropriate size based on data/instruction type. | Official HTML |

## 3) Proposed Lean architecture
### D-1 Unit-level instruction syntax
- Define a constructor for exactly one unit-level constructor:
  - `OrB32` with fields:
    - `guard : Guard` where `Guard := none | pred p false
    | pred p true` (the negated/nonnull predicate case comes from `@{!}p`)
    - `dest : OrDest` where `OrDest := reg RegRef | bucket` (`_`)
    - `src1 : OrSource`
    - `src2 : OrSource`
- `RegRef` is a register identifier local to this unit.
- Source of opcode is fixed to `.b32`.
- Grounding: SF-1, SF-2, SF-3.

### D-2 Operand categories
- `OrSource` includes:
  1. `srcReg : RegRef` (normative for ALU sources),
  2. `srcImm : IntConst` (supported when present in `or.b32` syntax/example).
- `IntConst` is interpreted using PTX integer literal/typing rules before instruction typing.
- Grounding: SF-1 example (`...0x00010001`), SF-9, SF-10.

### D-3 Type model for this bounded unit
- Keep a dedicated type tag for unit family:
  - `typeTag := .b32` for instruction class.
- Runtime value model:
  - bit-vector of width 32 for bitwise compute paths,
  - predicate values as 1-bit logical values at register-file layer.
- Compatibility for `or.b32` checking:
  - destination/source operands must be size-compatible by width for this unit,
  - allow compatible conversion when integer/bit compatible as per SF-8/SF-5, but the bounded execution model only instantiates `.b32` destination.
- Grounding: SF-1, SF-5, SF-8.

### D-4 Machine state model
- `OrState` contains only register-file components needed for unit:
  - `regs : Map RegRef B32Val` for non-predicate general registers used by this instruction,
  - `preds : Map PredRef Bool` for predicate guards.
- No addressable/shared/global memory model is included (not required for `or.b32` semantics).
- Grounding: SF-6, SF-7, SF-2.

### D-5 Predication semantics
- Define guard evaluation:
  - `none` → enabled,
  - `pred p false` → value of `p`,
  - `pred p true` → logical negation of `p`.
- If guard false, no destination write is performed (state is unchanged in this bounded model).
- This is marked as an architectural assumption because PTX gives conditional execution wording but not an explicit transition axiom for every instruction.
- Grounding: SF-3, SF-4, SF-2.

### D-6 Transition relation
- `ExecOrB32 : OrState → OrB32 → OrState` (partial relation via precondition in proposition form).
- Well-formedness conditions for execution case:
  1. Source/destination operands are accepted by bounded typing rules (SF-1/5/8/9),
  2. Operand values are read (`srcReg` from state; `srcImm` by conversion at use from SF-10),
  3. Guard evaluated (D-5),
  4. If enabled, write `d := src1 OR src2` using 32-bit bitwise OR; if `dest = bucket`, no writes.
- No explicit `Error`/trap/exception constructor is introduced because this is not stated for the bounded `or` behavior in sourced text.
- Grounding: SF-1, SF-2, SF-3, SF-5, SF-8, SF-10.

### D-7 Version/target metadata
- Record per instruction facts:
  - `introduced_in = 1.0`,
  - `supported_all_targets = true`.
- Grounding: SF-1.

## 4) Fact-to-design mapping
| Source fact | Design decisions |
|---|---|
| SF-1 | D-1, D-2 (opcode/format), D-3 (32-bit bounded instantiation), D-6 (semantics), D-7 |
| SF-2 | D-1, D-2, D-4, D-6 |
| SF-3 | D-1, D-5, D-6 |
| SF-4 | D-5 |
| SF-5 | D-2, D-3 |
| SF-6 | D-4 |
| SF-7 | D-4, D-2 |
| SF-8 | D-2, D-3, D-6 |
| SF-9 | D-2 (as default ALU source rule), D-6 (register-read path) |
| SF-10 | D-2, D-6 (immediate conversion path) |

## 5) Dependency graph
- **D-1 instruction shape** depends on D-2 and D-3 and SF-2.
- **D-2 operand typing** depends on SF-9 (ALU register rule) and SF-10 (literal conversion) and D-3.
- **D-3 typing/widening** depends on SF-5 and SF-8.
- **D-4 state** depends on SF-6 and SF-7.
- **D-5 guard** depends on D-1 and D-4.
- **D-6 transition** depends on D-1, D-2, D-3, D-4, and D-5.
- **D-7 metadata** is independent except for section reference.

## 6) Assumptions
- **A-1**: In bounded transition, guard-false implies no destination update and no other modeled state update.
- **A-2**: This unit excludes full-program error/exception behavior; semantics is defined only for well-typed/decodable `or.b32` forms.
- **A-3**: Immediate operands are accepted for `or.b32` in this bounded syntax only when the literal is converted to instruction type at use, with per-instruction operand admissibility carried by the constructor and explicit parser/type checks.

## 7) Ambiguities
- **AM-1**: `source-operands` states ALU sources must be `.reg` variables, while the `or` section example shows immediate in an ALU-3-operand form. The run resolves this by keeping register-form as normative and treating immediate as a unit-specific source variant guarded by additional type/parse checks.
- **AM-2**: PTX states “controls conditional execution” but does not provide an explicit state-update axiom for every false-guard case in these sections.
- **AM-3**: Instruction-family scope (`.pred/.b16/.b64` appear in SF-1), but this artifact targets only the bounded unit `or.b32`.

## 8) Open questions
- **OQ-1**: Is there an explicit normative rule elsewhere in PTX 9.3 that formalizes the exact false-guard state relation for all predicated instructions (including register side effects)?
- **OQ-2**: Is immediate-form ALU usage generally governed by a global parsing/typing clause not included in the cited instruction sections, and should that be incorporated in this bounded architecture as a required shared component?
- **OQ-3**: Should this architecture be refactored into a shared family-level module (`or` family polymorphic in type) in a later run, or remain bounded to `or.b32` here?

## 9) Candidate theorem-obligation families
- **TF-1 (Determinism under well-formedness):** For fixed state and a well-formed `or.b32`, execution result is unique.
- **TF-2 (Guard semantics):** Guard evaluation follows `none`/`@p`/`@!p` and matches enabled-vs-disabled behavior.
- **TF-3 (Operand-size compatibility):** Execution is admissible only when source/destination operand widths/types satisfy size compatibility for `.b32`.
- **TF-4 (Result relation):** When enabled, destination update equals bitwise OR of source values at 32-bit width.
- **TF-5 (Bit bucket):** `dest = _` preserves all registers and predicates.
- **TF-6 (Single-result update):** On enabled execution with register destination, only destination register changes.

## 10) Evidence index
- `documents/sources/nvidia/ptx/9.3/source-manifest.json`.
- `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` SHA-256 `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`.
- Anchors used: `logic-and-shift-instructions-or`, `ptx-instructions`, `predicated-execution`, `fundamental-types`, `register-state-space`, `variable-declarations`, `operand-type-information`, `source-operands`, `integer-constants`.

## 11) Gate A review checklist
- [ ] Scope is explicitly bounded to `or.b32` and does not model unsupported semantics outside the unit.
- [ ] Every source claim is tied to an explicit anchor and line span in PTX 9.3.
- [ ] All assumptions/ambiguities/open questions are explicitly labeled.
- [ ] Operand/source typing and register-state assumptions are derived from cited text and do not rely on unsupported behavior.
- [ ] No unsupported error/outcome branch is introduced in the transition relation.
- [ ] Immediate support is either justified or constrained by explicit assumptions and parser typing.
- [ ] Theorem obligation families are non-vacuous and statement-level.
- [ ] No gate is approved in this artifact.
