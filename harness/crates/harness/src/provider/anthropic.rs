use std::time::Duration;

use serde_json::{Value, json};

use super::http::JsonHttp;
use super::{Effort, Provider, Request, StopReason, ToolCall, TurnResponse};
use crate::error::HarnessError;
use crate::transcript::Usage;

pub const DEFAULT_MODEL: &str = "claude-opus-5";
const API_VERSION: &str = "2023-06-01";
const DEFAULT_BASE_URL: &str = "https://api.anthropic.com";

#[derive(Debug, Clone)]
pub struct AnthropicConfig {
    pub api_key: String,
    pub base_url: String,
    pub model: String,
    pub max_tokens: u32,
    pub effort: Option<Effort>,
    /// Ask the API to guarantee tool inputs validate against the declared
    /// schema. Off by default only because it is unverified against the live
    /// endpoint from this workspace; the typed deserialisation in each tool set
    /// is the primary guarantee either way.
    pub strict_tools: bool,
    pub timeout: Duration,
}

impl AnthropicConfig {
    /// Read credentials from the environment. `ANTHROPIC_API_KEY` is required;
    /// `ANTHROPIC_BASE_URL` overrides the endpoint for proxies and gateways.
    pub fn from_env(model: Option<String>) -> Result<Self, HarnessError> {
        let api_key = std::env::var("ANTHROPIC_API_KEY").map_err(|_| {
            HarnessError::Config(
                "ANTHROPIC_API_KEY is not set; export a key or select the openai provider".into(),
            )
        })?;
        Ok(Self {
            api_key,
            base_url: std::env::var("ANTHROPIC_BASE_URL")
                .unwrap_or_else(|_| DEFAULT_BASE_URL.to_string()),
            model: model.unwrap_or_else(|| DEFAULT_MODEL.to_string()),
            max_tokens: 16_000,
            effort: Some(Effort::High),
            strict_tools: false,
            timeout: Duration::from_secs(900),
        })
    }
}

pub struct AnthropicProvider {
    config: AnthropicConfig,
    http: JsonHttp,
}

impl AnthropicProvider {
    pub fn new(config: AnthropicConfig) -> Self {
        let http = JsonHttp::new(config.timeout);
        Self { config, http }
    }

    /// Build the request body.
    ///
    /// Cache placement matters more here than anywhere else in the pipeline.
    /// Render order is tools → system → messages, so the stable prefix of a
    /// unit session is [tools, system, the opening prompt] — and that opening
    /// prompt carries the seed nodes' exact specification text, which is the
    /// bulk of the tokens and is byte-identical across every step of the
    /// session. Two breakpoints (end of system, end of the opening prompt)
    /// therefore cover the whole expensive prefix; the tool results that grow
    /// turn by turn all land after them.
    pub(crate) fn body(&self, request: &Request<'_>) -> Value {
        let mut messages = vec![json!({
            "role": "user",
            "content": [{
                "type": "text",
                "text": request.prompt,
                "cache_control": {"type": "ephemeral"},
            }],
        })];
        for exchange in request.exchanges {
            messages.push(json!({"role": "assistant", "content": exchange.assistant}));
            let results: Vec<Value> = exchange
                .tool_results
                .iter()
                .map(|record| {
                    json!({
                        "type": "tool_result",
                        "tool_use_id": record.call_id,
                        "content": record.output,
                        "is_error": record.is_error,
                    })
                })
                .collect();
            messages.push(json!({"role": "user", "content": results}));
        }

        let tools: Vec<Value> = request
            .tools
            .iter()
            .map(|spec| {
                let mut tool = json!({
                    "name": spec.name,
                    "description": spec.description,
                    "input_schema": spec.input_schema,
                });
                if self.config.strict_tools {
                    tool["strict"] = Value::Bool(true);
                }
                tool
            })
            .collect();

        let mut body = json!({
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "system": [{
                "type": "text",
                "text": request.system,
                "cache_control": {"type": "ephemeral"},
            }],
            "messages": messages,
            "tools": tools,
            "thinking": {"type": "adaptive"},
        });
        if let Some(effort) = self.config.effort {
            body["output_config"] = json!({"effort": effort.as_str()});
        }
        body
    }

    pub(crate) fn parse(&self, response: &Value) -> Result<TurnResponse, HarnessError> {
        let content = response
            .get("content")
            .cloned()
            .ok_or_else(|| HarnessError::Decode("response has no content array".into()))?;
        let blocks = content
            .as_array()
            .ok_or_else(|| HarnessError::Decode("content is not an array".into()))?;

        let stop_reason = response
            .get("stop_reason")
            .and_then(Value::as_str)
            .map(StopReason::parse)
            .unwrap_or(StopReason::Other("missing".into()));

        // Guard before reading content: a declined turn is HTTP 200.
        if stop_reason == StopReason::Refusal {
            let details = response.get("stop_details");
            return Err(HarnessError::Refusal {
                category: details
                    .and_then(|value| value.get("category"))
                    .and_then(Value::as_str)
                    .map(str::to_string),
                explanation: details
                    .and_then(|value| value.get("explanation"))
                    .and_then(Value::as_str)
                    .map(str::to_string),
            });
        }

        let mut text = String::new();
        let mut tool_calls = Vec::new();
        for block in blocks {
            match block.get("type").and_then(Value::as_str) {
                Some("text") => {
                    if let Some(value) = block.get("text").and_then(Value::as_str) {
                        text.push_str(value);
                    }
                }
                Some("tool_use") => tool_calls.push(ToolCall {
                    id: block
                        .get("id")
                        .and_then(Value::as_str)
                        .ok_or_else(|| HarnessError::Decode("tool_use block has no id".into()))?
                        .to_string(),
                    name: block
                        .get("name")
                        .and_then(Value::as_str)
                        .ok_or_else(|| HarnessError::Decode("tool_use block has no name".into()))?
                        .to_string(),
                    input: block.get("input").cloned().unwrap_or_else(|| json!({})),
                }),
                _ => {}
            }
        }

        Ok(TurnResponse {
            assistant: content,
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
    Usage {
        input_tokens: field("input_tokens"),
        output_tokens: field("output_tokens"),
        cache_creation_input_tokens: field("cache_creation_input_tokens"),
        cache_read_input_tokens: field("cache_read_input_tokens"),
    }
}

impl Provider for AnthropicProvider {
    fn id(&self) -> &'static str {
        "anthropic"
    }

    fn model(&self) -> &str {
        &self.config.model
    }

    fn turn(&self, request: &Request<'_>) -> Result<TurnResponse, HarnessError> {
        let url = format!("{}/v1/messages", self.config.base_url.trim_end_matches('/'));
        let headers = [
            ("content-type", "application/json".to_string()),
            ("x-api-key", self.config.api_key.clone()),
            ("anthropic-version", API_VERSION.to_string()),
        ];
        let response = self.http.post_json(&url, &headers, &self.body(request))?;
        self.parse(&response)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::tool::ToolSpec;
    use crate::transcript::{Exchange, ToolResultRecord, Usage};

    fn provider() -> AnthropicProvider {
        AnthropicProvider::new(AnthropicConfig {
            api_key: "test".into(),
            base_url: DEFAULT_BASE_URL.into(),
            model: DEFAULT_MODEL.into(),
            max_tokens: 16_000,
            effort: Some(Effort::High),
            strict_tools: false,
            timeout: Duration::from_secs(1),
        })
    }

    fn exchange() -> Exchange {
        Exchange {
            assistant: json!([
                {"type": "thinking", "thinking": "", "signature": "sig"},
                {"type": "tool_use", "id": "toolu_1", "name": "spec_show", "input": {"nodeId": "node:1"}}
            ]),
            tool_results: vec![ToolResultRecord {
                call_id: "toolu_1".into(),
                name: "spec_show".into(),
                input: json!({"nodeId": "node:1"}),
                output: "{\"ok\":true}".into(),
                is_error: false,
            }],
            usage: Usage::default(),
        }
    }

    #[test]
    fn caches_the_stable_prefix_at_exactly_two_breakpoints() {
        let tools = [ToolSpec::new("spec_show", "show", json!({"type": "object"}))];
        let exchanges = [exchange()];
        let body = provider().body(&Request {
            system: "SYSTEM",
            prompt: "PROMPT",
            exchanges: &exchanges,
            tools: &tools,
        });

        // End of system, and end of the opening prompt — the whole expensive,
        // unchanging prefix. Everything that grows turn by turn sits after them.
        assert_eq!(
            body["system"][0]["cache_control"],
            json!({"type": "ephemeral"})
        );
        assert_eq!(
            body["messages"][0]["content"][0]["cache_control"],
            json!({"type": "ephemeral"})
        );
        let breakpoints = serde_json::to_string(&body)
            .unwrap()
            .matches("cache_control")
            .count();
        assert_eq!(breakpoints, 2, "at most four are allowed; two is what we need");
    }

    #[test]
    fn replays_assistant_content_verbatim() {
        let exchanges = [exchange()];
        let body = provider().body(&Request {
            system: "SYSTEM",
            prompt: "PROMPT",
            exchanges: &exchanges,
            tools: &[],
        });
        // The thinking block survives untouched — required for a valid
        // continuation, and impossible if we rebuilt content from parsed parts.
        assert_eq!(body["messages"][1]["role"], json!("assistant"));
        assert_eq!(body["messages"][1]["content"], exchanges[0].assistant);
        assert_eq!(
            body["messages"][2]["content"][0],
            json!({
                "type": "tool_result",
                "tool_use_id": "toolu_1",
                "content": "{\"ok\":true}",
                "is_error": false,
            })
        );
    }

    #[test]
    fn sends_adaptive_thinking_and_effort_but_never_a_token_budget() {
        let body = provider().body(&Request {
            system: "S",
            prompt: "P",
            exchanges: &[],
            tools: &[],
        });
        assert_eq!(body["thinking"], json!({"type": "adaptive"}));
        assert_eq!(body["output_config"]["effort"], json!("high"));
        assert!(body["thinking"].get("budget_tokens").is_none());
        assert_eq!(body["model"], json!("claude-opus-5"));
    }

    #[test]
    fn extracts_tool_calls_text_and_usage() {
        let response = json!({
            "model": "claude-opus-5",
            "stop_reason": "tool_use",
            "content": [
                {"type": "text", "text": "Reading the syntax block."},
                {"type": "tool_use", "id": "toolu_9", "name": "spec_show",
                 "input": {"nodeId": "node:html-syntax"}}
            ],
            "usage": {"input_tokens": 5, "output_tokens": 7,
                      "cache_creation_input_tokens": 11, "cache_read_input_tokens": 13},
        });
        let turn = provider().parse(&response).expect("parses");
        assert_eq!(turn.stop_reason, StopReason::ToolUse);
        assert_eq!(turn.text, "Reading the syntax block.");
        assert_eq!(turn.tool_calls.len(), 1);
        assert_eq!(turn.tool_calls[0].name, "spec_show");
        assert_eq!(turn.tool_calls[0].input["nodeId"], json!("node:html-syntax"));
        assert_eq!(turn.usage.cache_read_input_tokens, 13);
        assert_eq!(turn.usage.cache_creation_input_tokens, 11);
    }

    #[test]
    fn a_refusal_is_an_error_not_an_empty_turn() {
        // HTTP 200 with stop_reason refusal: reading `content` first would
        // silently produce a turn with no tool calls and end the session.
        let response = json!({
            "stop_reason": "refusal",
            "content": [],
            "stop_details": {"type": "refusal", "category": "cyber", "explanation": "no"},
        });
        match provider().parse(&response) {
            Err(HarnessError::Refusal { category, .. }) => {
                assert_eq!(category.as_deref(), Some("cyber"));
            }
            other => panic!("expected a refusal, got {other:?}"),
        }
    }
}
