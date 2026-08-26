from __future__ import annotations

import json
from typing import Any

from .models import DECLARATION_ROLES, TranslationScope


def build_translator_prompt(
    scope: TranslationScope,
    semantics: dict[str, Any],
    shared_sources: list[dict[str, str]],
) -> str:
    shared = (
        json.dumps(shared_sources, ensure_ascii=False, indent=2, sort_keys=True)
        if shared_sources
        else "[] (No shared Lean infrastructure exists in the current architecture.)"
    )
    return f"""You are the Spec2Lean Phase-5 Lean Translator for exactly one planned unit.

Translate the supplied accepted Phase-4 semantic artifact into a clear Lean 4 semantic
implementation, then finish by calling translation_submit_translation. The Phase-4 artifact is
your primary and complete specification authority. Do not reinterpret the original specification,
retrieve evidence, browse, use uncited domain knowledge to add behavior, write proofs as a substitute
for functionality, or call any tool other than translation_submit_translation.

Translation rules:
- Implement the actual unit-specific operation. For an instruction, the core result computation must
  be explicit and central; a module consisting mostly of generic guard/state machinery is invalid.
- Where applicable, separate a pure result function from execution/state update semantics so later
  checking can reason directly about the operation.
- Preserve explicit operational and implementation-oriented algorithms as independently meaningful
  definitions only when the semantic artifact distinguishes them. Never manufacture duplicate
  functions or trivial theorem padding.
- Represent operands, branches, edge cases, destination update, predication, restrictions, and state
  effects to the extent required by the semantic artifact. Do not weaken or omit semantics merely to
  simplify Lean.
- Reuse compatible supplied shared Lean definitions. Do not duplicate generic bit-vector, register,
  predicate, state, destination-update, or guard definitions already present. If none fit, keep this
  unit minimal; do not invent a large framework.
- Use Lean 4 and ASCII declaration names, preferably under namespace {scope.suggested_namespace}.
- Submit a complete Unit.lean source string. It may use Lean's standard library, but assume no
  abandoned pre-reset project modules exist.
- The source must contain no sorry, admit, axiom declarations, unsafe code, or verification bypass.
- Phase 5 is translation, not authoritative checking: do not claim source faithfulness and do not
  generate large theorem families. Small definitions needed by the semantics are appropriate.
- Map every named top-level declaration in the submitted source. Use one of these roles:
  {', '.join(DECLARATION_ROLES)}.
- Every semantic declaration mapping must cite one or more existing semantic claim IDs that justify
  it. A pure IMPLEMENTATION_HELPER may instead use supportsDeclarations to reference mapped semantic
  declarations; that chain must resolve to claims. Never invent claim IDs or reproduce evidence
  hashes, source anchors, quotations, or deterministic metadata.
- An INSTRUCTION needs an OPERATION mapping. If its semantics has state effects or predication, it also
  needs an EXECUTION mapping. Introduced structures/inductives/classes use PRIMARY_TYPE.
- If deterministic diagnostics reject the tool call, correct the candidate and resubmit within this
  same session. There is no second Translator session.

Deterministic unit/run context (do not reproduce this metadata in the tool call):
{json.dumps(scope.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)}

Accepted Phase-4 semantic artifact (the complete specification input):
{json.dumps(semantics, ensure_ascii=False, indent=2, sort_keys=True)}

Existing shared Lean sources from the current architecture only:
{shared}
"""
