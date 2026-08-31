use serde_json::Value;

use crate::model::ClaimKind;
use crate::scope::SemanticScope;

/// The stable half of the session — identical for every unit, so it sits at the
/// front of the cached prefix.
///
/// One line is conditional (the dual-rendition rule), which would break caching
/// across units if it lived here; it is carried in the per-unit prompt instead.
pub fn system_prompt() -> String {
    let kinds = ClaimKind::ALL
        .iter()
        .map(|kind| kind.as_str())
        .collect::<Vec<_>>()
        .join(", ");
    format!(
        "You are the Spec2Lean Phase-4 Semantic Extractor for exactly one planned unit.

Your only job is to interpret the supplied Phase-3 evidence bundle into a precise structured
semantic description and finish by calling submit_semantics. Do not write Lean, propose proofs,
retrieve more evidence, browse, or use prior knowledge to fill specification gaps.

Rules:
- Call get_evidence once before extracting. Its immutable result is the complete source
  boundary for this session.
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
- Classify claims only as {kinds}. Never create OPEN_QUESTION.
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
- The tools listed for you are the only capabilities that exist in this session."
    )
}

/// The per-unit half: the deterministic scope, plus the dual-rendition rule
/// when this bundle actually has both official renditions.
pub fn user_prompt(scope: &SemanticScope, bundle: &Value) -> String {
    let official: std::collections::BTreeSet<&str> = bundle
        .get("evidence")
        .and_then(Value::as_array)
        .map(|items| {
            items
                .iter()
                .filter_map(|item| item.get("sourceType").and_then(Value::as_str))
                .filter(|value| matches!(*value, "html" | "pdf"))
                .collect()
        })
        .unwrap_or_default();
    let dual_source_rule = if official.len() == 2 {
        "This bundle contains official HTML and PDF renditions. Every SOURCE_FACT and \
         DERIVED_INTERPRETATION claim must cite supporting evidence from both renditions. \
         Use the matching HTML/PDF passages; never add an unrelated citation just to satisfy \
         the rule.\n\n"
    } else {
        ""
    };
    format!(
        "{dual_source_rule}Deterministic unit/run context (do not reproduce metadata in the tool call):\n{}\n\nThe exact Phase-3 bundle is available through get_evidence.\n",
        serde_json::to_string_pretty(&scope.to_json()).unwrap_or_else(|_| "{}".into())
    )
}
