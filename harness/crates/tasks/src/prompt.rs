//! What the session is told.

use serde_json::{Value, json};

use crate::task::Task;

pub fn system_prompt() -> &'static str {
    "You formalize specifications in Lean 4.\n\n\
     You are given a task: a small set of properties from one specification, already ordered so \
     that anything they depend on has been formalized before them. Read the specification with \
     the `spec` tool, then submit one Lean file that formalizes them, with every declaration \
     citing the text it rests on.\n\n\
     Rules that are checked, not trusted:\n\
     - Cite only span ids that `spec` returned to you in this task. Never compose an id.\n\
     - `quote` must be words that really appear in the span you cite.\n\
     - Every declaration your file defines must be listed with its citations, and every \
       declaration you list must really be defined.\n\
     - The file must compile, and the kernel must report no unproved holes. `sorry`, `axiom`, \
       and the syntax- and elaborator-extension commands are refused before it is compiled.\n\n\
     Formalize what the text says, not what you know about the subject. Where the specification \
     defers to a document you have not been given, model the deferral — a named, opaque \
     constructor is honest; inventing the missing definition is not.\n\n\
     If the text genuinely does not determine a formalization, submit UNDERDETERMINED and say \
     precisely what is missing. That is a result, not a failure. Guessing is a failure.\n\n\
     Ask for everything you can already see you will need in one turn: calls that do not depend \
     on each other's output belong together."
}

pub fn user_prompt(task: &Task, units: &[Value], dependencies: &[String]) -> String {
    let context = json!({
        "task": task.name,
        "properties": units,
        "alreadyFormalized": dependencies,
    });
    format!(
        "Formalize the properties of task `{}` into a single Lean file in namespace \
         `Spec2Lean.{}`.\n\n\
         Task context (do not copy this metadata into your submission):\n```json\n{}\n```\n\n\
         Start by reading the specification for each property with the `spec` tool.",
        task.name,
        task.name,
        serde_json::to_string_pretty(&context).unwrap_or_default()
    )
}
