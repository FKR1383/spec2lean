from __future__ import annotations

import json

from .models import EVIDENCE_ROLES, EvidenceScope
from .query import EvidenceQuery
from .validation import required_official_renditions


MAX_INITIAL_TEXT_CHARS = 8_000


def build_retriever_prompt(query: EvidenceQuery, scope: EvidenceScope) -> str:
    initial = []
    for node_id, basis in scope.seed_nodes:
        value = query.show(node_id)
        value["exactText"] = value["exactText"][:MAX_INITIAL_TEXT_CHARS]
        value["textTruncated"] = value["textTruncated"] or len(query._row(node_id)["raw_text"]) > MAX_INITIAL_TEXT_CHARS
        value["scopeBasis"] = basis
        value["ancestors"] = query.ancestors(node_id)
        initial.append(value)
    context = {
        "planRunId": scope.plan_run_id,
        "unit": scope.unit,
        "relevantExternalPrerequisites": list(scope.prerequisites),
        "relatedDependencies": list(scope.dependencies),
        "initialSourceNodes": initial,
        "requiredOfficialRenditions": sorted(required_official_renditions(query, scope)),
    }
    roles = ", ".join(EVIDENCE_ROLES)
    return f"""You are the single Spec2Lean Phase-3 Evidence Retriever for exactly one planned unit.

Select exact specification evidence only. You are not a semantic extractor and must not create
claims, interpretations, assumptions, Lean, theorems, proofs, checking steps, or troubleshooting.

Rules:
- Stay within the one unit below. Begin with its attached Phase-1 nodes.
- Explore only their subtree/ancestors, explicit cross-references, definitions, correlations,
  relevant Phase-2 prerequisites, and nearby nodes needed for this unit.
- Use spec_search only as a last resort and give a specific relevance justification.
- Call spec_show before selecting a node discovered by another tool.
- Never invent or manually quote source text, node IDs, span IDs, provenance, hashes, anchors,
  pages, or bounding boxes. Deterministic code reconstructs those fields from Phase 1.
- Prefer meaningful paragraphs, syntax/algorithm blocks, table units, definitions, notes, or a
  small contiguous group of adjacent nodes. Avoid whole chapters and sentence-per-item slicing.
- CORE means directly needed to understand/formalize this unit. SUPPORTING means a bounded
  definition, shared rule, context, example, or explicit-reference aid.
- When requiredOfficialRenditions is ["html", "pdf"], use both official renditions. For every
  selected CORE/SUPPORTING role, select the corresponding passage from both HTML and PDF with
  the same role and tier. Do not pair unrelated text merely to satisfy this rule.
- Roles are relevance labels only: {roles}.
- Finish by calling specdb_submit_evidence with this exact unit ID and your selections.
- Each selection contains sourceNodeIds, optional sourceSpanIds, role, CORE/SUPPORTING tier, and
  a short relevance-only rationale. Do not include exact text or any semantic fields.
- If submission returns deterministic diagnostics, correct it and resubmit in this same session.
- Do not use shell, filesystem, internet, subagents, or any tool outside specdb.

Bounded Phase-2/Phase-1 context:
{json.dumps(context, ensure_ascii=False, indent=2, sort_keys=True)}
"""
