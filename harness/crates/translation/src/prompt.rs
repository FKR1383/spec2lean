use serde_json::Value;
use std::collections::BTreeMap;

use crate::scope::TranslationScope;
use crate::validation::DECLARATION_ROLES;

pub fn system_prompt() -> String {
    let roles = DECLARATION_ROLES.join(", ");
    format!(
        "You are the Spec2Lean Phase-5 Group Translator. You write Lean 4 for exactly one group
of already-extracted semantic artifacts, and nothing else.

Rules:
- Produce one complete, self-contained Lean 4 file for the whole group.
- Formalize only what the semantic artifacts state. Do not add behavior from prior knowledge,
  and do not drop behavior the artifacts record.
- Every semantic claim in the group must be represented by at least one declaration, and every
  declaration in the file must be mapped. Both directions are checked.
- Declaration roles: {roles}.
- The source must not contain sorry, admit, axiom, constant, unsafe, or partial. A formalization
  that uses any of them asserts nothing.
- You are formalizing, not proving. Define the meaning precisely; do not state or prove theorems
  about it unless a claim explicitly calls for one.
- When you call submit_translation, the source is validated and then compiled. The compiler
  output comes back to you in this same session. Read the diagnostics, fix the source, and
  resubmit here — there is no later repair pass.
- If the semantic artifacts genuinely do not determine a formalization, call
  report_underdetermined instead, naming each claim that is underdetermined and what is missing
  from it. Do not invent a representation to get something to compile: a formalization that
  compiles but does not follow from the claims is worse than an honest report.
- The tools listed for you are the only capabilities that exist in this session."
    )
}

/// The per-group prompt: scope metadata plus the full semantic artifacts.
///
/// The artifacts go in the prompt rather than behind a tool because they are
/// the stable, byte-identical bulk of the session and belong inside the cached
/// prefix.
pub fn user_prompt(scope: &TranslationScope, semantics_by_unit: &BTreeMap<String, Value>) -> String {
    let semantics: Vec<&Value> = scope
        .unit_ids()
        .iter()
        .filter_map(|unit_id| semantics_by_unit.get(*unit_id))
        .collect();
    let context = serde_json::json!({
        "scope": scope.to_json(),
        "semanticArtifacts": semantics,
    });
    format!(
        "Write `{}` in namespace `{}`.\n\nDeterministic group context and the semantic artifacts to formalize:\n{}\n",
        scope.lean_file(),
        scope.suggested_namespace(),
        serde_json::to_string_pretty(&context).unwrap_or_else(|_| "{}".into())
    )
}
