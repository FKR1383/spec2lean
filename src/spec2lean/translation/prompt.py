from __future__ import annotations

import json
from typing import Any

from .models import DECLARATION_ROLES, TranslationGroupScope


def build_translator_prompt(
    scope: TranslationGroupScope,
    semantics_by_unit: dict[str, dict[str, Any]],
    shared_core_source: str | None = None,
) -> str:
    if scope.shared_core is None:
        core_rules = """- This group has no planned shared prerequisites. Submit `sharedUses: []`.
- Keep genuinely unit-specific declarations in this group; do not invent a speculative global core.
"""
        core_context = "No shared core is required by this group."
    else:
        module = scope.shared_core["leanModule"]
        core_rules = f"""- Import the frozen module `{module}` exactly and reuse its registered declarations.
- Submit one `sharedUses` entry for every dependency in `sharedCore.concepts`; name the exact
  registered declarations actually referenced by this group.
- Do not redeclare, alias around, locally substitute for, or modify a shared-core concept. A local
  declaration may not claim a semantic claim owned by a shared dependency.
- If a required concept is absent, do not invent a local representation; report the deterministic
  `MISSING_SHARED_ABSTRACTION` condition instead of submitting a translation.
"""
        core_context = f"""Frozen shared-core registry:
{json.dumps(scope.shared_core, ensure_ascii=False, indent=2, sort_keys=True)}

Frozen shared-core Lean source (read-only):
```lean
{shared_core_source or ''}
```"""
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
{core_rules.rstrip()}
- Implement each exact instruction spelling as a distinct pure operation. Make this OPERATION the
  small, readable primary semantic declaration; do not let an unmodified instruction expose behavior
  belonging to a modifier variant.
- Generate an EXECUTION declaration only when it implements genuine behavior beyond the pure result
  and that behavior is supported by the unit's accepted Phase-4 stateEffects or predication. A
  destination-shaped syntax operand, result, or value-level destination assignment alone never
  requires EXECUTION.
- When Phase 4 has neither stateEffects nor predication, the pure OPERATION is the complete
  formalization. Do not add an execute* wrapper, an unused destination parameter, or a definition
  that merely returns the pure operation.
- Where execution semantics are present, keep them secondary to the pure result function so later
  checking can reason directly about the operation.
- Preserve explicit operational and implementation-oriented algorithms as independently meaningful
  definitions only when the semantic artifact distinguishes them. Never manufacture duplicate
  functions or trivial theorem padding.
- Represent operands, branches, edge cases, destination update, predication, restrictions, and state
  effects to the extent required by the semantic artifact. Do not weaken or omit semantics merely to
  simplify Lean.
- Use Lean 4 and ASCII declaration names. The file may use Lean's standard library.
- The source must contain no sorry, admit, axiom declarations, unsafe code, or verification bypass.
- Phase 5 is translation, not authoritative checking: do not claim source faithfulness and do not
  generate large theorem families. Small definitions needed by the semantics are appropriate.
- Map every named top-level declaration in the submitted source. Use one of these roles:
  {', '.join(DECLARATION_ROLES)}.
- Every semantic declaration mapping must cite one or more existing claimRefs, each containing the
  exact unitId and claimId. A pure
  IMPLEMENTATION_HELPER may instead use supportsDeclarations. Never invent IDs or reproduce evidence
  hashes, source anchors, quotations, or deterministic metadata.
- Every INSTRUCTION needs its own OPERATION mapping. Predicated semantics also need an EXECUTION
  mapping; other execution/state wrappers are optional and valid only when they implement genuine
  source-supported behavior. Introduced structures/inductives/classes use PRIMARY_TYPE.
- If deterministic diagnostics reject the tool call, correct the candidate and resubmit within this
  same session. There is no second Translator session.

Deterministic group/run context (do not reproduce this metadata in the tool call):
{json.dumps(scope.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)}

Accepted Phase-4 semantic artifacts keyed by unit ID (the complete specification input):
{json.dumps(semantics_by_unit, ensure_ascii=False, indent=2, sort_keys=True)}

{core_context}
"""
