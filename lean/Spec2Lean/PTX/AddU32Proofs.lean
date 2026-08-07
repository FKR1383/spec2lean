/-
Spec2Lean machine-checked proof candidate — PTX ISA 9.3 `add.u32`

Bounded formalization unit : PTX ISA 9.3 `add.u32` (base scalar, non-saturating,
                            unsigned 32-bit add)
Imported Lean semantics   : lean/Spec2Lean/PTX/AddU32.lean
Approved theorem set      : candidates/ptx/9.3/theorems/add-u32-obligations-v1.json
Theorem-strength decision : reviews/ptx-add-u32/theorem-strength/ptx-add-u32-theorem-strength-v1.json
                            (decision: approved; six theorem obligations plus one
                            read-before-write aliasing corollary)
Human overflow assumption : reviews/ptx-add-u32/assumptions/ptx-add-u32-overflow-assumption-v1.json
                            (decision: approved)

WARNING — HUMAN-APPROVED PROJECT ASSUMPTION (NOT AN NVIDIA SOURCE FACT):
  The modulo-2^32 result rule d := (a + b) mod 2^32 implemented by `addU32`
  is the project-level formalization assumption recorded in
  reviews/ptx-add-u32/assumptions/ptx-add-u32-overflow-assumption-v1.json
  (semantic claim PTX-ADD-SEM2-015). It is NOT an NVIDIA source fact and must
  never be presented as explicitly specified by NVIDIA. Only PTX-ADD-THM-002
  and the aliasing corollary `execAddU32_alias_source_a_uses_pre_state_value`
  depend on this modulo rule; their conclusions trace their modulo content to
  this human-approved assumption.

This file proves exactly the six approved theorem obligations
(PTX-ADD-THM-001 .. PTX-ADD-THM-006) and the one human-approved
read-before-write aliasing corollary. It does not modify AddU32.lean and
contains no sorry, admit, axiom, or unsafe.
-/

import Spec2Lean.PTX.AddU32

namespace Spec2Lean
namespace PTX

/-!
# PTX-ADD-THM-001 — totality on the well-formed lookup domain

`execAddU32_total_on_well_formed_lookup_domain`

On the approved well-formed lookup domain (the complete guard expression
resolves, and both sources resolve whenever the guard is true), `execAddU32`
always returns some outcome. `none` is never returned there; `none` denotes
partial execution for out-of-domain states only (PTX-ADD-SEM2-044/045/046/050),
never an error. This theorem does NOT demand source lookup when the guard is
false (`hsources` is guarded by `b = true`).
-/
theorem execAddU32_total_on_well_formed_lookup_domain
    (s : MachineState) (i : AddU32Instruction) (b : Bool)
    (hguard : evalGuard s i.guard = some b)
    (hsources : b = true -> (Exists fun va => Exists fun vb =>
        evalSource s i.a = some va /\
        evalSource s i.b = some vb)) :
    Exists fun (o : ExecOutcome) => execAddU32 s i = some o := by
  cases b with
  | false =>
      -- Guard false: no source lookup is needed; outcome is guardFalse s.
      refine ⟨ExecOutcome.guardFalse s, ?_⟩
      simp [execAddU32, hguard]
  | true =>
      -- Guard true: both sources resolve by hsources.
      rcases hsources rfl with ⟨va, vb, ha, hb⟩
      refine ⟨ExecOutcome.executed (updateDestination s i.d (addU32 va vb)), ?_⟩
      simp [execAddU32, hguard, ha, hb]

/-!
# PTX-ADD-THM-002 — arithmetic result conformance with read-before-write

`execAddU32_result_conforms_modulo_with_read_before_write`

When the guard is true and the destination is register r, the value written to
r is `addU32 va vb`, where `va` and `vb` are the source values read from the
PRE-instruction state s. Because the reads are pinned to s (never to the
post-state), this theorem subsumes read-before-write aliasing: when the
destination aliases a source register, the write is computed from the
pre-update value (PTX-ADD-SEM2-043).

MODULO TRACEABILITY: `addU32 va vb` is `(va + vb) mod 2^32` under the
HUMAN-APPROVED project assumption PTX-ADD-SEM2-015
(reviews/ptx-add-u32/assumptions/ptx-add-u32-overflow-assumption-v1.json).
This modulo rule is NOT an NVIDIA source fact and is never attributed to
NVIDIA as explicitly specified.
-/
theorem execAddU32_result_conforms_modulo_with_read_before_write
    (s : MachineState) (i : AddU32Instruction) (r : RegId) (va vb : U32)
    (hguard : evalGuard s i.guard = some true)
    (hd : i.d = Destination.reg r)
    (ha : evalSource s i.a = some va)
    (hb : evalSource s i.b = some vb) :
    Exists fun (s' : MachineState) =>
      execAddU32 s i = some (ExecOutcome.executed s') /\
      s'.valueRegs r = some (addU32 va vb) := by
  refine ⟨updateDestination s i.d (addU32 va vb), ?_⟩
  constructor
  · -- The executed outcome is reached with the computed value.
    simp [execAddU32, hguard, ha, hb]
  · -- The destination register r receives addU32 va vb.
    rw [hd]
    simp [updateDestination]

/-!
# PTX-ADD-THM-003 — guard-false state preservation

`execAddU32_guard_false_preserves_state`

When the complete guard expression evaluates false, `execAddU32` returns
exactly `some (ExecOutcome.guardFalse s)`: the outcome carries exactly the
input state s, so no machine-state component changes and no source operand is
read (the guard-false branch returns before evaluating sources). This is the
guard-false frame property, derived from the official predication clause
(PTX-ADD-SEM2-022/023/024/031); it is not a human assumption.
-/
theorem execAddU32_guard_false_preserves_state
    (s : MachineState) (i : AddU32Instruction)
    (hguard : evalGuard s i.guard = some false) :
    execAddU32 s i = some (ExecOutcome.guardFalse s) := by
  simp [execAddU32, hguard]

/-!
# PTX-ADD-THM-004 — destination-only frame

`execAddU32_destination_only_frame`

When the instruction executes with guard true and destination register r, the
only value register that may change is r; every other value register and every
predicate register is unchanged. The statement is strictly over the bounded
MachineState (value-register file plus predicate-register file) and retains
the negative-evidence caveat: the bounded model contains no carry-flag,
status-register, or condition-code component, and the absence of such writes
is absence-based negative evidence (SEM2-CRIT-F1 / LMAP-CRIT-F1 / risk R-1),
not an affirmative NVIDIA enumeration.
-/
theorem execAddU32_destination_only_frame
    (s : MachineState) (i : AddU32Instruction) (r : RegId) (va vb : U32)
    (hguard : evalGuard s i.guard = some true)
    (hd : i.d = Destination.reg r)
    (ha : evalSource s i.a = some va)
    (hb : evalSource s i.b = some vb) :
    Exists fun (s' : MachineState) =>
      execAddU32 s i = some (ExecOutcome.executed s') /\
      (forall (r' : RegId), r' ≠ r -> s'.valueRegs r' = s.valueRegs r') /\
      (forall (p : PredId), s'.predRegs p = s.predRegs p) := by
  refine ⟨updateDestination s i.d (addU32 va vb), ?_⟩
  constructor
  · -- The executed outcome is reached with the computed value.
    simp [execAddU32, hguard, ha, hb]
  constructor
  · -- Unrelated value registers are preserved.
    intro r' hr'
    rw [hd]
    -- simp rewrites the update condition (r' == r) = true to r' = r and
    -- reduces the if-equality, leaving the vacuous implication
    -- r' = r -> some (addU32 va vb) = s.valueRegs r'.  Since
    -- hr' : r' ≠ r, the antecedent is refutable.
    simp [updateDestination]
    intro hrr
    exfalso
    exact hr' hrr
  · -- Predicate registers are preserved.
    intro p
    rw [hd]
    simp [updateDestination]

/-!
# PTX-ADD-THM-005 — bit-bucket state preservation

`execAddU32_bit_bucket_preserves_state`

When the destination is the bit bucket `_`, the instruction executes (guard
true, sources resolve) but no value register is written and the whole modeled
state is unchanged: the executed outcome's state is exactly the input state s
(the result is discarded). STRENGTH CAVEAT: the no-write consequence is
supported only to the strength of the general section 9.2 bit-bucket rule
(AMB-1 / PTX-ADD-SEM2-030/047 / risk R-4); the add section does not
demonstrate the bit-bucket form, so this is not an add-specific explicit
NVIDIA source fact.
-/
theorem execAddU32_bit_bucket_preserves_state
    (s : MachineState) (i : AddU32Instruction) (va vb : U32)
    (hguard : evalGuard s i.guard = some true)
    (hd : i.d = Destination.bitBucket)
    (ha : evalSource s i.a = some va)
    (hb : evalSource s i.b = some vb) :
    Exists fun (s' : MachineState) =>
      execAddU32 s i = some (ExecOutcome.executed s') /\
      s' = s := by
  refine ⟨updateDestination s i.d (addU32 va vb), ?_⟩
  constructor
  · -- The executed outcome is reached with the computed value.
    simp [execAddU32, hguard, ha, hb]
  · -- The bit-bucket branch of updateDestination returns the input state.
    rw [hd]
    simp [updateDestination]

/-!
# PTX-ADD-THM-006 — executes iff guard true

`execAddU32_executes_iff_guard_true`

On the approved well-formed lookup domain, an executed outcome occurs if and
only if the complete guard expression evaluates true. This pins the outcome
classification of `execAddU32` (PTX-ADD-SEM2-023/024/050). It complements
THM-003: an executed outcome implies the guard was true, so an instruction can
never execute under a false complete guard. This is a classification statement,
not a determinism claim (PRF-1 is deferred). Source lookup is required only
when the guard is true (`hsources` is guarded by `b = true`).
-/
theorem execAddU32_executes_iff_guard_true
    (s : MachineState) (i : AddU32Instruction) (b : Bool)
    (hguard : evalGuard s i.guard = some b)
    (hsources : b = true -> (Exists fun va => Exists fun vb =>
        evalSource s i.a = some va /\
        evalSource s i.b = some vb)) :
    (Exists fun (s' : MachineState) =>
        execAddU32 s i = some (ExecOutcome.executed s')) <-> b = true := by
  constructor
  · -- executed outcome -> b = true
    rintro ⟨s', hexec'⟩
    by_cases hb : b = true
    · exact hb
    · exfalso
      have hbf : b = false := by
        cases b
        · rfl
        · exact False.elim (hb rfl)
      -- With guard false the code returns guardFalse, never executed; simp
      -- reduces the hypothesis to False and closes the goal.
      simp [execAddU32, hguard, hbf] at hexec'
  · -- b = true -> executed outcome exists
    intro hb
    rw [hb] at hguard hsources
    rcases hsources rfl with ⟨va, vb, ha, hb'⟩
    refine ⟨updateDestination s i.d (addU32 va vb), ?_⟩
    simp [execAddU32, hguard, ha, hb']

/-!
# Approved aliasing corollary — read-before-write with d == a

`execAddU32_alias_source_a_uses_pre_state_value`

Specialization of PTX-ADD-THM-002 for the official aliasing shape
`add.u32 %r, %r, ...` (PTX-9.3-ADD-025): when the guard is true, the
destination is register r, source a is the same register r, the pre-state
value of r is `va` (`s.valueRegs r = some va`), and source b resolves to `vb`,
then execution produces a post-state whose destination value is
`addU32 va vb`. The hypotheses pin `va` to the PRE-UPDATE value of r, exposing
the read-before-write behavior (PTX-ADD-SEM2-043).

MODULO TRACEABILITY: the written value `addU32 va vb` is `(va + vb) mod 2^32`
under the HUMAN-APPROVED project assumption PTX-ADD-SEM2-015
(reviews/ptx-add-u32/assumptions/ptx-add-u32-overflow-assumption-v1.json).
This modulo rule is NOT an NVIDIA source fact and is never attributed to
NVIDIA as explicitly specified. The corollary is a direct consequence of
THM-002 and adds no semantic assumption.
-/
theorem execAddU32_alias_source_a_uses_pre_state_value
    (s : MachineState) (i : AddU32Instruction) (r : RegId) (va vb : U32)
    (hguard : evalGuard s i.guard = some true)
    (hd : i.d = Destination.reg r)
    (ha : i.a = SourceOperand.reg r)
    (hva : s.valueRegs r = some va)
    (hb : evalSource s i.b = some vb) :
    Exists fun (s' : MachineState) =>
      execAddU32 s i = some (ExecOutcome.executed s') /\
      s'.valueRegs r = some (addU32 va vb) := by
  -- va is the pre-state value of source a because i.a is register r.
  have ha' : evalSource s i.a = some va := by
    rw [ha]
    simp [evalSource, hva]
  -- Direct consequence of THM-002.
  exact execAddU32_result_conforms_modulo_with_read_before_write s i r va vb hguard hd ha' hb

end PTX
end Spec2Lean
