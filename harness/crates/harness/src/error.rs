use std::fmt;

/// Every way a bounded session can fail. Deliberately exhaustive: the caller
/// decides what is retryable, and `Display` is what lands in a run manifest.
#[derive(Debug)]
pub enum HarnessError {
    /// Missing credentials, unusable base URL, contradictory settings.
    Config(String),
    /// The request never reached the provider, or the connection died.
    Transport(String),
    /// The provider answered with a non-2xx status after retries were exhausted.
    Status { code: u16, body: String },
    /// The provider answered 2xx with a body this adapter cannot interpret.
    Decode(String),
    /// A safety classifier declined the request (HTTP 200, `stop_reason: refusal`).
    Refusal {
        category: Option<String>,
        explanation: Option<String>,
    },
    /// The loop hit its step ceiling before the tool set reported completion.
    StepLimit { steps: u32 },
    /// The model stopped on its own before the tool set reported completion.
    Incomplete { stop_reason: String, steps: u32 },
    /// A transcript recorded against one provider was replayed into another.
    ProviderMismatch {
        expected: &'static str,
        found: String,
    },
}

impl fmt::Display for HarnessError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Config(detail) => write!(f, "harness configuration error: {detail}"),
            Self::Transport(detail) => write!(f, "provider transport error: {detail}"),
            Self::Status { code, body } => {
                write!(f, "provider returned HTTP {code}: {}", truncate(body, 800))
            }
            Self::Decode(detail) => write!(f, "could not decode the provider response: {detail}"),
            Self::Refusal {
                category,
                explanation,
            } => write!(
                f,
                "provider declined the request (category: {}, explanation: {})",
                category.as_deref().unwrap_or("<none>"),
                explanation.as_deref().unwrap_or("<none>")
            ),
            Self::StepLimit { steps } => write!(
                f,
                "session reached its {steps}-step ceiling without producing a submission"
            ),
            Self::Incomplete { stop_reason, steps } => write!(
                f,
                "session stopped after {steps} steps with stop_reason={stop_reason} and no submission"
            ),
            Self::ProviderMismatch { expected, found } => write!(
                f,
                "transcript belongs to provider {found}, but this session uses {expected}"
            ),
        }
    }
}

impl std::error::Error for HarnessError {}

pub(crate) fn truncate(value: &str, limit: usize) -> String {
    if value.chars().count() <= limit {
        return value.to_string();
    }
    let head: String = value.chars().take(limit).collect();
    format!("{head}… <{} chars total>", value.chars().count())
}
