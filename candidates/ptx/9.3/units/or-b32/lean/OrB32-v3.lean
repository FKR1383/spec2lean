/-
Spec2Lean Lean formalization candidate — PTX ISA 9.3 `or.b32`

Bounded formalization unit : PTX ISA 9.3 `or.b32`
Scoped syntax: `or.b32 d, a, b;` with optional predication `@p`/`@!p`.

Approved semantics: candidates/ptx/9.3/units/or-b32/semantics/semantics-v1.json
  (interpretation_id ptx-9.3-or-b32-semantics-v1)
Gate B record               : reviews/ptx-or-b32/gate-b/ptx-or-b32-b-approval-v1.json
Architecture reference      : candidates/ptx/9.3/units/or-b32/architecture/foundation-v4.md

Scope:
- Unit-internal form only: `or.b32 d, a, b;`.
- Operand order is `d, a, b`.
- In this bounded unit, source1 is register-only; source2 is register or immediate.
- Destination is register or bit bucket `_`.
- No explicit error/exception behavior for this bounded form; missing required reads yield partial
  execution via `none`.
- No theorems in this stage.

Every declaration below is bounded by the approved semantics and architecture choices.
-/

import Spec2Lean.Basic

namespace Spec2Lean.PTX.OrB32

-- PTX-OR-SEM1-001/069: `.b32` payload width.
def b32Bits : Nat := 32

def b32DomainSize : Nat := 2 ^ b32Bits

-- PTX-OR-SEM1-002/005: finite 32-bit untyped value domain.
structure B32 where
  toFin : Fin b32DomainSize
  deriving DecidableEq

-- Print the numeric value of B32 for examples/diagnostics.
instance : Repr B32 where
  reprPrec v _ := repr v.toFin.val

-- Registers are referenced by names.
structure RegId where
  name : String
  deriving DecidableEq, Repr

-- Predicate registers are modeled as named identifiers with Bool runtime values.
structure PredId where
  name : String
  deriving DecidableEq, Repr

-- PTX-OR-SEM1-005 + architecture D-3 (source-1 register-only in bounded scope).
inductive Source1Operand where
  | reg : RegId -> Source1Operand
  deriving DecidableEq, Repr

-- PTX-OR-SEM1-005 + architecture D-2 (bounded source-2 supports register or immediate).
inductive Source2Operand where
  | reg : RegId -> Source2Operand
  | imm : B32 -> Source2Operand
  deriving DecidableEq, Repr

-- PTX-PTX-2 (inherited) + PTX-9.3-OR-013: destination is register or bit-bucket.
inductive Destination where
  | reg : RegId -> Destination
  | bitBucket : Destination
  deriving DecidableEq, Repr

-- PTX-OR-SEM1-006: predication forms.
inductive Guard where
  | unguarded : Guard
  | atPos : PredId -> Guard
  | atNeg : PredId -> Guard
  deriving DecidableEq, Repr

-- PTX-OR-SEM1-001/003: bounded type specifier is `.b32`.
inductive OrTypeSpecifier where
  | b32 : OrTypeSpecifier
  deriving DecidableEq, Repr

-- Minimal machine state used by approved bounded semantics.
structure MachineState where
  valueRegs : RegId -> Option B32
  predRegs : PredId -> Option Bool

-- PTX-OR-SEM1-004: well-formed instruction shape (`d, a, b`).
structure OrB32Instruction where
  type : OrTypeSpecifier
  guard : Guard
  d : Destination
  a : Source1Operand
  b : Source2Operand
  deriving DecidableEq, Repr

-- PTX-OR-SEM1-005: source evaluation.
def evalSource1 (s : MachineState) : Source1Operand -> Option B32
  | Source1Operand.reg r => s.valueRegs r

-- PTX-OR-SEM1-005: source2 evaluation; immediates are constants.
def evalSource2 (s : MachineState) : Source2Operand -> Option B32
  | Source2Operand.reg r => s.valueRegs r
  | Source2Operand.imm v => some v

-- PTX-OR-SEM1-006: guard evaluation (partial when predicate state missing).
def evalGuard (s : MachineState) : Guard -> Option Bool
  | Guard.unguarded => some true
  | Guard.atPos p => s.predRegs p
  | Guard.atNeg p =>
      match s.predRegs p with
      | some b => some (not b)
      | none => none

-- PTX-OR-SEM1-005: compute bitwise OR on 32-bit values.
def orValue (a b : B32) : B32 :=
  let raw : UInt32 := UInt32.ofNat a.toFin.val ||| UInt32.ofNat b.toFin.val
  { toFin := Fin.mk raw.toNat (by simpa [b32Bits, b32DomainSize] using (UInt32.toNat_lt raw)) }

-- PTX-OR-SEM1-005: destination update is local to the target register; `_` is no-op.
def updateDestination (s : MachineState) (d : Destination) (result : B32) : MachineState :=
  match d with
  | Destination.reg r =>
      { s with valueRegs := fun r' => if r' == r then some result else s.valueRegs r' }
  | Destination.bitBucket => s

-- PTX-OR-SEM1-006: executable outcome shape for the guarded step.
inductive ExecOutcome where
  | executed : MachineState -> ExecOutcome
  | guardFalse : MachineState -> ExecOutcome

-- PTX-OR-SEM1-005/006/008: guarded execution with partial semantics for missing lookups.
def execOrB32 (s : MachineState) (i : OrB32Instruction) : Option ExecOutcome :=
  match evalGuard s i.guard with
  | none => none
  | some false => some (ExecOutcome.guardFalse s)
  | some true =>
      match evalSource1 s i.a, evalSource2 s i.b with
      | some va, some vb => some (ExecOutcome.executed (updateDestination s i.d (orValue va vb)))
      | _, _ => none

-- PTX-OR-SEM1-005/006: relation form of one-step semantics.
inductive OrB32Step : MachineState -> OrB32Instruction -> MachineState -> Prop where
  | guardFalse :
      (s : MachineState) ->
      (i : OrB32Instruction) ->
      evalGuard s i.guard = some false ->
      OrB32Step s i s
  | executed :
      (s : MachineState) ->
      (i : OrB32Instruction) ->
      (va vb : B32) ->
      evalGuard s i.guard = some true ->
      evalSource1 s i.a = some va ->
      evalSource2 s i.b = some vb ->
      OrB32Step s i (updateDestination s i.d (orValue va vb))

-- Utility constructor, useful for tests/examples in later stages.
def mkB32 (n : Nat) : B32 :=
  { toFin := Fin.mk (n % b32DomainSize) (Nat.mod_lt n (by decide : 0 < b32DomainSize)) }

-- Utility state constructor from finite bindings.
def mkState
    (valueRegBindings : List (RegId × B32))
    (predRegBindings : List (PredId × Bool)) : MachineState :=
  { valueRegs := fun r => valueRegBindings.find? (fun b => b.1 == r) |>.map Prod.snd
    , predRegs := fun p => predRegBindings.find? (fun b => b.1 == p) |>.map Prod.snd }

end Spec2Lean.PTX.OrB32
