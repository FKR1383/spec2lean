/-
Spec2Lean Lean formalization candidate — PTX ISA 9.3 `mov.b32`

Bounded formalization unit : PTX ISA 9.3 `mov.b32` (bounded scalar value-copy
                            form `mov.type d, a;` with instruction type `.b32`
                            and with source operand `a` a register variable or
                            an immediate value; instruction family `mov`,
                            section 9.7.9.3 "Data Movement and Conversion
                            Instructions: mov")

Approved semantic interpretation :
  candidates/ptx/9.3/units/mov-b32/semantics/semantics-v2.json
  (interpretation_id ptx-9.3-mov-b32-semantics-v2)
Gate B record               : reviews/ptx-mov-b32/gate-b/ptx-mov-b32-b-approval-v1.json
                              (decision: approved)
Gate A record               : reviews/ptx-mov-b32/gate-a/ptx-mov-b32-a-approval-v1.json
                              (decision: approved)
Architecture reference      : candidates/ptx/9.3/units/mov-b32/architecture/foundation-v1.md
                              (approved at Gate A; bounded-scope decision D-0c)
Primary source bundle       : candidates/ptx/9.3/units/mov-b32/source-bundles/source-bundle-v2.json
Semantic critique           : candidates/ptx/9.3/units/mov-b32/reviews/semantics-critic-v2.md

EPISTEMIC NOTE (no human-approved formalization assumption exists for mov.b32):
  semantics-v2 contains zero ASSUMPTION-classified claims (assumption_notes).
  In particular, the guard-false "no state update" consequence is a
  DERIVED_INTERPRETATION (PTX-MOV-SEM2-034/038) grounded in the official
  section 9.7.13.2 clause "Threads with a False guard predicate do nothing."
  (PTX-9.3-MOV-035/036; SOURCE_FACT PTX-MOV-SEM2-072/073). This candidate must
  never present that consequence as a human assumption or as an add.u32-style
  assumption import; it is implemented here as the approved derived
  interpretation.

Scope:
  - Only the bounded scalar value-copy form `mov.b32 d, a;` with source `a` a
    register variable or an immediate value is modeled (architecture D-0c;
    PTX-MOV-SEM2-004/007/013). The `sreg`, `avar`, `avar+imm`, `fname`, and
    `kernel` source categories of section 9.7.9.3 and the distinct vector
    pack/unpack form of section 9.7.9.4 are out of scope
    (PTX-MOV-SEM2-063/064).
  - No error, trap, undefined, or implementation-defined behavior is invented
    (PTX-MOV-SEM2-041/042/043). A register or predicate lookup that is not
    defined in the state is represented as PARTIAL execution (Option none), not
    as an error.
  - Version/target metadata is not modeled as state behavior: the base form was
    introduced in PTX ISA 1.0 (PTX-MOV-SEM2-044/028) and no family-specific
    target restriction is stated for it in the scalar section read
    (PTX-MOV-SEM2-045); the scalar base form's target set is an open question
    (PTX-MOV-SEM2-046). Version/target gating are validation obligations
    (architecture VAL-5/VAL-6), not execution behavior.
  - No theorem statements and no proofs are included in this candidate. The
    proof-obligation families PRF-1..PRF-7 (architecture Section 10;
    semantics-v2 future_theorem_obligation_topics) are deferred to the
    theorem-design and proof stages.

Traceability convention: each declaration below carries a comment citing the
relevant semantic claim IDs from
candidates/ptx/9.3/units/mov-b32/semantics/semantics-v2.json and, where
applicable, the architecture design choice.
-/

import Spec2Lean.Basic

namespace Spec2Lean
namespace PTX

/-! # mov.b32 bounded formalization -/

-- Width of the `.b32` fundamental type (32 bits).
-- Claim PTX-MOV-SEM2-016: `.b32` is a "Bits (untyped)" fundamental type;
-- claim PTX-MOV-SEM2-018: scalar registers may have a 32-bit width.
def b32Bits : Nat := 32

-- 2^32, the number of 32-bit bit patterns. This is the size of the fixed-width
-- 32-bit untyped bit-value domain proposed for `.b32` (design D-11;
-- PTX-MOV-SEM2-060).
def b32DomainSize : Nat := 2 ^ b32Bits

/-
2. 32-bit untyped bit-value representation.
A `.b32` value is a wrapper around a Fin (2^32) value, so every B32 value is a
number in [0, 2^32), in bijection with the 32-bit bit patterns of the "Bits
(untyped)" basic type (PTX-MOV-SEM2-016/021). The exact Lean encoding is a
Lean-mapping decision per design D-11 / PTX-MOV-SEM2-060. The wrapper
intentionally has no arithmetic operators: the only operation is the explicit
copy rule `copyValue` below, so the copy semantics `d = a;` cannot be hidden
inside a library operator.
-/
structure B32 where
  toFin : Fin b32DomainSize
deriving DecidableEq

-- Custom Repr so executable examples print the numeric value, not the proof
-- carrying Fin wrapper.
instance : Repr B32 where
  reprPrec v _ := repr v.toFin.val

/-
3. Register identifier representation.
Registers are referenced by name (registers are not fully addressable in PTX).
Claims PTX-MOV-SEM2-018/049; design D-12.
-/
structure RegId where
  name : String
deriving DecidableEq, Repr

/-
4. Predicate-register identifier representation.
Predicate registers are virtual `.pred` registers; the value domain is
two-valued (Boolean-like) per the architecture (design D-13). The exact Lean
encoding of the 1-bit predicate register value domain is an open question
(PTX-MOV-SEM2-069). Claim PTX-MOV-SEM2-027.
-/
structure PredId where
  name : String
deriving DecidableEq, Repr

/-
5. Source operands supported by the approved semantics.
A source is either a register variable of a type compatible with `.b32` or a
constant immediate (PTX-MOV-SEM2-013/026). The allowed range/encoding of
immediates is an open question (PTX-MOV-SEM2-048); a constant immediate is
represented as a B32 constant value.
-/
inductive SourceOperand where
  | reg : RegId -> SourceOperand   -- register source; read from the state
  | imm : B32 -> SourceOperand     -- constant immediate source
deriving DecidableEq, Repr

/-
6. Destination operand representation.
The destination is a register variable of a type compatible with `.b32`, or the
bit bucket `_` as a candidate alternative (design D-18). When `d` is the bit
bucket, execution performs no register write (the result is discarded),
supported only to the strength of the general section 9.2 rule
(PTX-MOV-SEM2-047, AMB-3).
-/
inductive Destination where
  | reg : RegId -> Destination     -- destination register
  | bitBucket : Destination        -- bit bucket `_`: result discarded
deriving DecidableEq, Repr

/-
7. Optional guard representation.
- unguarded : no guard; complete guard expression is true (unconditional).
- atPos p   : `@p`;  complete guard expression is the value of predicate p.
- atNeg p   : `@!p`; complete guard expression is the negation of predicate p.
Claims PTX-MOV-SEM2-009/027/031; design D-19/D-21.
-/
inductive Guard where
  | unguarded : Guard
  | atPos : PredId -> Guard
  | atNeg : PredId -> Guard
deriving DecidableEq, Repr

/-
Instruction type specifier for the bounded unit.
Only `.b32` is in scope; the unit identity fixes the mnemonic `mov`, the type
`.b32`, and the empty modifier set (the scalar mov syntax has no modifier
position). Claims PTX-MOV-SEM2-007/022.
-/
inductive MovTypeSpecifier where
  | b32 : MovTypeSpecifier
deriving DecidableEq, Repr

/-
8. Minimal state required by the approved semantics.
The state for the bounded base mov.b32 is the pair (value-register file,
predicate-register file). No memory, shared, special-register, or concurrency
state is required by the base form's syntax and description
(PTX-MOV-SEM2-058; design D-5/D-14). Lookups are partial: `valueRegs r = none`
means register r is not defined in the state, represented as partial execution
rather than an invented error (PTX-MOV-SEM2-041/042/043).
-/
structure MachineState where
  valueRegs : RegId -> Option B32
  predRegs : PredId -> Option Bool

/-
A well-formed mov.b32 instruction: optional guard, destination d, then the
single source operand a in that order (operand order `d, a`; the destination
comes first). Claims PTX-MOV-SEM2-010/059; design D-1/D-16.
-/
structure MovB32Instruction where
  type : MovTypeSpecifier
  guard : Guard
  d : Destination
  a : SourceOperand
deriving DecidableEq, Repr

/-
9. Source-operand evaluation.
Reads the current (pre-instruction) value of a source: a register is read from
the value-register file; a constant immediate is the immediate value. A missing
register yields none (partial execution), not an invented result.
Claims PTX-MOV-SEM2-026/030.
-/
def evalSource (s : MachineState) : SourceOperand -> Option B32
  | SourceOperand.reg r => s.valueRegs r
  | SourceOperand.imm v => some v

/-
10. Complete guard-expression evaluation.
- unguarded : true (unconditional execution)
- @p        : value of predicate register p
- @!p       : logical negation of the value of p
A missing predicate register yields none (partial execution).
Claims PTX-MOV-SEM2-009/027/031; design D-19.
-/
def evalGuard (s : MachineState) : Guard -> Option Bool
  | Guard.unguarded => some true
  | Guard.atPos p => s.predRegs p
  | Guard.atNeg p =>
      match s.predRegs p with
      | some b => some (not b)
      | none => none

/-
11. Explicit copy rule (d = a;).
`copyValue` returns its argument unchanged: the value written to the
destination equals the value of source operand a, a bit-for-bit copy of the
32-bit untyped `.b32` value. This is the mov Semantics line `d = a;`
(PTX-MOV-SEM2-035, SOURCE_FACT) and the copy-semantics derived interpretation
(PTX-MOV-SEM2-036). No arithmetic, conversion, or truncation is involved.
-/
def copyValue (v : B32) : B32 := v

/-
12. Destination update.
When the instruction executes and d is a register, the bounded MachineState
model updates only the destination value register and preserves all predicate
registers (PTX-MOV-SEM2-032/033). The model contains no carry-flag,
status-register, or condition-code component. Their absence from this bounded
model reflects the documented negative-evidence caveat (PTX-MOV-SEM2-041/042,
bundle GAP-3) and must NOT be read as an explicit NVIDIA statement that such
components are affirmatively enumerated as unwritten.
When d is the bit bucket `_`, no value register is written (the result is
discarded), supported to the strength of the general section 9.2 rule
(PTX-MOV-SEM2-047).
-/
def updateDestination (s : MachineState) (d : Destination) (value : B32) : MachineState :=
  match d with
  | Destination.reg r =>
      { s with valueRegs := fun r' => if r' == r then some value else s.valueRegs r' }
  | Destination.bitBucket => s

/-
Execution outcome representation (design D-8; PTX-MOV-SEM2-043).
No error constructor is proposed because no explicit exceptional behavior for
the bounded base mov.b32 is evidenced (PTX-MOV-SEM2-041, GAP-3).
-/
inductive ExecOutcome where
  | executed : MachineState -> ExecOutcome   -- guard true: destination updated
  | guardFalse : MachineState -> ExecOutcome -- guard false: state unchanged

/-
13. Guarded mov.b32 execution.
- The complete guard expression is evaluated first.
- If the guard expression evaluates FALSE, the thread does nothing and the
  state is unchanged (PTX-MOV-SEM2-034/038; source-resolved via the section
  9.7.13.2 clause "Threads with a False guard predicate do nothing.",
  PTX-9.3-MOV-035/036). Source operands are NOT read in this branch.
- If the guard expression evaluates TRUE (including the unguarded case), the
  source value is read and copied into the destination (d = a;) (claims
  PTX-MOV-SEM2-035/036/037). The source is read from the pre-instruction state
  before the destination update, so a destination that aliases the source
  register retains its own value (read-before-write; PTX-MOV-SEM2-062).
- `none` denotes PARTIAL execution: a required register lookup (guard predicate
  or source register) is not defined in the state. It is not an error, trap, or
  undefined behavior (PTX-MOV-SEM2-041/042).
-/
def execMovB32 (s : MachineState) (i : MovB32Instruction) : Option ExecOutcome :=
  match evalGuard s i.guard with
  | none => none
  | some false => some (ExecOutcome.guardFalse s)
  | some true =>
      match evalSource s i.a with
      | some va => some (ExecOutcome.executed (updateDestination s i.d (copyValue va)))
      | none => none

/-
14. Relational form of the execution semantics.
The approved execution-semantics representation design (architecture D-25;
PTX-MOV-SEM2-061) specifies the future execution semantics as an execution
relation between (state, instruction) and state, not merely as a function, so
that determinism (PRF-1) and frame/locality obligations (PRF-2..PRF-5) are
non-vacuous. This inductive relation is the relational counterpart of the
executable function `execMovB32`: it relates s to the unchanged state exactly
when the complete guard expression evaluates false, and to the updated state
exactly when the guard is true and the source resolves. The correspondence
between the relation and the executable function is a theorem-stage obligation
(PRF-1 family).
-/
inductive MovB32Step : MachineState -> MovB32Instruction -> MachineState -> Prop where
  | guardFalse : (s : MachineState) -> (i : MovB32Instruction) ->
      evalGuard s i.guard = some false -> MovB32Step s i s
  | executed : (s : MachineState) -> (i : MovB32Instruction) -> (va : B32) ->
      evalGuard s i.guard = some true ->
      evalSource s i.a = some va ->
      MovB32Step s i (updateDestination s i.d (copyValue va))

/-! # Helper definitions for executable examples (not semantic definitions) -/

-- Convenience constructor: reduce a Nat to the B32 domain modulo 2^32.
-- This is an example helper; it does not add semantics beyond copyValue.
def mkB32 (n : Nat) : B32 :=
  { toFin := Fin.mk (n % b32DomainSize) (Nat.mod_lt n (by decide : 0 < b32DomainSize)) }

-- Convenience state constructor from binding lists (first binding wins).
-- This is an example helper for the minimal state design (PTX-MOV-SEM2-058).
def mkState (valueRegBindings : List (RegId × B32)) (predRegBindings : List (PredId × Bool)) : MachineState :=
  { valueRegs := fun r => valueRegBindings.find? (fun b => b.1 == r) |>.map Prod.snd,
    predRegs := fun p => predRegBindings.find? (fun b => b.1 == p) |>.map Prod.snd }

-- Example-only identifiers (not part of the semantics).
private def exR1 : RegId := { name := "r1" }
private def exR2 : RegId := { name := "r2" }
private def exP1 : PredId := { name := "p1" }

/-! # Executable examples (demonstrative only; not proofs) -/

-- Copy rule: the value written equals the value read (d = a; PTX-MOV-SEM2-036).
-- 0xDEADBEEF is copied unchanged.
#eval copyValue (mkB32 0xDEADBEEF)

-- Unguarded complete guard expression is true (PTX-MOV-SEM2-009).
#eval evalGuard (mkState [] []) Guard.unguarded

-- @!p with p = false: complete guard expression is true.
#eval evalGuard (mkState [] [(exP1, false)]) (Guard.atNeg exP1)

-- Destination update writes only the destination register (PTX-MOV-SEM2-032/033).
#eval (updateDestination (mkState [(exR1, mkB32 1), (exR2, mkB32 2)] [])
         (Destination.reg exR1) (mkB32 100)).valueRegs exR1

-- Bit bucket `_`: no value register is written (PTX-MOV-SEM2-047, general
-- section 9.2 rule strength).
#eval (updateDestination (mkState [(exR1, mkB32 1)] [])
         Destination.bitBucket (mkB32 100)).valueRegs exR1

-- @p with p = false: instruction is not executed, state unchanged (r1 stays 5).
#eval
  let st : MachineState := mkState [(exR1, mkB32 5)] [(exP1, false)]
  let inst : MovB32Instruction :=
    { type := MovTypeSpecifier.b32, guard := Guard.atPos exP1,
      d := Destination.reg exR1, a := SourceOperand.reg exR1 }
  match execMovB32 st inst with
  | some (.guardFalse s') => s'.valueRegs exR1
  | some (.executed s') => s'.valueRegs exR1
  | none => none

-- @!p with p = false: guard expression true, executes, r1 becomes 7 (imm copy).
#eval
  let st : MachineState := mkState [(exR1, mkB32 5)] [(exP1, false)]
  let inst : MovB32Instruction :=
    { type := MovTypeSpecifier.b32, guard := Guard.atNeg exP1,
      d := Destination.reg exR1, a := SourceOperand.imm (mkB32 7) }
  match execMovB32 st inst with
  | some (.guardFalse s') => s'.valueRegs exR1
  | some (.executed s') => s'.valueRegs exR1
  | none => none

-- Aliasing d == a: the source is read before the destination update, so r1
-- retains its own value (read-before-write; PTX-MOV-SEM2-062).
#eval
  let st : MachineState := mkState [(exR1, mkB32 5)] []
  let inst : MovB32Instruction :=
    { type := MovTypeSpecifier.b32, guard := Guard.unguarded,
      d := Destination.reg exR1, a := SourceOperand.reg exR1 }
  match execMovB32 st inst with
  | some (.guardFalse s') => s'.valueRegs exR1
  | some (.executed s') => s'.valueRegs exR1
  | none => none

-- Partial execution: a missing source register yields none, not an invented
-- error (PTX-MOV-SEM2-041/042).
#eval
  let st : MachineState := mkState [] [(exP1, true)]
  let inst : MovB32Instruction :=
    { type := MovTypeSpecifier.b32, guard := Guard.atPos exP1,
      d := Destination.reg exR1, a := SourceOperand.reg exR1 }
  match execMovB32 st inst with
  | some (.guardFalse _) => "guard-false"
  | some (.executed _) => "executed"
  | none => "partial-none"

end PTX
end Spec2Lean
