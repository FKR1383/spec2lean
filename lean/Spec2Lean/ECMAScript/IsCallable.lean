-- bounded formalization unit: IsCallable
-- approved semantic artifact: candidates/ecmascript/2025/units/iscallable/semantics/semantics-v1.json
-- interpretation id: ecmascript-2025-iscallable-semantics-v1
-- approved semantic claim IDs: ECMASCRIPT-ISC-SEM-001, ECMASCRIPT-ISC-SEM-002, ECMASCRIPT-ISC-SEM-003, ECMASCRIPT-ISC-SEM-004, ECMASCRIPT-ISC-SEM-005, ECMASCRIPT-ISC-SEM-006
-- architecture design IDs used: D-1, D-2, D-3
-- source evidence fragments: ECMASCRIPT-2025-ISC-001, ECMASCRIPT-2025-ISC-002, ECMASCRIPT-2025-ISC-003, ECMASCRIPT-2025-ISC-004, ECMASCRIPT-2025-ISC-005, ECMASCRIPT-2025-ISC-006, ECMASCRIPT-2025-ISC-007
-- unresolved mapping questions (documented in source artifacts): OQ-1

import Spec2Lean.Basic

namespace Spec2Lean.ECMAScript.IsCallable

-- ECMASCRIPT-ISC-SEM-001, D-1; evidence: ECMASCRIPT-2025-ISC-002
-- ECMASCRIPT-ISC-SEM-001, D-2; evidence: ECMASCRIPT-2025-ISC-006
-- Purpose: local object carrier used to represent callability predicate by design choice.
structure EcmaObject where
  hasCall : Bool
  deriving DecidableEq, Repr

-- ECMASCRIPT-ISC-SEM-001, D-1
-- ECMASCRIPT-ISC-SEM-002, D-3
-- Purpose: ECMAScript value space for IsCallable; non-object constructors cover all branch-input kinds used here.
inductive EcmaValue where
  | undefined : EcmaValue
  | null : EcmaValue
  | boolean : Bool -> EcmaValue
  | number : Int -> EcmaValue
  | bigInt : Int -> EcmaValue
  | string : String -> EcmaValue
  | symbol : String -> EcmaValue
  | object : EcmaObject -> EcmaValue
  deriving DecidableEq, Repr

-- ECMASCRIPT-ISC-SEM-002, D-3; evidence: ECMASCRIPT-2025-ISC-003
-- Purpose: object predicate over values.
def isObject : EcmaValue → Bool
  | EcmaValue.object _ => true
  | _ => false

-- ECMASCRIPT-ISC-SEM-003, ECMASCRIPT-ISC-SEM-004, D-2
-- Purpose: normalized predicate for [[Call]] internal-method presence.
def hasCallInternalMethod : EcmaValue → Bool
  | EcmaValue.object o => o.hasCall
  | _ => false

-- ECMASCRIPT-ISC-SEM-002, ECMASCRIPT-ISC-SEM-003, ECMASCRIPT-ISC-SEM-004, D-1
-- Main abstract operation: If argument is not Object => false; else if [[Call]] exists => true else false.
def IsCallable (argument : EcmaValue) : Bool :=
  if isObject argument then
    hasCallInternalMethod argument
  else
    false

-- ECMASCRIPT-ISC-SEM-002, ECMASCRIPT-ISC-SEM-005
-- Alias preserving camelCase naming style used across ECMAScript AO declarations.
def isCallable (argument : EcmaValue) : Bool :=
  IsCallable argument

end Spec2Lean.ECMAScript.IsCallable
