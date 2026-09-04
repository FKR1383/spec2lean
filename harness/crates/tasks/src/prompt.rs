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

/// One task, stated whole.
///
/// Every earlier task has left the conversation by the time this is read, so
/// anything this task needs from one has to be here.
///
/// What is here is everything already formalized, not only what the plan
/// recorded an edge to. The plan's edges order the work; they are not an
/// access list. A task that needed something the plan did not foresee would
/// otherwise define it a second time, which is the duplication the ordering
/// exists to prevent — and a second definition of a concept is worse than a
/// redundant import.
///
/// Signatures rather than source, because a real run spent three compiles
/// discovering that reading a definition and using it across a namespace
/// boundary are different problems. `#check` answers the second question.
pub fn user_prompt(
    task: &Task,
    units: &[Value],
    available: &[(String, Vec<(String, String)>)],
) -> String {
    let context = json!({
        "task": task.name,
        "properties": units,
    });
    let mut prompt = format!(
        "Formalize the properties of task `{}` into a single Lean file in namespace \
         `Spec2Lean.{}`.\n\n\
         Task context (do not copy this metadata into your submission):\n```json\n{}\n```\n\n",
        task.name,
        task.name,
        serde_json::to_string_pretty(&context).unwrap_or_default()
    );

    if available.is_empty() {
        prompt.push_str("Nothing has been formalized yet, so define what you need.\n\n");
    } else {
        prompt.push_str(
            "These modules are already formalized and compiled, with the type of every \
             declaration as you would see it after importing. Import what you need and use \
             these declarations rather than restating them: a second definition of the same \
             concept is exactly what this ordering exists to prevent.\n\n",
        );
        for (module, declarations) in available {
            prompt.push_str(&format!("`import {module}`\n"));
            if declarations.is_empty() {
                prompt.push_str("  (no declarations reported)\n");
            }
            for (name, signature) in declarations {
                prompt.push_str(&format!("  {name} : {signature}\n"));
            }
            prompt.push('\n');
        }
    }

    prompt.push_str("Start by reading the specification for each property with the `spec` tool.");
    prompt
}
