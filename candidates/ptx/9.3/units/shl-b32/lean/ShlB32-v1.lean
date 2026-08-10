 /-
Spec2Lean Lean formalization candidate — PTX ISA 9.3 `shl.b32`.

Bounded formalization unit: `shl.b32`.
Approved semantic interpretation:
  candidates/ptx/9.3/units/shl-b32/semantics/semantics-v1.json
  (interpretation_id ptx-9.3-shl-b32-semantics-v1)

Gate-B-stage scope: no theorems in this artifact.

Traceability summary:
- Semantic claim IDs: PTX-SHL-SEM1-001 .. PTX-SHL-SEM1-010
- Open questions/GAP references: AMB-1, AMB-2, AMB-3
- Evidence fragment IDs: PTX-9.3-SHL-001 .. PTX-9.3-SHL-014
- Required namespace: Spec2Lean.PTX.ShlB32
- Import: Spec2Lean.Basic
- State model: partial lookup on undefined identifiers gives `none`.
-/

import Spec2Lean.Basic

namespace Spec2Lean.PTX.ShlB32

-- PTX-SHL-SEM1-003: `.b32` is the bounded form.
def b32Bits : Nat := 32

-- PTX-SHL-SEM1-001 and PTX-SHL-SEM1-008: finite 32-bit value domain size.
def b32DomainSize : Nat := 2 ^ b32Bits

-- PTX-9.3-SHL-001/002: explicit 32-bit untyped value representation.
structure B32 where
  toFin : Fin b32DomainSize
  deriving DecidableEq

instance : Repr B32 where
  reprPrec v _ := repr v.toFin.val

-- PTX-SHL-SEM1-010: bounded register identifiers.
structure RegId where
  name : String
  deriving DecidableEq, Repr

-- PTX-9.3-SHL-012: predicate-register identifiers.
structure PredId where
  name : String
  deriving DecidableEq, Repr

-- PTX-SHL-SEM1-004: source-1 read as value register.
inductive SourceOperand where
  | reg : RegId -> SourceOperand
  deriving DecidableEq, Repr

-- PTX-SHL-SEM1-004 and bounded architecture: destination is an updatable register.
inductive Destination where
  | reg : RegId -> Destination
  deriving DecidableEq, Repr

-- PTX-SHL-SEM1-006: guard forms (`none`/`@p`/`@!p`).
inductive Guard where
  | unguarded : Guard
  | atPos : PredId -> Guard
  | atNeg : PredId -> Guard
  deriving DecidableEq, Repr

-- PTX-SHL-SEM1-003: bounded type specifier.
inductive ShlTypeSpecifier where
  | b32 : ShlTypeSpecifier
  deriving DecidableEq, Repr

-- PTX-SHL-SEM1-009 and shared minimal-state scope.
structure MachineState where
  valueRegs : RegId -> Option B32
  predRegs : PredId -> Option Bool

-- PTX-9.3-SHL-003 / PTX-SHL-SEM1-004 / PTX-SHL-SEM1-001
structure ShlB32Instruction where
  type : ShlTypeSpecifier
  guard : Guard
  d : Destination
  a : SourceOperand
  b : SourceOperand
  deriving DecidableEq, Repr

-- PTX-9.3-SHL-004/007: source read from the pre-state value-register file.
def readSource (s : MachineState) : SourceOperand -> Option B32
  | SourceOperand.reg r => s.valueRegs r

-- PTX-9.3-SHL-012/013 and PTX-SHL-SEM1-006.
def evalGuard (s : MachineState) : Guard -> Option Bool
  | Guard.unguarded => some true
  | Guard.atPos p => s.predRegs p
  | Guard.atNeg p =>
      match s.predRegs p with
      | some b => some (not b)
      | none => none

-- PTX-SHL-SEM1-001 and AMB-1: clamp shift count to 32 when it exceeds 32.
def clampShiftAmount (n : Nat) : Nat :=
  Nat.min n b32Bits

-- PTX-9.3-SHL-004 and -006: `d = a << clamp(b, 32)` with zero-fill behavior.
def shlValue (a b : B32) : B32 :=
  let amt : Nat := clampShiftAmount b.toFin.val
  let v : Nat := (a.toFin.val * (2 ^ amt)) % b32DomainSize
  { toFin := Fin.mk v (by simpa [v, b32Bits, b32DomainSize] using Nat.mod_lt (a.toFin.val * (2 ^ amt)) (by decide : 0 < b32DomainSize)) }

-- PTX-SHL-SEM1-007 and PTX-SHL-SEM1-006: write only destination register.
def updateDestination (s : MachineState) (d : Destination) (value : B32) : MachineState :=
  match d with
  | Destination.reg r =>
      { s with valueRegs := fun r' => if r' == r then some value else s.valueRegs r' }

-- PTX-SHL-SEM1-008: no explicit exceptional behavior is modeled.
inductive ExecOutcome where
  | executed : MachineState -> ExecOutcome
  | guardFalse : MachineState -> ExecOutcome

-- PTX-9.3-SHL-011/013/012, PTX-SHL-SEM1-008: predication and state read/write order.
def execShlB32 (s : MachineState) (i : ShlB32Instruction) : Option ExecOutcome :=
  match evalGuard s i.guard with
  | none => none
  | some false => some (ExecOutcome.guardFalse s)
  | some true =>
      match readSource s i.a, readSource s i.b with
      | some va, some vb => some (ExecOutcome.executed (updateDestination s i.d (shlValue va vb)))
      | _, _ => none

-- Relational form for one-step bounded semantics.
inductive ShlB32Step : MachineState -> ShlB32Instruction -> MachineState -> Prop where
  | guardFalse : (s : MachineState) -> (i : ShlB32Instruction) ->
      evalGuard s i.guard = some false -> ShlB32Step s i s
  | executed : (s : MachineState) -> (i : ShlB32Instruction) ->
      (va vb : B32) ->
      evalGuard s i.guard = some true ->
      readSource s i.a = some va ->
      readSource s i.b = some vb ->
      ShlB32Step s i (updateDestination s i.d (shlValue va vb))

-- Helpers (non-semantic examples/constructors).
def mkB32 (n : Nat) : B32 :=
  { toFin := Fin.mk (n % b32DomainSize) (Nat.mod_lt n (by decide : 0 < b32DomainSize)) }

-- Convenience value-register state constructor.
def mkState (valueRegBindings : List (RegId × B32)) (predRegBindings : List (PredId × Bool)) : MachineState :=
  { valueRegs := fun r => valueRegBindings.find? (fun b => b.1 == r) |>.map Prod.snd,
    predRegs := fun p => predRegBindings.find? (fun b => b.1 == p) |>.map Prod.snd }

end Spec2Lean.PTX.ShlB32