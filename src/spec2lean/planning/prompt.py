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

Plan only the resolved request below. Your task is planning dependency/order and specification-
derived output grouping, not semantic extraction or Lean generation. Never invent an instruction,
unit ID, Phase-1 node ID, or a language-specific category table.
Use only candidate units and source nodes returned by the read-only specdb tools.

Rules:
- For an exact, source-subtree, or full-spec request, submit every required exact unit ID and no others.
- For a conceptual family request, select only genuine members from candidateUnits.
- External prerequisites stay external and are not scheduled requested units.
- Identify shared prerequisites needed by the bounded requested subset. A shared prerequisite is a
  source-level semantic concept reused by multiple requested units, or clearly specification-wide
  infrastructure genuinely needed by a requested unit. Keep it distinct from requested units and
  external prerequisites, and list exactly the selected unit IDs that require it in `requiredBy`.
- Give every shared prerequisite a short stable conceptual `key`, a specification-derived `name`,
  an open text `kind`, a planning reason, and source-node support. Do not use a built-in catalog of
  concepts, and do not add speculative concepts for the rest of the specification.
- Phase 2 is Lean-independent. Never choose or mention a Lean type, declaration, namespace, library,
  data representation, or implementation strategy in a shared prerequisite.
- Add an edge only for a real planning dependency. Independent units belong in the same layer.
- Edge direction is prerequisite -> dependent.
- Every edge needs a non-empty reason, source-node support, and origin EXPLICIT or INFERRED.
- Genuine cycles must remain in the submitted edges; deterministic code will represent them.
- Partition every requested unit into exactly one `translationGroups` entry. Derive concise
  UpperCamelCase group names from indexed specification headings, ancestors, terminology, and
  semantic cohesion. Prefer an explicit specification family/section when one exists; otherwise
  infer the smallest coherent group from the indexed structure.
- Units under the same meaningful indexed family should share a group. Prefer the family concept
  over repeating an individual instruction name in the group name; do not split sibling units that
  the specification presents as one semantic family merely because each has its own subsection.
- Every group needs a non-empty reason, origin EXPLICIT or INFERRED, and source nodes that support
  every member through that member's own indexed node or ancestors. Never classify by a built-in
  mnemonic list, and never use a catch-all merely because the source language is unfamiliar.
- Do not attempt filesystem, shell, internet, subagent, semantic extraction, or Lean work.
- You must finish by calling specdb_submit_plan. If it returns validation diagnostics, correct the
  semantic submission and call it again within this same session. Do not merely print JSON.

For external prerequisites, choose a short unique `key`; dependency endpoints may use that key or
a requested unit ID. The deterministic submit tool assigns prerequisite IDs, verifies group
partitions and structural support, and derives layers.

Resolved bounded context:
{json.dumps(context, ensure_ascii=False, indent=2, sort_keys=True)}
"""
