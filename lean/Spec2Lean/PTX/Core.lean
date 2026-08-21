import Spec2Lean.Basic

namespace Spec2Lean
namespace PTX
namespace Core

/-!
# Shared PTX Core

Reusable Lean infrastructure for the human-approved PTX 9.3 bounded scalar
`.b32` value-register and predicate-register semantic environment.

The declarations preserve the API used by accepted units. Instruction-specific
syntax, operand-position legality, numeric interpretation, operation, and edge
cases remain in each instruction delta. This module is project modeling
infrastructure bound to approved shared semantics; it is not new NVIDIA prose.
-/

-- spec2lean: ptx.9.3.b32.domain-source, ptx.9.3.register.value-representation-design
def b32Bits : Nat := 32

-- spec2lean: ptx.9.3.b32.domain-source, ptx.9.3.register.value-representation-design
def b32DomainSize : Nat := 2 ^ b32Bits

-- spec2lean: ptx.9.3.b32.domain-source, ptx.9.3.register.value-representation-design
structure B32 where
  toFin : Fin b32DomainSize
deriving DecidableEq

instance : Repr B32 where
  reprPrec v _ := repr v.toFin.val

-- spec2lean: ptx.9.3.register.state-space-source, ptx.9.3.state.register-model-design
structure RegId where
  name : String
deriving DecidableEq, Repr

-- spec2lean: ptx.9.3.predication.applicability-source, ptx.9.3.state.register-model-design
structure PredId where
  name : String
deriving DecidableEq, Repr

-- spec2lean: ptx.9.3.register.state-space-source, ptx.9.3.bit-bucket.rule-source
inductive Destination where
  | reg : RegId -> Destination
  | bitBucket : Destination
deriving DecidableEq, Repr

-- spec2lean: ptx.9.3.predication.applicability-source, ptx.9.3.predication.false-guard-source
inductive Guard where
  | unguarded : Guard
  | atPos : PredId -> Guard
  | atNeg : PredId -> Guard
deriving DecidableEq, Repr

-- spec2lean: ptx.9.3.register.state-space-source, ptx.9.3.state.register-model-design, ptx.9.3.register.lookup-partial-design
structure MachineState where
  valueRegs : RegId -> Option B32
  predRegs : PredId -> Option Bool

-- spec2lean: ptx.9.3.register.value-representation-design, ptx.9.3.register.lookup-partial-design
inductive B32Source where
  | reg : RegId -> B32Source
  | immediate : B32 -> B32Source
deriving DecidableEq, Repr

-- spec2lean: ptx.9.3.register.value-representation-design, ptx.9.3.register.lookup-partial-design
def readB32 (s : MachineState) : B32Source -> Option B32
  | B32Source.reg r => s.valueRegs r
  | B32Source.immediate value => some value

-- spec2lean: ptx.9.3.predication.applicability-source, ptx.9.3.predication.false-guard-source, ptx.9.3.predication.false-guard-noop-derived
def evalGuard (s : MachineState) : Guard -> Option Bool
  | Guard.unguarded => some true
  | Guard.atPos p => s.predRegs p
  | Guard.atNeg p =>
      match s.predRegs p with
      | some b => some (not b)
      | none => none

-- spec2lean: ptx.9.3.state.register-model-design, ptx.9.3.bit-bucket.rule-source
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

-- spec2lean: ptx.9.3.predication.false-guard-noop-derived, ptx.9.3.state.register-model-design
inductive ExecOutcome where
  | executed : MachineState -> ExecOutcome
  | guardFalse : MachineState -> ExecOutcome

-- spec2lean: ptx.9.3.b32.domain-source, ptx.9.3.register.value-representation-design
def mkB32 (n : Nat) : B32 :=
  {
    toFin :=
      Fin.mk
        (n % b32DomainSize)
        (Nat.mod_lt n (by decide : 0 < b32DomainSize))
  }

-- spec2lean: ptx.9.3.state.register-model-design, ptx.9.3.register.lookup-partial-design
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
