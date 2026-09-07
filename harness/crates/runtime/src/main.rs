//! Transport for current-main's Python MCP tools. No artifact schema lives here.
use std::io::{BufRead, BufReader, Read, Write};
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::mpsc::{Receiver, channel};
use std::time::{Duration, Instant};

use harness::provider::codex::{CodexConfig, Sandbox};
use harness::provider::codex_mcp::McpCodexProvider;
use harness::{Effort, Session, ToolOutcome, ToolSet, ToolSpec};
use serde::Deserialize;
use serde_json::{Value, json};

type Error = Box<dyn std::error::Error>;

#[derive(Deserialize)]
struct Input {
    prompt: String,
    model: String,
    reasoning: String,
    max_steps: u32,
    timeout_seconds: u64,
    tool_timeout_ms: u64,
    mcp_command: Vec<String>,
}

struct McpTools {
    child: Child,
    stdin: ChildStdin,
    incoming: Receiver<Result<Value, String>>,
    next_id: u64,
    specs: Vec<ToolSpec>,
    done: bool,
    timeout: Duration,
}

impl McpTools {
    fn start(command: &[String], timeout: Duration) -> Result<Self, Error> {
        let executable = command.first().ok_or("empty MCP command")?;
        let mut child = Command::new(executable)
            .args(&command[1..])
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .spawn()?;
        let stdin = child.stdin.take().ok_or("MCP stdin not piped")?;
        let stdout = child.stdout.take().ok_or("MCP stdout not piped")?;
        let (sender, incoming) = channel();
        std::thread::spawn(move || {
            for line in BufReader::new(stdout).lines() {
                let message = line
                    .map_err(|e| e.to_string())
                    .and_then(|s| serde_json::from_str(&s).map_err(|e| e.to_string()));
                if sender.send(message).is_err() {
                    break;
                }
            }
        });
        let mut tools = Self {
            child,
            stdin,
            incoming,
            next_id: 0,
            specs: Vec::new(),
            done: false,
            timeout,
        };
        tools.request(
            "initialize",
            json!({
                "protocolVersion": "2024-11-05", "capabilities": {},
                "clientInfo": {"name": "spec2lean-harness", "version": env!("CARGO_PKG_VERSION")}
            }),
        )?;
        writeln!(
            tools.stdin,
            "{}",
            json!({"jsonrpc":"2.0", "method":"notifications/initialized"})
        )?;
        tools.stdin.flush()?;
        let response = tools.request("tools/list", json!({}))?;
        for tool in response["tools"]
            .as_array()
            .ok_or("MCP tools/list has no tools")?
        {
            tools.specs.push(ToolSpec::new(
                tool["name"].as_str().ok_or("tool has no name")?,
                tool["description"].as_str().unwrap_or_default(),
                tool["inputSchema"].clone(),
            ));
        }
        Ok(tools)
    }

    fn request(&mut self, method: &str, params: Value) -> Result<Value, Error> {
        self.next_id += 1;
        let id = self.next_id;
        writeln!(
            self.stdin,
            "{}",
            json!({"jsonrpc":"2.0", "id":id, "method":method, "params":params})
        )?;
        self.stdin.flush()?;
        let deadline = Instant::now() + self.timeout;
        loop {
            let message = self
                .incoming
                .recv_timeout(deadline.saturating_duration_since(Instant::now()))??;
            if message["id"].as_u64() != Some(id) {
                continue;
            }
            if let Some(error) = message.get("error") {
                return Err(format!("MCP: {error}").into());
            }
            return message
                .get("result")
                .cloned()
                .ok_or_else(|| "MCP response has no result".into());
        }
    }
}

impl Drop for McpTools {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

impl ToolSet for McpTools {
    fn specs(&self) -> Vec<ToolSpec> {
        self.specs.clone()
    }
    fn finished(&self) -> bool {
        self.done
    }
    fn call(&mut self, name: &str, input: &Value) -> ToolOutcome {
        if !self.specs.iter().any(|spec| spec.name == name) {
            return ToolOutcome::Err(format!("unknown tool: {name}"));
        }
        let result = match self.request("tools/call", json!({"name":name, "arguments":input})) {
            Ok(value) => value,
            Err(error) => return ToolOutcome::Err(error.to_string()),
        };
        let failed = result["isError"].as_bool().unwrap_or(false);
        let mut text = String::new();
        if let Some(content) = result["content"].as_array() {
            for block in content {
                if let Some(part) = block["text"].as_str() {
                    if !text.is_empty() {
                        text.push('\n');
                    }
                    text.push_str(part);
                }
            }
        }
        if failed {
            return ToolOutcome::Err(text);
        }
        let value = serde_json::from_str::<Value>(&text).unwrap_or(Value::String(text));
        // Only current-main's validated submit tools may terminate a session.
        if name.starts_with("submit_") && value["accepted"] == true {
            self.done = true;
        }
        ToolOutcome::Ok(value)
    }
}

fn run() -> Result<(), Error> {
    if std::env::args().nth(1).as_deref() == Some("--version") {
        println!("spec2lean-harness {}", env!("CARGO_PKG_VERSION"));
        return Ok(());
    }
    let mut source = String::new();
    std::io::stdin().read_to_string(&mut source)?;
    let input: Input = serde_json::from_str(&source)?;
    if input.max_steps == 0
        || input.max_steps > 1000
        || input.timeout_seconds == 0
        || input.timeout_seconds > 86400
        || input.tool_timeout_ms == 0
        || input.tool_timeout_ms > 86400000
    {
        return Err("invalid session step or timeout bound".into());
    }
    let model = input
        .model
        .strip_prefix("openai/")
        .ok_or("expected the current-main openai/model ID")?;
    let effort = Effort::parse(&input.reasoning).ok_or("unsupported reasoning effort")?;
    let provider = McpCodexProvider::new(CodexConfig {
        executable: std::env::var("SPEC2LEAN_CODEX").unwrap_or_else(|_| "codex".into()),
        model: Some(model.into()),
        sandbox: Sandbox::ReadOnly,
        timeout_seconds: input.timeout_seconds,
        effort: Some(effort),
    });
    let mut tools = McpTools::start(
        &input.mcp_command,
        Duration::from_millis(input.tool_timeout_ms),
    )?;
    let mut session = Session::new(&provider, &input.prompt).with_max_steps(input.max_steps);
    let (outcome, transcript) = session.stage(
        "Carry out the phase instructions and submit using its validated tool.",
        &mut tools,
    );
    println!(
        "{}",
        json!({
            "runtime":"rust-harness", "sessionId":format!("harness:{}:{}", std::process::id(), transcript.started_at),
            "transcript":transcript,
        })
    );
    outcome.map_err(Into::into)
}

fn main() {
    if let Err(error) = run() {
        eprintln!("spec2lean-harness: {error}");
        std::process::exit(1);
    }
}
