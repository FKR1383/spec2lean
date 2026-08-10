import Spec2Lean.Basic

/-!
Bounded Lean formalization unit: PTX ISA 9.3 `xor.b16`

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

Traceability note: declarations cite only the IDs above when representing semantics.
-/

namespace Spec2Lean
namespace PTX
namespace XorB16

/-- 16-bit value domain for `.b16` operands (bounded unit form `xor.b16`).
See PTX-XORB16-SEM-002 and PTX-XORB16-SEM-005. -/
def b16Bits : Nat := 16

def b16DomainSize : Nat := 2 ^ b16Bits

structure B16 where
  toFin : Fin b16DomainSize
  deriving DecidableEq

instance : Repr B16 where
  reprPrec v _ := repr v.toFin.val

/-- Register identifiers are named objects. -/
structure RegId where
  name : String
  deriving DecidableEq, Repr

/-- Predicate identifiers are named objects. -/
structure PredId where
  name : String
  deriving DecidableEq, Repr

/-- Source operand representation for bounded `xor.b16`.
PTX-XORB16-SEM-005 models source reads of `a` and `b`.
PTX-XORB16-SEM-007 notes open questions about immediates; this bounded model
uses register sources only (no immediate constructor). -/
inductive SourceOperand where
  | reg : RegId -> SourceOperand
  deriving DecidableEq, Repr

/-- Destination operand representation for bounded `xor.b16`.
`Destination.reg r` writes register `r`; `.bitBucket` discards the result.
- PTX-XORB16-SEM-005, with open question PTX-XORB16-SEM-008 about legality for this form. -/
inductive Destination where
  | reg : RegId -> Destination
  | bitBucket : Destination
  deriving DecidableEq, Repr

/-- Optional predication/guard forms for bounded `xor.b16`.
PTX-XORB16-SEM-003 and PTX-XORB16-SEM-004: none, `@p`, `@!p`. -/
inductive Guard where
  | unguarded : Guard
  | atPos : PredId -> Guard
  | atNeg : PredId -> Guard
  deriving DecidableEq, Repr

/-- Type specifier for this bounded unit: `.b16` only.
PTX-XORB16-SEM-002. -/
inductive XorTypeSpecifier where
  | b16 : XorTypeSpecifier
  deriving DecidableEq, Repr

/-- Bounded state for this unit: value-register file and predicate-register file.
PTX-XORB16-SEM-005 (no extra component assertions). -/
structure MachineState where
  valueRegs : RegId -> Option B16
  predRegs : PredId -> Option Bool

/-- Instruction node order: `xor.b16 d, a, b` with optional guard. -/
structure XorB16Instruction where
  type : XorTypeSpecifier
  guard : Guard
  d : Destination
  a : SourceOperand
  b : SourceOperand
  deriving DecidableEq, Repr

/-- Evaluate a source operand from state.
PTX-XORB16-SEM-005 (read `a` and `b` before write). -/
def evalSource (s : MachineState) (o : SourceOperand) : Option B16 :=
  match o with
  | SourceOperand.reg r => s.valueRegs r

/-- Evaluate complete guard expression.
PTX-XORB16-SEM-003 and PTX-XORB16-SEM-004; missing predicate -> partial none. -/
def evalGuard : MachineState -> Guard -> Option Bool
  | _ , Guard.unguarded => some true
  | s, Guard.atPos p => s.predRegs p
  | s, Guard.atNeg p =>
      match s.predRegs p with
      | some b => some (not b)
      | none => none

/-- Bitwise XOR over `.b16` values implementing `d = a ^ b`.
PTX-XORB16-SEM-003. -/
def xorValue (x y : B16) : B16 :=
  {
    toFin := Fin.mk
      (Nat.xor x.toFin.val y.toFin.val % b16DomainSize)
      (Nat.mod_lt (Nat.xor x.toFin.val y.toFin.val) (by decide : 0 < b16DomainSize))
  }

/-- Destination update for bounded state.
PTX-XORB16-SEM-005; writes only destination register, bit-bucket discards. -/
def updateDestination
    (s : MachineState)
    (d : Destination)
    (value : B16) :
    MachineState :=
  match d with
  | Destination.reg r =>
      {
        s with
        valueRegs :=
          fun r' =>
            if r' == r then
              some value
            else
              s.valueRegs r'
      }
  | Destination.bitBucket =>
      s

/-- Execution outcome class used by this bounded model.
PTX-XORB16-SEM-005 (no explicit exceptional outcome recorded). -/
inductive ExecOutcome where
  | executed : MachineState -> ExecOutcome
  | guardFalse : MachineState -> ExecOutcome

/-- Guarded and partial semantics for bounded `xor.b16`:
- evaluate guard and sources in pre-state;
- on `none` from guard or source lookups => partial `none`;
- on false guard => `guardFalse` with unchanged state;
- on true guard and defined sources => write `a ^ b` to `d`. -/
def execXorB16 (s : MachineState) (i : XorB16Instruction) : Option ExecOutcome :=
  match evalGuard s i.guard with
  | none => none
  | some false => some (ExecOutcome.guardFalse s)
  | some true =>
      match evalSource s i.a with
      | none => none
      | some va =>
          match evalSource s i.b with
          | none => none
          | some vb => some (ExecOutcome.executed (updateDestination s i.d (xorValue va vb)))

/-- Relational semantics: partial relation over complete execution states.
PTX-XORB16-SEM-005.
-/
inductive XorB16Step : MachineState -> XorB16Instruction -> MachineState -> Prop where
  | guardFalse : (s : MachineState) -> (i : XorB16Instruction) ->
      evalGuard s i.guard = some false -> XorB16Step s i s
  | executed : (s : MachineState) -> (i : XorB16Instruction) -> (va : B16) -> (vb : B16) ->
      evalGuard s i.guard = some true ->
      evalSource s i.a = some va ->
      evalSource s i.b = some vb ->
      XorB16Step s i (updateDestination s i.d (xorValue va vb))

/-- Helper: truncate a Nat to the `.b16` domain. -/
def mkB16 (n : Nat) : B16 :=
  {
    toFin :=
      Fin.mk
        (n % b16DomainSize)
        (Nat.mod_lt n (by decide : 0 < b16DomainSize))
  }

/-- Helper: finite-state constructor from prioritized bindings. -/
def mkState
    (valueRegBindings : List (RegId × B16))
    (predRegBindings : List (PredId × Bool)) :
    MachineState :=
  {
    valueRegs :=
      fun r =>
        valueRegBindings
          |>.find? (fun b => b.1 == r)
          |> Option.map Prod.snd

    predRegs :=
      fun p =>
        predRegBindings
          |>.find? (fun b => b.1 == p)
          |> Option.map Prod.snd
  }

end XorB16
end PTX
end Spec2Lean