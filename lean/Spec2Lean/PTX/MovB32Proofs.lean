/-
Spec2Lean machine-checked proof candidate — PTX ISA 9.3 `mov.b32`

Approved theorem set:
  candidates/ptx/9.3/units/mov-b32/theorems/obligations-v1.json
Human theorem-strength approval:
  reviews/ptx-mov-b32/theorem-strength/ptx-mov-b32-theorem-strength-approval-v1.json
Imported packaged semantics:
  lean/Spec2Lean/PTX/MovB32.lean

This file states the approved theorem obligations at their reviewed strength.
It does not modify semantics and must contain no sorry, admit, new axiom, or
unsafe verification bypass.
-/

import Spec2Lean.PTX.MovB32

namespace Spec2Lean
namespace PTX
namespace MovB32

/-! ## PTX-MOV-THM-001 — relational determinism -/

theorem movB32Step_deterministic
    (s : MachineState) (i : MovB32Instruction) (s1 s2 : MachineState)
    (h1 : MovB32Step s i s1) (h2 : MovB32Step s i s2) :
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

/-! ## PTX-MOV-THM-002 — function/relation correspondence -/

theorem exec_sound_executed
    (s : MachineState) (i : MovB32Instruction) (s' : MachineState)
    (h : execMovB32 s i = some (ExecOutcome.executed s')) :
    MovB32Step s i s' := by
  cases hg : evalGuard s i.guard with
  | none =>
      simp [execMovB32, hg] at h
  | some b =>
      cases b with
      | false =>
          simp [execMovB32, hg] at h
      | true =>
          cases hs : evalSource s i.a with
          | none =>
              simp [execMovB32, hg, hs] at h
          | some va =>
              have hstate : updateDestination s i.d (copyValue va) = s' := by
                simpa [execMovB32, hg, hs] using h
              rw [← hstate]
              exact MovB32Step.executed s i va hg hs

theorem exec_sound_guardFalse
    (s : MachineState) (i : MovB32Instruction) (s' : MachineState)
    (h : execMovB32 s i = some (ExecOutcome.guardFalse s')) :
    MovB32Step s i s' := by
  cases hg : evalGuard s i.guard with
  | none =>
      simp [execMovB32, hg] at h
  | some b =>
      cases b with
      | false =>
          have hstate : s = s' := by
            simpa [execMovB32, hg] using h
          rw [← hstate]
          exact MovB32Step.guardFalse s i hg
      | true =>
          cases hs : evalSource s i.a with
          | none =>
              simp [execMovB32, hg, hs] at h
          | some va =>
              simp [execMovB32, hg, hs] at h

theorem step_complete
    (s : MachineState) (i : MovB32Instruction) (s' : MachineState)
    (h : MovB32Step s i s') :
    Exists fun (o : ExecOutcome) =>
      execMovB32 s i = some o /\
      (o = ExecOutcome.executed s' \/ o = ExecOutcome.guardFalse s') := by
  cases h with
  | guardFalse hg =>
      refine ⟨ExecOutcome.guardFalse s, ?_⟩
      constructor
      · simp [execMovB32, hg]
      · right
        rfl
  | executed va hg ha =>
      refine ⟨ExecOutcome.executed (updateDestination s i.d (copyValue va)), ?_⟩
      constructor
      · simp [execMovB32, hg, ha]
      · left
        rfl

theorem step_partial_complete
    (s : MachineState) (i : MovB32Instruction) :
    execMovB32 s i = none <->
      ¬ (Exists fun (s' : MachineState) => MovB32Step s i s') := by
  constructor
  · intro hnone
    rintro ⟨s', hstep⟩
    cases hstep with
    | guardFalse hg =>
        simp [execMovB32, hg] at hnone
    | executed _ hg ha =>
        simp [execMovB32, hg, ha] at hnone
  · intro hnone
    cases hg : evalGuard s i.guard with
    | none =>
        simp [execMovB32, hg]
    | some b =>
        cases b with
        | false =>
            have hstep : MovB32Step s i s :=
              MovB32Step.guardFalse s i hg
            exact False.elim (hnone ⟨s, hstep⟩)
        | true =>
            cases hs : evalSource s i.a with
            | none =>
                simp [execMovB32, hg, hs]
            | some va =>
                have hstep :
                    MovB32Step s i (updateDestination s i.d (copyValue va)) :=
                  MovB32Step.executed s i va hg hs
                exact False.elim
                  (hnone ⟨updateDestination s i.d (copyValue va), hstep⟩)

/-! ## PTX-MOV-THM-003 — exact copy fidelity -/

theorem execMovB32_copy_fidelity
    (s : MachineState) (i : MovB32Instruction) (r : RegId) (va : B32)
    (hguard : evalGuard s i.guard = some true)
    (hd : i.d = Destination.reg r)
    (ha : evalSource s i.a = some va) :
    Exists fun (s' : MachineState) =>
      execMovB32 s i = some (ExecOutcome.executed s') /\
      s'.valueRegs r = some va := by
  refine ⟨updateDestination s i.d (copyValue va), ?_⟩
  constructor
  · simp [execMovB32, hguard, ha]
  · rw [hd]
    simp [updateDestination, copyValue]

/-! ## PTX-MOV-THM-004 — destination-only frame -/

theorem movB32Step_destination_only_frame
    (s : MachineState) (i : MovB32Instruction) (s' : MachineState) (r : RegId)
    (hstep : MovB32Step s i s')
    (hd : i.d = Destination.reg r) :
    (forall (r' : RegId), r' ≠ r -> s'.valueRegs r' = s.valueRegs r') /\
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
        intro hrr
        exfalso
        exact hr' hrr
      · intro p
        rw [hd]
        simp [updateDestination]

/-! ## PTX-MOV-THM-005 — bit-bucket preservation

Strength caveat: this theorem is about the Gate-C-approved bounded Lean
mapping. Its source basis is only the general PTX section 9.2 bit-bucket rule;
it must not be presented as an explicit mov.b32-specific NVIDIA statement.
-/

theorem movB32Step_bit_bucket_preserves_state
    (s : MachineState) (i : MovB32Instruction) (s' : MachineState)
    (hstep : MovB32Step s i s')
    (hd : i.d = Destination.bitBucket) :
    s' = s := by
  cases hstep with
  | guardFalse _ =>
      rfl
  | executed va _ _ =>
      rw [hd]
      simp [updateDestination]

/-! ## PTX-MOV-THM-006 — guard-false frame -/

theorem execMovB32_guard_false_preserves_state
    (s : MachineState) (i : MovB32Instruction)
    (hguard : evalGuard s i.guard = some false) :
    execMovB32 s i = some (ExecOutcome.guardFalse s) := by
  simp [execMovB32, hguard]

theorem movB32Step_guard_false_frame
    (s : MachineState) (i : MovB32Instruction) (s' : MachineState)
    (hstep : MovB32Step s i s')
    (hguard : evalGuard s i.guard = some false) :
    s' = s := by
  cases hstep with
  | guardFalse _ =>
      rfl
  | executed _ hg _ =>
      exfalso
      rw [hguard] at hg
      simp at hg

/-! ## PTX-MOV-THM-007 — executes iff complete guard is true -/

theorem movB32_executes_iff_guard_true
    (s : MachineState) (i : MovB32Instruction) (b : Bool)
    (hguard : evalGuard s i.guard = some b)
    (hsources : b = true -> Exists fun (va : B32) => evalSource s i.a = some va) :
    (Exists fun (s' : MachineState) =>
        execMovB32 s i = some (ExecOutcome.executed s')) <-> b = true := by
  constructor
  · rintro ⟨s', hexec'⟩
    by_cases hb : b = true
    · exact hb
    · exfalso
      have hbf : b = false := by
        cases b
        · rfl
        · exact False.elim (hb rfl)
      simp [execMovB32, hguard, hbf] at hexec'
  · intro hb
    rw [hb] at hguard hsources
    rcases hsources rfl with ⟨va, ha⟩
    refine ⟨updateDestination s i.d (copyValue va), ?_⟩
    simp [execMovB32, hguard, ha]

/-! Supporting per-constructor guard-evaluation lemmas. -/

theorem evalGuard_unguarded_true
    (s : MachineState) :
    evalGuard s Guard.unguarded = some true := by
  rfl

theorem evalGuard_atPos_true
    (s : MachineState) (p : PredId) (h : s.predRegs p = some true) :
    evalGuard s (Guard.atPos p) = some true := by
  simp [evalGuard, h]

theorem evalGuard_atNeg_true_when_pred_false
    (s : MachineState) (p : PredId) (h : s.predRegs p = some false) :
    evalGuard s (Guard.atNeg p) = some true := by
  simp [evalGuard, h]

theorem evalGuard_atPos_false
    (s : MachineState) (p : PredId) (h : s.predRegs p = some false) :
    evalGuard s (Guard.atPos p) = some false := by
  simp [evalGuard, h]

theorem evalGuard_atNeg_false_when_pred_true
    (s : MachineState) (p : PredId) (h : s.predRegs p = some true) :
    evalGuard s (Guard.atNeg p) = some false := by
  simp [evalGuard, h]

end MovB32
end PTX
end Spec2Lean
