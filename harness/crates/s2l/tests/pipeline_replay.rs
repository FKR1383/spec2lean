//! The whole pipeline in one process, with no model and no network.
//!
//! Every phase has its own tests. This one exists for what those cannot see:
//! the artifacts each phase writes are the next phase's input, and a change
//! that keeps one phase's tests green can still break the seam between two.
//! Nothing here is mocked except the model's choices.

use std::collections::BTreeMap;
use std::path::PathBuf;

use harness::ToolSet;
use serde_json::{Value, json};
use spec2lean_checking::{CheckInputs, check};
use spec2lean_evidence::{EvidenceScope, EvidenceTools};
use spec2lean_planning::{PlanningRequest, PlanningTools, ScopeResolver, Selector};
use spec2lean_semantics::{SemanticScope, SemanticTools};
use spec2lean_shared_core::{SharedCoreTools, collect_shared_requirements};
use spec2lean_specdb::{SpecDb, UnitId, fixture};
use spec2lean_translation::{TranslationScope, TranslationTools};

const DIGEST: &str = "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd";
const CREATED: &str = "2026-09-01T00:00:00.000000Z";

fn lean_available() -> bool {
    std::process::Command::new("lean")
        .arg("--version")
        .output()
        .is_ok_and(|output| output.status.success())
}

struct Work {
    index: PathBuf,
    root: PathBuf,
}

impl Work {
    fn new(name: &str) -> Self {
        let root = std::env::temp_dir().join(format!("s2l-e2e-{name}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&root).expect("work root");
        let index = root.join("spec.sqlite");
        fixture::build(&index).expect("fixture index");
        Self { index, root }
    }
}

impl Drop for Work {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.root);
    }
}

/// A model that only ever makes the choices a correct one would.
///
/// The two-stage tools answer `accepted: false` with no diagnostics while the
/// compiler runs, so a rejection is specifically a response carrying
/// diagnostics.
fn expect_ok(outcome: &harness::ToolOutcome, what: &str) -> Value {
    assert!(!outcome.is_error(), "{what}: {outcome:?}");
    let value: Value = serde_json::from_str(&outcome.to_text()).unwrap_or(json!({}));
    if value.get("diagnostics").is_some() {
        panic!("{what} was rejected: {value}");
    }
    value
}

#[test]
fn a_request_becomes_checked_lean_through_every_phase() {
    if !lean_available() {
        eprintln!("skipping: lean is not on PATH");
        return;
    }
    let work = Work::new("full");
    let db = SpecDb::open(&work.index).expect("index opens");

    // ---- Phase 2 -------------------------------------------------------
    let request = PlanningRequest::new(
        "synthetic",
        "1.0",
        Selector::SourceSubtree(spec2lean_specdb::NodeId::parse("node:html-ch1").unwrap()),
    )
    .expect("request");
    let scope = ScopeResolver::new(&db).resolve(&request).expect("scope resolves");
    let units: Vec<String> = scope
        .candidate_units
        .iter()
        .filter_map(|unit| unit.get("unitId")?.as_str().map(str::to_string))
        .collect();
    assert_eq!(units.len(), 1, "{:?}", scope.candidate_units);
    let unit_id = units[0].clone();

    let mut planner = PlanningTools::new(&db, scope, "plan:e2e", DIGEST);
    expect_ok(
        &planner.call(
            "submit_plan",
            &json!({
                "requestedUnitIds": [unit_id],
                "translationGroups": [{
                    "name": "Add", "unitIds": [unit_id],
                    "reason": "the chapter this unit sits under",
                    "supportingNodeIds": ["node:html-ch1"], "origin": "EXPLICIT",
                }],
                "externalPrerequisites": [],
                "sharedPrerequisites": [{
                    "key": "predicate", "name": "predicate", "kind": "guard value",
                    "reason": "the unit guards execution on it",
                    "sourceNodeIds": ["node:html-def"],
                    "requiredBy": [unit_id],
                }],
                "dependencies": [],
            }),
        ),
        "plan",
    );
    let plan = planner.plan().expect("plan").clone();
    let shared_id = plan["sharedPrerequisites"][0]["dependencyId"]
        .as_str()
        .unwrap()
        .to_string();

    // ---- Phase 3 -------------------------------------------------------
    let parsed = UnitId::parse(&unit_id).unwrap();
    let evidence_scope = EvidenceScope::from_plan(&plan, &parsed).expect("evidence scope");
    let mut evidence = EvidenceTools::new(&db, evidence_scope).expect("evidence tools");
    evidence.call("spec_children", &json!({"nodeId": "node:html-ch1"}));
    expect_ok(
        &evidence.call("spec_show", &json!({"nodeId": "node:html-syntax"})),
        "spec_show",
    );
    expect_ok(
        &evidence.call(
            "submit_evidence",
            &json!({
                "unitId": unit_id,
                "selections": [
                    {"sourceNodeIds": ["node:html-syntax"], "role": "SYNTAX", "tier": "CORE",
                     "rationale": "the instruction form"},
                    {"sourceNodeIds": ["node:html-def"], "role": "SUPPORTING_DEFINITION",
                     "tier": "SUPPORTING", "rationale": "defines predicate"},
                ],
            }),
        ),
        "evidence",
    );
    let bundle = evidence.bundle().expect("bundle").clone();
    let evidence_ids: Vec<String> = bundle["evidence"]
        .as_array()
        .unwrap()
        .iter()
        .map(|item| item["evidenceId"].as_str().unwrap().to_string())
        .collect();

    // ---- Phase 4 -------------------------------------------------------
    let semantic_scope =
        SemanticScope::from_inputs(&plan, &bundle, &parsed, CREATED).expect("semantic scope");
    let extractor = json!({"provider": "replay", "model": "none"});
    let mut semantics = SemanticTools::new(semantic_scope, bundle.clone(), extractor.clone());
    semantics.call("get_evidence", &json!({}));
    expect_ok(
        &semantics.call(
            "submit_semantics",
            &json!({
                "outcome": "SUCCESS", "unitKind": "LANGUAGE_CONSTRUCT",
                "identity": {"name": "Add", "evidenceIds": [evidence_ids[0]]},
                "syntaxForms": [{"form": "add.type d, a, b;", "evidenceIds": [evidence_ids[0]]}],
                "inputs": [], "edgeCases": [], "stateEffects": [], "restrictions": [],
                "dependencies": [{
                    "dependencyId": shared_id, "concept": "predicate",
                    "description": "the one-bit guard on execution",
                    "semanticClaimIds": ["claim:guard"], "evidenceIds": [evidence_ids[1]],
                }],
                "claims": [
                    {"claimId": "claim:form", "kind": "SOURCE_FACT",
                     "statement": "the instruction form is add.type d, a, b;",
                     "evidenceIds": [evidence_ids[0]]},
                    {"claimId": "claim:guard", "kind": "SOURCE_FACT",
                     "statement": "a predicate is a one-bit value that guards execution",
                     "evidenceIds": [evidence_ids[1]]},
                ],
            }),
        ),
        "semantics",
    );
    let artifact = semantics.artifact().expect("artifact").clone();
    let semantics_by_unit = BTreeMap::from([(unit_id.clone(), artifact)]);

    // ---- the shared core -----------------------------------------------
    let requirements =
        collect_shared_requirements(&plan, &semantics_by_unit, None).expect("requirements");
    assert_eq!(requirements.len(), 1);
    let mut core = SharedCoreTools::new(
        requirements,
        "synthetic",
        "1.0",
        DIGEST,
        extractor.clone(),
        work.root.join("core"),
        "lean",
    );
    expect_ok(
        &core.call(
            "submit_core",
            &json!({
                "leanSource": "namespace Shared.Predicate\n\n\
                    /-- A predicate is a one-bit value that guards execution. -/\n\
                    def Predicate : Type := Bool\n\n\
                    end Shared.Predicate\n",
                "concepts": [{"dependencyId": shared_id,
                              "leanDeclarations": ["Shared.Predicate.Predicate"]}],
                "declarations": [{"declaration": "Shared.Predicate.Predicate",
                                  "role": "PRIMARY_TYPE",
                                  "claimRefs": [{"unitId": unit_id, "claimId": "claim:guard"}]}],
            }),
        ),
        "core structure",
    );
    let message = core.after_tool_call().expect("the core is compiled");
    assert!(message.contains("lean build: PASS"), "{message}");
    assert!(message.contains("axiom audit: PASS"), "{message}");
    let frozen = core.frozen().expect("frozen core");
    let core_path = work
        .root
        .join("core")
        .join(frozen.lean_module.split('.').collect::<PathBuf>())
        .with_extension("lean");

    // ---- Phase 5 -------------------------------------------------------
    let translation_scope = TranslationScope::from_inputs(
        &plan, "Add", &semantics_by_unit, CREATED, Some(&frozen.manifest),
    )
    .expect("translation scope");
    let group_dir = work.root.join("group");
    let mut translation = TranslationTools::new(
        translation_scope, group_dir.join("lean"), "lean", extractor,
    )
    .with_shared_core(&frozen.lean_module, core_path.clone());

    let source = format!(
        "import {}\n\nnamespace Spec2Lean.Synthetic.Add\n\n\
         open Shared.Predicate\n\n\
         /-- The instruction form: add.type d, a, b; -/\n\
         def form : String := \"add.type d, a, b;\"\n\n\
         /-- Execution is guarded by a predicate. -/\n\
         def guarded (p : Predicate) : Bool := p\n\n\
         end Spec2Lean.Synthetic.Add\n",
        frozen.lean_module
    );
    expect_ok(
        &translation.call(
            "submit_translation",
            &json!({
                "leanSource": source,
                "declarations": [
                    {"declaration": "Spec2Lean.Synthetic.Add.form", "role": "PRIMARY_TYPE",
                     "claimRefs": [{"unitId": unit_id, "claimId": "claim:form"}]},
                    {"declaration": "Spec2Lean.Synthetic.Add.guarded", "role": "OPERATION",
                     "claimRefs": [{"unitId": unit_id, "claimId": "claim:guard"}]},
                ],
                "sharedUses": [{"dependencyId": shared_id,
                                "leanDeclarations": ["Shared.Predicate.Predicate"]}],
            }),
        ),
        "translation structure",
    );
    let message = translation.after_tool_call().expect("the group is compiled");
    assert!(message.contains("lean build: PASS"), "{message}");
    assert!(message.contains("axiom audit: PASS"), "{message}");
    assert!(message.contains("Translation accepted"), "{message}");
    let manifest = translation.manifest().expect("manifest").clone();

    // ---- Phase 6 -------------------------------------------------------
    let lean_file = manifest["leanFile"].as_str().unwrap();
    let group_source = std::fs::read_to_string(group_dir.join("lean").join(lean_file)).unwrap();
    let core_source = std::fs::read_to_string(&core_path).unwrap();
    let report = check(
        &CheckInputs {
            bundles: &BTreeMap::from([(unit_id.clone(), bundle)]),
            semantics: &semantics_by_unit,
            manifest: &manifest,
            core_manifest: Some(&frozen.manifest),
            source: &group_source,
            core_source: Some(&core_source),
        },
        &work.index,
    )
    .expect("check runs");
    assert!(report.passed(), "{}", report.summary());

    // Every claim reaches Lean, in the group or in the core, and every
    // declaration traces back to text still in the index.
    assert_eq!(report.coverage.uncovered.len(), 0);
    assert_eq!(report.traceability.evidence_verified, 2);
    assert_eq!(
        manifest["claimIndex"][format!("{unit_id}/claim:form")],
        json!(["Spec2Lean.Synthetic.Add.form"])
    );
}

/// The same run, with the index rebuilt underneath the finished artifacts.
#[test]
fn a_finished_run_stops_passing_when_the_specification_moves() {
    if !lean_available() {
        eprintln!("skipping: lean is not on PATH");
        return;
    }
    // Reuse the happy path's artifacts by rebuilding them here would duplicate
    // the whole test; instead check the property the seam depends on: an
    // evidence record whose text no longer matches the index fails Phase 6.
    let work = Work::new("moved");
    let db = SpecDb::open(&work.index).expect("index");
    let row = db
        .node(&spec2lean_specdb::NodeId::parse("node:html-syntax").unwrap())
        .expect("node");
    let bundle = json!({
        "unit": {"unitId": "unit:add"},
        "evidence": [{
            "evidenceId": "evidence:1", "unitId": "unit:add", "role": "SYNTAX", "tier": "CORE",
            "sourceType": "html", "sourceNodeIds": ["node:html-syntax"], "sourceSpanIds": [],
            // What the specification said when this was retrieved.
            "exactText": format!("{} (since revised)", row.raw_text),
            "documentId": "doc:html", "documentSha256": "a".repeat(64),
        }],
    });
    let semantics = BTreeMap::from([(
        "unit:add".to_string(),
        json!({"unit": {"unitId": "unit:add"}, "semantics": {"claims": [
            {"claimId": "claim:form", "kind": "SOURCE_FACT", "statement": "the form",
             "evidenceIds": ["evidence:1"]}]}}),
    )]);
    let report = check(
        &CheckInputs {
            bundles: &BTreeMap::from([("unit:add".to_string(), bundle)]),
            semantics: &semantics,
            manifest: &json!({"declarations": [{"declaration": "F", "role": "PRIMARY_TYPE",
                "claimRefs": [{"unitId": "unit:add", "claimId": "claim:form"}]}]}),
            core_manifest: None,
            source: "def F : Nat := 1\n",
            core_source: None,
        },
        &work.index,
    )
    .expect("check runs");
    assert!(!report.passed(), "{}", report.summary());
    assert!(report.summary().contains("no longer matches the index"));
}
