/-
Gate-B-aligned Lean formalization for PTX ISA 9.3 bounded unit `or.b32`.

Bounded formalization unit: or.b32
Approved semantic artifact: candidates/ptx/9.3/units/or-b32/semantics/semantics-v1.json
(interpretation_id: ptx-9.3-or-b32-semantics-v1)

Traceability mapping requirements (for this immutable revision):
- Semantic claim IDs: PTX-OR-SEM1-001 through PTX-OR-SEM1-008
- Ambiguities: AMB-OR-1, AMB-OR-2
- Open questions: OQ-OR-1, OQ-OR-2
- Architecture design choices: D-2, D-3, D-4, D-5, D-6, D-7
- Evidence fragment IDs: PTX-9.3-OR-001 .. PTX-9.3-OR-016
- Lean path constraints: unit namespace Spec2Lean.PTX.OrB32, import only Spec2Lean.Basic
- Human-reported unresolved mapping question: no-op destination support for `_` is inherited from generic PTX syntax and recorded as a bounded design-evidence gap (AMB-OR-2).

Lean file path: candidates/ptx/9.3/units/or-b32/lean/OrB32-v6.lean
-/

import Spec2Lean.Basic

namespace Spec2Lean.PTX.OrB32

-- PTX-OR-SEM1-003: instruction is the `.b32` form only.
def b32Bits : Nat := 32

def b32DomainSize : Nat := 2 ^ b32Bits

-- PTX-OR-SEM1-005: explicit 32-bit value representation.
structure B32 where
  toFin : Fin b32DomainSize
  deriving DecidableEq, Repr

-- PTX-OR-SEM1-004: bounded architecture identifiers.
structure RegId where
  name : String
  deriving DecidableEq, Repr

structure PredId where
  name : String
  deriving DecidableEq, Repr

-- PTX-OR-SEM1-008 + AMB-OR-2 + D-2/D-6:
-- destination `_` is supported as project-bounded design for this unit,
-- inherited from generic PTX destination role/grammar, but not explicitly restated
-- in the or.b32 subsection.
inductive Destination where
  | reg : RegId → Destination
  | bitBucket : Destination
  deriving DecidableEq, Repr

-- PTX-OR-SEM1-003/004 + PRE-3 + ASS-OR-1 + D-3:
-- source-1 is register-only by bounded architecture restriction.
inductive Source1 where
  | reg : RegId → Source1
  deriving DecidableEq, Repr

-- PTX-OR-SEM1-003 + PRE-3 + ASS-OR-1 + D-3:
-- source-2 can be register or immediate in this bounded unit.
inductive Source2 where
  | reg : RegId → Source2
  | imm : B32 → Source2
  deriving DecidableEq, Repr

-- PTX-OR-SEM1-006 / D-5: optional predication guard, negation handled explicitly.
inductive Guard where
  | none : Guard
  | atPos : PredId → Guard
  | atNeg : PredId → Guard
  deriving DecidableEq, Repr

-- D-4/D-7: minimal local state: register file plus predicate file.
structure MachineState where
  valueRegs : RegId → Option B32
  predRegs : PredId → Option Bool

-- PTX-OR-SEM1-003/004: fixed operand order d, a, b.
structure OrB32Instruction where
  guard : Guard
  d : Destination
  a : Source1
  b : Source2
  deriving DecidableEq, Repr

-- PTX-OR-SEM1-005: read source operands (read-before-write in this unit).
def readSource1 (s : MachineState) : Source1 → Option B32
  | Source1.reg r => s.valueRegs r

-- PTX-OR-SEM1-005: read source-2 with immediate passthrough.
def readSource2 (s : MachineState) : Source2 → Option B32
  | Source2.reg r => s.valueRegs r
  | Source2.imm v => some v

-- PTX-OR-SEM1-006: predicate evaluation (predication false means no-op).
def evalGuard (s : MachineState) : Guard → Option Bool
  | Guard.none => some true
  | Guard.atPos p => s.predRegs p
  | Guard.atNeg p =>
      match s.predRegs p with
      | some b => some (not b)
      | none => none

-- PTX-OR-SEM1-005: 32-bit OR operation.
def orValue (x y : B32) : B32 :=
  let raw : UInt32 := UInt32.ofNat x.toFin.val ||| UInt32.ofNat y.toFin.val
  { toFin := Fin.mk raw.toNat (by simpa [b32Bits, b32DomainSize] using raw.toNat_lt) }

-- PTX-OR-SEM1-005: destination write is only for register destination.
def updateDestination (s : MachineState) : Destination → B32 → MachineState
  | Destination.reg r, result =>
      { s with valueRegs := fun r' => if r' == r then some result else s.valueRegs r' }
  | Destination.bitBucket, _ => s

-- PTX-OR-SEM1-006/005: one-step executable semantics with partial behavior for malformed state.
inductive ExecOutcome where
  | executed : MachineState → ExecOutcome
  | notExecuted : MachineState → ExecOutcome

-- PTX-OR-SEM1-006: false predicate produces no state change.
def execOrB32 (s : MachineState) (i : OrB32Instruction) : Option ExecOutcome :=
  match evalGuard s i.guard with
  | none => none
  | some false => some (ExecOutcome.notExecuted s)
  | some true =>
      match readSource1 s i.a, readSource2 s i.b with
      | some va, some vb => some (ExecOutcome.executed (updateDestination s i.d (orValue va vb)))
      | _, _ => none

-- PTX-OR-SEM1-005/006: relation form for one-step semantics.
inductive OrB32Step : MachineState → OrB32Instruction → MachineState → Prop where
  | notExecuted (s : MachineState) (i : OrB32Instruction) (h : evalGuard s i.guard = some false) :
      OrB32Step s i s
  | executed
      (s : MachineState)
      (i : OrB32Instruction)
      (va vb : B32)
      (hguard : evalGuard s i.guard = some true)
      (hasa : readSource1 s i.a = some va)
      (hasb : readSource2 s i.b = some vb) :
      OrB32Step s i (updateDestination s i.d (orValue va vb))

-- PTX-OR-SEM1-005: helper constructor.
def mkB32 (n : Nat) : B32 :=
  { toFin := Fin.mk (n % b32DomainSize) (Nat.mod_lt n (by decide : 0 < b32DomainSize)) }

end Spec2Lean.PTX.OrB32
