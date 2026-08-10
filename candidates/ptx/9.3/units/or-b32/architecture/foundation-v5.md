# PTX 9.3 `or.b32` Foundation Architecture v5

**Run target:** `ptx-9.3-or.b32-a1e12839`  
**Unit:** `or.b32` (bounded to scalar `.b32`)  
**Status note:** draft candidate produced for automated Gate A stage. Not human-approved.

## 1) Scope
- Language unit: one PTX instruction form `or.type d, a, b;` with `.type = .b32`.
- Semantics scope: single-instruction state transition over bounded thread-local state.
- In-scope: operand roles/shapes, predication (`@`, `@!`), destination update, version/target metadata, and basic state model.
- Out of scope: multi-instruction sequencing, memory model, exceptions, UB/ID behavior not stated for this form, and instruction families other than `or.b32`.

## 2) Official source facts
| ID | Source (document/version) | Section heading | Anchor | Lines | Fact | Status |
|---|---|---|---|---:|---|---|
| SF-1 | `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` (PTX 9.3) | Logic and Shift Instructions: `or` | `logic-and-shift-instructions-or` | 14298–14321 | `or.type d, a, b;` with `.type = { .pred, .b16, .b32, .b64 }`; semantics line `d = a \| b;`; notes “size must match…”; examples include `or.b32  mask mask,0x00010001` and `or.pred  p,q,r;`; PTX/target notes are 1.0 / all targets. | SOURCE FACT |
| SF-2 | same | PTX Instructions | `ptx-instructions` | 7517–7527 | Instruction forms allow optional guard before opcode; for resultful instructions `d` is destination and `a,b,c` are sources. | SOURCE FACT |
| SF-3 | same | PTX Instructions (continued) | `ptx-instructions` | 7534–7535 | Some instructions may use `_` bit bucket for optional destination. | SOURCE FACT |
| SF-4 | same | Predicated Execution | `predicated-execution` | 7547–7550 | All instructions have optional guard predicate; `@{!}p`; instructions without guard execute unconditionally. | SOURCE FACT |
| SF-5 | same | Predicated Execution | `predicated-execution` | 7561–7572 | Example `@p add.s32 ...` and `@!p bra ... // if False` show guarded execution-control behavior. | SOURCE FACT |
| SF-6 | same | Control Flow Instructions: @ | `control-flow-instructions-at` | 21838–21841 | “Execute an instruction…for threads that have the guard predicate True. Threads with a False guard predicate do nothing.” and semantics `If {!}p then instruction`. | SOURCE FACT |
| SF-7 | same | Source Operands | `source-operands` | 5331–5334 | Source operands are `a,b,c`; ALU operands must be in `.reg` variables (load-store model); sizes should be consistent. | SOURCE FACT |
| SF-8 | same | Operand Type Information | `operand-type-information` | 5321–5325 | Operand types are checked against instruction type; no automatic conversion; bit-size compatible with same-size types; compatible sizes may be silently cast. | SOURCE FACT |
| SF-9 | same | Integer Constants | `integer-constants` | 2070–2083 | Integer constants may be instruction operands; interpreted/converted to instruction size/type at use; constants are 64-bit. | SOURCE FACT |
| SF-10 | same | Fundamental Types | `fundamental-types` | 3019–3022 | Fundamental types have basic type and size; register variables are of fundamental type. | SOURCE FACT |
| SF-11 | same | Register State Space | `register-state-space` | 2617–2624 | `.reg` is register state space; scalar widths include 8/16/32/64/128 (plus 1-bit predicate). | SOURCE FACT |
| SF-12 | same | Variables | `variables` | 3751–3755 | Variable declarations include state space, type, name; predicate variables only in `.reg`. | SOURCE FACT |
| SF-13 | same | PTX ISA Notes for `or.b32` | `logic-and-shift-instructions-or` | 14314–14316 | “Introduced in PTX ISA version 1.0.” and “Supported on all target architectures.” | SOURCE FACT |

Derived interpretation from explicit source text (not source-assumed):
- DF-1: From SF-6 and SF-4, for a predicated instruction the machine effect is `If {!}p` then execute instruction, and if complete guard predicate is false, no instruction effect occurs. For bounded architecture, this is used as the guard-false unchanged-state design commitment and is marked as derived, not source-contradictory.

## 3) Proposed Lean architecture
- **D-1 Syntax envelope (bounded):**
  - `OrB32` node with fields:
    - `guard : Guard` where `Guard := none | pos : PredRef | neg : PredRef`.
    - `dest : RegRef` (register destination only; bit bucket not admitted as a commitment for this bounded unit because no or.b32-specific rule in SF-1).
    - `srcA : RegRef`.
    - `srcB : OrSrc` where `OrSrc := reg : RegRef | imm : IntConst`.
  - `.b32` is fixed at the instruction level.
- **D-2 State model:**
  - `OrState` contains:
    - `regFile : RegRef → Value32` for value registers relevant to this unit,
    - `predFile : PredRef → Bool` for predicate registers.
  - No memory/special state modeled for this unit.
- **D-3 Type/value model:**
  - Instruction type is fixed to `.b32` width and a 32-bit bit-pattern domain.
  - Well-formedness requires source/dest operands compatible by SF-8 and source-size constraints (SF-8/SF-1).
  - For `srcB`, immediate constants are parsed to a typed constant and converted for use by SF-9.
- **D-4 Predication model:**
  - `evalGuard none = true`.
  - `evalGuard (pos p) = predFile p`.
  - `evalGuard (neg p) = ¬ predFile p`.
  - Execution of the instruction occurs iff `evalGuard guard = true`.
  - Guard false yields unchanged state (DF-1), i.e. no destination update and no other local register changes.
- **D-5 Transition shape:**
  - `execOrB32 : OrState → OrB32 → Option OrState` (partial by `WellTyped`).
  - If ill-typed or unresolved predicate/register/constant conversion, semantics is undefined in this bounded model (`Option.none`).
  - If `evalGuard` false, return `some s`.
  - If true and `dest = d`, read `srcA`, read/resolve `srcB` (reg or immediate), write `d := srcA OR srcB` (32-bit bitwise OR).
- **D-6 Metadata:**
  - `introducedIn := 1.0`, `supportedAllTargets := true` from SF-13.

## 4) Fact-to-design mapping
- SF-1 → D-1, D-3, D-4, D-5, D-6.
- SF-2 → D-1, D-2, D-4, D-5.
- SF-3 → D-1 (not adopted in v5 as a commitment; carried as ambiguity/edge case).
- SF-4/SF-6 → D-4, D-5.
- SF-7/SF-8/SF-9 → D-3, D-5.
- SF-10/SF-11/SF-12 → D-2.
- SF-13 → D-6.

## 5) Dependency graph
- D-1 depends on SF-1 + SF-2.
- D-2 depends on SF-10 + SF-11 + SF-12.
- D-3 depends on SF-1 + SF-8 + SF-9 + SF-10.
- D-4 depends on SF-4 + SF-6 + D-3.
- D-5 depends on D-1 + D-2 + D-3 + D-4.
- D-6 depends on SF-13.

## 6) Assumptions
- **A-1 (bounded destination shape):** For this bounded formalization, destination is register-only. This is explicit scoping, not a claim of global PTX behavior for all uses of `or` instructions.
- **A-2 (no explicit error outcome):** No explicit malformed-state or runtime-error outcome is introduced for this bounded unit; non-well-typed cases are outside the model domain.
- **A-3 (state scope):** No memory, special-register, or control-state beyond value/predicate files is modeled.

## 7) Ambiguities
- **AM-1:** SF-7 suggests ALU sources in `.reg`, while SF-1 includes a `.b32` example with constant in `srcB`; this tension is handled by a bounded shape that permits immediates only in `srcB`.
- **AM-2:** SF-7’s ALU-operand text is general to section-level semantics and does not provide a definitive per-instruction immediate-position grammar table.
- **AM-3:** Whether an or instruction of this family can use bit bucket `_` as destination for `.b32` is not stated in SF-1. SF-3 is global and therefore non-local to this bounded unit.

## 8) Open questions
- **OQ-1:** What is the normative per-position immediate restriction for `or.b32` (if any) beyond the `or.b32` example in SF-1?
- **OQ-2:** Is bit bucket `_` admissible for `or.b32` specifically (general rule exists but no or-specific evidence in this section)?
- **OQ-3:** Are there any machine-state reads/side effects in the false-guard branch beyond the `do nothing` clause (e.g., trace/side-channel artifacts), which are not captured in this local model?

## 9) Candidate theorem-obligation families
- **TF-1 Well-typed determinism:** For fixed state and well-formed instruction, `execOrB32` yields at most one result.
- **TF-2 Guard semantics:** `evalGuard` matches optional predicate and negation.
- **TF-3 Operand compatibility:** Execution is only defined on well-typed 32-bit operands per SF-1/SF-8/SF-9.
- **TF-4 Guard-false frame:** If `evalGuard guard = false`, `execOrB32` returns unchanged state.
- **TF-5 Single-write locality:** In the execute branch with register destination, only that destination register may change.
- **TF-6 Update correctness:** In execute branch, destination receives the 32-bit OR of resolved source values.
- **TF-7 No-op destination branch:** No state change for any invalid/unsupported destination shape if it is precluded by `WellTyped` (closure obligation for partiality design).

## 10) Evidence index
- Source manifest: `documents/sources/nvidia/ptx/9.3/source-manifest.json` (initial_formalization_unit differs from this run; run metadata is authoritative).
- Primary HTML source: `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` (SHA-256 `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`).
- SHA list: `documents/sources/nvidia/ptx/9.3/SHA256SUMS`.
- Anchors used: `logic-and-shift-instructions-or`, `ptx-instructions`, `predicated-execution`, `control-flow-instructions-at`, `source-operands`, `operand-type-information`, `integer-constants`, `fundamental-types`, `register-state-space`, `variables`.
- Evidence status: all entries in Section 2 are directly read from official sources; DF-1 is an explicit derived interpretation chain from SF-6 and SF-4.

## 11) Gate A review checklist
- [ ] Scope is explicitly bounded to `or.b32` and does not silently cover other `or` widths or predicate-family forms.
- [ ] All source facts and table references use exact line spans and anchors.
- [ ] Source-backed vs design/assumption statements are separated.
- [ ] No bit-bucket destination commitment is made without or.b32-specific evidence; this is recorded as ambiguity/OQ-2.
- [ ] Guard-false behavior is stated as DF-1 (derived from SF-6) rather than a source-assumption assertion.
- [ ] Non-state-affecting concerns are explicitly listed as ambiguities/open questions.
- [ ] Candidate theorem-obligation families are non-vacuous and local-state aware.
