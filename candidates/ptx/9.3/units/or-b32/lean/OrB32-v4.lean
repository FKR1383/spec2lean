
/-
Lean formalization candidate for PTX ISA 9.3 bounded unit `or.b32`.

Approved sources:
- Gate B semantics: candidates/ptx/9.3/units/or-b32/semantics/semantics-v1.json
  (interpretation_id: ptx-9.3-or-b32-semantics-v1)
- Architecture reference: candidates/ptx/9.3/units/or-b32/architecture/foundation-v4.md
- Source bundle: candidates/ptx/9.3/units/or-b32/source-bundles/source-bundle-v2.json
- Gate B approval: reviews/ptx-or-b32/gate-b/ptx-or-b32-b-approval-v1.json

Scope:
- Unit-specific form only: `or.b32 d, a, b;` with optional predicate guard `@p`/`@!p`.
- Operand order is `d, a, b`.
- In this bounded unit, `a` is register-only; `b` is register-or-immediate.
- Destination is register-or-bit-bucket `_`.
- No exceptions or traps are modeled; undefined lookups are partial (`none`).
-/

import Spec2Lean.Basic

namespace Spec2Lean.PTX.OrB32

-- PTX-OR-SEM1-001/005: .b32 form uses 32-bit values.
def b32Bits : Nat := 32

-- PTX-OR-SEM1-001: finite domain size for 32-bit bit patterns.
def b32DomainSize : Nat := 2 ^ b32Bits

-- PTX-OR-SEM1-005: explicit 32-bit value representation.
structure B32 where
  toFin : Fin b32DomainSize
  deriving DecidableEq

instance : Repr B32 where
  reprPrec v _ := repr v.toFin.val

-- PTX-OR-SEM1-004: register names as identifiers.
structure RegId where
  name : String
  deriving DecidableEq, Repr

-- Predicate names as identifiers.
structure PredId where
  name : String
  deriving DecidableEq, Repr

-- PTX-OR-SEM1-003/061: src1 is register-only by unit-bound architecture.
inductive Source1Operand where
  | reg : RegId → Source1Operand
  deriving DecidableEq, Repr

-- PTX-OR-SEM1-005: src2 is register or immediate.
inductive Source2Operand where
  | reg : RegId → Source2Operand
  | imm : B32 → Source2Operand
  deriving DecidableEq, Repr

-- PTX-OR-SEM1-002/013: destination is register or bit bucket `_`.
inductive Destination where
  | reg : RegId → Destination
  | bitBucket : Destination
  deriving DecidableEq, Repr

-- PTX-OR-SEM1-006: predication forms.
inductive Guard where
  | none : Guard
  | atPos : PredId → Guard
  | atNeg : PredId → Guard
  deriving DecidableEq, Repr

-- Bounded-in-unit type specifier is `.b32`.
inductive OrB32Type where
  | b32 : OrB32Type
  deriving DecidableEq, Repr

-- PTX-OR-SEM1-004/006/008: bounded state with register values + predicate values.
structure MachineState where
  valueRegs : RegId → Option B32
  predRegs : PredId → Option Bool

-- PTX-OR-SEM1-004/007: bounded instruction shape `d, a, b`.
structure OrB32Instruction where
  type : OrB32Type
  guard : Guard
  d : Destination
  a : Source1Operand
  b : Source2Operand
  deriving DecidableEq, Repr

-- PTX-OR-SEM1-005: source evaluation (read-before-write model).
def evalSource1 (s : MachineState) : Source1Operand → Option B32
  | Source1Operand.reg r => s.valueRegs r

-- PTX-OR-SEM1-005: source2 eval from register file or immediate constant.
def evalSource2 (s : MachineState) : Source2Operand → Option B32
  | Source2Operand.reg r => s.valueRegs r
  | Source2Operand.imm v => some v

-- PTX-OR-SEM1-006: guard evaluation (`none`/`@p`/`@!p`).
def evalGuard (s : MachineState) : Guard → Option Bool
  | Guard.none => some true
  | Guard.atPos p => s.predRegs p
  | Guard.atNeg p =>
    match s.predRegs p with
    | some b => some (not b)
    | none => none

-- PTX-OR-SEM1-005: `d = a | b` bitwise OR on 32-bit values.
def orValue (a b : B32) : B32 :=
  let raw : UInt32 := UInt32.ofNat a.toFin.val ||| UInt32.ofNat b.toFin.val
  { toFin := Fin.mk raw.toNat (by simpa [b32Bits, b32DomainSize] using (UInt32.toNat_lt raw)) }

-- PTX-OR-SEM1-005: destination update is local to destination register, or no-op for `_`.
def updateDestination (s : MachineState) (d : Destination) (result : B32) : MachineState :=
  match d with
  | Destination.reg r =>
      { s with valueRegs := fun r' => if r' == r then some result else s.valueRegs r' }
  | Destination.bitBucket => s

-- PTX-OR-SEM1-006: executable guarded effect with partial behavior.
inductive ExecOutcome where
  | executed : MachineState → ExecOutcome
  | notExecuted : MachineState → ExecOutcome

def execOrB32 (s : MachineState) (i : OrB32Instruction) : Option ExecOutcome :=
  match evalGuard s i.guard with
  | none => none
  | some false => some (ExecOutcome.notExecuted s)
  | some true =>
    match evalSource1 s i.a, evalSource2 s i.b with
    | some va, some vb =>
        some (ExecOutcome.executed (updateDestination s i.d (orValue va vb)))
    | _, _ => none

-- PTX-OR-SEM1-005/006: relation form of one-step semantics.
inductive OrB32Step : MachineState → OrB32Instruction → MachineState → Prop where
  | notExecuted :
      (s : MachineState) →
      (i : OrB32Instruction) →
      evalGuard s i.guard = some false →
      OrB32Step s i s
  | executed :
      (s : MachineState) →
      (i : OrB32Instruction) →
      (va vb : B32) →
      evalGuard s i.guard = some true →
      evalSource1 s i.a = some va →
      evalSource2 s i.b = some vb →
      OrB32Step s i (updateDestination s i.d (orValue va vb))

-- PTX-OR-SEM1-005: helper for examples.
def mkB32 (n : Nat) : B32 :=
  { toFin := Fin.mk (n % b32DomainSize) (Nat.mod_lt n (by decide : 0 < b32DomainSize)) }

def mkState
    (valueRegBindings : List (RegId × B32))
    (predRegBindings : List (PredId × Bool)) : MachineState :=
  { valueRegs := fun r => valueRegBindings.find? (fun b => b.1 == r) |>.map Prod.snd
    , predRegs := fun p => predRegBindings.find? (fun b => b.1 == p) |>.map Prod.snd }

end Spec2Lean.PTX.OrB32