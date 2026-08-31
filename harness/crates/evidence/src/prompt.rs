use serde_json::{Value, json};
use spec2lean_specdb::{SpecDb, SpecDbError, truncate_chars};

use crate::model::Role;
use crate::render::show;
use crate::scope::EvidenceScope;
use crate::validation::required_official_renditions;

const MAX_INITIAL_TEXT_CHARS: usize = 8_000;

/// The stable half of the session: identical for every unit of every run, so it
/// sits at the front of the cached prefix and is paid for once.
pub fn system_prompt() -> String {
    let roles = Role::ALL
        .iter()
        .map(|role| role.as_str())
        .collect::<Vec<_>>()
        .join(", ");
    format!(
        "You are the single Spec2Lean Phase-3 Evidence Retriever for exactly one planned unit.

Select exact specification evidence only. You are not a semantic extractor and must not create
claims, interpretations, assumptions, Lean, theorems, proofs, checking steps, or troubleshooting.

Rules:
- Stay within the one unit you are given. Begin with its attached Phase-1 nodes.
- Explore only their subtree/ancestors, explicit cross-references, definitions, correlations,
  relevant Phase-2 external/shared prerequisites, and nearby nodes needed for this unit.
- Use spec_search only as a last resort and give a specific relevance justification.
- Call spec_show before selecting a node discovered by another tool.
- Never invent or manually quote source text, node IDs, span IDs, provenance, hashes, anchors,
  pages, or bounding boxes. Deterministic code reconstructs those fields from Phase 1.
- Prefer meaningful paragraphs, syntax/algorithm blocks, table units, definitions, notes, or a
  small contiguous group of adjacent nodes. Avoid whole chapters and sentence-per-item slicing.
- CORE means directly needed to understand/formalize this unit. SUPPORTING means a bounded
  definition, shared rule, context, example, or explicit-reference aid.
- When requiredOfficialRenditions is [\"html\", \"pdf\"], use both official renditions. For every
  selected CORE/SUPPORTING role, select the corresponding passage from both HTML and PDF with
  the same role and tier. Do not pair unrelated text merely to satisfy this rule.
- Roles are relevance labels only: {roles}.
- Finish by calling submit_evidence with this exact unit ID and your selections.
- Each selection contains sourceNodeIds, optional sourceSpanIds, role, CORE/SUPPORTING tier, and
  a short relevance-only rationale. Do not include exact text or any semantic fields.
- If submission returns deterministic diagnostics, correct it and resubmit in this same session.
- The tools listed for you are the only capabilities that exist in this session."
    )
}

/// The per-unit half: the Phase-2 boundary plus the seed nodes' exact text.
///
/// This is large and byte-identical across every step of a session, which is
/// why the Anthropic adapter puts a cache breakpoint at the end of it.
pub fn user_prompt(db: &SpecDb, scope: &EvidenceScope) -> Result<String, SpecDbError> {
    let mut initial = Vec::with_capacity(scope.seed_nodes.len());
    for seed in &scope.seed_nodes {
        let row = db.node(&seed.node_id)?;
        let mut value = show(db, &row)?;
        let (text, truncated) = truncate_chars(&row.raw_text, MAX_INITIAL_TEXT_CHARS);
        value["exactText"] = json!(text);
        value["textTruncated"] = json!(truncated);
        value["scopeBasis"] = json!(seed.basis);
        value["ancestors"] = json!(
            db.ancestors(&seed.node_id, 30)?
                .iter()
                .map(crate::render::planning_summary)
                .collect::<Vec<_>>()
        );
        initial.push(value);
    }
    let renditions: Vec<&str> = required_official_renditions(db, scope)?
        .iter()
        .map(|value| value.as_str())
        .collect();
    let context = json!({
        "planRunId": scope.plan_run_id,
        "unit": scope.unit,
        "relevantExternalPrerequisites": scope.prerequisites,
        "relevantSharedPrerequisites": scope.shared_prerequisites,
        "relatedDependencies": scope.dependencies,
        "initialSourceNodes": initial,
        "requiredOfficialRenditions": renditions,
    });
    Ok(format!(
        "Bounded Phase-2/Phase-1 context:\n{}\n",
        pretty(&context)
    ))
}

/// Two-space indented, key-sorted JSON — the shape the Python prompt used, kept
/// so prompts stay diffable between the two implementations.
fn pretty(value: &Value) -> String {
    serde_json::to_string_pretty(value).unwrap_or_else(|_| "{}".to_string())
}
