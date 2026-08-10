import Spec2Lean.Basic

/-!
Bounded Lean formalization unit: PTX ISA 9.3 `xor.b16`.

Approved semantic artifact:
  candidates/ptx/9.3/units/xor-b16/semantics/semantics-v1.json
  (interpretation_id: ptx-9.3-xor-b16-semantics-v1)

Exact approved semantic claim IDs in scope:
  PTX-XORB16-SEM-001
  PTX-XORB16-SEM-002
  PTX-XORB16-SEM-003
  PTX-XORB16-SEM-004
  PTX-XORB16-SEM-005
  PTX-XORB16-SEM-006
  PTX-XORB16-SEM-007
  PTX-XORB16-SEM-008

Unresolved mapping questions retained as open issues (no added semantic commitment):
- PTX-XORB16-SEM-007: whether source operand `a` may be immediate.
- PTX-XORB16-SEM-008: whether destination `_` (bit bucket) is legal/defined for
  xor.b16.

Traceability note: declarations below cite only approved semantic claim IDs above.
-/

namespace Spec2Lean.PTX.XorB16

-- 16-bit domain width for `.b16`.
-- PTX-XORB16-SEM-002.
def b16Bits : Nat := 16

-- Total number of representable `.b16` values.
-- PTX-XORB16-SEM-002, PTX-XORB16-SEM-003.
def b16DomainSize : Nat := 2 ^ b16Bits

-- 16-bit untyped value, represented as an element of `Fin (2^16)`.
-- PTX-XORB16-SEM-002, PTX-XORB16-SEM-003.
structure B16 where
  toFin : Fin b16DomainSize
  deriving DecidableEq

instance : Repr B16 where
  reprPrec v _ := repr v.toFin.val

-- Register identifier representation for value-register operands.
-- PTX-XORB16-SEM-002, PTX-XORB16-SEM-005.
structure RegId where
  name : String
  deriving DecidableEq, Repr

-- Predicate-register identifier representation.
-- PTX-XORB16-SEM-004, PTX-XORB16-SEM-005.
structure PredId where
  name : String
  deriving DecidableEq, Repr

-- Source operand `a` is modeled as a register variable in this bounded artifact.
-- PTX-XORB16-SEM-007 is unresolved and therefore retained as an explicit open
-- mapping question.
inductive SourceA where
  | reg : RegId -> SourceA
  deriving DecidableEq, Repr

-- Source operand `b` is modeled as register or `.b16` immediate.
-- The immediate form is represented as an already bounded `B16` constant; this
-- keeps the model open about any unproven wider-immediate cast policy.
-- PTX-XORB16-SEM-001, PTX-XORB16-SEM-003, PTX-XORB16-SEM-007.
inductive SourceB where
  | reg : RegId -> SourceB
  | imm16 : B16 -> SourceB
  deriving DecidableEq, Repr

-- Destination may be a register, with `_` present as a candidate syntax form only.
-- PTX-XORB16-SEM-008 records bit-bucket legality as unresolved for this form.
inductive Destination where
  | reg : RegId -> Destination
  | bitBucket : Destination
  deriving DecidableEq, Repr

-- Optional predication forms for this instruction family.
-- PTX-XORB16-SEM-004.
inductive Guard where
  | unguarded : Guard
  | atPos : PredId -> Guard
  | atNeg : PredId -> Guard
  deriving DecidableEq, Repr

-- Bounded form fixes instruction type to `.b16` only.
-- PTX-XORB16-SEM-002.
inductive XorTypeSpecifier where
  | b16 : XorTypeSpecifier
  deriving DecidableEq, Repr

-- Bounded state has register and predicate files only.
-- PTX-XORB16-SEM-005.
structure MachineState where
  valueRegs : RegId -> Option B16
  predRegs : PredId -> Option Bool

-- Bounded instruction node: `xor.b16 d, a, b` with optional guard.
-- PTX-XORB16-SEM-002, PTX-XORB16-SEM-004.
structure XorB16Instruction where
  type : XorTypeSpecifier
  guard : Guard
  d : Destination
  a : SourceA
  b : SourceB
  deriving DecidableEq, Repr

-- Read source `a` from register state.
-- PTX-XORB16-SEM-005.
def evalSourceA (s : MachineState) (o : SourceA) : Option B16 :=
  match o with
  | SourceA.reg r => s.valueRegs r

-- Read source `b` as register value or immediate bounded `.b16` value.
-- PTX-XORB16-SEM-005.
def evalSourceB (s : MachineState) (o : SourceB) : Option B16 :=
  match o with
  | SourceB.reg r => s.valueRegs r
  | SourceB.imm16 v => some v

-- Evaluate optional predicate guard.
-- PTX-XORB16-SEM-004 and PTX-XORB16-SEM-006 (open on explicit false-guard state behavior).
def evalGuard (s : MachineState) : Guard -> Option Bool
  | Guard.unguarded => some true
  | Guard.atPos p => s.predRegs p
  | Guard.atNeg p =>
      match s.predRegs p with
      | some b => some (not b)
      | none => none

-- Bitwise XOR over bounded `.b16` values.
-- PTX-XORB16-SEM-003.
def xorValue (x y : B16) : B16 :=
  {
    toFin := Fin.mk
      (Nat.xor x.toFin.val y.toFin.val % b16DomainSize)
      (Nat.mod_lt (Nat.xor x.toFin.val y.toFin.val) (by decide : 0 < b16DomainSize))
  }

-- Destination update writes only register destination.
-- For bit-bucket destination, semantics remains partial pending openness of
-- PTX-XORB16-SEM-008.
def updateDestination (s : MachineState) (d : Destination) (value : B16) : Option MachineState :=
  match d with
  | Destination.reg r =>
      some {
        s with
        valueRegs :=
          fun r' =>
            if r' == r then
              some value
            else
              s.valueRegs r'
      }
  | Destination.bitBucket => none

-- Partial transition used by the executable and relational semantics.
-- PTX-XORB16-SEM-005 and PTX-XORB16-SEM-008 (undecided bit-bucket case).
def eval : MachineState -> XorB16Instruction -> Option MachineState :=
  fun s i =>
    match evalGuard s i.guard with
    | none => none
    | some false => some s
    | some true =>
        match evalSourceA s i.a with
        | none => none
        | some va =>
            match evalSourceB s i.b with
            | none => none
            | some vb => updateDestination s i.d (xorValue va vb)

-- Guarded, partial executable outcomes.
-- PTX-XORB16-SEM-005 and PTX-XORB16-SEM-006 (explicit false-guard state behavior is
-- left as an open question in the interpretation).
inductive ExecOutcome where
  | executed : MachineState -> ExecOutcome
  | guardFalse : MachineState -> ExecOutcome

-- Executed/guard-false semantics mirror `eval`; bit-bucket remains undefined.
-- PTX-XORB16-SEM-005.
def execXorB16 (s : MachineState) (i : XorB16Instruction) : Option ExecOutcome :=
  match evalGuard s i.guard with
  | none => none
  | some false => some (ExecOutcome.guardFalse s)
  | some true =>
      match evalSourceA s i.a with
      | none => none
      | some va =>
          match evalSourceB s i.b with
          | none => none
          | some vb =>
              match updateDestination s i.d (xorValue va vb) with
              | none => none
              | some s' => some (ExecOutcome.executed s')

-- Relational semantics for explicit transitions.
-- PTX-XORB16-SEM-005.
inductive XorB16Step : MachineState -> XorB16Instruction -> MachineState -> Prop where
  | guardFalse : (s : MachineState) -> (i : XorB16Instruction) ->
      evalGuard s i.guard = some false ->
      XorB16Step s i s
  | executed : (s : MachineState) -> (i : XorB16Instruction) -> (va : B16) -> (vb : B16) ->
      (s' : MachineState) ->
      evalSourceA s i.a = some va ->
      evalSourceB s i.b = some vb ->
      updateDestination s i.d (xorValue va vb) = some s' ->
      XorB16Step s i s'

-- Helper to wrap natural constants as bounded `.b16` values.
-- Exact source-immediate cast/truncation policy is an open question; this helper
-- is a convenience for constructing `SourceB.imm16` values in tests.
def mkB16 (n : Nat) : B16 :=
  {
    toFin := Fin.mk
      (n % b16DomainSize)
      (Nat.mod_lt n (by decide : 0 < b16DomainSize))
  }

-- Helper for constructing bounded states from association lists.
-- PTX-XORB16-SEM-005.
def mkState
    (valueRegBindings : List (RegId × B16))
    (predRegBindings : List (PredId × Bool)) : MachineState :=
  {
    valueRegs := fun r =>
      valueRegBindings
        |>.find? (fun b => b.1 == r)
        |> Option.map Prod.snd
    predRegs := fun p =>
      predRegBindings
        |>.find? (fun b => b.1 == p)
        |> Option.map Prod.snd
  }

end Spec2Lean.PTX.XorB16