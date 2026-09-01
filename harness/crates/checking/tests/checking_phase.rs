//! Phase 6 against a real Phase-1 index.

use std::collections::BTreeMap;
use std::path::PathBuf;

use serde_json::{Value, json};
use spec2lean_checking::{CheckInputs, check};
use spec2lean_specdb::fixture;

struct Fixture(PathBuf);

impl Fixture {
    fn new(name: &str) -> Self {
        let path =
            std::env::temp_dir().join(format!("s2l-check-{name}-{}.sqlite", std::process::id()));
        let _ = std::fs::remove_file(&path);
        fixture::build(&path).expect("fixture index");
        Self(path)
    }
}

impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = std::fs::remove_file(&self.0);
    }
}

const SOURCE: &str = "namespace Spec\ndef syntaxForm : String := \"add\"\ndef predicate : Type := Bool\nend Spec\n";

/// An evidence record as Phase 3 would have written it, with text that really
/// is what the fixture index holds.
fn evidence(id: &str, node: &str, text: &str) -> Value {
    json!({
        "evidenceId": id,
        "unitId": "unit:add",
        "role": "SYNTAX",
        "tier": "CORE",
        "sourceType": "html",
        "sourceNodeIds": [node],
        "sourceSpanIds": [],
        "exactText": text,
        "documentId": "doc:html",
        "documentSha256": "a".repeat(64),
    })
}

fn bundles() -> BTreeMap<String, Value> {
    BTreeMap::from([(
        "unit:add".to_string(),
        json!({
            "unit": {"unitId": "unit:add"},
            "evidence": [
                evidence("evidence:syntax", "node:html-syntax", "add.type d, a, b;"),
                evidence("evidence:def", "node:html-def", "predicate: a one-bit value."),
            ],
        }),
    )])
}

fn semantics() -> BTreeMap<String, Value> {
    BTreeMap::from([(
        "unit:add".to_string(),
        json!({
            "unit": {"unitId": "unit:add"},
            "semantics": {"claims": [
                {"claimId": "claim:syntax", "kind": "SOURCE_FACT",
                 "statement": "the instruction form is add.type d, a, b;",
                 "evidenceIds": ["evidence:syntax"]},
                {"claimId": "claim:predicate", "kind": "SOURCE_FACT",
                 "statement": "a predicate is a one-bit value",
                 "evidenceIds": ["evidence:def"]},
            ]},
        }),
    )])
}

fn manifest() -> Value {
    json!({"declarations": [
        {"declaration": "Spec.syntaxForm", "role": "PRIMARY_TYPE",
         "claimRefs": [{"unitId": "unit:add", "claimId": "claim:syntax"}]},
        {"declaration": "Spec.predicate", "role": "SEMANTIC_HELPER",
         "claimRefs": [{"unitId": "unit:add", "claimId": "claim:predicate"}]},
    ]})
}

fn run(bundles: &BTreeMap<String, Value>, semantics: &BTreeMap<String, Value>, manifest: &Value, source: &str, fixture: &Fixture) -> spec2lean_checking::CheckReport {
    check(
        &CheckInputs {
            bundles,
            semantics,
            manifest,
            core_manifest: None,
            source,
            core_source: None,
        },
        &fixture.0,
    )
    .expect("check runs")
}

#[test]
fn a_complete_group_passes_both_directions() {
    let fixture = Fixture::new("pass");
    let report = run(&bundles(), &semantics(), &manifest(), SOURCE, &fixture);
    assert!(report.passed(), "{}", report.summary());
    // Two claims and two evidence items, all reaching Lean.
    assert_eq!(report.coverage.covered.len(), 4);
    assert!(report.coverage.uncovered.is_empty());
    assert_eq!(report.traceability.declarations_checked, 2);
    assert_eq!(report.traceability.evidence_verified, 2);
}

#[test]
fn a_claim_that_reaches_no_declaration_is_uncovered() {
    let fixture = Fixture::new("uncovered");
    let mut manifest = manifest();
    // Drop the mapping for the predicate claim.
    manifest["declarations"] = json!([manifest["declarations"][0]]);
    let report = run(&bundles(), &semantics(), &manifest, SOURCE, &fixture);
    assert!(!report.passed(), "{}", report.summary());
    let uncovered: Vec<&str> = report
        .coverage
        .uncovered
        .iter()
        .map(|item| item.item_id.as_str())
        .collect();
    // Both the claim and the evidence it rests on are now unreachable.
    assert!(uncovered.contains(&"claim:predicate"), "{uncovered:?}");
    assert!(uncovered.contains(&"evidence:def"), "{uncovered:?}");
    assert!(report.summary().contains("reaches no declaration"));
}

/// The check that makes the chain mean something: the recorded text must still
/// be what the index holds.
#[test]
fn evidence_that_no_longer_matches_the_index_is_caught() {
    let fixture = Fixture::new("drift");
    let mut bundles = bundles();
    bundles.get_mut("unit:add").unwrap()["evidence"][0]["exactText"] =
        json!("add.type d, a, b; -- and something the specification never said");
    let report = run(&bundles, &semantics(), &manifest(), SOURCE, &fixture);

    assert!(!report.passed(), "{}", report.summary());
    let link = report
        .traceability
        .broken
        .iter()
        .find(|link| link.code == "EVIDENCE_DRIFT")
        .expect("drift is reported");
    assert_eq!(link.evidence_id.as_deref(), Some("evidence:syntax"));
    assert!(link.message.contains("no longer matches the index"), "{}", link.message);
}

#[test]
fn a_document_rebuilt_under_the_artifacts_is_caught() {
    let fixture = Fixture::new("rebuilt");
    let mut bundles = bundles();
    // The record claims a document hash the index no longer has.
    bundles.get_mut("unit:add").unwrap()["evidence"][0]["documentSha256"] = json!("f".repeat(64));
    let report = run(&bundles, &semantics(), &manifest(), SOURCE, &fixture);
    assert!(!report.passed(), "{}", report.summary());
    let link = &report.traceability.broken[0];
    assert_eq!(link.code, "EVIDENCE_DRIFT");
    assert!(link.message.contains("the document has changed"), "{}", link.message);
}

#[test]
fn a_source_node_deleted_from_the_index_is_caught() {
    let fixture = Fixture::new("deleted");
    let mut bundles = bundles();
    bundles.get_mut("unit:add").unwrap()["evidence"][0]["sourceNodeIds"] =
        json!(["node:removed-by-a-reindex"]);
    let report = run(&bundles, &semantics(), &manifest(), SOURCE, &fixture);
    assert!(!report.passed());
    assert!(report.traceability.broken[0]
        .message
        .contains("no longer in the index"));
}

#[test]
fn a_manifest_naming_lean_that_does_not_exist_is_caught() {
    let fixture = Fixture::new("undefined");
    let mut manifest = manifest();
    manifest["declarations"][0]["declaration"] = json!("Spec.neverWritten");
    let report = run(&bundles(), &semantics(), &manifest, SOURCE, &fixture);
    assert!(!report.passed());
    let link = report
        .traceability
        .broken
        .iter()
        .find(|link| link.code == "UNDEFINED_DECLARATION")
        .expect("reported");
    assert_eq!(link.declaration.as_deref(), Some("Spec.neverWritten"));
}

#[test]
fn a_declaration_citing_a_claim_nothing_defines_is_caught() {
    let fixture = Fixture::new("phantom");
    let mut manifest = manifest();
    manifest["declarations"][0]["claimRefs"] =
        json!([{"unitId": "unit:add", "claimId": "claim:invented"}]);
    let report = run(&bundles(), &semantics(), &manifest, SOURCE, &fixture);
    assert!(!report.passed());
    assert!(report
        .traceability
        .broken
        .iter()
        .any(|link| link.code == "MISSING_CLAIM"));
}

/// A claim represented only by the shared core is still represented.
#[test]
fn declarations_in_the_frozen_core_count_towards_coverage() {
    let fixture = Fixture::new("core");
    let core_source = "namespace Shared\ndef predicate : Type := Bool\nend Shared\n";
    let core_manifest = json!({"declarations": [
        {"declaration": "Shared.predicate", "role": "PRIMARY_TYPE",
         "claimRefs": [{"unitId": "unit:add", "claimId": "claim:predicate"}]},
    ]});
    // The group itself only covers the syntax claim.
    let mut manifest = manifest();
    manifest["declarations"] = json!([manifest["declarations"][0]]);
    let group_source = "namespace Spec\ndef syntaxForm : String := \"add\"\nend Spec\n";

    let report = check(
        &CheckInputs {
            bundles: &bundles(),
            semantics: &semantics(),
            manifest: &manifest,
            core_manifest: Some(&core_manifest),
            source: group_source,
            core_source: Some(core_source),
        },
        &fixture.0,
    )
    .expect("check runs");

    assert!(report.passed(), "{}", report.summary());
    let predicate = report
        .coverage
        .covered
        .iter()
        .find(|item| item.item_id == "claim:predicate")
        .expect("covered");
    assert_eq!(predicate.declarations, vec!["Shared.predicate".to_string()]);
}
