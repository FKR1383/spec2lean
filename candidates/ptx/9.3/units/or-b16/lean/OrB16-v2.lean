/-
Gate-B-aligned Lean formalization for PTX ISA 9.3 bounded unit `or.b16`.

Bounded formalization unit: or.b16
Approved semantic artifact: candidates/ptx/9.3/units/or-b16/semantics/semantics-v2.json
(interpretation_id: ptx-9.3-or-b16-semantics-v2)

Exact approved semantic IDs enumerated from this artifact:
- SF-ORB16-001
- SF-ORB16-002
- SF-ORB16-003
- SF-ORB16-004
- SF-ORB16-005
- SF-ORB16-006
- SF-ORB16-007
- SF-ORB16-008
- SF-ORB16-009
- SF-ORB16-010
- DI-ORB16-001
- DI-ORB16-002
- DI-ORB16-003
- DI-ORB16-004
- DI-ORB16-005
- DI-ORB16-006
- DD-ORB16-001
- DD-ORB16-002
- OQ-ORB16-01
- OQ-ORB16-02
- OQ-ORB16-03
- OQ-ORB16-04

Evidence fragments referenced (for comments below):
PTX-9.3-ORB16-001 through PTX-9.3-ORB16-014

Lean file path: candidates/ptx/9.3/units/or-b16/lean/OrB16-v2.lean
-/

import Spec2Lean.Basic

namespace Spec2Lean.PTX.OrB16

-- SF-ORB16-001, SF-ORB16-003, SF-ORB16-010: `.b16` width.
-- DI-ORB16-003: bounded form is 16-bit.
def b16Bits : Nat := 16

-- SF-ORB16-010: fundamental b16 support.
def b16DomainSize : Nat := 2 ^ b16Bits

-- SF-ORB16-003, SF-ORB16-010: runtime representation in bounded unit, exact bits preserved.
structure B16 where
  toFin : Fin b16DomainSize
  deriving DecidableEq, Repr

-- SF-ORB16-001 and SF-ORB16-002: register identifier.
structure RegId where
  name : String
  deriving DecidableEq, Repr

-- SF-ORB16-001 and SF-ORB16-002: predicate identifier.
structure PredId where
  name : String
  deriving DecidableEq, Repr

-- SF-ORB16-001: source-operand order includes `a`.
inductive SourceA where
  | reg : RegId → SourceA
  deriving DecidableEq, Repr

-- SF-ORB16-001/004 and OQ-ORB16-01/02: source2 role exists, immediate support unresolved.
-- Per approved semantics, only register `b` is modeled here; immediate is intentionally omitted.
inductive SourceB where
  | reg : RegId → SourceB
  deriving DecidableEq, Repr

-- SF-ORB16-001/002/005 and DD-ORB16-002: destination is `d` operand; `_` behavior is not asserted.
inductive Destination where
  | reg : RegId → Destination
  deriving DecidableEq, Repr

-- SF-ORB16-006/007: optional predication guard forms.
inductive Guard where
  | none : Guard
  | atPos : PredId → Guard
  | atNeg : PredId → Guard
  deriving DecidableEq, Repr

-- SF-ORB16-007 and DI-ORB16-001: machine state includes register and predicate components.
structure MachineState where
  valueRegs : RegId → Option B16
  predRegs : PredId → Option Bool

-- SF-ORB16-001 and DI-ORB16-001: optional predicate + 3-operand form.
inductive OrTypeSpecifier where
  | b16 : OrTypeSpecifier
  deriving DecidableEq, Repr

-- SF-ORB16-001/002/004/007 and DI-ORB16-002: operand order is d, a, b.
structure OrB16Instruction where
  type : OrTypeSpecifier
  guard : Guard
  d : Destination
  a : SourceA
  b : SourceB
  deriving DecidableEq, Repr

-- SF-ORB16-007 and DI-ORB16-001: guard evaluation with False no-op/true/negated forms.
def evalGuard (s : MachineState) : Guard → Option Bool
  | Guard.none => some true
  | Guard.atPos p => s.predRegs p
  | Guard.atNeg p =>
      match s.predRegs p with
      | some b => some (not b)
      | none => none

-- SF-ORB16-007 and DI-ORB16-001: source reads use pre-state values.
def evalSourceA (s : MachineState) : SourceA → Option B16
  | SourceA.reg r => s.valueRegs r

def evalSourceB (s : MachineState) : SourceB → Option B16
  | SourceB.reg r => s.valueRegs r

-- SF-ORB16-003/005/006 and SF-ORB16-008: bit-wise OR for bounded 16-bit operands.
def orValue (x y : B16) : B16 :=
  let raw : UInt16 := UInt16.ofNat x.toFin.val ||| UInt16.ofNat y.toFin.val
  { toFin := Fin.mk raw.toNat (by simpa [b16Bits, b16DomainSize] using raw.toNat_lt) }

-- SF-ORB16-005 and DI-ORB16-006: on execute, write only destination register.
def updateDestination (s : MachineState) : Destination → B16 → MachineState
  | Destination.reg r, value =>
      { s with valueRegs := fun r' => if r' == r then some value else s.valueRegs r' }

-- SF-ORB16-007, OQ-ORB16-03 and DI-ORB16-002: false guard ⇒ unchanged; no modeled '_' destination.
inductive ExecOutcome where
  | executed : MachineState → ExecOutcome
  | notExecuted : MachineState → ExecOutcome

-- DI-ORB16-006 and SF-ORB16-006: guarded one-step transition.
def execOrB16 (s : MachineState) (i : OrB16Instruction) : Option ExecOutcome :=
  match evalGuard s i.guard with
  | none => none
  | some false => some (ExecOutcome.notExecuted s)
  | some true =>
      match evalSourceA s i.a, evalSourceB s i.b with
      | some va, some vb => some (ExecOutcome.executed (updateDestination s i.d (orValue va vb)))
      | _, _ => none

-- SF-ORB16-007 and DI-ORB16-006: equivalent relation form.
def OrB16Step (s : MachineState) (i : OrB16Instruction) (s' : MachineState) : Prop :=
  execOrB16 s i = some (ExecOutcome.executed s') ∨ execOrB16 s i = some (ExecOutcome.notExecuted s')

-- Utility constructor for bounded constants.
def mkB16 (n : Nat) : B16 :=
  { toFin := Fin.mk (n % b16DomainSize) (Nat.mod_lt n (by decide : 0 < b16DomainSize)) }

-- Utility constructor for state from bindings.
def mkState
    (valueRegBindings : List (RegId × B16))
    (predRegBindings : List (PredId × Bool)) : MachineState :=
  { valueRegs :=
      fun r => valueRegBindings |>.find? (fun b => b.1 == r) |>.map Prod.snd
    predRegs :=
      fun p => predRegBindings |>.find? (fun b => b.1 == p) |>.map Prod.snd }

end Spec2Lean.PTX.OrB16
