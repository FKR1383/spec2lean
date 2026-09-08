use serde::Serialize;
use serde_json::Value;

/// Token accounting for one provider turn.
#[derive(Debug, Clone, Copy, Default, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct Usage {
    pub input_tokens: u64,
    pub output_tokens: u64,
    pub cache_creation_input_tokens: u64,
    pub cache_read_input_tokens: u64,
}

impl Usage {
    pub fn accumulate(&mut self, other: &Usage) {
        self.input_tokens += other.input_tokens;
        self.output_tokens += other.output_tokens;
        self.cache_creation_input_tokens += other.cache_creation_input_tokens;
        self.cache_read_input_tokens += other.cache_read_input_tokens;
    }
}

/// One executed tool call and what the harness returned for it.
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ToolResultRecord {
    pub call_id: String,
    pub name: String,
    pub input: Value,
    pub output: String,
    pub is_error: bool,
}

/// One assistant turn plus the tool results the harness produced for it.
///
/// `assistant` holds the provider's own content, verbatim. Replaying it
/// unchanged is what keeps thinking blocks (and any block type added after this
/// code was written) valid on the next request. It is therefore provider-bound,
/// which `Transcript::provider` records and the session enforces.
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Exchange {
    /// The task stated immediately before this exchange, present only on the
    /// first exchange of a stage.
    ///
    /// One session runs many units, so a conversation contains several tasks.
    /// Without recording where each one was given, a provider can only render
    /// the *current* task followed by every earlier unit's work, which reads as
    /// though the earlier results were produced for the current task.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub prompt: Option<String>,
    pub assistant: Value,
    pub tool_results: Vec<ToolResultRecord>,
    /// Harness feedback delivered after this turn, separate from the provider's
    /// verbatim response and from actual tool results.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub feedback: Option<String>,
    pub usage: Usage,
}

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum SessionOutcome {
    /// The tool set reported a terminal artifact.
    Submitted,
    /// The model ended its turn without submitting.
    Stopped { stop_reason: String },
    /// The step ceiling was reached.
    StepLimit,
}

/// The complete, self-owned record of one bounded session.
///
/// The pipeline this replaces reconstructed session identity by regex-scraping
/// an agent binary's stdout for a `sessionID`. Here the transcript *is* the
/// session, and it is written as a first-class artifact.
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Transcript {
    pub schema_version: u32,
    pub provider: String,
    pub model: String,
    pub started_at: String,
    pub finished_at: String,
    pub system: String,
    pub prompt: String,
    pub tools: Vec<String>,
    pub max_steps: u32,
    pub steps: u32,
    pub exchanges: Vec<Exchange>,
    pub usage: Usage,
    pub outcome: SessionOutcome,
}
