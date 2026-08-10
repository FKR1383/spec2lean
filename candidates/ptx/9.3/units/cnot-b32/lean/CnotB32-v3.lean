/-
Spec2Lean Lean formalization candidate — PTX ISA 9.3 `cnot.b32`.

Bounded formalization unit: PTX ISA 9.3 `cnot.b32`.
Approved semantic source reference: candidates/ptx/9.3/units/cnot-b32/semantics/semantics-v2.json
  (interpretation_id ptx-9.3-cnot-b32-semantics-v2).

Scope:
- Base scalar `cnot.b32 d, a` only.
- Source and destination are register-only in this bounded formalization (OQ-1, OQ-2 unresolved).
- No theorem statements in this stage.
- No invented errors/UB/implementation-defined behavior.
- No partial-guard reordering; evaluate guard first.

Traceability convention: each declaration below cites semantic IDs from
`semantics-v2.json`; unresolved design choices explicitly cite open questions.
-/

import Spec2Lean.Basic

namespace Spec2Lean.PTX.CnotB32

/--
32-bit domain size used by this bounded form (`.b32`).
Claim IDs: SF-1, DI-1.
-/
def b32Bits : Nat := 32

/--
Modulus for 32-bit values (`2^32`).
Claim IDs: SF-1, DI-1.
-/
def b32Modulus : Nat := 2 ^ b32Bits

/--
32-bit value representation as `Fin (2^32)`.
Claim IDs: SF-1, SF-2, DI-1, DI-4.
-/
structure U32 where
  toFin : Fin b32Modulus
  deriving DecidableEq

/--
Register identifier for register operands.
Claim IDs: SF-1, SF-3, SF-6.
-/
structure RegId where
  name : String
  deriving DecidableEq, Repr

/--
Predicate-register identifier.
Claim IDs: SF-4.
-/
structure PredId where
  name : String
  deriving DecidableEq, Repr

/--
Source operand for bounded `cnot.b32`: register only.
Claim IDs: SF-1, SF-3, SF-6, OQ-1.
-/
inductive SourceOperand where
  | reg : RegId -> SourceOperand
  deriving DecidableEq, Repr

/--
Destination operand for bounded `cnot.b32`: register only.
Claim IDs: SF-1, SF-3, SF-6, OQ-2.
-/
inductive Destination where
  | reg : RegId -> Destination
  deriving DecidableEq, Repr

/--
Optional predication form.
- `unguarded` : execute iff true.
- `atPos p`   : execute iff predicate `p` is true.
- `atNeg p`   : execute iff predicate `p` is false.
Claim IDs: SF-4, DI-2.
-/
inductive Guard where
  | unguarded : Guard
  | atPos : PredId -> Guard
  | atNeg : PredId -> Guard
  deriving DecidableEq, Repr

/--
Instruction type specifier for bounded unit.
Only `.b32` is represented.
Claim IDs: SF-1, SF-3, DI-1.
-/
inductive CnotTypeSpecifier where
  | b32 : CnotTypeSpecifier
  deriving DecidableEq, Repr

/--
Minimal machine state for bounded semantics: value registers and predicate registers.
Missing entries model partial execution as `none`.
Claim IDs: DI-2, DI-4, OQ-4.
-/
structure MachineState where
  valueRegs : RegId -> Option U32
  predRegs : PredId -> Option Bool

/--
Instruction syntax model for bounded form.
Claim IDs: SF-1, SF-3, SF-6.
-/
structure CnotB32Instruction where
  type : CnotTypeSpecifier
  guard : Guard
  d : Destination
  a : SourceOperand
  deriving DecidableEq, Repr

/--
Construct a `.b32` value by reduction modulo `2^32`.
This resolves OQ-3 (literal cast width) by canonical modulo wrapping.
Claim IDs: SF-2, OQ-3.
-/
def mkB32 (n : Nat) : U32 :=
  { toFin := Fin.mk (n % b32Modulus) (Nat.mod_lt n (by decide : 0 < b32Modulus)) }

/--
Evaluate a source operand from pre-state value registers.
Claim IDs: SF-2, DI-3.
-/
def evalSource (s : MachineState) : SourceOperand -> Option U32
  | SourceOperand.reg r => s.valueRegs r

/--
Evaluate complete guard expression from pre-state predicate registers.
- unguarded -> true
- @p -> value of p
- @!p -> negation of p
Claim IDs: SF-4, DI-2.
-/
def evalGuard (s : MachineState) : Guard -> Option Bool
  | Guard.unguarded => some true
  | Guard.atPos p => s.predRegs p
  | Guard.atNeg p =>
      match s.predRegs p with
      | some b => some (not b)
      | none => none

/--
`cnot` behavior on 32-bit values.
`d := (a == 0) ? 1 : 0`.
Claim IDs: SF-2.
-/
def cnotB32 (a : U32) : U32 :=
  match a.toFin.val with
  | 0 => mkB32 1
  | _ => mkB32 0

/--
Write destination value register on execution.
Claim IDs: DI-3.
-/
def updateDestination (s : MachineState) (d : Destination) (result : U32) : MachineState :=
  match d with
  | Destination.reg r =>
      { s with valueRegs := fun r' => if r' == r then some result else s.valueRegs r' }

/--
Execution outcome classification for bounded unit.
- `executed`: full guard true path.
- `guardFalse`: complete guard false -> unchanged state.
Claim IDs: DI-2, DI-3, SF-5.
-/
inductive ExecOutcome where
  | executed : MachineState -> ExecOutcome
  | guardFalse : MachineState -> ExecOutcome

/--
Guarded single-step execution.
- Guard false -> unchanged state, no read of source.
- Guard true -> read source, compute logical negation, write destination.
- Missing guard predicate or missing source register yields `none` (partial).
Claims: SF-4, DI-2, DI-3, DI-4, OQ-4.
-/
def execCnotB32 (s : MachineState) (i : CnotB32Instruction) : Option ExecOutcome :=
  match evalGuard s i.guard with
  | none => none
  | some false => some (ExecOutcome.guardFalse s)
  | some true =>
      match evalSource s i.a with
      | some va => some (ExecOutcome.executed (updateDestination s i.d (cnotB32 va)))
      | none => none

/--
Convenience constructor for state-building examples (outside core semantics).
Claim IDs: architecture-only convenience.
-/
def mkState (valueRegBindings : List (RegId × U32)) (predRegBindings : List (PredId × Bool)) : MachineState :=
  { valueRegs := fun r => valueRegBindings.find? (fun b => b.1 == r) |>.map Prod.snd,
    predRegs := fun p => predRegBindings.find? (fun b => b.1 == p) |>.map Prod.snd }

end Spec2Lean.PTX.CnotB32
