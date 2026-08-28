from __future__ import annotations

import copy
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from spec2lean.checking.build import run_build_test
from spec2lean.checking.logical import coverage_test, traceability_test
from spec2lean.checking.models import check_result, routing_for
from spec2lean.checking.render import render_markdown
from spec2lean.checking.runner import run_checks
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
        "schemaVersion": 2,
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
