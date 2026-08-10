--
-- Spec2Lean Lean formalization candidate — PTX ISA 9.3 `and.b16`
--
-- Bounded formalization unit: PTX ISA 9.3 `and.b16`.
-- Approved semantic interpretation:
--   candidates/ptx/9.3/units/and-b16/semantics/semantics-v2.json
--
-- Traceability claim IDs from that artifact: PTX-AND16-SEM2-001 .. PTX-AND16-SEM2-009
--
import Spec2Lean.Basic

namespace Spec2Lean
namespace PTX
namespace AndB16

-- 16-bit width from the bounded `.b16` form. (PTX-AND16-SEM2-003)
def b16Bits : Nat := 16

def b16DomainSize : Nat := 2 ^ b16Bits

-- 16-bit untyped bit-value domain. (PTX-AND16-SEM2-003)
structure B16 where
  toFin : Fin b16DomainSize
  deriving DecidableEq

instance : Repr B16 where
  reprPrec v _ := repr v.toFin.val

-- Register identifiers (name-based). (PTX-AND16-SEM2-001)
structure RegId where
  name : String
  deriving DecidableEq, Repr

-- Predicate-register identifiers (name-based). (PTX-AND16-SEM2-004)
structure PredId where
  name : String
  deriving DecidableEq, Repr

-- Destination operand: register only in this bounded unit (design/semantics excludes bit-bucket). 
-- PTX-AND16-SEM2-001, PTX-AND16-SEM2-008, PTX-AND16-SEM2-006
inductive Destination where
  | reg : RegId -> Destination
  deriving DecidableEq, Repr

-- Guard syntax variants present in PTX predication. (PTX-AND16-SEM2-004)
inductive Guard where
  | unguarded : Guard
  | atPos : PredId -> Guard
  | atNeg : PredId -> Guard
  deriving DecidableEq, Repr

-- Source forms in this bounded construction are register references only, matching unresolved-immediate design choice.
-- PTX-AND16-SEM2-006, PTX-AND16-SEM2-007
abbrev SourceA := RegId
abbrev SourceB := RegId

-- Operand order is d, a, b; bounded type is `.b16`. (PTX-AND16-SEM2-001, PTX-AND16-SEM2-003)
structure AndB16Instruction where
  guard : Guard
  d : Destination
  a : SourceA
  b : SourceB
  deriving DecidableEq, Repr

-- State used by bounded semantics: value registers and predicate registers only.
-- PTX-AND16-SEM2-002, PTX-AND16-SEM2-005, PTX-AND16-SEM2-008
structure MachineState where
  valueRegs : RegId -> Option B16
  predRegs : PredId -> Option Bool

-- Evaluate source `a` from register file in pre-state. (PTX-AND16-SEM2-002)
def evalSourceA (s : MachineState) (r : SourceA) : Option B16 :=
  s.valueRegs r

-- Evaluate source `b` from register file in pre-state. (PTX-AND16-SEM2-002)
def evalSourceB (s : MachineState) (r : SourceB) : Option B16 :=
  s.valueRegs r

-- Predication evaluation: false guard branch is no-op by PTX control-flow rule. (PTX-AND16-SEM2-004, PTX-AND16-SEM2-005)
def evalGuard (s : MachineState) : Guard -> Option Bool
  | Guard.unguarded => some true
  | Guard.atPos p => s.predRegs p
  | Guard.atNeg p =>
      match s.predRegs p with
      | some b => some (not b)
      | none => none

-- Bitwise AND over `.b16` values. (PTX-AND16-SEM2-002)
def andValue (x y : B16) : B16 :=
  { toFin :=
      ⟨Nat.land x.toFin.val y.toFin.val % b16DomainSize,
        Nat.mod_lt (Nat.land x.toFin.val y.toFin.val) (by decide : 0 < b16DomainSize)⟩ }

-- Destination register update only. (PTX-AND16-SEM2-002, PTX-AND16-SEM2-008)
def updateDestination (s : MachineState) (d : Destination) (value : B16) : MachineState :=
  match d with
  | Destination.reg r =>
      { s with
        valueRegs := fun r' => if r' == r then some value else s.valueRegs r' }

-- Outcomes: executed state update or explicit guard-false unchanged-state outcome.
-- PTX-AND16-SEM2-005
inductive ExecOutcome where
  | executed : MachineState -> ExecOutcome
  | guardFalse : MachineState -> ExecOutcome

def mkB16 (n : Nat) : B16 :=
  { toFin := Fin.mk (n % b16DomainSize) (Nat.mod_lt n (by decide : 0 < b16DomainSize)) }

def mkState (valueRegBindings : List (RegId × B16)) (predRegBindings : List (PredId × Bool)) : MachineState :=
  { valueRegs := fun r => valueRegBindings.find? (fun b => b.1 == r) |>.map Prod.snd
    , predRegs := fun p => predRegBindings.find? (fun b => b.1 == p) |>.map Prod.snd }

-- Guarded execution of the bounded and.b16 semantics: if guard true evaluate a,b and write d.
-- PTX-AND16-SEM2-002, PTX-AND16-SEM2-004, PTX-AND16-SEM2-005
/-- Partial lookups remain partial (`Option.none`) rather than invented traps/errors. -/
def execAndB16 (s : MachineState) (i : AndB16Instruction) : Option ExecOutcome :=
  match evalGuard s i.guard with
  | none => none
  | some false => some (ExecOutcome.guardFalse s)
  | some true =>
      match evalSourceA s i.a, evalSourceB s i.b with
      | some va, some vb =>
          some (ExecOutcome.executed (updateDestination s i.d (andValue va vb)))
      | _, _ => none

-- Relational counterpart to the executable semantics.
-- PTX-AND16-SEM2-002
inductive AndB16Step : MachineState -> AndB16Instruction -> MachineState -> Prop where
  | guardFalse (s : MachineState) (i : AndB16Instruction) :
      evalGuard s i.guard = some false -> AndB16Step s i s
  | executed (s : MachineState) (i : AndB16Instruction) (va vb : B16) :
      evalGuard s i.guard = some true ->
      evalSourceA s i.a = some va ->
      evalSourceB s i.b = some vb ->
      AndB16Step s i (updateDestination s i.d (andValue va vb))

end AndB16
end PTX
end Spec2Lean
