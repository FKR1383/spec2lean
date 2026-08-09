import Spec2Lean.PTX.Core

namespace Spec2Lean
namespace PTX
namespace Core

theorem evalGuard_unguarded_true
    (s : MachineState) :
    evalGuard s Guard.unguarded = some true := by
  simp [evalGuard]

theorem evalGuard_atPos_true
    (s : MachineState)
    (p : PredId)
    (h : s.predRegs p = some true) :
    evalGuard s (Guard.atPos p) = some true := by
  simp [evalGuard, h]

theorem evalGuard_atPos_false
    (s : MachineState)
    (p : PredId)
    (h : s.predRegs p = some false) :
    evalGuard s (Guard.atPos p) = some false := by
  simp [evalGuard, h]

theorem evalGuard_atNeg_true_when_pred_false
    (s : MachineState)
    (p : PredId)
    (h : s.predRegs p = some false) :
    evalGuard s (Guard.atNeg p) = some true := by
  simp [evalGuard, h]

theorem evalGuard_atNeg_false_when_pred_true
    (s : MachineState)
    (p : PredId)
    (h : s.predRegs p = some true) :
    evalGuard s (Guard.atNeg p) = some false := by
  simp [evalGuard, h]


/-!
## Generic destination-update properties

These facts depend only on the shared PTX state/update machinery.
Instruction-specific proof files should reuse them rather than reproving
the implementation details of `updateDestination`.
-/

theorem updateDestination_reg_same
    (s : MachineState)
    (r : RegId)
    (value : B32) :
    (updateDestination s (Destination.reg r) value).valueRegs r =
      some value := by
  simp [updateDestination]

theorem updateDestination_reg_other
    (s : MachineState)
    (r r' : RegId)
    (value : B32)
    (hne : r' != r) :
    (updateDestination s (Destination.reg r) value).valueRegs r' =
      s.valueRegs r' := by
  simp [updateDestination]
  intro hrEq
  simp at hne
  exact False.elim (hne hrEq)

theorem updateDestination_reg_pred_unchanged
    (s : MachineState)
    (r : RegId)
    (value : B32)
    (p : PredId) :
    (updateDestination s (Destination.reg r) value).predRegs p =
      s.predRegs p := by
  simp [updateDestination]

theorem updateDestination_bitBucket_preserves_state
    (s : MachineState)
    (value : B32) :
    updateDestination s Destination.bitBucket value = s := by
  rfl

end Core
end PTX
end Spec2Lean
