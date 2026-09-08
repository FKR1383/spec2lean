from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from spec2lean.checking.models import check_result
from spec2lean.database import connect
from spec2lean.evidence.runner import unit_directory_name
from spec2lean.pipeline.runner import PipelineOptions, PipelineServices, run_pipeline
from spec2lean.planning.models import PlanningRequest
from spec2lean.planning.runner import source_database_digest
from spec2lean.planning.validation import derive_execution_schedule, derive_processing_order
from spec2lean.translation.groups import grouped_units
from spec2lean.semantics.models import evidence_bundle_hash
from spec2lean.translation.models import TranslationGroupScope
from spec2lean.util import canonical_json


GROUP = "InstructionSemantics"


def test_cyclic_pipeline_keeps_per_unit_stages_and_translates_joint_groups_once(
    planner_database, tmp_path,
):
    options = _options(tmp_path, planner_database)
    calls = []
    services = _services(options, planner_database, calls)
    original_builder = services.plan_builder

    def plan_builder(*args, **kwargs):
        directory = original_builder(*args, **kwargs)
        plan = json.loads((directory / "plan.json").read_text())
        base = plan["requestedUnits"][0]
        plan["requestedUnits"] = [{**base, "unitId": name, "name": name} for name in ("a", "b", "c")]
        planned = [{**plan["translationGroups"][0], "name": name, "unitIds": [unit]}
                   for name, unit in (("Syntax", "a"), ("Framing", "b"), ("Downstream", "c"))]
        edges = [{"from": a, "to": b} for a, b in (("a", "b"), ("b", "a"), ("b", "c"))]
        groups, schedule = derive_execution_schedule(["a", "b", "c"], edges, planned)
        layers, cycles, blocked = derive_processing_order(["a", "b", "c"], edges)
        plan.update(dependencies=edges, externalPrerequisites=[], plannedTranslationGroups=planned,
                    translationGroups=groups, executionSchedule=schedule, processingLayers=layers,
                    cycles=cycles, blockedUnitIds=blocked, graphStatus="CYCLIC")
        _json(directory / "plan.json", plan)
        return directory

    def evidence_builder(*args, unit_ids, **kwargs):
        calls.append(("evidence", tuple(unit_ids)))

    def semantics_builder(*args, unit_ids, **kwargs):
        calls.append(("semantics", tuple(unit_ids)))

    def translation_builder(plan, *args, group, **kwargs):
        members = tuple(unit["unitId"] for unit in grouped_units(plan)[group])
        calls.append(("translate", members))

    def checker(plan, *, group, **kwargs):
        members = tuple(unit["unitId"] for unit in grouped_units(plan)[group])
        calls.append(("check", members))
        return {unit: (tmp_path, {"phase": "CHECK", "status": "PASS", "build": {"status": "PASS"},
                                 "coverage": {"status": "PASS"}, "traceability": {"status": "PASS"}})
                for unit in members}

    services = PipelineServices(plan_builder, evidence_builder, semantics_builder,
                                translation_builder, checker, services.resolver)
    _, manifest = run_pipeline(PlanningRequest.exact("synthetic", "1.0", ["alpha.u32"]),
                               options, services=services)
    assert manifest["status"] == "COMPLETE"
    assert calls == ["plan", ("evidence", ("a",)), ("evidence", ("b",)), ("evidence", ("c",)),
                     ("semantics", ("a",)), ("semantics", ("b",)), ("semantics", ("c",)),
                     ("translate", ("a", "b")), ("translate", ("c",)),
                     ("check", ("a", "b")), ("check", ("c",))]
    assert set(manifest["units"]) == {"a", "b", "c"}
    assert all(unit["status"] == "PASS" and unit["stages"]["troubleshoot"] == "NOT_REQUIRED"
               for unit in manifest["units"].values())


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
        "schemaVersion": 2,
        "planRunId": "plan:pipeline",
        "language": "synthetic",
        "version": "1.0",
        "sourceDatabaseDigest": digest,
        "requestedUnits": [unit],
        "translationGroups": [{
            "name": GROUP,
            "unitIds": [unit["unitId"]],
            "reason": "Derived from the indexed synthetic instruction section.",
            "supportingNodeIds": [row["node_id"]],
            "origin": "INFERRED",
        }],
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
        scope = TranslationGroupScope.from_inputs(
            current_plan, GROUP, {unit["unitId"]: semantics}, created_at="now"
        )
        manifest = scope.manifest([])
        directory = root / "synthetic" / "1.0" / current_plan["planRunId"] / GROUP
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"{GROUP}.lean").write_text("def pipeline : Nat := 1\n", encoding="utf-8")
        _json(directory / "translation-manifest.json", manifest)
        _json(directory / "translator-run.json", {"outcome": "SUCCESS"})
        return directory

    def checker(current_plan, *, semantics_root, translations_root, checks_root, **_kwargs):
        calls.append("check")
        semantics = json.loads((semantics_root / "synthetic" / "1.0" / current_plan["planRunId"] / slug / "semantics.json").read_text())
        translation_dir = translations_root / "synthetic" / "1.0" / current_plan["planRunId"] / GROUP
        source = (translation_dir / f"{GROUP}.lean").read_text()
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
    monkeypatch.setattr("spec2lean.pipeline.runner.validate_bundle", lambda *_args: [])
    monkeypatch.setattr("spec2lean.pipeline.runner.validate_artifact", lambda *_args: [])
    monkeypatch.setattr("spec2lean.pipeline.runner.validate_published", lambda *_args: [])
    request = PlanningRequest.exact("synthetic", "1.0", ["alpha.u32"])
    progress: list[str] = []

    directory, manifest = run_pipeline(
        request, options, services=services, progress=progress.append
    )

    assert directory is not None and manifest["status"] == "COMPLETE"
    assert manifest["maxQuestionRounds"] == 2
    assert calls == ["plan", "evidence", "semantics", "translate", "check"]
    unit = next(iter(manifest["units"].values()))
    assert unit["status"] == "PASS"
    assert unit["stages"]["evidence"] == "BUILT"
    assert unit["stages"]["semantics"] == "BUILT"
    assert unit["stages"]["translate"] == "BUILT"
    assert unit["stages"]["check"]["disposition"] == "RAN"
    assert unit["stages"]["troubleshoot"] == "NOT_REQUIRED"
    assert any("phase 1/7 index: validating freshness" in item for item in progress)
    assert any(f"group {GROUP} (1 instruction(s)) phase 5/7 translate" in item for item in progress)
    assert set(manifest["timing"]["phases"]) == {
        "index", "plan", "evidence", "semantics", "translate", "check", "troubleshoot"
    }
    assert manifest["timing"]["elapsedSeconds"] >= 0
    assert manifest["timing"]["attempts"][0]["status"] == "COMPLETE"
    assert all(
        phase["elapsedSeconds"] >= 0
        for phase in manifest["timing"]["attempts"][0]["phases"].values()
    )
    assert any("total active pipeline time:" in item for item in progress)
    assert progress[-1].endswith("finished with status COMPLETE")

    calls.clear()
    resumed_options = _options(
        tmp_path, planner_database, resume=manifest["pipelineRunId"], from_phase="index"
    )
    _, resumed = run_pipeline(request, resumed_options, services=services)
    assert resumed["status"] == "COMPLETE"
    assert calls == []
    assert resumed["plan"]["disposition"] == "REUSED"
    assert {resumed["units"][key]["stages"]["evidence"] for key in resumed["units"]} == {"REUSED"}
    assert len(resumed["timing"]["attempts"]) == 2
    assert all(item["status"] == "COMPLETE" for item in resumed["timing"]["attempts"])


def test_resume_rebuilds_evidence_rejected_by_current_validation(
    planner_database, tmp_path, monkeypatch
):
    options = _options(tmp_path, planner_database, until_phase="evidence")
    calls: list[str] = []
    services = _services(
        options,
        options.index_root / "synthetic" / "1.0" / "specification.sqlite",
        calls,
    )
    monkeypatch.setattr("spec2lean.pipeline.runner.validate_bundle", lambda *_args: [])
    request = PlanningRequest.exact("synthetic", "1.0", ["alpha.u32"])
    _, first = run_pipeline(request, options, services=services)
    assert calls == ["plan", "evidence"]

    calls.clear()
    monkeypatch.setattr(
        "spec2lean.pipeline.runner.validate_bundle",
        lambda *_args: [{
            "code": "MISSING_SOURCE_RENDITION",
            "message": "dual-source evidence is stale",
            "path": "$.evidence",
        }],
    )
    resumed_options = _options(
        tmp_path,
        planner_database,
        resume=first["pipelineRunId"],
        from_phase="evidence",
        until_phase="evidence",
    )
    _, resumed = run_pipeline(request, resumed_options, services=services)
    assert calls == ["evidence"]
    assert {
        resumed["units"][key]["stages"]["evidence"] for key in resumed["units"]
    } == {"BUILT"}


def test_resume_rejects_legacy_grouping_plan_after_plan_phase(
    planner_database, tmp_path, monkeypatch
):
    options = _options(tmp_path, planner_database)
    calls: list[str] = []
    services = _services(
        options,
        options.index_root / "synthetic" / "1.0" / "specification.sqlite",
        calls,
    )
    monkeypatch.setattr("spec2lean.pipeline.runner.validate_artifact", lambda *_args: [])
    monkeypatch.setattr("spec2lean.pipeline.runner.validate_published", lambda *_args: [])
    request = PlanningRequest.exact("synthetic", "1.0", ["alpha.u32"])
    _, manifest = run_pipeline(request, options, services=services)
    plan_path = options.plans_root / "synthetic" / "1.0" / manifest["planRunId"] / "plan.json"
    legacy = json.loads(plan_path.read_text())
    legacy["schemaVersion"] = 1
    legacy.pop("translationGroups")
    _json(plan_path, legacy)

    calls.clear()
    resumed_options = _options(
        tmp_path,
        planner_database,
        resume=manifest["pipelineRunId"],
        from_phase="semantics",
    )
    with pytest.raises(RuntimeError, match="rerun with --from plan"):
        run_pipeline(request, resumed_options, services=services)
    assert calls == []


@pytest.mark.parametrize("from_phase", ["plan", "semantics"])
def test_resume_legacy_cycle_requires_and_runs_planning(planner_database, tmp_path, from_phase):
    options = _options(tmp_path, planner_database, until_phase="plan")
    calls = []
    services = _services(options, planner_database, calls)
    request = PlanningRequest.exact("synthetic", "1.0", ["alpha.u32"])
    _, manifest = run_pipeline(request, options, services=services)
    path = options.plans_root / "synthetic" / "1.0" / manifest["planRunId"] / "plan.json"
    legacy = json.loads(path.read_text())
    legacy.update(graphStatus="CYCLIC", processingLayers=[])
    _json(path, legacy)
    calls.clear()
    resumed = _options(tmp_path, planner_database, resume=manifest["pipelineRunId"],
                       from_phase=from_phase, until_phase="semantics" if from_phase == "semantics" else "plan")
    if from_phase == "semantics":
        with pytest.raises(RuntimeError, match="rerun with --from plan"):
            run_pipeline(request, resumed, services=services)
        assert calls == []
    else:
        _, result = run_pipeline(request, resumed, services=services)
        assert result["status"] == "COMPLETE"
        assert calls == ["plan"]


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


def test_dry_run_never_reuses_checks_when_group_translation_would_change(
    planner_database, tmp_path, monkeypatch
):
    options = _options(tmp_path, planner_database)
    calls: list[str] = []
    database = options.index_root / "synthetic" / "1.0" / "specification.sqlite"
    services = _services(options, database, calls)
    monkeypatch.setattr("spec2lean.pipeline.runner.validate_bundle", lambda *_args: [])
    monkeypatch.setattr("spec2lean.pipeline.runner.validate_artifact", lambda *_args: [])
    monkeypatch.setattr("spec2lean.pipeline.runner.validate_published", lambda *_args: [])
    request = PlanningRequest.exact("synthetic", "1.0", ["alpha.u32"])
    _, first = run_pipeline(request, options, services=services)

    monkeypatch.setattr("spec2lean.pipeline.runner._translation_reusable", lambda *_args: False)
    dry_options = _options(
        tmp_path,
        planner_database,
        resume=first["pipelineRunId"],
        from_phase="translate",
        until_phase="check",
        dry_run=True,
    )
    _, dry = run_pipeline(request, dry_options, services=services)
    state = next(iter(dry["units"].values()))
    assert state["stages"]["translate"] == "WOULD_BUILD"
    assert state["stages"]["check"] == {"disposition": "WOULD_RUN", "status": None}
    assert state["status"] == "PLANNED"


def test_keyboard_interrupt_is_persisted_with_resume_progress(planner_database, tmp_path, monkeypatch):
    options = _options(tmp_path, planner_database)
    calls: list[str] = []
    database = options.index_root / "synthetic" / "1.0" / "specification.sqlite"
    base = _services(options, database, calls)
    monkeypatch.setattr("spec2lean.pipeline.runner.validate_artifact", lambda *_args: [])

    def interrupt_translation(*_args, **_kwargs):
        raise KeyboardInterrupt

    services = PipelineServices(
        base.plan_builder,
        base.evidence_builder,
        base.semantics_builder,
        interrupt_translation,
        base.checker,
        base.resolver,
    )
    progress: list[str] = []
    with pytest.raises(KeyboardInterrupt):
        run_pipeline(
            PlanningRequest.exact("synthetic", "1.0", ["alpha.u32"]),
            options,
            services=services,
            progress=progress.append,
        )
    manifests = list(options.runs_root.glob("synthetic/1.0/*/run.json"))
    assert len(manifests) == 1
    manifest = json.loads(manifests[0].read_text())
    assert manifest["status"] == "INTERRUPTED"
    assert manifest["error"] == "interrupted by user"
    assert manifest["timing"]["attempts"][0]["status"] == "INTERRUPTED"
    assert manifest["timing"]["attempts"][0]["phases"]["translate"]["status"] == "INTERRUPTED"
    assert progress[-1].endswith(f"resume with --resume {manifest['pipelineRunId']}")


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
