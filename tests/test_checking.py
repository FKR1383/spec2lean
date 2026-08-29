from __future__ import annotations

import copy
import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from spec2lean.checking.build import run_build_test
from spec2lean.checking.logical import (
    coverage_test,
    group_coverage_test,
    group_traceability_test,
    traceability_test,
)
from spec2lean.checking.models import check_result, routing_for
from spec2lean.checking.render import render_markdown
from spec2lean.checking.runner import run_checks, run_group_checks
from spec2lean.cli import main
from spec2lean.database import connect, semantic_digest
from spec2lean.evidence.runner import unit_directory_name
from spec2lean.semantics.models import evidence_bundle_hash
from spec2lean.translation.models import semantics_artifact_hash


UNIT = {"unitId": "unit:check", "name": "check.unit", "sourceNodeIds": ["node:placeholder"]}
SOURCE = """namespace Spec2Lean.Check

def operation (a b : Nat) : Nat := a + b

def execute (a b : Nat) : Nat := operation a b

end Spec2Lean.Check
"""


def _inputs(database: Path) -> tuple[dict, dict, dict, dict]:
    with connect(database, read_only=True) as connection:
        node = connection.execute(
            "SELECT n.node_id, n.document_id, d.source_type, d.sha256, "
            "d.local_path, d.official_url "
            "FROM nodes n JOIN documents d USING(document_id) "
            "WHERE n.parent_id IS NOT NULL ORDER BY n.node_id LIMIT 1"
        ).fetchone()
        span = connection.execute(
            "SELECT span_id FROM source_spans WHERE node_id = ? ORDER BY ordinal LIMIT 1",
            (node["node_id"],),
        ).fetchone()
        digest = semantic_digest(connection)
    unit = copy.deepcopy(UNIT)
    unit["sourceNodeIds"] = [node["node_id"]]
    plan = {
        "schemaVersion": 3,
        "planRunId": "plan:check-test",
        "language": "synthetic",
        "version": "1.0",
        "sourceDatabaseDigest": digest,
        "requestedUnits": [unit],
        "translationGroups": [{
            "name": "InstructionSemantics",
            "unitIds": [unit["unitId"]],
            "reason": "Derived from the indexed synthetic instruction section.",
            "supportingNodeIds": [node["node_id"]],
            "origin": "INFERRED",
        }],
        "sharedPrerequisites": [],
    }
    evidence_id = "evidence:source"
    evidence = {
        "evidenceId": evidence_id,
        "unitId": unit["unitId"],
        "role": "OPERATION",
        "tier": "CORE",
        "sourceNodeId": node["node_id"],
        "sourceNodeIds": [node["node_id"]],
        "sourceSpanIds": [span["span_id"]] if span else [],
        "sourceType": node["source_type"],
        "documentId": node["document_id"],
        "documentSha256": node["sha256"],
        "sourcePath": node["local_path"],
        "officialUrl": node["official_url"],
        "provenance": [{
            "sourceNodeId": node["node_id"],
            "sourceSpans": ([{"spanId": span["span_id"]}] if span else []),
        }],
    }
    bundle = {
        "schemaVersion": 1,
        "phase": "RETRIEVE_EVIDENCE",
        "planRunId": plan["planRunId"],
        "language": plan["language"],
        "version": plan["version"],
        "sourceDatabaseDigest": digest,
        "unit": unit,
        "evidence": [evidence],
    }
    semantics = {
        "schemaVersion": 1,
        "phase": "SEMANTIC_EXTRACTOR",
        "planRunId": plan["planRunId"],
        "language": plan["language"],
        "version": plan["version"],
        "unit": unit,
        "evidenceBundleHash": evidence_bundle_hash(bundle),
        "runId": "semantic-run:check",
        "outcome": "SUCCESS",
        "semantics": {
            "claims": [
                {
                    "claimId": "claim:operation",
                    "kind": "SOURCE_FACT",
                    "statement": "The operation adds its inputs.",
                    "evidenceIds": [evidence_id],
                },
                {
                    "claimId": "claim:execution",
                    "kind": "DESIGN_DEPENDENCY",
                    "statement": "An execution entry point is needed.",
                    "evidenceIds": [],
                },
            ]
        },
    }
    manifest = {
        "schemaVersion": 1,
        "phase": "LLM_TRANSLATOR",
        "planRunId": plan["planRunId"],
        "language": plan["language"],
        "version": plan["version"],
        "unit": unit,
        "translationRunId": "translation-run:check",
        "semanticsRunId": semantics["runId"],
        "semanticsArtifactHash": semantics_artifact_hash(semantics),
        "leanFile": "Unit.lean",
        "declarations": [
            {
                "declaration": "Spec2Lean.Check.operation",
                "role": "OPERATION",
                "semanticClaimIds": ["claim:operation"],
            },
            {
                "declaration": "Spec2Lean.Check.execute",
                "role": "EXECUTION",
                "semanticClaimIds": ["claim:execution"],
            },
        ],
    }
    return plan, bundle, semantics, manifest


def _write_artifacts(
    tmp_path: Path, database: Path
) -> tuple[dict, Path, Path, Path, Path, Path]:
    plan, bundle, semantics, manifest = _inputs(database)
    slug = unit_directory_name(plan["requestedUnits"][0])
    roots = [tmp_path / name for name in ("plans", "evidence", "semantics", "translations", "checks")]
    plans_root, evidence_root, semantics_root, translations_root, checks_root = roots
    plan_dir = plans_root / "synthetic" / "1.0" / plan["planRunId"]
    plan_dir.mkdir(parents=True)
    (plan_dir / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    for root, name, value in (
        (evidence_root, "evidence.json", bundle),
        (semantics_root, "semantics.json", semantics),
        (translations_root, "translation-manifest.json", manifest),
    ):
        directory = root / "synthetic" / "1.0" / plan["planRunId"] / slug
        directory.mkdir(parents=True)
        (directory / name).write_text(json.dumps(value), encoding="utf-8")
    translation_dir = translations_root / "synthetic" / "1.0" / plan["planRunId"] / slug
    (translation_dir / "Unit.lean").write_text(SOURCE, encoding="utf-8")
    (translation_dir / "translator-run.json").write_text("{}", encoding="utf-8")
    return plan, evidence_root, semantics_root, translations_root, checks_root, plans_root


def _passing_build(_: Path) -> dict:
    return {
        "status": "PASS",
        "exitCode": 0,
        "leanVersion": "Lean (version 4.test)",
        "durationMs": 7,
        "diagnostics": [],
    }


def _failing_build(_: Path) -> dict:
    return {
        "status": "FAIL",
        "exitCode": 1,
        "leanVersion": "Lean (version 4.test)",
        "durationMs": 7,
        "diagnostics": [{
            "stream": "stderr", "severity": "ERROR", "message": "type mismatch",
            "file": "Unit.lean", "line": 3, "column": 1,
        }],
    }


def test_build_test_records_pass_failure_version_diagnostics_and_location(tmp_path, monkeypatch):
    lean = tmp_path / "lean"
    lean.write_text("", encoding="utf-8")
    monkeypatch.setattr("spec2lean.checking.build.shutil.which", lambda _: str(lean))

    def passing(command, **kwargs):
        if command[-1] == "--version":
            return subprocess.CompletedProcess(command, 0, "Lean (version 4.test)\n", "")
        return subprocess.CompletedProcess(command, 0, "", "")

    times = iter((10.0, 10.125))
    passed = run_build_test(tmp_path / "Unit.lean", run_command=passing, monotonic=lambda: next(times))
    assert passed == {
        "status": "PASS", "exitCode": 0, "leanVersion": "Lean (version 4.test)",
        "durationMs": 125, "diagnostics": [],
    }

    def failing(command, **kwargs):
        if command[-1] == "--version":
            return subprocess.CompletedProcess(command, 0, "Lean (version 4.test)\n", "")
        return subprocess.CompletedProcess(
            command, 1, "", "Unit.lean:3:7: error(lean.test): type mismatch\n"
            "  supplied\n"
            "has type\n"
            "  Nat\n"
            "but is expected to have type\n"
            "  UInt32\n"
        )

    times = iter((20.0, 20.01))
    failed = run_build_test(tmp_path / "Unit.lean", run_command=failing, monotonic=lambda: next(times))
    assert failed["status"] == "FAIL" and failed["exitCode"] == 1
    assert routing_for("FAIL", "PASS", "PASS") == ["TROUBLESHOOTER"]
    assert {
        key: failed["diagnostics"][0][key]
        for key in ("file", "line", "column", "severity")
    } == {"file": "Unit.lean", "line": 3, "column": 7, "severity": "ERROR"}
    assert len(failed["diagnostics"]) == 1
    assert "supplied\nhas type\n  Nat" in failed["diagnostics"][0]["message"]


@pytest.mark.skipif(shutil.which("lean") is None, reason="Lean toolchain is not installed")
def test_build_test_typechecks_valid_lean_with_project_toolchain(tmp_path):
    source = tmp_path / "Unit.lean"
    source.write_text("def phase6BuildSmoke : Nat := 6\n", encoding="utf-8")
    result = run_build_test(source)
    assert result["status"] == "PASS"
    assert result["exitCode"] == 0
    assert result["leanVersion"].startswith("Lean (version 4")


@pytest.mark.skipif(shutil.which("lean") is None, reason="Lean toolchain is not installed")
def test_build_test_stages_one_frozen_dependency_for_multiple_modules(tmp_path):
    frozen = tmp_path / "frozen" / "Core.lean"
    frozen.parent.mkdir()
    frozen.write_text(
        "namespace Spec2Lean.Synthetic.Shared\n"
        "abbrev Value := Nat\n"
        "end Spec2Lean.Synthetic.Shared\n",
        encoding="utf-8",
    )
    module = "Spec2Lean.Synthetic.Shared.Core"
    for index in (1, 2):
        source = tmp_path / f"Unit{index}.lean"
        source.write_text(
            f"import {module}\n"
            f"def sharedCoreConsumer{index} : Spec2Lean.Synthetic.Shared.Value := {index}\n",
            encoding="utf-8",
        )
        result = run_build_test(source, dependency_modules=[(module, frozen)])
        assert result["status"] == "PASS", result["diagnostics"]
    assert not frozen.with_suffix(".olean").exists()


def test_coverage_pass_and_missing_claim_routes_to_translator(html_database):
    plan, _, semantics, manifest = _inputs(html_database)
    covered = coverage_test(semantics, SOURCE, manifest)
    assert covered["status"] == "PASS" and covered["uncovered"] == []
    manifest["declarations"][1]["semanticClaimIds"] = ["claim:operation"]
    missing = coverage_test(semantics, SOURCE, manifest)
    assert missing["status"] == "FAIL"
    assert [item["itemId"] for item in missing["uncovered"]] == ["claim:execution"]
    result = check_result(
        plan=plan, unit=plan["requestedUnits"][0], translation_run_id="translation-run:check",
        build=_passing_build(Path()), coverage=missing,
        traceability={"status": "PASS", "validMappings": [], "brokenMappings": []},
    )
    assert result["routing"]["next"] == ["TRANSLATOR"]


def test_traceability_pass_and_missing_claim_mapping_routes_to_semantics(html_database):
    plan, bundle, semantics, manifest = _inputs(html_database)
    traced = traceability_test(plan, bundle, semantics, SOURCE, manifest, html_database)
    assert traced["status"] == "PASS" and len(traced["validMappings"]) == 2
    manifest["declarations"] = manifest["declarations"][:1]
    broken = traceability_test(plan, bundle, semantics, SOURCE, manifest, html_database)
    assert broken["status"] == "FAIL"
    assert "MISSING_CLAIM_MAPPING" in {item["code"] for item in broken["brokenMappings"]}
    result = check_result(
        plan=plan, unit=plan["requestedUnits"][0], translation_run_id="translation-run:check",
        build=_passing_build(Path()), coverage={"status": "PASS", "covered": [], "uncovered": []},
        traceability=broken,
    )
    assert result["routing"]["next"] == ["SEMANTIC_EXTRACTOR"]


def test_traceability_detects_broken_claim_evidence_reference(html_database):
    plan, bundle, semantics, manifest = _inputs(html_database)
    semantics["semantics"]["claims"][0]["evidenceIds"] = ["evidence:missing"]
    manifest["semanticsArtifactHash"] = semantics_artifact_hash(semantics)
    traced = traceability_test(plan, bundle, semantics, SOURCE, manifest, html_database)
    assert "MISSING_EVIDENCE" in {item["code"] for item in traced["brokenMappings"]}
    assert traced["status"] == "FAIL"


def test_traceability_detects_broken_phase1_source_provenance(html_database):
    plan, bundle, semantics, manifest = _inputs(html_database)
    bundle["evidence"][0]["sourceNodeIds"] = ["node:missing"]
    bundle["evidence"][0]["provenance"] = [{"sourceNodeId": "node:missing", "sourceSpans": []}]
    semantics["evidenceBundleHash"] = evidence_bundle_hash(bundle)
    manifest["semanticsArtifactHash"] = semantics_artifact_hash(semantics)
    traced = traceability_test(plan, bundle, semantics, SOURCE, manifest, html_database)
    assert "MISSING_SOURCE_NODE" in {item["code"] for item in traced["brokenMappings"]}


def test_group_coverage_and_traceability_resolve_imported_shared_core(html_database):
    plan, bundle, semantics, _ = _inputs(html_database)
    unit_id = plan["requestedUnits"][0]["unitId"]
    semantics["semantics"]["dependencies"] = [{
        "dependencyId": "shared:operation",
        "concept": "Common operation domain",
        "description": "The operation is shared with other requested units.",
        "semanticClaimIds": ["claim:operation"],
        "evidenceIds": ["evidence:source"],
    }]
    group_source = """namespace Spec2Lean.Synthetic.Unit

def operation (a b : Nat) : Nat := Spec2Lean.Synthetic.Shared.operation a b

def execute (a b : Nat) : Nat := a + b

end Spec2Lean.Synthetic.Unit
"""
    group_manifest = {
        "schemaVersion": 2,
        "phase": "LLM_GROUP_TRANSLATOR",
        "planRunId": plan["planRunId"],
        "language": plan["language"],
        "version": plan["version"],
        "group": {"name": "InstructionSemantics", "unitIds": [unit_id]},
        "translationRunId": "translation-group-run:check",
        "semanticsArtifacts": [{
            "unitId": unit_id,
            "runId": semantics["runId"],
            "artifactHash": semantics_artifact_hash(semantics),
        }],
        "declarations": [{
            "declaration": "Spec2Lean.Synthetic.Unit.operation",
            "role": "OPERATION",
            "claimRefs": [],
            "supportsDeclarations": ["Spec2Lean.Synthetic.Shared.operation"],
        }, {
            "declaration": "Spec2Lean.Synthetic.Unit.execute",
            "role": "EXECUTION",
            "claimRefs": [{"unitId": unit_id, "claimId": "claim:execution"}],
        }],
        "sharedUses": [{
            "dependencyId": "shared:operation",
            "leanDeclarations": ["Spec2Lean.Synthetic.Shared.operation"],
            "claimRefs": [{"unitId": unit_id, "claimId": "claim:operation"}],
        }],
    }
    core_source = """namespace Spec2Lean.Synthetic.Shared

def operation (a b : Nat) : Nat := a + b

end Spec2Lean.Synthetic.Shared
"""
    core_manifest = {
        "concepts": [{
            "dependencyId": "shared:operation",
            "name": "Common operation domain",
            "kind": "semantic-domain",
            "sourceNodeIds": plan["requestedUnits"][0]["sourceNodeIds"],
            "requiredBy": [unit_id],
            "semanticInputHash": "sha256:" + "a" * 64,
            "leanDeclarations": ["Spec2Lean.Synthetic.Shared.operation"],
            "claimRefs": [{"unitId": unit_id, "claimId": "claim:operation"}],
        }],
        "declarations": [{
            "declaration": "Spec2Lean.Synthetic.Shared.operation",
            "role": "OPERATION",
            "dependencyIds": ["shared:operation"],
            "claimRefs": [{"unitId": unit_id, "claimId": "claim:operation"}],
        }],
    }

    without_core = group_coverage_test(unit_id, semantics, group_source, group_manifest)
    assert [item["itemId"] for item in without_core["uncovered"]] == [
        "claim:operation", "evidence:source"
    ]
    coverage = group_coverage_test(
        unit_id,
        semantics,
        group_source,
        group_manifest,
        core_source=core_source,
        core_manifest=core_manifest,
    )
    assert coverage["status"] == "PASS" and coverage["uncovered"] == []
    traceability = group_traceability_test(
        plan,
        {unit_id: bundle},
        {unit_id: semantics},
        group_source,
        group_manifest,
        html_database,
        core_source=core_source,
        core_manifest=core_manifest,
    )
    assert traceability["status"] == "PASS", traceability["brokenMappings"]
    assert {item["declaration"] for item in traceability["validMappings"]} == {
        "Spec2Lean.Synthetic.Shared.operation",
        "Spec2Lean.Synthetic.Unit.operation",
        "Spec2Lean.Synthetic.Unit.execute",
    }
    delegated = next(
        item for item in traceability["validMappings"]
        if item["declaration"] == "Spec2Lean.Synthetic.Unit.operation"
    )
    assert delegated["claimRefs"] == [{
        "unitId": unit_id,
        "claimId": "claim:operation",
        "evidenceIds": ["evidence:source"],
    }]
    shared = next(
        item for item in traceability["validMappings"]
        if item["declaration"] == "Spec2Lean.Synthetic.Shared.operation"
    )
    assert shared["claimRefs"] == [{
        "unitId": unit_id,
        "claimId": "claim:operation",
        "evidenceIds": ["evidence:source"],
    }]

    precise_semantics = copy.deepcopy(semantics)
    precise_semantics["semantics"]["dependencies"][0]["semanticClaimIds"] = [
        "claim:operation", "claim:execution",
    ]
    precise_group = copy.deepcopy(group_manifest)
    precise_group["semanticsArtifacts"][0]["artifactHash"] = semantics_artifact_hash(
        precise_semantics
    )
    precise_group["sharedUses"][0]["leanDeclarations"] = [
        "Spec2Lean.Synthetic.Shared.operation",
        "Spec2Lean.Synthetic.Shared.executionRelation",
    ]
    precise_group["sharedUses"][0]["claimRefs"] = [
        {"unitId": unit_id, "claimId": "claim:operation"},
        {"unitId": unit_id, "claimId": "claim:execution"},
    ]
    precise_core = copy.deepcopy(core_manifest)
    precise_core["concepts"][0]["leanDeclarations"].append(
        "Spec2Lean.Synthetic.Shared.executionRelation"
    )
    precise_core["concepts"][0]["claimRefs"].append(
        {"unitId": unit_id, "claimId": "claim:execution"}
    )
    precise_core["declarations"].append({
        "declaration": "Spec2Lean.Synthetic.Shared.executionRelation",
        "role": "EXECUTION",
        "dependencyIds": ["shared:operation"],
        "claimRefs": [{"unitId": unit_id, "claimId": "claim:execution"}],
    })
    precise_source = core_source.replace(
        "end Spec2Lean.Synthetic.Shared",
        "def executionRelation (result : Nat) : Prop := result > 0\n\n"
        "end Spec2Lean.Synthetic.Shared",
    )
    precise_trace = group_traceability_test(
        plan,
        {unit_id: bundle},
        {unit_id: precise_semantics},
        group_source,
        precise_group,
        html_database,
        core_source=precise_source,
        core_manifest=precise_core,
    )
    assert precise_trace["status"] == "PASS", precise_trace["brokenMappings"]
    precise_refs = {
        item["declaration"]: {
            (ref["unitId"], ref["claimId"]) for ref in item["claimRefs"]
        }
        for item in precise_trace["validMappings"]
        if item["declaration"].startswith("Spec2Lean.Synthetic.Shared.")
    }
    assert precise_refs == {
        "Spec2Lean.Synthetic.Shared.operation": {(unit_id, "claim:operation")},
        "Spec2Lean.Synthetic.Shared.executionRelation": {(unit_id, "claim:execution")},
    }

    broken_manifest = copy.deepcopy(core_manifest)
    broken_manifest["concepts"][0]["claimRefs"] = []
    broken = group_traceability_test(
        plan,
        {unit_id: bundle},
        {unit_id: semantics},
        group_source,
        group_manifest,
        html_database,
        core_source=core_source,
        core_manifest=broken_manifest,
    )
    assert "SHARED_CONCEPT_CLAIM_MISMATCH" in {
        item["code"] for item in broken["brokenMappings"]
    }

    extra_core = copy.deepcopy(core_manifest)
    extra_core["concepts"][0]["leanDeclarations"].append(
        "Spec2Lean.Synthetic.Shared.unused"
    )
    extra_core["declarations"].append({
        "declaration": "Spec2Lean.Synthetic.Shared.unused",
        "role": "SEMANTIC_HELPER",
        "dependencyIds": ["shared:operation"],
        "claimRefs": [{"unitId": unit_id, "claimId": "claim:operation"}],
    })
    extra_source = core_source.replace(
        "end Spec2Lean.Synthetic.Shared",
        "def unused : Nat := 0\n\nend Spec2Lean.Synthetic.Shared",
    )
    subset = group_traceability_test(
        plan,
        {unit_id: bundle},
        {unit_id: semantics},
        group_source,
        group_manifest,
        html_database,
        core_source=extra_source,
        core_manifest=extra_core,
    )
    assert subset["status"] == "PASS", subset["brokenMappings"]
    assert "Spec2Lean.Synthetic.Shared.unused" not in {
        item["declaration"] for item in subset["validMappings"]
    }

    # A reused frozen representation may be globally traceable through an
    # earlier unit without owning a claim in the current group.  It must not be
    # misreported as an unmapped current declaration; current claim coverage
    # remains independently mandatory.
    reused_group = copy.deepcopy(group_manifest)
    reused_group["sharedUses"][0]["leanDeclarations"].append(
        "Spec2Lean.Synthetic.Shared.historicalRepresentation"
    )
    reused_core = copy.deepcopy(core_manifest)
    reused_core["concepts"][0]["leanDeclarations"].append(
        "Spec2Lean.Synthetic.Shared.historicalRepresentation"
    )
    reused_core["concepts"][0]["claimRefs"].append({
        "unitId": "unit:historical", "claimId": "claim:historical",
    })
    reused_core["declarations"].append({
        "declaration": "Spec2Lean.Synthetic.Shared.historicalRepresentation",
        "role": "PRIMARY_TYPE",
        "dependencyIds": ["shared:operation"],
        "claimRefs": [{
            "unitId": "unit:historical", "claimId": "claim:historical",
        }],
    })
    reused_source = core_source.replace(
        "end Spec2Lean.Synthetic.Shared",
        "abbrev historicalRepresentation := Nat\n\n"
        "end Spec2Lean.Synthetic.Shared",
    )
    reused_trace = group_traceability_test(
        plan,
        {unit_id: bundle},
        {unit_id: semantics},
        group_source,
        reused_group,
        html_database,
        core_source=reused_source,
        core_manifest=reused_core,
    )
    assert reused_trace["status"] == "PASS", reused_trace["brokenMappings"]
    assert "Spec2Lean.Synthetic.Shared.historicalRepresentation" not in {
        item["declaration"] for item in reused_trace["validMappings"]
    }


def test_group_run_loads_frozen_core_builds_with_it_and_hashes_it(
    tmp_path, html_database, monkeypatch
):
    plan, bundle, semantics, _ = _inputs(html_database)
    unit = plan["requestedUnits"][0]
    unit_id = unit["unitId"]
    dependency_id = "shared:operation"
    plan["sharedPrerequisites"] = [{
        "dependencyId": dependency_id,
        "name": "Common operation domain",
        "kind": "semantic-domain",
        "reason": "The operation is shared by translated units.",
        "sourceNodeIds": unit["sourceNodeIds"],
        "requiredBy": [unit_id],
    }]
    semantics["semantics"]["dependencies"] = [{
        "dependencyId": dependency_id,
        "concept": "Common operation domain",
        "description": "The operation is provided by the shared core.",
        "semanticClaimIds": ["claim:operation"],
        "evidenceIds": ["evidence:source"],
    }]

    core_module = "Spec2Lean.Synthetic.Shared.Core"
    core_run_id = "shared-core-run:" + "1" * 24
    core_source_hash = "sha256:" + "a" * 64
    core_manifest_hash = "sha256:" + "b" * 64
    core_source = """namespace Spec2Lean.Synthetic.Shared

def operation (a b : Nat) : Nat := a + b

end Spec2Lean.Synthetic.Shared
"""
    core_manifest = {
        "concepts": [{
            "dependencyId": dependency_id,
            "name": "Common operation domain",
            "kind": "semantic-domain",
            "sourceNodeIds": unit["sourceNodeIds"],
            "requiredBy": [unit_id],
            "semanticInputHash": "sha256:" + "c" * 64,
            "leanDeclarations": ["Spec2Lean.Synthetic.Shared.operation"],
            "claimRefs": [{"unitId": unit_id, "claimId": "claim:operation"}],
        }],
        "declarations": [{
            "declaration": "Spec2Lean.Synthetic.Shared.operation",
            "role": "OPERATION",
            "dependencyIds": [dependency_id],
            "claimRefs": [{"unitId": unit_id, "claimId": "claim:operation"}],
        }],
    }
    group_source = f"""import {core_module}

namespace Spec2Lean.Synthetic.Unit

def execute (a b : Nat) : Nat := Spec2Lean.Synthetic.Shared.operation a b

end Spec2Lean.Synthetic.Unit
"""
    group_manifest = {
        "schemaVersion": 3,
        "phase": "LLM_GROUP_TRANSLATOR",
        "planRunId": plan["planRunId"],
        "language": plan["language"],
        "version": plan["version"],
        "group": {"name": "InstructionSemantics", "unitIds": [unit_id]},
        "translationRunId": "translation-group-run:check-core",
        "semanticsArtifacts": [{
            "unitId": unit_id,
            "runId": semantics["runId"],
            "artifactHash": semantics_artifact_hash(semantics),
        }],
        "translator": {
            "provider": "opencode",
            "model": "openai/gpt-5.6-sol",
            "reasoning": "medium",
        },
        "target": {"language": "Lean", "version": "4"},
        "leanFile": "InstructionSemantics.lean",
        "createdAt": "2026-08-29T00:00:00Z",
        "declarations": [{
            "declaration": "Spec2Lean.Synthetic.Unit.execute",
            "role": "EXECUTION",
            "claimRefs": [{"unitId": unit_id, "claimId": "claim:execution"}],
        }],
        "sharedCore": {
            "coreRunId": core_run_id,
            "manifestHash": core_manifest_hash,
            "sourceHash": core_source_hash,
            "leanModule": core_module,
        },
        "sharedUses": [{
            "dependencyId": dependency_id,
            "leanDeclarations": ["Spec2Lean.Synthetic.Shared.operation"],
            "claimRefs": [{"unitId": unit_id, "claimId": "claim:operation"}],
        }],
    }

    evidence_root = tmp_path / "evidence"
    semantics_root = tmp_path / "semantics"
    translations_root = tmp_path / "translations"
    checks_root = tmp_path / "checks"
    relative = Path(plan["language"]) / plan["version"] / plan["planRunId"]
    unit_slug = unit_directory_name(unit)
    evidence_directory = evidence_root / relative / unit_slug
    semantics_directory = semantics_root / relative / unit_slug
    translation_directory = translations_root / relative / "InstructionSemantics"
    for directory in (evidence_directory, semantics_directory, translation_directory):
        directory.mkdir(parents=True)
    (evidence_directory / "evidence.json").write_text(
        json.dumps(bundle), encoding="utf-8"
    )
    (semantics_directory / "semantics.json").write_text(
        json.dumps(semantics), encoding="utf-8"
    )
    (translation_directory / "translation-manifest.json").write_text(
        json.dumps(group_manifest), encoding="utf-8"
    )
    (translation_directory / "translator-run.json").write_text("{}", encoding="utf-8")
    (translation_directory / "InstructionSemantics.lean").write_text(
        group_source, encoding="utf-8"
    )
    frozen_source = tmp_path / "frozen" / "Core.lean"
    frozen_source.parent.mkdir()
    frozen_source.write_text(core_source, encoding="utf-8")
    frozen = SimpleNamespace(
        source=core_source,
        manifest=core_manifest,
        source_path=frozen_source,
        core_run_id=core_run_id,
        lean_module=core_module,
        source_hash=core_source_hash,
        manifest_hash=core_manifest_hash,
    )
    loaded: list[tuple[Path, str]] = []

    def load_core(root, loaded_plan, loaded_core_run_id):
        assert loaded_plan is plan
        loaded.append((root, loaded_core_run_id))
        return frozen

    monkeypatch.setattr("spec2lean.translation.shared_core.load_core", load_core)
    builds: list[tuple[Path, list[tuple[str, Path]] | None]] = []

    def build_runner(path, *, dependency_modules=None):
        builds.append((path, dependency_modules))
        return _passing_build(path)

    results = run_group_checks(
        plan,
        evidence_root=evidence_root,
        semantics_root=semantics_root,
        translations_root=translations_root,
        checks_root=checks_root,
        database=html_database,
        group="InstructionSemantics",
        build_runner=build_runner,
    )
    _, result = results[unit_id]
    assert result["status"] == "PASS", result["traceability"]["brokenMappings"]
    assert loaded == [(translations_root, core_run_id)]
    assert builds == [(
        translation_directory / "InstructionSemantics.lean",
        [(core_module, frozen_source)],
    )]
    assert result["inputHashes"]["sharedCoreSource"] == core_source_hash
    assert result["inputHashes"]["sharedCoreManifest"] == core_manifest_hash


def test_run_preserves_simultaneous_failures_and_writes_deterministic_artifacts(tmp_path, html_database):
    plan, evidence_root, semantics_root, translations_root, checks_root, _ = _write_artifacts(
        tmp_path, html_database
    )
    slug = unit_directory_name(plan["requestedUnits"][0])
    semantic_path = semantics_root / "synthetic" / "1.0" / plan["planRunId"] / slug / "semantics.json"
    semantics = json.loads(semantic_path.read_text())
    semantics["semantics"]["claims"].append({
        "claimId": "claim:uncovered", "kind": "SOURCE_FACT",
        "statement": "This claim is not translated.", "evidenceIds": ["evidence:missing"],
    })
    semantic_path.write_text(json.dumps(semantics), encoding="utf-8")

    output, result = run_checks(
        plan, evidence_root=evidence_root, semantics_root=semantics_root,
        translations_root=translations_root, checks_root=checks_root,
        database=html_database, unit_id=UNIT["unitId"], build_runner=_failing_build,
    )
    assert result["status"] == "FAIL"
    assert set(result["inputHashes"]) == {"semantics", "leanSource", "translationManifest"}
    assert all(value.startswith("sha256:") for value in result["inputHashes"].values())
    assert result["build"]["status"] == result["coverage"]["status"] == result["traceability"]["status"] == "FAIL"
    assert result["routing"]["next"] == [
        "SEMANTIC_EXTRACTOR", "TRANSLATOR", "TROUBLESHOOTER"
    ]
    first_json = (output / "check.json").read_text()
    first_markdown = (output / "check.md").read_text()
    _, repeated = run_checks(
        plan, evidence_root=evidence_root, semantics_root=semantics_root,
        translations_root=translations_root, checks_root=checks_root,
        database=html_database, unit_id=UNIT["unitId"], build_runner=_failing_build,
    )
    assert repeated == result
    assert (output / "check.json").read_text() == first_json
    assert (output / "check.md").read_text() == first_markdown == render_markdown(result)


def test_all_three_pass_route_complete_and_inspection_cli(tmp_path, html_database, capsys):
    plan, evidence_root, semantics_root, translations_root, checks_root, plans_root = _write_artifacts(
        tmp_path, html_database
    )
    _, result = run_checks(
        plan, evidence_root=evidence_root, semantics_root=semantics_root,
        translations_root=translations_root, checks_root=checks_root,
        database=html_database, unit_id=UNIT["unitId"], build_runner=_passing_build,
    )
    assert result["status"] == "PASS"
    assert result["routing"]["next"] == ["COMPLETE"]
    for command, field in (("show", None), ("coverage", "status"), ("traceability", "status")):
        assert main([
            "check", command, "--plan-run", plan["planRunId"], "--unit", UNIT["unitId"],
            "--plans-root", str(plans_root), "--checks-root", str(checks_root),
        ]) == 0
        shown = json.loads(capsys.readouterr().out)
        if field is None:
            assert shown["status"] == "PASS" and shown["phase"] == "CHECK"
        else:
            assert shown[field] == "PASS"
