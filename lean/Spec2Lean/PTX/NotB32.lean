/-
Spec2Lean Lean formalization candidate — PTX ISA 9.3 `not.b32`

Bounded formalization unit : PTX ISA 9.3 `not.b32` (bounded scalar 32-bit
                            bit-size form `not.type d, a;` with instruction
                            type `.b32`; instruction family `not`, section
                            9.7.8.4 "Logic and Shift Instructions: not",
                            HTML anchor logic-and-shift-instructions-not)

Approved semantic interpretation :
  candidates/ptx/9.3/units/not-b32/semantics/semantics-v1.json
  (interpretation_id ptx-9.3-not-b32-semantics-v1)
Gate B record               : reviews/ptx-not-b32/gate-b/ptx-not-b32-b-approval-v1.json
                              (decision: approved)
Gate A record               : reviews/ptx-not-b32/gate-a/ptx-not-b32-a-approval-v1.json
                              (decision: approved)
Architecture reference      : candidates/ptx/9.3/units/not-b32/architecture/foundation-v2.md
                              (approved at Gate A; bounded-scope decision D-0c)
Primary source bundle       : candidates/ptx/9.3/units/not-b32/source-bundles/source-bundle-v1.json
Semantic critique           : candidates/ptx/9.3/units/not-b32/reviews/semantics-critic-v1.md

EPISTEMIC NOTE (no human-approved formalization assumption exists for not.b32):
  semantics-v1 contains zero ASSUMPTION-classified claims (assumption_notes).
  In particular, the guard-false "no state update" consequence is a
  DERIVED_INTERPRETATION (PTX-NOT-SEM1-035) grounded in the official section
  9.7.13.2 clause "Threads with a False guard predicate do nothing."
  (PTX-9.3-NOT-031/032; SOURCE_FACT PTX-NOT-SEM1-028). This candidate must
  never present that consequence as a human assumption or as an add.u32-style
  assumption import; it is implemented here as the approved derived
  interpretation.

Scope:
  - Only the bounded scalar 32-bit bit-size form `not.b32 d, a;` with
    instruction type `.b32` is modeled (architecture D-0c;
    PTX-NOT-SEM1-003/004/005). The `.pred`, `.b16`, and `.b64` forms of the
    same section and the sibling logic/shift instructions are out of scope
    (PTX-NOT-SEM1-068).
  - The source operand `a` is modeled as a register variable only
    (PTX-NOT-SEM1-010/043). A constant-immediate source is NOT modeled: its
    permissibility is not explicitly evidenced in the not section (bundle
    GAP-1; open question PTX-NOT-SEM1-066), and sibling-family immediate
    examples (PTX-9.3-NOT-011/012) are recorded as source facts but are not
    used to infer not's allowed operand forms (do_not_infer: true).
  - The bit-bucket destination `_` is modeled as a candidate alternative
    destination form at the strength of the general section 9.2 rule
    (PTX-9.3-NOT-016; PTX-NOT-SEM1-011/067); scalar not.b32-specific
    applicability remains an open question (PTX-NOT-SEM1-067).
  - No error, trap, undefined, or implementation-defined behavior is invented
    (PTX-NOT-SEM1-052/053/054). A register or predicate lookup that is not
    defined in the state is represented as PARTIAL execution (Option none), not
    as an error.
  - Version/target metadata is not modeled as state behavior: the base form
    was introduced in PTX ISA 1.0 (PTX-NOT-SEM1-048/050) and is supported on
    all target architectures (PTX-NOT-SEM1-049/051). Version/target gating are
    validation obligations (architecture VAL-5/VAL-6), not execution behavior.
  - No theorem statements and no proofs are included in this candidate. The
    proof-obligation families PRF-1..PRF-7 (architecture Section 10;
    semantics-v1 future_theorem_obligation_topics) are deferred to the
    theorem-design and proof stages.

Traceability convention: each declaration below carries a comment citing the
relevant semantic claim IDs from
candidates/ptx/9.3/units/not-b32/semantics/semantics-v1.json and, where
applicable, the architecture design choice.
-/

import Spec2Lean.PTX.Core

namespace Spec2Lean
namespace PTX
namespace NotB32

/-! # not.b32 bounded formalization -/

/-!
Compatibility layer for the pre-v2 NotB32 vocabulary.

These declarations are definitional aliases of the shared PTX Core.
Existing NotB32 theorem statements and downstream names therefore retain
their previous shape while the common implementation is reused.
-/

abbrev b32Bits := Core.b32Bits
abbrev b32DomainSize := Core.b32DomainSize

abbrev B32 := Core.B32
abbrev RegId := Core.RegId
abbrev PredId := Core.PredId

/-
5. Source operand representation for the approved semantics.
For the bounded base unit, the source operand a is a register variable
(PTX-NOT-SEM1-010/043; official example `not.b32 mask,mask;`, PTX-9.3-NOT-009).
Whether a may also be a constant immediate is NOT explicitly evidenced in the
not section (bundle GAP-1; open question PTX-NOT-SEM1-066); sibling-family
immediate examples (PTX-9.3-NOT-011/012) are recorded as source facts but are
not used to infer not's allowed operand forms (do_not_infer: true). Therefore
the source is modeled as a register variable only: no immediate constructor is
introduced, because adding one would assert semantics not present in the
approved interpretation.
-/
inductive SourceOperand where
  | reg : RegId -> SourceOperand   -- register source; read from the state
deriving DecidableEq, Repr

/-
6. Destination operand representation.
The destination is a register variable (of a type size-compatible with .b32)
or the bit bucket `_` as a candidate alternative (design D-18). When `d` is the
bit bucket, execution performs no register write (the result is discarded),
supported only to the strength of the general section 9.2 rule
(PTX-9.3-NOT-016; PTX-NOT-SEM1-011/067).
-/
abbrev Destination := Core.Destination

namespace Destination

abbrev reg : RegId -> Destination :=
  Core.Destination.reg

abbrev bitBucket : Destination :=
  Core.Destination.bitBucket

end Destination

/-
7. Optional guard representation.
- unguarded : no guard; complete guard expression is true (unconditional).
- atPos p   : `@p`;  complete guard expression is the value of predicate p.
- atNeg p   : `@!p`; complete guard expression is the negation of predicate p.
Claims PTX-NOT-SEM1-022/037/044; design D-19/D-21.
-/
abbrev Guard := Core.Guard

namespace Guard

abbrev unguarded : Guard :=
  Core.Guard.unguarded

abbrev atPos : PredId -> Guard :=
  Core.Guard.atPos

abbrev atNeg : PredId -> Guard :=
  Core.Guard.atNeg

end Guard

/-
Instruction type specifier for the bounded unit.
Only `.b32` is in scope; the unit identity fixes the mnemonic `not`, the type
`.b32`, and the empty modifier set (the scalar not syntax has no modifier
position). Claims PTX-NOT-SEM1-004/005/020.
-/
inductive NotTypeSpecifier where
  | b32 : NotTypeSpecifier
deriving DecidableEq, Repr

/-
8. Minimal state required by the approved semantics.
The state for the bounded base not.b32 is the pair (value-register file,
predicate-register file). No memory, shared, special-register, or concurrency
state is required by the base form's syntax and description
(PTX-NOT-SEM1-060; design D-5/D-14). Lookups are partial: `valueRegs r = none`
means register r is not defined in the state, represented as partial execution
rather than an invented error (PTX-NOT-SEM1-052/053/054).
-/
abbrev MachineState := Core.MachineState

/-
A well-formed not.b32 instruction: optional guard, destination d, then the
single source operand a in that order (operand order `d, a`; the destination
comes first). Claims PTX-NOT-SEM1-006/061; design D-1/D-16.
-/
structure NotB32Instruction where
  type : NotTypeSpecifier
  guard : Guard
  d : Destination
  a : SourceOperand
deriving DecidableEq, Repr

/-
9. Source-operand evaluation.
Reads the current (pre-instruction) value of a source: a register is read from
the value-register file. A missing register yields none (partial execution),
not an invented result.
Claims PTX-NOT-SEM1-036/043.
-/
def evalSource (s : MachineState) : SourceOperand -> Option B32
  | SourceOperand.reg r => s.valueRegs r

/-
10. Complete guard-expression evaluation.
- unguarded : true (unconditional execution)
- @p        : value of predicate register p
- @!p       : logical negation of the value of p
A missing predicate register yields none (partial execution).
Claims PTX-NOT-SEM1-022/037; design D-19.
-/
abbrev evalGuard := Core.evalGuard

/-
11. Explicit bitwise-complement rule (d = ~a;).
`complementValue` returns the bitwise complement of its argument over the
32-bit untyped `.b32` bit-value domain: every one of the 32 bits is inverted.
For the Fin (2^32) encoding, the bitwise complement of v is (2^32 - 1) - v,
because x + (~x) = 2^32 - 1 (all 32 bits set) for 0 <= x < 2^32. The
representation below carries the bound proof through `Nat.mod_lt` (the modulo
is a no-op for the in-range value (2^32 - 1) - v, which is always < 2^32);
this keeps the Fin bound proof definitionally immediate and purely
computational. This implements the not Semantics line `d = ~a;`
(PTX-NOT-SEM1-032, SOURCE_FACT) and the derived bit-complement semantics
(PTX-NOT-SEM1-033). The exact formal statement of the bit-complement fidelity
candidate obligation PRF-7 (each bit flipped) is a theorem-stage matter
(PTX-NOT-SEM1-072, OQ-8).
-/
def complementValue (v : B32) : B32 :=
  { toFin :=
      ⟨(b32DomainSize - 1 - v.toFin.val) % b32DomainSize,
       Nat.mod_lt (b32DomainSize - 1 - v.toFin.val) (by decide : 0 < b32DomainSize)⟩ }

/-
12. Destination update.
When the instruction executes and d is a register, the bounded MachineState
model updates only the destination value register and preserves all predicate
registers (PTX-NOT-SEM1-038/039). The model contains no carry-flag,
status-register, or condition-code component; the base form has no such
operands (PTX-NOT-SEM1-039).
When d is the bit bucket `_`, no value register is written (the result is
discarded), supported to the strength of the general section 9.2 rule
(PTX-NOT-SEM1-067).
-/
abbrev updateDestination := Core.updateDestination

/-
Execution outcome representation (design D-8; PTX-NOT-SEM1-064).
No error constructor is proposed because no explicit exceptional behavior for
the bounded base not.b32 is evidenced (PTX-NOT-SEM1-052, GAP-4).
-/
abbrev ExecOutcome := Core.ExecOutcome

namespace ExecOutcome

abbrev executed : MachineState -> ExecOutcome :=
  Core.ExecOutcome.executed

abbrev guardFalse : MachineState -> ExecOutcome :=
  Core.ExecOutcome.guardFalse

end ExecOutcome

/-
13. Guarded not.b32 execution.
- The complete guard expression is evaluated first.
- If the guard expression evaluates FALSE, the thread does nothing and the
  state is unchanged (PTX-NOT-SEM1-035; source-resolved via the section
  9.7.13.2 clause "Threads with a False guard predicate do nothing.",
  PTX-9.3-NOT-031/032). Source operands are NOT read in this branch.
- If the guard expression evaluates TRUE (including the unguarded case), the
  source value is read and the destination is updated with its bitwise
  complement (d = ~a;) (claims PTX-NOT-SEM1-033/034/038). The source is read
  from the pre-instruction state before the destination update, so a
  destination that aliases the source register retains its own value
  (read-before-write; PTX-NOT-SEM1-065).
- `none` denotes PARTIAL execution: a required register lookup (guard predicate
  or source register) is not defined in the state. It is not an error, trap, or
  undefined behavior (PTX-NOT-SEM1-052/053/054).
-/
def execNotB32 (s : MachineState) (i : NotB32Instruction) : Option ExecOutcome :=
  match evalGuard s i.guard with
  | none => none
  | some false => some (ExecOutcome.guardFalse s)
  | some true =>
      match evalSource s i.a with
      | some va => some (ExecOutcome.executed (updateDestination s i.d (complementValue va)))
      | none => none

/-
14. Relational form of the execution semantics.
The approved execution-semantics representation design (architecture D-25;
PTX-NOT-SEM1-063) specifies the future execution semantics as an execution
relation between (state, instruction) and state, not merely as a function, so
that determinism (PRF-1) and frame/locality obligations (PRF-2..PRF-5) are
non-vacuous. This inductive relation is the relational counterpart of the
executable function `execNotB32`: it relates s to the unchanged state exactly
when the complete guard expression evaluates false, and to the updated state
exactly when the guard is true and the source resolves. The correspondence
between the relation and the executable function is a theorem-stage obligation
(PRF-1 family).
-/
inductive NotB32Step : MachineState -> NotB32Instruction -> MachineState -> Prop where
  | guardFalse : (s : MachineState) -> (i : NotB32Instruction) ->
      evalGuard s i.guard = some false -> NotB32Step s i s
  | executed : (s : MachineState) -> (i : NotB32Instruction) -> (va : B32) ->
      evalGuard s i.guard = some true ->
      evalSource s i.a = some va ->
      NotB32Step s i (updateDestination s i.d (complementValue va))

/-! # Helper definitions for executable examples (not semantic definitions) -/

-- Convenience constructor: reduce a Nat to the B32 domain modulo 2^32.
-- This is an example helper; it does not add semantics beyond complementValue.
abbrev mkB32 := Core.mkB32

-- Convenience state constructor from binding lists (first binding wins).
-- This is an example helper for the minimal state design (PTX-NOT-SEM1-060).
abbrev mkState := Core.mkState

-- Example-only identifiers (not part of the semantics).
private def exR1 : RegId := { name := "r1" }
private def exR2 : RegId := { name := "r2" }
private def exP1 : PredId := { name := "p1" }

/-! # Executable examples (demonstrative only; not proofs) -/

-- Complement rule: ~0 = 0xFFFFFFFF (d = ~a; PTX-NOT-SEM1-033).
#eval complementValue (mkB32 0)

-- Complement rule: ~0xFFFFFFFF = 0.
#eval complementValue (mkB32 0xFFFFFFFF)

-- Complement of 5 over 32 bits: ~5 = 0xFFFFFFFA = 4294967290.
#eval complementValue (mkB32 5)

-- Unguarded complete guard expression is true (PTX-NOT-SEM1-022).
#eval evalGuard (mkState [] []) Guard.unguarded

-- @!p with p = false: complete guard expression is true.
#eval evalGuard (mkState [] [(exP1, false)]) (Guard.atNeg exP1)

-- Destination update writes only the destination register (PTX-NOT-SEM1-038).
#eval (updateDestination (mkState [(exR1, mkB32 1), (exR2, mkB32 2)] [])
         (Destination.reg exR1) (mkB32 100)).valueRegs exR1

-- Bit bucket `_`: no value register is written (PTX-NOT-SEM1-067, general
-- section 9.2 rule strength).
#eval (updateDestination (mkState [(exR1, mkB32 1)] [])
         Destination.bitBucket (mkB32 100)).valueRegs exR1

-- @p with p = false: instruction is not executed, state unchanged (r1 stays 5).
#eval
  let st : MachineState := mkState [(exR1, mkB32 5)] [(exP1, false)]
  let inst : NotB32Instruction :=
    { type := NotTypeSpecifier.b32, guard := Guard.atPos exP1,
      d := Destination.reg exR1, a := SourceOperand.reg exR1 }
  match execNotB32 st inst with
  | some (.guardFalse s') => s'.valueRegs exR1
  | some (.executed s') => s'.valueRegs exR1
  | none => none

-- @!p with p = false: guard expression true, executes, r1 becomes ~5.
#eval
  let st : MachineState := mkState [(exR1, mkB32 5)] [(exP1, false)]
  let inst : NotB32Instruction :=
    { type := NotTypeSpecifier.b32, guard := Guard.atNeg exP1,
      d := Destination.reg exR1, a := SourceOperand.reg exR1 }
  match execNotB32 st inst with
  | some (.guardFalse s') => s'.valueRegs exR1
  | some (.executed s') => s'.valueRegs exR1
  | none => none

-- Aliasing d == a: the source is read before the destination update, so r1
-- becomes ~5 (read-before-write; PTX-NOT-SEM1-065, official example
-- `not.b32 mask,mask;`).
#eval
  let st : MachineState := mkState [(exR1, mkB32 5)] []
  let inst : NotB32Instruction :=
    { type := NotTypeSpecifier.b32, guard := Guard.unguarded,
      d := Destination.reg exR1, a := SourceOperand.reg exR1 }
  match execNotB32 st inst with
  | some (.guardFalse s') => s'.valueRegs exR1
  | some (.executed s') => s'.valueRegs exR1
  | none => none

-- Partial execution: a missing source register yields none, not an invented
-- error (PTX-NOT-SEM1-052/053/054).
#eval
  let st : MachineState := mkState [] [(exP1, true)]
  let inst : NotB32Instruction :=
    { type := NotTypeSpecifier.b32, guard := Guard.atPos exP1,
      d := Destination.reg exR1, a := SourceOperand.reg exR1 }
  match execNotB32 st inst with
  | some (.guardFalse _) => "guard-false"
  | some (.executed _) => "executed"
  | none => "partial-none"

end NotB32
end PTX
end Spec2Lean
