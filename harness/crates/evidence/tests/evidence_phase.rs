//! Behavioural tests for Phase 3 against a real Phase-1 index.

use std::path::PathBuf;

use harness::{ToolSet, Transcript};
use serde_json::{Value, json};
use spec2lean_evidence::{EvidenceScope, EvidenceTools};
use spec2lean_specdb::{SpecDb, UnitId, fixture};

const DIGEST: &str = "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd";

struct Fixture {
    path: PathBuf,
}

impl Fixture {
    fn new(name: &str) -> Self {
        let path = std::env::temp_dir().join(format!("s2l-{name}-{}.sqlite", std::process::id()));
        let _ = std::fs::remove_file(&path);
        fixture::build(&path).expect("fixture index builds");
        Self { path }
    }

    fn db(&self) -> SpecDb {
        SpecDb::open(&self.path).expect("fixture index opens")
    }
}

impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = std::fs::remove_file(&self.path);
    }
}

/// A unit attached to the HTML chapter only, so the both-renditions rule is off.
fn html_only_plan() -> Value {
    json!({
        "planRunId": "plan:test",
        "language": "synthetic",
        "version": "1.0",
        "sourceDatabaseDigest": DIGEST,
        "requestedUnits": [{
            "unitId": "unit:add",
            "name": "add",
            "sourceNodeIds": ["node:html-ch1"],
        }],
        "sharedPrerequisites": [{
            "dependencyId": "shared:predicate",
            "requiredBy": ["unit:add"],
            "sourceNodeIds": ["node:html-def"],
        }],
        "externalPrerequisites": [],
        "dependencies": [],
    })
}

/// A unit attached to both renditions, which turns the pairing rule on.
fn both_renditions_plan() -> Value {
    json!({
        "planRunId": "plan:test",
        "language": "synthetic",
        "version": "1.0",
        "sourceDatabaseDigest": DIGEST,
        "requestedUnits": [{
            "unitId": "unit:add",
            "name": "add",
            "sourceNodeIds": ["node:html-ch1", "node:pdf-ch1"],
        }],
        "sharedPrerequisites": [],
        "externalPrerequisites": [],
        "dependencies": [],
    })
}

fn scope(plan: &Value) -> EvidenceScope {
    EvidenceScope::from_plan(plan, &UnitId::parse("unit:add").unwrap()).expect("scope resolves")
}

fn submit(node_ids: &[&str], role: &str, tier: &str) -> Value {
    json!({
        "unitId": "unit:add",
        "selections": [{
            "sourceNodeIds": node_ids,
            "role": role,
            "tier": tier,
            "rationale": "relevant to the unit",
        }],
    })
}

/// Codes of the diagnostics in a rejected submission result.
fn codes(outcome: &harness::ToolOutcome) -> Vec<String> {
    let harness::ToolOutcome::Ok(value) = outcome else {
        panic!("expected a validated response, got {outcome:?}");
    };
    assert_eq!(value["accepted"], json!(false), "expected a rejection: {value}");
    value["diagnostics"]
        .as_array()
        .expect("diagnostics array")
        .iter()
        .map(|item| item["code"].as_str().unwrap_or_default().to_string())
        .collect()
}

#[test]
fn seeds_are_selectable_and_produce_a_complete_bundle() {
    let fixture = Fixture::new("happy");
    let db = fixture.db();
    let mut tools = EvidenceTools::new(&db, scope(&html_only_plan())).unwrap();

    // Discover the syntax block, then read it so it becomes selectable.
    tools.call("spec_children", &json!({"nodeId": "node:html-ch1"}));
    tools.call("spec_show", &json!({"nodeId": "node:html-syntax"}));

    let outcome = tools.call(
        "submit_evidence",
        &json!({
            "unitId": "unit:add",
            "selections": [
                {"sourceNodeIds": ["node:html-syntax"], "role": "SYNTAX", "tier": "CORE",
                 "rationale": "the instruction form"},
                {"sourceNodeIds": ["node:html-def"], "role": "SUPPORTING_DEFINITION",
                 "tier": "SUPPORTING", "rationale": "defines predicate"},
            ],
        }),
    );
    assert!(!outcome.is_error(), "{outcome:?}");
    assert!(tools.finished());

    let bundle = tools.bundle().expect("bundle exists");
    let evidence = bundle["evidence"].as_array().unwrap();
    assert_eq!(evidence.len(), 2);
    // CORE sorts first.
    assert_eq!(evidence[0]["tier"], json!("CORE"));
    // Exact text is reconstructed from Phase 1, never from the model.
    assert_eq!(evidence[0]["exactText"], json!("add.type d, a, b;"));
    assert_eq!(
        evidence[0]["documentSha256"],
        json!("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    );
    // The basis records how the node entered the session.
    assert_eq!(
        evidence[0]["selectionBasis"][0]["basis"],
        json!(["CHILD_OF:node:html-ch1", "SHOW"])
    );
    assert_eq!(bundle["phase"], json!("RETRIEVE_EVIDENCE"));
    assert_eq!(bundle["sourceDatabaseDigest"], json!(DIGEST));
}

#[test]
fn a_node_never_shown_with_its_text_cannot_be_selected() {
    let fixture = Fixture::new("unexposed");
    let db = fixture.db();
    let mut tools = EvidenceTools::new(&db, scope(&html_only_plan())).unwrap();

    // Listed as a child — discovered, but its exact text was never returned.
    tools.call("spec_children", &json!({"nodeId": "node:html-ch1"}));
    let outcome = tools.call("submit_evidence", &submit(&["node:html-note"], "OTHER", "CORE"));
    assert_eq!(codes(&outcome), vec!["NODE_NOT_EXPOSED"]);
    assert!(!tools.finished());
}

#[test]
fn an_invented_node_is_rejected_before_it_reaches_a_query() {
    let fixture = Fixture::new("invented");
    let db = fixture.db();
    let mut tools = EvidenceTools::new(&db, scope(&html_only_plan())).unwrap();

    let outcome = tools.call(
        "submit_evidence",
        &submit(&["node:does-not-exist"], "SYNTAX", "CORE"),
    );
    assert_eq!(codes(&outcome), vec!["INVENTED_SOURCE_NODE"]);

    // A malformed identifier fails the same way rather than reaching SQL.
    let outcome = tools.call("submit_evidence", &submit(&["not-a-node-id"], "SYNTAX", "CORE"));
    assert_eq!(codes(&outcome), vec!["INVENTED_SOURCE_NODE"]);
}

#[test]
fn tools_refuse_nodes_outside_the_session_boundary() {
    let fixture = Fixture::new("boundary");
    let db = fixture.db();
    let mut tools = EvidenceTools::new(&db, scope(&html_only_plan())).unwrap();

    // The PDF chapter exists but is not in this unit's boundary.
    let outcome = tools.call("spec_show", &json!({"nodeId": "node:pdf-ch1"}));
    assert!(outcome.is_error());
    assert!(outcome.to_text().contains("outside the bounded session context"));
}

#[test]
fn malformed_tool_arguments_are_reported_not_panicked() {
    let fixture = Fixture::new("malformed");
    let db = fixture.db();
    let mut tools = EvidenceTools::new(&db, scope(&html_only_plan())).unwrap();

    for input in [
        json!({}),                                        // missing nodeId
        json!({"nodeId": 7}),                             // wrong type
        json!({"nodeId": "span:html-syntax-0"}),          // wrong namespace
        json!({"nodeId": "node:html-ch1", "extra": 1}),   // unknown field
    ] {
        let outcome = tools.call("spec_show", &input);
        assert!(outcome.is_error(), "expected rejection for {input}");
    }
    // An out-of-range limit is a bounded-query violation, not a crash.
    let outcome = tools.call("spec_children", &json!({"nodeId": "node:html-ch1", "limit": 5000}));
    assert!(outcome.is_error());
    assert!(outcome.to_text().contains("limit must be between 1 and 100"));
}

#[test]
fn grouped_nodes_must_be_contiguous_siblings() {
    let fixture = Fixture::new("contiguous");
    let db = fixture.db();
    let mut tools = EvidenceTools::new(&db, scope(&html_only_plan())).unwrap();
    tools.call("spec_subtree", &json!({"nodeId": "node:html-ch1", "maxDepth": 1}));

    // ordinals 0 and 2 with 1 skipped.
    let outcome = tools.call(
        "submit_evidence",
        &submit(&["node:html-syntax", "node:html-note"], "SYNTAX", "CORE"),
    );
    assert_eq!(codes(&outcome), vec!["NONCONTIGUOUS_NODES"]);

    // Adjacent siblings are accepted and merge into one record.
    let outcome = tools.call(
        "submit_evidence",
        &submit(&["node:html-syntax", "node:html-def"], "SYNTAX", "CORE"),
    );
    assert!(!outcome.is_error(), "{outcome:?}");
    let bundle = tools.bundle().unwrap();
    assert_eq!(bundle["evidence"].as_array().unwrap().len(), 1);
    assert_eq!(
        bundle["evidence"][0]["exactText"],
        json!("add.type d, a, b;\npredicate: a one-bit value.")
    );
}

#[test]
fn a_bundle_without_core_evidence_is_rejected() {
    let fixture = Fixture::new("nocore");
    let db = fixture.db();
    let mut tools = EvidenceTools::new(&db, scope(&html_only_plan())).unwrap();
    tools.call("spec_show", &json!({"nodeId": "node:html-ch1"}));

    let outcome = tools.call(
        "submit_evidence",
        &submit(&["node:html-ch1"], "OTHER", "SUPPORTING"),
    );
    assert_eq!(codes(&outcome), vec!["MISSING_CORE_EVIDENCE"]);
}

#[test]
fn both_renditions_are_required_only_when_the_plan_attached_both() {
    let fixture = Fixture::new("renditions");
    let db = fixture.db();
    let mut tools = EvidenceTools::new(&db, scope(&both_renditions_plan())).unwrap();
    tools.call("spec_subtree", &json!({"nodeId": "node:html-ch1", "maxDepth": 1}));
    tools.call("spec_subtree", &json!({"nodeId": "node:pdf-ch1", "maxDepth": 1}));

    // HTML alone is not enough now.
    let outcome = tools.call("submit_evidence", &submit(&["node:html-syntax"], "SYNTAX", "CORE"));
    let found = codes(&outcome);
    assert!(found.contains(&"MISSING_SOURCE_RENDITION".to_string()), "{found:?}");
    assert!(found.contains(&"UNPAIRED_SOURCE_RENDITION".to_string()), "{found:?}");

    // The matching PDF passage, same role and tier, satisfies it.
    let outcome = tools.call(
        "submit_evidence",
        &json!({
            "unitId": "unit:add",
            "selections": [
                {"sourceNodeIds": ["node:html-syntax"], "role": "SYNTAX", "tier": "CORE",
                 "rationale": "html form"},
                {"sourceNodeIds": ["node:pdf-syntax"], "role": "SYNTAX", "tier": "CORE",
                 "rationale": "pdf form"},
            ],
        }),
    );
    assert!(!outcome.is_error(), "{outcome:?}");
    let bundle = tools.bundle().unwrap();
    let pdf = bundle["evidence"]
        .as_array()
        .unwrap()
        .iter()
        .find(|item| item["sourceType"] == json!("pdf"))
        .expect("a pdf record");
    // Provenance comes back from Phase 1: page, and a merged bounding box.
    assert_eq!(pdf["pdfPage"], json!(2));
    assert_eq!(pdf["bbox"], json!([10.0, 20.0, 95.0, 40.0]));
    // Two spans on different lines are joined with a newline.
    assert_eq!(pdf["exactText"], json!("add.type d, a, b;"));
}

#[test]
fn selected_spans_must_be_exposed_belong_to_the_node_and_cover_it() {
    let fixture = Fixture::new("spans");
    let db = fixture.db();
    let mut tools = EvidenceTools::new(&db, scope(&both_renditions_plan())).unwrap();
    tools.call("spec_subtree", &json!({"nodeId": "node:pdf-ch1", "maxDepth": 1}));
    tools.call("spec_subtree", &json!({"nodeId": "node:html-ch1", "maxDepth": 1}));

    let with_spans = |node: &str, spans: Vec<&str>| {
        json!({
            "unitId": "unit:add",
            "selections": [{
                "sourceNodeIds": [node],
                "sourceSpanIds": spans,
                "role": "SYNTAX",
                "tier": "CORE",
                "rationale": "the form",
            }],
        })
    };

    // A span that does not exist.
    let outcome = tools.call("submit_evidence", &with_spans("node:pdf-syntax", vec!["span:nope"]));
    assert!(codes(&outcome).contains(&"INVENTED_SOURCE_SPAN".to_string()));

    // A real span belonging to a different node.
    let outcome = tools.call(
        "submit_evidence",
        &with_spans("node:pdf-syntax", vec!["span:html-syntax-0"]),
    );
    let found = codes(&outcome);
    assert!(found.contains(&"SPAN_NODE_MISMATCH".to_string()), "{found:?}");
    assert!(found.contains(&"SPAN_NODE_COVERAGE".to_string()), "{found:?}");

    // A real, exposed, owned span narrows the record to just that span.
    let outcome = tools.call(
        "submit_evidence",
        &json!({
            "unitId": "unit:add",
            "selections": [
                {"sourceNodeIds": ["node:pdf-syntax"], "sourceSpanIds": ["span:pdf-syntax-0"],
                 "role": "SYNTAX", "tier": "CORE", "rationale": "pdf form"},
                {"sourceNodeIds": ["node:html-syntax"], "role": "SYNTAX", "tier": "CORE",
                 "rationale": "html form"},
            ],
        }),
    );
    assert!(!outcome.is_error(), "{outcome:?}");
    let bundle = tools.bundle().unwrap();
    let pdf = bundle["evidence"]
        .as_array()
        .unwrap()
        .iter()
        .find(|item| item["sourceType"] == json!("pdf"))
        .unwrap();
    assert_eq!(pdf["exactText"], json!("add.type d, "));
    assert_eq!(pdf["sourceSpanIds"], json!(["span:pdf-syntax-0"]));
}

#[test]
fn a_submission_carrying_semantic_fields_is_rejected() {
    let fixture = Fixture::new("semantic");
    let db = fixture.db();
    let mut tools = EvidenceTools::new(&db, scope(&html_only_plan())).unwrap();
    tools.call("spec_show", &json!({"nodeId": "node:html-ch1"}));

    // The retriever must not smuggle claims or quoted text into the bundle.
    let outcome = tools.call(
        "submit_evidence",
        &json!({
            "unitId": "unit:add",
            "claims": ["add wraps on overflow"],
            "selections": [{
                "sourceNodeIds": ["node:html-ch1"],
                "role": "SYNTAX",
                "tier": "CORE",
                "rationale": "the form",
                "exactText": "something the model typed",
            }],
        }),
    );
    let found = codes(&outcome);
    assert_eq!(found, vec!["UNEXPECTED_FIELD", "UNEXPECTED_FIELD"]);
}

#[test]
fn the_evidence_id_does_not_depend_on_how_the_node_was_found() {
    let fixture = Fixture::new("stable");
    // Two different discovery routes to the same passage.
    let record = |route: &[(&str, Value)]| {
        let db = fixture.db();
        let mut tools = EvidenceTools::new(&db, scope(&html_only_plan())).unwrap();
        for (name, input) in route {
            let outcome = tools.call(name, input);
            assert!(!outcome.is_error(), "{name}: {outcome:?}");
        }
        assert!(!tools
            .call("submit_evidence", &submit(&["node:html-syntax"], "SYNTAX", "CORE"))
            .is_error());
        tools.bundle().unwrap()["evidence"][0].clone()
    };

    let via_subtree = record(&[(
        "spec_subtree",
        json!({"nodeId": "node:html-ch1", "maxDepth": 1}),
    )]);
    let via_show = record(&[
        ("spec_children", json!({"nodeId": "node:html-ch1"})),
        ("spec_show", json!({"nodeId": "node:html-syntax"})),
    ]);

    // The identity covers the index digest, the nodes, the spans, the role and
    // the tier — not the route, which is recorded separately.
    assert_eq!(via_subtree["evidenceId"], via_show["evidenceId"]);
    assert_eq!(
        via_subtree["selectionBasis"][0]["basis"],
        json!(["SUBTREE_OF:node:html-ch1"])
    );
    assert_eq!(
        via_show["selectionBasis"][0]["basis"],
        json!(["CHILD_OF:node:html-ch1", "SHOW"])
    );
}

#[test]
fn the_full_session_runs_the_loop_and_writes_a_transcript() {
    use harness::provider::recorded::RecordedProvider;
    use harness::provider::{StopReason, ToolCall, TurnResponse};
    use harness::session::anthropic_tool_use;
    use harness::{Session, Usage};

    let fixture = Fixture::new("session");
    let db = fixture.db();
    let mut tools = EvidenceTools::new(&db, scope(&html_only_plan())).unwrap();

    let turn = |id: &str, name: &str, input: Value| TurnResponse {
        assistant: anthropic_tool_use(id, name, input.clone()),
        text: String::new(),
        tool_calls: vec![ToolCall {
            id: id.into(),
            name: name.into(),
            input,
        }],
        stop_reason: StopReason::ToolUse,
        usage: Usage {
            input_tokens: 100,
            output_tokens: 20,
            cache_creation_input_tokens: 0,
            cache_read_input_tokens: 80,
        },
        model: "test".into(),
    };

    let provider = RecordedProvider::new(
        "test",
        vec![
            // Discovery only: the children are now visible but not selectable.
            turn("t1", "spec_children", json!({"nodeId": "node:html-ch1"})),
            // A submission the validator rejects, because the text was never shown.
            turn("t2", "submit_evidence", submit(&["node:html-note"], "OTHER", "CORE")),
            turn("t3", "spec_show", json!({"nodeId": "node:html-syntax"})),
            // The corrected submission.
            turn("t4", "submit_evidence", submit(&["node:html-syntax"], "SYNTAX", "CORE")),
        ],
    );

    let (outcome, transcript): (_, Transcript) =
        Session::new(&provider, "system", "prompt").run(&mut tools);

    assert!(outcome.is_ok(), "{:?}", outcome.err().map(|e| e.to_string()));
    assert_eq!(transcript.steps, 4);
    assert_eq!(transcript.tools.len(), 9);
    assert!(transcript.exchanges[1].tool_results[0].output.contains("NODE_NOT_EXPOSED"));
    assert_eq!(transcript.usage.cache_read_input_tokens, 320);
    assert!(tools.bundle().is_some());

    // The transcript serialises, which is what gets written next to the bundle.
    let value = serde_json::to_value(&transcript).unwrap();
    assert_eq!(value["outcome"], json!("SUBMITTED"));
}
