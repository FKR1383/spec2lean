use serde::Serialize;
use serde_json::Value;

/// One tool as advertised to the model. `input_schema` is JSON Schema; the
/// adapters reshape it for their own wire format.
#[derive(Debug, Clone, Serialize)]
pub struct ToolSpec {
    pub name: String,
    pub description: String,
    pub input_schema: Value,
}

impl ToolSpec {
    pub fn new(
        name: impl Into<String>,
        description: impl Into<String>,
        input_schema: Value,
    ) -> Self {
        Self {
            name: name.into(),
            description: description.into(),
            input_schema,
        }
    }
}

/// The result of one tool call. `Err` is not a harness failure: it is handed
/// back to the model as an error tool result so it can correct itself in the
/// same session, which is exactly how the deterministic validators are meant to
/// be used.
#[derive(Debug, Clone)]
pub enum ToolOutcome {
    Ok(Value),
    Err(String),
}

impl ToolOutcome {
    pub fn is_error(&self) -> bool {
        matches!(self, Self::Err(_))
    }

    /// Wire text for a tool result block. Objects are emitted as canonical
    /// (key-sorted, separator-free) JSON so identical results are byte-identical
    /// across runs and never invalidate a cached prefix.
    pub fn to_text(&self) -> String {
        match self {
            Self::Ok(value) => serde_json::to_string(value)
                .unwrap_or_else(|error| format!("{{\"error\":\"unserializable: {error}\"}}")),
            Self::Err(message) => message.clone(),
        }
    }
}

/// The complete capability surface of one bounded session.
///
/// This is the whole security model. The model can call exactly what `specs()`
/// advertises and nothing else — there is no ambient filesystem, shell, or
/// network capability to deny, because none is ever registered. Compare the
/// OpenCode design this replaces, which had to disable fourteen built-in tools
/// and set a deny-by-default permission table to reach the same position.
pub trait ToolSet {
    fn specs(&self) -> Vec<ToolSpec>;

    /// Dispatch one call. Implementations own their own state, so calls are
    /// executed in the order the model emitted them.
    fn call(&mut self, name: &str, input: &Value) -> ToolOutcome;

    /// Has this session produced its terminal artifact? The loop stops as soon
    /// as this is true, which replaces OpenCode's "did a file appear on disk"
    /// check with something the tool set actually knows.
    fn finished(&self) -> bool {
        false
    }

    /// Deterministic work the harness runs itself after *each* tool call — a
    /// compiler, a validator, a checker. Returning `Some(text)` appends it to
    /// that call's own result, so the model sees the outcome in the same
    /// conversation rather than in a fresh process one phase later.
    ///
    /// Per call, not per batch: a model may emit several tool calls in one
    /// turn, and attaching one deterministic result to the wrong call would
    /// report a build of submission A as though it were the verdict on B.
    fn after_tool_call(&mut self) -> Option<String> {
        None
    }
}
