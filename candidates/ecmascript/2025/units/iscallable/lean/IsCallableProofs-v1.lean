import Spec2Lean.ECMAScript.IsCallable

namespace Spec2Lean.ECMAScript.IsCallable

-- ECMASCRIPT-ISC-SEM-002
-- isCallable_non_object_false
 theorem isCallable_non_object_false (argument : EcmaValue) (h : isObject argument = false) : IsCallable argument = false := by
  simp [IsCallable, h]

-- ECMASCRIPT-ISC-SEM-004
-- isCallable_object_with_call_true
theorem isCallable_object_with_call_true (o : EcmaObject) (h : o.hasCall = true) : IsCallable (EcmaValue.object o) = true := by
  simp [IsCallable, hasCallInternalMethod, isObject, h]

-- ECMASCRIPT-ISC-SEM-003
-- isCallable_object_without_call_false
theorem isCallable_object_without_call_false (o : EcmaObject) (h : o.hasCall = false) : IsCallable (EcmaValue.object o) = false := by
  simp [IsCallable, hasCallInternalMethod, isObject, h]

-- ECMASCRIPT-ISC-SEM-002, ECMASCRIPT-ISC-SEM-003, ECMASCRIPT-ISC-SEM-004
-- isCallable_equivalent_branch_predicate
theorem isCallable_equivalent_branch_predicate (argument : EcmaValue) : IsCallable argument = true ↔ isObject argument = true ∧ hasCallInternalMethod argument = true := by
  constructor
  · intro hcall
    by_cases hObj : isObject argument = true
    · exact ⟨hObj, by simpa [IsCallable, hObj] using hcall⟩
    · exfalso
      simpa [IsCallable, hObj] using hcall
  · rintro ⟨hObj, hcall⟩
    simpa [IsCallable, hObj] using hcall

-- ECMASCRIPT-ISC-SEM-005, ECMASCRIPT-ISC-SEM-006
-- isCallable_is_boolean
theorem isCallable_is_boolean (argument : EcmaValue) : IsCallable argument = true ∨ IsCallable argument = false := by
  cases hcall : IsCallable argument <;> simp [hcall]

end Spec2Lean.ECMAScript.IsCallable