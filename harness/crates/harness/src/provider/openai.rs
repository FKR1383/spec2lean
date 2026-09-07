use std::time::Duration;

use serde_json::{Value, json};

use super::http::JsonHttp;
use super::{Provider, Request, StopReason, ToolCall, TurnResponse};
use crate::error::HarnessError;
use crate::transcript::Usage;

const DEFAULT_BASE_URL: &str = "https://api.openai.com/v1";

/// An OpenAI-compatible chat-completions adapter. Kept so the harness swap can
/// be evaluated against the model the pipeline already targets, and so any
/// compatible gateway works by setting `OPENAI_BASE_URL`.
#[derive(Debug, Clone)]
pub struct OpenAiConfig {
    pub api_key: String,
    pub base_url: String,
    pub model: String,
    pub max_tokens: Option<u32>,
    pub timeout: Duration,
}

impl OpenAiConfig {
    pub fn from_env(model: Option<String>) -> Result<Self, HarnessError> {
        let api_key = std::env::var("OPENAI_API_KEY").map_err(|_| {
            HarnessError::Config(
                "OPENAI_API_KEY is not set; export a key or select the anthropic provider".into(),
            )
        })?;
        Ok(Self {
            api_key,
            base_url: std::env::var("OPENAI_BASE_URL")
                .unwrap_or_else(|_| DEFAULT_BASE_URL.to_string()),
            model: model.ok_or_else(|| {
                HarnessError::Config("the openai provider requires an explicit --model".into())
            })?,
            max_tokens: None,
            timeout: Duration::from_secs(900),
        })
    }
}

pub struct OpenAiProvider {
    config: OpenAiConfig,
    http: JsonHttp,
}

impl OpenAiProvider {
    pub fn new(config: OpenAiConfig) -> Self {
        let http = JsonHttp::new(config.timeout);
        Self { config, http }
    }

    pub(crate) fn body(&self, request: &Request<'_>) -> Value {
        let mut messages = vec![json!({"role": "system", "content": request.system})];
        for exchange in request.exchanges {
            // Each task is stated where it was given, so a session that runs
            // several units does not attribute one unit's results to another.
            if let Some(task) = &exchange.prompt {
                messages.push(json!({"role": "user", "content": task}));
            }
            messages.push(exchange.assistant.clone());
            for record in &exchange.tool_results {
                messages.push(json!({
                    "role": "tool",
                    "tool_call_id": record.call_id,
                    "content": record.output,
                }));
            }
        }
        if request.prompt_pending {
            messages.push(json!({"role": "user", "content": request.prompt}));
        }
        let tools: Vec<Value> = request
            .tools
            .iter()
            .map(|spec| {
                json!({
                    "type": "function",
                    "function": {
                        "name": spec.name,
                        "description": spec.description,
                        "parameters": spec.input_schema,
                    },
                })
            })
            .collect();
        let mut body = json!({
            "model": self.config.model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
        });
        if let Some(limit) = self.config.max_tokens {
            body["max_completion_tokens"] = json!(limit);
        }
        body
    }

    pub(crate) fn parse(&self, response: &Value) -> Result<TurnResponse, HarnessError> {
        let choice = response
            .get("choices")
            .and_then(Value::as_array)
            .and_then(|choices| choices.first())
            .ok_or_else(|| HarnessError::Decode("response has no choices".into()))?;
        let message = choice
            .get("message")
            .cloned()
            .ok_or_else(|| HarnessError::Decode("choice has no message".into()))?;

        let stop_reason = choice
            .get("finish_reason")
            .and_then(Value::as_str)
            .map(StopReason::parse)
            .unwrap_or(StopReason::Other("missing".into()));
        if stop_reason == StopReason::Refusal {
            return Err(HarnessError::Refusal {
                category: Some("content_filter".into()),
                explanation: None,
            });
        }

        let text = message
            .get("content")
            .and_then(Value::as_str)
            .unwrap_or_default()
            .to_string();

        let mut tool_calls = Vec::new();
        for call in message
            .get("tool_calls")
            .and_then(Value::as_array)
            .map(Vec::as_slice)
            .unwrap_or_default()
        {
            let function = call
                .get("function")
                .ok_or_else(|| HarnessError::Decode("tool call has no function".into()))?;
            let arguments = function
                .get("arguments")
                .and_then(Value::as_str)
                .unwrap_or("{}");
            // Arguments arrive as a JSON *string*; never pattern-match it, parse it.
            let input = serde_json::from_str::<Value>(arguments).map_err(|error| {
                HarnessError::Decode(format!("tool call arguments are not valid JSON: {error}"))
            })?;
            tool_calls.push(ToolCall {
                id: call
                    .get("id")
                    .and_then(Value::as_str)
                    .ok_or_else(|| HarnessError::Decode("tool call has no id".into()))?
                    .to_string(),
                name: function
                    .get("name")
                    .and_then(Value::as_str)
                    .ok_or_else(|| HarnessError::Decode("tool call has no name".into()))?
                    .to_string(),
                input,
            });
        }

        // A tool-calling turn can report `stop`; normalise so the loop keys off
        // what actually happened rather than a provider quirk.
        let stop_reason = if !tool_calls.is_empty() {
            StopReason::ToolUse
        } else {
            stop_reason
        };

        Ok(TurnResponse {
            assistant: message,
            text,
            tool_calls,
            stop_reason,
            usage: usage(response.get("usage")),
            model: response
                .get("model")
                .and_then(Value::as_str)
                .unwrap_or(&self.config.model)
                .to_string(),
        })
    }
}

fn usage(value: Option<&Value>) -> Usage {
    let field = |name: &str| {
        value
            .and_then(|usage| usage.get(name))
            .and_then(Value::as_u64)
            .unwrap_or(0)
    };
    let cached = value
        .and_then(|usage| usage.get("prompt_tokens_details"))
        .and_then(|details| details.get("cached_tokens"))
        .and_then(Value::as_u64)
        .unwrap_or(0);
    Usage {
        input_tokens: field("prompt_tokens").saturating_sub(cached),
        output_tokens: field("completion_tokens"),
        cache_creation_input_tokens: 0,
        cache_read_input_tokens: cached,
    }
}

impl Provider for OpenAiProvider {
    fn id(&self) -> &'static str {
        "openai"
    }

    fn model(&self) -> &str {
        &self.config.model
    }

    fn turn(&self, request: &Request<'_>) -> Result<TurnResponse, HarnessError> {
        let url = format!(
            "{}/chat/completions",
            self.config.base_url.trim_end_matches('/')
        );
        let headers = [
            ("content-type", "application/json".to_string()),
            ("authorization", format!("Bearer {}", self.config.api_key)),
        ];
        let response = self.http.post_json(&url, &headers, &self.body(request))?;
        self.parse(&response)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::transcript::{Exchange, ToolResultRecord, Usage};

    fn provider() -> OpenAiProvider {
        OpenAiProvider::new(OpenAiConfig {
            api_key: "test".into(),
            base_url: DEFAULT_BASE_URL.into(),
            model: "gpt-test".into(),
            max_tokens: None,
            timeout: Duration::from_secs(1),
        })
    }

    #[test]
    fn tool_results_become_their_own_messages() {
        let exchanges = [Exchange {
            // The stage's first exchange carries the task it was given under.
            prompt: Some("P".to_string()),
            assistant: json!({
                "role": "assistant",
                "tool_calls": [{"id": "call_1", "type": "function",
                                "function": {"name": "spec_show", "arguments": "{}"}}],
            }),
            tool_results: vec![ToolResultRecord {
                call_id: "call_1".into(),
                name: "spec_show".into(),
                input: json!({}),
                output: "{}".into(),
                is_error: false,
            }],
            usage: Usage::default(),
        }];
        let body = provider().body(&Request {
            prompt_pending: false,
            session: 1,
            system: "S",
            prompt: "P",
            exchanges: &exchanges,
            tools: &[],
        });
        assert_eq!(body["messages"][0]["role"], json!("system"));
        assert_eq!(body["messages"][1]["role"], json!("user"));
        assert_eq!(body["messages"][1]["content"], json!("P"));
        assert_eq!(body["messages"][2], exchanges[0].assistant);
        assert_eq!(body["messages"][3]["role"], json!("tool"));
        assert_eq!(body["messages"][3]["tool_call_id"], json!("call_1"));
    }

    #[test]
    fn tool_arguments_are_parsed_never_string_matched() {
        let response = json!({
            "model": "gpt-test",
            "choices": [{
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": null,
                    "tool_calls": [{
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "spec_show",
                            // Escaped forward slashes and unicode: string
                            // matching would mangle this, parsing does not.
                            "arguments": "{\"nodeId\": \"node:a\\/b\", \"note\": \"\\u00e9\"}"
                        }
                    }]
                }
            }],
            "usage": {"prompt_tokens": 30, "completion_tokens": 4,
                      "prompt_tokens_details": {"cached_tokens": 10}},
        });
        let turn = provider().parse(&response).expect("parses");
        assert_eq!(turn.stop_reason, StopReason::ToolUse);
        assert_eq!(turn.tool_calls[0].input["nodeId"], json!("node:a/b"));
        assert_eq!(turn.tool_calls[0].input["note"], json!("é"));
        // Cached tokens are reported separately, not double counted.
        assert_eq!(turn.usage.input_tokens, 20);
        assert_eq!(turn.usage.cache_read_input_tokens, 10);
    }

    #[test]
    fn a_tool_calling_turn_reported_as_stop_is_normalised() {
        let response = json!({
            "choices": [{
                "finish_reason": "stop",
                "message": {"role": "assistant", "tool_calls": [
                    {"id": "c", "type": "function",
                     "function": {"name": "spec_show", "arguments": "{}"}}]},
            }],
        });
        assert_eq!(
            provider().parse(&response).unwrap().stop_reason,
            StopReason::ToolUse
        );
    }
}
