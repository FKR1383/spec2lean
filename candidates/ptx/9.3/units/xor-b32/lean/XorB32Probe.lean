import Spec2Lean.Basic

namespace Spec2Lean
namespace PTX
namespace XorB32

def b32DomainSize : Nat := 2 ^ 32

def xorNat (x y : Nat) : Nat :=
  Nat.xor x y

#eval xorNat 5 3
#eval xorNat 0xFFFFFFFF 0xFFFFFFFF
#eval xorNat 0xFFFF0000 0x00FF00FF
#eval (Nat.xor 5 3) % b32DomainSize

end XorB32
end PTX
end Spec2Lean
