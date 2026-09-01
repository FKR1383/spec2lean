//! Behavioural tests for Phase 4.

use harness::ToolSet;
use serde_json::{Value, json};
use spec2lean_semantics::{SemanticScope, SemanticTools, evidence_bundle_hash};
use spec2lean_specdb::UnitId;

const DIGEST: &str = "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd";

fn unit() -> Value {
    json!({"unitId": "unit:add", "name": "add", "sourceNodeIds": ["node:html-ch1"]})
}

fn plan() -> Value {
    json!({
        "planRunId": "plan:test",
        "language": "synthetic",
        "version": "1.0",
        "sourceDatabaseDigest": DIGEST,
        "requestedUnits": [unit()],
        "sharedPrerequisites": [{
            "dependencyId": "shared:predicate",
            "name": "predicate",
            "requiredBy": ["unit:add"],
        }],
    })
}

fn record(id: &str, role: &str, source_type: &str) -> Value {
    json!({
        "evidenceId": id,
        "unitId": "unit:add",
        "role": role,
        "tier": "CORE",
        "rationale": "relevant",
        "sourceType": source_type,
        "exactText": "add.type d, a, b;",
        "documentId": format!("doc:{source_type}"),
        "documentSha256": "a".repeat(64),
        "sourceNodeIds": ["node:html-syntax"],
    })
}

fn bundle_with(evidence: Vec<Value>, resolutions: Vec<Value>) -> Value {
    let mut bundle = json!({
        "schemaVersion": 1,
        "phase": "RETRIEVE_EVIDENCE",
        "planRunId": "plan:test",
        "language": "synthetic",
        "version": "1.0",
        "sourceDatabaseDigest": DIGEST,
        "unit": unit(),
        "evidence": evidence,
    });
    if !resolutions.is_empty() {
        bundle["resolutions"] = json!(resolutions);
    }
    bundle
}

/// A single-rendition bundle, so the HTML/PDF claim rule is off.
fn base_bundle() -> Value {
    bundle_with(
        vec![
            record("evidence:op", "OPERATION", "html"),
            record("evidence:syntax", "SYNTAX", "html"),
        ],
        vec![],
    )
}

fn scope(plan: &Value, bundle: &Value) -> SemanticScope {
    SemanticScope::from_inputs(
        plan,
        bundle,
        &UnitId::parse("unit:add").unwrap(),
        "2026-01-01T00:00:00.000000Z",
    )
    .expect("scope resolves")
}

fn extractor() -> Value {
    json!({"provider": "recorded", "model": "test"})
}

fn make_tools(bundle: &Value) -> SemanticTools {
    let plan = plan();
    SemanticTools::new(scope(&plan, bundle), bundle.clone(), extractor())
}

/// A complete, valid INSTRUCTION submission.
fn base_submission() -> Value {
    json!({
        "outcome": "SUCCESS",
        "unitKind": "INSTRUCTION",
        "identity": {"name": "add", "evidenceIds": ["evidence:syntax"]},
        "syntaxForms": [{"form": "add.type d, a, b;", "evidenceIds": ["evidence:syntax"]}],
        "inputs": [{
            "name": "a", "role": "source operand", "description": "the first addend",
            "constraints": ["must be a register"], "evidenceIds": ["evidence:syntax"],
        }],
        "result": {
            "name": "d", "description": "the destination register",
            "constraints": ["written on completion"], "evidenceIds": ["evidence:op"],
        },
        "operation": {
            "description": "computes the sum of the two source operands",
            "inputs": ["a", "b"],
            "result": "d",
            "branches": [],
            "evidenceIds": ["evidence:op"],
        },
        "edgeCases": [],
        "stateEffects": [],
        "restrictions": [],
        "dependencies": [{
            "dependencyId": "shared:predicate",
            "concept": "predicate",
            "description": "a one-bit guard value",
            "semanticClaimIds": ["claim:1"],
            "evidenceIds": [],
        }],
        "claims": [{
            "claimId": "claim:1",
            "kind": "SOURCE_FACT",
            "statement": "add computes the sum of its two source operands",
            "evidenceIds": ["evidence:op"],
        }],
    })
}

fn read_and_submit(tools: &mut SemanticTools, submission: &Value) -> Value {
    tools.call("get_evidence", &json!({}));
    let outcome = tools.call("submit_semantics", submission);
    let harness::ToolOutcome::Ok(value) = outcome else {
        panic!("expected a validated response, got {outcome:?}");
    };
    value
}

fn codes(value: &Value) -> Vec<String> {
    assert_eq!(value["accepted"], json!(false), "expected a rejection: {value}");
    value["diagnostics"]
        .as_array()
        .expect("diagnostics")
        .iter()
        .map(|item| item["code"].as_str().unwrap_or_default().to_string())
        .collect()
}

#[test]
fn a_complete_submission_becomes_a_deterministic_artifact() {
    let bundle = base_bundle();
    let mut tools = make_tools(&bundle);
    let response = read_and_submit(&mut tools, &base_submission());

    assert_eq!(response["accepted"], json!(true), "{response}");
    assert!(tools.finished());
    let artifact = tools.artifact().expect("artifact");

    assert_eq!(artifact["phase"], json!("SEMANTIC_EXTRACTOR"));
    assert_eq!(artifact["schemaVersion"], json!(2));
    assert_eq!(artifact["outcome"], json!("SUCCESS"));
    // The payload moves under `semantics`, with `outcome` lifted out.
    assert!(artifact["semantics"].get("outcome").is_none());
    assert_eq!(artifact["semantics"]["unitKind"], json!("INSTRUCTION"));
    // The artifact is pinned to the exact bundle it was extracted from.
    assert_eq!(artifact["evidenceBundleHash"], json!(evidence_bundle_hash(&bundle)));
    // The extractor block records what actually ran.
    assert_eq!(artifact["extractor"], extractor());
}

#[test]
fn extracting_before_reading_the_evidence_is_refused() {
    let bundle = base_bundle();
    let mut tools = make_tools(&bundle);
    let outcome = tools.call("submit_semantics", &base_submission());
    let harness::ToolOutcome::Ok(value) = outcome else {
        panic!("unexpected {outcome:?}");
    };
    assert_eq!(codes(&value), vec!["EVIDENCE_NOT_READ"]);
    assert!(!tools.finished());
}

#[test]
fn the_evidence_view_projects_provenance_but_keeps_every_passage() {
    let bundle = base_bundle();
    let mut tools = make_tools(&bundle);
    let harness::ToolOutcome::Ok(view) = tools.call("get_evidence", &json!({})) else {
        panic!("get_evidence failed");
    };
    assert_eq!(view["evidence"].as_array().unwrap().len(), 2);
    assert_eq!(view["evidence"][0]["exactText"], json!("add.type d, a, b;"));
    // Verbose GUI provenance is dropped from the transport...
    assert!(view["evidence"][0].get("provenance").is_none());
    assert!(view["evidence"][0].get("bbox").is_none());
    // ...but the hash still covers the complete bundle.
    assert_eq!(
        view["transport"]["evidenceBundleHash"],
        json!(evidence_bundle_hash(&bundle))
    );
    assert_eq!(view["transport"]["complete"], json!(true));
}

#[test]
fn a_claim_cannot_cite_evidence_outside_this_bundle() {
    let bundle = base_bundle();
    let mut tools = make_tools(&bundle);
    let mut submission = base_submission();
    submission["claims"][0]["evidenceIds"] = json!(["evidence:from-another-unit"]);
    let response = read_and_submit(&mut tools, &submission);
    assert!(codes(&response).contains(&"UNKNOWN_EVIDENCE_ID".to_string()));
}

#[test]
fn an_instruction_operation_must_rest_on_functional_evidence() {
    let bundle = base_bundle();
    let mut tools = make_tools(&bundle);
    let mut submission = base_submission();
    // Citing only the syntax form: the operation would describe behaviour the
    // cited evidence never states.
    submission["operation"]["evidenceIds"] = json!(["evidence:syntax"]);
    let response = read_and_submit(&mut tools, &submission);
    assert_eq!(codes(&response), vec!["NONFUNCTIONAL_OPERATION"]);
}

#[test]
fn an_instruction_without_inputs_result_or_operation_is_rejected() {
    let bundle = base_bundle();
    let mut tools = make_tools(&bundle);
    let mut submission = base_submission();
    let object = submission.as_object_mut().unwrap();
    object.remove("operation");
    object.remove("result");
    // Omitted entirely, not empty: an artifact that never mentions inputs has
    // not said the instruction has none.
    object.remove("inputs");
    object.remove("stateEffects");
    let response = read_and_submit(&mut tools, &submission);
    let found = codes(&response);
    for code in ["MISSING_OPERATION", "MISSING_RESULT", "MISSING_INPUTS"] {
        assert!(found.contains(&code.to_string()), "{found:?}");
    }
}

/// External review, confirmed against the PTX index: `trap` and `brkpt` take no
/// operands and produce no value. Demanding a result and a non-empty input list
/// made them unformalizable.
#[test]
fn an_operandless_instruction_is_formalizable_when_it_says_so() {
    let bundle = bundle_with(vec![record("evidence:op", "OPERATION", "html")], vec![]);
    let mut plan = plan();
    plan["sharedPrerequisites"] = json!([]);
    let scope = SemanticScope::from_inputs(
        &plan, &bundle, &UnitId::parse("unit:add").unwrap(), "2026-01-01T00:00:00.000000Z",
    )
    .expect("scope");
    let mut tools = SemanticTools::new(scope, bundle.clone(), extractor());

    let response = read_and_submit(
        &mut tools,
        &json!({
            "outcome": "SUCCESS", "unitKind": "INSTRUCTION",
            "identity": {"name": "add", "evidenceIds": ["evidence:op"]},
            "syntaxForms": [], "edgeCases": [], "restrictions": [], "dependencies": [],
            // No operands and no result — said explicitly, not omitted.
            "inputs": [],
            "operation": {
                "description": "aborts execution of the thread",
                "inputs": [], "result": "none; execution does not continue",
                "branches": [], "evidenceIds": ["evidence:op"],
            },
            "stateEffects": [{"target": "thread execution", "effect": "aborted",
                              "evidenceIds": ["evidence:op"]}],
            "claims": [{"claimId": "claim:1", "kind": "SOURCE_FACT",
                        "statement": "the instruction aborts execution",
                        "evidenceIds": ["evidence:op"]}],
        }),
    );
    assert_eq!(response["accepted"], json!(true), "{response}");
}

#[test]
fn every_relevant_shared_prerequisite_must_be_bound_exactly_once_by_name() {
    let bundle = base_bundle();

    // Omitted entirely.
    let mut tools = make_tools(&bundle);
    let mut submission = base_submission();
    submission["dependencies"] = json!([]);
    let response = read_and_submit(&mut tools, &submission);
    assert!(codes(&response).contains(&"MISSING_SHARED_DEPENDENCY".to_string()));

    // Bound, but renamed.
    let mut tools = make_tools(&bundle);
    let mut submission = base_submission();
    submission["dependencies"][0]["concept"] = json!("predicate register");
    let response = read_and_submit(&mut tools, &submission);
    assert!(codes(&response).contains(&"SHARED_DEPENDENCY_NAME_MISMATCH".to_string()));

    // Bound, but not linked to any local claim.
    let mut tools = make_tools(&bundle);
    let mut submission = base_submission();
    submission["dependencies"][0]["semanticClaimIds"] = json!([]);
    let response = read_and_submit(&mut tools, &submission);
    assert!(codes(&response).contains(&"MISSING_SHARED_DEPENDENCY_CLAIMS".to_string()));

    // Linked to a claim this artifact never defines.
    let mut tools = make_tools(&bundle);
    let mut submission = base_submission();
    submission["dependencies"][0]["semanticClaimIds"] = json!(["claim:nowhere"]);
    let response = read_and_submit(&mut tools, &submission);
    assert!(codes(&response).contains(&"UNKNOWN_SEMANTIC_CLAIM_ID".to_string()));
}

#[test]
fn non_normative_resolutions_cannot_be_laundered_into_specification_facts() {
    let bundle = bundle_with(
        vec![record("evidence:op", "OPERATION", "html")],
        vec![json!({
            "resolutionId": "resolution:rounding",
            "unitId": "unit:add",
            "nonNormative": true,
            "role": "OPERATION",
            "provenance": "INTERNET",
        })],
    );
    let mut submission = base_submission();
    submission["identity"]["evidenceIds"] = json!(["evidence:op"]);
    submission["syntaxForms"][0]["evidenceIds"] = json!(["evidence:op"]);
    submission["inputs"][0]["evidenceIds"] = json!(["evidence:op"]);
    submission["result"]["evidenceIds"] = json!(["evidence:op"]);

    // Citing a resolution from a SOURCE_FACT claim.
    let mut tools = make_tools(&bundle);
    let mut bad = submission.clone();
    bad["claims"][0]["evidenceIds"] = json!(["evidence:op", "resolution:rounding"]);
    let response = read_and_submit(&mut tools, &bad);
    assert!(codes(&response).contains(&"NON_NORMATIVE_CLAIM_KIND".to_string()));

    // Using a resolution somewhere else without any ASSUMPTION claim owning it.
    let mut tools = make_tools(&bundle);
    let mut unmapped = submission.clone();
    unmapped["operation"]["evidenceIds"] = json!(["evidence:op", "resolution:rounding"]);
    let response = read_and_submit(&mut tools, &unmapped);
    assert!(codes(&response).contains(&"UNMAPPED_NON_NORMATIVE_RESOLUTION".to_string()));

    // Correctly owned by an ASSUMPTION claim.
    let mut tools = make_tools(&bundle);
    let mut good = submission.clone();
    good["operation"]["evidenceIds"] = json!(["evidence:op", "resolution:rounding"]);
    good["claims"] = json!([
        {"claimId": "claim:1", "kind": "SOURCE_FACT",
         "statement": "add computes the sum of its two source operands",
         "evidenceIds": ["evidence:op"]},
        {"claimId": "claim:2", "kind": "ASSUMPTION",
         "statement": "rounding follows the platform default",
         "evidenceIds": ["resolution:rounding"]},
    ]);
    let response = read_and_submit(&mut tools, &good);
    assert_eq!(response["accepted"], json!(true), "{response}");
}

#[test]
fn a_dual_rendition_bundle_requires_factual_claims_to_cite_both() {
    let bundle = bundle_with(
        vec![
            record("evidence:op-html", "OPERATION", "html"),
            record("evidence:op-pdf", "OPERATION", "pdf"),
        ],
        vec![],
    );
    let mut submission = base_submission();
    for path in ["identity", "result", "operation"] {
        submission[path]["evidenceIds"] = json!(["evidence:op-html", "evidence:op-pdf"]);
    }
    submission["syntaxForms"][0]["evidenceIds"] = json!(["evidence:op-html"]);
    submission["inputs"][0]["evidenceIds"] = json!(["evidence:op-html"]);

    // HTML only on a factual claim.
    let mut tools = make_tools(&bundle);
    let mut bad = submission.clone();
    bad["claims"][0]["evidenceIds"] = json!(["evidence:op-html"]);
    let response = read_and_submit(&mut tools, &bad);
    let found = codes(&response);
    assert!(found.contains(&"MISSING_CLAIM_RENDITION".to_string()), "{found:?}");

    // Both renditions cited.
    let mut tools = make_tools(&bundle);
    let mut good = submission.clone();
    good["claims"][0]["evidenceIds"] = json!(["evidence:op-html", "evidence:op-pdf"]);
    let response = read_and_submit(&mut tools, &good);
    assert_eq!(response["accepted"], json!(true), "{response}");
}

#[test]
fn restating_a_claim_with_the_same_authority_is_a_duplicate() {
    let bundle = base_bundle();
    let mut tools = make_tools(&bundle);
    let mut submission = base_submission();
    submission["claims"] = json!([
        {"claimId": "claim:1", "kind": "SOURCE_FACT",
         "statement": "add computes the sum of its two source operands",
         "evidenceIds": ["evidence:op"]},
        // Same meaning, different whitespace and case.
        {"claimId": "claim:2", "kind": "SOURCE_FACT",
         "statement": "Add   computes the sum of its two source operands",
         "evidenceIds": ["evidence:op"]},
    ]);
    let response = read_and_submit(&mut tools, &submission);
    assert!(codes(&response).contains(&"DUPLICATE_CLAIM".to_string()));
}

#[test]
fn insufficient_evidence_is_a_first_class_outcome() {
    let bundle = base_bundle();
    let mut tools = make_tools(&bundle);
    let response = read_and_submit(
        &mut tools,
        &json!({
            "outcome": "INSUFFICIENT_EVIDENCE",
            "missingAspects": ["the overflow behaviour is never stated"],
            "explanation": "the bundle describes the syntax but not the wrapping semantics",
            "evidenceIds": ["evidence:syntax"],
        }),
    );
    assert_eq!(response["accepted"], json!(true), "{response}");
    let artifact = tools.artifact().unwrap();
    assert_eq!(artifact["outcome"], json!("INSUFFICIENT_EVIDENCE"));
    // The payload lands under `failure`, never `semantics`.
    assert!(artifact.get("semantics").is_none());
    assert_eq!(
        artifact["failure"]["missingAspects"][0],
        json!("the overflow behaviour is never stated")
    );
}

#[test]
fn a_guess_dressed_as_a_failure_is_still_rejected() {
    let bundle = base_bundle();
    let mut tools = make_tools(&bundle);
    let response = read_and_submit(
        &mut tools,
        &json!({
            "outcome": "INSUFFICIENT_EVIDENCE",
            "missingAspects": ["overflow", "  overflow  "],
            "explanation": "",
            "claims": [],
        }),
    );
    let found = codes(&response);
    assert!(found.contains(&"DUPLICATE_MISSING_ASPECT".to_string()), "{found:?}");
    assert!(found.contains(&"INVALID_TEXT".to_string()), "{found:?}");
    assert!(found.contains(&"UNEXPECTED_FIELD".to_string()), "{found:?}");
}

#[test]
fn the_scope_refuses_a_bundle_that_disagrees_with_the_plan() {
    let unit_id = UnitId::parse("unit:add").unwrap();
    let created = "2026-01-01T00:00:00.000000Z";

    // Different index digest: every node ID in the plan would be meaningless.
    let mut bundle = base_bundle();
    bundle["sourceDatabaseDigest"] = json!("e".repeat(64));
    let error = SemanticScope::from_inputs(&plan(), &bundle, &unit_id, created).unwrap_err();
    assert!(error.to_string().contains("source specification does not match"));

    // Evidence belonging to another unit.
    let mut bundle = base_bundle();
    bundle["evidence"][0]["unitId"] = json!("unit:sub");
    let error = SemanticScope::from_inputs(&plan(), &bundle, &unit_id, created).unwrap_err();
    assert!(error.to_string().contains("belongs to a different unit"));

    // An empty bundle.
    let bundle = bundle_with(vec![], vec![]);
    let error = SemanticScope::from_inputs(&plan(), &bundle, &unit_id, created).unwrap_err();
    assert!(error.to_string().contains("must contain evidence"));

    // A resolution that forgot to declare itself non-normative.
    let bundle = bundle_with(
        vec![record("evidence:op", "OPERATION", "html")],
        vec![json!({"resolutionId": "resolution:x", "unitId": "unit:add"})],
    );
    let error = SemanticScope::from_inputs(&plan(), &bundle, &unit_id, created).unwrap_err();
    assert!(error.to_string().contains("invalid unit or authority flag"));
}

#[test]
fn the_run_id_and_hash_change_with_the_evidence() {
    let plan = plan();
    let first = scope(&plan, &base_bundle());
    let mut altered = base_bundle();
    altered["evidence"][0]["exactText"] = json!("add.type d, a, b; // reworded");
    let second = scope(&plan, &altered);

    assert_ne!(first.evidence_bundle_hash, second.evidence_bundle_hash);
    assert_ne!(first.run_id, second.run_id);
    assert!(first.run_id.starts_with("semantic-run:"));
}

#[test]
fn the_full_session_corrects_itself_after_a_diagnostic() {
    use harness::provider::recorded::RecordedProvider;
    use harness::provider::{StopReason, ToolCall, TurnResponse};
    use harness::session::anthropic_tool_use;
    use harness::{Session, Usage};

    let bundle = base_bundle();
    let mut tools = make_tools(&bundle);

    let turn = |id: &str, name: &str, input: Value| TurnResponse {
        assistant: anthropic_tool_use(id, name, input.clone()),
        text: String::new(),
        tool_calls: vec![ToolCall { id: id.into(), name: name.into(), input }],
        stop_reason: StopReason::ToolUse,
        usage: Usage::default(),
        model: "test".into(),
    };

    let mut wrong = base_submission();
    wrong["operation"]["evidenceIds"] = json!(["evidence:syntax"]);

    let provider = RecordedProvider::new(
        "test",
        vec![
            turn("t1", "get_evidence", json!({})),
            turn("t2", "submit_semantics", wrong),
            turn("t3", "submit_semantics", base_submission()),
        ],
    );

    let (outcome, transcript) = Session::new(&provider, "system", "prompt").run(&mut tools);
    assert!(outcome.is_ok(), "{:?}", outcome.err().map(|e| e.to_string()));
    assert_eq!(transcript.steps, 3);
    assert!(transcript.exchanges[1].tool_results[0]
        .output
        .contains("NONFUNCTIONAL_OPERATION"));
    assert!(tools.artifact().is_some());
}

#[test]
fn identity_is_required_but_a_result_is_only_required_for_instructions() {
    let bundle = base_bundle();

    // A concept with no result: valid. The Python implementation reported
    // EXPECTED_OBJECT here, which forced extractors to invent a result.
    // The bundle must carry no OPERATION or ALGORITHM evidence, or the unit is
    // treated as an instruction whatever its declared kind.
    let concept_bundle = bundle_with(
        vec![
            record("evidence:syntax", "SYNTAX", "html"),
            record("evidence:def", "SUPPORTING_DEFINITION", "html"),
        ],
        vec![],
    );
    let mut tools = make_tools(&concept_bundle);
    let mut concept = base_submission();
    let object = concept.as_object_mut().unwrap();
    object.insert("unitKind".into(), json!("SHARED_CONCEPT"));
    object.remove("result");
    object.remove("operation");
    object.remove("inputs");
    concept["claims"][0]["evidenceIds"] = json!(["evidence:syntax"]);
    let response = read_and_submit(&mut tools, &concept);
    assert_eq!(response["accepted"], json!(true), "{response}");

    // An instruction with no result is still rejected, by the diagnostic that
    // actually explains the problem.
    let mut tools = make_tools(&bundle);
    let mut instruction = base_submission();
    instruction.as_object_mut().unwrap().remove("result");
    let response = read_and_submit(&mut tools, &instruction);
    assert_eq!(codes(&response), vec!["MISSING_RESULT"]);

    // Identity remains mandatory for every unit kind.
    let mut tools = make_tools(&bundle);
    let mut anonymous = base_submission();
    anonymous.as_object_mut().unwrap().remove("identity");
    let response = read_and_submit(&mut tools, &anonymous);
    assert!(codes(&response).contains(&"EXPECTED_OBJECT".to_string()));
}

/// External review: `unitKind` was model-supplied, so a unit the plan selected
/// by instruction spelling could declare OTHER and skip the requirement to have
/// inputs, a result and an operation.
#[test]
fn a_unit_the_plan_asked_for_by_instruction_cannot_relabel_its_way_out() {
    // Only SYNTAX evidence, so nothing in the bundle forces the instruction
    // shape; the plan's request mode is the only thing that does.
    let bundle = bundle_with(vec![record("evidence:syntax", "SYNTAX", "html")], vec![]);
    let mut plan = plan();
    plan["request"] = json!({"scope": {"mode": "EXACT_INSTRUCTIONS", "instructions": ["add"]}});
    plan["sharedPrerequisites"] = json!([]);

    let scope = SemanticScope::from_inputs(
        &plan, &bundle, &UnitId::parse("unit:add").unwrap(), "2026-01-01T00:00:00.000000Z",
    )
    .expect("scope");
    assert!(scope.planned_as_instruction);

    let mut tools = SemanticTools::new(scope, bundle.clone(), extractor());
    let response = read_and_submit(
        &mut tools,
        &json!({
            "outcome": "SUCCESS",
            "unitKind": "OTHER",
            "identity": {"name": "add", "evidenceIds": ["evidence:syntax"]},
            "syntaxForms": [], "edgeCases": [], "restrictions": [],
            "dependencies": [],
            "claims": [{"claimId": "claim:1", "kind": "SOURCE_FACT",
                        "statement": "add names a destination and two sources",
                        "evidenceIds": ["evidence:syntax"]}],
        }),
    );
    let found = codes(&response);
    for code in ["MISSING_OPERATION", "MISSING_RESULT", "MISSING_INPUTS"] {
        assert!(found.contains(&code.to_string()), "{found:?}");
    }
}

/// A required citation must be required even when the field is absent, not only
/// when it is present and empty.
#[test]
fn a_component_that_omits_its_citations_is_refused() {
    let bundle = base_bundle();
    let mut tools = make_tools(&bundle);
    let mut submission = base_submission();
    // `identity` with no evidenceIds at all.
    submission["identity"] = json!({"name": "add"});
    let response = read_and_submit(&mut tools, &submission);
    assert!(
        codes(&response).contains(&"MISSING_EVIDENCE".to_string()),
        "{:?}",
        codes(&response)
    );
}

/// External review: unused functional evidence in the bundle forced the
/// instruction shape onto a unit that is not one.
#[test]
fn uncited_functional_evidence_does_not_make_a_concept_an_instruction() {
    // The bundle contains OPERATION evidence, but the artifact never cites it.
    let bundle = bundle_with(
        vec![
            record("evidence:syntax", "SYNTAX", "html"),
            record("evidence:unused-op", "OPERATION", "html"),
        ],
        vec![],
    );
    let mut plan = plan();
    plan["sharedPrerequisites"] = json!([]);
    let scope = SemanticScope::from_inputs(
        &plan, &bundle, &UnitId::parse("unit:add").unwrap(), "2026-01-01T00:00:00.000000Z",
    )
    .expect("scope");
    let mut tools = SemanticTools::new(scope, bundle.clone(), extractor());
    let response = read_and_submit(
        &mut tools,
        &json!({
            "outcome": "SUCCESS",
            "unitKind": "SHARED_CONCEPT",
            "identity": {"name": "add", "evidenceIds": ["evidence:syntax"]},
            "syntaxForms": [], "inputs": [], "edgeCases": [], "restrictions": [],
            "dependencies": [],
            "claims": [{"claimId": "claim:1", "kind": "SOURCE_FACT",
                        "statement": "the concept is named add",
                        "evidenceIds": ["evidence:syntax"]}],
        }),
    );
    assert_eq!(response["accepted"], json!(true), "{response}");
}

/// External review: the same statement could be asserted as both an ASSUMPTION
/// (resting on a non-normative resolution) and a SOURCE_FACT, laundering the
/// assumption into something the specification says.
#[test]
fn the_same_statement_cannot_be_asserted_with_two_authorities() {
    let bundle = bundle_with(
        vec![record("evidence:op", "OPERATION", "html")],
        vec![json!({
            "resolutionId": "resolution:rounding", "unitId": "unit:add",
            "nonNormative": true, "role": "OPERATION", "provenance": "INTERNET",
        })],
    );
    let mut tools = make_tools(&bundle);
    let mut submission = base_submission();
    submission["claims"] = json!([
        {"claimId": "claim:1", "kind": "ASSUMPTION",
         "statement": "rounding follows the platform default",
         "evidenceIds": ["resolution:rounding"]},
        {"claimId": "claim:2", "kind": "SOURCE_FACT",
         "statement": "Rounding  follows the platform default",
         "evidenceIds": ["evidence:op"]},
    ]);
    submission["dependencies"][0]["semanticClaimIds"] = json!(["claim:1"]);
    let response = read_and_submit(&mut tools, &submission);
    assert!(
        codes(&response).contains(&"CONFLICTING_CLAIM_AUTHORITY".to_string()),
        "{:?}",
        codes(&response)
    );
}
