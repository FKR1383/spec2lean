import Spec2Lean.PTX.AndB32

namespace Spec2Lean
namespace PTX
namespace AndB32

-- Probe M: does simp [hne] close the frame if-goal directly?
example (r r' : RegId) (s : MachineState) (v : B32) (hne : (r' != r) = true) :
    (if r' == r then some v else s.valueRegs r') = s.valueRegs r' := by
  simp [hne]

-- Probe N: does simpa using hbeq give r' = r from (r' == r) = true?
example (r r' : RegId) (hbeq : (r' == r) = true) : r' = r := by
  simpa using hbeq

-- Probe O: full frame executed branch as intended
example (s : MachineState) (i : AndB32Instruction) (r : RegId)
    (hstep : AndB32Step s i s') (hd : i.d = Destination.reg r) :
    (forall (r' : RegId), r' != r -> s'.valueRegs r' = s.valueRegs r') := by
  cases hstep with
  | guardFalse hgf =>
      intro r' hne
      rfl
  | executed va vb hgt hsa hsb =>
      intro r' hne
      rw [hd]
      simp [updateDestination, hne]

end AndB32
end PTX
end Spec2Lean
