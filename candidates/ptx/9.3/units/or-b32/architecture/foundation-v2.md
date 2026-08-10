# PTX 9.3 `or.b32` Foundation Architecture v2

## 1) Scope
Bounded to a single-instruction, single-state semantics artifact for `or` with `.b32` type (source unit: `or.b32`).

## 2) Official source facts

| ID | Document identity | Spec version | Section heading | Anchor | Lines | Evidence text | Status |
|---|---|---:|---|---|---:|---|---|
| SF-1 | `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` | 9.3 | Logic and Shift Instructions: `or` | `logic-and-shift-instructions-or` | 14290–14323 | Syntax: `or.type d, a, b;` with `.type = { .pred, .b16, .b32, .b64 }`; semantics `d = a | b`; “The size of the operands must match, but not necessarily the type.”; “Allowed types include predicate registers.”; PTX ISA note “Introduced in PTX ISA version 1.0.”; target note “Supported on all target architectures.”; examples `or.b32 mask, mask,0x00010001` and `or.pred p,q,r`. | Official HTML |
| SF-2 | `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` | 9.3 | PTX Instructions | `ptx-instructions` | 7513–7527 | PTX instructions have optional `@p` guard predicate (forms shown for 0–4 operands, `@p opcode d,a,b,c;`), `d` is destination for resultful instructions and `a,b,c` are source operands, optional destination may be underscore bit bucket for some instructions. | Official HTML |
| SF-3 | `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` | 9.3 | Predicated Execution | `predicated-execution` | 7541–7550 | Predicate variables are `.pred`; all instructions have optional guard `@{!}p`; instructions without guard execute unconditionally; “controls conditional execution.” | Official HTML |
| SF-4 | `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` | 9.3 | Predicated Execution (examples) | `predicated-execution` | 7561–7572 | Example of `@p add.s32` for conditional update and `@!p bra L1` in inverse branch pattern. | Official HTML |
| SF-5 | `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` | 9.3 | Fundamental Types | `fundamental-types` | 3019–3020, 3062–3066 | Fundamental types combine basic type + size; same basic+size compatibility; signed/unsigned same size compatible; bit-size compatible with any type of same size. | Official HTML |
| SF-6 | `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` | 9.3 | Register State Space | `register-state-space` | 2617–2627 | Registers are in `.reg`, fast storage; scalar registers widths 8/16/32/64/128 bits; predicate registers are 1-bit; registers are not fully addressable (cannot refer to address of register). | Official HTML |
| SF-7 | `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` | 9.3 | Variable Declarations | `variable-declarations` | 3751–3755 | Variables reside in a state space; declaration includes state space/type/name; predicate variables may only be in register state space. | Official HTML |
| SF-8 | `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` | 9.3 | Operand Type Information | `operand-type-information` | 5320–5325 | All instruction operands have known type; each operand compatible with instruction type; no automatic conversion, but bit-size operands may be compatible and silently cast to instruction type. | Official HTML |
| SF-9 | `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` | 9.3 | Source Operands | `source-operands` | 5331–5334 | ALU-style source operands `a,b,c`; PTX describes load-store machine, so ALU operands must be variables in `.reg`; sizes usually consistent. | Official HTML |
| SF-10 | `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` | 9.3 | Integer Constants | `integer-constants` | 2074–2083, 2084–2089 | Integer constants are 64-bit signed/unsigned, non-negative, with C-like literal syntax, and “when used in an instruction … converted to the appropriate size based on instruction type at its use.” | Official HTML |

## 3) Proposed Lean architecture

### D-1 Instruction representation (syntax envelope)
- `OrB32Inst` with fields:
  - optional guard: `none | some (predicate : PredRef) × (negate : Bool)`
  - destination: `Dest` where `Dest := reg` or bit-bucket `_`
  - source1 : `Operand`
  - source2 : `Operand`
  - optional metadata fields for provenance (`introduced_in : Version`, `target_all : Bool`)
- **Design basis:** SF-1, SF-2, SF-3.

### D-2 Operand model
- `Operand` supports:
  - register reference in register state (`RegRef`),
  - integer immediate literal (`Imm`), interpreted via source-to-type conversion at operand typing.
- Type-cast policy follows compatibility relation from SF-5/SF-8.
- **Design basis:** SF-1 example, SF-9, SF-10, SF-8.

### D-3 Type/value model
- Distinguish `PTXType` from runtime value widths:
  - fundamental types include `.pred`, `.b16`, `.b32`, `.b64`, plus width abstraction for 64-bit/32-bit values.
  - `or.b32` is validated as instruction family member where type index includes `.b32` and size checks enforce size-equality (not necessarily same basic kind) from SF-1+SF-5.
- Value model:
  - `Bit`-vector for bit-size/predicate-like semantics,
  - `Bool`-interpreted predicate registers (1-bit domain).
- **Design basis:** SF-1, SF-5, SF-6, SF-7.

### D-4 State model (bounded to this unit)
- `MachineState` contains:
  - register file keyed by register names/types (`RegFile`),
  - predicate-file keyed by predicate names (`PredFile`),
  - no modeled global/shared/memory state for execution of a single `or.b32` ALU instruction.
- **Design basis:** SF-3, SF-6, SF-7, SF-2.

### D-5 Guard semantics
- Define deterministic guard evaluation:
  - `none` ⇒ execute,
  - `@p` ⇒ execute iff predicate true,
  - `@!p` ⇒ execute iff predicate false.
- When guard is false, architecture models no destination update (stability of modeled state is a design requirement).
- **Design basis:** SF-3; SF-4 supports conditional execution intent; SF-2 gives guard syntax.
- **Note:** “no-op on false guard” is a standard PTX interpretation of conditional execution, but full formal semantics of non-execution is not stated in one sentence for all instructions.

### D-6 Transition semantics (small-step relation)
- `exec_or_b32 : OrB32Inst → MachineState → MachineState ⊕ Error` (or a relation to `MachineState` with explicit `wellTyped` precondition for this unit).
- Transition algorithm:
  1. Type/operand validation for compatibility and size rule,
  2. Resolve source values from operands (`RegRef` read / immediate conversion),
  3. Evaluate guard if present,
  4. If guard true and destination is register, write `d := a OR b` with b32 semantics in width-8/16/32/64 polymorphic? (for this unit: fixed `.b32` runtime width),
  5. If guard false or destination is `_`, state unchanged.
- **Design basis:** SF-1, SF-2, SF-3, SF-9, SF-10, SF-5.

### D-7 Version / target metadata
- Attach static metadata constants:
  - introduced_in = 1.0,
  - supported_targets = all.
- **Design basis:** SF-1.

## 4) Fact-to-design mapping
- SF-1 → D-1, D-2, D-3, D-6, D-7
- SF-2 → D-1, D-4, D-6
- SF-3 → D-1, D-5, D-6
- SF-4 → D-5
- SF-5 → D-3, D-2, D-6
- SF-6 → D-4
- SF-7 → D-3, D-4
- SF-8 → D-2, D-3, D-6
- SF-9 → D-2, D-6
- SF-10 → D-2, D-3, D-6

## 5) Dependency graph
- **Syntax & operands:** D-1 depends on D-3 (types) and D-2 (operand form), plus SF-3/2 for guarded form.
- **Typing and value layer:** D-3 depends on D-4 (state carriers), and SF-5/8.
- **State transition:** D-6 depends on D-1, D-2, D-3, D-4, D-5.
- **Metadata:** D-7 independent (informational).

## 6) Assumptions
- **A-1:** For bounded semantics, a false optional guard means instruction has no state update (stable state transition), based on PTX’s “conditional execution” wording and examples.
- **A-2:** We treat only single-thread register/predicate state for the unit; no memory/order/dispatch/concurrency model is required for `or.b32`.
- **A-3:** For this bounded run, immediate literals in source operands are supported for `or.b32` because integer constants are admitted as instruction operands and the `or.b32` example includes `0x00010001`.
- **A-4:** Predicate truth values are interpreted as booleans (`True`/`False`) when evaluated as guards.

## 7) Ambiguities
- **AM-1:** Source section 6.2 says ALU operands must be `.reg` variables, while the `or.b32` example contains an immediate operand literal. This tension is unresolved without a more precise per-instruction operand form section for constants.
- **AM-2:** Source text does not state in one place what happens to state when guard condition is false beyond “controls conditional execution.”
- **AM-3:** No explicit treatment in the `or` section for trap/error outcomes of invalid dynamic instruction-typing at runtime.

## 8) Open questions
- **OQ-1:** Should `or` family be modeled polymorphically for `.pred/.b16/.b32/.b64` in this stage, or restricted strictly to `.b32` execution code path?
- **OQ-2:** Should `pred` results for `or.pred` be interpreted as arithmetic bitwise OR over 1-bit values and then cast to predicate boolean, or constrained via a dedicated predicate domain?
- **OQ-3:** Is silent “no-op” on false guard an explicit theorem to prove or should it remain a modeling axiom within this run?
- **OQ-4:** Should non-`or.b32` example forms in SF-1 (e.g., `.pred`, `.b16`, `.b64`) be included in proof obligations now or deferred.

## 9) Candidate theorem-obligation families
- **TF-1 (Well-typed execution determinism):** For a well-typed `or.b32` and fixed state, transition result is unique.
- **TF-2 (Guard correctness):** Guard evaluation implements `none`/`@p`/`@!p` as intended and controls whether result write occurs.
- **TF-3 (Bit-bucket preservation):** If destination is `_`, state is unchanged after execution attempt.
- **TF-4 (Single write):** If destination is a register and execution is enabled, only destination register is updated.
- **TF-5 (Operand compatibility):** Size-matching (and compatibility) checks reject mismatched-typed instances and accept compatible type pairs per SF-5/SF-8.
- **TF-6 (Semantic result):** On enabled execution, destination value equals bitwise OR of source values in instruction width.

## 10) Evidence index
- **Official manifest:** `documents/sources/nvidia/ptx/9.3/source-manifest.json` (PTX 9.3, official sources).
- **Primary HTML:** `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` SHA-256 `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856` (anchors above).
- **Key anchors used:** `logic-and-shift-instructions-or`, `ptx-instructions`, `predicated-execution`, `fundamental-types`, `register-state-space`, `variable-declarations`, `operand-type-information`, `source-operands`, `integer-constants`.

## 11) Gate A review checklist
- [ ] Scope is bounded to this unit and does not encode full PTX execution or concurrency.
- [ ] Every source claim is tied to specific anchor+lines and listed in Section 2.
- [ ] Architectural decisions are labeled as Source Facts / Proposed Design / Assumptions / Ambiguities / Open Questions.
- [ ] Type compatibility and register/predicate assumptions are explicit and source-backed.
- [ ] Predicate guard handling is modeled and justified only from official predication evidence.
- [ ] Bit bucket `_` behavior is represented consistently.
- [ ] Metadata (`introduced_in`, target coverage) recorded from official notes.
- [ ] Theorem-obligation families are non-vacuous and state concrete properties.
- [ ] No added semantics without source evidence; unresolved points are explicit.
