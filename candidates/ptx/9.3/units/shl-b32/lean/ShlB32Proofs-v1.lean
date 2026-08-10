import Spec2Lean.PTX.ShlB32

namespace Spec2Lean.PTX.ShlB32

theorem ShlB32_ShlB32Step_deterministic
    (s : MachineState) (i : ShlB32Instruction) (s1 s2 : MachineState)
    (h1 : ShlB32Step s i s1) (h2 : ShlB32Step s i s2) : s1 = s2 := by
  cases h1 with
  | guardFalse hg1 =>
      cases h2 with
      | guardFalse hg2 =>
          simpa using hg1.trans hg2.symm
      | executed _ _ hg2 _ _ =>
          exfalso
          rw [hg2] at hg1
          simp at hg1
  | executed va1 vb1 hg1 ha1 hb1 =>
      cases h2 with
      | guardFalse hg2 =>
          exfalso
          rw [hg2] at hg1
          simp at hg1
      | executed va2 vb2 hg2 ha2 hb2 =>
          have hva : va1 = va2 := by
            apply Option.some.inj
            calc
              (some va1 : Option B32) = readSource s i.a := by simpa [ha1]
              _ = (some va2 : Option B32) := by simpa [ha2]
          have hvb : vb1 = vb2 := by
            apply Option.some.inj
            calc
              (some vb1 : Option B32) = readSource s i.b := by simpa [hb1]
              _ = (some vb2 : Option B32) := by simpa [hb2]
          rw [hva, hvb]


theorem ShlB32_execShlB32_executed_sound
    (s : MachineState) (i : ShlB32Instruction) (s' : MachineState) :
    execShlB32 s i = some (ExecOutcome.executed s') -> ∃ va vb : B32, ShlB32Step s i s' := by
  intro h
  unfold execShlB32 at h
  cases hg : evalGuard s i.guard with
  | none =>
      simp [hg] at h
  | some g =>
      cases g with
      | false =>
          simp [hg] at h
      | true =>
          cases ha : readSource s i.a with
          | none =>
              simp [hg, ha] at h
          | some va =>
              cases hb : readSource s i.b with
              | none =>
                  simp [hg, ha, hb] at h
              | some vb =>
                  have hs : s' = updateDestination s i.d (shlValue va vb) := by
                    simpa [hg, ha, hb] using h.symm
                  refine ⟨va, vb, ?_⟩
                  rw [hs]
                  exact ShlB32Step.executed (s := s) (i := i) va vb (by simpa [hg]) (by simpa [ha]) (by simpa [hb])


theorem ShlB32_execShlB32_guardFalse_iff
    (s : MachineState) (i : ShlB32Instruction) (s' : MachineState) :
    execShlB32 s i = some (ExecOutcome.guardFalse s') ↔
      (evalGuard s i.guard = some false ∧ s' = s) := by
  constructor
  · intro h
    unfold execShlB32 at h
    cases hg : evalGuard s i.guard with
    | none =>
        simp [hg] at h
    | some g =>
        cases g with
        | false =>
            have hs : s = s' := by
              simpa [hg] using h
            exact ⟨by simpa [hg], hs.symm⟩
        | true =>
            cases ha : readSource s i.a with
            | none =>
                simp [hg, ha] at h
            | some _ =>
                cases hb : readSource s i.b with
                | none =>
                    simp [hg, ha, hb] at h
                | some _ =>
                    simp [hg, ha, hb] at h
  · rintro ⟨hguard, hsEq⟩
    subst hsEq
    simp [execShlB32, hguard]


theorem ShlB32_execShlB32_none_iff_no_step
    (s : MachineState) (i : ShlB32Instruction) :
    execShlB32 s i = none ↔ ¬ ∃ s', ShlB32Step s i s' := by
  constructor
  · intro h hstep
    rcases hstep with ⟨s', hstep⟩
    cases hstep with
    | guardFalse hguard =>
        unfold execShlB32 at h
        rw [hguard] at h
        simp at h
    | executed va vb hguard ha hb =>
        unfold execShlB32 at h
        simp [hguard, ha, hb] at h
  · intro h
    unfold execShlB32
    cases hg : evalGuard s i.guard with
    | none =>
        simp [hg]
    | some g =>
        cases g with
        | false =>
            exfalso
            apply h
            exact ⟨s, ShlB32Step.guardFalse (s := s) (i := i) (by simpa [hg])⟩
        | true =>
            cases ha : readSource s i.a with
            | none =>
                simp [hg, ha]
            | some va =>
                cases hb : readSource s i.b with
                | none =>
                    simp [hg, ha, hb]
                | some vb =>
                    exfalso
                    apply h
                    exact ⟨updateDestination s i.d (shlValue va vb),
                      ShlB32Step.executed (s := s) (i := i) va vb (by simpa [hg]) (by simpa [ha]) (by simpa [hb])⟩

end Spec2Lean.PTX.ShlB32
