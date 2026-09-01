//! A provider backed by the `codex` CLI.
//!
//! Codex is an agent, not a completion endpoint, so this adapter uses only the
//! part of it that is one: a single non-interactive turn whose reply is
//! constrained to a JSON schema. Codex's own loop, sandbox and tools are
//! deliberately unused — the harness keeps its loop, so the exposure ledger,
//! the submission gates and the deterministic step after each tool call behave
//! exactly as they do on an HTTP provider. Swapping the model must not swap the
//! discipline.
//!
//! The cost of that choice is the whole conversation on every turn: `codex
//! exec` is stateless here by construction, because a provider that remembered
//! its own history could disagree with the transcript the harness is building.

use std::io::{Read, Write};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicU64, Ordering};

use serde_json::{Value, json};

use crate::error::HarnessError;
use crate::provider::{Provider, Request, StopReason, ToolCall, TurnResponse};
use crate::tool::ToolSpec;
use crate::transcript::Usage;

/// How much of the filesystem codex may touch. The harness runs every tool
/// itself, so the adapter has no reason to grant more than the weakest policy;
/// it is configurable only because a caller may already be inside a sandbox.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Sandbox {
    ReadOnly,
    WorkspaceWrite,
}

impl Sandbox {
    fn as_str(self) -> &'static str {
        match self {
            Self::ReadOnly => "read-only",
            Self::WorkspaceWrite => "workspace-write",
        }
    }
}

#[derive(Debug, Clone)]
pub struct CodexConfig {
    pub executable: String,
    /// `None` means "whatever the user's codex config selects". The transcript
    /// then records `codex:config-default` rather than inventing a model id.
    pub model: Option<String>,
    pub sandbox: Sandbox,
    pub timeout_seconds: u64,
}

impl Default for CodexConfig {
    fn default() -> Self {
        Self {
            executable: "codex".to_string(),
            model: None,
            sandbox: Sandbox::ReadOnly,
            timeout_seconds: 900,
        }
    }
}

pub struct CodexProvider {
    config: CodexConfig,
    model: String,
}

impl CodexProvider {
    pub fn new(config: CodexConfig) -> Self {
        let model = match &config.model {
            Some(name) => format!("codex:{name}"),
            None => "codex:config-default".to_string(),
        };
        Self { config, model }
    }

    /// The reply shape. `arguments_json` is a *string* holding JSON rather than
    /// a nested object: structured-output modes require every object to close
    /// itself with `additionalProperties: false`, which no schema for
    /// "arbitrary tool input" can satisfy. Parsing one extra layer here is the
    /// price of keeping the constraint enforceable.
    fn reply_schema() -> Value {
        json!({
            "type": "object",
            "additionalProperties": false,
            "required": ["reply", "tool_calls"],
            "properties": {
                "reply": {
                    "type": "string",
                    "description": "Prose for the transcript. Empty when you are only calling tools."
                },
                "tool_calls": {
                    "type": "array",
                    "description": "The tools to run next. Empty ends the turn.",
                    "items": {
                        "type": "object",
                        "additionalProperties": false,
                        "required": ["name", "arguments_json"],
                        "properties": {
                            "name": {"type": "string"},
                            "arguments_json": {
                                "type": "string",
                                "description": "The tool's arguments, as a JSON object encoded in a string."
                            }
                        }
                    }
                }
            }
        })
    }

    fn render_tools(tools: &[ToolSpec]) -> String {
        let mut rendered = String::from("# Tools\n\nYou may call only these:\n\n");
        for tool in tools {
            rendered.push_str(&format!(
                "## {}\n{}\n\nInput schema:\n```json\n{}\n```\n\n",
                tool.name,
                tool.description,
                serde_json::to_string_pretty(&tool.input_schema).unwrap_or_default()
            ));
        }
        rendered
    }

    /// The conversation, flattened. The harness owns the history, so it is
    /// re-sent whole every turn; codex is asked to act, never to remember.
    fn render_prompt(request: &Request<'_>) -> String {
        let mut prompt = String::new();
        prompt.push_str(
            "You are driving a tool-using task through a harness that executes every tool for \
             you. Do not use your own shell, file or search tools: they cannot see this task's \
             data, and anything they return is noise. Your entire output is the JSON reply the \
             schema describes.\n\n",
        );
        prompt.push_str("# Instructions\n\n");
        prompt.push_str(request.system);
        prompt.push_str("\n\n");
        prompt.push_str(&Self::render_tools(request.tools));
        prompt.push_str("# Task\n\n");
        prompt.push_str(request.prompt);
        prompt.push_str("\n\n# Transcript so far\n\n");

        if request.exchanges.is_empty() {
            prompt.push_str("(nothing yet — this is the first turn)\n");
        }
        for (index, exchange) in request.exchanges.iter().enumerate() {
            prompt.push_str(&format!("## Turn {}\n\nYou replied:\n", index + 1));
            let reply = exchange.assistant["reply"].as_str().unwrap_or("");
            if reply.is_empty() {
                prompt.push_str("(no prose)\n");
            } else {
                prompt.push_str(reply);
                prompt.push('\n');
            }
            for result in &exchange.tool_results {
                prompt.push_str(&format!(
                    "\nYou called `{}` with:\n```json\n{}\n```\nThe harness answered{}:\n```\n{}\n```\n",
                    result.name,
                    serde_json::to_string(&result.input).unwrap_or_default(),
                    if result.is_error { " with an error" } else { "" },
                    result.output
                ));
            }
            prompt.push('\n');
        }

        prompt.push_str(
            "# Now\n\nDecide the next step and answer with the JSON reply. Call tools when you \
             need them; return an empty `tool_calls` only when you genuinely cannot continue, \
             and then say why in `reply`.\n",
        );
        prompt
    }

    fn scratch(&self) -> Result<PathBuf, HarnessError> {
        static COUNTER: AtomicU64 = AtomicU64::new(0);
        let nonce = COUNTER.fetch_add(1, Ordering::Relaxed);
        let dir =
            std::env::temp_dir().join(format!("s2l-codex-{}-{nonce}", std::process::id()));
        std::fs::create_dir_all(&dir)
            .map_err(|e| HarnessError::Transport(format!("could not create {}: {e}", dir.display())))?;
        Ok(dir)
    }

    fn spawn(&self, dir: &PathBuf, schema: &PathBuf, out: &PathBuf) -> Result<Child, HarnessError> {
        let mut command = Command::new(&self.config.executable);
        command
            .arg("exec")
            .arg("--json")
            .arg("--ephemeral")
            .arg("--skip-git-repo-check")
            .arg("--sandbox")
            .arg(self.config.sandbox.as_str())
            .arg("--output-schema")
            .arg(schema)
            .arg("--output-last-message")
            .arg(out)
            .arg("-C")
            .arg(dir);
        if let Some(model) = &self.config.model {
            command.arg("--model").arg(model);
        }
        command
            .arg("-")
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        command.spawn().map_err(|e| {
            HarnessError::Config(format!(
                "could not start `{}`: {e}. Install the codex CLI or pass --provider anthropic.",
                self.config.executable
            ))
        })
    }
}

/// Wait for the child, draining both pipes so a full buffer cannot deadlock it,
/// and kill it if it outlives the deadline. Returns (status ok, stdout, stderr).
fn wait_with_timeout(
    mut child: Child,
    prompt: String,
    timeout_seconds: u64,
) -> Result<(bool, String, String), HarnessError> {
    let mut stdin = child
        .stdin
        .take()
        .ok_or_else(|| HarnessError::Transport("codex stdin was not piped".into()))?;
    let writer = std::thread::spawn(move || {
        let _ = stdin.write_all(prompt.as_bytes());
    });
    let mut stdout = child.stdout.take();
    let mut stderr = child.stderr.take();
    let out_reader = std::thread::spawn(move || {
        let mut buffer = String::new();
        if let Some(pipe) = stdout.as_mut() {
            let _ = pipe.read_to_string(&mut buffer);
        }
        buffer
    });
    let err_reader = std::thread::spawn(move || {
        let mut buffer = String::new();
        if let Some(pipe) = stderr.as_mut() {
            let _ = pipe.read_to_string(&mut buffer);
        }
        buffer
    });

    let deadline = std::time::Instant::now() + std::time::Duration::from_secs(timeout_seconds);
    let status = loop {
        match child.try_wait() {
            Ok(Some(status)) => break Some(status),
            Ok(None) => {
                if std::time::Instant::now() >= deadline {
                    let _ = child.kill();
                    let _ = child.wait();
                    break None;
                }
                std::thread::sleep(std::time::Duration::from_millis(100));
            }
            Err(e) => return Err(HarnessError::Transport(format!("waiting on codex: {e}"))),
        }
    };

    let _ = writer.join();
    let out = out_reader.join().unwrap_or_default();
    let err = err_reader.join().unwrap_or_default();
    match status {
        Some(status) => Ok((status.success(), out, err)),
        None => Err(HarnessError::Transport(format!(
            "codex did not finish within {timeout_seconds}s and was killed"
        ))),
    }
}

/// Codex reports token counts per turn on `turn.completed`. It has no notion of
/// a cache breakpoint, so those two counters stay zero rather than being
/// guessed at — a transcript that invented a cache hit would misreport cost.
fn usage_from_events(events: &str) -> Usage {
    let mut usage = Usage::default();
    for line in events.lines() {
        let Ok(event) = serde_json::from_str::<Value>(line) else {
            continue;
        };
        if event["type"] == "turn.completed" {
            let counts = &event["usage"];
            usage.input_tokens += counts["input_tokens"].as_u64().unwrap_or(0);
            usage.output_tokens += counts["output_tokens"].as_u64().unwrap_or(0);
            usage.cache_read_input_tokens += counts["cached_input_tokens"].as_u64().unwrap_or(0);
        }
    }
    usage
}

/// Turn codex's final message into a turn's text and tool calls.
///
/// Split out from the transport so the wire contract is testable without a
/// subprocess: this is where a schema-constrained reply becomes something the
/// loop can execute, and it is the only place that decides what a malformed
/// reply means.
fn parse_reply(body: &str, turn_index: usize) -> Result<(String, Vec<ToolCall>), HarnessError> {
    let reply: Value = serde_json::from_str(body).map_err(|e| {
        HarnessError::Decode(format!(
            "codex's final message was not JSON ({e}): {}",
            crate::error::truncate(body, 800)
        ))
    })?;
    let text = reply["reply"].as_str().unwrap_or("").to_string();

    let mut tool_calls = Vec::new();
    if let Some(requested) = reply["tool_calls"].as_array() {
        for (index, call) in requested.iter().enumerate() {
            let name = call["name"].as_str().unwrap_or_default().to_string();
            if name.is_empty() {
                return Err(HarnessError::Decode(
                    "codex requested a tool with no name".into(),
                ));
            }
            // A malformed argument string is the model's mistake, not a
            // decoding failure: report it as an empty object so the tool's own
            // validator produces the diagnostic the model can act on. Failing
            // the session here would replace a recoverable turn with a crash.
            let raw = call["arguments_json"].as_str().unwrap_or("{}");
            let input = serde_json::from_str(raw).unwrap_or_else(|_| json!({}));
            tool_calls.push(ToolCall {
                id: format!("codex_{turn_index}_{index}"),
                name,
                input,
            });
        }
    }
    Ok((text, tool_calls))
}

impl Provider for CodexProvider {
    fn id(&self) -> &'static str {
        "codex"
    }

    fn model(&self) -> &str {
        &self.model
    }

    fn turn(&self, request: &Request<'_>) -> Result<TurnResponse, HarnessError> {
        let dir = self.scratch()?;
        let schema_path = dir.join("schema.json");
        let out_path = dir.join("reply.json");
        std::fs::write(
            &schema_path,
            serde_json::to_vec_pretty(&Self::reply_schema()).unwrap_or_default(),
        )
        .map_err(|e| HarnessError::Transport(format!("could not write the reply schema: {e}")))?;

        let child = self.spawn(&dir, &schema_path, &out_path)?;
        let (ok, events, errors) =
            wait_with_timeout(child, Self::render_prompt(request), self.config.timeout_seconds)?;

        let body = std::fs::read_to_string(&out_path).unwrap_or_default();
        let _ = std::fs::remove_dir_all(&dir);

        if !ok && body.trim().is_empty() {
            return Err(HarnessError::Transport(format!(
                "codex exited without a reply: {}",
                crate::error::truncate(errors.trim(), 800)
            )));
        }
        if body.trim().is_empty() {
            return Err(HarnessError::Decode(format!(
                "codex produced no final message: {}",
                crate::error::truncate(errors.trim(), 800)
            )));
        }

        let (text, tool_calls) = parse_reply(body.trim(), request.exchanges.len())?;

        let stop_reason = if tool_calls.is_empty() {
            StopReason::EndTurn
        } else {
            StopReason::ToolUse
        };
        Ok(TurnResponse {
            assistant: json!({
                "reply": text,
                "toolCalls": tool_calls.iter().map(|call| json!({
                    "id": call.id, "name": call.name, "input": call.input,
                })).collect::<Vec<_>>(),
            }),
            text,
            tool_calls,
            stop_reason,
            usage: usage_from_events(&events),
            model: self.model.clone(),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::transcript::{Exchange, ToolResultRecord};

    fn reply(body: &str) -> (String, Vec<ToolCall>) {
        parse_reply(body, 0).expect("this reply should parse")
    }

    #[test]
    fn arguments_arrive_as_a_json_string_and_are_decoded_into_tool_input() {
        let (text, calls) = reply(
            r#"{"reply":"looking","tool_calls":[
                 {"name":"get_node","arguments_json":"{\"nodeId\":\"node:1\"}"}]}"#,
        );
        assert_eq!(text, "looking");
        assert_eq!(calls.len(), 1);
        assert_eq!(calls[0].name, "get_node");
        assert_eq!(calls[0].input["nodeId"], "node:1");
    }

    #[test]
    fn a_malformed_argument_string_becomes_an_empty_input_rather_than_a_failed_session() {
        // The tool's own validator is a better diagnostic than a decode error,
        // and it leaves the model a turn in which to correct itself.
        let (_, calls) = reply(r#"{"reply":"","tool_calls":[{"name":"get_node","arguments_json":"{oops"}]}"#);
        assert_eq!(calls[0].input, json!({}));
    }

    #[test]
    fn an_empty_tool_call_list_ends_the_turn() {
        let (text, calls) = reply(r#"{"reply":"I cannot continue.","tool_calls":[]}"#);
        assert!(calls.is_empty());
        assert_eq!(text, "I cannot continue.");
    }

    #[test]
    fn a_nameless_tool_call_is_a_decode_error() {
        let error = parse_reply(r#"{"reply":"","tool_calls":[{"name":"","arguments_json":"{}"}]}"#, 0)
            .expect_err("a call with no name cannot be dispatched");
        assert!(matches!(error, HarnessError::Decode(_)));
    }

    #[test]
    fn prose_that_is_not_json_is_reported_as_a_decode_error_with_the_body() {
        let error = parse_reply("I think the answer is 4.", 0).expect_err("prose is not a reply");
        match error {
            HarnessError::Decode(detail) => assert!(detail.contains("I think the answer is 4.")),
            other => panic!("expected a decode error, got {other:?}"),
        }
    }

    #[test]
    fn call_ids_are_unique_within_and_across_turns() {
        let body = r#"{"reply":"","tool_calls":[
            {"name":"a","arguments_json":"{}"},{"name":"b","arguments_json":"{}"}]}"#;
        let (_, first) = parse_reply(body, 0).unwrap();
        let (_, second) = parse_reply(body, 1).unwrap();
        let ids: Vec<_> = first.iter().chain(second.iter()).map(|c| c.id.clone()).collect();
        let unique: std::collections::BTreeSet<_> = ids.iter().collect();
        assert_eq!(ids.len(), unique.len(), "duplicate call ids: {ids:?}");
    }

    #[test]
    fn usage_sums_every_completed_turn_and_never_invents_a_cache_write() {
        let events = concat!(
            r#"{"type":"thread.started","thread_id":"t"}"#, "\n",
            r#"{"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":2,"cached_input_tokens":7}}"#, "\n",
            "not json at all\n",
            r#"{"type":"turn.completed","usage":{"input_tokens":5,"output_tokens":1,"cached_input_tokens":0}}"#, "\n",
        );
        let usage = usage_from_events(events);
        assert_eq!(usage.input_tokens, 15);
        assert_eq!(usage.output_tokens, 3);
        assert_eq!(usage.cache_read_input_tokens, 7);
        // Codex has no cache breakpoints; reporting one would misstate cost.
        assert_eq!(usage.cache_creation_input_tokens, 0);
    }

    #[test]
    fn the_prompt_carries_the_tools_the_task_and_every_earlier_tool_result() {
        let tools = vec![ToolSpec::new("get_node", "Fetch one node.", json!({"type": "object"}))];
        let exchanges = vec![Exchange {
            assistant: json!({"reply": "first look"}),
            tool_results: vec![ToolResultRecord {
                call_id: "codex_0_0".into(),
                name: "get_node".into(),
                input: json!({"nodeId": "node:1"}),
                output: "the reset section text".into(),
                is_error: false,
            }],
            usage: Usage::default(),
        }];
        let request = Request {
            system: "SYSTEM RULES",
            prompt: "TASK BODY",
            exchanges: &exchanges,
            tools: &tools,
        };
        let prompt = CodexProvider::render_prompt(&request);
        for expected in [
            "SYSTEM RULES",
            "TASK BODY",
            "get_node",
            "Fetch one node.",
            "first look",
            "the reset section text",
        ] {
            assert!(prompt.contains(expected), "prompt is missing {expected:?}");
        }
    }

    #[test]
    fn the_first_turn_says_the_transcript_is_empty_rather_than_leaving_a_gap() {
        let request = Request {
            system: "s",
            prompt: "p",
            exchanges: &[],
            tools: &[],
        };
        assert!(CodexProvider::render_prompt(&request).contains("this is the first turn"));
    }

    #[test]
    fn a_missing_executable_is_a_configuration_error_that_names_the_alternative() {
        let provider = CodexProvider::new(CodexConfig {
            executable: "codex-does-not-exist".into(),
            ..CodexConfig::default()
        });
        let request = Request { system: "s", prompt: "p", exchanges: &[], tools: &[] };
        match provider.turn(&request) {
            Err(HarnessError::Config(detail)) => {
                assert!(detail.contains("codex-does-not-exist"));
                assert!(detail.contains("--provider anthropic"));
            }
            other => panic!("expected a config error, got {other:?}"),
        }
    }

    #[test]
    fn the_recorded_model_never_invents_an_id_the_user_did_not_choose() {
        assert_eq!(CodexProvider::new(CodexConfig::default()).model(), "codex:config-default");
        assert_eq!(
            CodexProvider::new(CodexConfig { model: Some("gpt-5.6-sol".into()), ..CodexConfig::default() }).model(),
            "codex:gpt-5.6-sol"
        );
    }
}
