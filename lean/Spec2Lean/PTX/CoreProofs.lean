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

end Core
end PTX
end Spec2Lean
