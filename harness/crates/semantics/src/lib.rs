//! Phase 4: evidence-bounded semantic extraction for one planned unit.
//!
//! The extractor reads exactly one Phase-3 bundle and produces one structured
//! semantic artifact, or a precise insufficient-evidence failure. The central
//! discipline is the claim taxonomy: what the specification states, what was
//! derived from it, what is a later modeling need, and what is an assumption —
//! kept apart so a formalization never quietly outruns its source.

pub mod model;
pub mod prompt;
pub mod scope;
pub mod tools;
pub mod validation;

pub use model::{ClaimKind, Diagnostic, DiagnosticCode, Outcome, RestrictionKind, UnitKind};
pub use scope::{SEMANTICS_SCHEMA_VERSION, ScopeError, SemanticScope, evidence_bundle_hash};
pub use tools::{SemanticTools, semantic_evidence_view};
pub use validation::validate_submission;
