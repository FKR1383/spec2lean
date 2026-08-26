from __future__ import annotations

import json
from typing import Any

from .models import DECLARATION_ROLES, TranslationScope


def build_translation_revision_prompt(
    scope: TranslationScope,
    semantics: dict[str, Any],
    current_source: str,
    current_manifest: dict[str, Any],
    diagnostics: list[dict[str, Any]],
    reason: str,
    shared_sources: list[dict[str, str]],
) -> str:
    return f"""You are performing one bounded Spec2Lean Phase-5 Lean translation revision.

Update the current Lean translation only as needed to address the supplied upstream diagnostics,
then finish by calling translation_submit_translation with the complete revised Unit.lean source
and complete declaration mappings. This separate revision prompt does not replace or modify the
original Phase-5 translation prompt.

Rules:
- The current Phase-4 semantic artifact is the complete semantic authority.
- For COVERAGE_FAILURE, represent every listed uncovered semantic claim/evidence relationship.
- For SEMANTICS_REVISED, reconcile the translation and mappings with the revised semantic artifact.
- Preserve valid existing Lean declarations and behavior where compatible; prefer a focused patch.
- Do not weaken semantics to compile, retrieve evidence, browse, plan, critique Phase 4, or generate
  theorem/proof padding.
- Map every named declaration using only these roles: {', '.join(DECLARATION_ROLES)}.
- Cite only claim IDs in the current semantic artifact. Do not manufacture deterministic metadata.
- Use only translation_submit_translation. This is one session with no automatic retry session.

Revision reason: {reason}

Exact Phase-6/upstream diagnostics:
{json.dumps(diagnostics, ensure_ascii=False, indent=2, sort_keys=True)}

Deterministic translation scope (do not reproduce metadata):
{json.dumps(scope.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)}

Current Phase-4 semantic artifact:
{json.dumps(semantics, ensure_ascii=False, indent=2, sort_keys=True)}

Current Unit.lean:
```lean
{current_source}
```

Current translation manifest:
{json.dumps(current_manifest, ensure_ascii=False, indent=2, sort_keys=True)}

Existing shared Lean sources:
{json.dumps(shared_sources, ensure_ascii=False, indent=2, sort_keys=True)}
"""
