from __future__ import annotations

import json
from typing import Any

from .models import DECLARATION_ROLES, TranslationGroupScope


def build_translator_prompt(
    scope: TranslationGroupScope,
    semantics_by_unit: dict[str, dict[str, Any]],
) -> str:
    return f"""You are the Spec2Lean Phase-5 Lean Translator for exactly one instruction group.

Translate all supplied accepted Phase-4 semantic artifacts into one clear Lean 4 semantic
implementation, then finish by calling translation_submit_translation. The Phase-4 artifacts are
your primary and complete specification authority. Do not reinterpret the original specification,
retrieve evidence, browse, use uncited domain knowledge to add behavior, write proofs as a substitute
for functionality, or call any tool other than translation_submit_translation.

Translation rules:
- Submit one complete {scope.lean_file} source string. No per-instruction Unit.lean files or hidden
  fragments exist.
- Put the complete group under namespace {scope.suggested_namespace}.
- Define canonical value, carry, predicate, and machine-state types once and reuse them for every
  instruction in this group. Never create incompatible per-instruction State, U32, register, carry,
  or predicate representations.
- Implement each exact instruction spelling as a distinct operation and, when required, execution
  function. Do not let an unmodified instruction expose behavior belonging to a modifier variant.
- Where applicable, separate a pure result function from execution/state update semantics so later
  checking can reason directly about the operation.
- Preserve explicit operational and implementation-oriented algorithms as independently meaningful
  definitions only when the semantic artifact distinguishes them. Never manufacture duplicate
  functions or trivial theorem padding.
- Represent operands, branches, edge cases, destination update, predication, restrictions, and state
  effects to the extent required by the semantic artifact. Do not weaken or omit semantics merely to
  simplify Lean.
- Preserve ASSUMPTION claims as explicit modeling choices in the Lean source comments and claim
  mappings. Carry any abstract inputs and constraints into the definitions; do not silently turn
  assumptions into specification facts or introduce axiom declarations for them.
- Use Lean 4 and ASCII declaration names. The file may use Lean's standard library.
- The source must contain no sorry, admit, axiom declarations, unsafe code, or verification bypass.
- Phase 5 is translation, not authoritative checking: do not claim source faithfulness and do not
  generate large theorem families. Small definitions needed by the semantics are appropriate.
- Map every named top-level declaration in the submitted source. Use one of these roles:
  {', '.join(DECLARATION_ROLES)}.
- Every semantic declaration mapping must cite one or more existing claimRefs, each containing the
  exact unitId and claimId. A shared declaration may cite claims from several units. A pure
  IMPLEMENTATION_HELPER may instead use supportsDeclarations. Never invent IDs or reproduce evidence
  hashes, source anchors, quotations, or deterministic metadata.
- Every INSTRUCTION needs its own OPERATION mapping. If its semantics has state effects or predication,
  it also needs its own EXECUTION mapping. Introduced structures/inductives/classes use PRIMARY_TYPE.
- If deterministic diagnostics reject the tool call, correct the candidate and resubmit within this
  same session. There is no second Translator session.

Deterministic group/run context (do not reproduce this metadata in the tool call):
{json.dumps(scope.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)}

Accepted Phase-4 semantic artifacts keyed by unit ID (the complete specification input):
{json.dumps(semantics_by_unit, ensure_ascii=False, indent=2, sort_keys=True)}
"""
