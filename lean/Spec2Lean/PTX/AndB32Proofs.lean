/-
Spec2Lean proof artifact — PTX ISA 9.3 `and.b32`

Run ID      : ptx-9.3-and.b32-d33dfec2
Unit        : and.b32
Stage       : PROOF_GENERATION (PROVE_BATCH)
Obligations : PTX-AND-THM-001 .. PTX-AND-THM-007 (16 approved theorem
              declarations, theorem-strength approved)

Semantics module : Spec2Lean.PTX.AndB32 (installed under lean/Spec2Lean/PTX/AndB32.lean)

This file contains machine-checked proofs of the approved theorem
declarations only. It imports only the installed semantics module.
No semantic definition, state representation, or theorem statement is
modified here; no `sorry`, `admit`, `axiom`, or `unsafe` is used.

Proof family correspondence (architecture Section 10 / PRF families):
  PTX-AND-THM-001 : relational determinism of AndB32Step (PRF-1)
  PTX-AND-THM-002 : executable/relational correspondence (PRF-2)
  PTX-AND-THM-003 : and-fidelity of the destination write (PRF-3/PRF-7)
  PTX-AND-THM-004 : destination-only frame property (PRF-4)
  PTX-AND-THM-005 : bit-bucket preservation (PRF-3, general 9.2 strength)
  PTX-AND-THM-006 : guard-false preservation (PRF-5)
  PTX-AND-THM-007 : guard classification lemmas (PRF-5)
-/

import Spec2Lean.PTX.AndB32
import Spec2Lean.PTX.CoreProofs

namespace Spec2Lean
namespace PTX
namespace AndB32

/-! # PTX-AND-THM-001: relational determinism of AndB32Step -/

theorem andB32Step_deterministic
    (s : MachineState) (i : AndB32Instruction) (s1 s2 : MachineState)
    (h1 : AndB32Step s i s1) (h2 : AndB32Step s i s2) :
    s1 = s2 := by
  cases h1 with
  | guardFalse hgf =>
      cases h2 with
      | guardFalse hgf' => rfl
      | executed va vb hgt hsa hsb =>
          rw [hgt] at hgf
          nomatch hgf
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

/-! # PTX-AND-THM-002: executable/relational correspondence -/

theorem exec_sound_executed
    (s : MachineState) (i : AndB32Instruction) (s' : MachineState)
    (h : execAndB32 s i = some (ExecOutcome.executed s')) :
    AndB32Step s i s' := by
  unfold execAndB32 at h
  cases hg : evalGuard s i.guard with
  | none => simp [hg] at h
  | some g =>
      cases g with
      | false => simp [hg] at h
      | true =>
          simp [hg] at h
          cases ha : evalSourceA s i.a with
          | none => simp [ha] at h
          | some va =>
              simp [ha] at h
              cases hb : evalSourceB s i.b with
              | none => simp [hb] at h
              | some vb =>
                  simp [hb] at h
                  have hstep : AndB32Step s i (updateDestination s i.d (andValue va vb)) :=
                    AndB32Step.executed s i va vb hg ha hb
                  rw [← h]
                  exact hstep

theorem exec_sound_guardFalse
    (s : MachineState) (i : AndB32Instruction) (s' : MachineState)
    (h : execAndB32 s i = some (ExecOutcome.guardFalse s')) :
    AndB32Step s i s' := by
  unfold execAndB32 at h
  cases hg : evalGuard s i.guard with
  | none => simp [hg] at h
  | some g =>
      cases g with
      | false =>
          have hstep : AndB32Step s i s := AndB32Step.guardFalse s i hg
          simp [hg] at h
          rw [← h]
          exact hstep
      | true =>
          simp [hg] at h
          cases ha : evalSourceA s i.a with
          | none => simp [ha] at h
          | some va =>
              simp [ha] at h
              cases hb : evalSourceB s i.b with
              | none => simp [hb] at h
              | some vb => simp [hb] at h

theorem step_complete
    (s : MachineState) (i : AndB32Instruction) (s' : MachineState)
    (h : AndB32Step s i s') :
    Exists fun (o : ExecOutcome) =>
      execAndB32 s i = some o /\
      (o = ExecOutcome.executed s' \/ o = ExecOutcome.guardFalse s') := by
  cases h with
  | guardFalse hgf =>
      refine ⟨ExecOutcome.guardFalse s, ?_, ?_⟩
      · simp [execAndB32, hgf]
      · right; rfl
  | executed va vb hgt hsa hsb =>
      refine ⟨ExecOutcome.executed (updateDestination s i.d (andValue va vb)), ?_, ?_⟩
      · simp [execAndB32, hgt, hsa, hsb]
      · left; rfl

theorem step_partial_complete
    (s : MachineState) (i : AndB32Instruction) :
    execAndB32 s i = none <->
      ¬ (Exists fun (s' : MachineState) => AndB32Step s i s') := by
  constructor
  · intro hnone
    intro hex
    rcases hex with ⟨s', hstep⟩
    rcases step_complete s i s' hstep with ⟨o, ho, _⟩
    rw [hnone] at ho
    nomatch ho
  · intro hno
    cases hExec : execAndB32 s i with
    | none => rfl
    | some o =>
        cases o with
        | executed s' =>
            have hstep : AndB32Step s i s' := exec_sound_executed s i s' hExec
            exact False.elim (hno ⟨s', hstep⟩)
        | guardFalse s' =>
            have hstep : AndB32Step s i s' := exec_sound_guardFalse s i s' hExec
            exact False.elim (hno ⟨s', hstep⟩)

/-! # PTX-AND-THM-003: and-fidelity of the destination write -/

theorem execAndB32_and_fidelity
    (s : MachineState) (i : AndB32Instruction) (r : RegId) (va vb : B32)
    (hguard : evalGuard s i.guard = some true)
    (hd : i.d = Destination.reg r)
    (ha : evalSourceA s i.a = some va)
    (hb : evalSourceB s i.b = some vb) :
    Exists fun (s' : MachineState) =>
      execAndB32 s i = some (ExecOutcome.executed s') /\
      s'.valueRegs r = some (andValue va vb) := by
  refine ⟨updateDestination s i.d (andValue va vb), ?_, ?_⟩
  · simp [execAndB32, hguard, ha, hb]
  · rw [hd]
    exact Core.updateDestination_reg_same s r (andValue va vb)

/-! # PTX-AND-THM-004: destination-only frame property -/

theorem andB32Step_destination_only_frame
    (s : MachineState) (i : AndB32Instruction) (s' : MachineState) (r : RegId)
    (hstep : AndB32Step s i s')
    (hd : i.d = Destination.reg r) :
    (forall (r' : RegId), r' != r -> s'.valueRegs r' = s.valueRegs r') /\
    (forall (p : PredId), s'.predRegs p = s.predRegs p) := by
  cases hstep with
  | guardFalse hgf =>
      constructor
      · intro r' hne
        rfl
      · intro p
        rfl
  | executed va vb hgt hsa hsb =>
      constructor
      · intro r' hne
        rw [hd]
        exact
          Core.updateDestination_reg_other
            s r r' (andValue va vb) hne
      · intro p
        rw [hd]
        exact
          Core.updateDestination_reg_pred_unchanged
            s r (andValue va vb) p

/-! # PTX-AND-THM-005: bit-bucket destination preserves the state -/

theorem andB32Step_bit_bucket_preserves_state
    (s : MachineState) (i : AndB32Instruction) (s' : MachineState)
    (hstep : AndB32Step s i s')
    (hd : i.d = Destination.bitBucket) :
    s' = s := by
  cases hstep with
  | guardFalse hgf => rfl
  | executed va vb hgt hsa hsb =>
      rw [hd]
      exact
        Core.updateDestination_bitBucket_preserves_state
          s (andValue va vb)

/-! # PTX-AND-THM-006: guard-false behavior preserves the state -/

theorem execAndB32_guard_false_preserves_state
    (s : MachineState) (i : AndB32Instruction)
    (hguard : evalGuard s i.guard = some false) :
    execAndB32 s i = some (ExecOutcome.guardFalse s) := by
  simp [execAndB32, hguard]

theorem andB32Step_guard_false_frame
    (s : MachineState) (i : AndB32Instruction) (s' : MachineState)
    (hstep : AndB32Step s i s')
    (hguard : evalGuard s i.guard = some false) :
    s' = s := by
  cases hstep with
  | guardFalse hgf => rfl
  | executed va vb hgt hsa hsb =>
      rw [hgt] at hguard
      nomatch hguard

/-! # PTX-AND-THM-007: guard classification lemmas -/

theorem andB32_executes_iff_guard_true
    (s : MachineState) (i : AndB32Instruction) (b : Bool)
    (hguard : evalGuard s i.guard = some b)
    (hsources : b = true -> Exists fun (va : B32) => Exists fun (vb : B32) =>
        evalSourceA s i.a = some va /\ evalSourceB s i.b = some vb) :
    (Exists fun (s' : MachineState) =>
        execAndB32 s i = some (ExecOutcome.executed s')) <-> b = true := by
  constructor
  · intro hex
    cases b with
    | false =>
        rcases hex with ⟨s', hex'⟩
        simp [execAndB32, hguard] at hex'
    | true => rfl
  · intro hb
    rw [hb] at hguard
    rcases hsources hb with ⟨va, hv⟩
    rcases hv with ⟨vb, hsa, hsb⟩
    refine ⟨updateDestination s i.d (andValue va vb), ?_⟩
    simp [execAndB32, hguard, hsa, hsb]

theorem evalGuard_unguarded_true
    (s : MachineState) : evalGuard s Guard.unguarded = some true := by
  exact Core.evalGuard_unguarded_true s

theorem evalGuard_atPos_true
    (s : MachineState) (p : PredId) (h : s.predRegs p = some true) :
    evalGuard s (Guard.atPos p) = some true := by
  exact Core.evalGuard_atPos_true s p h

theorem evalGuard_atNeg_true_when_pred_false
    (s : MachineState) (p : PredId) (h : s.predRegs p = some false) :
    evalGuard s (Guard.atNeg p) = some true := by
  exact Core.evalGuard_atNeg_true_when_pred_false s p h

theorem evalGuard_atPos_false
    (s : MachineState) (p : PredId) (h : s.predRegs p = some false) :
    evalGuard s (Guard.atPos p) = some false := by
  exact Core.evalGuard_atPos_false s p h

theorem evalGuard_atNeg_false_when_pred_true
    (s : MachineState) (p : PredId) (h : s.predRegs p = some true) :
    evalGuard s (Guard.atNeg p) = some false := by
  exact Core.evalGuard_atNeg_false_when_pred_true s p h

end AndB32
end PTX
end Spec2Lean
