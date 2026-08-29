from __future__ import annotations

import json
from typing import Any

from .models import CLAIM_KINDS, SemanticScope


def build_extractor_prompt(scope: SemanticScope, bundle: dict[str, Any]) -> str:
    official_types = {
        item.get("sourceType") for item in bundle.get("evidence", [])
        if isinstance(item, dict)
    } & {"html", "pdf"}
    dual_source_rule = (
        "- This bundle contains official HTML and PDF renditions. Every SOURCE_FACT and "
        "DERIVED_INTERPRETATION claim must cite supporting evidence from both renditions. "
        "Use the matching HTML/PDF passages; never add an unrelated citation just to satisfy "
        "the rule.\n"
        if official_types == {"html", "pdf"} else ""
    )
    return f"""You are the Spec2Lean Phase-4 Semantic Extractor for exactly one planned unit.

Your only job is to interpret the supplied Phase-3 evidence bundle into a precise structured
semantic description and finish by calling semantics_submit_semantics. Do not write Lean, propose proofs,
retrieve more evidence, browse, use prior knowledge to fill specification gaps, or call any tool
other than semantics_get_evidence and semantics_submit_semantics.

Rules:
- Call semantics_get_evidence once before extracting. Its immutable result is the complete source
  boundary for this session. Do not attempt to read evidence from the filesystem.
- The bundle may contain `resolutions` created by the Open Question Handler. These are explicitly
  non-normative. Any claim that cites a resolution:* ID must be ASSUMPTION, never SOURCE_FACT or
  DERIVED_INTERPRETATION. Keep its INTERNET, RUNTIME, or LLM_REASONING provenance visible through
  that citation; do not describe it as official specification evidence.
- Use instruction-specific functionality as the center of an INSTRUCTION artifact: explicit
  inputs, result, core operation, and meaningful algorithm branches where the evidence has them.
- Separate the pure operation from destination/machine state effects and predication.
- Preserve exceptional, invalid, undefined, edge, version, and target behavior only when supported.
- Every semantic component must cite evidence IDs from this bundle. A DESIGN_DEPENDENCY may omit
  evidence only when it is explicitly a later modeling need rather than a specification fact.
{dual_source_rule}- Classify claims only as {', '.join(CLAIM_KINDS)}. Never create OPEN_QUESTION.
- SOURCE_FACT is directly stated by evidence. DERIVED_INTERPRETATION is the operational reading
  derived from cited evidence. DESIGN_DEPENDENCY is a later modeling need. ASSUMPTION is a genuine
  assumption not established by the evidence. Do not disguise modeling choices as source facts.
- Use short stable claim IDs beginning claim:, unique within this artifact.
- For every `relevantSharedPrerequisites` entry in the deterministic scope, include exactly one
  dependency with its exact dependencyId and concept name. Describe WHAT the shared concept must
  mean, and link it to one or more local claims through semanticClaimIds.
- A genuinely discovered modeling dependency that is not in relevantSharedPrerequisites may remain
  unbound by omitting dependencyId. Do not claim that a shared semantic artifact already exists.
- Do not include Lean-specific representation choices.
- If a required semantic aspect cannot safely be determined, submit INSUFFICIENT_EVIDENCE with
  concrete missingAspects and an explanation. Do not guess to obtain SUCCESS.
- If deterministic diagnostics reject a submission, correct it and resubmit in this same session.

Deterministic unit/run context (do not reproduce metadata in the tool call):
{json.dumps(scope.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)}

The exact Phase-3 bundle is available only through semantics_get_evidence so it is not duplicated
inside this operating-system command-line argument.
"""
