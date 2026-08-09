/-
Spec2Lean Lean formalization candidate — PTX ISA 9.3 `and.b32`

Bounded formalization unit : PTX ISA 9.3 `and.b32` (bounded scalar 32-bit
                            bit-size form `and.type d, a, b;` with instruction
                            type `.b32`; instruction family `and`, section
                            9.7.8.1 "Logic and Shift Instructions: and",
                            HTML anchor logic-and-shift-instructions-and)

Approved semantic interpretation :
  candidates/ptx/9.3/units/and-b32/semantics/semantics-v2.json
  (interpretation_id ptx-9.3-and-b32-semantics-v2; SHA-256
   45e0fe93f02a3261976962026eb7b5b2e1a5343c10d4a388f500f6f30a24ca0e)
Gate B record               : reviews/ptx-and-b32/gate-b/ptx-and-b32-b-approval-v1.json
                              (decision: approved)
Gate A record               : reviews/ptx-and-b32/gate-a/ptx-and-b32-a-approval-v1.json
                              (decision: approved)
Architecture reference      : candidates/ptx/9.3/units/and-b32/architecture/foundation-v1.md
                              (approved at Gate A; bounded-scope decision D-0c)
Primary source bundle       : candidates/ptx/9.3/units/and-b32/source-bundles/source-bundle-v2.json
                              (bundle_id source-bundle-v2; SHA-256
                               57e86be0f823fa70e7559ca21cba30bf7f4b434a87c33cb39b134ce13f27ea53)
Semantic critique           : candidates/ptx/9.3/units/and-b32/reviews/semantics-critic-v1.md
                              (verdict: READY FOR PRESENTATION TO HUMAN GATE B)

EPISTEMIC NOTE (no human-approved formalization assumption exists for and.b32):
  semantics-v2 contains zero ASSUMPTION-classified claims (assumption_notes;
  semantic-critic F-1..F-5 are MINOR/NOTE only). In particular, the guard-false
  "no state update" consequence is a DERIVED_INTERPRETATION
  (PTX-AND-SEM2-063) grounded in the official section 9.7.13.2 clause "Threads
  with a False guard predicate do nothing." (SOURCE_FACT PTX-AND-SEM2-071;
  CTX-08), applied through the general predicability rules (CTX-07, CTX-02).
  This candidate must never present that consequence as a human assumption or
  as an add.u32-style assumption import; it is implemented here as the
  approved derived interpretation.

Scope:
  - Only the bounded scalar 32-bit bit-size form `and.b32 d, a, b;` with
    instruction type `.b32` is modeled (architecture D-0c;
    PTX-AND-SEM2-003/004/005). The `.pred`, `.b16`, and `.b64` forms of the
    same section and the sibling logic/shift instructions are out of scope
    (PTX-AND-SEM2-064).
  - Source operand `a` is modeled as a register variable only
    (PTX-AND-SEM2-023/025): every read example uses a register in position `a`
    (`and.b32  x,q,r;`, AND_B32_EXAMPLE_1; `and.b32  sign,fpvalue,0x80000000;`,
    AND_B32_EXAMPLE_2). Whether `a` may also be a constant immediate is NOT
    explicitly evidenced and is retained as an open question
    (PTX-AND-SEM2-061); therefore no immediate constructor is introduced for
    position `a`, because adding one would assert permissibility not present in
    the approved interpretation.
  - Source operand `b` is modeled as a register variable or a constant
    immediate (PTX-AND-SEM2-023/024): the official example
    `and.b32  sign,fpvalue,0x80000000;` (AND_B32_EXAMPLE_2) directly evidences
    an immediate constant (0x80000000) in source position `b` for the `.b32`
    form, resolving architecture OQ-1 for position b.
  - The bit-bucket destination `_` is modeled as a candidate alternative
    destination form at the strength of the general section 9.2 rule
    (architecture SF-A13); scalar and.b32-specific applicability remains an
    open question (PTX-AND-SEM2-062). The `lop3.and.b32 _|p, ...` match in the
    `lop3` section is a different instruction and is not evidence for `and`.
  - No error, trap, undefined, or implementation-defined behavior is invented
    (PTX-AND-SEM2-048/049/050). A register or predicate lookup that is not
    defined in the state is represented as PARTIAL execution (Option none), not
    as an error.
  - Version/target metadata is not modeled as state behavior: the base form
    was introduced in PTX ISA 1.0 (PTX-AND-SEM2-046) and is supported on all
    target architectures (PTX-AND-SEM2-047). Version/target gating are
    validation obligations (architecture VAL-5/VAL-6), not execution behavior.
  - No theorem statements and no proofs are included in this candidate. The
    proof-obligation families PRF-1..PRF-7 (architecture Section 10;
    semantics-v2 future_theorem_obligation_topics) are deferred to the
    theorem-design and proof stages.

Traceability convention: each declaration below carries a comment citing the
relevant semantic claim IDs from
candidates/ptx/9.3/units/and-b32/semantics/semantics-v2.json and, where
applicable, the architecture design choice.
-/

import Spec2Lean.PTX.Core

namespace Spec2Lean
namespace PTX
namespace AndB32

/-! # and.b32 bounded formalization -/

/-!
Compatibility layer for the pre-v2 AndB32 vocabulary.

These declarations are definitional aliases of the shared PTX Core.
Existing AndB32 theorem statements and downstream names therefore retain
their previous shape while the common implementation is reused.
-/

abbrev b32Bits := Core.b32Bits
abbrev b32DomainSize := Core.b32DomainSize

abbrev B32 := Core.B32
abbrev RegId := Core.RegId
abbrev PredId := Core.PredId

abbrev Destination := Core.Destination

namespace Destination

abbrev reg : RegId -> Destination :=
  Core.Destination.reg

abbrev bitBucket : Destination :=
  Core.Destination.bitBucket

end Destination

abbrev Guard := Core.Guard

namespace Guard

abbrev unguarded : Guard :=
  Core.Guard.unguarded

abbrev atPos : PredId -> Guard :=
  Core.Guard.atPos

abbrev atNeg : PredId -> Guard :=
  Core.Guard.atNeg

end Guard

abbrev MachineState := Core.MachineState
abbrev evalGuard := Core.evalGuard
abbrev updateDestination := Core.updateDestination

abbrev ExecOutcome := Core.ExecOutcome

namespace ExecOutcome

abbrev executed : MachineState -> ExecOutcome :=
  Core.ExecOutcome.executed

abbrev guardFalse : MachineState -> ExecOutcome :=
  Core.ExecOutcome.guardFalse

end ExecOutcome

abbrev mkB32 := Core.mkB32
abbrev mkState := Core.mkState

/-
5. Source operand representation for the approved semantics.
The approved semantics distinguishes the two source positions, so the two
positions are given two distinct types and the type system itself enforces the
approved asymmetry:
- Source operand `a` is a register variable in every read example
  (`and.b32  x,q,r;`, AND_B32_EXAMPLE_1; `and.b32  sign,fpvalue,0x80000000;`,
  AND_B32_EXAMPLE_2; PTX-AND-SEM2-023/025). Whether `a` may also be a constant
  immediate is NOT explicitly evidenced (open question PTX-AND-SEM2-061);
  therefore position `a` is modeled as a register variable only, and no
  immediate constructor is introduced for it (adding one would assert
  permissibility not present in the approved interpretation).
- Source operand `b` is a register variable or a constant immediate: the
  official example `and.b32  sign,fpvalue,0x80000000;` (AND_B32_EXAMPLE_2)
  directly evidences an immediate constant (0x80000000) in source position `b`
  for the `.b32` form (PTX-AND-SEM2-024; resolves architecture OQ-1 for
  position b). The register-source case is evidenced by `and.b32  x,q,r;`
  (AND_B32_EXAMPLE_1; PTX-AND-SEM2-023).
-/
inductive SourceA where
  | reg : RegId -> SourceA   -- first source `a`: register variable only
deriving DecidableEq, Repr

inductive SourceB where
  | reg : RegId -> SourceB   -- second source `b`: register source
  | imm : B32 -> SourceB     -- second source `b`: constant immediate
deriving DecidableEq, Repr

/-
Instruction type specifier for the bounded unit.
Only `.b32` is in scope; the unit identity fixes the mnemonic `and`, the type
`.b32`, and the empty modifier set (the scalar and syntax has no modifier
position). Claims PTX-AND-SEM2-003/004/005/028.
-/
inductive AndTypeSpecifier where
  | b32 : AndTypeSpecifier
deriving DecidableEq, Repr

/-
A well-formed and.b32 instruction: optional guard, destination d, then the two
source operands a and b in that order (operand order `d, a, b`; the destination
comes first). Claims PTX-AND-SEM2-006/021/055; design D-1/D-16.
-/
structure AndB32Instruction where
  type : AndTypeSpecifier
  guard : Guard
  d : Destination
  a : SourceA
  b : SourceB
deriving DecidableEq, Repr

/-
9. Source-operand evaluation.
Reads the current (pre-instruction) value of a source: a register is read from
the value-register file; a constant immediate (position b) is the immediate
value. A missing register yields none (partial execution), not an invented
result.
Claims PTX-AND-SEM2-034.
-/
def evalSourceA (s : MachineState) : SourceA -> Option B32
  | SourceA.reg r => s.valueRegs r

def evalSourceB (s : MachineState) : SourceB -> Option B32
  | SourceB.reg r => s.valueRegs r
  | SourceB.imm v => some v

/-
11. Explicit bitwise-and rule (d = a & b;).
`andValue` returns the bitwise and of its two arguments over the 32-bit untyped
`.b32` bit-value domain: each of the 32 bits of the result is the and of the
two corresponding bits of the arguments. For the Fin (2^32) encoding, the value
domain is in bijection with the 32-bit bit patterns, so the natural-number
encoding `Nat.land` computes the bitwise and of the bit patterns; the reduction
modulo 2^32 is a no-op for arguments in [0, 2^32) (their bitwise and is again
in [0, 2^32)) and keeps the Fin bound proof definitionally immediate and purely
computational.
This implements the and Semantics line `d = a & b;` (PTX-AND-SEM2-008,
SOURCE_FACT) and the derived bitwise-and semantics (PTX-AND-SEM2-032). The
exact formal statement of the and-fidelity candidate obligation PRF-7 (each
bit of the result is the and of the corresponding source bits) is a
theorem-stage matter (PTX-AND-SEM2-068, OQ-8).
-/
def andValue (x y : B32) : B32 :=
  { toFin :=
      ⟨Nat.land x.toFin.val y.toFin.val % b32DomainSize,
       Nat.mod_lt (Nat.land x.toFin.val y.toFin.val) (by decide : 0 < b32DomainSize)⟩ }

/-
13. Guarded and.b32 execution.
- The complete guard expression is evaluated first.
- If the guard expression evaluates FALSE, the thread does nothing and the
  state is unchanged (PTX-AND-SEM2-063; source-resolved via the section
  9.7.13.2 clause "Threads with a False guard predicate do nothing.",
  CTX-08 / PTX-AND-SEM2-071). Source operands are NOT read in this branch.
- If the guard expression evaluates TRUE (including the unguarded case), the
  source values are read and the destination is updated with their bitwise
  and (d = a & b;) (claims PTX-AND-SEM2-032/033/034/036). The sources are read
  from the pre-instruction state before the destination update, so a
  destination that aliases a source register retains its own value
  (read-before-write; PTX-AND-SEM2-060).
- `none` denotes PARTIAL execution: a required register lookup (guard predicate
  or source register) is not defined in the state. It is not an error, trap, or
  undefined behavior (PTX-AND-SEM2-048/049/050).
-/
def execAndB32 (s : MachineState) (i : AndB32Instruction) : Option ExecOutcome :=
  match evalGuard s i.guard with
  | none => none
  | some false => some (ExecOutcome.guardFalse s)
  | some true =>
      match evalSourceA s i.a with
      | none => none
      | some va =>
          match evalSourceB s i.b with
          | none => none
          | some vb => some (ExecOutcome.executed (updateDestination s i.d (andValue va vb)))

/-
14. Relational form of the execution semantics.
The approved execution-semantics representation design (architecture D-25;
PTX-AND-SEM2-057) specifies the future execution semantics as an execution
relation between (state, instruction) and state, not merely as a function, so
that determinism (PRF-1) and frame/locality obligations (PRF-2..PRF-5) are
non-vacuous. This inductive relation is the relational counterpart of the
executable function `execAndB32`: it relates s to the unchanged state exactly
when the complete guard expression evaluates false, and to the updated state
exactly when the guard is true and both sources resolve. The correspondence
between the relation and the executable function is a theorem-stage obligation
(PRF-1 family).
-/
inductive AndB32Step : MachineState -> AndB32Instruction -> MachineState -> Prop where
  | guardFalse : (s : MachineState) -> (i : AndB32Instruction) ->
      evalGuard s i.guard = some false -> AndB32Step s i s
  | executed : (s : MachineState) -> (i : AndB32Instruction) -> (va : B32) -> (vb : B32) ->
      evalGuard s i.guard = some true ->
      evalSourceA s i.a = some va ->
      evalSourceB s i.b = some vb ->
      AndB32Step s i (updateDestination s i.d (andValue va vb))

/-! # Helper definitions for executable examples (not semantic definitions) -/

-- Example-only identifiers (not part of the semantics).
private def exR1 : RegId := { name := "r1" }
private def exR2 : RegId := { name := "r2" }
private def exR3 : RegId := { name := "r3" }
private def exP1 : PredId := { name := "p1" }

/-! # Executable examples (demonstrative only; not proofs) -/

-- And rule: 0 & 0 = 0 (d = a & b; PTX-AND-SEM2-032).
#eval andValue (mkB32 0) (mkB32 0)

-- And rule: 0xFFFFFFFF & 0xFFFFFFFF = 0xFFFFFFFF.
#eval andValue (mkB32 0xFFFFFFFF) (mkB32 0xFFFFFFFF)

-- And rule: 0xFFFFFFFF & 0 = 0 (0 is the annihilator of and).
#eval andValue (mkB32 0xFFFFFFFF) (mkB32 0)

-- And rule: 5 & 3 = 1 (5 = 0b101, 3 = 0b011, and = 0b001 = 1).
#eval andValue (mkB32 5) (mkB32 3)

-- Bit-pattern example: 0xFFFF0000 & 0x00FF00FF = 0x00FF0000 = 16711680.
#eval andValue (mkB32 0xFFFF0000) (mkB32 0x00FF00FF)

-- Official .b32 immediate example shape: `and.b32  sign,fpvalue,0x80000000;`
-- (AND_B32_EXAMPLE_2; PTX-AND-SEM2-024). With fpvalue = 0xFFFFFFFF, the
-- destination sign becomes 0xFFFFFFFF & 0x80000000 = 0x80000000 = 2147483648.
#eval
  let st : MachineState := mkState [(exR1, mkB32 0xFFFFFFFF)] []
  let inst : AndB32Instruction :=
    { type := AndTypeSpecifier.b32, guard := Guard.unguarded,
      d := Destination.reg exR3, a := SourceA.reg exR1,
      b := SourceB.imm (mkB32 0x80000000) }
  match execAndB32 st inst with
  | some (.guardFalse s') => s'.valueRegs exR3
  | some (.executed s') => s'.valueRegs exR3
  | none => none

-- Register-source example shape: `and.b32  x,q,r;` (AND_B32_EXAMPLE_1).
-- With q = 0xFFFF0000 and r = 0x00FF00FF, x becomes 0x00FF0000 = 16711680.
#eval
  let st : MachineState := mkState [(exR1, mkB32 0xFFFF0000), (exR2, mkB32 0x00FF00FF)] []
  let inst : AndB32Instruction :=
    { type := AndTypeSpecifier.b32, guard := Guard.unguarded,
      d := Destination.reg exR3, a := SourceA.reg exR1, b := SourceB.reg exR2 }
  match execAndB32 st inst with
  | some (.guardFalse s') => s'.valueRegs exR3
  | some (.executed s') => s'.valueRegs exR3
  | none => none

-- Unguarded complete guard expression is true (PTX-AND-SEM2-029).
#eval evalGuard (mkState [] []) Guard.unguarded

-- @!p with p = false: complete guard expression is true (PTX-AND-SEM2-029).
#eval evalGuard (mkState [] [(exP1, false)]) (Guard.atNeg exP1)

-- Destination update writes only the destination register (PTX-AND-SEM2-036).
#eval (updateDestination (mkState [(exR1, mkB32 1), (exR2, mkB32 2)] [])
         (Destination.reg exR1) (mkB32 100)).valueRegs exR1

-- Bit bucket `_`: no value register is written (PTX-AND-SEM2-062, general
-- section 9.2 rule strength).
#eval (updateDestination (mkState [(exR1, mkB32 1)] [])
         Destination.bitBucket (mkB32 100)).valueRegs exR1

-- @p with p = false: instruction is not executed, state unchanged (r1 stays 5;
-- guard-false consequence PTX-AND-SEM2-063).
#eval
  let st : MachineState := mkState [(exR1, mkB32 5), (exR2, mkB32 3)] [(exP1, false)]
  let inst : AndB32Instruction :=
    { type := AndTypeSpecifier.b32, guard := Guard.atPos exP1,
      d := Destination.reg exR1, a := SourceA.reg exR1, b := SourceB.reg exR2 }
  match execAndB32 st inst with
  | some (.guardFalse s') => s'.valueRegs exR1
  | some (.executed s') => s'.valueRegs exR1
  | none => none

-- @!p with p = false: guard expression true, executes, r1 becomes 5 & 3 = 1.
#eval
  let st : MachineState := mkState [(exR1, mkB32 5), (exR2, mkB32 3)] [(exP1, false)]
  let inst : AndB32Instruction :=
    { type := AndTypeSpecifier.b32, guard := Guard.atNeg exP1,
      d := Destination.reg exR1, a := SourceA.reg exR1, b := SourceB.reg exR2 }
  match execAndB32 st inst with
  | some (.guardFalse s') => s'.valueRegs exR1
  | some (.executed s') => s'.valueRegs exR1
  | none => none

-- Immediate source b (PTX-AND-SEM2-024): r1 becomes 5 & 3 = 1 with b = imm 3.
#eval
  let st : MachineState := mkState [(exR1, mkB32 5)] []
  let inst : AndB32Instruction :=
    { type := AndTypeSpecifier.b32, guard := Guard.unguarded,
      d := Destination.reg exR1, a := SourceA.reg exR1, b := SourceB.imm (mkB32 3) }
  match execAndB32 st inst with
  | some (.guardFalse s') => s'.valueRegs exR1
  | some (.executed s') => s'.valueRegs exR1
  | none => none

-- Aliasing d == a: the sources are read before the destination update, so r1
-- becomes 5 & 3 = 1 (read-before-write; PTX-AND-SEM2-060).
#eval
  let st : MachineState := mkState [(exR1, mkB32 5), (exR2, mkB32 3)] []
  let inst : AndB32Instruction :=
    { type := AndTypeSpecifier.b32, guard := Guard.unguarded,
      d := Destination.reg exR1, a := SourceA.reg exR1, b := SourceB.reg exR2 }
  match execAndB32 st inst with
  | some (.guardFalse s') => s'.valueRegs exR1
  | some (.executed s') => s'.valueRegs exR1
  | none => none

-- Self-aliasing d == a == b: r1 becomes 5 & 5 = 5.
#eval
  let st : MachineState := mkState [(exR1, mkB32 5)] []
  let inst : AndB32Instruction :=
    { type := AndTypeSpecifier.b32, guard := Guard.unguarded,
      d := Destination.reg exR1, a := SourceA.reg exR1, b := SourceB.reg exR1 }
  match execAndB32 st inst with
  | some (.guardFalse s') => s'.valueRegs exR1
  | some (.executed s') => s'.valueRegs exR1
  | none => none

-- Partial execution: a missing source register yields none, not an invented
-- error (PTX-AND-SEM2-048/049/050).
#eval
  let st : MachineState := mkState [] [(exP1, true)]
  let inst : AndB32Instruction :=
    { type := AndTypeSpecifier.b32, guard := Guard.atPos exP1,
      d := Destination.reg exR1, a := SourceA.reg exR1, b := SourceB.reg exR2 }
  match execAndB32 st inst with
  | some (.guardFalse _) => "guard-false"
  | some (.executed _) => "executed"
  | none => "partial-none"

end AndB32
end PTX
end Spec2Lean
