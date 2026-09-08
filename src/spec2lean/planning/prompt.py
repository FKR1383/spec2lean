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
- Before planning, compare every extracted candidate unit with the instructions or instruction
  scope supplied by the user. Inspect its indexed heading, syntax, description, ancestors, and
  explicit cross-references as needed; do not infer relevance from a shared word alone.
- Treat a candidate as relevant only when the indexed specification establishes a concrete logical
  relationship to the user's input: direct instruction identity, an explicitly documented alias or
  encoding/form variant, membership in the requested specification-defined instruction family, or
  an explicit semantic dependency or cross-reference required by a requested instruction.
- Similar spelling, a shared generic operation word, or an incidental occurrence of the user's
  mnemonic in a heading description or body prose is not a logical relationship.
- Completely ignore every unrelated candidate. Do not include its unit ID in `requestedUnitIds`,
  place it in a translation group, use its nodes as supporting evidence, create a prerequisite or
  dependency for it, or allow it to affect ordering or group names. Never invent or rationalize a
  relationship merely to preserve an extracted candidate.
- For every request mode, submit only candidates that pass this relevance check. Preserve all
  required units that pass it and add no unrelated units.
- External prerequisites stay external and are not scheduled requested units.
- Add an edge only for a real planning dependency. Name the definition, constraint, or semantic
  input the dependent unit needs from its prerequisite. A citation, comparison, or "see also"
  reference alone does not impose an order; it remains available through spec_xrefs for retrieval.
  Independent units belong in the same layer.
- Edge direction is prerequisite -> dependent.
- Every edge needs a non-empty reason, source-node support, and origin EXPLICIT or INFERRED.
- Genuine cycles must remain in the submitted edges. Deterministic code schedules mutually
  dependent units together and merges translation groups where their dependencies require joint
  translation. Preserve all real edges and their source support; do not remove an edge to obtain
  an acyclic unit graph. Derive the semantic grouping below from the specification as usual.
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
  semantic submission and call it again within this same session, but never reintroduce an
  unrelated candidate just to make validation pass. Do not merely print JSON.

For external prerequisites, choose a short unique `key`; dependency endpoints may use that key or
a requested unit ID. The deterministic submit tool assigns prerequisite IDs, verifies group
partitions and structural support, and derives layers.

Resolved bounded context:
{json.dumps(context, ensure_ascii=False, indent=2, sort_keys=True)}
"""
