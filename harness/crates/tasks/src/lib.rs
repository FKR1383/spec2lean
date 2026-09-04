//! A task loop.
//!
//! The phase pipeline made one model session per stage per unit: evidence,
//! then semantics, then a shared core, then translation. Every boundary between
//! them meant serialising what the model already knew into JSON and re-injecting
//! it into a fresh session, which on a two-unit run turned about 2,400 tokens of
//! real content into 54,000 tokens of request.
//!
//! Here the plan still decides what to formalize and in what order — dependency
//! order and shared concepts are its job, and it is unchanged. What follows is
//! one loop: take a task whose dependencies are done, let one session find the
//! text and write the Lean, and check it. The checks are the same ones, because
//! they were never the expensive part: the source compiles, the kernel reports
//! no unsound axiom, every citation was actually shown by a tool, and every
//! cited span still matches the index.
//!
//! Evidence is not a stage here. It is the citation on a declaration.

pub mod embedder;
pub mod prompt;
pub mod spec_tool;
pub mod task;
pub mod tools;
pub mod validation;

pub use task::{Task, tasks_from_plan};
pub use tools::TaskTools;
