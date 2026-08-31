pub mod anthropic;
pub mod http;
pub mod openai;
pub mod recorded;

use serde::Serialize;
use serde_json::Value;

use crate::error::HarnessError;
use crate::tool::ToolSpec;
use crate::transcript::{Exchange, Usage};

/// Why the model stopped. Kept as an enum so a stop reason the harness does not
/// recognise cannot be silently treated as a normal end-of-turn.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum StopReason {
    EndTurn,
    ToolUse,
    MaxTokens,
    StopSequence,
    PauseTurn,
    Refusal,
    Other(String),
}

impl StopReason {
    pub fn parse(value: &str) -> Self {
        match value {
            "end_turn" => Self::EndTurn,
            "tool_use" | "tool_calls" => Self::ToolUse,
            "max_tokens" | "length" => Self::MaxTokens,
            "stop_sequence" | "stop" => Self::StopSequence,
            "pause_turn" => Self::PauseTurn,
            "refusal" | "content_filter" => Self::Refusal,
            other => Self::Other(other.to_string()),
        }
    }

    pub fn as_str(&self) -> &str {
        match self {
            Self::EndTurn => "end_turn",
            Self::ToolUse => "tool_use",
            Self::MaxTokens => "max_tokens",
            Self::StopSequence => "stop_sequence",
            Self::PauseTurn => "pause_turn",
            Self::Refusal => "refusal",
            Self::Other(value) => value,
        }
    }
}

/// One tool invocation requested by the model.
#[derive(Debug, Clone)]
pub struct ToolCall {
    pub id: String,
    pub name: String,
    pub input: Value,
}

/// What one provider turn produced, normalised for the loop.
#[derive(Debug, Clone)]
pub struct TurnResponse {
    /// The provider's own assistant content, preserved for verbatim replay.
    pub assistant: Value,
    pub text: String,
    pub tool_calls: Vec<ToolCall>,
    pub stop_reason: StopReason,
    pub usage: Usage,
    pub model: String,
}

/// Everything a provider needs to render one request.
pub struct Request<'a> {
    pub system: &'a str,
    pub prompt: &'a str,
    pub exchanges: &'a [Exchange],
    pub tools: &'a [ToolSpec],
}

/// The whole LLM dependency, in five lines.
///
/// Everything else in this workspace is provider-agnostic, which is what makes
/// swapping models a config change rather than a code change — the pipeline
/// this replaces hardcoded one model string in six separate files.
pub trait Provider {
    /// Stable identifier recorded in the transcript; a transcript may only be
    /// replayed into the provider that produced it.
    fn id(&self) -> &'static str;
    fn model(&self) -> &str;
    fn turn(&self, request: &Request<'_>) -> Result<TurnResponse, HarnessError>;
}

/// Reasoning effort, where the provider supports it.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Effort {
    Low,
    Medium,
    High,
    XHigh,
    Max,
}

impl Effort {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Low => "low",
            Self::Medium => "medium",
            Self::High => "high",
            Self::XHigh => "xhigh",
            Self::Max => "max",
        }
    }

    pub fn parse(value: &str) -> Option<Self> {
        match value {
            "low" => Some(Self::Low),
            "medium" => Some(Self::Medium),
            "high" => Some(Self::High),
            "xhigh" => Some(Self::XHigh),
            "max" => Some(Self::Max),
            _ => None,
        }
    }
}
