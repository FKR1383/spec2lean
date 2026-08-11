-- Formalization context:
-- unit: ToBoolean (ecmascript-2025)
-- approved semantic artifact: candidates/ecmascript/2025/units/toboolean/semantics/semantics-v1.json
-- interpretation id: ecmascript-2025-toboolean-semantics-v1
-- source bundle: candidates/ecmascript/2025/units/toboolean/source-bundles/source-bundle-v3.json
-- source evidence fragments used: ECMASCRIPT-2025-TOB-V3-001 ... ECMASCRIPT-2025-TOB-V3-015
-- bounded Lean file: candidates/ecmascript/2025/units/toboolean/lean/ToBoolean-v1.lean
-- unresolved questions (tracked): host-defined object coverage for [[IsHTMLDDA]] and numeric canonical encoding details remain open as per source
-- assumptions: (A-1) basic value model is available locally in this unit; (A-2) literal mappings +0𝔽/-0𝔽/NaN/0ℤ are represented by dedicated constructors.

import Spec2Lean.Basic

namespace Spec2Lean.ECMAScript.ToBoolean

-- ECMASCRIPT-TOB-SEM-001, D-2; evidence: ECMASCRIPT-2025-TOB-V3-002
-- Purpose: support Boolean branch behavior and exact return type.
inductive EcmaBoolean where
  | false : EcmaBoolean
  | true : EcmaBoolean
  deriving DecidableEq, Repr

-- ECMASCRIPT-TOB-SEM-002, D-2; evidence: ECMASCRIPT-2025-TOB-V3-003
-- Purpose: support Number value forms needed for falsy vs truthy checks.
inductive EcmaNumber where
  | posZero : EcmaNumber
  | negZero : EcmaNumber
  | nan : EcmaNumber
  | nonZero : Int -> EcmaNumber
  deriving DecidableEq, Repr

-- ECMASCRIPT-TOB-SEM-002, D-2; evidence: ECMASCRIPT-2025-TOB-V3-014
-- Purpose: BigInt branch uses zero/nonzero behavior.
abbrev EcmaBigInt : Type := Int

-- D-2; evidence: ECMASCRIPT-2025-TOB-V3-010
-- Purpose: String representation needed for empty-string falsy check.
abbrev EcmaString : Type := String

-- D-2; evidence: ECMASCRIPT-2025-TOB-V3-008
-- Purpose: symbol values fall through to the default truthy branch.
inductive EcmaSymbol where
  | mk : String -> EcmaSymbol
  deriving DecidableEq, Repr

-- D-1, ECMASCRIPT-TOB-SEM-004; evidence: ECMASCRIPT-2025-TOB-V3-007
-- Purpose: object branch with explicit [[IsHTMLDDA]] state for the web-compat replacement.
structure EcmaObject where
  hasIsHTMLDDA : Bool
  deriving DecidableEq, Repr

-- ECMASCRIPT-TOB-SEM-001, ECMASCRIPT-TOB-SEM-009; evidence: ECMASCRIPT-2025-TOB-V3-009
-- Purpose: domain includes all ECMAScript language values appearing in ToBoolean.
inductive EcmaValue where
  | undefined : EcmaValue
  | null : EcmaValue
  | boolean : EcmaBoolean -> EcmaValue
  | string : EcmaString -> EcmaValue
  | symbol : EcmaSymbol -> EcmaValue
  | number : EcmaNumber -> EcmaValue
  | bigInt : EcmaBigInt -> EcmaValue
  | object : EcmaObject -> EcmaValue
  deriving DecidableEq, Repr

-- ECMASCRIPT-TOB-SEM-002; evidence: ECMASCRIPT-2025-TOB-V3-003
-- Returns the same Boolean value for Boolean inputs.
def toBooleanBool : EcmaBoolean -> Bool
  | EcmaBoolean.false => false
  | EcmaBoolean.true => true

-- ECMASCRIPT-TOB-SEM-003; evidence: ECMASCRIPT-2025-TOB-V3-004
-- True iff a Number is one of the falsy literals +0𝔽, -0𝔽, or NaN.
def numberIsFalsy (n : EcmaNumber) : Bool :=
  match n with
  | EcmaNumber.posZero => true
  | EcmaNumber.negZero => true
  | EcmaNumber.nan => true
  | EcmaNumber.nonZero _ => false

-- ECMASCRIPT-TOB-SEM-003; evidence: ECMASCRIPT-2025-TOB-V3-004
-- True iff a BigInt is zero (0ℤ).
def bigintIsFalsy (z : EcmaBigInt) : Bool :=
  z = 0

-- ECMASCRIPT-TOB-SEM-003; evidence: ECMASCRIPT-2025-TOB-V3-004, ECMASCRIPT-2025-TOB-V3-010
-- True iff String is empty.
def stringIsFalsy (s : EcmaString) : Bool :=
  s.isEmpty

-- ECMASCRIPT-TOB-SEM-001, ECMASCRIPT-TOB-SEM-002, ECMASCRIPT-TOB-SEM-003,
-- ECMASCRIPT-TOB-SEM-004, ECMASCRIPT-TOB-SEM-005, ECMASCRIPT-TOB-SEM-006, D-1, D-2
-- Main abstract-operation definition corresponding to ToBoolean(argument).
def ToBoolean (argument : EcmaValue) : Bool :=
  match argument with
  | EcmaValue.boolean b => toBooleanBool b
  | EcmaValue.undefined => false
  | EcmaValue.null => false
  | EcmaValue.number n => if numberIsFalsy n then false else true
  | EcmaValue.bigInt z => if bigintIsFalsy z then false else true
  | EcmaValue.string s => if stringIsFalsy s then false else true
  | EcmaValue.object o => if o.hasIsHTMLDDA then false else true
  | EcmaValue.symbol _ => true

-- D-1, ECMASCRIPT-TOB-SEM-001 + ECMASCRIPT-TOB-SEM-006
-- Alias preserving the JS-style camelCase helper style.
def toBoolean (argument : EcmaValue) : Bool :=
  ToBoolean argument

end Spec2Lean.ECMAScript.ToBoolean
