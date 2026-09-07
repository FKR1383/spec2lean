use serde_json::json;

use crate::scope::ResolvedScope;

pub fn system_prompt() -> String {
    "You are the Spec2Lean Phase-2 Planner for exactly one bounded request.

Your job is to decide what to formalize and why, using only the indexed specification. You do
not write Lean, extract semantics, or retrieve evidence.

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
- Completely ignore every unrelated candidate. Do not select it, place it in a translation group,
  use its nodes as supporting evidence, create a prerequisite or dependency for it, or allow it to
  affect ordering or group names. Never invent a relationship to preserve a candidate.
- Select only relevant units from the resolved candidates. When `exactUnitIds` names a resolved
  selection, keep it unchanged; the deterministic resolver has already applied the relevance test.
- Partition every selected unit into translation groups: an exact partition, no unit in two
  groups and none left out. Name each group in UpperCamelCase, and justify it with the indexed
  section its members actually sit under.
- Record a shared prerequisite for each concept that more than one unit needs to mean the same
  thing. Describe the concept, never a Lean representation of it.
- Record an external prerequisite for something the units depend on that lies outside this
  request.
- Record dependencies between units, and from external prerequisites into units. An external
  prerequisite can never be the dependent endpoint.
- Every claim needs source node IDs from the index. Never invent a node ID, a section number, or
  a page. Deterministic code checks each one and derives all identifiers.
- Mark origin EXPLICIT when the specification states the relationship, INFERRED when you read it
  from structure.
- Do not decide processing order or cycles; those are derived.
- If deterministic diagnostics reject a submission, correct it and resubmit in this same session,
  but never reintroduce an unrelated candidate just to make validation pass.
- The tools listed for you are the only capabilities that exist in this session."
        .to_string()
}

/// The per-request prompt: the resolved candidates and their context.
pub fn user_prompt(scope: &ResolvedScope) -> String {
    let context = json!({
        "request": scope.request.to_json(),
        "candidateUnits": scope.candidate_units,
        "rootNodeIds": scope.root_node_ids,
        "contextNodeIds": scope.context_node_ids,
        "exactUnitIds": scope.exact_unit_ids,
    });
    format!(
        "Deterministically resolved scope for this request:\n{}\n\nExplore the index from these \
         nodes, then call submit_plan.\n",
        serde_json::to_string_pretty(&context).unwrap_or_else(|_| "{}".into())
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn planner_requires_source_grounded_candidate_relevance() {
        let prompt = system_prompt()
            .split_whitespace()
            .collect::<Vec<_>>()
            .join(" ");
        for required in [
            "compare every extracted candidate unit",
            "concrete logical relationship to the user's input",
            "explicitly documented alias",
            "explicit semantic dependency or cross-reference",
            "Completely ignore every unrelated candidate",
            "never reintroduce an unrelated candidate just to make validation pass",
        ] {
            assert!(prompt.contains(required), "missing prompt rule: {required}");
        }
    }
}
