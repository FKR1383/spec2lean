/-
Spec2Lean Lean formalization candidate — PTX ISA 9.3 `or.b32`

Bounded formalization unit : PTX ISA 9.3 `or.b32`
(form `or.type d, a, b;` with type `.b32`, plus optional predication and `@!p`).

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
  - Only scalar `or.b32 d, a, b;` is in scope (out-of-scope: .pred/.b16/.b64; no extra side-effects).
  - Operand order is `d, a, b` (destination first), with source-1 register-only and source-2 register-or-immediate
    by bounded architecture restriction.
  - Predicate guard is optional (`@p`, `@!p`) and false guard yields no update.
  - No special memory/sync/special-register state is modeled. Register/predicate lookups are partial
    (missing lookup => `none`), not errors.
  - No theorem statements are included in this artifact.

Traceability convention: each declaration below carries a comment citing relevant semantic claim IDs
from `candidates/ptx/9.3/units/or-b32/semantics/semantics-v1.json` and approved source evidence.
Unresolved mapping questions (kept explicit):
  - Open question on immediate-width/range for source-2.
  - Malformed-state handling for illegal names/illegal mixes is modeled as partial (`none`) in this stage.
-/

import Spec2Lean.Basic

namespace Spec2Lean
namespace PTX
namespace OrB32

-- 1. `.b32` value width.
-- Claim PTX-OR-SEM1-005 / PTX-9.3-OR-006 / PTX-9.3-OR-016
-- (source: `.b32` operand form and size-compatible 32-bit operation).
def b32Bits : Nat := 32

-- 2. Modulus for finite-domain bit-value representation.
def b32DomainSize : Nat := 2 ^ b32Bits

-- 3. 32-bit untyped value encoding.
-- Wrapper avoids implicit arithmetic semantics; only explicit `orValue` defines operation.
structure B32 where
  toFin : Fin b32DomainSize
  deriving DecidableEq

instance : Repr B32 where
  reprPrec v _ := repr v.toFin.val

-- 4. Register identifier representation.
-- Claim PTX-9.3-OR-003/PTX-9.3-OR-006
structure RegId where
  name : String
  deriving DecidableEq, Repr

-- 5. Predicate-register identifier representation.
-- Claim PTX-9.3-OR-025 / predicate-domain handling is 1-bit bool in bounded model.
structure PredId where
  name : String
  deriving DecidableEq, Repr

-- 6. Source-1 and source-2 operand taxonomy.
-- Bounded architecture: source-1 register-only, source-2 register-or-immediate.
inductive Source1Operand where
  | reg : RegId -> Source1Operand
  deriving DecidableEq, Repr

inductive Source2Operand where
  | reg : RegId -> Source2Operand
  | imm : B32 -> Source2Operand
  deriving DecidableEq, Repr

-- 7. Destination operand with `_` candidate alternative.
-- Strength from generic instruction rule PTX-9.3-OR-010.
inductive Destination where
  | reg : RegId -> Destination
  | bitBucket : Destination
  deriving DecidableEq, Repr

-- 8. Optional predicate guard.
inductive Guard where
  | unguarded : Guard
  | atPos : PredId -> Guard
  | atNeg : PredId -> Guard
  deriving DecidableEq, Repr

-- 9. In-scope type specifier.
inductive OrTypeSpecifier where
  | b32 : OrTypeSpecifier
  deriving DecidableEq, Repr

-- 10. Minimal state: value register file + predicate register file.
structure MachineState where
  valueRegs : RegId -> Option B32
  predRegs : PredId -> Option Bool

-- 11. Well-formed bounded instruction shape.
structure OrB32Instruction where
  type : OrTypeSpecifier
  guard : Guard
  d : Destination
  a : Source1Operand
  b : Source2Operand
  deriving DecidableEq, Repr

-- 12. Source-1 and source-2 evaluation from pre-state.
def evalSource1 (s : MachineState) : Source1Operand -> Option B32
  | Source1Operand.reg r => s.valueRegs r

def evalSource2 (s : MachineState) : Source2Operand -> Option B32
  | Source2Operand.reg r => s.valueRegs r
  | Source2Operand.imm v => some v

-- 13. Complete-guard evaluation.
def evalGuard (s : MachineState) : Guard -> Option Bool
  | Guard.unguarded => some true
  | Guard.atPos p => s.predRegs p
  | Guard.atNeg p =>
      match s.predRegs p with
      | some b => some (not b)
      | none => none

-- 14. Explicit bitwise-or operation on bounded operands.
-- Claim PTX-OR-SEM1-005 and PTX-9.3-OR-005 (core pseudocode `d = a | b;`).
def orValue (a b : B32) : B32 :=
  let raw : UInt32 := (UInt32.ofNat a.toFin.val) ||| (UInt32.ofNat b.toFin.val)
  let n : Nat := raw.toNat
  { toFin := Fin.mk n (by simpa [b32Bits, b32DomainSize] using (UInt32.toNat_lt raw)) }

-- 15. Destination update.
def updateDestination (s : MachineState) (d : Destination) (result : B32) : MachineState :=
  match d with
  | Destination.reg r =>
      { s with valueRegs := fun r' => if r' == r then some result else s.valueRegs r' }
  | Destination.bitBucket => s

-- 16. Executable outcomes: no explicit exceptional constructor.
inductive ExecOutcome where
  | executed : MachineState -> ExecOutcome
  | guardFalse : MachineState -> ExecOutcome

-- 17. Guarded execution.
-- Read-before-write behavior follows source-then-destination structure; undefined register reads
-- remain partial (none).
def execOrB32 (s : MachineState) (i : OrB32Instruction) : Option ExecOutcome :=
  match evalGuard s i.guard with
  | none => none
  | some false => some (ExecOutcome.guardFalse s)
  | some true =>
      match evalSource1 s i.a, evalSource2 s i.b with
      | some va, some vb => some (ExecOutcome.executed (updateDestination s i.d (orValue va vb)))
      | _, _ => none

-- 18. Relational form of bounded semantics.
inductive OrB32Step : MachineState -> OrB32Instruction -> MachineState -> Prop where
  | guardFalse : (s : MachineState) -> (i : OrB32Instruction) ->
      evalGuard s i.guard = some false -> OrB32Step s i s
  | executed : (s : MachineState) -> (i : OrB32Instruction) -> (va vb : B32) ->
      evalGuard s i.guard = some true ->
      evalSource1 s i.a = some va ->
      evalSource2 s i.b = some vb ->
      OrB32Step s i (updateDestination s i.d (orValue va vb))

/-! # Helper definitions for executable examples (not semantic definitions) -/

def mkB32 (n : Nat) : B32 :=
  { toFin := Fin.mk (n % b32DomainSize) (Nat.mod_lt n (by decide : 0 < b32DomainSize)) }

def mkState (valueRegBindings : List (RegId × B32)) (predRegBindings : List (PredId × Bool)) : MachineState :=
  { valueRegs := fun r => valueRegBindings.find? (fun b => b.1 == r) |>.map Prod.snd,
    predRegs := fun p => predRegBindings.find? (fun b => b.1 == p) |>.map Prod.snd }

private def exR1 : RegId := { name := "r1" }
private def exR2 : RegId := { name := "r2" }
private def exP1 : PredId := { name := "p1" }

#eval orValue (mkB32 0x00010001) (mkB32 0x00000003)
#eval
  let st : MachineState := mkState [(exR1, mkB32 7)] [(exP1, false)]
  let inst : OrB32Instruction :=
    { type := OrTypeSpecifier.b32, guard := Guard.atNeg exP1,
      d := Destination.reg exR1, a := Source1Operand.reg exR1,
      b := Source2Operand.imm (mkB32 0x00010001) }
  match execOrB32 st inst with
  | some (.guardFalse s') => s'.valueRegs exR1
  | some (.executed s') => s'.valueRegs exR1
  | none => none

#eval
  let st : MachineState := mkState [(exR1, mkB32 5)] [(exP1, true)]
  let inst : OrB32Instruction :=
    { type := OrTypeSpecifier.b32, guard := Guard.atPos exP1,
      d := Destination.bitBucket, a := Source1Operand.reg exR1,
      b := Source2Operand.reg exR2 }
  match execOrB32 st inst with
  | some (.guardFalse _) => "not executed"
  | some (.executed _) => "executed"
  | none => "partial"

#eval
  let st : MachineState := mkState [(exR1, mkB32 5)] []
  let inst : OrB32Instruction :=
    { type := OrTypeSpecifier.b32, guard := Guard.unguarded,
      d := Destination.reg exR1, a := Source1Operand.reg exR1,
      b := Source2Operand.imm (mkB32 0) }
  match execOrB32 st inst with
  | some (.guardFalse s') => s'.valueRegs exR1
  | some (.executed s') => s'.valueRegs exR1
  | none => none

end OrB32
end PTX
end Spec2Lean
