/-
Spec2Lean Lean formalization candidate — PTX ISA 9.3 `cnot.b32`.

Bounded formalization unit: PTX ISA 9.3 `cnot.b32`.
Approved semantic source reference: candidates/ptx/9.3/units/cnot-b32/semantics/semantics-v2.json
  (interpretation_id ptx-9.3-cnot-b32-semantics-v2).

Scope:
- Base scalar `cnot.b32 d, a` only.
- No theorem statements and no proofs in this stage.
- No invented error/exception behavior.
- No assumptions beyond the approved Lean architecture for this unit.

Traceability convention: each declaration below has comments with relevant
semantic claim IDs from the approved semantics file.
-/

import Spec2Lean.Basic

namespace Spec2Lean.PTX.CnotB32

/--
Bits-32 width used by bounded form `cnot.b32`.
-/
def b32Bits : Nat := 32

/-- Modulus for 32-bit bit-domain values (`2^32`).
-/
def b32Modulus : Nat := 2 ^ b32Bits

/--
32-bit value representation as `Fin (2^32)`.
Claim IDs: SF-1, SF-2, DI-1.
-/
structure U32 where
  toFin : Fin b32Modulus
  deriving DecidableEq

/-- Register identifier for value-register operands.
Claims: SF-C15, SF-3, SF-6.
-/
structure RegId where
  name : String
  deriving DecidableEq, Repr

/-- Predicate-register identifier for optional guard evaluation.
Claims: SF-C12 and SF-C13.
-/
structure PredId where
  name : String
  deriving DecidableEq, Repr

/--
Source operand for this bounded unit: register only.
The immediate-source form for `cnot.b32` is an unresolved open question in the
reviewed semantics (OQ-1), so this bounded model uses registers only.
Claims: SF-C3, SF-9.
-/
inductive SourceOperand where
  | reg : RegId -> SourceOperand
  deriving DecidableEq, Repr

/--
Destination operand for this bounded unit: register-only.
Bit-bucket `_` is unresolved in the reviewed semantics (OQ-2), so omitted here.
Claims: SF-C3, SF-9.
-/
inductive Destination where
  | reg : RegId -> Destination
  deriving DecidableEq, Repr

/--
Optional guard form for PTX predication.
- unguarded : executes unconditionally
- atPos p   : executes iff predicate p is true
- atNeg p   : executes iff predicate p is false
Claims: SF-C12, SF-C13.
-/
inductive Guard where
  | unguarded : Guard
  | atPos : PredId -> Guard
  | atNeg : PredId -> Guard
  deriving DecidableEq, Repr

/--
Instruction type specifier. The bounded unit fixes `.b32`.
Claim: DI-1.
-/
inductive CnotTypeSpecifier where
  | b32 : CnotTypeSpecifier
  deriving DecidableEq, Repr

/--
Minimal machine state for this unit.
Lookups are partial: a missing register yields `none` (partial execution), not an
invented trap/error.
Claims: SF-C15/16, D-5, D-13.
-/
structure MachineState where
  valueRegs : RegId -> Option U32
  predRegs : PredId -> Option Bool

/--
Instruction syntax model for bounded `cnot.b32 d, a`.
Claim: SF-C3, SF-C9.
-/
structure CnotB32Instruction where
  type : CnotTypeSpecifier
  guard : Guard
  d : Destination
  a : SourceOperand
  deriving DecidableEq, Repr

/-- 32-bit constant constructor by modulo reduction. -/
def mkB32 (n : Nat) : U32 :=
  { toFin := Fin.mk (n % b32Modulus) (Nat.mod_lt n (by decide : 0 < b32Modulus)) }

/--
Evaluate source operand from pre-state value-register file.
Claims: SF-C5 and source-read entry.
-/
def evalSource (s : MachineState) : SourceOperand -> Option U32
  | SourceOperand.reg r => s.valueRegs r

/--
Evaluate complete guard expression.
Claims: SF-C12 and DI-2.
-/
def evalGuard (s : MachineState) : Guard -> Option Bool
  | Guard.unguarded => some true
  | Guard.atPos p => s.predRegs p
  | Guard.atNeg p =>
      match s.predRegs p with
      | some b => some (not b)
      | none => none

/--
Logical negation behavior on 32-bit domain:
`d := (a == 0) ? 1 : 0`.
Claim IDs: SF-C5, SF-4.
-/
def cnotB32 (a : U32) : U32 :=
  match a.toFin.val with
  | 0 => mkB32 1
  | _ => mkB32 0

/--
Destination write on execute.
Only destination register is updated.
Claims: SF-C5 and state-write entry.
-/
def updateDestination (s : MachineState) (d : Destination) (result : U32) : MachineState :=
  match d with
  | Destination.reg r =>
      { s with valueRegs := fun r' => if r' == r then some result else s.valueRegs r' }

/--
Execution outcome classification for bounded unit:
- `executed` : guard is true and destination is written
- `guardFalse` : guard is false and state is unchanged.
Claims: SF-C16, DI-3.
-/
inductive ExecOutcome where
  | executed : MachineState -> ExecOutcome
  | guardFalse : MachineState -> ExecOutcome

/--
Single-step guarded execution of `cnot.b32`.

a) Guard false / unresolved predicate => partial (`none`) for missing predicate state.

b) If guard false: returns unchanged state, source is not read in this branch.

c) If guard true: read source a from pre-state, compute logical negation bit value,
   and write to destination.

No explicit error/UB branch is introduced; absence of required bindings yields
`none`.
Claims: SF-C5, SF-C16, SF-5, source-read/write entries.
-/
def execCnotB32 (s : MachineState) (i : CnotB32Instruction) : Option ExecOutcome :=
  match evalGuard s i.guard with
  | none => none
  | some false => some (ExecOutcome.guardFalse s)
  | some true =>
      match evalSource s i.a with
      | some va => some (ExecOutcome.executed (updateDestination s i.d (cnotB32 va)))
      | none => none

/-- Convenience constructor for state-building examples. -/
def mkState (valueRegBindings : List (RegId × U32)) (predRegBindings : List (PredId × Bool)) : MachineState :=
  { valueRegs := fun r => valueRegBindings.find? (fun b => b.1 == r) |>.map Prod.snd,
    predRegs := fun p => predRegBindings.find? (fun b => b.1 == p) |>.map Prod.snd }

end Spec2Lean.PTX.CnotB32
