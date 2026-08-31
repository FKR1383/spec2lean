//! A small, self-contained agent harness.
//!
//! Everything outside the model lives here: the provider adapters, the tool
//! registry, the bounded loop, and the transcript. Tools run in this process,
//! so the harness can also run deterministic work of its own — a compiler, a
//! validator — between turns and feed the result straight back into the same
//! conversation.
//!
//! There is no external agent binary, no subprocess, no stdio protocol, and no
//! ambient capability to disable.

pub mod clock;
pub mod error;
pub mod provider;
pub mod session;
pub mod tool;
pub mod transcript;

pub use error::HarnessError;
pub use provider::{Effort, Provider, Request, StopReason, ToolCall, TurnResponse};
pub use session::Session;
pub use tool::{ToolOutcome, ToolSet, ToolSpec};
pub use transcript::{Exchange, SessionOutcome, ToolResultRecord, Transcript, Usage};
