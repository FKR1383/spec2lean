//! Phase 5 behaviour, including the compile-repair loop against real `lean`.

use std::collections::BTreeMap;
use std::path::PathBuf;

use harness::ToolSet;
use serde_json::{Value, json};
use spec2lean_translation::{TranslationScope, TranslationTools};

fn lean_available() -> bool {
    std::process::Command::new("lean")
        .arg("--version")
        .output()
        .is_ok_and(|output| output.status.success())
}

struct Work(PathBuf);

impl Work {
    fn new(name: &str) -> Self {
        let path = std::env::temp_dir().join(format!("s2l-tr-{name}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&path);
        std::fs::create_dir_all(&path).expect("workspace");
        Self(path)
    }
}

impl Drop for Work {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}

fn unit() -> Value {
    json!({"unitId": "unit:add", "name": "add", "sourceNodeIds": ["node:x"]})
}

fn plan() -> Value {
    json!({
        "planRunId": "plan:test",
        "language": "synthetic",
        "version": "1.0",
        "requestedUnits": [unit()],
        "translationGroups": [{"name": "arithmetic", "unitIds": ["unit:add"]}],
    })
}

fn semantics() -> BTreeMap<String, Value> {
    BTreeMap::from([(
        "unit:add".to_string(),
        json!({
            "phase": "SEMANTIC_EXTRACTOR",
            "outcome": "SUCCESS",
            "planRunId": "plan:test",
            "language": "synthetic",
            "version": "1.0",
            "unit": unit(),
            "runId": "semantic-run:abc",
            "semantics": {
                "claims": [
                    {"claimId": "claim:1", "kind": "SOURCE_FACT",
                     "statement": "add computes the sum of two operands"},
                ],
            },
        }),
    )])
}

fn scope() -> TranslationScope {
    TranslationScope::from_inputs(&plan(), "arithmetic", &semantics(), "2026-01-01T00:00:00.000000Z")
        .expect("scope resolves")
}

fn make_tools(work: &Work) -> TranslationTools {
    TranslationTools::new(
        scope(),
        work.0.clone(),
        "lean",
        json!({"provider": "test", "model": "test"}),
    )
}

fn mapping() -> Value {
    json!([{
        "declaration": "Spec2Lean.Synthetic.Arithmetic.add",
        "role": "OPERATION",
        "claimRefs": [{"unitId": "unit:add", "claimId": "claim:1"}],
    }])
}

fn submit(tools: &mut TranslationTools, source: &str) -> String {
    let outcome = tools.call(
        "submit_translation",
        &json!({"leanSource": source, "declarations": mapping()}),
    );
    let mut text = outcome.to_text();
    // The harness runs the compiler here, exactly as the session loop does.
    if let Some(extra) = tools.after_tools() {
        text.push('\n');
        text.push_str(&extra);
    }
    text
}

const GOOD: &str = "namespace Spec2Lean.Synthetic.Arithmetic\n\ndef add (a b : Nat) : Nat := a + b\n\nend Spec2Lean.Synthetic.Arithmetic\n";
const BROKEN: &str = "namespace Spec2Lean.Synthetic.Arithmetic\n\ndef add (a b : Nat) : Nat := a ++ b\n\nend Spec2Lean.Synthetic.Arithmetic\n";

#[test]
fn a_valid_translation_is_compiled_and_accepted_in_one_pass() {
    if !lean_available() {
        eprintln!("skipping: lean is not on PATH");
        return;
    }
    let work = Work::new("pass");
    let mut tools = make_tools(&work);
    let text = submit(&mut tools, GOOD);

    assert!(text.contains("lean build: PASS"), "{text}");
    assert!(tools.finished());
    assert_eq!(tools.build_count(), 1);

    let manifest = tools.manifest().expect("manifest");
    assert_eq!(manifest["phase"], json!("LLM_GROUP_TRANSLATOR"));
    assert_eq!(manifest["build"]["status"], json!("PASS"));
    assert_eq!(manifest["leanFile"], json!("Arithmetic.lean"));
    // Every claim resolves to the declarations that represent it.
    assert_eq!(
        manifest["claimIndex"]["unit:add/claim:1"],
        json!(["Spec2Lean.Synthetic.Arithmetic.add"])
    );
    // The file the compiler actually saw is on disk.
    assert!(tools.lean_path().is_file());
}

/// The architectural claim, tested: a real compiler error becomes a reply to
/// the submission, and the fix lands in the same session.
#[test]
fn a_compiler_error_is_returned_in_session_and_the_repair_is_accepted() {
    if !lean_available() {
        eprintln!("skipping: lean is not on PATH");
        return;
    }
    let work = Work::new("repair");
    let mut tools = make_tools(&work);

    let first = submit(&mut tools, BROKEN);
    assert!(first.contains("lean build: FAIL"), "{first}");
    // The diagnostic is specific enough to act on: a real location and message.
    assert!(first.contains("Arithmetic.lean:3:"), "{first}");
    assert!(first.contains("resubmit"), "{first}");
    assert!(!tools.finished());
    assert_eq!(tools.build_count(), 1);

    // Same tool set, same session, corrected source.
    let second = submit(&mut tools, GOOD);
    assert!(second.contains("lean build: PASS"), "{second}");
    assert!(second.contains("Translation accepted"), "{second}");
    assert!(tools.finished());
    assert_eq!(tools.build_count(), 2);
    assert_eq!(tools.manifest().unwrap()["build"]["attempt"], json!(2));
}

#[test]
fn structural_failures_are_reported_before_the_compiler_runs() {
    let work = Work::new("structure");

    // A declaration the source does not define.
    let mut tools = make_tools(&work);
    let outcome = tools.call(
        "submit_translation",
        &json!({
            "leanSource": GOOD,
            "declarations": [{
                "declaration": "Spec2Lean.Synthetic.Arithmetic.subtract",
                "role": "OPERATION",
                "claimRefs": [{"unitId": "unit:add", "claimId": "claim:1"}],
            }],
        }),
    );
    let value: Value = serde_json::from_str(&outcome.to_text()).unwrap();
    assert_eq!(value["stage"], json!("STRUCTURE"));
    let codes: Vec<&str> = value["diagnostics"]
        .as_array()
        .unwrap()
        .iter()
        .filter_map(|item| item["code"].as_str())
        .collect();
    assert!(codes.contains(&"MISSING_DECLARATION"), "{codes:?}");
    assert!(codes.contains(&"UNMAPPED_DECLARATION"), "{codes:?}");
    // No build was attempted, and nothing was left pending for one.
    assert!(tools.after_tools().is_none());
    assert_eq!(tools.build_count(), 0);
}

#[test]
fn every_claim_must_reach_the_lean_and_every_declaration_must_be_mapped() {
    let work = Work::new("coverage");
    let mut tools = make_tools(&work);
    // A second declaration in the source, mapped to nothing.
    let source = "namespace Spec2Lean.Synthetic.Arithmetic\ndef add (a b : Nat) : Nat := a + b\ndef helper : Nat := 0\nend Spec2Lean.Synthetic.Arithmetic\n";
    let outcome = tools.call(
        "submit_translation",
        &json!({"leanSource": source, "declarations": mapping()}),
    );
    let value: Value = serde_json::from_str(&outcome.to_text()).unwrap();
    let messages: Vec<&str> = value["diagnostics"]
        .as_array()
        .unwrap()
        .iter()
        .filter_map(|item| item["message"].as_str())
        .collect();
    assert!(
        messages.iter().any(|m| m.contains("helper")),
        "{messages:?}"
    );

    // And the other direction: a claim with no declaration.
    let mut tools = make_tools(&work);
    let outcome = tools.call(
        "submit_translation",
        &json!({
            "leanSource": GOOD,
            "declarations": [{
                "declaration": "Spec2Lean.Synthetic.Arithmetic.add",
                "role": "OPERATION",
                "claimRefs": [{"unitId": "unit:add", "claimId": "claim:missing"}],
            }],
        }),
    );
    let value: Value = serde_json::from_str(&outcome.to_text()).unwrap();
    let codes: Vec<&str> = value["diagnostics"]
        .as_array()
        .unwrap()
        .iter()
        .filter_map(|item| item["code"].as_str())
        .collect();
    assert!(codes.contains(&"UNKNOWN_CLAIM_REF"), "{codes:?}");
    assert!(codes.contains(&"UNCOVERED_CLAIM"), "{codes:?}");
}

#[test]
fn escape_hatches_are_refused_however_they_are_spelled() {
    let work = Work::new("forbidden");
    for source in [
        "def add : Nat := sorry\n",
        "theorem add : True := by admit\n",
        "axiom add : Nat\n",
        "unsafe def add : Nat := 1\n",
        "partial def add : Nat := 1\n",
    ] {
        let mut tools = make_tools(&work);
        let outcome = tools.call(
            "submit_translation",
            &json!({"leanSource": source, "declarations": mapping()}),
        );
        let value: Value = serde_json::from_str(&outcome.to_text()).unwrap();
        let codes: Vec<&str> = value["diagnostics"]
            .as_array()
            .unwrap()
            .iter()
            .filter_map(|item| item["code"].as_str())
            .collect();
        assert!(
            codes.iter().any(|code| code.starts_with("FORBIDDEN_")),
            "{source:?} produced {codes:?}"
        );
        assert_eq!(tools.build_count(), 0);
    }
}

#[test]
fn a_group_with_shared_prerequisites_is_refused_rather_than_half_translated() {
    let mut plan = plan();
    plan["sharedPrerequisites"] = json!([{
        "dependencyId": "shared:predicate",
        "name": "predicate",
        "requiredBy": ["unit:add"],
    }]);
    let error = TranslationScope::from_inputs(&plan, "arithmetic", &semantics(), "t").unwrap_err();
    assert!(error.to_string().contains("shared:predicate"), "{error}");
    assert!(error.to_string().contains("not ported"), "{error}");
}

#[test]
fn the_scope_refuses_semantics_that_do_not_match_the_plan() {
    // A failed extraction cannot be translated.
    let mut broken = semantics();
    broken.get_mut("unit:add").unwrap()["outcome"] = json!("INSUFFICIENT_EVIDENCE");
    let error = TranslationScope::from_inputs(&plan(), "arithmetic", &broken, "t").unwrap_err();
    assert!(error.to_string().contains("requires successful semantics"));

    // Nor can semantics for a different plan.
    let mut wrong = semantics();
    wrong.get_mut("unit:add").unwrap()["planRunId"] = json!("plan:other");
    let error = TranslationScope::from_inputs(&plan(), "arithmetic", &wrong, "t").unwrap_err();
    assert!(error.to_string().contains("planRunId does not match"));

    // Nor a group missing one of its units' artifacts.
    let error =
        TranslationScope::from_inputs(&plan(), "arithmetic", &BTreeMap::new(), "t").unwrap_err();
    assert!(error.to_string().contains("exactly one semantic artifact"));
}

#[test]
fn the_full_session_repairs_a_build_failure_without_a_second_process() {
    use harness::provider::recorded::RecordedProvider;
    use harness::provider::{StopReason, ToolCall, TurnResponse};
    use harness::session::anthropic_tool_use;
    use harness::{Session, Usage};

    if !lean_available() {
        eprintln!("skipping: lean is not on PATH");
        return;
    }
    let work = Work::new("session");
    let mut tools = make_tools(&work);

    let turn = |id: &str, source: &str| {
        let input = json!({"leanSource": source, "declarations": mapping()});
        TurnResponse {
            assistant: anthropic_tool_use(id, "submit_translation", input.clone()),
            text: String::new(),
            tool_calls: vec![ToolCall {
                id: id.into(),
                name: "submit_translation".into(),
                input,
            }],
            stop_reason: StopReason::ToolUse,
            usage: Usage::default(),
            model: "test".into(),
        }
    };

    let provider = RecordedProvider::new("test", vec![turn("t1", BROKEN), turn("t2", GOOD)]);
    let (outcome, transcript) = Session::new(&provider, "system", "prompt").run(&mut tools);

    assert!(outcome.is_ok(), "{:?}", outcome.err().map(|e| e.to_string()));
    // Two turns, two compiles, one session, one process.
    assert_eq!(transcript.steps, 2);
    assert_eq!(tools.build_count(), 2);
    // The compiler diagnostic reached the model as a tool result.
    assert!(transcript.exchanges[0].tool_results[0]
        .output
        .contains("lean build: FAIL"));
    assert!(tools.manifest().is_some());
}
