# PTX `or.b16` Foundation Architecture v1 — DRAFT (UNAPPROVED)

## 1) Scope

- **Scope unit:** bounded language architecture for PTX 9.3 instruction `or.b16` only.
- **Bounded syntax envelope:** one optional guard predicate, one destination, and two source operands.
- **Type focus:** active `.b16` form of the `or` instruction.
- **Excluded by scope:** `or.pred`, `or.b32`, and `or.b64`; program-level control flow, memory, synchronization, and non-control side effects.
- **No Lean code/theorems/axioms** are introduced in this stage.

## 2) Official source facts

- **SF-OR-1 (direct):** `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` (PTX ISA 9.3) — section **“Logic and Shift Instructions: or”** (`logic-and-shift-instructions-or`), lines 14290–14322: syntax `or.type d, a, b;`, type set `{ .pred, .b16, .b32, .b64 }`, semantics `d = a | b`, notes on equal-size operands, and examples `or.b32 mask, mask, 0x00010001` and `or.pred p,q,r`.
- **SF-OR-2 (direct):** same document/section, line 14295: description “Biwise OR.”
- **SF-OR-3 (direct):** same section, lines 14303–14310: operation is bit-wise OR (`d = a | b`) and operands must match in size, not necessarily in type; predicate types are allowed.
- **SF-OR-4 (direct):** same document, section **“PTX Instructions”** (`ptx-instructions`), lines 7517–7527: optional guard predicate and operand role (destination `d`, sources `a,b,c` in result-producing instruction forms).
- **SF-OR-5 (direct):** same section, lines 7534–7535: destination may be optional and `_` may be used as bit bucket for destination register.
- **SF-OR-6 (direct):** same document, section **“Predicated Execution”** (`predicated-execution`), lines 7547–7550: optional guard predicate syntax `@{!}p`, absent guard is unconditional.
- **SF-OR-7 (direct):** same document, section **“Control Flow Instructions: @”** (`control-flow-instructions-at`), lines 21831–21840: threads with false guard do nothing.
- **SF-OR-8 (direct):** same document, section **“Constants”** (`constants`), lines 2069–2073: constants and constant expressions may be used as operands to instructions.
- **SF-OR-9 (direct):** same document, section **“Fundamental Types”** (`fundamental-types`), lines 3020–3022: same type-size specifiers are used for declarations and instruction typing.
- **SF-OR-10 (direct):** same document, section **“Register State Space”** (`register-state-space`), lines 2617–2624: scalar register widths include 8/16/32/64/128; predicate registers are 1-bit.
- **SF-OR-11 (direct):** same document, section **“Predicated Execution”** (`predicated-execution`), lines 7541–7544 and line 7544 example: predicate variables use `.pred` declaration style.
- **SF-OR-12 (direct):** same document, section **“Variables”** (`variables`), lines 3751–3755: variables declare state space + type; predicate variables only in register space.

## 3) Proposed Lean architecture

- **A-1 Instruction node:** `OrB16` with fields:
  - optional guard `guard : Option Guard` where guard is `none`, `pred p`, or `!pred p`.
  - `dst : OrB16Dst`.
  - `src1 : OrB16Src`.
  - `src2 : OrB16Src2`.
- **A-2 Operand taxonomy:**
  - `OrB16Dst := RegisterRef | BitBucket`.
  - `OrB16Src := RegisterRef` (unit-local restriction for source 1).
  - `OrB16Src2 := RegisterRef | Immediate` (for bounded support, second source immediate only unless explicit parser evidence states otherwise).
- **A-3 Typing invariant:** all runtime-relevant operands are 16-bit values for this unit.
- **A-4 State model:** `State := RegFile × PredFile`; no memory/cf/control-stack/thread-state in this bounded unit.
  - `RegFile` maps register declarations to 16-bit bit patterns.
  - `PredFile` maps predicate variables (`.pred`) to booleans for guard evaluation.
- **A-5 Predication semantics:**
  - `none` ⇒ true.
  - `pred p` ⇒ value of `p`.
  - `!pred p` ⇒ negation of `p`.
- **A-6 One-step execution relation:**
  - Outcomes: `executed`, `notExecuted`, or `stuck` (malformed name/state or invalid bounded shape).
  - On `notExecuted`: state unchanged.
  - On `executed` with `dst = reg`: write bitwise OR of resolved operands to destination register (16-bit width).
  - On `executed` with `dst = _`: no state write.
- **A-7 Metadata:** bind unit descriptor to `.b16`, PTX ISA note “Supported on all target architectures,” intro note “Introduced in PTX ISA version 1.0.”

## 4) Fact-to-design mapping

- SF-OR-1, SF-OR-2, SF-OR-3, SF-OR-4, SF-OR-5, SF-OR-7 → A-1, A-2, A-6.
- SF-OR-8 → A-2 (bounded immediate support in source-2).
- SF-OR-4 → A-1 operand roles and arity.
- SF-OR-9, SF-OR-10, SF-OR-11, SF-OR-12 → A-3, A-4.
- SF-OR-6, SF-OR-7 → A-5, A-6.

## 5) Dependency graph

1. **Type/shape foundations:** SF-OR-9, SF-OR-10, SF-OR-11, SF-OR-12 ⇒ A-3, A-4.
2. **Instruction shape layer:** SF-OR-1, SF-OR-4, SF-OR-5 ⇒ A-1, A-2.
3. **Predication control layer:** SF-OR-6, SF-OR-7 ⇒ A-5, A-6.
4. **Operational layer:** SF-OR-3, SF-OR-1 ⇒ A-6.

## 6) Assumptions

- **ASS-1:** The bounded architecture targets only `or.b16` and excludes `.pred`/`.b32`/`.b64` variants.
- **ASS-2:** Register references in this unit resolve to declared 16-bit registers.
- **ASS-3:** Operand-size equality for this unit is enforced as 16-bit compatibility after parsing and typing.
- **ASS-4:** Predicate values are booleans; malformed/uninitialized predicate state is mapped to `stuck` unless caller guarantees preconditions.

## 7) Ambiguities

- **AMB-1:** The `or` section gives a concrete `or.b32` immediate example, but no explicit `or.b16` immediate example.
- **AMB-2:** Parser-level evidence for whether source-1 allows immediate operands for `or` is not explicit in this unit text.
- **AMB-3:** The handling of immediate sizing/casting to 16 bits for this operand class is not explicitly defined in the `or` subsection.
- **AMB-4:** The spec does not fully define behavior for malformed references or missing declarations inside the local `or.b16` relation.

## 8) Open questions

- OQ-1: Should bounded architecture permit immediate operands in `src1` for `or.b16` once broader grammar evidence is reviewed?
- OQ-2: Should immediate typing be parsed by explicit bit-width check (16-bit) or via common integer typing and later width-compatibility check?
- OQ-3: Is a three-way result (`executed`/`notExecuted`/`stuck`) adequate, or should malformed references be separated as a distinct error classification?

## 9) Candidate theorem-obligation families

### Validation obligations

- VO-1: structural well-formedness has exactly one optional guard, one destination-or-`_`, and two source operands.
- VO-2: destination is register or bit-bucket.
- VO-3: source1 is a register reference.
- VO-4: source2 is register or immediate.
- VO-5: execution requires 16-bit-sized operands/target.
- VO-6: guard is `none`, `p`, or `!p` and predicate names resolve.

### Semantic obligations

- SO-1: guard false yields `notExecuted` and unchanged state.
- SO-2: for well-typed inputs and true guard, execution is deterministic.
- SO-3: in `executed`, destination is updated to bitwise OR of resolved values (16-bit), or unchanged if `_`.
- SO-4: no other state except destination register may change.
- SO-5: malformed state/reference inputs map to `stuck`.

## 10) Evidence index

- `documents/sources/nvidia/ptx/9.3/source-manifest.json` (specification version 9.3).
- `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` (SHA-256 `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`):
  - `logic-and-shift-instructions-or` (14290–14322)
  - `ptx-instructions` (7517–7535)
  - `predicated-execution` (7541–7550)
  - `control-flow-instructions-at` (21831–21840)
  - `constants` (2069–2073)
  - `fundamental-types` (3020–3022)
  - `register-state-space` (2617–2624)
  - `variables` (3751–3755)
- Evidence status: all above are direct pulls; mapping to A-2 second-source-immediate support is derived and bounded by SF-OR-1 examples + SF-OR-8 generic constant-operand permission.

## 11) Gate A review checklist

- [ ] Scope is explicitly `or.b16` only.
- [ ] Source facts are separated from design choices, assumptions, ambiguities, and open questions.
- [ ] Each source claim includes document identity, spec version, section anchor, line evidence, and status.
- [ ] Design includes syntax, operands, typing, state, predication, and one-step behavior.
- [ ] Candidate theorem obligations are non-vacuous and localized to bounded unit.
- [ ] No Lean code/theorems/axioms are introduced.
- [ ] Open ambiguities are recorded and not silently resolved.
