import Spec2Lean.PTX.OrB16

namespace Spec2Lean.PTX.OrB16

 theorem OrB16Step_deterministic
    (s : MachineState) (i : OrB16Instruction) (s1 s2 : MachineState)
    (h1 : OrB16Step s i s1) (h2 : OrB16Step s i s2) : s1 = s2 := by
  unfold OrB16Step at h1 h2
  rcases h1 with h1 | h1
  · rcases h2 with h2 | h2
    · have hEq : ExecOutcome.executed s1 = ExecOutcome.executed s2 := by
        simpa [h1] using h2
      injection hEq
    · have hEq : some (ExecOutcome.executed s1) = some (ExecOutcome.notExecuted s2) := by
        simpa [h1] using h2
      cases hEq
  · rcases h2 with h2 | h2
    · have hEq : some (ExecOutcome.notExecuted s1) = some (ExecOutcome.executed s2) := by
        simpa [h1] using h2
      cases hEq
    · have hEq : ExecOutcome.notExecuted s1 = ExecOutcome.notExecuted s2 := by
        simpa [h1] using h2
      injection hEq

 theorem execOrB16_or_result
    (s : MachineState) (i : OrB16Instruction) (r : RegId) (va vb : B16)
    (hguard : evalGuard s i.guard = some true) (hd : i.d = Destination.reg r)
    (ha : evalSourceA s i.a = some va) (hb : evalSourceB s i.b = some vb) :
    ∃ s', execOrB16 s i = some (ExecOutcome.executed s') ∧ s'.valueRegs r = some (orValue va vb) := by
  refine ⟨updateDestination s i.d (orValue va vb), ?_, ?_⟩
  · simp [execOrB16, hguard, ha, hb]
  · rw [hd]
    simp [updateDestination]

 theorem OrB16Step_false_guard_preserves_state
    (s : MachineState) (i : OrB16Instruction) (s' : MachineState)
    (h : OrB16Step s i s') (hguard : evalGuard s i.guard = some false) : s' = s := by
  have h' : execOrB16 s i = some (ExecOutcome.notExecuted s) := by
    simp [execOrB16, hguard]
  unfold OrB16Step at h
  rcases h with h | h
  · have hbad : some (ExecOutcome.notExecuted s) = some (ExecOutcome.executed s') := by
      exact Eq.trans (Eq.symm h') h
    cases hbad
  · have hs : some (ExecOutcome.notExecuted s) = some (ExecOutcome.notExecuted s') := by
      exact Eq.trans (Eq.symm h') h
    have hs' : ExecOutcome.notExecuted s = ExecOutcome.notExecuted s' := by
      exact Option.some.inj hs
    have hss : s = s' := by injection hs'
    exact hss.symm

 theorem OrB16Step_predicate_file_frame
    (s : MachineState) (i : OrB16Instruction) (s' : MachineState)
    (h : OrB16Step s i s') : ∀ p, s'.predRegs p = s.predRegs p := by
  intro p
  unfold OrB16Step at h
  rcases h with h | h
  · -- executed branch
    cases hg : evalGuard s i.guard with
    | none =>
        simp [execOrB16, hg] at h
    | some b =>
        cases b with
        | false =>
            simp [execOrB16, hg] at h
        | true =>
            cases hs1 : evalSourceA s i.a with
            | none =>
                simp [execOrB16, hg, hs1] at h
            | some va =>
                cases hs2 : evalSourceB s i.b with
                | none =>
                    simp [execOrB16, hg, hs1, hs2] at h
                | some vb =>
                    have hs' : updateDestination s i.d (orValue va vb) = s' := by
                      simpa [execOrB16, hg, hs1, hs2] using h
                    rw [hs'.symm]
                    simp [updateDestination]
  · -- notExecuted branch
    cases hg : evalGuard s i.guard with
    | none =>
        simp [execOrB16, hg] at h
    | some b =>
        cases b with
        | false =>
            have hs : s = s' := by
              unfold execOrB16 at h
              rw [hg] at h
              simpa using h
            simpa [hs]
        | true =>
            have hFalse : False := by
              cases hs1 : evalSourceA s i.a with
              | none =>
                  simp [execOrB16, hg, hs1] at h
              | some va =>
                  cases hs2 : evalSourceB s i.b with
                  | none =>
                      simp [execOrB16, hg, hs1, hs2] at h
                  | some vb =>
                      simp [execOrB16, hg, hs1, hs2] at h
            exact False.elim hFalse

end Spec2Lean.PTX.OrB16
