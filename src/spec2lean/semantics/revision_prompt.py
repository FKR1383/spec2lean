from __future__ import annotations

import json
from typing import Any

from .models import CLAIM_KINDS, SemanticScope


def build_semantic_revision_prompt(
    scope: SemanticScope,
    bundle: dict[str, Any],
    current: dict[str, Any],
    diagnostics: list[dict[str, Any]],
) -> str:
    return f"""You are performing one bounded Spec2Lean Phase-4 semantic revision.

Revalidate the current semantic artifact against the exact Phase-3 evidence bundle and correct only
the supplied Phase-6 traceability failures. Finish by calling semantics_submit_semantics with the
complete revised semantic submission. This is a revision session; the original Phase-4 extraction
prompt and extraction path are not being replaced.

Rules:
- The evidence bundle remains the complete source boundary. Never retrieve or invent evidence.
- Correct broken claim/evidence relationships, stale semantic structure, or missing traceability
  only where the diagnostics and evidence justify it.
- Preserve valid semantic content and stable claim IDs whenever possible.
- Do not write Lean, repair syntax, translate, plan, browse, or generate proofs.
- Classify claims only as {', '.join(CLAIM_KINDS)} and cite only supplied evidence IDs.
- If the bundle cannot support a required correction, submit INSUFFICIENT_EVIDENCE rather than guess.
- Use only semantics_submit_semantics. This is one session with no automatic retry session.

Deterministic revision scope (do not reproduce metadata):
{json.dumps(scope.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)}

Exact Phase-6 broken traceability diagnostics:
{json.dumps(diagnostics, ensure_ascii=False, indent=2, sort_keys=True)}

Current Phase-4 semantic artifact:
{json.dumps(current, ensure_ascii=False, indent=2, sort_keys=True)}

Exact Phase-3 evidence bundle:
{json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True)}
"""
