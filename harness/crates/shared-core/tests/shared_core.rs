//! The frozen shared core, end to end, against real `lean`.

use std::collections::BTreeMap;
use std::path::PathBuf;

use harness::ToolSet;
use serde_json::{Value, json};
use spec2lean_shared_core::{SharedCoreTools, collect_shared_requirements};
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
        let path = std::env::temp_dir().join(format!("s2l-core-{name}-{}", std::process::id()));
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

const SHARED: &str = "shared:predicate";

fn unit(id: &str, name: &str) -> Value {
    json!({"unitId": id, "name": name, "sourceNodeIds": ["node:x"]})
}

/// Two units in two groups, both depending on one shared concept.
fn plan() -> Value {
    json!({
        "planRunId": "plan:test",
        "language": "synthetic",
        "version": "1.0",
        "sourceDatabaseDigest": "d".repeat(64),
        "requestedUnits": [unit("unit:add", "add"), unit("unit:sub", "sub")],
        "translationGroups": [
            {"name": "Add", "unitIds": ["unit:add"]},
            {"name": "Sub", "unitIds": ["unit:sub"]},
        ],
        "sharedPrerequisites": [{
            "dependencyId": SHARED,
            "name": "predicate",
            "kind": "guard value",
            "sourceNodeIds": ["node:def"],
            "requiredBy": ["unit:add", "unit:sub"],
        }],
    })
}

fn semantics_for(unit_id: &str, name: &str) -> Value {
    json!({
        "phase": "SEMANTIC_EXTRACTOR",
        "outcome": "SUCCESS",
        "planRunId": "plan:test",
        "language": "synthetic",
        "version": "1.0",
        "unit": unit(unit_id, name),
        "runId": format!("semantic-run:{name}"),
        "semantics": {
            "claims": [
                {"claimId": "claim:guard", "kind": "SOURCE_FACT",
                 "statement": "a predicate is a one-bit value that guards execution"},
                {"claimId": "claim:op", "kind": "SOURCE_FACT",
                 "statement": format!("{name} computes a result from two operands")},
            ],
            "dependencies": [{
                "dependencyId": SHARED,
                "concept": "predicate",
                "description": "the one-bit guard that decides whether the operation executes",
                "semanticClaimIds": ["claim:guard"],
            }],
        },
    })
}

fn semantics() -> BTreeMap<String, Value> {
    BTreeMap::from([
        ("unit:add".to_string(), semantics_for("unit:add", "add")),
        ("unit:sub".to_string(), semantics_for("unit:sub", "sub")),
    ])
}

/// A group receives exactly its own units' artifacts, never the whole plan's.
fn semantics_of(unit_id: &str) -> BTreeMap<String, Value> {
    let all = semantics();
    BTreeMap::from([(unit_id.to_string(), all[unit_id].clone())])
}

const CORE_SOURCE: &str = "namespace Spec2LeanShared.Predicate\n\n\
/-- A predicate is a one-bit value that guards execution. -/\n\
def Predicate : Type := Bool\n\n\
/-- Whether a guarded operation executes under a predicate. -/\n\
def executes (p : Predicate) : Bool := p\n\n\
end Spec2LeanShared.Predicate\n";

fn core_submission() -> Value {
    json!({
        "leanSource": CORE_SOURCE,
        "concepts": [{
            "dependencyId": SHARED,
            "leanDeclarations": ["Spec2LeanShared.Predicate.Predicate"],
        }],
        "declarations": [
            {"declaration": "Spec2LeanShared.Predicate.Predicate", "role": "PRIMARY_TYPE",
             "claimRefs": [{"unitId": "unit:add", "claimId": "claim:guard"}]},
            {"declaration": "Spec2LeanShared.Predicate.executes", "role": "SEMANTIC_HELPER",
             "claimRefs": [{"unitId": "unit:sub", "claimId": "claim:guard"}],
             "supportsDeclarations": ["Spec2LeanShared.Predicate.Predicate"]},
        ],
    })
}

fn core_tools(work: &Work) -> SharedCoreTools {
    let requirements = collect_shared_requirements(&plan(), &semantics(), None).expect("requirements");
    SharedCoreTools::new(
        requirements,
        "synthetic",
        "1.0",
        "d".repeat(64),
        json!({"provider": "test", "model": "test"}),
        work.0.join("core"),
        "lean",
    )
}

fn freeze(work: &Work) -> (SharedCoreTools, PathBuf) {
    let mut tools = core_tools(work);
    let outcome = tools.call("submit_core", &core_submission());
    assert!(!outcome.is_error(), "{outcome:?}");
    let text = tools.after_tool_call().expect("build ran");
    assert!(text.contains("lean build: PASS"), "{text}");
    assert!(tools.finished(), "{text}");
    let module = tools.frozen().unwrap().lean_module.clone();
    let path = work
        .0
        .join("core")
        .join(module.split('.').collect::<PathBuf>())
        .with_extension("lean");
    (tools, path)
}

#[test]
fn requirements_carry_the_claims_that_define_each_concept() {
    let requirements = collect_shared_requirements(&plan(), &semantics(), None).expect("ok");
    assert_eq!(requirements.len(), 1);
    let requirement = &requirements[0];
    assert_eq!(requirement.dependency_id, SHARED);
    assert_eq!(requirement.required_by, vec!["unit:add", "unit:sub"]);
    // Both units' guard claims, and nothing else.
    assert_eq!(
        requirement.claim_refs,
        vec![
            ("unit:add".to_string(), "claim:guard".to_string()),
            ("unit:sub".to_string(), "claim:guard".to_string()),
        ]
    );
    assert!(requirement.semantic_input_hash.starts_with("sha256:"));
}

#[test]
fn a_concept_phase_four_never_pinned_down_cannot_be_cored() {
    // The dependency names a claim the artifact does not define.
    let mut broken = semantics();
    broken.get_mut("unit:add").unwrap()["semantics"]["dependencies"][0]["semanticClaimIds"] =
        json!(["claim:nowhere"]);
    let error = collect_shared_requirements(&plan(), &broken, None).unwrap_err();
    assert!(error.to_string().contains("MISSING_SHARED_ABSTRACTION"), "{error}");
    assert!(error.to_string().contains("missing Phase-4 claims"), "{error}");

    // A unit that needs the concept has no successful artifact at all.
    let mut absent = semantics();
    absent.get_mut("unit:sub").unwrap()["outcome"] = json!("INSUFFICIENT_EVIDENCE");
    let error = collect_shared_requirements(&plan(), &absent, None).unwrap_err();
    assert!(error.to_string().contains("not successful"), "{error}");
}

#[test]
fn a_core_is_frozen_only_after_it_compiles() {
    if !lean_available() {
        eprintln!("skipping: lean is not on PATH");
        return;
    }
    let work = Work::new("freeze");
    let (tools, path) = freeze(&work);
    let frozen = tools.frozen().expect("frozen");

    assert!(frozen.core_run_id.starts_with("shared-core-run:"));
    assert!(frozen.lean_module.starts_with("Spec2LeanShared.Synthetic.V10.N"));
    assert!(frozen.source_hash.starts_with("sha256:"));
    assert_eq!(frozen.manifest["build"]["status"], json!("PASS"));
    // The registry records the full concept metadata, not just what was sent.
    let concept = &frozen.manifest["concepts"][0];
    assert_eq!(concept["dependencyId"], json!(SHARED));
    assert_eq!(concept["kind"], json!("guard value"));
    assert_eq!(concept["requiredBy"], json!(["unit:add", "unit:sub"]));
    // The file is on disk under its module path, ready to stage as a dependency.
    assert!(path.is_file(), "{}", path.display());
}

#[test]
fn a_core_that_does_not_compile_is_not_frozen() {
    if !lean_available() {
        eprintln!("skipping: lean is not on PATH");
        return;
    }
    let work = Work::new("badcore");
    let mut tools = core_tools(&work);
    let mut broken = core_submission();
    broken["leanSource"] = json!(
        "namespace Spec2LeanShared.Predicate\ndef Predicate : Type := \"not a type\"\nend Spec2LeanShared.Predicate\n"
    );
    broken["declarations"] = json!([{
        "declaration": "Spec2LeanShared.Predicate.Predicate", "role": "PRIMARY_TYPE",
        "claimRefs": [{"unitId": "unit:add", "claimId": "claim:guard"}],
    }]);
    assert!(!tools.call("submit_core", &broken).is_error());
    let text = tools.after_tool_call().expect("build ran");
    assert!(text.contains("lean build: FAIL"), "{text}");
    assert!(text.contains("not frozen"), "{text}");
    assert!(!tools.finished());
}

#[test]
fn a_core_must_represent_every_required_concept_and_cite_real_claims() {
    let work = Work::new("coreval");
    let codes = |submission: &Value| {
        let mut tools = core_tools(&work);
        let outcome = tools.call("submit_core", submission);
        let value: Value = serde_json::from_str(&outcome.to_text()).expect("json");
        assert_eq!(value["accepted"], json!(false), "{value}");
        value["diagnostics"]
            .as_array()
            .unwrap()
            .iter()
            .filter_map(|item| item["code"].as_str().map(str::to_string))
            .collect::<Vec<_>>()
    };

    // Represents nothing.
    let mut empty = core_submission();
    empty["concepts"] = json!([]);
    assert!(codes(&empty).contains(&"MISSING_SHARED_CONCEPT".to_string()));

    // Registers a declaration the source does not define.
    let mut phantom = core_submission();
    phantom["concepts"][0]["leanDeclarations"] = json!(["Spec2LeanShared.Predicate.Ghost"]);
    assert!(codes(&phantom).contains(&"MISSING_DECLARATION".to_string()));

    // Cites a claim that never described this concept.
    let mut wrong_claim = core_submission();
    wrong_claim["declarations"][0]["claimRefs"] =
        json!([{"unitId": "unit:add", "claimId": "claim:op"}]);
    assert!(codes(&wrong_claim).contains(&"UNKNOWN_CLAIM_REF".to_string()));

    // Escape hatches are refused before any build.
    let mut unsound = core_submission();
    unsound["leanSource"] = json!("axiom Predicate : Type\n");
    assert!(codes(&unsound).iter().any(|code| code.starts_with("FORBIDDEN_")));
}

/// The point of the whole mechanism: two groups, one representation.
#[test]
fn two_groups_compile_against_the_same_frozen_core() {
    if !lean_available() {
        eprintln!("skipping: lean is not on PATH");
        return;
    }
    let work = Work::new("groups");
    let (core_tools, core_path) = freeze(&work);
    let frozen = core_tools.frozen().expect("frozen");
    let module = &frozen.lean_module;

    for (group, unit_id, name) in [("Add", "unit:add", "add"), ("Sub", "unit:sub", "sub")] {
        let scope = TranslationScope::from_inputs(
            &plan(),
            group,
            &semantics_of(unit_id),
            "2026-01-01T00:00:00.000000Z",
            Some(&frozen.manifest),
        )
        .expect("scope resolves with a core");
        assert_eq!(scope.shared_dependency_ids(), vec![SHARED]);
        assert_eq!(scope.core_lean_module(), Some(module.as_str()));

        let mut tools = TranslationTools::new(
            scope,
            work.0.join(format!("group-{group}")),
            "lean",
            json!({"provider": "test", "model": "test"}),
        )
        .with_shared_core(module, core_path.clone());

        let source = format!(
            "import {module}\n\nnamespace Spec2Lean.Synthetic.{group}\n\n\
             open Spec2LeanShared.Predicate\n\n\
             def {name} (p : Predicate) (a b : Nat) : Nat := if executes p then a + b else a\n\n\
             end Spec2Lean.Synthetic.{group}\n"
        );
        let submission = json!({
            "leanSource": source,
            "declarations": [{
                "declaration": format!("Spec2Lean.Synthetic.{group}.{name}"),
                "role": "OPERATION",
                "claimRefs": [
                    {"unitId": unit_id, "claimId": "claim:guard"},
                    {"unitId": unit_id, "claimId": "claim:op"},
                ],
            }],
            "sharedUses": [{
                "dependencyId": SHARED,
                "leanDeclarations": ["Spec2LeanShared.Predicate.Predicate"],
            }],
        });
        assert!(!tools.call("submit_translation", &submission).is_error());
        let text = tools.after_tool_call().expect("build ran");
        assert!(text.contains("lean build: PASS"), "{group}: {text}");
        assert!(tools.finished(), "{group}: {text}");

        // The manifest pins the exact core this group compiled against.
        let manifest = tools.manifest().unwrap();
        assert_eq!(manifest["sharedCore"]["coreRunId"], json!(frozen.core_run_id));
        assert_eq!(manifest["sharedCore"]["sourceHash"], json!(frozen.source_hash));
        assert_eq!(manifest["sharedUses"][0]["dependencyId"], json!(SHARED));
    }
}

#[test]
fn a_group_must_import_the_core_and_bind_only_registered_declarations() {
    if !lean_available() {
        eprintln!("skipping: lean is not on PATH");
        return;
    }
    let work = Work::new("binding");
    let (core_tools, core_path) = freeze(&work);
    let frozen = core_tools.frozen().expect("frozen");
    let module = frozen.lean_module.clone();

    let make = || {
        let scope = TranslationScope::from_inputs(
            &plan(), "Add", &semantics_of("unit:add"), "t", Some(&frozen.manifest),
        )
        .expect("scope");
        TranslationTools::new(scope, work.0.join("g"), "lean", json!({"provider": "t", "model": "t"}))
            .with_shared_core(&module, core_path.clone())
    };
    let codes = |tools: &mut TranslationTools, submission: &Value| {
        let outcome = tools.call("submit_translation", submission);
        let value: Value = serde_json::from_str(&outcome.to_text()).expect("json");
        assert_eq!(value["accepted"], json!(false), "{value}");
        value["diagnostics"]
            .as_array()
            .unwrap()
            .iter()
            .filter_map(|item| item["code"].as_str().map(str::to_string))
            .collect::<Vec<_>>()
    };
    let body = "namespace Spec2Lean.Synthetic.Add\ndef add : Nat := 1\nend Spec2Lean.Synthetic.Add\n";
    let declarations = json!([{
        "declaration": "Spec2Lean.Synthetic.Add.add", "role": "OPERATION",
        "claimRefs": [
            {"unitId": "unit:add", "claimId": "claim:guard"},
            {"unitId": "unit:add", "claimId": "claim:op"},
        ],
    }]);

    // Uses the core but never imports it.
    let mut tools = make();
    let found = codes(&mut tools, &json!({
        "leanSource": body, "declarations": declarations,
        "sharedUses": [{"dependencyId": SHARED,
                        "leanDeclarations": ["Spec2LeanShared.Predicate.Predicate"]}],
    }));
    assert!(found.contains(&"MISSING_CORE_IMPORT".to_string()), "{found:?}");

    // Imports it, but binds a declaration the core never registered for this
    // concept — a helper that exists is still not the agreed representation.
    let mut tools = make();
    let found = codes(&mut tools, &json!({
        "leanSource": format!("import {module}\n{body}"), "declarations": declarations,
        "sharedUses": [{"dependencyId": SHARED,
                        "leanDeclarations": ["Spec2LeanShared.Predicate.executes"]}],
    }));
    assert!(found.contains(&"UNREGISTERED_SHARED_DECLARATION".to_string()), "{found:?}");

    // Imports it, but binds nothing.
    let mut tools = make();
    let found = codes(&mut tools, &json!({
        "leanSource": format!("import {module}\n{body}"), "declarations": declarations,
        "sharedUses": [],
    }));
    assert!(found.contains(&"MISSING_SHARED_USE".to_string()), "{found:?}");
}

/// External review: claim authorisation was one global union across every
/// required concept, so a single declaration citing concept B's claims could
/// stand in as the representation of concept A. This is that exact trigger.
#[test]
fn a_concept_cannot_be_represented_by_another_concepts_claims() {
    let work = Work::new("crosswired");
    let requirements = collect_shared_requirements(&plan(), &semantics(), None).expect("ok");
    let mut tools = SharedCoreTools::new(
        requirements,
        "synthetic",
        "1.0",
        "d".repeat(64),
        json!({"provider": "test", "model": "test"}),
        work.0.join("core"),
        "lean",
    );
    // One declaration, registered for the concept, citing a claim that
    // describes something else entirely.
    let outcome = tools.call(
        "submit_core",
        &json!({
            "leanSource": CORE_SOURCE,
            "concepts": [{
                "dependencyId": SHARED,
                "leanDeclarations": ["Spec2LeanShared.Predicate.Predicate"],
            }],
            "declarations": [
                {"declaration": "Spec2LeanShared.Predicate.Predicate", "role": "PRIMARY_TYPE",
                 "claimRefs": [{"unitId": "unit:add", "claimId": "claim:op"}]},
                {"declaration": "Spec2LeanShared.Predicate.executes", "role": "SEMANTIC_HELPER",
                 "claimRefs": [{"unitId": "unit:add", "claimId": "claim:op"}]},
            ],
        }),
    );
    let value: Value = serde_json::from_str(&outcome.to_text()).expect("json");
    assert_eq!(value["accepted"], json!(false), "{value}");
    let codes: Vec<&str> = value["diagnostics"]
        .as_array()
        .unwrap()
        .iter()
        .filter_map(|item| item["code"].as_str())
        .collect();
    // `claim:op` is not one of the claims that describe the predicate concept.
    assert!(
        codes.contains(&"UNKNOWN_CLAIM_REF") || codes.contains(&"UNGROUNDED_SHARED_CONCEPT"),
        "{codes:?}"
    );
    assert!(!tools.finished());
}

/// External review: `None == None` let a plan and an artifact that both omit
/// their identity agree about belonging to the same specification.
#[test]
fn artifacts_and_plans_missing_their_identity_do_not_match_by_default() {
    let mut bare_plan = plan();
    for key in ["planRunId", "language", "version"] {
        bare_plan.as_object_mut().unwrap().remove(key);
    }
    let mut bare_semantics = semantics();
    for artifact in bare_semantics.values_mut() {
        for key in ["planRunId", "language", "version"] {
            artifact.as_object_mut().unwrap().remove(key);
        }
    }
    let error = collect_shared_requirements(&bare_plan, &bare_semantics, None).unwrap_err();
    assert!(error.to_string().contains("belongs to another"), "{error}");
}
