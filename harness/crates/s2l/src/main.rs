//! spec2lean command line entry point.
//!
//! Deliberately dependency-free argument parsing: this binary is the whole
//! runtime surface of the harness, and the point of the rewrite is that it
//! needs nothing on `PATH` to work.

mod pipeline;
mod verdict;

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::process::ExitCode;

use harness::provider::anthropic::{AnthropicConfig, AnthropicProvider};
use harness::provider::openai::{OpenAiConfig, OpenAiProvider};
use harness::provider::codex::{CodexConfig, CodexProvider};
use harness::provider::codex_mcp::McpCodexProvider;
use harness::{Effort, Provider, Session};
use serde_json::{Value, json};
use spec2lean_checking::{CheckInputs, check};
use spec2lean_evidence::{EvidenceScope, EvidenceTools, prompt};
use spec2lean_planning::{PlanningRequest, PlanningTools, ScopeResolver, Selector};
use spec2lean_semantics::{SemanticScope, SemanticTools};
use spec2lean_shared_core::{SharedCoreTools, collect_shared_requirements};
use spec2lean_translation::{TranslationScope, TranslationTools};
use spec2lean_specdb::{SpecDb, UnitId};

const USAGE: &str = "\
spec2lean harness

USAGE:
    s2l run              --database <PATH> --language <L> --version <V> [SELECTOR]
                         --out <DIR> [PROVIDER OPTIONS] [--lean <EXECUTABLE>]
                         (plan -> evidence -> semantics -> core -> translate -> check)

    s2l plan scope       --database <PATH> --language <L> --version <V> [SELECTOR]
    s2l plan prompt      --database <PATH> --language <L> --version <V> [SELECTOR]
    s2l plan replay      --database <PATH> --language <L> --version <V> [SELECTOR]
                         --calls <PATH> [--out <DIR>]
    s2l plan run         --database <PATH> --language <L> --version <V> [SELECTOR]
                         --out <DIR> [PROVIDER OPTIONS]

    s2l evidence prompt  --database <PATH> --plan <PATH> --unit <unit:ID>
    s2l evidence scope   --database <PATH> --plan <PATH> --unit <unit:ID>
    s2l evidence replay  --database <PATH> --plan <PATH> --unit <unit:ID> --calls <PATH> [--out <DIR>]
    s2l evidence run     --database <PATH> --plan <PATH> --unit <unit:ID> --out <DIR>
                         [PROVIDER OPTIONS]

    s2l semantics prompt --plan <PATH> --bundle <PATH> --unit <unit:ID>
    s2l semantics replay --plan <PATH> --bundle <PATH> --unit <unit:ID> --calls <PATH> [--out <DIR>]
    s2l semantics run    --plan <PATH> --bundle <PATH> --unit <unit:ID> --out <DIR>
                         [PROVIDER OPTIONS]

    s2l core prompt      --plan <PATH> --semantics <DIR>
    s2l core replay      --plan <PATH> --semantics <DIR> --calls <PATH> --out <DIR>
    s2l core run         --plan <PATH> --semantics <DIR> --out <DIR>
                         [PROVIDER OPTIONS] [--lean <EXECUTABLE>]

    s2l translate prompt --plan <PATH> --semantics <DIR> --group <NAME>
    s2l translate replay --plan <PATH> --semantics <DIR> --group <NAME> --calls <PATH> [--out <DIR>]
    s2l translate run    --plan <PATH> --semantics <DIR> --group <NAME> --out <DIR>
                         [PROVIDER OPTIONS] [--lean <EXECUTABLE>] [--core <DIR>]

    Any command accepts --verdict <WORKSPACE>, which appends one EDLab verdict
    line to <WORKSPACE>/.edlab/verdicts.jsonl and exits 0 or 1.

    s2l check            --database <PATH> --group-dir <DIR> --units <DIR>
                         [--core <DIR>]

    s2l lean check       --file <PATH> [--lean <EXECUTABLE>]

SELECTOR (exactly one; --full is the default):
    --instructions <a,b,c> | --family <NAME> | --subtree <node:ID> | --full

PROVIDER OPTIONS:
    [--provider anthropic|openai|codex|codex-mcp] [--model <ID>]
    [--timeout <S>]
    [--effort low|medium|high|xhigh|max] [--max-steps <N>]

ENVIRONMENT:
    ANTHROPIC_API_KEY / ANTHROPIC_BASE_URL    credentials for --provider anthropic
    OPENAI_API_KEY / OPENAI_BASE_URL          credentials for --provider openai

`replay` runs a scripted list of tool calls with no provider and no network,
which is how the tool set, the exposure ledger, and the deterministic validator
are exercised offline.
";

fn main() -> ExitCode {
    let arguments: Vec<String> = std::env::args().skip(1).collect();
    let outcome = run();
    // `--verdict <workspace>` makes this a drop-in EDLab tool: one JSON line
    // per run, and an exit code that says whether it passed.
    if let Some(index) = arguments.iter().position(|value| value == "--verdict")
        && let Some(workspace) = arguments.get(index + 1)
    {
        let phase = arguments.first().map(String::as_str).unwrap_or("spec2lean");
        let (passed, summary) = verdict::summarise(phase, &outcome);
        let value = verdict::verdict(&format!("spec2lean-{phase}"), passed, &summary, None);
        if let Err(error) = verdict::append(Path::new(workspace), &value) {
            eprintln!("warning: {error}");
        }
    }
    match outcome {
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
        ["run", rest @ ..] => {
            let flags = Flags::parse(rest)?;
            pipeline_run(&flags)
        }
        ["plan", command, rest @ ..] => {
            let flags = Flags::parse(rest)?;
            match *command {
                "scope" => plan_scope(&flags),
                "prompt" => plan_prompt(&flags),
                "replay" => plan_replay(&flags),
                "run" => plan_run(&flags),
                other => Err(format!("unknown plan command: {other}\n\n{USAGE}")),
            }
        }
        ["check", rest @ ..] => {
            let flags = Flags::parse(rest)?;
            logical_check(&flags)
        }
        ["lean", "check", rest @ ..] => {
            let flags = Flags::parse(rest)?;
            lean_check(&flags)
        }
        ["core", command, rest @ ..] => {
            let flags = Flags::parse(rest)?;
            match *command {
                "prompt" => core_prompt(&flags),
                "replay" => core_replay(&flags),
                "run" => core_run(&flags),
                other => Err(format!("unknown core command: {other}\n\n{USAGE}")),
            }
        }
        ["translate", command, rest @ ..] => {
            let flags = Flags::parse(rest)?;
            match *command {
                "prompt" => translate_prompt(&flags),
                "scope" => translate_scope(&flags),
                "replay" => translate_replay(&flags),
                "run" => translate_run(&flags),
                other => Err(format!("unknown translate command: {other}\n\n{USAGE}")),
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
    let mut session = Session::new(provider.as_ref(), prompt::system_prompt())
        .with_max_steps(max_steps(flags)?);
    let (outcome, transcript) = session.stage(user, &mut tools);

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
        "codex" | "codex-mcp" => {
            let mut config = CodexConfig {
                model,
                effort,
                ..CodexConfig::default()
            };
            if let Some(value) = flags.optional("timeout") {
                config.timeout_seconds = value
                    .parse()
                    .map_err(|_| format!("--timeout must be whole seconds, found {value:?}"))?;
            }
            // One long-lived MCP server instead of a process per turn, which
            // also replaces codex's own preamble rather than re-sending it.
            if flags.optional("provider") == Some("codex-mcp") {
                Box::new(McpCodexProvider::new(config))
            } else {
                Box::new(CodexProvider::new(config))
            }
        }
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

    let mut session = Session::new(provider.as_ref(), semantic_prompt::system_prompt())
        .with_max_steps(max_steps(flags)?);
    let (outcome, transcript) = session.stage(user, &mut tools);

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

/// Everything the shared core must represent for this plan.
fn core_context(flags: &Flags) -> Result<(Value, spec2lean_shared_core::SharedCoreTools), String> {
    let plan: Value = read_json(&flags.path("plan")?)?;
    let semantics = load_semantics(&flags.path("semantics")?)?;
    let requirements = collect_shared_requirements(&plan, &semantics, None)
        .map_err(|error| error.to_string())?;
    if requirements.is_empty() {
        return Err("this plan has no shared prerequisites; no core is needed".into());
    }
    let out = flags
        .optional("out")
        .map(PathBuf::from)
        .unwrap_or_else(std::env::temp_dir);
    let generator = match flags.optional("provider") {
        None => json!({"provider": "replay", "model": "none"}),
        Some(_) => json!({"provider": flags.optional("provider").unwrap_or("anthropic"),
                          "model": flags.optional("model").unwrap_or("default")}),
    };
    let tools = SharedCoreTools::new(
        requirements,
        plan.get("language").and_then(Value::as_str).unwrap_or_default(),
        plan.get("version").and_then(Value::as_str).unwrap_or_default(),
        plan.get("sourceDatabaseDigest").and_then(Value::as_str).unwrap_or_default(),
        generator,
        out.join("lean"),
        flags.optional("lean").unwrap_or("lean"),
    );
    Ok((plan, tools))
}

fn core_prompt(flags: &Flags) -> Result<(), String> {
    use spec2lean_shared_core::prompt as core_prompt_module;
    let (_plan, tools) = core_context(flags)?;
    println!(
        "=== system ===\n{}\n\n=== user ===\n{}",
        core_prompt_module::system_prompt(),
        core_prompt_module::user_prompt(tools.requirements())
    );
    Ok(())
}

fn core_replay(flags: &Flags) -> Result<(), String> {
    use harness::ToolSet;
    let (_plan, mut tools) = core_context(flags)?;
    let out = flags.path("out")?;
    let calls: Value = read_json(&flags.path("calls")?)?;
    let calls = calls.as_array().ok_or("the calls file must contain a JSON array")?;
    for (index, call) in calls.iter().enumerate() {
        let name = call.get("tool").and_then(Value::as_str).unwrap_or("submit_core");
        let input = call.get("input").cloned().unwrap_or_else(|| json!({}));
        let mut text = tools.call(name, &input).to_text();
        if let Some(extra) = tools.after_tool_call() {
            text.push('\n');
            text.push_str(&extra);
        }
        println!("--- {index}: {name} ---\n{text}");
    }
    write_core_artifacts(&out, &tools, None)?;
    if tools.finished() {
        println!("\ncore frozen after {} build(s)", tools.build_count());
        Ok(())
    } else {
        Err("the scripted calls did not freeze a core".into())
    }
}

fn core_run(flags: &Flags) -> Result<(), String> {
    use spec2lean_shared_core::prompt as core_prompt_module;
    let (_plan, mut tools) = core_context(flags)?;
    let out = flags.path("out")?;
    let provider = provider(flags)?;
    let user = core_prompt_module::user_prompt(tools.requirements());
    let mut session = Session::new(provider.as_ref(), core_prompt_module::system_prompt())
        .with_max_steps(max_steps(flags)?);
    let (outcome, transcript) = session.stage(user, &mut tools);
    write_core_artifacts(&out, &tools, Some(&transcript))?;
    match outcome {
        Ok(()) => {
            let frozen = tools.frozen().expect("frozen");
            println!(
                "core {} frozen in {} steps after {} build(s): module {}",
                frozen.core_run_id, transcript.steps, tools.build_count(), frozen.lean_module
            );
            Ok(())
        }
        Err(error) => Err(format!("{error} (artifacts written to {})", out.display())),
    }
}

fn write_core_artifacts(
    out: &Path,
    tools: &SharedCoreTools,
    transcript: Option<&harness::Transcript>,
) -> Result<(), String> {
    std::fs::create_dir_all(out).map_err(|error| format!("{}: {error}", out.display()))?;
    if let Some(frozen) = tools.frozen() {
        write_json(&out.join("shared-core-manifest.json"), &frozen.manifest)?;
    }
    if let Some(transcript) = transcript {
        let value = serde_json::to_value(transcript).map_err(|error| error.to_string())?;
        write_json(&out.join("transcript.json"), &value)?;
    }
    Ok(())
}

/// Load a frozen core from a directory produced by `s2l core`.
fn load_core(flags: &Flags) -> Result<Option<(Value, PathBuf)>, String> {
    let Some(directory) = flags.optional("core") else {
        return Ok(None);
    };
    let directory = PathBuf::from(directory);
    let manifest = read_json(&directory.join("shared-core-manifest.json"))?;
    let module = manifest
        .get("leanModule")
        .and_then(Value::as_str)
        .ok_or("the core manifest has no leanModule")?;
    let source = directory
        .join("lean")
        .join(module.split('.').collect::<PathBuf>())
        .with_extension("lean");
    if !source.is_file() {
        return Err(format!("the core source is missing: {}", source.display()));
    }
    Ok(Some((manifest, source)))
}

/// Build the request from flags. Exactly one selector may be given; the sum
/// type makes a contradictory request unrepresentable rather than resolved by
/// precedence.
fn planning_request(flags: &Flags) -> Result<PlanningRequest, String> {
    let mut selectors = Vec::new();
    if let Some(value) = flags.optional("instructions") {
        selectors.push(Selector::ExactInstructions(
            value.split(',').map(|item| item.trim().to_string()).collect(),
        ));
    }
    if let Some(value) = flags.optional("family") {
        selectors.push(Selector::InstructionFamily(value.to_string()));
    }
    if let Some(value) = flags.optional("subtree") {
        selectors.push(Selector::SourceSubtree(
            spec2lean_specdb::NodeId::parse(value).map_err(|error| error.to_string())?,
        ));
    }
    if flags.optional("full").is_some() {
        selectors.push(Selector::FullSpecification);
    }
    let selector = match selectors.len() {
        0 => Selector::FullSpecification,
        1 => selectors.remove(0),
        _ => {
            return Err(
                "give exactly one of --instructions, --family, --subtree, or --full".into(),
            );
        }
    };
    PlanningRequest::new(flags.get("language")?, flags.get("version")?, selector)
        .map_err(|error| error.to_string())
}

/// Open the index, resolve the request, and derive the plan run identity.
fn planning_context(
    flags: &Flags,
) -> Result<(SpecDb, spec2lean_planning::ResolvedScope, String, String), String> {
    let db = SpecDb::open(&flags.path("database")?).map_err(|error| error.to_string())?;
    let request = planning_request(flags)?;
    let scope = ScopeResolver::new(&db)
        .resolve(&request)
        .map_err(|error| error.to_string())?;
    let digest = db.semantic_digest().map_err(|error| error.to_string())?;
    let started_at = flags
        .optional("created-at")
        .map(str::to_string)
        .unwrap_or_else(harness::clock::utc_now_iso);
    // Identity binds the request, the exact index, and when it ran.
    let plan_run_id = flags.optional("plan-run-id").map(str::to_string).unwrap_or_else(|| {
        spec2lean_specdb::stable_id(
            "plan",
            &[
                &request.language.to_lowercase(),
                &request.version,
                &digest,
                &started_at,
            ],
            24,
        )
    });
    Ok((db, scope, plan_run_id, digest))
}

fn plan_scope(flags: &Flags) -> Result<(), String> {
    let (_db, scope, _, _) = planning_context(flags)?;
    println!("{}", pretty(&scope.to_json()));
    Ok(())
}

fn plan_prompt(flags: &Flags) -> Result<(), String> {
    use spec2lean_planning::prompt as planning_prompt;
    let (_db, scope, _, _) = planning_context(flags)?;
    println!(
        "=== system ===\n{}\n\n=== user ===\n{}",
        planning_prompt::system_prompt(),
        planning_prompt::user_prompt(&scope)
    );
    Ok(())
}

fn plan_replay(flags: &Flags) -> Result<(), String> {
    use harness::ToolSet;

    let (db, scope, plan_run_id, digest) = planning_context(flags)?;
    let calls: Value = read_json(&flags.path("calls")?)?;
    let calls = calls
        .as_array()
        .ok_or("the calls file must contain a JSON array")?;
    let mut tools = PlanningTools::new(&db, scope, plan_run_id, digest);

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
        write_plan_artifacts(Path::new(out), &tools, None)?;
    }
    if tools.finished() {
        println!("\nplan accepted");
        Ok(())
    } else {
        Err("the scripted calls did not produce an accepted plan".into())
    }
}

fn plan_run(flags: &Flags) -> Result<(), String> {
    use spec2lean_planning::prompt as planning_prompt;

    let (db, scope, plan_run_id, digest) = planning_context(flags)?;
    let out = flags.path("out")?;
    let provider = provider(flags)?;
    let user = planning_prompt::user_prompt(&scope);
    let mut tools = PlanningTools::new(&db, scope, plan_run_id, digest);

    let mut session = Session::new(provider.as_ref(), planning_prompt::system_prompt())
        .with_max_steps(max_steps(flags)?);
    let (outcome, transcript) = session.stage(user, &mut tools);

    write_plan_artifacts(&out, &tools, Some(&transcript))?;
    match outcome {
        Ok(()) => {
            let plan = tools.plan().expect("accepted");
            println!(
                "plan {} accepted in {} steps: {} unit(s), {} group(s), {}",
                plan["planRunId"].as_str().unwrap_or_default(),
                transcript.steps,
                plan["requestedUnits"].as_array().map_or(0, Vec::len),
                plan["translationGroups"].as_array().map_or(0, Vec::len),
                plan["graphStatus"].as_str().unwrap_or("UNKNOWN"),
            );
            Ok(())
        }
        Err(error) => Err(format!("{error} (artifacts written to {})", out.display())),
    }
}

fn write_plan_artifacts(
    out: &Path,
    tools: &PlanningTools<'_>,
    transcript: Option<&harness::Transcript>,
) -> Result<(), String> {
    std::fs::create_dir_all(out).map_err(|error| format!("{}: {error}", out.display()))?;
    write_json(&out.join("planning-scope.json"), &tools.scope().to_json())?;
    if let Some(plan) = tools.plan() {
        write_json(&out.join("plan.json"), plan)?;
    }
    if let Some(transcript) = transcript {
        let value = serde_json::to_value(transcript).map_err(|error| error.to_string())?;
        write_json(&out.join("transcript.json"), &value)?;
    }
    Ok(())
}

/// The whole pipeline, one phase at a time.
///
/// Composed from the same functions the individual commands use, so there is
/// one implementation of each phase. It stops a *unit* at its first failure and
/// keeps going with the others: a run that formalized three of four units is
/// more useful than one that reports only that it failed.
fn pipeline_run(flags: &Flags) -> Result<(), String> {
    use pipeline::{
        Layout, PhaseRecord, empty_manifest, processable_units, ready_groups, write_manifest,
    };
    use spec2lean_evidence::prompt as evidence_prompt;
    use spec2lean_semantics::prompt as semantic_prompt;
    use spec2lean_shared_core::prompt as core_prompt_module;
    use spec2lean_translation::prompt as translation_prompt;

    let layout = Layout::new(flags.path("out")?);
    let started_at = harness::clock::utc_now_iso();
    let mut manifest = empty_manifest(&layout.root, started_at.clone());
    let lean = flags.optional("lean").unwrap_or("lean").to_string();
    let steps = max_steps(flags)?;

    // ---- Phase 2 ---------------------------------------------------------
    let (db, scope, plan_run_id, digest) = planning_context(flags)?;
    let provider = provider(flags)?;
    let mut planner = PlanningTools::new(&db, scope, plan_run_id, digest.clone());
    let user = spec2lean_planning::prompt::user_prompt(planner.scope());
    let (outcome, transcript) =
        Session::new(provider.as_ref(), spec2lean_planning::prompt::system_prompt())
            .with_max_steps(steps)
            .stage(user, &mut planner);
    write_plan_artifacts(&layout.plan(), &planner, Some(&transcript))?;
    if let Err(error) = outcome {
        manifest.phases.push(PhaseRecord::failed("plan", "request", error.to_string()));
        manifest.status = "FAIL";
        manifest.finished_at = harness::clock::utc_now_iso();
        write_manifest(&layout, &manifest)?;
        println!("{}", manifest.summary());
        return Err("planning failed".into());
    }
    let plan = planner.plan().expect("accepted").clone();
    manifest
        .phases
        .push(PhaseRecord::ok("plan", "request").with_transcript(&transcript));

    let (ordered, excluded) = processable_units(&plan);
    for unit_id in &excluded {
        manifest.phases.push(PhaseRecord::skipped(
            "unit",
            unit_id,
            "inside or downstream of a dependency cycle the plan could not order",
        ));
    }

    // ---- Phases 3 and 4, per unit ----------------------------------------
    //
    // One session per phase, not one per unit. Every unit under a phase runs
    // under the same instructions and the same tool schemas, so a provider
    // that can resume a conversation pays for them once instead of once per
    // unit. The two phases stay separate sessions on purpose: semantics must
    // extract from the evidence bundle it was handed, and a session that had
    // also gathered that evidence would be extracting from memory of the
    // specification instead.
    let mut evidence_session =
        Session::new(provider.as_ref(), evidence_prompt::system_prompt()).with_max_steps(steps);
    let mut semantic_session =
        Session::new(provider.as_ref(), semantic_prompt::system_prompt()).with_max_steps(steps);
    let mut bundles: BTreeMap<String, Value> = BTreeMap::new();
    let mut semantics: BTreeMap<String, Value> = BTreeMap::new();
    for unit_id in &ordered {
        let directory = layout.unit(unit_id);
        let parsed = match UnitId::parse(unit_id) {
            Ok(parsed) => parsed,
            Err(error) => {
                manifest.phases.push(PhaseRecord::failed("evidence", unit_id, error.to_string()));
                continue;
            }
        };
        let unit_scope = match EvidenceScope::from_plan(&plan, &parsed) {
            Ok(scope) => scope,
            Err(error) => {
                manifest.phases.push(PhaseRecord::failed("evidence", unit_id, error.to_string()));
                continue;
            }
        };
        let user = match evidence_prompt::user_prompt(&db, &unit_scope) {
            Ok(user) => user,
            Err(error) => {
                manifest.phases.push(PhaseRecord::failed("evidence", unit_id, error.to_string()));
                continue;
            }
        };
        let mut tools = match EvidenceTools::new(&db, unit_scope) {
            Ok(tools) => tools,
            Err(error) => {
                manifest.phases.push(PhaseRecord::failed("evidence", unit_id, error.to_string()));
                continue;
            }
        };
        let (outcome, transcript) = evidence_session.stage(user, &mut tools);
        write_artifacts(&directory, &tools, Some(&transcript))?;
        let Ok(()) = outcome else {
            manifest.phases.push(PhaseRecord::failed(
                "evidence",
                unit_id,
                outcome.unwrap_err().to_string(),
            ));
            continue;
        };
        let bundle = tools.bundle().expect("accepted").clone();
        manifest
            .phases
            .push(PhaseRecord::ok("evidence", unit_id).with_transcript(&transcript));

        let semantic_scope = match SemanticScope::from_inputs(
            &plan,
            &bundle,
            &parsed,
            &harness::clock::utc_now_iso(),
        ) {
            Ok(scope) => scope,
            Err(error) => {
                manifest.phases.push(PhaseRecord::failed("semantics", unit_id, error.to_string()));
                bundles.insert(unit_id.clone(), bundle);
                continue;
            }
        };
        let user = semantic_prompt::user_prompt(&semantic_scope, &bundle);
        let mut tools = SemanticTools::new(
            semantic_scope,
            bundle.clone(),
            extractor(provider.as_ref()),
        );
        let (outcome, transcript) = semantic_session.stage(user, &mut tools);
        write_semantic_artifacts(&directory, &tools, Some(&transcript))?;
        bundles.insert(unit_id.clone(), bundle);
        match outcome {
            Ok(()) => {
                let artifact = tools.artifact().expect("accepted").clone();
                // An honest "the evidence does not settle this" is a real
                // outcome, but nothing downstream can translate it.
                if artifact["outcome"] == json!("SUCCESS") {
                    semantics.insert(unit_id.clone(), artifact);
                    manifest
                        .phases
                        .push(PhaseRecord::ok("semantics", unit_id).with_transcript(&transcript));
                } else {
                    manifest.phases.push(PhaseRecord::failed(
                        "semantics",
                        unit_id,
                        "INSUFFICIENT_EVIDENCE: the retrieved evidence does not settle this unit",
                    ));
                }
            }
            Err(error) => manifest
                .phases
                .push(PhaseRecord::failed("semantics", unit_id, error.to_string())),
        }
    }

    // ---- the shared core -------------------------------------------------
    let requirements =
        collect_shared_requirements(&plan, &semantics, None).map_err(|error| error.to_string())?;
    let mut core: Option<(Value, PathBuf)> = None;
    if !requirements.is_empty() {
        let count = requirements.len();
        let mut tools = SharedCoreTools::new(
            requirements,
            plan.get("language").and_then(Value::as_str).unwrap_or_default(),
            plan.get("version").and_then(Value::as_str).unwrap_or_default(),
            &digest,
            extractor(provider.as_ref()),
            layout.core().join("lean"),
            &lean,
        );
        let user = core_prompt_module::user_prompt(tools.requirements());
        let (outcome, transcript) =
            Session::new(provider.as_ref(), core_prompt_module::system_prompt())
                .with_max_steps(steps)
                .stage(user, &mut tools);
        write_core_artifacts(&layout.core(), &tools, Some(&transcript))?;
        match outcome {
            Ok(()) => {
                let frozen = tools.frozen().expect("frozen");
                let source = layout
                    .core()
                    .join("lean")
                    .join(frozen.lean_module.split('.').collect::<PathBuf>())
                    .with_extension("lean");
                core = Some((frozen.manifest.clone(), source));
                manifest.phases.push(
                    PhaseRecord::ok("core", format!("{count} shared concept(s)"))
                        .with_transcript(&transcript),
                );
            }
            Err(error) => {
                manifest.phases.push(PhaseRecord::failed("core", "shared concepts", error.to_string()));
                manifest.status = "FAIL";
                manifest.finished_at = harness::clock::utc_now_iso();
                write_manifest(&layout, &manifest)?;
                println!("{}", manifest.summary());
                return Err("the shared core could not be frozen".into());
            }
        }
    }

    // ---- Phases 5 and 6, per group ---------------------------------------
    //
    // One session for every group, for the same reason as the unit phases. The
    // compiler still runs per submission: `after_tool_call` is bound to the
    // tool set, and each group gets its own.
    let mut translation_session =
        Session::new(provider.as_ref(), translation_prompt::system_prompt()).with_max_steps(steps);
    let (ready, blocked) = ready_groups(&plan, &semantics);
    for (group, missing) in blocked {
        manifest.phases.push(PhaseRecord::skipped(
            "translate",
            group,
            format!("waiting on {}", missing.join(", ")),
        ));
    }
    for (group, members) in ready {
        let directory = layout.group(&group);
        let group_semantics: BTreeMap<String, Value> = members
            .iter()
            .filter_map(|unit_id| Some((unit_id.clone(), semantics.get(unit_id)?.clone())))
            .collect();
        let scope = match TranslationScope::from_inputs(
            &plan,
            &group,
            &group_semantics,
            &harness::clock::utc_now_iso(),
            core.as_ref().map(|(manifest, _)| manifest),
        ) {
            Ok(scope) => scope,
            Err(error) => {
                manifest.phases.push(PhaseRecord::failed("translate", &group, error.to_string()));
                continue;
            }
        };
        let user = translation_prompt::user_prompt(&scope, &group_semantics);
        let mut tools = TranslationTools::new(
            scope,
            directory.join("lean"),
            &lean,
            extractor(provider.as_ref()),
        );
        if let Some((core_manifest, source)) = &core {
            tools = tools.with_shared_core(
                core_manifest["leanModule"].as_str().unwrap_or_default(),
                source.clone(),
            );
        }
        let (outcome, transcript) = translation_session.stage(user, &mut tools);
        write_translation_artifacts(&directory, &tools, Some(&transcript))?;
        let Ok(()) = outcome else {
            manifest.phases.push(PhaseRecord::failed(
                "translate",
                &group,
                outcome.unwrap_err().to_string(),
            ));
            manifest.status = "FAIL";
            continue;
        };
        // The translator may have reported that the semantics do not determine
        // a formalization. That ends the group without a translation to check.
        if let Some(report) = tools.underdetermined() {
            let claims: Vec<String> = report["underdeterminedClaims"]
                .as_array()
                .map(Vec::as_slice)
                .unwrap_or_default()
                .iter()
                .filter_map(|item| {
                    Some(format!(
                        "{}/{}",
                        item.get("unitId")?.as_str()?,
                        item.get("claimId")?.as_str()?
                    ))
                })
                .collect();
            manifest.phases.push(PhaseRecord::failed(
                "translate",
                &group,
                format!("UNDERDETERMINED: {}", claims.join(", ")),
            ));
            manifest.status = "FAIL";
            continue;
        }
        manifest
            .phases
            .push(PhaseRecord::ok("translate", &group).with_transcript(&transcript));

        let group_manifest = tools.manifest().expect("accepted").clone();
        let lean_file = group_manifest["leanFile"].as_str().unwrap_or_default();
        let source = std::fs::read_to_string(directory.join("lean").join(lean_file))
            .map_err(|error| error.to_string())?;
        let core_source = match &core {
            None => None,
            Some((_, path)) => Some(std::fs::read_to_string(path).map_err(|e| e.to_string())?),
        };
        let report = check(
            &CheckInputs {
                bundles: &bundles,
                semantics: &group_semantics,
                manifest: &group_manifest,
                core_manifest: core.as_ref().map(|(manifest, _)| manifest),
                source: &source,
                core_source: core_source.as_deref(),
            },
            &flags.path("database")?,
        )?;
        write_json(
            &directory.join("check-result.json"),
            &serde_json::to_value(&report).map_err(|error| error.to_string())?,
        )?;
        if report.passed() {
            manifest.phases.push(PhaseRecord::ok("check", &group));
        } else {
            manifest.phases.push(PhaseRecord::failed("check", &group, report.summary()));
            manifest.status = "FAIL";
        }
    }

    if manifest.phases.iter().any(|record| record.status == "FAIL") {
        manifest.status = "FAIL";
    }
    manifest.usage = pipeline::total_usage(&manifest.phases);
    manifest.finished_at = harness::clock::utc_now_iso();
    write_manifest(&layout, &manifest)?;
    println!("{}", manifest.summary());
    if manifest.status == "PASS" {
        Ok(())
    } else {
        Err("the pipeline did not complete every phase".into())
    }
}

/// Load every Phase-3 bundle under a directory, keyed by unit.
fn load_bundles(root: &Path) -> Result<BTreeMap<String, Value>, String> {
    let mut found = BTreeMap::new();
    let mut stack = vec![root.to_path_buf()];
    while let Some(directory) = stack.pop() {
        let entries = std::fs::read_dir(&directory)
            .map_err(|error| format!("could not read {}: {error}", directory.display()))?;
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_dir() {
                stack.push(path);
                continue;
            }
            if path.file_name().and_then(|value| value.to_str()) != Some("evidence-bundle.json") {
                continue;
            }
            let value = read_json(&path)?;
            if let Some(unit_id) = value
                .get("unit")
                .and_then(|unit| unit.get("unitId"))
                .and_then(Value::as_str)
            {
                found.insert(unit_id.to_string(), value);
            }
        }
    }
    if found.is_empty() {
        return Err(format!("no Phase-3 bundles found under {}", root.display()));
    }
    Ok(found)
}

/// Phase 6: check a finished group against its inputs and against the index.
fn logical_check(flags: &Flags) -> Result<(), String> {
    let group_dir = flags.path("group-dir")?;
    let units = flags.path("units")?;
    let manifest = read_json(&group_dir.join("translation-manifest.json"))?;
    let lean_file = manifest
        .get("leanFile")
        .and_then(Value::as_str)
        .ok_or("the translation manifest has no leanFile")?;
    let source = std::fs::read_to_string(group_dir.join("lean").join(lean_file))
        .map_err(|error| format!("could not read the group's Lean: {error}"))?;

    let core = load_core(flags)?;
    let core_source = match &core {
        None => None,
        Some((manifest, path)) => {
            let _ = manifest;
            Some(
                std::fs::read_to_string(path)
                    .map_err(|error| format!("could not read the core's Lean: {error}"))?,
            )
        }
    };

    let report = check(
        &CheckInputs {
            bundles: &load_bundles(&units)?,
            semantics: &load_semantics(&units)?,
            manifest: &manifest,
            core_manifest: core.as_ref().map(|(manifest, _)| manifest),
            source: &source,
            core_source: core_source.as_deref(),
        },
        &flags.path("database")?,
    )?;

    write_json(
        &group_dir.join("check-result.json"),
        &serde_json::to_value(&report).map_err(|error| error.to_string())?,
    )?;
    println!("{}", report.summary());
    if report.passed() {
        Ok(())
    } else {
        // Carry the first line of the report, so a one-line verdict still says
        // what went wrong rather than only that something did.
        // Skip the overall header and report the check that actually failed.
        Err(report
            .summary()
            .lines()
            .skip(1)
            .find(|line| line.contains("FAIL"))
            .unwrap_or("logical checks failed")
            .trim()
            .to_string())
    }
}

/// Load every Phase-4 artifact under a directory, keyed by unit ID.
///
/// Accepts the layout `s2l semantics run` writes: one directory per unit, each
/// containing `semantic-artifact.json`.
fn load_semantics(root: &Path) -> Result<BTreeMap<String, Value>, String> {
    let mut found = BTreeMap::new();
    let mut stack = vec![root.to_path_buf()];
    while let Some(directory) = stack.pop() {
        let entries = std::fs::read_dir(&directory)
            .map_err(|error| format!("could not read {}: {error}", directory.display()))?;
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_dir() {
                stack.push(path);
                continue;
            }
            if path.extension().and_then(|value| value.to_str()) != Some("json") {
                continue;
            }
            let Ok(value) = read_json(&path) else { continue };
            if value.get("phase").and_then(Value::as_str) != Some("SEMANTIC_EXTRACTOR") {
                continue;
            }
            let Some(unit_id) = value
                .get("unit")
                .and_then(|unit| unit.get("unitId"))
                .and_then(Value::as_str)
                .map(str::to_string)
            else {
                continue;
            };
            // Two different artifacts for one unit would make the group's
            // identity ambiguous; identical duplicates are harmless.
            if let Some(existing) = found.insert(unit_id.clone(), value.clone())
                && existing != value
            {
                return Err(format!(
                    "{} contains conflicting semantic artifacts for {unit_id}",
                    root.display()
                ));
            }
        }
    }
    if found.is_empty() {
        return Err(format!(
            "no Phase-4 semantic artifacts found under {}",
            root.display()
        ));
    }
    Ok(found)
}

type TranslationContext = (
    TranslationScope,
    BTreeMap<String, Value>,
    Option<(Value, PathBuf)>,
);

fn translation_context(flags: &Flags) -> Result<TranslationContext, String> {
    let plan: Value = read_json(&flags.path("plan")?)?;
    let all = load_semantics(&flags.path("semantics")?)?;
    let group = flags.get("group")?;
    // A group receives exactly its own units' artifacts.
    let members: Vec<String> = spec2lean_translation::grouped_units(&plan)
        .map_err(|error| error.to_string())?
        .get(group)
        .map(|units| {
            units
                .iter()
                .filter_map(|unit| unit.get("unitId")?.as_str().map(str::to_string))
                .collect()
        })
        .ok_or_else(|| format!("translation group is not present in the plan: {group}"))?;
    let semantics: BTreeMap<String, Value> = members
        .iter()
        .filter_map(|unit_id| Some((unit_id.clone(), all.get(unit_id)?.clone())))
        .collect();
    let created_at = flags
        .optional("created-at")
        .map(str::to_string)
        .unwrap_or_else(harness::clock::utc_now_iso);
    let core = load_core(flags)?;
    let scope = TranslationScope::from_inputs(
        &plan,
        group,
        &semantics,
        &created_at,
        core.as_ref().map(|(manifest, _)| manifest),
    )
    .map_err(|error| error.to_string())?;
    Ok((scope, semantics, core))
}

fn translate_scope(flags: &Flags) -> Result<(), String> {
    let (scope, _, _) = translation_context(flags)?;
    println!("{}", pretty(&scope.to_json()));
    Ok(())
}

fn translate_prompt(flags: &Flags) -> Result<(), String> {
    use spec2lean_translation::prompt as translation_prompt;
    let (scope, semantics, _) = translation_context(flags)?;
    println!(
        "=== system ===\n{}\n\n=== user ===\n{}",
        translation_prompt::system_prompt(),
        translation_prompt::user_prompt(&scope, &semantics)
    );
    Ok(())
}

fn translate_replay(flags: &Flags) -> Result<(), String> {
    use harness::ToolSet;

    let (scope, _, core) = translation_context(flags)?;
    let calls: Value = read_json(&flags.path("calls")?)?;
    let calls = calls
        .as_array()
        .ok_or("the calls file must contain a JSON array")?;
    let out = flags
        .optional("out")
        .map(PathBuf::from)
        .unwrap_or_else(std::env::temp_dir);
    let mut tools = TranslationTools::new(
        scope,
        out.join("lean"),
        flags.optional("lean").unwrap_or("lean"),
        json!({"provider": "replay", "model": "none"}),
    );
    if let Some((manifest, source)) = &core {
        tools = tools.with_shared_core(
            manifest["leanModule"].as_str().unwrap_or_default(),
            source.clone(),
        );
    }

    for (index, call) in calls.iter().enumerate() {
        let name = call
            .get("tool")
            .and_then(Value::as_str)
            .unwrap_or("submit_translation");
        let input = call.get("input").cloned().unwrap_or_else(|| json!({}));
        let mut text = tools.call(name, &input).to_text();
        // The harness's own deterministic step, exactly as the loop runs it.
        if let Some(extra) = tools.after_tool_call() {
            text.push('\n');
            text.push_str(&extra);
        }
        println!("--- {index}: {name} ---\n{text}");
    }

    write_translation_artifacts(&out, &tools, None)?;
    if tools.underdetermined().is_some() {
        println!("\nreported UNDERDETERMINED; see underdetermined.json");
        return Ok(());
    }
    if tools.finished() {
        println!("\ntranslation accepted after {} build(s)", tools.build_count());
        Ok(())
    } else {
        Err("the scripted calls did not produce an accepted translation".into())
    }
}

fn translate_run(flags: &Flags) -> Result<(), String> {
    use spec2lean_translation::prompt as translation_prompt;

    let (scope, semantics, core) = translation_context(flags)?;
    let out = flags.path("out")?;
    let provider = provider(flags)?;
    let user = translation_prompt::user_prompt(&scope, &semantics);
    let mut tools = TranslationTools::new(
        scope,
        out.join("lean"),
        flags.optional("lean").unwrap_or("lean"),
        extractor(provider.as_ref()),
    );
    if let Some((manifest, source)) = &core {
        tools = tools.with_shared_core(
            manifest["leanModule"].as_str().unwrap_or_default(),
            source.clone(),
        );
    }

    let mut session = Session::new(provider.as_ref(), translation_prompt::system_prompt())
        .with_max_steps(max_steps(flags)?);
    let (outcome, transcript) = session.stage(user, &mut tools);

    write_translation_artifacts(&out, &tools, Some(&transcript))?;
    if tools.underdetermined().is_some() {
        println!("reported UNDERDETERMINED; see underdetermined.json");
        return Ok(());
    }
    match outcome {
        Ok(()) => {
            println!(
                "translation accepted in {} steps after {} build(s) ({} cached input tokens)",
                transcript.steps,
                tools.build_count(),
                transcript.usage.cache_read_input_tokens
            );
            Ok(())
        }
        Err(error) => Err(format!("{error} (artifacts written to {})", out.display())),
    }
}

fn write_translation_artifacts(
    out: &Path,
    tools: &TranslationTools,
    transcript: Option<&harness::Transcript>,
) -> Result<(), String> {
    std::fs::create_dir_all(out).map_err(|error| format!("{}: {error}", out.display()))?;
    write_json(&out.join("translation-scope.json"), &tools.scope().to_json())?;
    if let Some(manifest) = tools.manifest() {
        write_json(&out.join("translation-manifest.json"), manifest)?;
    }
    // An honest "these semantics do not determine a formalization" is a real
    // result and is written as one, not folded into a generic failure.
    if let Some(report) = tools.underdetermined() {
        write_json(&out.join("underdetermined.json"), report)?;
    }
    if let Some(transcript) = transcript {
        let value = serde_json::to_value(transcript).map_err(|error| error.to_string())?;
        write_json(&out.join("transcript.json"), &value)?;
    }
    Ok(())
}

/// Compile one Lean file and report structured diagnostics. Useful on its own,
/// and it exercises exactly the code path the translation loop uses.
fn lean_check(flags: &Flags) -> Result<(), String> {
    let file = flags.path("file")?;
    let result = spec2lean_lean::run_build(&file, &[], flags.optional("lean").unwrap_or("lean"));
    println!("{}", pretty(&serde_json::to_value(&result).map_err(|e| e.to_string())?));
    if result.passed() {
        Ok(())
    } else {
        Err(result.summary(12))
    }
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
