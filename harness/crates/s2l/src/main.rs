//! spec2lean command line entry point.
//!
//! Deliberately dependency-free argument parsing: this binary is the whole
//! runtime surface of the harness, and the point of the rewrite is that it
//! needs nothing on `PATH` to work.

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::process::ExitCode;

use harness::provider::anthropic::{AnthropicConfig, AnthropicProvider};
use harness::provider::openai::{OpenAiConfig, OpenAiProvider};
use harness::{Effort, Provider, Session};
use serde_json::{Value, json};
use spec2lean_evidence::{EvidenceScope, EvidenceTools, prompt};
use spec2lean_semantics::{SemanticScope, SemanticTools};
use spec2lean_specdb::{SpecDb, UnitId};

const USAGE: &str = "\
spec2lean harness

USAGE:
    s2l evidence prompt  --database <PATH> --plan <PATH> --unit <unit:ID>
    s2l evidence scope   --database <PATH> --plan <PATH> --unit <unit:ID>
    s2l evidence replay  --database <PATH> --plan <PATH> --unit <unit:ID> --calls <PATH> [--out <DIR>]
    s2l evidence run     --database <PATH> --plan <PATH> --unit <unit:ID> --out <DIR>
                         [PROVIDER OPTIONS]

    s2l semantics prompt --plan <PATH> --bundle <PATH> --unit <unit:ID>
    s2l semantics replay --plan <PATH> --bundle <PATH> --unit <unit:ID> --calls <PATH> [--out <DIR>]
    s2l semantics run    --plan <PATH> --bundle <PATH> --unit <unit:ID> --out <DIR>
                         [PROVIDER OPTIONS]

PROVIDER OPTIONS:
    [--provider anthropic|openai] [--model <ID>]
    [--effort low|medium|high|xhigh|max] [--max-steps <N>]

ENVIRONMENT:
    ANTHROPIC_API_KEY / ANTHROPIC_BASE_URL    credentials for --provider anthropic
    OPENAI_API_KEY / OPENAI_BASE_URL          credentials for --provider openai

`replay` runs a scripted list of tool calls with no provider and no network,
which is how the tool set, the exposure ledger, and the deterministic validator
are exercised offline.
";

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(message) => {
            eprintln!("error: {message}");
            ExitCode::FAILURE
        }
    }
}

fn run() -> Result<(), String> {
    let arguments: Vec<String> = std::env::args().skip(1).collect();
    let words: Vec<&str> = arguments.iter().map(String::as_str).collect();
    match words.as_slice() {
        [] | ["-h"] | ["--help"] | ["help"] => {
            print!("{USAGE}");
            Ok(())
        }
        ["evidence", command, rest @ ..] => {
            let flags = Flags::parse(rest)?;
            match *command {
                "prompt" => evidence_prompt(&flags),
                "scope" => evidence_scope(&flags),
                "replay" => evidence_replay(&flags),
                "run" => evidence_run(&flags),
                other => Err(format!("unknown evidence command: {other}\n\n{USAGE}")),
            }
        }
        ["semantics", command, rest @ ..] => {
            let flags = Flags::parse(rest)?;
            match *command {
                "prompt" => semantics_prompt(&flags),
                "scope" => semantics_scope(&flags),
                "replay" => semantics_replay(&flags),
                "run" => semantics_run(&flags),
                other => Err(format!("unknown semantics command: {other}\n\n{USAGE}")),
            }
        }
        [other, ..] => Err(format!("unknown command: {other}\n\n{USAGE}")),
    }
}

struct Flags(BTreeMap<String, String>);

impl Flags {
    fn parse(words: &[&str]) -> Result<Self, String> {
        let mut flags = BTreeMap::new();
        let mut index = 0;
        while index < words.len() {
            let word = words[index];
            let name = word
                .strip_prefix("--")
                .ok_or_else(|| format!("expected a --flag, found {word:?}"))?;
            let value = words
                .get(index + 1)
                .ok_or_else(|| format!("--{name} requires a value"))?;
            flags.insert(name.to_string(), (*value).to_string());
            index += 2;
        }
        Ok(Self(flags))
    }

    fn get(&self, name: &str) -> Result<&str, String> {
        self.0
            .get(name)
            .map(String::as_str)
            .ok_or_else(|| format!("--{name} is required"))
    }

    fn optional(&self, name: &str) -> Option<&str> {
        self.0.get(name).map(String::as_str)
    }

    fn path(&self, name: &str) -> Result<PathBuf, String> {
        Ok(PathBuf::from(self.get(name)?))
    }
}

/// Open the index and resolve the Phase-2 boundary for one unit.
fn context(flags: &Flags) -> Result<(SpecDb, EvidenceScope), String> {
    let db = SpecDb::open(&flags.path("database")?).map_err(|error| error.to_string())?;
    let plan: Value = read_json(&flags.path("plan")?)?;
    let unit_id = UnitId::parse(flags.get("unit")?).map_err(|error| error.to_string())?;
    let scope = EvidenceScope::from_plan(&plan, &unit_id).map_err(|error| error.to_string())?;

    // A plan built against a different index cannot be honoured: every node ID
    // in it would be meaningless. Fail before spending a single token.
    let digest = db.semantic_digest().map_err(|error| error.to_string())?;
    if digest != scope.source_database_digest {
        return Err(format!(
            "plan was built against a different index: plan digest {} != database digest {digest}",
            scope.source_database_digest
        ));
    }
    Ok((db, scope))
}

fn evidence_scope(flags: &Flags) -> Result<(), String> {
    let (_db, scope) = context(flags)?;
    println!("{}", pretty(&scope.to_json()));
    Ok(())
}

fn evidence_prompt(flags: &Flags) -> Result<(), String> {
    let (db, scope) = context(flags)?;
    let user = prompt::user_prompt(&db, &scope).map_err(|error| error.to_string())?;
    println!("=== system ===\n{}\n\n=== user ===\n{user}", prompt::system_prompt());
    Ok(())
}

/// Run a scripted list of `{"tool": ..., "input": {...}}` calls with no
/// provider. Everything except the model is exercised.
fn evidence_replay(flags: &Flags) -> Result<(), String> {
    use harness::ToolSet;

    let (db, scope) = context(flags)?;
    let calls: Value = read_json(&flags.path("calls")?)?;
    let calls = calls
        .as_array()
        .ok_or("the calls file must contain a JSON array")?;
    let mut tools = EvidenceTools::new(&db, scope).map_err(|error| error.to_string())?;

    for (index, call) in calls.iter().enumerate() {
        let name = call
            .get("tool")
            .and_then(Value::as_str)
            .ok_or_else(|| format!("call {index} has no \"tool\""))?;
        let input = call.get("input").cloned().unwrap_or_else(|| json!({}));
        let outcome = tools.call(name, &input);
        println!("--- {index}: {name} ({}) ---", if outcome.is_error() { "error" } else { "ok" });
        println!("{}", outcome.to_text());
    }

    if let Some(out) = flags.optional("out") {
        write_artifacts(Path::new(out), &tools, None)?;
    }
    if tools.finished() {
        println!("\nbundle accepted");
        Ok(())
    } else {
        Err("the scripted calls did not produce an accepted bundle".into())
    }
}

fn evidence_run(flags: &Flags) -> Result<(), String> {
    let (db, scope) = context(flags)?;
    let out = flags.path("out")?;
    let user = prompt::user_prompt(&db, &scope).map_err(|error| error.to_string())?;
    let mut tools = EvidenceTools::new(&db, scope).map_err(|error| error.to_string())?;

    let provider = provider(flags)?;
    let session = Session::new(provider.as_ref(), prompt::system_prompt(), user)
        .with_max_steps(max_steps(flags)?);
    let (outcome, transcript) = session.run(&mut tools);

    // The transcript is written whether or not the session succeeded — a failed
    // run is exactly the one whose transcript you need.
    write_artifacts(&out, &tools, Some(&transcript))?;
    match outcome {
        Ok(()) => {
            let count = tools
                .bundle()
                .and_then(|bundle| bundle["evidence"].as_array())
                .map_or(0, Vec::len);
            println!(
                "accepted {count} evidence items in {} steps ({} cached input tokens)",
                transcript.steps, transcript.usage.cache_read_input_tokens
            );
            Ok(())
        }
        Err(error) => Err(format!("{error} (artifacts written to {})", out.display())),
    }
}


/// Build the configured provider. Shared by every phase, so a model or effort
/// change is one flag rather than an edit in each phase's runner.
fn provider(flags: &Flags) -> Result<Box<dyn Provider>, String> {
    let model = flags.optional("model").map(str::to_string);
    let effort = match flags.optional("effort") {
        None => Some(Effort::High),
        Some(value) => {
            Some(Effort::parse(value).ok_or_else(|| format!("unknown effort level: {value}"))?)
        }
    };
    Ok(match flags.optional("provider").unwrap_or("anthropic") {
        "anthropic" => {
            let mut config = AnthropicConfig::from_env(model).map_err(|e| e.to_string())?;
            config.effort = effort;
            Box::new(AnthropicProvider::new(config))
        }
        "openai" => Box::new(OpenAiProvider::new(
            OpenAiConfig::from_env(model).map_err(|e| e.to_string())?,
        )),
        other => return Err(format!("unknown provider: {other}")),
    })
}

fn max_steps(flags: &Flags) -> Result<u32, String> {
    match flags.optional("max-steps") {
        None => Ok(100),
        Some(value) => value
            .parse::<u32>()
            .map_err(|_| format!("--max-steps must be a positive integer, found {value:?}")),
    }
}

/// What produced an artifact. Recorded honestly rather than hardcoded, which is
/// what the OpenCode-era `provider: "opencode"` field amounted to.
fn extractor(provider: &dyn Provider) -> Value {
    json!({"provider": provider.id(), "model": provider.model()})
}

/// Resolve the Phase-4 boundary from a plan and a Phase-3 bundle.
fn semantic_context(flags: &Flags) -> Result<(SemanticScope, Value), String> {
    let plan: Value = read_json(&flags.path("plan")?)?;
    let bundle: Value = read_json(&flags.path("bundle")?)?;
    let unit_id = UnitId::parse(flags.get("unit")?).map_err(|error| error.to_string())?;
    let created_at = flags
        .optional("created-at")
        .map(str::to_string)
        .unwrap_or_else(harness::clock::utc_now_iso);
    let scope = SemanticScope::from_inputs(&plan, &bundle, &unit_id, &created_at)
        .map_err(|error| error.to_string())?;
    Ok((scope, bundle))
}

fn semantics_scope(flags: &Flags) -> Result<(), String> {
    let (scope, _bundle) = semantic_context(flags)?;
    println!("{}", pretty(&scope.to_json()));
    Ok(())
}

fn semantics_prompt(flags: &Flags) -> Result<(), String> {
    use spec2lean_semantics::prompt as semantic_prompt;
    let (scope, bundle) = semantic_context(flags)?;
    println!(
        "=== system ===\n{}\n\n=== user ===\n{}",
        semantic_prompt::system_prompt(),
        semantic_prompt::user_prompt(&scope, &bundle)
    );
    Ok(())
}

fn semantics_replay(flags: &Flags) -> Result<(), String> {
    use harness::ToolSet;

    let (scope, bundle) = semantic_context(flags)?;
    let calls: Value = read_json(&flags.path("calls")?)?;
    let calls = calls
        .as_array()
        .ok_or("the calls file must contain a JSON array")?;
    let mut tools = SemanticTools::new(
        scope,
        bundle,
        json!({"provider": "replay", "model": "none"}),
    );

    for (index, call) in calls.iter().enumerate() {
        let name = call
            .get("tool")
            .and_then(Value::as_str)
            .ok_or_else(|| format!("call {index} has no \"tool\""))?;
        let input = call.get("input").cloned().unwrap_or_else(|| json!({}));
        let outcome = tools.call(name, &input);
        println!(
            "--- {index}: {name} ({}) ---",
            if outcome.is_error() { "error" } else { "ok" }
        );
        println!("{}", outcome.to_text());
    }

    if let Some(out) = flags.optional("out") {
        write_semantic_artifacts(Path::new(out), &tools, None)?;
    }
    if tools.finished() {
        println!("\nartifact accepted");
        Ok(())
    } else {
        Err("the scripted calls did not produce an accepted artifact".into())
    }
}

fn semantics_run(flags: &Flags) -> Result<(), String> {
    use spec2lean_semantics::prompt as semantic_prompt;

    let (scope, bundle) = semantic_context(flags)?;
    let out = flags.path("out")?;
    let provider = provider(flags)?;
    let user = semantic_prompt::user_prompt(&scope, &bundle);
    let mut tools = SemanticTools::new(scope, bundle, extractor(provider.as_ref()));

    let session = Session::new(provider.as_ref(), semantic_prompt::system_prompt(), user)
        .with_max_steps(max_steps(flags)?);
    let (outcome, transcript) = session.run(&mut tools);

    write_semantic_artifacts(&out, &tools, Some(&transcript))?;
    match outcome {
        Ok(()) => {
            let artifact_outcome = tools
                .artifact()
                .and_then(|artifact| artifact["outcome"].as_str())
                .unwrap_or("UNKNOWN");
            println!(
                "{artifact_outcome} in {} steps ({} cached input tokens)",
                transcript.steps, transcript.usage.cache_read_input_tokens
            );
            Ok(())
        }
        Err(error) => Err(format!("{error} (artifacts written to {})", out.display())),
    }
}

fn write_semantic_artifacts(
    out: &Path,
    tools: &SemanticTools,
    transcript: Option<&harness::Transcript>,
) -> Result<(), String> {
    std::fs::create_dir_all(out).map_err(|error| format!("{}: {error}", out.display()))?;
    write_json(&out.join("semantic-scope.json"), &tools.scope().to_json())?;
    if let Some(artifact) = tools.artifact() {
        write_json(&out.join("semantic-artifact.json"), artifact)?;
    }
    if let Some(transcript) = transcript {
        let value = serde_json::to_value(transcript).map_err(|error| error.to_string())?;
        write_json(&out.join("transcript.json"), &value)?;
    }
    Ok(())
}

fn write_artifacts(
    out: &Path,
    tools: &EvidenceTools<'_>,
    transcript: Option<&harness::Transcript>,
) -> Result<(), String> {
    std::fs::create_dir_all(out).map_err(|error| format!("{}: {error}", out.display()))?;
    write_json(&out.join("evidence-scope.json"), &tools.scope().to_json())?;
    write_json(&out.join("exposure-trace.json"), &tools.ledger().to_json())?;
    if let Some(bundle) = tools.bundle() {
        write_json(&out.join("evidence-bundle.json"), bundle)?;
    }
    if let Some(transcript) = transcript {
        let value = serde_json::to_value(transcript).map_err(|error| error.to_string())?;
        write_json(&out.join("transcript.json"), &value)?;
    }
    Ok(())
}

fn read_json(path: &Path) -> Result<Value, String> {
    let text = std::fs::read_to_string(path)
        .map_err(|error| format!("could not read {}: {error}", path.display()))?;
    serde_json::from_str(&text).map_err(|error| format!("{} is not valid JSON: {error}", path.display()))
}

fn write_json(path: &Path, value: &Value) -> Result<(), String> {
    std::fs::write(path, format!("{}\n", pretty(value)))
        .map_err(|error| format!("could not write {}: {error}", path.display()))
}

fn pretty(value: &Value) -> String {
    serde_json::to_string_pretty(value).unwrap_or_else(|_| "{}".into())
}
