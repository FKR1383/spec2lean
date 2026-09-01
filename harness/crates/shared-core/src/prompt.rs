use serde_json::json;

use crate::requirements::SharedRequirement;

pub fn system_prompt() -> String {
    "You are the Spec2Lean Shared-Core Materializer.

Several units of this specification depend on the same concepts. You write ONE Lean 4 file that
gives each of those concepts a single representation, which every group will then import. Once it
compiles it is frozen: nothing downstream may redefine or reinterpret it.

Rules:
- Represent exactly the concepts you are given. Do not add representations nothing asked for, and
  do not omit one because it seems obvious.
- Represent only what the cited claims state. The claims are the whole specification you have for
  these concepts; anything else is invention.
- The core is shared, so keep it minimal and neutral: define the concept, not one unit's
  particular use of it.
- For every concept, register the Lean declarations that represent it. Every registered
  declaration must be defined in your source, and every declaration in your source must be mapped
  to at least one claim.
- The source must not contain sorry, admit, axiom, constant, unsafe, or partial.
- You are formalizing, not proving. Define meaning precisely; do not state theorems about it.
- On submit the source is validated and then compiled, and the results come back to you here.
  Read any diagnostics, fix the source, and resubmit in this same session.
- The tools listed for you are the only capabilities that exist in this session."
        .to_string()
}

pub fn user_prompt(requirements: &[SharedRequirement]) -> String {
    let context = json!({
        "sharedConcepts": requirements
            .iter()
            .map(SharedRequirement::brief)
            .collect::<Vec<_>>(),
    });
    format!(
        "Write one Lean 4 file representing every shared concept below.\n\nEach concept lists the \
         units that need it, what those units said it must mean, and the claims you must cite:\n{}\n",
        serde_json::to_string_pretty(&context).unwrap_or_else(|_| "{}".into())
    )
}
