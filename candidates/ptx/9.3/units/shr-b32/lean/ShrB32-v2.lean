import Spec2Lean.Basic

/-!
Bounded PTX formalization unit: `shr.b32` (spec 9.3)

Lean artifact path: candidates/ptx/9.3/units/shr-b32/lean/ShrB32-v2.lean
Source/semantics artifact: candidates/ptx/9.3/units/shr-b32/semantics/semantics-v1.json
interpretation_id: ptx-9.3-shr-b32-semantics-v1

Approved semantic claim IDs present in this artifact:
- PTX-SHR-SEM1-001
- PTX-SHR-SEM1-002
- PTX-SHR-SEM1-003
- PTX-SHR-SEM1-004
- PTX-SHR-SEM1-005
- PTX-SHR-SEM1-006
- PTX-SHR-SEM1-007
- PTX-SHR-SEM1-008
- PTX-SHR-SEM1-009
- PTX-SHR-SEM1-010
- PTX-SHR-SEM1-011
- PTX-SHR-SEM1-012
- PTX-SHR-SEM1-013
- PTX-SHR-SEM1-014
- PTX-SHR-SEM1-015
- OQ-1, OQ-2, OQ-3, OQ-4

Architecture design IDs relied on:
- D-1, D-2, D-3, D-4, D-5, D-7, D-8, D-10, DD-1, DD-2, DD-3

Open questions tracked in this file:
- OQ-1: whether `_` destination is admissible for `shr` syntax (unmodeled here).
- OQ-2: exact source-form classes for `a`/`b` (modeled as register or immediate here).
- OQ-3: clamp amount semantics relies on `N = 32` design resolution (DD-3).
- OQ-4: no-state-change on false guard is enforced for this bounded state.

Assumptions:
- no explicit exceptional/undefined/implementation-defined behavior is modeled (open questions retained).
- false predicate branch does not read sources and does not update any state.
- malformed/invalid predecessor conditions (missing predicate or missing source read) transition to `stuck`.
-/

namespace Spec2Lean.PTX.ShrB32

-- PTX-SHR-SEM1-003: bounded 32-bit family width.
def b32Bits : Nat := 32

-- PTX-SHR-SEM1-002 and PTX-SHR-SEM1-003: finite 32-bit machine-word domain.
def b32DomainSize : Nat := 2 ^ b32Bits

-- PTX-SHR-SEM1-011: bounded value representation for `.b32`.
structure B32 where
  toFin : Fin b32DomainSize
  deriving DecidableEq

instance : Repr B32 where
  reprPrec v _ := repr v.toFin.val

-- PTX-SHR-SEM1-002 and PTX-SHR-SEM1-008:
-- bounded register-name representation.
structure RegId where
  name : String
  deriving DecidableEq, Repr

-- PTX-SHR-SEM1-008 and PTX-SHR-SEM1-011:
-- bounded predicate-name representation.
structure PredId where
  name : String
  deriving DecidableEq, Repr

-- PTX-SHR-SEM1-001: three-operand form d, a, b.
-- PTX-SHR-SEM1-014: source classes are not fully specified, so this bounded model
-- includes register and immediate as source options.
inductive SourceOperand where
  | reg : RegId -> SourceOperand
  | imm : B32 -> SourceOperand
  deriving DecidableEq, Repr

-- PTX-SHR-SEM1-001 and D-4: destination is modeled as an updatable register.
-- `_` admissibility is left unresolved (OQ-1).
inductive Destination where
  | reg : RegId -> Destination
  deriving DecidableEq, Repr

-- PTX-SHR-SEM1-008: predication syntax forms.
inductive Guard where
  | unguarded : Guard
  | atPos : PredId -> Guard
  | atNeg : PredId -> Guard
  deriving DecidableEq, Repr

-- D-1 / PTX-SHR-SEM1-010: bounded instruction constructor.
inductive ShrTypeSpecifier where
  | b32 : ShrTypeSpecifier
  deriving DecidableEq, Repr

-- PTX-SHR-SEM1-001/002 and D-3/D-10:
-- minimal bounded machine state for this unit.
structure MachineState where
  valueRegs : RegId -> Option B32
  predRegs : PredId -> Option Bool

-- PTX-SHR-SEM1-010: constructor fields for this bounded instruction.
structure ShrB32Instruction where
  type : ShrTypeSpecifier
  guard : Guard
  d : Destination
  a : SourceOperand
  b : SourceOperand
  deriving DecidableEq, Repr

-- PTX-SHR-SEM1-004 and PTX-SHR-SEM1-005:
-- source evaluation from pre-state or immediates.
def readSource (s : MachineState) : SourceOperand -> Option B32
  | SourceOperand.reg r => s.valueRegs r
  | SourceOperand.imm v => some v

-- PTX-SHR-SEM1-008 and PTX-SHR-SEM1-012: complete guard evaluation.
def evalGuard (s : MachineState) : Guard -> Option Bool
  | Guard.unguarded => some true
  | Guard.atPos p => s.predRegs p
  | Guard.atNeg p =>
      match s.predRegs p with
      | some b => some (not b)
      | none => none

-- PTX-SHR-SEM1-005 and DD-3: shift amount is clamped for this bounded form.
def clampShiftAmount (n : Nat) : Nat := Nat.min n b32Bits

-- PTX-SHR-SEM1-011 and PTX-SHR-SEM1-003: zero-fill logical right shift on `.b32`.
def shrB32Value (a b : B32) : B32 :=
  let amt : Nat := clampShiftAmount b.toFin.val
  let shifted : Nat := Nat.shiftRight a.toFin.val amt
  { toFin := Fin.mk (shifted % b32DomainSize) (Nat.mod_lt shifted (by decide : 0 < b32DomainSize)) }

-- PTX-SHR-SEM1-002 and D-4/D-5:
-- only destination register updates are performed; other state components unchanged.
def updateDestination (s : MachineState) (d : Destination) (value : B32) : MachineState :=
  match d with
  | Destination.reg r =>
      { s with
        valueRegs := fun r' => if r' == r then some value else s.valueRegs r' }

-- PTX-SHR-SEM1-011, PTX-SHR-SEM1-012 and PTX-SHR-SEM1-013/014/015:
-- three-way execution shape: executed, guardFalse, and malformed/stuck.
inductive ExecOutcome where
  | executed : MachineState -> ExecOutcome
  | guardFalse : MachineState -> ExecOutcome
  | malformed : MachineState -> ExecOutcome

-- PTX-SHR-SEM1-011/012 and PTX-SHR-SEM1-013/014/015:
-- one-step executable semantics.
def execShrB32 (s : MachineState) (i : ShrB32Instruction) : Option ExecOutcome :=
  match evalGuard s i.guard with
  | none => some (ExecOutcome.malformed s)
  | some false => some (ExecOutcome.guardFalse s)
  | some true =>
      match readSource s i.a, readSource s i.b with
      | some va, some vb => some (ExecOutcome.executed (updateDestination s i.d (shrB32Value va vb)))
      | _, _ => some (ExecOutcome.malformed s)

-- PTX-SHR-SEM1-012: relational semantics.
inductive ShrB32Step : MachineState -> ShrB32Instruction -> MachineState -> Prop where
  | guardFalse : (s : MachineState) -> (i : ShrB32Instruction) ->
      evalGuard s i.guard = some false ->
      ShrB32Step s i s
  | executed : (s : MachineState) -> (i : ShrB32Instruction) ->
      (va vb : B32) ->
      evalGuard s i.guard = some true ->
      readSource s i.a = some va ->
      readSource s i.b = some vb ->
      ShrB32Step s i (updateDestination s i.d (shrB32Value va vb))
  | malformed : (s : MachineState) -> (i : ShrB32Instruction) ->
      (evalGuard s i.guard = none ∨
        readSource s i.a = none ∨
        readSource s i.b = none) ->
      ShrB32Step s i s

-- PTX-SHR-SEM1-003 and D-5:
def mkB32 (n : Nat) : B32 :=
  { toFin := Fin.mk (n % b32DomainSize) (Nat.mod_lt n (by decide : 0 < b32DomainSize)) }

-- PTX-SHR-SEM1-008 and D-4:
def mkState (valueRegBindings : List (RegId × B32)) (predRegBindings : List (PredId × Bool)) : MachineState :=
  { valueRegs := fun r => valueRegBindings.find? (fun b => b.1 == r) |>.map Prod.snd,
    predRegs := fun p => predRegBindings.find? (fun b => b.1 == p) |>.map Prod.snd }

end Spec2Lean.PTX.ShrB32