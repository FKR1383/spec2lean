import Spec2Lean.PTX.CnotB32

namespace Spec2Lean.PTX.CnotB32

/-! PTX-CNOT-THM-001 -/
theorem cnotB32_exec_guard_false_no_state_change (s : MachineState) (i : CnotB32Instruction) (h : evalGuard s i.guard = some false) : execCnotB32 s i = some (ExecOutcome.guardFalse s) := by
  unfold execCnotB32
  simp [h]

/-! PTX-CNOT-THM-002 -/
theorem cnotB32_exec_true_guard_writes_cnot_result (s : MachineState) (i : CnotB32Instruction) (r : RegId) (va : U32) (hguard : evalGuard s i.guard = some true) (hd : i.d = Destination.reg r) (ha : evalSource s i.a = some va) : ∃ s', execCnotB32 s i = some (ExecOutcome.executed s') ∧ s'.valueRegs r = some (cnotB32 va) := by
  refine ⟨updateDestination s i.d (cnotB32 va), ?_, ?_⟩
  · simp [execCnotB32, hguard, ha]
  · unfold updateDestination
    rw [hd]
    simp

/-! PTX-CNOT-THM-003 -/
theorem cnotB32_exec_none_iff_missing_guard_or_true_source (s : MachineState) (i : CnotB32Instruction) : execCnotB32 s i = none ↔ (evalGuard s i.guard = none) ∨ (evalGuard s i.guard = some true ∧ evalSource s i.a = none) := by
  unfold execCnotB32
  cases hgs : evalGuard s i.guard with
  | none =>
      simp [hgs]
  | some b =>
      cases b with
      | false =>
          simp [hgs]
      | true =>
          cases hs : evalSource s i.a with
          | none =>
              simp [hgs, hs]
          | some va =>
              simp [hgs, hs]

end Spec2Lean.PTX.CnotB32
