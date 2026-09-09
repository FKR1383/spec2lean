from __future__ import annotations

import json
from typing import Any

from .models import DECLARATION_ROLES, TranslationGroupScope


def build_translation_revision_prompt(
    scope: TranslationGroupScope,
    semantics_by_unit: dict[str, dict[str, Any]],
    current_source: str,
    current_manifest: dict[str, Any],
    diagnostics: list[dict[str, Any]],
    reason: str,
    triggering_unit_id: str,
) -> str:
    return f"""You are performing one bounded Spec2Lean Phase-5 group translation revision.

Update the current group translation only as needed to address the supplied upstream diagnostics,
then finish by calling translation_submit_translation with the complete revised {scope.lean_file}
source and complete declaration mappings. The group file is atomic: never submit a fragment or a
per-instruction Unit.lean file.

Rules:
- All supplied Phase-4 semantic artifacts are the complete semantic authority.
- The diagnostics were triggered while checking {triggering_unit_id}, but preserve and correctly map
  every other instruction and shared declaration in group {scope.group}.
- For COVERAGE_FAILURE, represent every listed uncovered semantic claim/evidence relationship.
- For SEMANTICS_REVISED, reconcile the complete group source and mappings with all current artifacts.
- Preserve valid existing declarations and behavior where compatible; prefer a focused patch.
- Do not weaken semantics to compile, retrieve evidence, browse, critique Phase 4, or add proof padding.
- Map every named declaration using only these roles: {', '.join(DECLARATION_ROLES)}.
- Use fully qualified names, including the namespace, in declaration and supportsDeclarations.
  Unambiguous namespace-relative names are resolved automatically; ambiguous names are rejected.
- Every semantic mapping uses claimRefs containing an exact unitId and claimId. Do not manufacture
  deterministic metadata.
- For mapping-only rejection diagnostics, preserve the Lean source and repair the mappings using
  the exact declarationNames and semanticClaimRefs returned in repairContext. Do not guess claim
  associations or remove declarations to avoid mapping them.
- Use only translation_submit_translation. This is one session with no automatic retry session.

Revision reason: {reason}

Exact Phase-6/upstream diagnostics:
{json.dumps(diagnostics, ensure_ascii=False, indent=2, sort_keys=True)}

Deterministic group scope (do not reproduce metadata):
{json.dumps(scope.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)}

Current Phase-4 artifacts keyed by unit ID:
{json.dumps(semantics_by_unit, ensure_ascii=False, indent=2, sort_keys=True)}

Current {scope.lean_file}:
```lean
{current_source}
```

Current translation manifest:
{json.dumps(current_manifest, ensure_ascii=False, indent=2, sort_keys=True)}
"""
