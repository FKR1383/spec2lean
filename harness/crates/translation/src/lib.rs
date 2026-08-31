//! Phase 5: translate one group of semantic artifacts into Lean 4.
//!
//! The difference from the pipeline this replaces is where the compiler sits.
//! Previously a translator process emitted Lean, exited, and a separate Phase 6
//! compiled it; a build failure then went to Phase 7, which started a *fresh*
//! session with a repair prompt and no memory of why the code was written that
//! way. Here the harness runs `lean` itself after each submission and hands the
//! diagnostics back as a tool result in the same conversation.

pub mod prompt;
pub mod scope;
pub mod source;
pub mod tools;
pub mod validation;

pub use scope::{ScopeError, TRANSLATION_SCHEMA_VERSION, TranslationScope, grouped_units};
pub use tools::TranslationTools;
pub use validation::{DECLARATION_ROLES, Diagnostic, validate_submission};
