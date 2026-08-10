def b32Bits : Nat := 32
 def b32DomainSize : Nat := 2 ^ b32Bits
#check (fun x : UInt32 => (by
  have h := UInt32.toNat_lt x
  simpa [b32Bits, b32DomainSize] using h) :
    ∀ x : UInt32, x.toNat < b32DomainSize)