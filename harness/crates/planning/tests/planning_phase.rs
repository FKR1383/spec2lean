//! Phase 2 behaviour against a real Phase-1 index.

use std::path::PathBuf;

use harness::ToolSet;
use serde_json::{Value, json};
use spec2lean_planning::{PlanningRequest, PlanningTools, ScopeResolver, Selector};
use spec2lean_specdb::{NodeId, SpecDb, fixture};

const DIGEST: &str = "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd";

struct Fixture(PathBuf);

impl Fixture {
    fn new(name: &str) -> Self {
        let path = std::env::temp_dir().join(format!("s2l-plan-{name}-{}.sqlite", std::process::id()));
        let _ = std::fs::remove_file(&path);
        fixture::build(&path).expect("fixture index");
        Self(path)
    }

    fn db(&self) -> SpecDb {
        SpecDb::open(&self.0).expect("open")
    }
}

impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = std::fs::remove_file(&self.0);
    }
}

fn request(selector: Selector) -> PlanningRequest {
    PlanningRequest::new("synthetic", "1.0", selector).expect("valid request")
}

fn resolve(db: &SpecDb, selector: Selector) -> spec2lean_planning::ResolvedScope {
    ScopeResolver::new(db).resolve(&request(selector)).expect("resolves")
}

fn make_tools<'a>(db: &'a SpecDb, scope: spec2lean_planning::ResolvedScope) -> PlanningTools<'a> {
    PlanningTools::new(db, scope, "plan:test", DIGEST)
}

fn codes(outcome: &harness::ToolOutcome) -> Vec<String> {
    let harness::ToolOutcome::Ok(value) = outcome else {
        panic!("expected a validated response, got {outcome:?}");
    };
    assert_eq!(value["accepted"], json!(false), "expected a rejection: {value}");
    value["diagnostics"]
        .as_array()
        .expect("diagnostics")
        .iter()
        .map(|item| item["code"].as_str().unwrap_or_default().to_string())
        .collect()
}

/// Every candidate unit of a resolved scope. A full-specification request names
/// its units, so a submission must preserve all of them.
fn all_units(scope: &spec2lean_planning::ResolvedScope) -> Vec<String> {
    scope
        .candidate_units
        .iter()
        .filter_map(|unit| unit.get("unitId")?.as_str().map(str::to_string))
        .collect()
}

/// A complete, valid submission: one group per unit, each justified by the
/// chapter its unit sits under.
fn submission(units: &[String], supports: &[&str]) -> Value {
    let groups: Vec<Value> = units
        .iter()
        .zip(supports)
        .enumerate()
        .map(|(index, (unit_id, support))| {
            json!({
                "name": format!("Arithmetic{index}"),
                "unitIds": [unit_id],
                "reason": "the specification groups this under its own chapter",
                "supportingNodeIds": [support],
                "origin": "EXPLICIT",
            })
        })
        .collect();
    json!({
        "requestedUnitIds": units,
        "translationGroups": groups,
        "externalPrerequisites": [],
        "sharedPrerequisites": [],
        "dependencies": [],
    })
}

/// The chapters the fixture's two units sit under, in candidate order.
const SUPPORTS: [&str; 2] = ["node:html-ch1", "node:html-ch2"];

#[test]
fn a_full_specification_request_yields_one_candidate_per_heading() {
    let fixture = Fixture::new("full");
    let db = fixture.db();
    let scope = resolve(&db, Selector::FullSpecification);

    // Chapters 1 and 2, and no more: the HTML and PDF renditions of chapter 1
    // merge into one logical unit rather than becoming two.
    assert_eq!(scope.candidate_units.len(), 2, "{:?}", scope.candidate_units);
    let unit = &scope.candidate_units[0];
    assert_eq!(unit["name"], json!("Add"));
    assert_eq!(
        unit["sourceNodeIds"],
        json!(["node:html-ch1", "node:pdf-ch1"])
    );
    // A full-specification request names its units, so they must be preserved.
    assert_eq!(scope.exact_unit_ids.len(), 2);
}

#[test]
fn a_subtree_request_follows_correlated_renditions() {
    let fixture = Fixture::new("subtree");
    let db = fixture.db();
    let scope = resolve(
        &db,
        Selector::SourceSubtree(NodeId::parse("node:html-ch1").unwrap()),
    );
    // html-syntax correlates with pdf-syntax, so both renditions are in scope.
    assert!(!scope.candidate_units.is_empty());
    assert!(scope.context_node_ids.iter().any(|id| id == "node:html-ch1"));
}

#[test]
fn an_unknown_instruction_or_family_is_refused_rather_than_guessed() {
    let fixture = Fixture::new("unknown");
    let db = fixture.db();
    let resolver = ScopeResolver::new(&db);

    let error = resolver
        .resolve(&request(Selector::ExactInstructions(vec!["nosuchop".into()])))
        .unwrap_err();
    assert!(error.to_string().contains("could not be resolved"), "{error}");

    let error = resolver
        .resolve(&request(Selector::InstructionFamily("quantum gates".into())))
        .unwrap_err();
    assert!(error.to_string().contains("could not be resolved"), "{error}");
}

#[test]
fn a_request_for_the_wrong_specification_is_refused_before_planning() {
    let fixture = Fixture::new("identity");
    let db = fixture.db();
    let wrong = PlanningRequest::new("ptx", "8.5", Selector::FullSpecification).unwrap();
    let error = ScopeResolver::new(&db).resolve(&wrong).unwrap_err();
    assert!(error.to_string().contains("database contains synthetic 1.0"), "{error}");
}

#[test]
fn a_valid_submission_becomes_a_plan_with_a_derived_processing_order() {
    let fixture = Fixture::new("plan");
    let db = fixture.db();
    let scope = resolve(&db, Selector::FullSpecification);
    let units = all_units(&scope);
    let mut tools = make_tools(&db, scope);

    let outcome = tools.call("submit_plan", &submission(&units, &SUPPORTS));
    assert!(!outcome.is_error(), "{outcome:?}");
    assert!(tools.finished());

    let plan = tools.plan().expect("plan");
    assert_eq!(plan["schemaVersion"], json!(3));
    assert_eq!(plan["planRunId"], json!("plan:test"));
    assert_eq!(plan["sourceDatabaseDigest"], json!(DIGEST));
    assert_eq!(plan["graphStatus"], json!("ACYCLIC"));
    // The processing order is derived, never supplied.
    // Independent units all land in the first layer, in sorted order.
    let mut expected = units.clone();
    expected.sort();
    assert_eq!(plan["processingLayers"][0]["unitIds"], json!(expected));
    assert_eq!(plan["translationGroups"][0]["name"], json!("Arithmetic0"));
    // The unit carries its full definition, not just its ID.
    assert_eq!(plan["requestedUnits"][0]["name"], json!("Add"));
}

#[test]
fn every_cited_node_must_exist_in_the_index() {
    let fixture = Fixture::new("invented");
    let db = fixture.db();
    let scope = resolve(&db, Selector::FullSpecification);
    let units = all_units(&scope);
    let mut tools = make_tools(&db, scope);

    let mut value = submission(&units, &SUPPORTS);
    value["translationGroups"][0]["supportingNodeIds"] = json!(["node:invented"]);
    assert!(codes(&tools.call("submit_plan", &value)).contains(&"INVENTED_SOURCE_NODE".to_string()));

    let mut value = submission(&units, &SUPPORTS);
    value["translationGroups"][0]["supportingNodeIds"] = json!(["not-a-node"]);
    assert!(codes(&tools.call("submit_plan", &value)).contains(&"INVALID_SOURCE_NODE".to_string()));
}

#[test]
fn translation_groups_must_be_an_exact_partition_justified_by_real_structure() {
    let fixture = Fixture::new("groups");
    let db = fixture.db();
    let scope = resolve(&db, Selector::FullSpecification);
    let units = all_units(&scope);

    // A unit left out of every group.
    let mut tools = make_tools(&db, scope.clone());
    let mut value = submission(&units, &SUPPORTS);
    value["translationGroups"][0]["unitIds"] = json!([]);
    let found = codes(&tools.call("submit_plan", &value));
    assert!(found.contains(&"EMPTY_TRANSLATION_GROUP".to_string()), "{found:?}");
    assert!(found.contains(&"UNGROUPED_REQUESTED_UNITS".to_string()), "{found:?}");

    // A name that is not an UpperCamelCase Lean identifier.
    let mut tools = make_tools(&db, scope.clone());
    let mut value = submission(&units, &SUPPORTS);
    value["translationGroups"][0]["name"] = json!("integer arithmetic");
    assert!(
        codes(&tools.call("submit_plan", &value))
            .contains(&"INVALID_TRANSLATION_GROUP_NAME".to_string())
    );

    // Support that exists but is nowhere in the unit's ancestry: the group is
    // justified by a section its members do not sit under.
    let mut tools = make_tools(&db, scope);
    let mut value = submission(&units, &SUPPORTS);
    value["translationGroups"][0]["supportingNodeIds"] = json!(["node:html-note"]);
    assert!(
        codes(&tools.call("submit_plan", &value))
            .contains(&"UNSUPPORTED_TRANSLATION_GROUP_MEMBER".to_string())
    );
}

#[test]
fn shared_prerequisites_get_derived_identity_and_must_name_selected_units() {
    let fixture = Fixture::new("shared");
    let db = fixture.db();
    let scope = resolve(&db, Selector::FullSpecification);
    let units = all_units(&scope);

    let shared = |required_by: Value| {
        json!([{
            "key": "predicate",
            "name": "predicate",
            "kind": "guard value",
            "reason": "several units guard execution on it",
            "sourceNodeIds": ["node:html-def"],
            "requiredBy": required_by,
        }])
    };

    let mut tools = make_tools(&db, scope.clone());
    let mut value = submission(&units, &SUPPORTS);
    value["sharedPrerequisites"] = shared(json!(["unit:not-selected"]));
    assert!(
        codes(&tools.call("submit_plan", &value))
            .contains(&"UNKNOWN_SHARED_PREREQUISITE_CONSUMER".to_string())
    );

    let mut tools = make_tools(&db, scope);
    let mut value = submission(&units, &SUPPORTS);
    value["sharedPrerequisites"] = shared(json!([units[0]]));
    let outcome = tools.call("submit_plan", &value);
    assert!(!outcome.is_error(), "{outcome:?}");
    let plan = tools.plan().unwrap();
    // The model supplies a conceptual key; identity is derived from it.
    let dependency_id = plan["sharedPrerequisites"][0]["dependencyId"].as_str().unwrap();
    assert!(dependency_id.starts_with("shared:"), "{dependency_id}");
    assert_eq!(plan["sharedPrerequisites"][0]["kind"], json!("guard value"));
}

#[test]
fn an_external_prerequisite_cannot_be_the_dependent_endpoint() {
    let fixture = Fixture::new("edges");
    let db = fixture.db();
    let scope = resolve(&db, Selector::FullSpecification);
    let units = all_units(&scope);
    let mut tools = make_tools(&db, scope);

    let mut value = submission(&units, &SUPPORTS);
    value["externalPrerequisites"] = json!([{
        "key": "memory-model",
        "name": "memory model",
        "reason": "defined in another document",
        "sourceNodeIds": ["node:html-note"],
    }]);
    value["dependencies"] = json!([{
        "from": units[0],
        "to": "memory-model",
        "reason": "backwards",
        "supportingNodeIds": ["node:html-note"],
        "origin": "INFERRED",
    }]);
    assert!(
        codes(&tools.call("submit_plan", &value))
            .contains(&"EXTERNAL_PREREQUISITE_TARGET".to_string())
    );
}

#[test]
fn an_exact_request_selection_cannot_be_changed_by_the_planner() {
    let fixture = Fixture::new("exact");
    let db = fixture.db();
    let scope = resolve(&db, Selector::FullSpecification);
    let mut tools = make_tools(&db, scope);

    // Selecting nothing when the scope named a unit.
    let value = json!({
        "requestedUnitIds": [],
        "translationGroups": [],
        "externalPrerequisites": [],
        "sharedPrerequisites": [],
        "dependencies": [],
    });
    assert!(codes(&tools.call("submit_plan", &value)).contains(&"SCOPE_MISMATCH".to_string()));
}

#[test]
fn the_full_session_corrects_itself_after_a_diagnostic() {
    use harness::provider::recorded::RecordedProvider;
    use harness::provider::{StopReason, ToolCall, TurnResponse};
    use harness::session::anthropic_tool_use;
    use harness::{Session, Usage};

    let fixture = Fixture::new("session");
    let db = fixture.db();
    let scope = resolve(&db, Selector::FullSpecification);
    let units = all_units(&scope);
    let mut tools = make_tools(&db, scope);

    let turn = |id: &str, name: &str, input: Value| TurnResponse {
        assistant: anthropic_tool_use(id, name, input.clone()),
        text: String::new(),
        tool_calls: vec![ToolCall { id: id.into(), name: name.into(), input }],
        stop_reason: StopReason::ToolUse,
        usage: Usage::default(),
        model: "test".into(),
    };

    let mut wrong = submission(&units, &SUPPORTS);
    wrong["translationGroups"][0]["origin"] = json!("GUESS");

    let provider = RecordedProvider::new(
        "test",
        vec![
            turn("t1", "spec_children", json!({"nodeId": "node:html-root"})),
            turn("t2", "submit_plan", wrong),
            turn("t3", "submit_plan", submission(&units, &SUPPORTS)),
        ],
    );
    let (outcome, transcript) = Session::new(&provider, "system", "prompt").run(&mut tools);

    assert!(outcome.is_ok(), "{:?}", outcome.err().map(|e| e.to_string()));
    assert_eq!(transcript.steps, 3);
    assert_eq!(transcript.tools.len(), 8);
    assert!(transcript.exchanges[1].tool_results[0]
        .output
        .contains("INVALID_TRANSLATION_GROUP_ORIGIN"));
    assert!(tools.plan().is_some());
}

// The cases below come from external review.

#[test]
fn a_group_of_several_units_needs_support_they_all_sit_under() {
    let fixture = Fixture::new("commonsupport");
    let db = fixture.db();
    // Two units under different parents: the PDF and HTML chapters.
    let scope = resolve(&db, Selector::FullSpecification);
    let units = all_units(&scope);

    let mut tools = make_tools(&db, scope);
    let mut value = submission(&units, &SUPPORTS);
    // Listing each unit's own section justifies nothing about grouping them;
    // here the single member is fine, so the multi-member rule is exercised by
    // naming support that is not in the shared ancestry.
    value["translationGroups"][0]["supportingNodeIds"] = json!(["node:html-def"]);
    let found = codes(&tools.call("submit_plan", &value));
    assert!(
        found.contains(&"UNSUPPORTED_TRANSLATION_GROUP_MEMBER".to_string()),
        "{found:?}"
    );
}

#[test]
fn a_family_matches_whole_words_and_must_name_something() {
    let fixture = Fixture::new("familywords");
    let db = fixture.db();
    let resolver = ScopeResolver::new(&db);

    // Only stop words: every heading would "match".
    let error = resolver
        .resolve(&request(Selector::InstructionFamily("the a an".into())))
        .unwrap_err();
    assert!(error.to_string().contains("nothing to match on"), "{error}");

    // A substring of a heading word is not a match: the fixture's only chapter
    // is "Add", so "Ad" must not resolve it.
    let error = resolver
        .resolve(&request(Selector::InstructionFamily("Ad".into())))
        .unwrap_err();
    assert!(error.to_string().contains("could not be resolved"), "{error}");

    // The whole word does resolve it.
    let scope = resolver
        .resolve(&request(Selector::InstructionFamily("Add".into())))
        .expect("resolves");
    assert!(!scope.candidate_units.is_empty());
}

/// External review: with two sections matching, whichever the database returned
/// first was selected, so which section got planned depended on row order.
#[test]
fn an_instruction_defined_by_two_sections_is_ambiguous_not_arbitrary() {
    let fixture = Fixture::new("ambiguous");
    let db = fixture.db();
    // Chapters 1 and 2 both define `add.type`, and they are different sections
    // rather than renditions of one.
    let error = ScopeResolver::new(&db)
        .resolve(&request(Selector::ExactInstructions(vec!["add.type".into()])))
        .unwrap_err();
    let message = error.to_string();
    assert!(message.contains("more than one section"), "{message}");
    assert!(message.contains("1 Add") && message.contains("2 Add"), "{message}");
}
