//! The codex CLI as one long-lived MCP server rather than a process per turn.
//!
//! `codex exec` costs a process start every turn — measured at roughly five
//! seconds against a real, minimally-sized turn — and re-sends codex's own
//! instructions underneath ours each time. `codex mcp-server` is the same model
//! behind a conversation that stays open: `codex` opens a thread, `codex-reply`
//! continues it, and `base-instructions` replaces codex's default preamble
//! instead of merely caching it.
//!
//! What is given up is `--output-schema`: the MCP tools return a string, so the
//! reply contract moves into the instructions and is checked before dispatch.
//! Native argument objects avoid extra string encoding. Malformed replies are
//! retained in the transcript and corrected within the same bounded session.

use std::io::{BufRead, BufReader, Write};
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::Mutex;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::mpsc::{Receiver, RecvTimeoutError, channel};
use std::time::{Duration, Instant};

use serde_json::{Value, json};

use crate::error::HarnessError;
use crate::provider::codex::{CodexConfig, CodexProvider, Thread, codex_effort, resumable};
use crate::provider::{Provider, Request, StopReason, ToolCall, TurnResponse};
use crate::transcript::Usage;

/// A JSON-RPC peer speaking MCP over the child's stdio.
struct Server {
    child: Child,
    stdin: ChildStdin,
    incoming: Receiver<Value>,
    next_id: AtomicU64,
}

impl Server {
    fn start(executable: &str) -> Result<Self, HarnessError> {
        let mut child = Command::new(executable)
            .args([
                "-c",
                "features.shell_tool=false",
                "-c",
                "features.apps=false",
                "-c",
                "features.plugins=false",
                "-c",
                "features.multi_agent=false",
                "-c",
                "web_search=\"disabled\"",
                "-c",
                "tools.view_image=false",
                "-c",
                "mcp_servers={}",
                "-c",
                "project_doc_max_bytes=0",
            ])
            .arg("mcp-server")
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|e| {
                HarnessError::Config(format!(
                    "could not start `{executable} mcp-server`: {e}. Install/authenticate the Codex \
                     CLI and put it on PATH, or set SPEC2LEAN_CODEX to its absolute executable path."
                ))
            })?;
        let stdin = child
            .stdin
            .take()
            .ok_or_else(|| HarnessError::Transport("codex stdin was not piped".into()))?;
        let stdout = child
            .stdout
            .take()
            .ok_or_else(|| HarnessError::Transport("codex stdout was not piped".into()))?;

        // One reader thread, because a blocking read on the response would
        // otherwise stall behind the notifications codex interleaves with it.
        let (sender, incoming) = channel();
        std::thread::spawn(move || {
            for line in BufReader::new(stdout).lines().map_while(Result::ok) {
                if let Ok(message) = serde_json::from_str::<Value>(&line)
                    && sender.send(message).is_err()
                {
                    return;
                }
            }
        });

        let server = Self {
            child,
            stdin,
            incoming,
            next_id: AtomicU64::new(1),
        };
        server.handshake()?;
        Ok(server)
    }

    fn handshake(&self) -> Result<(), HarnessError> {
        self.request(
            "initialize",
            json!({
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "spec2lean", "version": env!("CARGO_PKG_VERSION")},
            }),
            Duration::from_secs(30),
        )?;
        self.notify("notifications/initialized", json!({}))
    }

    fn write(&self, message: &Value) -> Result<(), HarnessError> {
        let mut stdin = &self.stdin;
        let line = format!("{message}\n");
        stdin
            .write_all(line.as_bytes())
            .and_then(|()| stdin.flush())
            .map_err(|e| HarnessError::Transport(format!("writing to codex mcp-server: {e}")))
    }

    fn notify(&self, method: &str, params: Value) -> Result<(), HarnessError> {
        self.write(&json!({"jsonrpc": "2.0", "method": method, "params": params}))
    }

    /// Send one request and read until its response, accumulating the token
    /// counts codex reports for it along the way.
    fn request_with_usage(
        &self,
        method: &str,
        params: Value,
        timeout: Duration,
    ) -> Result<(Value, Usage), HarnessError> {
        let id = self.next_id.fetch_add(1, Ordering::Relaxed);
        self.write(&json!({
            "jsonrpc": "2.0", "id": id, "method": method, "params": params
        }))?;

        let mut usage = Usage::default();
        let deadline = Instant::now() + timeout;
        loop {
            let remaining = deadline.saturating_duration_since(Instant::now());
            if remaining.is_zero() {
                return Err(HarnessError::Transport(format!(
                    "codex mcp-server did not answer {method} within {}s",
                    timeout.as_secs()
                )));
            }
            let message = match self.incoming.recv_timeout(remaining) {
                Ok(message) => message,
                Err(RecvTimeoutError::Timeout) => continue,
                Err(RecvTimeoutError::Disconnected) => {
                    return Err(HarnessError::Transport(
                        "codex mcp-server closed its output".into(),
                    ));
                }
            };

            // Usage arrives as notifications, not in the response, and one turn
            // may make several model calls. Each `token_count` reports the call
            // that just finished, so they are summed rather than replaced.
            if message["method"] == "codex/event"
                && message["params"]["_meta"]["requestId"].as_u64() == Some(id)
                && message["params"]["msg"]["type"] == "token_count"
            {
                accumulate(
                    &mut usage,
                    &message["params"]["msg"]["info"]["last_token_usage"],
                );
            }

            if message["id"].as_u64() == Some(id) {
                if let Some(error) = message.get("error") {
                    return Err(HarnessError::Transport(format!(
                        "codex mcp-server rejected {method}: {error}"
                    )));
                }
                return Ok((message["result"].clone(), usage));
            }
        }
    }

    fn request(
        &self,
        method: &str,
        params: Value,
        timeout: Duration,
    ) -> Result<Value, HarnessError> {
        self.request_with_usage(method, params, timeout)
            .map(|(result, _)| result)
    }
}

impl Drop for Server {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

pub(crate) fn accumulate(usage: &mut Usage, counts: &Value) {
    let field = |name: &str| counts[name].as_u64().unwrap_or(0);
    usage.input_tokens += field("input_tokens");
    // Reasoning tokens are generated and billed like any other output.
    usage.output_tokens += field("output_tokens") + field("reasoning_output_tokens");
    usage.cache_read_input_tokens += field("cached_input_tokens");
}

pub struct McpCodexProvider {
    config: CodexConfig,
    model: String,
    state: Mutex<State>,
}

#[derive(Default)]
struct State {
    server: Option<Server>,
    threads: std::collections::HashMap<u64, Thread>,
}

impl McpCodexProvider {
    pub fn new(config: CodexConfig) -> Self {
        let model = match &config.model {
            Some(name) => format!("codex-mcp:{name}"),
            None => "codex-mcp:config-default".to_string(),
        };
        Self {
            config,
            model,
            state: Mutex::new(State::default()),
        }
    }

    /// Codex's own preamble, replaced. It carries what the exec transport put
    /// in every prompt — how to answer, and not to reach for its own tools —
    /// plus the phase's instructions, which are constant for a thread and so
    /// are stated once rather than on every turn.
    fn base_instructions(request: &Request<'_>) -> String {
        format!(
            "You are driving a tool-using task through a harness that executes every tool for \
             you. Do not use your own shell, file or search tools: they cannot see this task's \
             data, and anything they return is noise.\n\n\
             Every reply you send must be exactly one JSON object matching this schema, with no \
             prose around it and no code fence:\n\n```json\n{}\n```\n\n\
             `arguments` is the tool's complete arguments object, not a JSON-encoded string.\n\n\
             # Instructions\n\n{}\n\n{}",
            serde_json::to_string_pretty(&json!({
                "type": "object", "required": ["reply", "tool_calls"],
                "additionalProperties": false,
                "properties": {
                    "reply": {"type": "string"},
                    "tool_calls": {"type": "array", "items": {
                        "type": "object", "required": ["name", "arguments"],
                        "additionalProperties": false,
                        "properties": {
                            "name": {"type": "string", "enum": request.tools.iter()
                                .map(|tool| tool.name.clone()).collect::<Vec<_>>()},
                            "arguments": {"type": "object"}
                        }
                    }}
                }
            }))
            .unwrap_or_default(),
            request.system,
            CodexProvider::render_tools(request.tools),
        )
    }

    fn open(&self, request: &Request<'_>) -> Value {
        let mut arguments = json!({
            "prompt": CodexProvider::render_full(request),
            "sandbox": self.config.sandbox.as_str(),
            "base-instructions": Self::base_instructions(request),
            "approval-policy": "never",
        });
        if let Some(model) = &self.config.model {
            arguments["model"] = json!(model);
        }
        if let Some(effort) = self.config.effort {
            arguments["config"] = json!({"model_reasoning_effort": codex_effort(effort)});
        }
        arguments
    }
}

impl Provider for McpCodexProvider {
    fn id(&self) -> &'static str {
        "codex"
    }

    fn model(&self) -> &str {
        &self.model
    }

    fn turn(&self, request: &Request<'_>) -> Result<TurnResponse, HarnessError> {
        let mut state = self
            .state
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner);
        if state.server.is_none() {
            state.server = Some(Server::start(&self.config.executable)?);
        }

        let resume = state
            .threads
            .get(&request.session)
            .filter(|open| resumable(open, request))
            .map(|open| (open.id.clone(), open.sent, open.prompt != request.prompt));

        let timeout = Duration::from_secs(self.config.timeout_seconds);
        let arguments = match &resume {
            Some((id, sent, new_task)) => json!({
                "name": "codex-reply",
                "arguments": {
                    "threadId": id,
                    "prompt": CodexProvider::render_delta(request, *sent, *new_task),
                },
            }),
            None => json!({"name": "codex", "arguments": self.open(request)}),
        };

        let server = state.server.as_ref().expect("started above");
        let attempt = server.request_with_usage("tools/call", arguments, timeout);

        // A thread that cannot be continued is recoverable: the harness holds
        // the whole conversation, so open a new one and replay it.
        let (result, usage) = match attempt {
            Ok(answer) => answer,
            Err(error) => {
                if resume.is_none() {
                    return Err(error);
                }
                state.threads.remove(&request.session);
                let server = state.server.as_ref().expect("started above");
                server.request_with_usage(
                    "tools/call",
                    json!({"name": "codex", "arguments": self.open(request)}),
                    timeout,
                )?
            }
        };

        let structured = &result["structuredContent"];
        let content = structured["content"].as_str().unwrap_or_default();
        let thread = structured["threadId"]
            .as_str()
            .unwrap_or_default()
            .to_string();
        if thread.is_empty() {
            return Err(HarnessError::Decode(
                "codex mcp-server answered without a thread id".into(),
            ));
        }

        state.threads.insert(
            request.session,
            Thread {
                id: thread,
                sent: request.exchanges.len(),
                system: request.system.to_string(),
                prompt: request.prompt.to_string(),
            },
        );

        // Retain the thread before decoding: malformed output is corrected in
        // this conversation and consumes a normal bounded session step.
        match decode_reply(content, request.exchanges.len()) {
            Ok((text, tool_calls)) => Ok(TurnResponse {
                assistant: json!({
                    "reply": text,
                    "toolCalls": tool_calls.iter().map(|call| json!({
                        "id": call.id, "name": call.name, "input": call.input,
                    })).collect::<Vec<_>>(),
                }),
                text,
                stop_reason: if tool_calls.is_empty() {
                    StopReason::EndTurn
                } else {
                    StopReason::ToolUse
                },
                tool_calls,
                usage,
                model: self.model.clone(),
            }),
            Err(error) => Ok(TurnResponse {
                assistant: json!({"reply": "", "rawResponse": content, "responseError": error.to_string()}),
                text: String::new(),
                tool_calls: Vec::new(),
                stop_reason: StopReason::InvalidResponse,
                usage,
                model: self.model.clone(),
            }),
        }
    }
}

/// Decode the complete reply before executing any of its calls. Native argument
/// objects avoid an extra escaping layer around large Lean submissions. Accept
/// the original string encoding too, but never replace malformed inputs with {}.
fn decode_reply(content: &str, turn: usize) -> Result<(String, Vec<ToolCall>), HarnessError> {
    let invalid =
        |detail: &str| HarnessError::Decode(format!("invalid Codex tool reply: {detail}"));
    let reply: Value = serde_json::from_str(&repair(extract_object(content)))
        .map_err(|error| invalid(&error.to_string()))?;
    let text = reply["reply"]
        .as_str()
        .ok_or_else(|| invalid("reply must be a string"))?;
    let calls = reply["tool_calls"]
        .as_array()
        .ok_or_else(|| invalid("tool_calls must be an array"))?;
    let mut tool_calls = Vec::with_capacity(calls.len());
    for (index, call) in calls.iter().enumerate() {
        let name = call["name"]
            .as_str()
            .filter(|name| !name.is_empty())
            .ok_or_else(|| invalid("every call needs a nonempty name"))?;
        let input = match (call.get("arguments"), call.get("arguments_json")) {
            (Some(arguments), None) if arguments.is_object() => arguments.clone(),
            (None, Some(Value::String(encoded))) => serde_json::from_str(encoded)
                .map_err(|error| invalid(&format!("arguments_json: {error}")))?,
            _ => {
                return Err(invalid(
                    "provide exactly one arguments object (or legacy arguments_json string)",
                ));
            }
        };
        if !input.is_object() {
            return Err(invalid("tool arguments must be a JSON object"));
        }
        tool_calls.push(ToolCall {
            id: format!("codex_{turn}_{index}"),
            name: name.into(),
            input,
        });
    }
    Ok((text.to_owned(), tool_calls))
}

/// Escape the raw control characters a hand-written JSON string may contain.
///
/// With `--output-schema` the server produced the JSON and escaped it. Here the
/// model types it, and specification text is full of tabs and newlines — a
/// register table is literally `Bits\tType\tReset\tDescription` — which it
/// embeds verbatim inside a string. Strict JSON rejects those, so a faithful
/// quotation of the evidence would be unparseable and the model would be asked
/// to fix something it had got right.
///
/// Only characters inside a string literal are touched, and an escape sequence
/// that is already correct is left alone.
pub(crate) fn repair(content: &str) -> String {
    let mut repaired = String::with_capacity(content.len());
    let mut in_string = false;
    let mut escaped = false;
    for character in content.chars() {
        if escaped {
            repaired.push(character);
            escaped = false;
            continue;
        }
        match character {
            '\\' if in_string => {
                repaired.push(character);
                escaped = true;
            }
            '"' => {
                in_string = !in_string;
                repaired.push(character);
            }
            control if in_string && (control as u32) < 0x20 => match control {
                '\t' => repaired.push_str("\\t"),
                '\n' => repaired.push_str("\\n"),
                '\r' => repaired.push_str("\\r"),
                other => repaired.push_str(&format!("\\u{:04x}", other as u32)),
            },
            other => repaired.push(other),
        }
    }
    repaired
}

/// The outermost balanced JSON object in a reply, or the reply unchanged.
///
/// Without a schema on the wire a model that is asked for bare JSON will
/// occasionally fence it or introduce it. Rejecting those costs a turn to say
/// something the text already contains; misreading them costs correctness, so
/// this recovers only a well-formed object and leaves anything else to fail in
/// the reply decoder, which can request correction without executing any tools.
pub(crate) fn extract_object(content: &str) -> &str {
    let bytes = content.as_bytes();
    let Some(start) = content.find('{') else {
        return content.trim();
    };
    let mut depth = 0usize;
    let mut in_string = false;
    let mut escaped = false;
    for (index, byte) in bytes.iter().enumerate().skip(start) {
        if in_string {
            match byte {
                _ if escaped => escaped = false,
                b'\\' => escaped = true,
                b'"' => in_string = false,
                _ => {}
            }
            continue;
        }
        match byte {
            b'"' => in_string = true,
            b'{' => depth += 1,
            b'}' => {
                depth -= 1;
                if depth == 0 {
                    return &content[start..=index];
                }
            }
            _ => {}
        }
    }
    content.trim()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::provider::codex::parse_reply;

    /// Without `--output-schema` the reply is whatever the model typed, and a
    /// model asked for bare JSON will sometimes fence it or introduce it.
    #[test]
    fn a_fenced_or_introduced_reply_still_yields_its_object() {
        let bare = r#"{"reply":"ok","tool_calls":[]}"#;
        assert_eq!(extract_object(bare), bare);
        assert_eq!(
            extract_object("```json\n{\"reply\":\"ok\"}\n```"),
            r#"{"reply":"ok"}"#
        );
        assert_eq!(
            extract_object("Here you go:\n{\"reply\":\"ok\"}\nhope that helps"),
            r#"{"reply":"ok"}"#
        );
    }

    #[test]
    fn braces_inside_strings_do_not_close_the_object() {
        let reply = r#"{"reply":"a } and a { in prose","tool_calls":[]}"#;
        assert_eq!(extract_object(reply), reply);
        let escaped = r#"{"reply":"quote \" then }","tool_calls":[]}"#;
        assert_eq!(extract_object(escaped), escaped);
    }

    #[test]
    fn nesting_is_balanced_rather_than_stopping_at_the_first_close() {
        let reply = r#"{"reply":"","tool_calls":[{"name":"a","arguments_json":"{}"}]}"#;
        assert_eq!(extract_object(reply), reply);
    }

    /// A reply with no object at all is handed on unchanged, so it fails in
    /// `parse_reply` with the same diagnostic the exec transport produces.
    #[test]
    fn prose_with_no_object_is_left_for_the_shared_parser_to_reject() {
        assert_eq!(extract_object("  I cannot do that.  "), "I cannot do that.");
        assert!(parse_reply(extract_object("I cannot do that."), 0).is_err());
        // An unterminated object is not an object.
        assert_eq!(extract_object("{\"reply\": "), "{\"reply\":");
    }

    /// Usage arrives only as notifications, and one turn may make several model
    /// calls, so the counts are summed rather than overwritten.
    #[test]
    fn token_counts_accumulate_across_a_turns_model_calls() {
        let mut usage = Usage::default();
        accumulate(
            &mut usage,
            &json!({
                "input_tokens": 100, "cached_input_tokens": 40,
                "output_tokens": 10, "reasoning_output_tokens": 900
            }),
        );
        accumulate(
            &mut usage,
            &json!({
                "input_tokens": 50, "cached_input_tokens": 5,
                "output_tokens": 2, "reasoning_output_tokens": 8
            }),
        );
        assert_eq!(usage.input_tokens, 150);
        assert_eq!(usage.cache_read_input_tokens, 45);
        assert_eq!(usage.output_tokens, 920, "reasoning tokens are output too");
    }

    #[test]
    fn the_base_instructions_carry_the_reply_contract_the_phase_and_the_tools() {
        let tools = [crate::tool::ToolSpec::new(
            "get_evidence",
            "Read the bundle.",
            json!({}),
        )];
        let request = Request {
            system: "PHASE RULES",
            prompt: "the task",
            prompt_pending: true,
            exchanges: &[],
            tools: &tools,
            session: 1,
        };
        let instructions = McpCodexProvider::base_instructions(&request);
        // Codex's own preamble is replaced, so everything it used to carry has
        // to be here instead.
        for expected in [
            "arguments",
            "PHASE RULES",
            "get_evidence",
            "Read the bundle.",
        ] {
            assert!(instructions.contains(expected), "missing {expected:?}");
        }
        assert!(instructions.contains("Do not use your own shell"));
    }

    #[test]
    fn a_missing_executable_explains_how_to_configure_the_provider() {
        let provider = McpCodexProvider::new(CodexConfig {
            executable: "codex-does-not-exist".into(),
            ..CodexConfig::default()
        });
        let request = Request {
            system: "s",
            prompt: "p",
            prompt_pending: true,
            exchanges: &[],
            tools: &[],
            session: 1,
        };
        match provider.turn(&request) {
            Err(HarnessError::Config(detail)) => {
                assert!(detail.contains("codex-does-not-exist"));
                assert!(detail.contains("SPEC2LEAN_CODEX"));
            }
            other => panic!("expected a config error, got {other:?}"),
        }
    }

    #[test]
    fn the_recorded_model_distinguishes_the_transport() {
        assert_eq!(
            McpCodexProvider::new(CodexConfig::default()).model(),
            "codex-mcp:config-default"
        );
    }

    /// The real failure this fixes: a doorbell register's evidence is a tab
    /// separated table, the model quoted it faithfully into a JSON string, and
    /// strict JSON rejected the tabs. The quotation was right; the escaping was
    /// not, and asking the model to try again would have taught it to quote the
    /// specification less accurately.
    #[test]
    fn raw_tabs_and_newlines_from_specification_text_are_escaped_not_rejected() {
        let typed = "{\"reply\":\"Bits\tType\tReset\nDescription\",\"tool_calls\":[]}";
        assert!(
            serde_json::from_str::<serde_json::Value>(typed).is_err(),
            "precondition"
        );

        let value: serde_json::Value = serde_json::from_str(&repair(typed)).expect("repaired");
        assert_eq!(value["reply"], "Bits\tType\tReset\nDescription");
    }

    #[test]
    fn escapes_that_were_already_correct_are_left_alone() {
        let correct = r#"{"reply":"a\tb","tool_calls":[]}"#;
        assert_eq!(repair(correct), correct);
        let value: serde_json::Value = serde_json::from_str(&repair(correct)).unwrap();
        assert_eq!(value["reply"], "a\tb");
    }

    #[test]
    fn an_escaped_quote_does_not_end_the_string_being_repaired() {
        let typed = "{\"reply\":\"say \\\" then\ttab\",\"tool_calls\":[]}";
        let value: serde_json::Value = serde_json::from_str(&repair(typed)).expect("repaired");
        assert_eq!(value["reply"], "say \" then\ttab");
    }

    #[test]
    fn whitespace_between_tokens_is_not_inside_a_string_and_stays_as_it_is() {
        let pretty = "{\n  \"reply\": \"ok\",\n  \"tool_calls\": []\n}";
        assert_eq!(repair(pretty), pretty, "only string contents are rewritten");
        assert!(serde_json::from_str::<serde_json::Value>(&repair(pretty)).is_ok());
    }

    #[test]
    fn an_exotic_control_character_becomes_a_unicode_escape() {
        let typed = "{\"reply\":\"bell\u{7}here\",\"tool_calls\":[]}";
        let value: serde_json::Value = serde_json::from_str(&repair(typed)).expect("repaired");
        assert_eq!(value["reply"], "bell\u{7}here");
    }
}
