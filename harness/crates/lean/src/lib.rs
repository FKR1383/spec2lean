//! Invoke the Lean toolchain and turn its output into structured diagnostics.
//!
//! Kept separate from any phase so the harness can run a build as a
//! deterministic step *inside* a translation session — the compiler result
//! becomes a tool result in the same conversation, rather than a separate phase
//! reached through a fresh process.

pub mod build;
pub mod diagnostic;
pub mod tempdir;

pub use build::{BuildResult, BuildStatus, DependencyModule, run_build};
pub use diagnostic::{Diagnostic, Severity};
