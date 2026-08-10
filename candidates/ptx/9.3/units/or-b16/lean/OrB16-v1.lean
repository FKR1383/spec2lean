/-
Gate-B-aligned Lean formalization for PTX ISA 9.3 bounded unit `or.b16`.

Bounded formalization unit: or.b16
Approved semantic artifact: candidates/ptx/9.3/units/or-b16/semantics/semantics-v2.json
(interpretation_id: ptx-9.3-or-b16-semantics-v2)

Enumerated approved semantic claim IDs used below:
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
- SF-ORB16-011

Evidence fragments referenced (for traceability comments below):
PTX-9.3-ORB16-001 through PTX-9.3-ORB16-010, PTX-9.3-ORB16-013, PTX-9.3-ORB16-014.

Lean file path: candidates/ptx/9.3/units/or-b16/lean/OrB16-v1.lean
-/

import Spec2Lean.Basic

namespace Spec2Lean.PTX.OrB16

-- SF-ORB16-001 (or family syntax) and SF-ORB16-003 (16-bit form): bit-width for this bounded unit.
-- SF-ORB16-010 (fundamental b16 support).
def b16Bits : Nat := 16

-- SF-ORB16-010 and PTX-9.3-ORB16-010.
def b16DomainSize : Nat := 2 ^ b16Bits

-- SF-ORB16-003 (runtime representation in bounded unit, exact bits preserved).
structure B16 where
  toFin : Fin b16DomainSize
  deriving DecidableEq, Repr

-- SF-ORB16-011 + PTX-9.3-ORB16-012 (register-style identifiers in PTX).
structure RegId where
  name : String
  deriving DecidableEq, Repr

-- SF-ORB16-011 + PTX-9.3-ORB16-011 (predicate identifiers in PTX).
structure PredId where
  name : String
  deriving DecidableEq, Repr

-- SF-ORB16-001 (source1 position exists and is a source operand).
inductive SourceA where
  | reg : RegId → SourceA
  deriving DecidableEq, Repr

-- SF-ORB16-001/004 (source2 position exists and may be register or immediate).
inductive SourceB where
  | reg : RegId → SourceB
  | imm : B16 → SourceB
  deriving DecidableEq, Repr

-- SF-ORB16-001 (destination/result role) and SF-ORB16-005 (bit-bucket may be used).
inductive Destination where
  | reg : RegId → Destination
  | bitBucket : Destination
  deriving DecidableEq, Repr

-- SF-ORB16-006 (optional predication guard forms).
inductive Guard where
  | none : Guard
  | atPos : PredId → Guard
  | atNeg : PredId → Guard
  deriving DecidableEq, Repr

-- SF-ORB16-001 and SF-ORB16-002 (register + predicate state are relevant per source semantics).
structure MachineState where
  valueRegs : RegId → Option B16
  predRegs : PredId → Option Bool

-- SF-ORB16-001 (operand roles/order d, a, b).
-- SF-ORB16-003 (bounded to `.b16`).
-- SF-ORB16-006 (no modifiers in bounded constructor slice).
inductive OrTypeSpecifier where
  | b16 : OrTypeSpecifier
  deriving DecidableEq, Repr

-- SF-ORB16-001/002/004/005 (operand shape and optional predicate).
structure OrB16Instruction where
  type : OrTypeSpecifier
  guard : Guard
  d : Destination
  a : SourceA
  b : SourceB
  deriving DecidableEq, Repr

-- SF-ORB16-006: evaluate guard with predication semantics.
def evalGuard (s : MachineState) : Guard → Option Bool
  | Guard.none => some true
  | Guard.atPos p => s.predRegs p
  | Guard.atNeg p =>
      match s.predRegs p with
      | some b => some (not b)
      | none => none

-- SF-ORB16-001/004: source reads use pre-state values.
def evalSourceA (s : MachineState) : SourceA → Option B16
  | SourceA.reg r => s.valueRegs r

def evalSourceB (s : MachineState) : SourceB → Option B16
  | SourceB.reg r => s.valueRegs r
  | SourceB.imm v => some v

-- SF-ORB16-003 (bit-wise OR) and SF-ORB16-004 (same-size behavior is preserved by bounded domain).
def orValue (x y : B16) : B16 :=
  let raw : UInt16 := UInt16.ofNat x.toFin.val ||| UInt16.ofNat y.toFin.val
  { toFin := Fin.mk raw.toNat (by simpa [b16Bits, b16DomainSize] using raw.toNat_lt) }

-- SF-ORB16-005 (destination update writes only destination register, `_` is sink).
def updateDestination (s : MachineState) : Destination → B16 → MachineState
  | Destination.reg r, value =>
      { s with valueRegs := fun r' => if r' == r then some value else s.valueRegs r' }
  | Destination.bitBucket, _ => s

-- SF-ORB16-006 (guard false ⇒ no state change); SF-ORB16-007 (partial reads are stuck behavior).
inductive ExecOutcome where
  | executed : MachineState → ExecOutcome
  | notExecuted : MachineState → ExecOutcome

-- SF-ORB16-006/007: total one-step execution relation with partiality as `none`.
def execOrB16 (s : MachineState) (i : OrB16Instruction) : Option ExecOutcome :=
  match evalGuard s i.guard with
  | none => none
  | some false => some (ExecOutcome.notExecuted s)
  | some true =>
      match evalSourceA s i.a, evalSourceB s i.b with
      | some va, some vb => some (ExecOutcome.executed (updateDestination s i.d (orValue va vb)))
      | _, _ => none

-- SF-ORB16-006/007: relational statement equivalent to executable semantics.
def OrB16Step (s : MachineState) (i : OrB16Instruction) (s' : MachineState) : Prop :=
  execOrB16 s i = some (ExecOutcome.executed s') ∨ execOrB16 s i = some (ExecOutcome.notExecuted s')

-- Utility constructor for immediate literals in this bounded grammar.
def mkB16 (n : Nat) : B16 :=
  { toFin := Fin.mk (n % b16DomainSize) (Nat.mod_lt n (by decide : 0 < b16DomainSize)) }

-- Utility constructor for instruction states from association lists (for compact examples/tests).
def mkState
    (valueRegBindings : List (RegId × B16))
    (predRegBindings : List (PredId × Bool)) : MachineState :=
  { valueRegs :=
      fun r => valueRegBindings |>.find? (fun b => b.1 == r) |>.map Prod.snd
    predRegs :=
      fun p => predRegBindings |>.find? (fun b => b.1 == p) |>.map Prod.snd }

end Spec2Lean.PTX.OrB16
