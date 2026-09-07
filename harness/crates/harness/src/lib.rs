//! A small, self-contained agent harness.
//!
//! Everything outside the model lives here: the provider adapters, the tool
//! registry, the bounded loop, and the transcript. Tools run in this process,
//! so the harness can also run deterministic work of its own — a compiler, a
//! validator — between turns and feed the result straight back into the same
//! conversation.
//!
//! The loop is the harness's own in every case. The `codex` provider does shell
//! out to a CLI, but only for one schema-constrained turn at a time: codex's
//! own agent loop, tools and sandbox stay unused, so the tool contract, the
//! exposure ledger and the deterministic step after each call do not change
//! when the model does. That is the line the OpenCode integration crossed —
//! it owned the loop and the artifact, leaving nothing to validate.

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
