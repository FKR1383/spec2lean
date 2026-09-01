//! Phase 2: turn a bounded request into a validated, specification-supported plan.
//!
//! Everything downstream consumes this plan: which units exist, how they group
//! for translation, which concepts they share, and what depends on what. The
//! planner selects and justifies; deterministic code resolves identity,
//! validates every claim against the index, and derives the processing order.

pub mod graph;
pub mod prompt;
pub mod request;
pub mod scope;
pub mod tools;
pub mod validation;

pub use graph::{derive_processing_order, strongly_connected_components};
pub use request::{PlanningRequest, RequestError, ScopeMode, Selector};
pub use tools::PlanningTools;
pub use validation::{Diagnostic, PLAN_SCHEMA_VERSION, build_validated_plan, validate_submission};
pub use scope::{ResolvedScope, ScopeError, ScopeResolver};
