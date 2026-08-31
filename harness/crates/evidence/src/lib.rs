//! Phase 3: bounded evidence retrieval for one planned unit.
//!
//! The tools run in-process. What used to be an OpenCode subprocess talking
//! stdio JSON-RPC to a Python MCP server is now a `ToolSet` the harness calls
//! directly, with the same deterministic validation and the same diagnostic
//! codes.

pub mod ledger;
pub mod model;
pub mod prompt;
pub mod render;
pub mod scope;
pub mod tools;
pub mod validation;

pub use ledger::ExposureLedger;
pub use model::{Diagnostic, DiagnosticCode, Role, Tier};
pub use scope::{EvidenceScope, ScopeError, SeedNode};
pub use tools::EvidenceTools;
pub use validation::{build_evidence_record, required_official_renditions, validate_submission};
