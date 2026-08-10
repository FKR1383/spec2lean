/-
Spec2Lean Lean formalization candidate — PTX ISA 9.3 `or.b32`

Bounded formalization unit : PTX ISA 9.3 `or.b32` (syntax form
`or.type d, a, b;` with family type `.b32`, plus optional predication).

Approved semantic interpretation :
  candidates/ptx/9.3/units/or-b32/semantics/semantics-v1.json
  (interpretation_id ptx-9.3-or-b32-semantics-v1)
Gate B record               : reviews/ptx-or-b32/gate-b/ptx-or-b32-b-approval-v1.json
                              (decision: approved)
Gate A record               : reviews/ptx-or-b32/gate-a/ptx-or-b32-a-approval-v1.json
                              (decision: approved)
Architecture reference      : candidates/ptx/9.3/units/or-b32/architecture/foundation-v4.md
Primary source bundle       : candidates/ptx/9.3/units/or-b32/source-bundles/source-bundle-v2.json

Scope:
- Only the bounded form `or.b32 d, a, b;` is in scope.
- Operand order is `d, a, b` where `a` and `b` are sources.
- In this bounded unit, source1 is register-only and source2 is register or immediate,
  matching the approved architecture/semantics claim set.
- Optional guard is `@p` / `@!p`; false guard means no state change.
- No exceptional behavior is modeled; undefined/malformed lookups are represented as
  partial execution (`none`), not as an invented error.
- No theorems are included in this stage.

Traceability: each declaration has comments pointing to
`candidates/ptx/9.3/units/or-b32/semantics/semantics-v1.json` claim IDs.
-/

import Spec2Lean.Basic

namespace Spec2Lean.PTX.OrB32

-- PTX-OR-SEM1-001 / PTX-OR-SEM1-005: `.b32` width is 32.
-- PTX-OR-SEM1-005 uses 32-bit fixed-domain bit-wise OR.
def b32Bits : Nat := 32

-- Domain cardinality for 32-bit bit patterns.
def b32DomainSize : Nat := 2 ^ b32Bits

-- PTX-OR-SEM1-005: values are 32-bit untyped bit patterns.
structure B32 where
  toFin : Fin b32DomainSize
  deriving DecidableEq

instance : Repr B32 where
  reprPrec v _ := repr v.toFin.val

-- PTX-OR-SEM1-004: register references use register identifiers.
structure RegId where
  name : String
  deriving DecidableEq, Repr

-- PTX-OR-SEM1-006: predicate register references are modeled as names.
structure PredId where
  name : String
  deriving DecidableEq, Repr

-- PTX-9.3-OR-SEM1-SEM-SEM: source1 register-only, source2 reg or immediate.
inductive Source1Operand where
  | reg : RegId -> Source1Operand
  deriving DecidableEq, Repr

inductive Source2Operand where
  | reg : RegId -> Source2Operand
  | imm : B32 -> Source2Operand
  deriving DecidableEq, Repr

-- PTX-9.3-OR-SEM1-001: destination is register or bit bucket `_`.
inductive Destination where
  | reg : RegId -> Destination
  | bitBucket : Destination
  deriving DecidableEq, Repr

-- PTX-OR-SEM1-006, PTX-9.3-OR-013: predication forms.
inductive Guard where
  | unguarded : Guard
  | atPos : PredId -> Guard
  | atNeg : PredId -> Guard
  deriving DecidableEq, Repr

-- PTX-OR-SEM1-003: bounded unit is `.b32` only.
inductive OrB32Type where
  | b32 : OrB32Type
  deriving DecidableEq, Repr

-- PTX-OR-SEM1-007: state has value and predicate maps in this bounded unit.
structure MachineState where
  valueRegs : RegId -> Option B32
  predRegs : PredId -> Option Bool

-- PTX-OR-SEM1-003/004: instruction shape (`d, a, b`).
structure OrB32Instruction where
  type : OrB32Type
  guard : Guard
  d : Destination
  a : Source1Operand
  b : Source2Operand
  deriving DecidableEq, Repr

-- PTX-OR-SEM1-005: explicit evaluation of source1 from state.
def evalSource1 (s : MachineState) : Source1Operand -> Option B32
  | Source1Operand.reg r => s.valueRegs r

-- PTX-OR-SEM1-005: explicit evaluation of source2 from state/immediate.
def evalSource2 (s : MachineState) : Source2Operand -> Option B32
  | Source2Operand.reg r => s.valueRegs r
  | Source2Operand.imm v => some v

-- PTX-9.3-OR-011/012/013, PTX-OR-SEM1-006: complete guard evaluation.
def evalGuard (s : MachineState) : Guard -> Option Bool
  | Guard.unguarded => some true
  | Guard.atPos p => s.predRegs p
  | Guard.atNeg p =>
      match s.predRegs p with
      | some b => some (not b)
      | none => none

-- PTX-OR-SEM1-005: `d = a | b`.
def orValue (a b : B32) : B32 :=
  let raw : UInt32 := UInt32.ofNat a.toFin.val ||| UInt32.ofNat b.toFin.val
  { toFin := Fin.mk raw.toNat (by simpa [b32Bits, b32DomainSize] using (UInt32.toNat_lt raw)) }

-- PTX-OR-SEM1-002/005: destination update writes only destination register or no-op.
def updateDestination (s : MachineState) (d : Destination) (result : B32) : MachineState :=
  match d with
  | Destination.reg r =>
      { s with valueRegs := fun r' => if r' == r then some result else s.valueRegs r' }
  | Destination.bitBucket => s

-- PTX-OR-SEM1-006: explicit outcome carrier for this executable model.
inductive ExecOutcome where
  | executed : MachineState -> ExecOutcome
  | guardFalse : MachineState -> ExecOutcome

-- PTX-OR-SEM1-006 / PTX-9.3-OR-013: guarded execution relation with partial lookups.
def execOrB32 (s : MachineState) (i : OrB32Instruction) : Option ExecOutcome :=
  match evalGuard s i.guard with
  | none => none
  | some false => some (ExecOutcome.guardFalse s)
  | some true =>
      match evalSource1 s i.a, evalSource2 s i.b with
      | some va, some vb =>
          some (ExecOutcome.executed (updateDestination s i.d (orValue va vb)))
      | _, _ => none

-- PTX-OR-SEM1-005 / PTX-OR-SEM1-006: relational form of one-step semantics.
inductive OrB32Step : MachineState -> OrB32Instruction -> MachineState -> Prop where
  | guardFalse :
      (s : MachineState) -> (i : OrB32Instruction) ->
      evalGuard s i.guard = some false ->
      OrB32Step s i s
  | executed :
      (s : MachineState) -> (i : OrB32Instruction) -> (va vb : B32) ->
      evalGuard s i.guard = some true ->
      evalSource1 s i.a = some va ->
      evalSource2 s i.b = some vb ->
      OrB32Step s i (updateDestination s i.d (orValue va vb))

-- PTX-OR-SEM1-005: utility constructor.
def mkB32 (n : Nat) : B32 :=
  { toFin := Fin.mk (n % b32DomainSize) (Nat.mod_lt n (by decide : 0 < b32DomainSize)) }

-- PTX-OR-SEM1-005: utility state constructor for examples/diagnostics.
def mkState
    (valueRegBindings : List (RegId × B32))
    (predRegBindings : List (PredId × Bool)) : MachineState :=
  { valueRegs := fun r => valueRegBindings.find? (fun b => b.1 == r) |>.map Prod.snd
    , predRegs := fun p => predRegBindings.find? (fun b => b.1 == p) |>.map Prod.snd }

end Spec2Lean.PTX.OrB32
