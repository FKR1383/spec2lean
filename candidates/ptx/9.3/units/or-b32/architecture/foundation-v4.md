# PTX 9.3 `or.b32` Foundation Architecture v4

## 1) Scope
- Unit: bounded formalization of the PTX instruction `or.b32`.
- Instruction model: single instruction form, single-thread local state transition.
- Bounded omissions: no whole-program flow, scheduling, barriers, shared/global state coherence, exceptions, undefined behavior taxonomy, or other `or`-family type variants.

## 2) Official source facts
| ID | Document identity | Spec version | Section heading | Anchor | Lines | Evidence | Status |
|---|---|---:|---|---|---:|---|---|
| SF-1 | `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` | 9.3 | Logic and Shift Instructions: `or` | `logic-and-shift-instructions-or` | 14298–14301, 14304–14307, 14311–14312, 14290–14290, 14219–14321 | Syntax `or.type d, a, b;` with `.type={.pred,.b16,.b32,.b64}` and semantics `d = a \| b`; notes: operand sizes must match, not necessarily type; allowed types include predicates. Examples include `or.b32 mask mask,0x00010001` and `or.pred p,q,r`. | Official HTML |
| SF-2 | `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` | 9.3 | PTX Instructions | `ptx-instructions` | 7517–7527, 7534–7535 | Instruction forms include optional `@p` guard and 0–4 operands; for resultful instructions `d` is destination and `a,b,c` are source operands; destination may be `_` (bit bucket). | Official HTML |
| SF-3 | `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` | 9.3 | Predicated Execution | `predicated-execution` | 7547–7550, 7549–7550, 7570 | Optional guard predicate with `@{!}p`, optionally negated; guard controls conditional execution; unguarded instructions execute unconditionally. | Official HTML |
| SF-4 | `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` | 9.3 | Predicated Execution example | `predicated-execution` | 7561–7572 | Example uses `@p` and `@!p`, reinforcing that `{!}` negates predicate in control form. | Official HTML |
| SF-5 | `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` | 9.3 | Source Operands | `source-operands` | 5331–5334 | ALU source operands `a,b,c` in this section are declared variables in `.reg` (load-store model). | Official HTML |
| SF-6 | `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` | 9.3 | Integer Constants | `integer-constants` | 2079–2083, 2070–2073, 2094–2096 | Integer constants are 64-bit (`.s64`/`.u64`), converted to instruction/data size at use; zero/non-zero interpretation (`False`/`True`) for predicate-type data/instructions. | Official HTML |
| SF-7 | `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` | 9.3 | Operand Type Information | `operand-type-information` | 5320–5325 | Operands have known type, must be compatible with instruction-determined type; no automatic conversion; bit-size/integer compatibility by size allows silent cast. | Official HTML |
| SF-8 | `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` | 9.3 | Fundamental Types | `fundamental-types` | 3020–3022 | Register variables are fundamental types with basic type + size; supports bit-widthed types including `.b32`. | Official HTML |
| SF-9 | `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` | 9.3 | Register State Space | `register-state-space` | 2617–2624 | Registers (`.reg`) are state-space locals; scalar registers widths include 8/16/32/64/128-bit; predicate registers are 1-bit. | Official HTML |
| SF-10 | `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` | 9.3 | Variable Declarations | `variable-declarations` | 3751–3755 | Variables reside in state spaces; declarations include type/name; predicate variables may only be in register space. | Official HTML |

## 3) Proposed Lean architecture
- **D-1 Syntax envelope (bounded to this unit)**
  - `OrB32` instruction node with fields:
    - `guard : Guard` where `Guard := none | pos : PredRef | neg : PredRef` (for `@p` and `@!p`),
    - `dest : OrDest` where `OrDest := reg : RegRef | bucket`,
    - `srcA : RegRef` (source 1 constrained to register reference),
    - `srcB : OrSourceB` where `OrSourceB := reg : RegRef | imm : IntConst`.
  - `Type index` is fixed to `.b32` in this architecture.
- **D-2 State model**
  - `OrState` includes:
    - integer register file over `.reg` names used by this unit,
    - predicate register file over `.pred` names/booleans,
    - any additional fields only as needed by parser/proof scaffolding (not machine model).
- **D-3 Type/value model for this unit**
  - Instruction-level type fixed to 32-bit bit-width semantics for update path.
  - Source compatibility checked by a bounded predicate:
    - destination and `srcA`/`srcB` must satisfy size/compatibility constraints from SF-5/7,
    - accepted as valid `or.b32` form via constructor/precondition.
  - `IntConst` interpreted as PTX integer constant and converted at use (SF-6).
- **D-4 Guard semantics**
  - `guardEval(none)=true`, `guardEval(pos p)=value(p)`, `guardEval(neg p)=!value(p)`.
  - If disabled, bounded transition performs no modeled state update (assumption A-1).
- **D-5 Transition relation**
  - `execOrB32 : OrState → OrB32 → Option OrState` (partial via precondition `WellTyped`):
    1. check `or`-specific well-formedness (`or` syntax, `.b32`, operand-compatibility, and source-shape constraints),
    2. read `srcA` from register state,
    3. read/convert `srcB` from register or integer constant,
    4. evaluate guard,
    5. if enabled and destination is `reg r`, write `r := srcA OR srcB` at 32-bit width,
    6. if `dest = bucket` or disabled, keep state unchanged.
- **D-6 Version/target metadata**
  - Attach constants from SF-1: `introducedIn = 1.0`, `supportedAllTargets = true`.

## 4) Fact-to-design mapping
- SF-1 → D-1, D-3, D-5, D-6
- SF-2 → D-1, D-2, D-5
- SF-3 → D-1, D-4, D-5
- SF-4 → D-4, D-5
- SF-5 → D-1, D-3, D-5
- SF-6 → D-3, D-2
- SF-7 → D-2
- SF-8 → D-3, D-5
- SF-9 → D-1, D-2, D-3
- SF-10 → D-3, D-5

## 5) Dependency graph
- D-1 depends on SF-1/SF-2 and D-3.
- D-2 depends on SF-2/SF-9/SF-10 and D-3.
- D-3 depends on SF-5/SF-8/SF-10.
- D-4 depends on SF-6/SF-9.
- D-4 (guard semantics) depends on SF-3/SF-4 and D-1.
- D-5 depends on D-1, D-2, D-3, D-4.
- D-6 depends on SF-1 only.

## 6) Assumptions
- **A-1 (guard false behavior):** For bounded modeling, disabled guards correspond to no state updates on this unit.
- **A-2 (state scope):** Only local register and predicate files are modeled; other PTX memory/state spaces are out of scope.
- **A-3 (immediate in second source only):** `or.b32` allows immediate in `srcB` because a section example uses an immediate there; no official line in the same slice proves or denies immediate in `srcA`, so this is a unit-design restriction, not normative evidence.
- **A-4 (error behavior):** This architecture does not introduce an explicit runtime error outcome; ill-typed executions are blocked by a `WellTyped` precondition and treated as out-of-domain in the bounded transition.

## 7) Ambiguities
- **AM-1:** SF-5 says ALU sources must be `.reg` variables, while SF-1 example shows a constant in `or.b32` source position `b`. This architecture models immediate only in `srcB`, with `srcA` register-only.
- **AM-2:** PTX states conditional execution control but not an explicit step-indexed state equation for every false-guard case.
- **AM-3:** `or` family text is polymorphic (`.pred/.b16/.b32/.b64`) but this run is intentionally bounded to `.b32` only.

## 8) Open questions
- **OQ-1:** Is there a normative operand-class list elsewhere in PTX that authoritatively allows immediates for source operands of ALU operations and per-position allowances?
- **OQ-2:** Is the bounded modeling choice “guard false = no write, no other change” accepted as semantics, or should it be introduced later as a separate explicit axiom from another normative subsection?
- **OQ-3:** For predicate result typing, should `.pred` be represented by a dedicated one-bit domain or by the general compatibility machinery with `Bool` interpretations?

## 9) Candidate theorem-obligation families
- **TF-1 (Well-typed determinism):** For fixed state and well-typed `OrB32`, `execOrB32` is single-valued.
- **TF-2 (Guard correctness):** Guard evaluation matches `@`, `@!`, and no-guard intent in SF-3/4.
- **TF-3 (Size compatibility):** Execution is only admitted when source/dest operands are `.b32`-compatible (size/type rules).
- **TF-4 (Semantic result):** Enabled execution with register destination updates destination to `srcA OR srcB` at 32-bit width.
- **TF-5 (Bucket preservation):** `dest = bucket` preserves state.
- **TF-6 (Single write):** Enabled register-destination execution only mutates destination register.
- **TF-7 (Guard-false stability):** Disabled guard yields unchanged state.

## 10) Evidence index
- PTX manifest: `documents/sources/nvidia/ptx/9.3/source-manifest.json` (PTX 9.3 official).
- Primary source file: `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` SHA-256 `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`.
- Anchors cited: `logic-and-shift-instructions-or`, `ptx-instructions`, `predicated-execution`, `operand-type-information`, `source-operands`, `fundamental-types`, `register-state-space`, `variable-declarations`, `integer-constants`.

## 11) Gate A review checklist
- [ ] Scope is explicitly limited to `or.b32` and does not broaden to full PTX or other `or` widths.
- [ ] All source facts are traceable to the anchors and line spans in section 2.
- [ ] Distinct sections clearly separate source facts, design choices, assumptions, ambiguities, open questions.
- [ ] Any non-supported behavior (no-error/guard-false no-update) is explicit as assumptions.
- [ ] Immediate acceptance is constrained to `srcB` with explicit unresolved-note on global evidence.
- [ ] State model is minimal and unit-bounded.
- [ ] Candidate theorem obligations are non-vacuous and relate directly to this bounded design.
