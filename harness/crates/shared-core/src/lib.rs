//! The frozen shared core.
//!
//! When several units depend on the same concept — a reset event, a register
//! layout, a predicate — each group translating that concept independently
//! would produce Lean that only accidentally agrees. The core gives the concept
//! one representation, generated once, compiled once, then frozen: later groups
//! import it and must use the declarations it registered.

pub mod identity;
pub mod prompt;
pub mod requirements;
pub mod tools;
pub mod validation;

pub use identity::{core_namespace, core_run_id, json_hash, text_hash};
pub use tools::{FrozenCore, SharedCoreTools};
pub use requirements::{
    MissingSharedAbstraction, RequirementError, SharedRequirement, collect_shared_requirements,
    relevant_dependency_ids,
};
