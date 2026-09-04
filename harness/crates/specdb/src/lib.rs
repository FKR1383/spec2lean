//! Read-only, typed access to the Phase-1 specification index.
//!
//! Phase 1 (PDF/HTML parsing) stays in Python for now: it emits a SQLite
//! database, which is a file artifact rather than a live protocol, so consuming
//! it from Rust introduces no process boundary of the kind this rewrite exists
//! to remove.

pub mod db;
#[cfg(any(test, feature = "fixture"))]
pub mod fixture;
pub mod ids;
pub mod text;

pub use db::{EmbeddingBuild, SemanticHit, 
    CorrelationRow, DefinitionRow, MAX_NODE_TEXT_CHARS, MAX_TOOL_ROWS, NodeRow, SearchHit, SpanRow,
    SpecDb, SpecDbError, SourceType, XrefRow, truncate_chars,
};
pub use ids::{IdError, NodeId, SpanId, UnitId};
pub use text::{canonical_json, normalize_text, stable_id};
