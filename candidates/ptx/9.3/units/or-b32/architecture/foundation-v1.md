# PTX 9.3 `or.b32` Foundation Architecture v1

## Scope
Bounded to language-wide foundations required for formalizing the PTX instruction `or.b32` as a single-instruction semantic relation in Lean. This artifact does not define LLVM/PTX program execution, memory model, concurrency, or full PTX front-end parsing.

## Official source facts
Source: `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` (SHA-256 `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`), PTX ISA 9.3.

| ID | Section heading | Anchor | Lines | Evidence | Status |
|---|---|---|---:|---|---|
| SF-1 | 9.7.8.2. Logic and Shift Instructions: or | `logic-and-shift-instructions-or` | 14290-14323 | `or.type d, a, b;` with `.type={.pred,.b16,.b32,.b64}`, description “bit-wise or”, semantics `d = a | b`, notes “The size of the operands must match, but not necessarily the type.” and “Allowed types include predicate registers.”, PTX ISA notes “Introduced in PTX ISA version 1.0.”, target notes “Supported on all target architectures.”, examples include `or.b32 mask, mask,0x00010001` and `or.pred p,q,r` | Official text | 
| SF-2 | PTX Instructions | `ptx-instructions` | 7513-7536 | Instructions have from 0–4 operands and optional guard predicate (`@p` form); `@p opcode d,a,b,c;` style; `d` is destination for resultful instructions; source operands are `a`,`b`,`c`; destination can be omitted using bit bucket `_`. | Official text |
| SF-3 | Predicated Execution | `predicated-execution` | 7537-7550 | Predicate registers are virtual with `.pred`; all instructions have optional guard predicate; syntax prefix `@{!}p`; instructions without guard execute unconditionally. | Official text |
| SF-4 | 9.3 Predication examples | `predicated-execution` | 7553-7572 | Example sequence shows `@p add.s32 j, j, 1;` and `@!p bra L1;`/branch-not behavior examples. | Official text |
| SF-5 | Fundamental Types | `fundamental-types` | 3019-3022, 3024-3023, 3062-3066 | Fundamental type = basic type + size; used by instructions and declarations; register variables are always of fundamental type; operand compatibility checked against instruction types; bit-size types compatible with same-size fundamentals. | Official text |
| SF-6 | Register State Space | `register-state-space` | 2617-2624 | Register state space, typed/untyped; aside from predicate registers which are 1-bit, scalar registers are 8/16/32/64/128-bit; registers are not addressable as memory. | Official text |
| SF-7 | Variables | `variables` | 3751-3755 | Variable declarations name state space and type; predicate variables may only be declared in register state space. | Official text |

Assumption status attached to ambiguous/indirect claims below.

## Proposed Lean architecture
- **D-1 Instruction AST (unit-level).** Represent an instruction as:
  - optional guard: `none | some (PredRef, negated : Bool)`
  - opcode family: `or`
  - type tag: `pred | b16 | b32 | b64` with unit scope restricted to `b32`
  - destination operand: register or bit-bucket
  - source operands: two operands (`a`,`b`).
  Grounding: SF-1, SF-2.

- **D-2 Operand model.** Operands required for this unit are:
  - register reference operand (for source/destination in register space),
  - immediate literal operand (indicated by example `0x00010001` in SF-1).
  Grounding: SF-1; SF-2+SF-3 for overall instruction form.

- **D-3 Type model.** Reuse PTX fundamental-type abstraction: basic-kind + size; for this unit include `.pred`, `.b16`, `.b32`, `.b64` compatibility and allow source/destination size-equality with cross-type bit-compatible behavior.
  Grounding: SF-1, SF-5.

- **D-4 State model (single-instruction semantics scope).** Thread-local state has:
  - value-register file (by name)
  - predicate-register file (by name, boolean-like)
  No additional addressable memory modeled for this unit.
  Grounding: SF-3, SF-6, SF-7.

- **D-5 Guard semantics architecture.** Define guard evaluation:
  - none → true,
  - `@p` → value of `p`,
  - `@!p` → negation of `p`.
  Execution applies this guard before state update.
  Grounding: SF-2, SF-3, SF-4.

- **D-6 Core transition architecture.** Transition relation `exec_or` on `(state, or_inst)`:
  - type- and arity-check preconditions,
  - fetch source values,
  - if guard true, write destination result.
  - no guarded execution / no-op path modeled as unchanged state on guard false (see A-1).
  - if destination is bit bucket `_`, no destination update.
  Grounding: SF-1, SF-2, SF-3.

- **D-7 Version/target metadata.** Record `introduced_in := 1.0` and `target := all`, inherited from instruction notes.
  Grounding: SF-1.

## Fact-to-design mapping
- SF-1 → D-1, D-3, D-6, D-7 (instruction grammar, types, meaning, scope metadata, examples).
- SF-2 → D-1, D-2, D-6 (3-operand form, optional guard, destination role).
- SF-3 → D-1, D-5, D-6 (predication mechanics).
- SF-4 → D-5, D-6 (guard behavior examples).
- SF-5 → D-3, D-4, D-6 (type checking and compatibility basis).
- SF-6 → D-4 (register file characteristics, no addressability assumptions).
- SF-7 → D-4 (predicate registers as register-state entities).

## Dependency graph
- **Instruction syntax (D-1)** depends on **operand categories (D-2)** and **type model (D-3)**.
- **Guard semantics (D-5)** depends on **instruction syntax (D-1)** and **state model (D-4)**.
- **Transition relation (D-6)** depends on **state (D-4)** + **syntax (D-1)** + **types (D-3)** + **guard (D-5)**.
- **Metadata (D-7)** is independent and validated from SF-1 section notes.

## Assumptions
- **A-1**: The exact meaning of a false guard is interpreted as “no state update” (no-op) based on predication examples, until human-approved in Gate A; the official wording is “controls conditional execution.”
- **A-2**: The unit target is single-instruction, single-thread state; no scheduling/concurrency/control-flow threading is modeled.
- **A-3**: Immediate operands for `or.b32` are supported as in the provided example, although only a local example evidence is present in SF-1.

## Ambiguities
- **AM-1**: SF-1 gives syntax `or.type d,a,b`, but does not normatively state whether source operands are restricted to register/immediate for this specific instruction. The example uses immediate (`0x00010001`), so immediate support is modeled as a design choice.
- **AM-2**: No explicit exception/error branch is stated in the `or` section; architecture chooses no special error state now.

## Open questions
- **OQ-1**: Do `.type = { .pred, .b16, .b32, .b64 }` indicate that the `or` family is polymorphic and should be modeled generically, or should architecture remain bound only to `.b32` for this bounded unit?
- **OQ-2**: Should formalization include a richer “execution outcome” (e.g., fault/undefined) despite no explicit source evidence in this section?
- **OQ-3**: What is the definitive semantics for undefined/ill-typed operands when preconditions are violated (stuck relation vs error value)?

## Candidate theorem-obligation families
- **PRF-1 Guard-determinism family:** For well-typed `or.b32` and fixed state, execution outcome is unique for each guard case (`none`, `@p`, `@!p`).
- **PRF-2 Guard-behavior family:** Execution occurs iff guard evaluates true under the complete-guard semantics; when false, result is non-effect/no-update.
- **PRF-3 Operand-frame family:** Only the destination register is updated on execution; other value/predicate registers are unchanged.
- **PRF-4 Result-family:** If executed, destination equals bitwise OR of operand values at `d = a | b`.
- **PRF-5 Bit-bucket family:** If destination is `_`, no destination update occurs; all state remains unchanged except possibly required non-state effects (none currently modeled).
- **PRF-6 Compatibility-family:** Instruction-typing check enforces that operand sizes match and are type-compatible as per SF-1/SF-5.

## Evidence index
- `documents/sources/nvidia/ptx/9.3/source-manifest.json`, retrieved lines 1-38 (metadata for document and SHA-256s).
- `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html`:
  - SF-1 (`logic-and-shift-instructions-or`, lines 14290-14323)
  - SF-2 (`ptx-instructions`, lines 7513-7536)
  - SF-3 (`predicated-execution`, lines 7537-7550)
  - SF-4 (`predicated-execution`, lines 7553-7572)
  - SF-5 (`fundamental-types`, lines 3019-3022, 3062-3066)
  - SF-6 (`register-state-space`, lines 2617-2624)
  - SF-7 (`variables`, lines 3751-3755)
- Evidence status: all above are read from official HTML lines with status “official evidence.”

## Gate A review checklist
- [ ] Scope is bounded to this unit and does not define full PTX program semantics.
- [ ] All architectural and semantic claims are labeled as source facts, design choices, assumptions, ambiguities, or open questions.
- [ ] Every source fact is traceable to explicit heading+anchor+lines in PTX 9.3 HTML.
- [ ] Type and register/predicate interactions are consistent with official compatibility and state-space text.
- [ ] Predication is modeled uniformly via complete-guard evaluation and no-guard is unconditonal.
- [ ] Version/target metadata for `or.b32` is recorded from SF-1 notes.
- [ ] Candidate theorem families are non-vacuous and statement-level (not just implementation artifacts).
- [ ] No `sorry`/`admit`/new axioms/`unsafe`; no artifact promotion or gate approval done in this stage.
