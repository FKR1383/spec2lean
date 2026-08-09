import Spec2Lean.Basic

namespace Spec2Lean
namespace PTX
namespace Core

/-!
# Shared PTX Core

Reusable formal infrastructure for bounded scalar PTX units.

This module intentionally contains only representation and execution machinery
that is common across multiple already-reviewed PTX units. Instruction-specific
operand legality, operations, syntax, and semantic claims remain outside Core.

The purpose of this extraction is code reuse, proof reuse, and reduced
per-instruction generation cost. It does not introduce new PTX semantics.
-/

def b32Bits : Nat := 32

def b32DomainSize : Nat := 2 ^ b32Bits

structure B32 where
  toFin : Fin b32DomainSize
deriving DecidableEq

instance : Repr B32 where
  reprPrec v _ := repr v.toFin.val

structure RegId where
  name : String
deriving DecidableEq, Repr

structure PredId where
  name : String
deriving DecidableEq, Repr

inductive Destination where
  | reg : RegId -> Destination
  | bitBucket : Destination
deriving DecidableEq, Repr

inductive Guard where
  | unguarded : Guard
  | atPos : PredId -> Guard
  | atNeg : PredId -> Guard
deriving DecidableEq, Repr

structure MachineState where
  valueRegs : RegId -> Option B32
  predRegs : PredId -> Option Bool

def evalGuard (s : MachineState) : Guard -> Option Bool
  | Guard.unguarded => some true
  | Guard.atPos p => s.predRegs p
  | Guard.atNeg p =>
      match s.predRegs p with
      | some b => some (not b)
      | none => none

def updateDestination
    (s : MachineState)
    (d : Destination)
    (value : B32) :
    MachineState :=
  match d with
  | Destination.reg r =>
      {
        s with
        valueRegs :=
          fun r' =>
            if r' == r then
              some value
            else
              s.valueRegs r'
      }
  | Destination.bitBucket =>
      s

inductive ExecOutcome where
  | executed : MachineState -> ExecOutcome
  | guardFalse : MachineState -> ExecOutcome

def mkB32 (n : Nat) : B32 :=
  {
    toFin :=
      Fin.mk
        (n % b32DomainSize)
        (Nat.mod_lt n (by decide : 0 < b32DomainSize))
  }

def mkState
    (valueRegBindings : List (RegId × B32))
    (predRegBindings : List (PredId × Bool)) :
    MachineState :=
  {
    valueRegs :=
      fun r =>
        valueRegBindings
          |>.find? (fun b => b.1 == r)
          |>.map Prod.snd

    predRegs :=
      fun p =>
        predRegBindings
          |>.find? (fun b => b.1 == p)
          |>.map Prod.snd
  }

end Core
end PTX
end Spec2Lean
