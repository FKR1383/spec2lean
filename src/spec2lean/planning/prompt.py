from __future__ import annotations

import json

from .scope import Phase1Query, ResolvedScope


MAX_INITIAL_NODE_DETAILS = 16


def build_planner_prompt(query: Phase1Query, scope: ResolvedScope) -> str:
    detailed_nodes = []
    for node_id in scope.root_node_ids[:MAX_INITIAL_NODE_DETAILS]:
        node = query.show(node_id)
        was_truncated = node["textTruncated"] or len(node["text"]) > 8_000
        node["text"] = node["text"][:8_000]
        node["textTruncated"] = was_truncated
        node["ancestors"] = query.ancestors(node_id)
        node["crossReferences"] = query.xrefs(node_id)
        detailed_nodes.append(node)
    context = {
        "request": scope.request.to_dict(),
        "candidateUnits": list(scope.candidate_units),
        "requiredExactUnitIds": list(scope.exact_unit_ids),
        "initialSourceNodes": detailed_nodes,
        "additionalContextNodeIds": list(scope.context_node_ids),
    }
    return f"""You are the single Spec2Lean request-scoped Planner.

Plan only the resolved request below. Your task is planning dependency/order, not semantic
extraction or Lean generation. Never invent an instruction, unit ID, or Phase-1 node ID.
Use only candidate units and source nodes returned by the read-only specdb tools.

Rules:
- For an exact, source-subtree, or full-spec request, submit every required exact unit ID and no others.
- For a conceptual family request, select only genuine members from candidateUnits.
- External prerequisites stay external and are not scheduled requested units.
- Add an edge only for a real planning dependency. Independent units belong in the same layer.
- Edge direction is prerequisite -> dependent.
- Every edge needs a non-empty reason, source-node support, and origin EXPLICIT or INFERRED.
- Genuine cycles must remain in the submitted edges; deterministic code will represent them.
- Do not attempt filesystem, shell, internet, subagent, semantic extraction, or Lean work.
- You must finish by calling specdb_submit_plan. If it returns validation diagnostics, correct the
  semantic submission and call it again within this same session. Do not merely print JSON.

For external prerequisites, choose a short unique `key`; dependency endpoints may use that key or
a requested unit ID. The deterministic submit tool assigns prerequisite IDs and derives layers.

Resolved bounded context:
{json.dumps(context, ensure_ascii=False, indent=2, sort_keys=True)}
"""
