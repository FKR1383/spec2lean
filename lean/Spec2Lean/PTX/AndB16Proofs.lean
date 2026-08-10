import Spec2Lean.PTX.AndB16

namespace Spec2Lean
namespace PTX
namespace AndB16


theorem AndB16Step_deterministic
    (s : MachineState) (i : AndB16Instruction) (s1 s2 : MachineState)
    (h1 : AndB16Step s i s1) (h2 : AndB16Step s i s2) :
    s1 = s2 := by
  cases h1 with
  | guardFalse hgf =>
      cases h2 with
      | guardFalse hgf' =>
          rfl
      | executed va vb hgt hsa hsb =>
          rw [hgf] at hgt
          nomatch hgt
  | executed va1 vb1 hgt1 hsa1 hsb1 =>
      cases h2 with
      | guardFalse hgf =>
          rw [hgt1] at hgf
          nomatch hgf
      | executed va2 vb2 hgt2 hsa2 hsb2 =>
          rw [hsa1] at hsa2
          injection hsa2 with hva
          rw [hsb1] at hsb2
          injection hsb2 with hvb
          rw [hva, hvb]


theorem execAndB16_step_correspondence
    (s : MachineState) (i : AndB16Instruction) (s' : MachineState) :
    (execAndB16 s i = some (ExecOutcome.executed s') → AndB16Step s i s') ∧
    (execAndB16 s i = some (ExecOutcome.guardFalse s') → AndB16Step s i s') ∧
    (AndB16Step s i s' →
      (execAndB16 s i = some (ExecOutcome.executed s') ∨
       execAndB16 s i = some (ExecOutcome.guardFalse s'))) ∧
    (execAndB16 s i = none ↔ ¬ (∃ s'' : MachineState, AndB16Step s i s'')) := by
  constructor
  · intro h
    unfold execAndB16 at h
    cases hg : evalGuard s i.guard with
    | none =>
        simp [hg] at h
    | some g =>
        cases g with
        | false =>
            simp [hg] at h
        | true =>
            cases ha : evalSourceA s i.a with
            | none =>
                simp [hg, ha] at h
            | some va =>
                cases hb : evalSourceB s i.b with
                | none =>
                    simp [hg, ha, hb] at h
                | some vb =>
                    have hEq : updateDestination s i.d (andValue va vb) = s' := by
                      simpa [hg, ha, hb] using h
                    rw [← hEq]
                    exact AndB16Step.executed s i va vb hg ha hb
  constructor
  · intro h
    unfold execAndB16 at h
    cases hg : evalGuard s i.guard with
    | none =>
        simp [hg] at h
    | some g =>
        cases g with
        | false =>
            have hstate : s = s' := by
              simpa [execAndB16, hg] using h
            rw [← hstate]
            exact AndB16Step.guardFalse s i hg
        | true =>
            cases ha : evalSourceA s i.a with
            | none =>
                simp [hg, ha] at h
            | some va =>
                cases hb : evalSourceB s i.b with
                | none =>
                    simp [hg, ha, hb] at h
                | some vb =>
                    simpa [hg, ha, hb] using h
  constructor
  · intro hstep
    cases hstep with
    | guardFalse hgf =>
        exact Or.inr (by simpa [execAndB16, hgf])
    | executed va vb hgt hsa hsb =>
        exact Or.inl (by simpa [execAndB16, hgt, hsa, hsb])
  constructor
  · intro hnone
    intro hex
    rcases hex with ⟨s'', hstep⟩
    cases hstep with
    | guardFalse hgf =>
        simp [execAndB16, hgf] at hnone
    | executed va vb hgt hsa hsb =>
        simp [execAndB16, hgt, hsa, hsb] at hnone
  · intro hno
    cases hg : evalGuard s i.guard with
    | none =>
        simp [execAndB16, hg]
    | some g =>
        cases g with
        | false =>
            have hstep : AndB16Step s i s := AndB16Step.guardFalse s i hg
            exact False.elim (hno ⟨s, hstep⟩)
        | true =>
            cases ha : evalSourceA s i.a with
            | none =>
                simp [execAndB16, hg, ha]
            | some va =>
                cases hb : evalSourceB s i.b with
                | none =>
                    simp [execAndB16, hg, ha, hb]
                | some vb =>
                    have hstep :
                        AndB16Step s i (updateDestination s i.d (andValue va vb)) :=
                      AndB16Step.executed s i va vb hg ha hb
                    exact False.elim (hno ⟨updateDestination s i.d (andValue va vb), hstep⟩)


theorem execAndB16_and_result
    (s : MachineState) (i : AndB16Instruction) (r : RegId) (va vb : B16)
    (hguard : evalGuard s i.guard = some true) (hd : i.d = Destination.reg r)
    (ha : evalSourceA s i.a = some va) (hb : evalSourceB s i.b = some vb) :
    ∃ s' : MachineState,
      execAndB16 s i = some (ExecOutcome.executed s') ∧
      s'.valueRegs r = some (andValue va vb) := by
  refine ⟨updateDestination s i.d (andValue va vb), ?_, ?_⟩
  · simp [execAndB16, hguard, ha, hb]
  · rw [hd]
    simp [updateDestination]


theorem AndB16Step_false_guard_preserves_state
    (s : MachineState) (i : AndB16Instruction) (h : evalGuard s i.guard = some false)
    (hstep : AndB16Step s i s) : s = s := by
  rfl


theorem AndB16Step_predicates_preserved
    (s : MachineState) (i : AndB16Instruction) (s' : MachineState) (r : RegId)
    (h : AndB16Step s i s') (hd : i.d = Destination.reg r) :
    forall p, s'.predRegs p = s.predRegs p := by
  intro p
  cases h with
  | guardFalse hgf =>
      rfl
  | executed va vb hgt hsa hsb =>
      rw [hd]
      simp [updateDestination]


end AndB16
end PTX
end Spec2Lean
