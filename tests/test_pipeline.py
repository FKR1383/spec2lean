from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from spec2lean.checking.models import check_result
from spec2lean.database import connect
from spec2lean.evidence.runner import unit_directory_name
from spec2lean.pipeline.runner import PipelineOptions, PipelineServices, run_pipeline
from spec2lean.planning.models import PlanningRequest
from spec2lean.planning.runner import source_database_digest
from spec2lean.semantics.models import evidence_bundle_hash
from spec2lean.translation.models import semantics_artifact_hash
from spec2lean.util import canonical_json


def _json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _options(tmp_path: Path, database: Path, **overrides) -> PipelineOptions:
    index = tmp_path / "indexes" / "synthetic" / "1.0" / "specification.sqlite"
    index.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(database, index)
    values = {
        "repository_root": tmp_path,
        "index_root": tmp_path / "indexes",
        "plans_root": tmp_path / "plans",
        "evidence_root": tmp_path / "evidence",
        "semantics_root": tmp_path / "semantics",
        "translations_root": tmp_path / "translations",
        "checks_root": tmp_path / "checks",
        "troubleshooting_root": tmp_path / "troubleshooting",
        "runs_root": tmp_path / "runs",
    }
    values.update(overrides)
    return PipelineOptions(**values)


def _services(options: PipelineOptions, database: Path, calls: list[str], *, fail_check=False):
    with connect(database, read_only=True) as connection:
        digest = source_database_digest(connection)
        row = connection.execute(
            "SELECT n.node_id, d.document_id, d.sha256, d.local_path "
            "FROM nodes n JOIN documents d USING(document_id) "
            "WHERE n.parent_id IS NOT NULL ORDER BY n.node_id LIMIT 1"
        ).fetchone()
    unit = {"unitId": "unit:pipeline", "name": "alpha.u32", "sourceNodeIds": [row["node_id"]]}
    plan = {
        "schemaVersion": 1,
        "planRunId": "plan:pipeline",
        "language": "synthetic",
        "version": "1.0",
        "sourceDatabaseDigest": digest,
        "requestedUnits": [unit],
        "graphStatus": "ACYCLIC",
        "processingLayers": [{"layer": 0, "unitIds": [unit["unitId"]]}],
    }
    slug = unit_directory_name(unit)

    def plan_builder(_database, plans_root, request, **_kwargs):
        calls.append("plan")
        directory = plans_root / "synthetic" / "1.0" / plan["planRunId"]
        _json(directory / "request.json", request.to_dict())
        _json(directory / "plan.json", plan)
        _json(directory / "planner-run.json", {"outcome": "VALID", "finishedAt": "now"})
        return directory

    def evidence_builder(_database, current_plan, root, **_kwargs):
        calls.append("evidence")
        evidence = {
            "evidenceId": "evidence:pipeline",
            "unitId": unit["unitId"],
            "documentId": row["document_id"],
            "documentSha256": row["sha256"],
            "sourceType": "html",
            "sourceNodeId": row["node_id"],
            "sourceNodeIds": [row["node_id"]],
            "sourceSpanIds": [],
        }
        bundle = {
            "schemaVersion": 1,
            "phase": "RETRIEVE_EVIDENCE",
            "planRunId": current_plan["planRunId"],
            "language": "synthetic",
            "version": "1.0",
            "sourceDatabaseDigest": digest,
            "unit": unit,
            "evidence": [evidence],
        }
        directory = root / "synthetic" / "1.0" / current_plan["planRunId"] / slug
        _json(directory / "evidence.json", bundle)
        _json(directory / "retriever-run.json", {"outcome": "VALID", "unitId": unit["unitId"]})
        return directory.parent

    def semantics_builder(current_plan, evidence_root, root, **_kwargs):
        calls.append("semantics")
        bundle = json.loads((evidence_root / "synthetic" / "1.0" / current_plan["planRunId"] / slug / "evidence.json").read_text())
        artifact = {
            "schemaVersion": 1,
            "phase": "SEMANTIC_EXTRACTOR",
            "planRunId": current_plan["planRunId"],
            "language": "synthetic",
            "version": "1.0",
            "unit": unit,
            "evidenceBundleHash": evidence_bundle_hash(bundle),
            "runId": "semantic-run:pipeline",
            "outcome": "SUCCESS",
            "semantics": {"claims": [{"claimId": "claim:pipeline"}]},
        }
        directory = root / "synthetic" / "1.0" / current_plan["planRunId"] / slug
        _json(directory / "semantics.json", artifact)
        return directory.parent

    def translation_builder(current_plan, semantics_root, root, **_kwargs):
        calls.append("translate")
        semantics = json.loads((semantics_root / "synthetic" / "1.0" / current_plan["planRunId"] / slug / "semantics.json").read_text())
        manifest = {
            "phase": "LLM_TRANSLATOR",
            "planRunId": current_plan["planRunId"],
            "language": "synthetic",
            "version": "1.0",
            "unit": unit,
            "translationRunId": "translation-run:pipeline",
            "semanticsArtifactHash": semantics_artifact_hash(semantics),
            "leanFile": "Unit.lean",
            "declarations": [],
        }
        directory = root / "synthetic" / "1.0" / current_plan["planRunId"] / slug
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "Unit.lean").write_text("def pipeline : Nat := 1\n", encoding="utf-8")
        _json(directory / "translation-manifest.json", manifest)
        _json(directory / "translator-run.json", {"outcome": "SUCCESS"})
        return directory

    def checker(current_plan, *, semantics_root, translations_root, checks_root, **_kwargs):
        calls.append("check")
        semantics = json.loads((semantics_root / "synthetic" / "1.0" / current_plan["planRunId"] / slug / "semantics.json").read_text())
        translation_dir = translations_root / "synthetic" / "1.0" / current_plan["planRunId"] / slug
        source = (translation_dir / "Unit.lean").read_text()
        translation_manifest = json.loads((translation_dir / "translation-manifest.json").read_text())
        passing = {"status": "PASS", "diagnostics": []}
        coverage = {"status": "FAIL" if fail_check else "PASS", "uncovered": ["claim:pipeline"] if fail_check else []}
        result = check_result(
            plan=current_plan,
            unit=unit,
            translation_run_id=translation_manifest["translationRunId"],
            build=passing,
            coverage=coverage,
            traceability={"status": "PASS", "brokenMappings": []},
            input_hashes={
                "semantics": "sha256:" + hashlib.sha256(canonical_json(semantics).encode()).hexdigest(),
                "leanSource": "sha256:" + hashlib.sha256(source.encode()).hexdigest(),
                "translationManifest": "sha256:" + hashlib.sha256(canonical_json(translation_manifest).encode()).hexdigest(),
            },
        )
        directory = checks_root / "synthetic" / "1.0" / current_plan["planRunId"] / slug
        _json(directory / "check.json", result)
        return directory, result

    def resolver(current_plan, *, checks_root, troubleshooting_root, **_kwargs):
        calls.append("troubleshoot")
        directory = troubleshooting_root / "synthetic" / "1.0" / current_plan["planRunId"] / slug
        resolution = {"outcome": "COMPLETE", "dispatches": 1, "stopReason": "ALL_CHECKS_PASS"}
        _json(directory / "resolution.json", resolution)
        return directory, resolution

    return PipelineServices(plan_builder, evidence_builder, semantics_builder, translation_builder, checker, resolver)


def test_pipeline_composes_all_phases_and_resume_reuses_fresh_artifacts(
    planner_database, tmp_path, monkeypatch
):
    options = _options(tmp_path, planner_database)
    calls: list[str] = []
    services = _services(options, options.index_root / "synthetic" / "1.0" / "specification.sqlite", calls)
    monkeypatch.setattr("spec2lean.pipeline.runner.validate_artifact", lambda *_args: [])
    monkeypatch.setattr("spec2lean.pipeline.runner.validate_published", lambda *_args: [])
    request = PlanningRequest.exact("synthetic", "1.0", ["alpha.u32"])

    directory, manifest = run_pipeline(request, options, services=services)

    assert directory is not None and manifest["status"] == "COMPLETE"
    assert calls == ["plan", "evidence", "semantics", "translate", "check"]
    unit = next(iter(manifest["units"].values()))
    assert unit["status"] == "PASS"
    assert unit["stages"]["troubleshoot"] == "NOT_REQUIRED"

    calls.clear()
    resumed_options = _options(
        tmp_path, planner_database, resume=manifest["pipelineRunId"], from_phase="index"
    )
    _, resumed = run_pipeline(request, resumed_options, services=services)
    assert resumed["status"] == "COMPLETE"
    assert calls == []
    assert resumed["plan"]["disposition"] == "REUSED"
    assert {resumed["units"][key]["stages"]["evidence"] for key in resumed["units"]} == {"REUSED"}


def test_pipeline_routes_a_failed_check_through_phase_7(planner_database, tmp_path, monkeypatch):
    options = _options(tmp_path, planner_database)
    calls: list[str] = []
    database = options.index_root / "synthetic" / "1.0" / "specification.sqlite"
    services = _services(options, database, calls, fail_check=True)
    monkeypatch.setattr("spec2lean.pipeline.runner.validate_artifact", lambda *_args: [])
    monkeypatch.setattr("spec2lean.pipeline.runner.validate_published", lambda *_args: [])

    _, manifest = run_pipeline(
        PlanningRequest.exact("synthetic", "1.0", ["alpha.u32"]), options, services=services
    )

    assert manifest["status"] == "COMPLETE"
    assert calls[-1] == "troubleshoot"
    stage = next(iter(manifest["units"].values()))["stages"]["troubleshoot"]
    assert stage["disposition"] == "ROUTED"
    assert stage["outcome"] == "COMPLETE"
    assert stage["dispatches"] == 1
    assert stage["stopReason"] == "ALL_CHECKS_PASS"


def test_dry_run_does_not_create_a_manifest_when_phase_1_is_missing(tmp_path):
    options = PipelineOptions(
        repository_root=tmp_path,
        index_root=tmp_path / "indexes",
        plans_root=tmp_path / "plans",
        evidence_root=tmp_path / "evidence",
        semantics_root=tmp_path / "semantics",
        translations_root=tmp_path / "translations",
        checks_root=tmp_path / "checks",
        troubleshooting_root=tmp_path / "troubleshooting",
        runs_root=tmp_path / "runs",
        dry_run=True,
    )
    directory, manifest = run_pipeline(
        PlanningRequest.exact("synthetic", "1.0", ["alpha.u32"]), options
    )
    assert directory is None
    assert manifest["status"] == "DRY_RUN"
    assert manifest["phase1"]["disposition"] == "WOULD_BUILD"
    assert not options.runs_root.exists()


def test_pipeline_builds_phase_1_from_a_hash_pinned_source_manifest(tmp_path):
    source = Path(__file__).parent / "fixtures" / "planner_specification.html"
    manifest_root = tmp_path / "documents" / "sources" / "vendor" / "synthetic" / "1.0"
    raw = manifest_root / "raw" / "specification.html"
    raw.parent.mkdir(parents=True)
    shutil.copy2(source, raw)
    _json(manifest_root / "source-manifest.json", {
        "artifacts": [{
            "kind": "html",
            "local_path": "raw/specification.html",
            "url": "https://example.test/specification.html",
            "sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
        }]
    })
    options = PipelineOptions(
        repository_root=tmp_path,
        index_root=tmp_path / "indexes",
        plans_root=tmp_path / "plans",
        evidence_root=tmp_path / "evidence",
        semantics_root=tmp_path / "semantics",
        translations_root=tmp_path / "translations",
        checks_root=tmp_path / "checks",
        troubleshooting_root=tmp_path / "troubleshooting",
        runs_root=tmp_path / "runs",
        until_phase="index",
    )

    directory, manifest = run_pipeline(
        PlanningRequest.exact("synthetic", "1.0", ["alpha.u32"]), options
    )

    assert directory is not None
    assert manifest["status"] == "COMPLETE"
    assert manifest["phase1"]["disposition"] == "BUILT"
    index_directory = options.index_root / "synthetic" / "1.0"
    assert (index_directory / "specification.sqlite").is_file()
    assert json.loads((index_directory / "index-manifest.json").read_text())["sources"][0]["sha256"]
