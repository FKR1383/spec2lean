use std::time::Duration;

use serde_json::{Value, json};

use super::http::JsonHttp;
use super::{Effort, Provider, Request, StopReason, ToolCall, TurnResponse};
use crate::error::HarnessError;
use crate::transcript::Usage;

pub const DEFAULT_MODEL: &str = "claude-opus-5";
const API_VERSION: &str = "2023-06-01";
const DEFAULT_BASE_URL: &str = "https://api.anthropic.com";

/// How this client authenticates.
///
/// An API key and an OAuth token are sent differently, and mixing them up
/// yields a 401 that says nothing useful. The distinction is a type so it
/// cannot be got wrong at the call site.
#[derive(Debug, Clone)]
pub enum Credential {
    /// A `sk-ant-api…` key, sent as `x-api-key`.
    ApiKey(String),
    /// An OAuth access token, sent as `Authorization: Bearer` with the beta
    /// header that opts into OAuth on the Messages API. This is what a
    /// `claude` or `ant auth login` session already has, so a machine that can
    /// run Claude Code needs no second credential.
    OAuth(String),
}

impl Credential {
    fn headers(&self) -> Vec<(&'static str, String)> {
        match self {
            Self::ApiKey(key) => vec![("x-api-key", key.clone())],
            Self::OAuth(token) => vec![
                ("authorization", format!("Bearer {token}")),
                ("anthropic-beta", "oauth-2025-04-20".to_string()),
            ],
        }
    }
}

#[derive(Debug, Clone)]
pub struct AnthropicConfig {
    pub credential: Credential,
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
    /// Read credentials from the environment, in the order the SDKs use:
    /// `ANTHROPIC_API_KEY`, then `ANTHROPIC_AUTH_TOKEN`. `ANTHROPIC_BASE_URL`
    /// overrides the endpoint for proxies and gateways.
    pub fn from_env(model: Option<String>) -> Result<Self, HarnessError> {
        let credential = match std::env::var("ANTHROPIC_API_KEY") {
            Ok(key) if !key.is_empty() => Credential::ApiKey(key),
            _ => match std::env::var("ANTHROPIC_AUTH_TOKEN") {
                Ok(token) if !token.is_empty() => Credential::OAuth(token),
                _ => {
                    return Err(HarnessError::Config(
                        "no Anthropic credential: set ANTHROPIC_API_KEY, or set \
                         ANTHROPIC_AUTH_TOKEN to an OAuth access token, or select the openai \
                         provider"
                            .into(),
                    ));
                }
            },
        };
        Ok(Self {
            credential,
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
    /// Render order is tools → system → messages, and the API allows four
    /// breakpoints. They are spent as follows:
    ///
    /// 1. End of the system prompt — identical for every unit of every run.
    /// 2. End of the opening prompt — the per-unit boundary and, in Phase 3,
    ///    the seed nodes' exact specification text. Byte-identical across every
    ///    step of the session.
    /// 3. End of the first exchange's tool results. Phases that hand the model
    ///    a large immutable payload through a tool rather than the prompt (Phase
    ///    4 reads its whole evidence bundle through `get_evidence`) would
    ///    otherwise re-send it uncached on every subsequent step. It is stable
    ///    for the rest of the session, so it caches perfectly.
    /// 4. A rolling breakpoint at the previous exchange, so history accumulated
    ///    since is written once and read back on every later step.
    fn cache_control() -> Value {
        json!({"type": "ephemeral"})
    }

    pub(crate) fn body(&self, request: &Request<'_>) -> Value {
        let mut messages: Vec<Value> = Vec::new();
        let mut opened = false;

        let count = request.exchanges.len();
        // The rolling breakpoint trails by one exchange so it never lands on
        // content that is still being appended to this turn.
        let rolling = count.checked_sub(2);
        for (index, exchange) in request.exchanges.iter().enumerate() {
            // A task is stated where it was given. One session runs many units,
            // so putting the current task first and every unit's work after it
            // would say that the earlier results answered the later question.
            if let Some(task) = &exchange.prompt {
                let mut content = json!({"type": "text", "text": task});
                if !opened {
                    content["cache_control"] = Self::cache_control();
                    opened = true;
                }
                messages.push(json!({"role": "user", "content": [content]}));
            }
            messages.push(json!({"role": "assistant", "content": exchange.assistant}));
            let mut results: Vec<Value> = exchange
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
            let breakpoint = index == 0 || Some(index) == rolling;
            if breakpoint && let Some(last) = results.last_mut() {
                last["cache_control"] = Self::cache_control();
            }
            messages.push(json!({"role": "user", "content": results}));
        }

        // A stage whose first exchange does not exist yet still has to state
        // its task, and it belongs last: it is the newest thing said.
        if request.prompt_pending {
            let mut content = json!({"type": "text", "text": request.prompt});
            if !opened {
                content["cache_control"] = Self::cache_control();
            }
            messages.push(json!({"role": "user", "content": [content]}));
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
                "cache_control": Self::cache_control(),
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
        let mut headers = vec![
            ("content-type", "application/json".to_string()),
            ("anthropic-version", API_VERSION.to_string()),
        ];
        headers.extend(self.config.credential.headers());
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
            credential: Credential::ApiKey("test".into()),
            base_url: DEFAULT_BASE_URL.into(),
            model: DEFAULT_MODEL.into(),
            max_tokens: 16_000,
            effort: Some(Effort::High),
            strict_tools: false,
            timeout: Duration::from_secs(1),
        })
    }

    fn exchange() -> Exchange {
        exchange_for(None)
    }

    /// The first exchange of a stage carries the task it was given under.
    fn opening_exchange() -> Exchange {
        exchange_for(Some("PROMPT".to_string()))
    }

    fn exchange_for(prompt: Option<String>) -> Exchange {
        Exchange {
            prompt,
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

    fn breakpoints(body: &Value) -> usize {
        serde_json::to_string(body)
            .unwrap()
            .matches("cache_control")
            .count()
    }

    #[test]
    fn caches_the_stable_prefix() {
        let tools = [ToolSpec::new(
            "spec_show",
            "show",
            json!({"type": "object"}),
        )];
        let exchanges = [opening_exchange()];
        let body = provider().body(&Request {
            prompt_pending: false,
            session: 1,
            system: "SYSTEM",
            prompt: "PROMPT",
            exchanges: &exchanges,
            tools: &tools,
        });

        // End of system and end of the opening prompt: the whole per-session
        // prefix, unchanged from the first step to the last.
        assert_eq!(
            body["system"][0]["cache_control"],
            json!({"type": "ephemeral"})
        );
        assert_eq!(
            body["messages"][0]["content"][0]["cache_control"],
            json!({"type": "ephemeral"})
        );
        // Plus the first exchange's tool results, which is where a phase that
        // ships a large immutable payload through a tool puts it.
        assert_eq!(
            body["messages"][2]["content"][0]["cache_control"],
            json!({"type": "ephemeral"})
        );
        assert_eq!(breakpoints(&body), 3);
    }

    #[test]
    fn the_rolling_breakpoint_trails_by_one_and_stays_within_the_limit() {
        let mut exchanges: Vec<Exchange> = (0..6).map(|_| exchange()).collect();
        exchanges[0].prompt = Some("P".to_string());
        for count in 0..=exchanges.len() {
            let body = provider().body(&Request {
                prompt_pending: count == 0,
                session: 1,
                system: "S",
                prompt: "P",
                exchanges: &exchanges[..count],
                tools: &[],
            });
            assert!(
                breakpoints(&body) <= 4,
                "{count} exchanges produced {} breakpoints; the API allows four",
                breakpoints(&body)
            );
        }

        // With six exchanges: system, prompt, exchange 0, and exchange 4 —
        // never the exchange being appended to this turn.
        let body = provider().body(&Request {
            prompt_pending: false,
            session: 1,
            system: "S",
            prompt: "P",
            exchanges: &exchanges,
            tools: &[],
        });
        assert_eq!(breakpoints(&body), 4);
        let marked: Vec<usize> = (0..exchanges.len())
            .filter(|index| {
                !body["messages"][2 + index * 2]["content"][0]["cache_control"].is_null()
            })
            .collect();
        assert_eq!(marked, vec![0, 4]);
    }

    #[test]
    fn replays_assistant_content_verbatim() {
        let exchanges = [opening_exchange()];
        let body = provider().body(&Request {
            prompt_pending: false,
            session: 1,
            system: "SYSTEM",
            prompt: "PROMPT",
            exchanges: &exchanges,
            tools: &[],
        });
        // The thinking block survives untouched — required for a valid
        // continuation, and impossible if we rebuilt content from parsed parts.
        assert_eq!(body["messages"][1]["role"], json!("assistant"));
        assert_eq!(body["messages"][1]["content"], exchanges[0].assistant);
        let result = &body["messages"][2]["content"][0];
        assert_eq!(result["type"], json!("tool_result"));
        assert_eq!(result["tool_use_id"], json!("toolu_1"));
        assert_eq!(result["content"], json!("{\"ok\":true}"));
        assert_eq!(result["is_error"], json!(false));
    }

    #[test]
    fn sends_adaptive_thinking_and_effort_but_never_a_token_budget() {
        let body = provider().body(&Request {
            prompt_pending: true,
            session: 1,
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
        assert_eq!(
            turn.tool_calls[0].input["nodeId"],
            json!("node:html-syntax")
        );
        assert_eq!(turn.usage.cache_read_input_tokens, 13);
        assert_eq!(turn.usage.cache_creation_input_tokens, 11);
    }

    #[test]
    fn each_credential_kind_is_sent_the_way_the_api_expects() {
        let key = Credential::ApiKey("sk-ant-api-x".into()).headers();
        assert_eq!(key, vec![("x-api-key", "sk-ant-api-x".to_string())]);

        // An OAuth token goes on Authorization, and needs the beta that opts
        // the Messages API into accepting one at all.
        let oauth = Credential::OAuth("sk-ant-oat01-x".into()).headers();
        assert_eq!(
            oauth,
            vec![
                ("authorization", "Bearer sk-ant-oat01-x".to_string()),
                ("anthropic-beta", "oauth-2025-04-20".to_string()),
            ]
        );
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

    /// One session runs many units, so the conversation contains many tasks.
    /// Rendering only the current task, ahead of every unit's work, tells the
    /// model that the earlier results were produced for the current question.
    #[test]
    fn each_stages_task_is_rendered_where_it_was_given() {
        let exchanges = [
            exchange_for(Some("TASK A".into())),
            exchange_for(None),
            exchange_for(Some("TASK B".into())),
        ];
        let body = provider().body(&Request {
            prompt_pending: false,
            session: 1,
            system: "S",
            prompt: "TASK B",
            exchanges: &exchanges,
            tools: &[],
        });
        let messages = body["messages"].as_array().unwrap();
        let text_of = |m: &Value| m["content"][0]["text"].as_str().unwrap_or("").to_string();
        let users: Vec<String> = messages
            .iter()
            .filter(|m| m["role"] == "user")
            .map(text_of)
            .filter(|t| !t.is_empty())
            .collect();
        assert_eq!(users, vec!["TASK A".to_string(), "TASK B".to_string()]);

        // And TASK B is stated after unit A's work, not before it.
        let a = messages
            .iter()
            .position(|m| text_of(m) == "TASK A")
            .unwrap();
        let b = messages
            .iter()
            .position(|m| text_of(m) == "TASK B")
            .unwrap();
        assert!(a < b, "task A was given first and must be rendered first");
        assert_eq!(
            b, 5,
            "task B belongs after A's two exchanges, not at the top"
        );
    }

    #[test]
    fn a_stage_that_has_produced_nothing_yet_states_its_task_last() {
        let exchanges = [exchange_for(Some("TASK A".into()))];
        let body = provider().body(&Request {
            prompt_pending: true,
            session: 1,
            system: "S",
            prompt: "TASK B",
            exchanges: &exchanges,
            tools: &[],
        });
        let messages = body["messages"].as_array().unwrap();
        let last = messages.last().unwrap();
        assert_eq!(last["role"], json!("user"));
        assert_eq!(last["content"][0]["text"], json!("TASK B"));
    }
}
