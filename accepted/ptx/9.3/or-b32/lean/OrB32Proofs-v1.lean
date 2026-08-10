import Spec2Lean.PTX.OrB32

namespace Spec2Lean.PTX.OrB32

theorem OrB32_OrB32Step_deterministic
    (s : MachineState) (i : OrB32Instruction) (s1 s2 : MachineState)
    (h1 : OrB32Step s i s1) (h2 : OrB32Step s i s2) :
    s1 = s2 := by
  cases h1 with
  | notExecuted hg1 =>
      cases h2 with
      | notExecuted _ =>
          rfl
      | executed va2 vb2 hg2 ha2 hb2 =>
          exfalso
          rw [hg1] at hg2
          simp at hg2
  | executed va1 vb1 hg1 ha1 hb1 =>
      cases h2 with
      | notExecuted hg2 =>
          exfalso
          rw [hg2] at hg1
          simp at hg1
      | executed va2 vb2 hg2 ha2 hb2 =>
          have hva : va1 = va2 := by
            rw [ha1] at ha2
            simpa using ha2
          have hvb : vb1 = vb2 := by
            rw [hb1] at hb2
            simpa using hb2
          rw [hva, hvb]

theorem OrB32_execOrB32_executed_soundness
    (s : MachineState) (i : OrB32Instruction) (s' : MachineState) :
    execOrB32 s i = some (ExecOutcome.executed s') -> OrB32Step s i s' := by
  intro h
  unfold execOrB32 at h
  cases hg : evalGuard s i.guard with
  | none =>
      simp [hg] at h
  | some g =>
      cases g with
      | false =>
          simp [hg] at h
      | true =>
          cases hs1 : readSource1 s i.a with
          | none =>
              simp [hg, hs1] at h
          | some va =>
              cases hs2 : readSource2 s i.b with
              | none =>
                  simp [hg, hs1, hs2] at h
              | some vb =>
                  have hEq : updateDestination s i.d (orValue va vb) = s' := by
                    simpa [hg, hs1, hs2] using h
                  rw [←hEq]
                  exact OrB32Step.executed s i va vb hg hs1 hs2

theorem OrB32_execOrB32_notExecuted_iff_false_guard (s : MachineState) (i : OrB32Instruction) (s' : MachineState) :
  execOrB32 s i = some (ExecOutcome.notExecuted s') ↔ (evalGuard s i.guard = some false ∧ s' = s) := by
  constructor
  · intro h
    unfold execOrB32 at h
    cases hg : evalGuard s i.guard with
    | none =>
        simp [hg] at h
    | some b =>
        cases b with
        | false =>
            rw [hg] at h
            have hs' : s = s' := by
              simpa using h
            exact ⟨by simpa [hg], hs'.symm⟩
        | true =>
            exfalso
            cases hs1 : readSource1 s i.a <;> cases hs2 : readSource2 s i.b <;> simp [hg, hs1, hs2] at h
  · rintro ⟨hguard, hsEq⟩
    subst hsEq
    simp [execOrB32, hguard]

theorem OrB32_OrB32Step_implies_execOrB32_or_notExecuted
    (s : MachineState) (i : OrB32Instruction) (s' : MachineState) (h : OrB32Step s i s') :
    ∃ out, execOrB32 s i = some out ∧ (out = ExecOutcome.executed s' ∨ out = ExecOutcome.notExecuted s') := by
  cases h with
  | notExecuted hg =>
      refine ⟨ExecOutcome.notExecuted s, ?_, Or.inr rfl⟩
      simp [execOrB32, hg]
  | executed va vb hg hasa hasb =>
      refine ⟨ExecOutcome.executed (updateDestination s i.d (orValue va vb)), ?_, Or.inl rfl⟩
      simp [execOrB32, hg, hasa, hasb]

theorem OrB32_execOrB32_none_iff_no_step (s : MachineState) (i : OrB32Instruction) :
    execOrB32 s i = none ↔ ¬ ∃ s', OrB32Step s i s' := by
  constructor
  · intro h hstep
    rcases hstep with ⟨s', hstep'⟩
    cases hstep' with
    | notExecuted hg =>
      unfold execOrB32 at h
      rw [hg] at h
      simp at h
    | executed va vb hg hasa hasb =>
      unfold execOrB32 at h
      simp [hg, hasa, hasb] at h
  · intro h
    unfold execOrB32
    cases hg : evalGuard s i.guard with
    | none =>
      simp [hg]
    | some g =>
      cases g with
      | false =>
        exfalso
        apply h
        exact ⟨s, OrB32Step.notExecuted s i hg⟩
      | true =>
        cases hs1 : readSource1 s i.a with
        | none =>
          simp [hg, hs1]
        | some va =>
          cases hs2 : readSource2 s i.b with
          | none =>
            simp [hg, hs1, hs2]
          | some vb =>
            exfalso
            apply h
            refine ⟨updateDestination s i.d (orValue va vb), OrB32Step.executed s i va vb hg ?_ ?_⟩
            · simpa [hs1]
            · simpa [hs2]

theorem OrB32_OrB32Step_false_guard_no_change (s : MachineState) (i : OrB32Instruction) (s' : MachineState)
    (h : OrB32Step s i s') (hfalse : evalGuard s i.guard = some false) : s' = s := by
  cases h with
  | notExecuted hnot =>
      rfl
  | executed va vb htrue _ _ =>
      exfalso
      rw [htrue] at hfalse
      simpa using hfalse


theorem OrB32_OrB32Step_preserves_predicates
    (s : MachineState) (i : OrB32Instruction) (s' : MachineState) (h : OrB32Step s i s') : ∀ p, s'.predRegs p = s.predRegs p := by
  intro p
  cases h with
  | notExecuted hguard =>
      rfl
  | executed _ _ _ _ _ =>
      cases i.d <;> rfl

theorem OrB32_OrB32Step_value_reg_frame_nonDest
    (s : MachineState) (i : OrB32Instruction) (s' : MachineState) (r : RegId)
    (h : OrB32Step s i s') (hd : i.d ≠ Destination.reg r) : s'.valueRegs r = s.valueRegs r := by
  cases h with
  | notExecuted _ =>
      rfl
  | executed va vb hg hasa hasb =>
      cases hdest : i.d with
      | reg r' =>
          have hr' : r ≠ r' := by
            intro hEq
            apply hd
            simpa [hEq] using hdest
          simp [updateDestination, hdest, hr']
      | bitBucket =>
          rfl

 theorem OrB32_OrB32Step_bitBucket_noop (s : MachineState) (i : OrB32Instruction) (s' : MachineState)
    (h : OrB32Step s i s') (hd : i.d = Destination.bitBucket) : s' = s := by
  cases h with
  | notExecuted hnd =>
      rfl
  | executed va vb hguard hs1 hs2 =>
      simp [updateDestination, hd]

end Spec2Lean.PTX.OrB32
