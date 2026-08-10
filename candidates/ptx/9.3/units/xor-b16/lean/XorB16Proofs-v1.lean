import Spec2Lean.PTX.XorB16

namespace Spec2Lean.PTX.XorB16


theorem XorB16Step_deterministic
    (s : MachineState) (i : XorB16Instruction) (s1 s2 : MachineState)
    (h1 : XorB16Step s i s1) (h2 : XorB16Step s i s2) : s1 = s2 := by
  cases h1 with
  | guardFalse hg1 =>
      cases h2 with
      | guardFalse _ =>
          rfl
      | executed _ _ ha2 hb2 hupd2 =>
          exfalso
          -- Guard-false step produces `s1 = s`; executed step may only occur on
          -- evaluated sources, with no guard constraint in this bounded relation.
          simp [hg1] at hupd2
  | executed va1 vb1 ha1 hb1 hupd1 =>
      cases h2 with
      | guardFalse hg2 =>
          exfalso
          simp [hg2] at hupd1
      | executed va2 vb2 ha2 hb2 hupd2 =>
          have hva : va1 = va2 := by
            rw [ha1] at ha2
            simpa using ha2
          have hvb : vb1 = vb2 := by
            rw [hb1] at hb2
            simpa using hb2
          rw [hva, hvb] at hupd1 hupd2 ⊢
          simpa [hupd1] using hupd2


theorem execXorB16_xor_result
    (s : MachineState) (i : XorB16Instruction) (r : RegId) (va vb : B16)
    (hguard : evalGuard s i.guard = some true) (hd : i.d = Destination.reg r)
    (ha : evalSourceA s i.a = some va) (hb : evalSourceB s i.b = some vb) :
    ∃ s', execXorB16 s i = some (ExecOutcome.executed s') ∧ s'.valueRegs r = some (xorValue va vb) := by
  let s' : MachineState :=
    { s with
      valueRegs := fun r' => if r' == r then some (xorValue va vb) else s.valueRegs r'
    }
  refine ⟨s', ?_, ?_⟩
  · simp [execXorB16, hguard, ha, hb, s', hd, updateDestination]
  · simp [s', hd]


theorem XorB16Step_predicate_file_frame
    (s : MachineState) (i : XorB16Instruction) (s' : MachineState)
    (h : XorB16Step s i s') : ∀ p, s'.predRegs p = s.predRegs p := by
  intro p
  cases h with
  | guardFalse hgf =>
      rfl
  | executed va vb hsa hsb hupd =>
      cases i.d with
      | reg r =>
          have hs' : ({
              valueRegs := fun r' => if r' == r then some (xorValue va vb) else s.valueRegs r'
              predRegs := s.predRegs
            } : MachineState) = s' := by
            simpa [updateDestination] using hupd
          rw [hs']
          rfl
      | bitBucket =>
          cases hupd

end Spec2Lean.PTX.XorB16