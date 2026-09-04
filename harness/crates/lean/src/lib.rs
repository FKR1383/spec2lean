//! Invoke the Lean toolchain and turn its output into structured diagnostics.
//!
//! Kept separate from any phase so the harness can run a build as a
//! deterministic step *inside* a translation session — the compiler result
//! becomes a tool result in the same conversation, rather than a separate phase
//! reached through a fresh process.

pub mod axioms;
pub mod build;
pub mod diagnostic;
pub mod signatures;
pub mod tempdir;

pub use axioms::{AxiomAudit, DeclarationAxioms, audit};
pub use build::{BuildResult, BuildStatus, DependencyModule, run_build};
pub use signatures::signatures;
pub use diagnostic::{Diagnostic, Severity};

/// Every declaration a Lean source defines, fully qualified.
///
/// The signature probe needs names before anything has been elaborated, and it
/// cannot reach for the translation crate's scanner without inverting the
/// dependency between them. This is deliberately the crude version: a name it
/// misses costs a missing signature, never a wrong one.
pub fn declaration_names(source: &str) -> Vec<String> {
    const KINDS: &[&str] = &[
        "def", "abbrev", "theorem", "structure", "inductive", "instance", "class",
    ];
    let mut namespaces: Vec<String> = Vec::new();
    let mut found = Vec::new();
    for line in source.lines() {
        let mut words = line.split_whitespace();
        match words.next() {
            Some("namespace") => {
                if let Some(name) = words.next() {
                    namespaces.push(name.to_string());
                }
            }
            Some("end") => {
                // `end` without a name closes a section, which owns no names.
                if words.next().is_some() {
                    namespaces.pop();
                }
            }
            Some(word) if KINDS.contains(&word) => {
                if let Some(name) = words.next() {
                    let name = name.trim_end_matches([':', '(', '{', '['].as_ref());
                    if !name.is_empty() && !name.starts_with('_') {
                        let mut path = namespaces.clone();
                        path.push(name.to_string());
                        found.push(path.join("."));
                    }
                }
            }
            _ => {}
        }
    }
    found
}
