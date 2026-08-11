import Spec2Lean.ECMAScript.ToBoolean

namespace Spec2Lean.ECMAScript.ToBoolean

-- ECMASCRIPT-TOB-SEM-001, ECMASCRIPT-TOB-SEM-004, ECMASCRIPT-TOB-SEM-005
-- toBoolean_boolean_identity
 theorem toBoolean_boolean_identity (b : EcmaBoolean) : ToBoolean (EcmaValue.boolean b) = toBooleanBool b := by
  rfl

-- ECMASCRIPT-TOB-SEM-001, ECMASCRIPT-TOB-SEM-002, ECMASCRIPT-TOB-SEM-003
-- toBoolean_falsy_primitive_cases
 theorem toBoolean_falsy_primitive_cases : ToBoolean EcmaValue.undefined = false ∧ ToBoolean EcmaValue.null = false ∧ ToBoolean (EcmaValue.number EcmaNumber.posZero) = false ∧ ToBoolean (EcmaValue.number EcmaNumber.negZero) = false ∧ ToBoolean (EcmaValue.number EcmaNumber.nan) = false ∧ ToBoolean (EcmaValue.bigInt 0) = false ∧ ToBoolean (EcmaValue.string "") = false := by
  constructor
  · rfl
  constructor
  · rfl
  constructor
  · rfl
  constructor
  · rfl
  constructor
  · rfl
  constructor
  · rfl
  · decide

-- ECMASCRIPT-TOB-SEM-005, ECMASCRIPT-TOB-SEM-001
-- toBoolean_object_isHTMLDDA_falsey_branch
 theorem toBoolean_object_isHTMLDDA_falsey_branch (o : EcmaObject) (h : o.hasIsHTMLDDA = true) : ToBoolean (EcmaValue.object o) = false := by
  simp [ToBoolean, h]

-- ECMASCRIPT-TOB-SEM-001, ECMASCRIPT-TOB-SEM-003, ECMASCRIPT-TOB-SEM-004
-- toBoolean_truthy_default_branch
 theorem toBoolean_truthy_default_branch (argument : EcmaValue) : (argument = EcmaValue.boolean EcmaBoolean.true ∨ (∃ n, argument = EcmaValue.number n ∧ numberIsFalsy n = false) ∨ (∃ z, argument = EcmaValue.bigInt z ∧ z ≠ 0) ∨ (∃ s, argument = EcmaValue.string s ∧ stringIsFalsy s = false) ∨ (∃ o, argument = EcmaValue.object o ∧ o.hasIsHTMLDDA = false) ∨ (∃ sym, argument = EcmaValue.symbol sym)) → ToBoolean argument = true := by
  intro hA
  rcases hA with hbool | hnum | hbig | hstr | hobj | hsym
  · subst hbool
    simp [ToBoolean, toBooleanBool]
  · rcases hnum with ⟨n, rfl, hnf⟩
    simp [ToBoolean, hnf]
  · rcases hbig with ⟨z, rfl, hnonzero⟩
    simp [ToBoolean, bigintIsFalsy, hnonzero]
  · rcases hstr with ⟨s, rfl, hsf⟩
    have hsf' : String.isEmpty s = false := by simpa [stringIsFalsy] using hsf
    simp [ToBoolean, stringIsFalsy, hsf']
  · rcases hobj with ⟨o, rfl, hhtml⟩
    simp [ToBoolean, hhtml]
  · rcases hsym with ⟨sym, rfl⟩
    simp [ToBoolean]

-- ECMASCRIPT-TOB-SEM-003, ECMASCRIPT-TOB-SEM-004, ECMASCRIPT-TOB-SEM-005, ECMASCRIPT-TOB-SEM-006, ECMASCRIPT-TOB-SEM-007, ECMASCRIPT-TOB-SEM-008, ECMASCRIPT-TOB-SEM-009
-- toBoolean_false_iff_falsy_cases
 theorem toBoolean_false_iff_falsy_cases (argument : EcmaValue) :
    ToBoolean argument = false ↔
      (argument = EcmaValue.boolean EcmaBoolean.false ∨ argument = EcmaValue.undefined ∨ argument = EcmaValue.null ∨
        (∃ n, argument = EcmaValue.number n ∧ numberIsFalsy n) ∨ (∃ z, argument = EcmaValue.bigInt z ∧ z = 0) ∨
        (∃ s, argument = EcmaValue.string s ∧ stringIsFalsy s) ∨ (∃ o, argument = EcmaValue.object o ∧ o.hasIsHTMLDDA = true)) := by
  constructor
  · intro h
    cases argument with
    | boolean b =>
      cases b with
      | false =>
        exact Or.inl rfl
      | true =>
        exact False.elim (by
          have : toBooleanBool EcmaBoolean.true = false := by simpa [ToBoolean] using h
          simpa [toBooleanBool] using this)
    | undefined =>
      exact Or.inr (Or.inl rfl)
    | null =>
      exact Or.inr (Or.inr (Or.inl rfl))
    | number n =>
      by_cases hnf : numberIsFalsy n
      · exact Or.inr (Or.inr (Or.inr (Or.inl ⟨n, rfl, hnf⟩)))
      · exact False.elim (by simpa [ToBoolean, hnf] using h)
    | bigInt z =>
      have hz0 : z = 0 := by
        have hz : bigintIsFalsy z = true := by simpa [ToBoolean] using h
        simpa [bigintIsFalsy] using hz
      exact Or.inr (Or.inr (Or.inr (Or.inr (Or.inl ⟨z, rfl, hz0⟩))))
    | string s =>
      have hs : stringIsFalsy s := by
        simpa [ToBoolean] using h
      exact Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inl ⟨s, rfl, hs⟩)))))
    | object o =>
      have hhtml : o.hasIsHTMLDDA = true := by
        simpa [ToBoolean] using h
      let hobj : ∃ o', EcmaValue.object o = EcmaValue.object o' ∧ o'.hasIsHTMLDDA = true := ⟨o, rfl, hhtml⟩
      exact Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr hobj)))))
    | symbol s =>
      exact False.elim (by simpa [ToBoolean] using h)
  · intro h
    rcases h with hFalse | hUndef | hNull | hNum | hBig | hStr | hObj
    · rcases hFalse with rfl
      simpa [ToBoolean, toBooleanBool]
    · rcases hUndef with rfl
      simp [ToBoolean]
    · rcases hNull with rfl
      simp [ToBoolean]
    · rcases hNum with ⟨n, rfl, hnf⟩
      simp [ToBoolean, hnf]
    · rcases hBig with ⟨z, rfl, hz⟩
      simp [ToBoolean, hz, bigintIsFalsy]
    · rcases hStr with ⟨s, rfl, hs⟩
      simp [ToBoolean, hs]
    · rcases hObj with ⟨o, rfl, hhtml⟩
      simp [ToBoolean, hhtml]

end Spec2Lean.ECMAScript.ToBoolean