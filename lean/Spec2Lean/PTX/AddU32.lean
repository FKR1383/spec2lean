/-
Spec2Lean Lean formalization candidate — PTX ISA 9.3 `add.u32`

Bounded formalization unit : PTX ISA 9.3 `add.u32` (base scalar, non-saturating,
                            unsigned 32-bit add; instruction family `add`,
                            section 9.7.1.1 "Integer Arithmetic Instructions: add")

Approved semantic interpretation :
  candidates/ptx/9.3/semantics/add-u32-v2.json
  (interpretation_id ptx-9.3-add-u32-semantics-v2)
Gate B record               : reviews/ptx-add-u32/gate-b/ptx-add-u32-gate-b-v2.json
                              (decision: approved)
Gate A record               : reviews/ptx-add-u32/gate-a/ptx-add-u32-gate-a-v2.json
                              (decision: approved)
Architecture reference      : candidates/ptx/9.3/architecture/add-u32-foundation-v2.md
Human overflow-assumption   : reviews/ptx-add-u32/assumptions/ptx-add-u32-overflow-assumption-v1.json
record                        (decision: approved)
Primary source bundle       : candidates/ptx/9.3/source-bundles/add-u32-v1.json
Supplement source bundle    : candidates/ptx/9.3/source-bundles/add-u32-blockers-supplement-v2.json
Semantic critique           : candidates/ptx/9.3/reviews/add-u32-semantics-v2-critic.md

WARNING — HUMAN-APPROVED PROJECT ASSUMPTION (NOT AN NVIDIA SOURCE FACT):
  The result rule d := (a + b) mod 2^32, equivalently the low 32 bits of the
  mathematical sum, is the human-approved formalization assumption recorded in
  reviews/ptx-add-u32/assumptions/ptx-add-u32-overflow-assumption-v1.json and in
  semantic claim PTX-ADD-SEM2-015. It must never be presented as explicitly
  specified by NVIDIA. The official source leaves the exact base add.u32 result
  for sums exceeding the unsigned 32-bit range undetermined (BLOCK-1 NOT_FOUND).

Scope:
  - Only base scalar add.u32 is modeled. add.sat.u32 and the packed forms
    (add.u16x2, add.s16x2, add.u8x4, add.s8x4 and their sat forms) are out of
    scope.
  - No error, trap, undefined, or implementation-defined behavior is invented
    (PTX-ADD-SEM2-044/045/046). A register lookup that is not defined in the
    state is represented as PARTIAL execution (Option none), not as an error.
  - No theorem statements and no proofs are included in this candidate.

Traceability convention: each declaration below carries a comment citing the
relevant semantic claim IDs from candidates/ptx/9.3/semantics/add-u32-v2.json.
-/

import Spec2Lean.Basic

namespace Spec2Lean
namespace PTX

/-! # add.u32 bounded formalization -/

-- Width and modulus for the `.u32` fundamental type.
-- Claim PTX-ADD-SEM2-009: `.u32` is an unsigned integer fundamental type;
-- claim PTX-ADD-SEM2-010: scalar registers have width 32 bits for `.u32`.
def u32Bits : Nat := 32

-- 2^32, the modulus used by the human-approved addition rule
-- (PTX-ADD-SEM2-015). This constant exists only to make the modulo rule
-- explicit; it is not an NVIDIA source fact.
def u32Modulus : Nat := 2 ^ u32Bits

/-
2. 32-bit unsigned value representation.
A `.u32` value is a wrapper around a Fin (2^32) value, so every U32 value is a
number in [0, 2^32). The wrapper intentionally has no arithmetic operators:
the only way to add is the explicit addU32 rule below, so the modulo behavior
cannot be hidden inside a library operator.
Claims PTX-ADD-SEM2-009/010/012; design D-11 (fixed-width 32-bit unsigned domain).
-/
structure U32 where
  toFin : Fin u32Modulus
deriving DecidableEq

-- Custom Repr so executable examples print the numeric value, not the proof
-- carrying Fin wrapper.
instance : Repr U32 where
  reprPrec u _ := repr u.toFin.val

/-
3. Register identifier representation.
Registers are referenced by name (registers are not fully addressable in PTX).
Claims PTX-ADD-SEM2-010, PTX-ADD-SEM2-049; design D-12.
-/
structure RegId where
  name : String
deriving DecidableEq, Repr

/-
4. Predicate-register identifier representation.
Predicate registers are virtual `.pred` registers; the value domain is
two-valued (Boolean-like) per the architecture (design D-13, assumption A-7).
Claim PTX-ADD-SEM2-021.
-/
structure PredId where
  name : String
deriving DecidableEq, Repr

/-
5. Source operands supported by the approved semantics.
A source is either a register variable of compatible type or a constant
immediate. The allowed range/encoding of immediates is an open question
(PTX-ADD-SEM2-053); a constant immediate is represented as a U32 constant value.
Claims PTX-ADD-SEM2-025/026/034.
-/
inductive SourceOperand where
  | reg : RegId -> SourceOperand   -- register source; read from the state
  | imm : U32 -> SourceOperand     -- constant immediate source
deriving DecidableEq, Repr

/-
6. Destination operand representation.
The destination is a register variable of type `.u32` or the bit bucket `_`.
When `d` is the bit bucket, execution performs no register write (the result is
discarded), supported to the strength of the general section 9.2 rule
(PTX-ADD-SEM2-030, PTX-ADD-SEM2-047).
Claims PTX-ADD-SEM2-030/033/047.
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
Claims PTX-ADD-SEM2-018/023/035.
-/
inductive Guard where
  | unguarded : Guard
  | atPos : PredId -> Guard
  | atNeg : PredId -> Guard
deriving DecidableEq, Repr

/-
Instruction type specifier for the bounded unit.
Only `.u32` is in scope; the unit identity fixes the mnemonic `add`, the type
`.u32`, and the empty modifier set (no `.sat`).
Claims PTX-ADD-SEM2-012/048.
-/
inductive AddTypeSpecifier where
  | u32 : AddTypeSpecifier
deriving DecidableEq, Repr

/-
8. Minimal state required by the approved semantics.
The state for base add.u32 is the pair (value-register file, predicate-register
file). No memory, shared, special-register, or concurrency state is required.
Lookups are partial: `valueRegs r = none` means register r is not defined in
the state, which is represented as partial execution rather than an invented
error (PTX-ADD-SEM2-044/045/046; design D-5/D-14, claim PTX-ADD-SEM2-049).
-/
structure MachineState where
  valueRegs : RegId -> Option U32
  predRegs : PredId -> Option Bool

/-
A well-formed add.u32 instruction: optional guard, destination d, then sources
a and b in that order (operand order `d, a, b`).
Claims PTX-ADD-SEM2-004/048.
-/
structure AddU32Instruction where
  type : AddTypeSpecifier
  guard : Guard
  d : Destination
  a : SourceOperand
  b : SourceOperand
deriving DecidableEq, Repr

/-
11. Explicit modulo-2^32 addition rule (HUMAN-APPROVED PROJECT ASSUMPTION).
`addU32 a b` returns the mathematical sum reduced modulo 2^32, equivalently the
low 32 bits of the mathematical sum: d := (a + b) mod 2^32.
This rule is claim PTX-ADD-SEM2-015 (HUMAN_APPROVED_ASSUMPTION) and the fully
determined destination value is claim PTX-ADD-SEM2-016 (DERIVED_INTERPRETATION
depending on PTX-ADD-SEM2-015). It is NOT an NVIDIA source fact and is never
attributed to NVIDIA as explicitly specified.
-/
def addU32 (a b : U32) : U32 :=
  let sum : Nat := a.toFin.val + b.toFin.val
  { toFin := Fin.mk (sum % u32Modulus) (Nat.mod_lt sum (by decide : 0 < u32Modulus)) }

/-
9. Source-operand evaluation.
Reads the current (pre-instruction) value of a source: a register is read from
the value-register file; a constant immediate is the immediate value. A missing
register yields none (partial execution), not an invented result.
Claims PTX-ADD-SEM2-025/026.
-/
def evalSource (s : MachineState) : SourceOperand -> Option U32
  | SourceOperand.reg r => s.valueRegs r
  | SourceOperand.imm v => some v

/-
10. Complete guard-expression evaluation.
- unguarded : true (unconditional execution)
- @p        : value of predicate register p
- @!p       : logical negation of the value of p
A missing predicate register yields none (partial execution).
Claims PTX-ADD-SEM2-023/027.
-/
def evalGuard (s : MachineState) : Guard -> Option Bool
  | Guard.unguarded => some true
  | Guard.atPos p => s.predRegs p
  | Guard.atNeg p =>
      match s.predRegs p with
      | some b => some (not b)
      | none => none

/-
12. Destination update.
When the instruction executes and d is a register, the bounded MachineState
model updates only the destination value register and preserves all predicate
registers. The model contains no carry-flag, status-register, or condition-code
component. Their absence from this bounded model reflects the documented
negative-evidence caveat and must NOT be read as an explicit NVIDIA statement
that such components are affirmatively enumerated as unwritten.
When d is the bit bucket `_`, no value register is written (the result is
discarded).
Claims PTX-ADD-SEM2-028/029/030; caveat SEM2-CRIT-F1 / LMAP-CRIT-F1.
-/
def updateDestination (s : MachineState) (d : Destination) (result : U32) : MachineState :=
  match d with
  | Destination.reg r =>
      { s with valueRegs := fun r' => if r' == r then some result else s.valueRegs r' }
  | Destination.bitBucket => s

/-
Execution outcome representation (architecture D-8; claim PTX-ADD-SEM2-050).
No error constructor is proposed because no explicit exceptional behavior for
base add is evidenced (PTX-ADD-SEM2-044/055).
-/
inductive ExecOutcome where
  | executed : MachineState -> ExecOutcome   -- guard true: destination updated
  | guardFalse : MachineState -> ExecOutcome -- guard false: state unchanged

/-
13. Guarded add.u32 execution.
- The complete guard expression is evaluated first.
- If the guard expression evaluates FALSE, the thread does nothing and the
  state is unchanged (claims PTX-ADD-SEM2-024/031; source-supported via the
  section 9.7.13.2 predication clause, PTX-ADD-SEM2-022). Source operands are
  NOT read in this branch.
- If the guard expression evaluates TRUE (including the unguarded case), the
  source values are read, the result (a + b) mod 2^32 is computed (human
  assumption PTX-ADD-SEM2-015), and the destination is updated (claims
  PTX-ADD-SEM2-016/029). Sources are read before the destination update, so a
  destination that aliases a source does not corrupt the source value used
  (read-before-write; claim PTX-ADD-SEM2-043).
- `none` denotes PARTIAL execution: a required register lookup (guard predicate
  or source register) is not defined in the state. It is not an error, trap, or
  undefined behavior (PTX-ADD-SEM2-044/045/046).
-/
def execAddU32 (s : MachineState) (i : AddU32Instruction) : Option ExecOutcome :=
  match evalGuard s i.guard with
  | none => none
  | some false => some (ExecOutcome.guardFalse s)
  | some true =>
      match evalSource s i.a, evalSource s i.b with
      | some va, some vb => some (ExecOutcome.executed (updateDestination s i.d (addU32 va vb)))
      | _, _ => none

/-! # Helper definitions for executable examples (not semantic definitions) -/

-- Convenience constructor: reduce a Nat to the U32 domain modulo 2^32.
-- This is an example helper; it does not add semantics beyond addU32.
def mkU32 (n : Nat) : U32 :=
  { toFin := Fin.mk (n % u32Modulus) (Nat.mod_lt n (by decide : 0 < u32Modulus)) }

-- Convenience state constructor from binding lists (first binding wins).
-- This is an example helper for the minimal state design (PTX-ADD-SEM2-049).
def mkState (valueRegBindings : List (RegId × U32)) (predRegBindings : List (PredId × Bool)) : MachineState :=
  { valueRegs := fun r => valueRegBindings.find? (fun b => b.1 == r) |>.map Prod.snd,
    predRegs := fun p => predRegBindings.find? (fun b => b.1 == p) |>.map Prod.snd }

-- Example-only identifiers (not part of the semantics).
private def exR1 : RegId := { name := "r1" }
private def exR2 : RegId := { name := "r2" }
private def exP1 : PredId := { name := "p1" }

/-! # Executable examples (demonstrative only; not proofs) -/

-- Basic addition: 5 + 7 = 12.
#eval addU32 (mkU32 5) (mkU32 7)

-- Modulo-2^32 wrap under the human-approved assumption: 0xFFFFFFFF + 1 = 0.
-- (Human assumption PTX-ADD-SEM2-015; never an NVIDIA source fact.)
#eval addU32 (mkU32 0xFFFFFFFF) (mkU32 1)

-- Unguarded complete guard expression is true.
#eval evalGuard (mkState [] []) Guard.unguarded

-- @!p with p = false: complete guard expression is true.
#eval evalGuard (mkState [] [(exP1, false)]) (Guard.atNeg exP1)

-- Destination update writes only the destination register.
#eval (updateDestination (mkState [(exR1, mkU32 1), (exR2, mkU32 2)] [])
         (Destination.reg exR1) (mkU32 100)).valueRegs exR1

-- Bit bucket `_`: no value register is written.
#eval (updateDestination (mkState [(exR1, mkU32 1)] [])
         Destination.bitBucket (mkU32 100)).valueRegs exR1

-- @p with p = false: instruction is not executed, state unchanged (r1 stays 5).
#eval
  let st : MachineState := mkState [(exR1, mkU32 5)] [(exP1, false)]
  let inst : AddU32Instruction :=
    { type := AddTypeSpecifier.u32, guard := Guard.atPos exP1,
      d := Destination.reg exR1, a := SourceOperand.reg exR1,
      b := SourceOperand.imm (mkU32 7) }
  match execAddU32 st inst with
  | some (.guardFalse s') => s'.valueRegs exR1
  | some (.executed s') => s'.valueRegs exR1
  | none => none

-- @!p with p = false: guard expression true, executes, r1 becomes 12.
#eval
  let st : MachineState := mkState [(exR1, mkU32 5)] [(exP1, false)]
  let inst : AddU32Instruction :=
    { type := AddTypeSpecifier.u32, guard := Guard.atNeg exP1,
      d := Destination.reg exR1, a := SourceOperand.reg exR1,
      b := SourceOperand.imm (mkU32 7) }
  match execAddU32 st inst with
  | some (.guardFalse s') => s'.valueRegs exR1
  | some (.executed s') => s'.valueRegs exR1
  | none => none

-- Partial execution: a missing source register yields none, not an invented error.
#eval
  let st : MachineState := mkState [] [(exP1, true)]
  let inst : AddU32Instruction :=
    { type := AddTypeSpecifier.u32, guard := Guard.atPos exP1,
      d := Destination.reg exR1, a := SourceOperand.reg exR1,
      b := SourceOperand.imm (mkU32 7) }
  match execAddU32 st inst with
  | some (.guardFalse _) => "guard-false"
  | some (.executed _) => "executed"
  | none => "partial-none"

end PTX
end Spec2Lean
