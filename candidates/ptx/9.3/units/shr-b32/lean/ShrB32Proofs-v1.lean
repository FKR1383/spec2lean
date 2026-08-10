import Spec2Lean.PTX.ShrB32

namespace Spec2Lean.PTX.ShrB32

theorem shrB32Step_deterministic (s : MachineState) (i : ShrB32Instruction) (s1 s2 : MachineState)
    (h1 : ShrB32Step s i s1) (h2 : ShrB32Step s i s2) : s1 = s2 := by
  cases h1 with
  | guardFalse hg1 =>
      cases h2 with
      | guardFalse _ =>
          rfl
      | executed va2 vb2 hg2 _ _ =>
          exfalso
          have : (false : Bool) = true := by
            simpa [hg1] using hg2
          cases this
      | malformed _ =>
          rfl
  | executed va1 vb1 hg1 ha1 hb1 =>
      cases h2 with
      | guardFalse hg2 =>
          exfalso
          have : (true : Bool) = false := by
            simpa [hg2] using hg1
          cases this
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
      | malformed hcond2 =>
          exfalso
          rw [hg1] at hcond2
          cases hcond2 with
          | inl hnone =>
              cases (show False by simpa [hg1] using hnone)
          | inr hsrc =>
              cases hsrc with
              | inl hnone =>
                  cases (show False by simpa [ha1] using hnone)
              | inr hnone =>
                  cases (show False by simpa [hb1] using hnone)
  | malformed hcond1 =>
      cases h2 with
      | guardFalse _ =>
          rfl
      | executed va2 vb2 hg2 ha2 hb2 =>
          exfalso
          rw [hg2] at hcond1
          cases hcond1 with
          | inl hnone =>
              cases (show False by simpa [ha2] using hnone)
          | inr hsrc =>
              cases hsrc with
              | inl hnone =>
                  cases (show False by simpa [ha2] using hnone)
              | inr hnone =>
                  cases (show False by simpa [hb2] using hnone)
      | malformed _ =>
          rfl


theorem execShrB32_sound_guardFalse
    (s : MachineState) (i : ShrB32Instruction) (s' : MachineState)
    (h : execShrB32 s i = some (ExecOutcome.guardFalse s')) : ShrB32Step s i s' := by
  unfold execShrB32 at h
  cases hg : evalGuard s i.guard with
  | none =>
      simp [hg] at h
  | some g =>
      cases g with
      | false =>
          have hs : s = s' := by
            simpa [hg] using h
          rw [← hs]
          exact ShrB32Step.guardFalse (s := s) (i := i) (by simpa [hg])
      | true =>
          cases ha : readSource s i.a with
          | none =>
              cases hb : readSource s i.b with
              | none =>
                  simp [hg, ha, hb] at h
              | some vb =>
                  simp [hg, ha, hb] at h
          | some va =>
              cases hb : readSource s i.b with
              | none =>
                  simp [hg, ha, hb] at h
              | some vb =>
                  simp [hg, ha, hb] at h


theorem execShrB32_sound_executed
    (s : MachineState) (i : ShrB32Instruction) (s' : MachineState)
    (h : execShrB32 s i = some (ExecOutcome.executed s')) :
    ∃ (va vb : B32), ShrB32Step s i s' := by
  unfold execShrB32 at h
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
                  have hs : s' = updateDestination s i.d (shrB32Value va vb) := by
                    simpa [hg, ha, hb] using h.symm
                  subst hs
                  exact ⟨va, vb, ShrB32Step.executed (s := s) (i := i) va vb (by simpa [hg]) (by simpa [ha]) (by simpa [hb])⟩


theorem execShrB32_sound_malformed
    (s : MachineState) (i : ShrB32Instruction) (s' : MachineState)
    (h : execShrB32 s i = some (ExecOutcome.malformed s')) :
    ShrB32Step s i s' ∧ evalGuard s i.guard ≠ some false := by
  unfold execShrB32 at h
  cases hg : evalGuard s i.guard with
  | none =>
      have hs : s' = s := by
        simpa [hg] using h.symm
      constructor
      · cases hs
        exact ShrB32Step.malformed (s := s) (i := i) (Or.inl (by simp [hg]))
      · intro hfalse
        simpa [hg] using hfalse
  | some g =>
      cases g with
      | false =>
          simp [hg] at h
      | true =>
          cases ha : readSource s i.a with
          | none =>
              cases hb : readSource s i.b with
              | none =>
                  have hs : s' = s := by
                    simpa [execShrB32, hg, ha, hb] using h.symm
                  constructor
                  · cases hs
                    exact ShrB32Step.malformed (s := s) (i := i) (Or.inr (Or.inl (by simpa [ha])) )
                  · intro hfalse
                    simpa [hg] using hfalse
              | some vb =>
                  have hs : s' = s := by
                    simpa [execShrB32, hg, ha, hb] using h.symm
                  constructor
                  · cases hs
                    exact ShrB32Step.malformed (s := s) (i := i) (Or.inr (Or.inl (by simpa [ha])) )
                  · intro hfalse
                    simpa [hg] using hfalse
          | some va =>
              cases hb : readSource s i.b with
              | none =>
                  have hs : s' = s := by
                    simpa [execShrB32, hg, ha, hb] using h.symm
                  constructor
                  · cases hs
                    exact ShrB32Step.malformed (s := s) (i := i) (Or.inr (Or.inr (by simpa [hb])) )
                  · intro hfalse
                    simpa [hg] using hfalse
              | some vb =>
                  simp [execShrB32, hg, ha, hb] at h


theorem shrB32Step_to_exec_correspondence
    (s : MachineState) (i : ShrB32Instruction) (s' : MachineState) (hstep : ShrB32Step s i s') :
    (∃ h : evalGuard s i.guard = some false, execShrB32 s i = some (ExecOutcome.guardFalse s')) ∨
    (∃ va vb : B32, ∃ hg : evalGuard s i.guard = some true, ∃ ha : readSource s i.a = some va, ∃ hb : readSource s i.b = some vb,
      s' = updateDestination s i.d (shrB32Value va vb) ∧ execShrB32 s i = some (ExecOutcome.executed s')) ∨
    (evalGuard s i.guard ≠ some false ∧ execShrB32 s i = some (ExecOutcome.malformed s')) := by
  cases hstep with
  | guardFalse hg =>
      exact Or.inl ⟨hg, by simp [execShrB32, hg]⟩
  | executed va vb hg ha hb =>
      exact Or.inr (Or.inl ⟨va, vb, hg, ha, hb, rfl, by simp [execShrB32, hg, ha, hb]⟩)
  | malformed hcond =>
      by_cases hfalse : evalGuard s i.guard = some false
      · exact Or.inl ⟨hfalse, by simp [execShrB32, hfalse]⟩
      · refine Or.inr (Or.inr ?_)
        constructor
        · exact hfalse
        · cases hcond with
          | inl hnone =>
              simp [execShrB32, hnone]
          | inr hsrc =>
              cases hsrc with
              | inl hA =>
                  cases hg : evalGuard s i.guard with
                  | none => simp [execShrB32, hg]
                  | some g =>
                      cases g with
                      | false => exact False.elim (hfalse hg)
                      | true => simp [execShrB32, hg, hA]
              | inr hB =>
                  cases hg : evalGuard s i.guard with
                  | none => simp [execShrB32, hg]
                  | some g =>
                      cases g with
                      | false => exact False.elim (hfalse hg)
                      | true => simp [execShrB32, hg, hB]


theorem execShrB32_malformed_iff_malformed_condition
    (s : MachineState) (i : ShrB32Instruction) (s' : MachineState) :
    execShrB32 s i = some (ExecOutcome.malformed s') ↔
      ((evalGuard s i.guard = none ∨ (evalGuard s i.guard = some true ∧ (readSource s i.a = none ∨ readSource s i.b = none))) ∧ s' = s) := by
  constructor
  · intro h
    unfold execShrB32 at h
    cases hg : evalGuard s i.guard with
    | none =>
        have hs : s' = s := by
          simpa [hg] using h.symm
        exact ⟨Or.inl rfl, hs⟩
    | some g =>
        cases g with
        | false =>
            simp [hg] at h
        | true =>
            cases ha : readSource s i.a with
            | none =>
                have hs : s' = s := by
                  simpa [hg, ha] using h.symm
                exact ⟨Or.inr ⟨by simpa [hg], Or.inl (by simpa [ha])⟩, hs⟩
            | some va =>
                cases hb : readSource s i.b with
                | none =>
                    have hs : s' = s := by
                      simpa [hg, ha, hb] using h.symm
                    exact ⟨Or.inr ⟨by simpa [hg], Or.inr (by simpa [hb])⟩, hs⟩
                | some vb =>
                    simp [hg, ha, hb] at h
  · rintro ⟨hcond, hs'⟩
    subst hs'
    rcases hcond with hcond | hcond
    · simpa [execShrB32, hcond]
    · rcases hcond with ⟨htrue, hnone⟩
      rcases hnone with hnone | hnone
      · simpa [execShrB32, htrue, hnone]
      · simpa [execShrB32, htrue, hnone]


theorem execShrB32_shr_fidelity
    (s : MachineState) (i : ShrB32Instruction) (r : RegId) (va vb : B32)
    (hguard : evalGuard s i.guard = some true) (hd : i.d = Destination.reg r)
    (ha : readSource s i.a = some va) (hb : readSource s i.b = some vb) :
    ∃ s' : MachineState, execShrB32 s i = some (ExecOutcome.executed s') ∧ s'.valueRegs r = some (shrB32Value va vb) := by
  refine ⟨updateDestination s i.d (shrB32Value va vb), ?_⟩
  constructor
  · simp [execShrB32, hguard, ha, hb]
  · rw [hd]
    simp [updateDestination]


theorem shrB32Step_destination_only_frame
    (s : MachineState) (i : ShrB32Instruction) (s' : MachineState) (r : RegId)
    (hstep : ShrB32Step s i s') (hd : i.d = Destination.reg r) :
    (∀ r' : RegId, r' ≠ r -> s'.valueRegs r' = s.valueRegs r') ∧
      (∀ p : PredId, s'.predRegs p = s.predRegs p) := by
  cases hstep with
  | guardFalse _ =>
      constructor
      · intro r' hr'
        rfl
      · intro p
        rfl
  | executed _ _ _ _ _ =>
      constructor
      · intro r' hr'
        rw [hd]
        simp [updateDestination, hr']
      · intro p
        rw [hd]
        simp [updateDestination]
  | malformed _ =>
      constructor
      · intro r' hr'
        rfl
      · intro p
        rfl

end Spec2Lean.PTX.ShrB32
