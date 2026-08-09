/-
Spec2Lean machine-checked proof candidate — PTX ISA 9.3 `not.b32`

Approved theorem set:
  candidates/ptx/9.3/units/not-b32/theorems/obligations-v1.json
  (obligation set ptx-9.3-not-b32-obligations-v1, run ptx-9.3-not.b32-5e83de43)
Human theorem-strength approval:
  (authoritative theorem statements supplied by the orchestrator for the
  PROOF_GENERATION stage)
Imported packaged semantics:
  lean/Spec2Lean/PTX/NotB32.lean
  (namespace Spec2Lean.PTX.NotB32)

This file states the approved theorem obligations at their reviewed strength.
It does not modify semantics and must contain no sorry, admit, new axiom, or
unsafe verification bypass.

Current content: PTX-NOT-THM-001 (relational determinism over NotB32Step,
semantics PRF-1 / design D-25), PTX-NOT-THM-002 parts (a), (b), (c), and
(d) (function/relation correspondence: executable `execNotB32` is sound with
respect to `NotB32Step` on the executed outcome and on the guard-false
outcome, is complete in that every `NotB32Step` is realized by some function
outcome, and is partial-complete in that `execNotB32 s i = none` occurs
exactly when the relation admits no step). The relation omits the none
partial case (it relates only complete executions; mapping decision D-25 /
mapping-critic F-3), so the correspondence is precise rather than hiding
partiality: no statement here asserts any totality of execNotB32.
Also present: PTX-NOT-THM-003 (complement fidelity: with a true guard and a
resolved register source, execution writes `complementValue va` to the
register destination; PRF-7, complement rule `d = ~a;` per
PTX-NOT-SEM1-032/033, read-before-write aliasing per PTX-NOT-SEM1-065).
Also present: PTX-NOT-THM-004 (destination-only frame over the relational
step: when the destination is register r, every other value register and
every predicate register is unchanged; semantics PRF-2, derived claims
PTX-NOT-SEM1-038/039, with the risk R-1 negative-evidence caveat that the
bounded model contains no carry/status component and the absence of such
writes must not be cited as an explicit NVIDIA enumeration).
Also present: PTX-NOT-THM-005 (bit-bucket destination preserves the whole
state: when `i.d = Destination.bitBucket`, the related state s' equals s and
the computed value is discarded; semantics PRF-3, supported only to the
strength of the general section 9.2 bit-bucket rule, PTX-NOT-SEM1-011/067,
with the risk R-3 caveat that the scalar not.b32-specific applicability of
the bit-bucket form remains an open question (PTX-NOT-SEM1-067, mapping-critic
F-2) and must not be presented as not.b32-specific explicit NVIDIA behavior).
Also present: PTX-NOT-THM-006 (guard-false preserves the whole state: when
the complete guard expression evaluates to false, `execNotB32 s i` returns
`some (ExecOutcome.guardFalse s)` carrying exactly the unchanged input state,
and the relational step `NotB32Step s i s'` yields `s' = s`;
DERIVED_INTERPRETATION from the explicit predication clause applied to
not.b32, PTX-NOT-SEM1-035/031, source facts PTX-9.3-NOT-031/032; stated over
the bounded model state pair only, deferred property PTX-NOT-DEF-001).
Also present: PTX-NOT-THM-007 (guard classification: `execNotB32` produces an
executed outcome exactly when the complete guard expression is true; PRF-5,
per-constructor guard evaluation facts; classification statement, not a
determinism claim) and its supporting per-constructor guard-evaluation lemmas
`evalGuard_unguarded_true` (the unguarded complete guard expression is true,
PTX-NOT-SEM1-022, design D-19), `evalGuard_atPos_true` (the `@p` guard
expression is `some true` when the predicate lookup is `some true`,
PTX-NOT-SEM1-022, design D-19), `evalGuard_atPos_false` (the `@p` guard
expression is `some false` when the predicate lookup is `some false`,
PTX-NOT-SEM1-022, design D-19), `evalGuard_atNeg_true_when_pred_false`
(the `@!p` guard expression is `some true` when the predicate lookup is
`some false`, PTX-NOT-SEM1-022/037, design D-19), and
`evalGuard_atNeg_false_when_pred_true` (the `@!p` guard expression is
`some false` when the predicate lookup is `some true`, PTX-NOT-SEM1-022/037,
design D-19).

Note on notation: the theorem statements use `Not` (the Prop negation) for
the approved statement's `not`; in this Lean environment the lowercase
identifier `not` resolves to `Bool.not` (the `!` operator on Bool), so
`not (P : Prop)` would be ill-typed. `Not P` is the identical proposition.
Note on inequality notation: PTX-NOT-THM-004 follows the approved statement's
`r' != r` (Boolean inequality over the DecidableEq-derived BEq on RegId, which
elaborates as a hypothesis to `(r' != r) = true` and simplifies to
`¬ r' = r`), matching `updateDestination`'s update condition `r' == r`.
-/

import Spec2Lean.PTX.NotB32

namespace Spec2Lean
namespace PTX
namespace NotB32

/-! ## PTX-NOT-THM-001 — relational determinism -/

theorem notB32Step_deterministic
    (s : MachineState) (i : NotB32Instruction) (s1 s2 : MachineState)
    (h1 : NotB32Step s i s1) (h2 : NotB32Step s i s2) :
    s1 = s2 := by
  cases h1 with
  | guardFalse hg1 =>
      cases h2 with
      | guardFalse _ =>
          rfl
      | executed _ hg2 _ =>
          exfalso
          rw [hg1] at hg2
          simp at hg2
  | executed va1 hg1 ha1 =>
      cases h2 with
      | guardFalse hg2 =>
          exfalso
          rw [hg2] at hg1
          simp at hg1
      | executed va2 _ ha2 =>
          have hva : va1 = va2 := by
            rw [ha1] at ha2
            simpa using ha2
          rw [hva]

/-! ## PTX-NOT-THM-002 — executable function is sound with respect to the
execution relation -/

/-! ### PTX-NOT-THM-002 (a) — soundness on the executed outcome -/

theorem exec_sound_executed
    (s : MachineState) (i : NotB32Instruction) (s' : MachineState)
    (h : execNotB32 s i = some (ExecOutcome.executed s')) :
    NotB32Step s i s' := by
  unfold execNotB32 at h
  cases hg : evalGuard s i.guard with
  | none =>
      simp [hg] at h
  | some b =>
      cases b with
      | false =>
          simp [hg] at h
      | true =>
          cases hs : evalSource s i.a with
          | none =>
              simp [hg, hs] at h
          | some va =>
              simp [hg, hs] at h
              rw [← h]
              exact NotB32Step.executed s i va hg hs

/-! ### PTX-NOT-THM-002 (b) — soundness on the guard-false outcome -/

theorem exec_sound_guardFalse
    (s : MachineState) (i : NotB32Instruction) (s' : MachineState)
    (h : execNotB32 s i = some (ExecOutcome.guardFalse s')) :
    NotB32Step s i s' := by
  unfold execNotB32 at h
  cases hg : evalGuard s i.guard with
  | none =>
      simp [hg] at h
  | some b =>
      cases b with
      | false =>
          simp [hg] at h
          rw [← h]
          exact NotB32Step.guardFalse s i hg
      | true =>
          cases hs : evalSource s i.a with
          | none =>
              simp [hg, hs] at h
          | some va =>
              simp [hg, hs] at h

/-! ### PTX-NOT-THM-002 (c) — completeness: every step is realized by some
function outcome -/

theorem step_complete
    (s : MachineState) (i : NotB32Instruction) (s' : MachineState)
    (h : NotB32Step s i s') :
    Exists fun (o : ExecOutcome) =>
      execNotB32 s i = some o /\
      (o = ExecOutcome.executed s' \/ o = ExecOutcome.guardFalse s') := by
  cases h with
  | guardFalse hg =>
      refine ⟨ExecOutcome.guardFalse s, ?_, ?_⟩
      · unfold execNotB32
        simp [hg]
      · right
        rfl
  | executed va hg hs =>
      refine ⟨ExecOutcome.executed (updateDestination s i.d (complementValue va)), ?_, ?_⟩
      · unfold execNotB32
        simp [hg, hs]
      · left
        rfl

/-! ### PTX-NOT-THM-002 (d) — partial-completeness: none occurs exactly when
the relation admits no step -/

theorem step_partial_complete
    (s : MachineState) (i : NotB32Instruction) :
    execNotB32 s i = none <->
      Not (Exists fun (s' : MachineState) => NotB32Step s i s') := by
  unfold execNotB32
  cases hg : evalGuard s i.guard with
  | none =>
      constructor
      · intro _ hstep
        rcases hstep with ⟨s', hstep'⟩
        cases hstep' with
        | guardFalse hg' =>
            rw [hg] at hg'
            cases hg'
        | executed va hg' hs' =>
            rw [hg] at hg'
            cases hg'
      · intro _
        rfl
  | some b =>
      cases b with
      | false =>
          constructor
          · intro h
            cases h
          · intro hnot
            exfalso
            exact hnot ⟨s, NotB32Step.guardFalse s i hg⟩
      | true =>
          cases hs : evalSource s i.a with
          | none =>
              constructor
              · intro _ hstep
                rcases hstep with ⟨s', hstep'⟩
                cases hstep' with
                | guardFalse hg' =>
                    rw [hg] at hg'
                    cases hg'
                | executed va hg' hs' =>
                    rw [hs] at hs'
                    cases hs'
              · intro _
                rfl
          | some va =>
              constructor
              · intro h
                cases h
              · intro hnot
                exfalso
                exact hnot ⟨updateDestination s i.d (complementValue va), NotB32Step.executed s i va hg hs⟩

/-! ## PTX-NOT-THM-003 — complement fidelity: d = ~a -/

theorem execNotB32_complement_fidelity
    (s : MachineState) (i : NotB32Instruction) (r : RegId) (va : B32)
    (hguard : evalGuard s i.guard = some true)
    (hd : i.d = Destination.reg r)
    (ha : evalSource s i.a = some va) :
    Exists fun (s' : MachineState) =>
      execNotB32 s i = some (ExecOutcome.executed s') /\
      s'.valueRegs r = some (complementValue va) := by
  refine ⟨updateDestination s i.d (complementValue va), ?_, ?_⟩
  · simp [execNotB32, hguard, ha]
  · unfold updateDestination
    rw [hd]
    simp

/-! ## PTX-NOT-THM-004 — destination-only frame

Strength caveats (approved; obligations-v1.json PTX-NOT-THM-004):
- Risk R-1 (PTX-NOT-SEM1-039/052/053/054): this theorem is stated over the
  bounded model only (value-register file plus predicate-register file) and
  must not be cited as an explicit NVIDIA statement that "no carry flag /
  status register is written". The absence-based caveat remains traceable
  until final acceptance.
- This theorem does not assert the value written to r itself (that is
  PTX-NOT-THM-003); it makes no assertion about components outside the model.
-/

theorem notB32Step_destination_only_frame
    (s : MachineState) (i : NotB32Instruction) (s' : MachineState) (r : RegId)
    (hstep : NotB32Step s i s')
    (hd : i.d = Destination.reg r) :
    (forall (r' : RegId), r' != r -> s'.valueRegs r' = s.valueRegs r') /\
    (forall (p : PredId), s'.predRegs p = s.predRegs p) := by
  cases hstep with
  | guardFalse _ =>
      constructor
      · intro r' _
        rfl
      · intro p
        rfl
  | executed va _ _ =>
      constructor
      · intro r' hr'
        rw [hd]
        simp [updateDestination]
        simp at hr'
        intro hrr
        exfalso
        exact hr' hrr
      · intro p
        rw [hd]
        simp [updateDestination]

/-! ## PTX-NOT-THM-005 — bit-bucket destination preserves the whole state

Strength caveats (approved; obligations-v1.json PTX-NOT-THM-005):
- Risk R-3 (AMB-3 / PTX-NOT-SEM1-067 / mapping-critic F-2): this theorem must
  not be presented as not.b32-specific explicit NVIDIA behavior; it is
  supported only to the strength of the general section 9.2 bit-bucket rule
  (SOURCE_FACT PTX-NOT-SEM1-011 / fragment PTX-9.3-NOT-016). PRF-3 strength
  must not exceed this.
- If the theorem-strength review decides the bit-bucket constructor should be
  deferred until the scalar applicability question (PTX-NOT-SEM1-067) is
  resolved, this obligation is removed or weakened accordingly; the current
  statement is faithful to the Gate-C-approved Lean mapping, which materializes
  the constructor at candidate strength (mapping-critic F-2).
-/

theorem notB32Step_bit_bucket_preserves_state
    (s : MachineState) (i : NotB32Instruction) (s' : MachineState)
    (hstep : NotB32Step s i s')
    (hd : i.d = Destination.bitBucket) :
    s' = s := by
  cases hstep with
  | guardFalse _ =>
      rfl
  | executed va _ _ =>
      rw [hd]
      simp [updateDestination]

/-! ## PTX-NOT-THM-006 — guard-false preserves the whole state

Strength caveats (approved; obligations-v1.json PTX-NOT-THM-006):
- The guard-false behavior is a DERIVED_INTERPRETATION from the explicit
  predication clause applied to not.b32 (PTX-NOT-SEM1-035/031): threads with
  a false guard predicate do nothing (section 9.7.13.2 clause, source facts
  PTX-9.3-NOT-031/032). This theorem is never presented as an affirmative
  per-instruction SOURCE_FACT that the PTX not section itself states this.
- The theorem is stated over the bounded model state pair (value-register
  file and predicate-register file); it does not by itself assert anything
  about components outside the model (deferred property PTX-NOT-DEF-001).
- The equality to `ExecOutcome.guardFalse s` (carrying exactly s) is a full
  state-preservation statement because guardFalse carries the whole
  MachineState and the only producer of guardFalse in execNotB32 is the
  unchanged input state.
-/

theorem execNotB32_guard_false_preserves_state
    (s : MachineState) (i : NotB32Instruction)
    (hguard : evalGuard s i.guard = some false) :
    execNotB32 s i = some (ExecOutcome.guardFalse s) := by
  unfold execNotB32
  simp [hguard]

/-! ### PTX-NOT-THM-006 (relational form) — guard-false frame over
`NotB32Step`: the related state is exactly the unchanged input state. This is
the relational counterpart of `execNotB32_guard_false_preserves_state`; the
only producer of the guard-false branch in `execNotB32` is the unchanged
input state, and the only `NotB32Step` constructor with a false guard is
`NotB32Step.guardFalse s i _`, whose related state is s itself. -/

theorem notB32Step_guard_false_frame
    (s : MachineState) (i : NotB32Instruction) (s' : MachineState)
    (hstep : NotB32Step s i s')
    (hguard : evalGuard s i.guard = some false) :
    s' = s := by
  cases hstep with
  | guardFalse _ =>
      rfl
  | executed va hg _ =>
      rw [hguard] at hg
      simp at hg

/-! ## PTX-NOT-THM-007 — guard classification: executed outcome iff complete
guard expression is true

Strength caveats (approved; PRF-5):
- This theorem is a classification/guard-behavior statement, not a
  determinism claim; it must not be mistaken for PTX-NOT-THM-001 (relational
  determinism) or for the functional single-valuedness of `execNotB32`.
- The hypothesis shape matches the well-formed lookup domain exactly:
  `hsources` is conditioned on `b = true`, so no source-resolution hypothesis
  is assumed unconditionally (adding one unconditionally, even when
  `b = false`, would be an unapproved strengthening and would make the
  reverse direction trivial in a different way).
- The proof is a simple per-constructor definitional case analysis (the
  per-constructor guard evaluation facts behind PRF-5); it is not presented
  as a deep semantic theorem. The two directions are:
  - (->) if some executed state is produced, the guard must have been true
    (the guard-false branch returns `ExecOutcome.guardFalse`, never
    `ExecOutcome.executed`);
  - (<-) if the guard is true, the well-formed-domain hypothesis provides a
    resolvable source value, so the executed branch is taken.
-/

/-! ### PTX-NOT-THM-007 (supporting lemma) — unguarded complete guard
expression evaluates to true

Definitional per-constructor guard-evaluation fact behind PRF-5: the
`Guard.unguarded` constructor's complete guard expression is `some true`
(unconditional execution; semantics PTX-NOT-SEM1-022, design D-19). This is a
simple definitional statement (the `evalGuard` clause `Guard.unguarded =>
some true`), not a deep semantic theorem. It is presented only as the
per-constructor guard evaluation fact behind PRF-5, never as a determinism or
totality claim. -/

theorem evalGuard_unguarded_true
    (s : MachineState) : evalGuard s Guard.unguarded = some true := by
  simp [evalGuard]

/-! ### PTX-NOT-THM-007 (supporting lemma) — `@p` guard expression evaluates
to true when the predicate lookup is true

Definitional per-constructor guard-evaluation fact behind PRF-5: the
`Guard.atPos` constructor's complete guard expression is the predicate value
`some true` exactly when the well-formed lookup domain contains `p -> true`
(semantics PTX-NOT-SEM1-022, design D-19). This is a simple definitional
statement (the `evalGuard` clause `Guard.atPos p => s.predRegs p`), not a
deep semantic theorem. It is presented only as the per-constructor guard
evaluation fact behind PRF-5, never as a determinism or totality claim. -/

theorem evalGuard_atPos_true
    (s : MachineState) (p : PredId) (h : s.predRegs p = some true) :
    evalGuard s (Guard.atPos p) = some true := by
  simp [evalGuard, h]

/-! ### PTX-NOT-THM-007 (supporting lemma) — `@p` guard expression evaluates
to false when the predicate lookup is false

Definitional per-constructor guard-evaluation fact behind PRF-5: the
`Guard.atPos` constructor's complete guard expression is the predicate value
`some false` exactly when the well-formed lookup domain contains `p -> false`
(semantics PTX-NOT-SEM1-022, design D-19). This is a simple definitional
statement (the `evalGuard` clause `Guard.atPos p => s.predRegs p`), not a
deep semantic theorem. It is presented only as the per-constructor guard
evaluation fact behind PRF-5, never as a determinism or totality claim. -/

theorem evalGuard_atPos_false
    (s : MachineState) (p : PredId) (h : s.predRegs p = some false) :
    evalGuard s (Guard.atPos p) = some false := by
  simp [evalGuard, h]

/-! ### PTX-NOT-THM-007 (supporting lemma) — `@!p` guard expression evaluates
to true when the predicate lookup is false

Definitional per-constructor guard-evaluation fact behind PRF-5: the
`Guard.atNeg` constructor's complete guard expression is the logical negation
of the predicate value, so it is `some true` exactly when the well-formed
lookup domain contains `p -> false` (semantics PTX-NOT-SEM1-022/037, design
D-19). This is a simple definitional statement (the `evalGuard` clause
`Guard.atNeg p => ... some (not b)` with `not false = true`), not a deep
semantic theorem. It is presented only as the per-constructor guard
evaluation fact behind PRF-5, never as a determinism or totality claim. -/

theorem evalGuard_atNeg_true_when_pred_false
    (s : MachineState) (p : PredId) (h : s.predRegs p = some false) :
    evalGuard s (Guard.atNeg p) = some true := by
  simp [evalGuard, h]

/-! ### PTX-NOT-THM-007 (supporting lemma) — `@!p` guard expression evaluates
to false when the predicate lookup is true

Definitional per-constructor guard-evaluation fact behind PRF-5: the
`Guard.atNeg` constructor's complete guard expression is the logical negation
of the predicate value, so it is `some false` exactly when the well-formed
lookup domain contains `p -> true` (semantics PTX-NOT-SEM1-022/037, design
D-19). This is a simple definitional statement (the `evalGuard` clause
`Guard.atNeg p => ... some (not b)` with `not true = false`), not a deep
semantic theorem. It is presented only as the per-constructor guard
evaluation fact behind PRF-5, never as a determinism or totality claim. -/

theorem evalGuard_atNeg_false_when_pred_true
    (s : MachineState) (p : PredId) (h : s.predRegs p = some true) :
    evalGuard s (Guard.atNeg p) = some false := by
  simp [evalGuard, h]

theorem notB32_executes_iff_guard_true
    (s : MachineState) (i : NotB32Instruction) (b : Bool)
    (hguard : evalGuard s i.guard = some b)
    (hsources : b = true -> Exists fun (va : B32) => evalSource s i.a = some va) :
    (Exists fun (s' : MachineState) =>
        execNotB32 s i = some (ExecOutcome.executed s')) <-> b = true := by
  constructor
  · intro h
    rcases h with ⟨s', h⟩
    unfold execNotB32 at h
    rw [hguard] at h
    cases b with
    | false =>
        simp at h
    | true =>
        rfl
  · intro hb
    rcases hsources hb with ⟨va, hva⟩
    refine ⟨updateDestination s i.d (complementValue va), ?_⟩
    unfold execNotB32
    simp [hguard, hb, hva]

end NotB32
end PTX
end Spec2Lean
