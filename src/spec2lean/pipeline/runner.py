from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

from ..checking.runner import run_group_checks
from ..embeddings import ensure as ensure_embeddings, index_mode, retrieval_selection
from ..checking.store import load_check
from ..constants import INDEX_SCHEMA_VERSION, PARSER_VERSION
from ..database import build_database, connect
from ..evidence.runner import build_evidence, unit_directory_name
from ..evidence.query import EvidenceQuery
from ..evidence.store import evidence_run_root, load_unit_bundle
from ..evidence.validation import validate_bundle
from ..parsers import parse_html, parse_pdf
from ..planning.models import PlanningRequest
from ..planning.runner import build_plan, source_database_digest
from ..planning.validation import PLAN_SCHEMA_VERSION, validate_execution_schedule
from ..semantics.models import SemanticScope
from ..semantics.runner import build_semantics
from ..semantics.store import load_semantics, unit_directory as semantics_unit_directory
from ..semantics.validation import validate_artifact
from ..translation.groups import grouped_units
from ..translation.models import TranslationGroupScope
from ..translation.runner import build_group_translation
from ..translation.store import (
    group_directory as translation_group_directory,
    legacy_unit_directory as legacy_translation_unit_directory,
    load_group_translation,
    load_translation,
)
from ..translation.validation import validate_published
from ..troubleshooting.models import NO_ACTION, action_for
from ..troubleshooting.resolver import resolve_check_failure
from ..util import canonical_json, sha256_file, stable_id
from ..validation import validate_database


PHASES = ("index", "plan", "evidence", "semantics", "translate", "check", "troubleshoot")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.3f}s"
    minutes, remainder = divmod(seconds, 60)
    if minutes < 60:
        return f"{int(minutes)}m {remainder:.3f}s"
    hours, minutes = divmod(int(minutes), 60)
    return f"{hours}h {minutes}m {remainder:.3f}s"


def _hash_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


@dataclass(frozen=True, slots=True)
class PipelineOptions:
    repository_root: Path
    index_root: Path
    plans_root: Path
    evidence_root: Path
    semantics_root: Path
    translations_root: Path
    checks_root: Path
    troubleshooting_root: Path
    runs_root: Path
    timeout_seconds: int = 1800
    max_dispatches: int = 8
    max_question_rounds: int = 2
    from_phase: str = "index"
    until_phase: str = "troubleshoot"
    dry_run: bool = False
    resume: str | None = None
    index_mode: str = "lexical"

    def __post_init__(self) -> None:
        if self.index_mode not in {"lexical", "semantic"}:
            raise ValueError("index_mode must be lexical or semantic")
        if self.from_phase not in PHASES or self.until_phase not in PHASES:
            raise ValueError(f"pipeline phases must be one of: {', '.join(PHASES)}")
        if PHASES.index(self.from_phase) > PHASES.index(self.until_phase):
            raise ValueError("--from cannot come after --until")
        if self.timeout_seconds < 1 or self.max_dispatches < 1 or self.max_question_rounds < 0:
            raise ValueError("pipeline timeout/dispatches must be positive and question rounds non-negative")


@dataclass(frozen=True, slots=True)
class PipelineServices:
    plan_builder: Callable[..., Path] = build_plan
    evidence_builder: Callable[..., Path] = build_evidence
    semantics_builder: Callable[..., Path] = build_semantics
    translation_builder: Callable[..., Path] = build_group_translation
    checker: Callable[..., dict[str, tuple[Path, dict[str, Any]]]] = run_group_checks
    resolver: Callable[..., tuple[Path, dict[str, Any]]] = resolve_check_failure


def _run_root(runs_root: Path, language: str, version: str, run_id: str) -> Path:
    return runs_root.resolve() / language.casefold() / version / run_id


def find_pipeline_run(runs_root: Path, run_id: str) -> Path:
    matches = [path.parent for path in runs_root.resolve().glob(f"*/*/{run_id}/run.json")]
    if not matches:
        raise FileNotFoundError(f"pipeline run does not exist: {run_id}")
    if len(matches) > 1:
        raise RuntimeError(f"pipeline run ID is ambiguous: {run_id}")
    return matches[0]


def load_pipeline_run(runs_root: Path, run_id: str) -> tuple[Path, dict[str, Any]]:
    directory = find_pipeline_run(runs_root, run_id)
    return directory, json.loads((directory / "run.json").read_text(encoding="utf-8"))


def _latest_compatible_run(runs_root: Path, request: PlanningRequest, mode: str = "lexical") -> str:
    candidates: list[tuple[str, str]] = []
    for path in runs_root.resolve().glob(f"{request.language.casefold()}/{request.version}/*/run.json"):
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if item.get("request") == request.to_dict() and item.get("indexMode", "lexical") == mode:
            candidates.append((str(item.get("updatedAt", "")), str(item.get("pipelineRunId", ""))))
    if not candidates:
        raise FileNotFoundError("no compatible pipeline run exists to resume")
    return max(candidates)[1]


def _database_for(options: PipelineOptions, request: PlanningRequest) -> Path:
    return options.index_root.resolve() / request.language.casefold() / request.version / "specification.sqlite"


def _source_manifest(options: PipelineOptions, request: PlanningRequest) -> Path:
    roots = options.repository_root.resolve() / "documents" / "sources"
    matches = sorted(roots.glob(f"*/{request.language.casefold()}/{request.version}/source-manifest.json"))
    matches.extend(sorted(roots.glob(f"{request.language.casefold()}/{request.version}/source-manifest.json")))
    unique = list(dict.fromkeys(path.resolve() for path in matches))
    if not unique:
        raise FileNotFoundError(
            f"official source manifest does not exist for {request.language} {request.version}"
        )
    if len(unique) > 1:
        raise RuntimeError(f"multiple source manifests match {request.language} {request.version}: {unique}")
    return unique[0]


def _manifest_sources(path: Path) -> list[tuple[str, Path, str | None]]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    result: list[tuple[str, Path, str | None]] = []
    for artifact in manifest.get("artifacts", []):
        kind = str(artifact.get("kind", "")).casefold()
        if kind not in {"pdf", "html"}:
            continue
        source = (path.parent / str(artifact.get("local_path", ""))).resolve()
        if not source.is_file():
            raise FileNotFoundError(f"official {kind} source does not exist: {source}")
        expected = str(artifact.get("sha256", ""))
        actual = sha256_file(source)
        if expected and actual != expected:
            raise ValueError(f"official source SHA-256 mismatch for {source}: expected {expected}, got {actual}")
        result.append((kind, source, artifact.get("url")))
    if not result:
        raise ValueError(f"source manifest has no supported PDF or HTML artifacts: {path}")
    return result


def _phase1_state(database: Path) -> tuple[bool, dict[str, Any]]:
    if not database.is_file():
        return False, {"ok": False, "reason": "DATABASE_MISSING", "database": str(database)}
    try:
        with connect(database, read_only=True) as connection:
            report = validate_database(connection)
            digest = source_database_digest(connection)
    except Exception as exc:
        return False, {"ok": False, "reason": "DATABASE_INVALID", "database": str(database), "error": str(exc)}
    errors = [item for item in report.get("issues", []) if item.get("severity") == "ERROR"]
    return not errors, {
        "ok": not errors,
        "reason": "FRESH" if not errors else "VALIDATION_FAILED",
        "database": str(database),
        "sourceDatabaseDigest": digest,
        "parserVersion": PARSER_VERSION,
        "schemaVersion": INDEX_SCHEMA_VERSION,
        "errors": errors,
        "warnings": [item for item in report.get("issues", []) if item.get("severity") == "WARNING"],
    }


def _ensure_phase1(options: PipelineOptions, request: PlanningRequest) -> dict[str, Any]:
    database = _database_for(options, request)
    fresh, state = _phase1_state(database)
    if fresh:
        return {**state, "disposition": "REUSED"}
    if options.dry_run:
        return {**state, "disposition": "WOULD_BUILD"}
    manifest_path = _source_manifest(options, request)
    parsed = []
    for kind, source, url in _manifest_sources(manifest_path):
        parsed.append(parse_pdf(source, url) if kind == "pdf" else parse_html(source, url))
    result = build_database(
        database, language=request.language, version=request.version, documents=parsed
    )
    page_text_by_source = {
        artifact["source_sha256"]: artifact for artifact in result["page_text_artifacts"]
    }
    index_manifest = {
        "language": request.language,
        "specification_version": request.version,
        "database": str(database),
        "parser_version": PARSER_VERSION,
        "index_schema_version": INDEX_SCHEMA_VERSION,
        "creation_timestamp": result["created_at"],
        "semantic_digest": result["semantic_digest"],
        "sources": [],
    }
    for item in sorted(parsed, key=lambda value: value.source_type):
        source_entry = {
            "source_type": item.source_type,
            "official_url": item.official_url,
            "local_path": item.path,
            "sha256": item.sha256,
            "byte_size": item.byte_size,
        }
        if item.sha256 in page_text_by_source:
            source_entry["page_text"] = page_text_by_source[item.sha256]
        index_manifest["sources"].append(source_entry)
    _write_json_atomic(database.with_name("index-manifest.json"), index_manifest)
    fresh, state = _phase1_state(database)
    if not fresh:
        raise RuntimeError(f"rebuilt Phase-1 index failed validation: {state.get('errors') or state.get('error')}")
    return {**state, "disposition": "BUILT", "sourceManifest": str(manifest_path)}


def prepare_index(
    request: PlanningRequest, options: PipelineOptions, *,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Prepare source/search indexes without creating a formalization run."""
    report = progress or (lambda _message: None)
    with retrieval_selection(options.index_mode):
        report("phase 1/7 index: validating freshness")
        state = _ensure_phase1(options, request)
        if options.index_mode == "semantic" and state.get("ok"):
            report("phase 1/7 index: ensuring semantic vectors")
            embedding_state = ensure_embeddings(
                _database_for(options, request),
                dry_run=options.dry_run or not _phase_selected(options, "index"),
            )
            state["semanticIndex"] = embedding_state
            if embedding_state["disposition"] == "WOULD_BUILD" and not options.dry_run:
                raise FileNotFoundError("semantic index needs building but Phase 1 is before --from")
        report(f"phase 1/7 index: {state['disposition'].lower()} ({state['reason']})")
        return state


def _matching_plan(plans_root: Path, request: PlanningRequest, digest: str) -> tuple[Path, dict[str, Any]] | None:
    matches: list[tuple[str, Path, dict[str, Any]]] = []
    expected = request.to_dict()
    for directory in plans_root.resolve().glob(f"{request.language.casefold()}/{request.version}/plan:*"):
        try:
            stored_request = json.loads((directory / "request.json").read_text(encoding="utf-8"))
            plan = json.loads((directory / "plan.json").read_text(encoding="utf-8"))
            metadata = json.loads((directory / "planner-run.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (
            stored_request == expected
            and plan.get("schemaVersion") == PLAN_SCHEMA_VERSION
            and plan.get("sourceDatabaseDigest") == digest
            and metadata.get("outcome") == "VALID"
            and metadata.get("indexMode", "lexical") == index_mode()
            and (plan.get("graphStatus") == "ACYCLIC" or "executionSchedule" in plan)
        ):
            matches.append((str(metadata.get("finishedAt", "")), directory, plan))
    if not matches:
        return None
    _, directory, plan = max(matches, key=lambda item: item[0])
    return directory, plan


def _plan_for_manifest(options: PipelineOptions, manifest: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    plan_run_id = manifest.get("planRunId")
    if not plan_run_id:
        raise FileNotFoundError("resumed pipeline run has no Phase-2 plan")
    matches = [path.parent for path in options.plans_root.resolve().glob(f"*/*/{plan_run_id}/plan.json")]
    if len(matches) != 1:
        raise FileNotFoundError(f"resumed Phase-2 plan does not exist uniquely: {plan_run_id}")
    return matches[0], json.loads((matches[0] / "plan.json").read_text(encoding="utf-8"))


def _ordered_units(plan: dict[str, Any]) -> list[dict[str, Any]]:
    if "executionSchedule" in plan:
        validate_execution_schedule(plan)
    elif plan.get("graphStatus") != "ACYCLIC":
        raise RuntimeError("Phase-2 dependency graph is cyclic and has no validated execution schedule; rerun with --from plan")
    by_id = {item["unitId"]: item for item in plan.get("requestedUnits", [])}
    ordered: list[dict[str, Any]] = []
    for layer in sorted(plan.get("processingLayers", []), key=lambda item: item["layer"]):
        for unit_id in layer.get("unitIds", []):
            if unit_id not in by_id:
                raise RuntimeError(f"processing layer references unknown unit: {unit_id}")
            ordered.append(by_id[unit_id])
    if len(ordered) != len(by_id) or {item["unitId"] for item in ordered} != set(by_id):
        raise RuntimeError("Phase-2 processing layers must schedule every requested unit exactly once")
    return ordered


def _archive_directory(path: Path, run_directory: Path, phase: str, unit_id: str) -> None:
    if not path.exists():
        return
    safe_unit = unit_id.replace(":", "-").replace("/", "-")
    destination = run_directory / "superseded" / phase / safe_unit / utc_now().replace(":", "-")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(destination))


def _evidence_reusable(
    options: PipelineOptions, plan: dict[str, Any], unit_id: str, database: Path
) -> bool:
    try:
        _, bundle = load_unit_bundle(options.evidence_root, plan, unit_id)
        SemanticScope.from_inputs(plan, bundle, unit_id, created_at="reuse-check")
        with connect(database, read_only=True) as connection:
            return not validate_bundle(EvidenceQuery(connection), plan, bundle)
    except (FileNotFoundError, KeyError, RuntimeError, ValueError, json.JSONDecodeError):
        return False


def _semantics_reusable(options: PipelineOptions, plan: dict[str, Any], unit_id: str) -> bool:
    try:
        _, bundle = load_unit_bundle(options.evidence_root, plan, unit_id)
        _, artifact = load_semantics(options.semantics_root, plan, unit_id)
        return artifact.get("outcome") == "SUCCESS" and not validate_artifact(plan, bundle, artifact)
    except (FileNotFoundError, KeyError, RuntimeError, ValueError, json.JSONDecodeError):
        return False


def _translation_reusable(options: PipelineOptions, plan: dict[str, Any], group: str) -> bool:
    try:
        directory, _, manifest, metadata = load_group_translation(
            options.translations_root, plan, group
        )
        if manifest.get("schemaVersion") != 2:
            return False
        semantics_by_unit = {
            str(unit["unitId"]): load_semantics(
                options.semantics_root, plan, str(unit["unitId"])
            )[1]
            for unit in grouped_units(plan).get(group, [])
        }
        scope = TranslationGroupScope.from_inputs(
            plan, group, semantics_by_unit, created_at=str(manifest.get("createdAt", ""))
        )
        return (
            metadata.get("outcome") == "SUCCESS"
            and manifest.get("translationRunId") == scope.translation_run_id
            and not validate_published(plan, semantics_by_unit, directory)
        )
    except (FileNotFoundError, KeyError, RuntimeError, ValueError, json.JSONDecodeError):
        return False


def _check_reusable(options: PipelineOptions, plan: dict[str, Any], unit_id: str) -> tuple[bool, dict[str, Any] | None]:
    try:
        _, semantics = load_semantics(options.semantics_root, plan, unit_id)
        _, source, translation_manifest, _ = load_translation(options.translations_root, plan, unit_id)
        _, check = load_check(options.checks_root, plan, unit_id)
    except (FileNotFoundError, KeyError, RuntimeError, ValueError, json.JSONDecodeError):
        return False, None
    expected = {
        "semantics": _hash_text(canonical_json(semantics)),
        "leanSource": _hash_text(source),
        "translationManifest": _hash_text(canonical_json(translation_manifest)),
    }
    valid = (
        check.get("phase") == "CHECK"
        and check.get("translationRunId") == translation_manifest.get("translationRunId")
        and check.get("inputHashes") == expected
    )
    return valid, check if valid else None


def _new_manifest(request: PlanningRequest, options: PipelineOptions) -> tuple[Path, dict[str, Any]]:
    created = utc_now()
    run_id = stable_id("pipeline-run", request.language.casefold(), request.version, request.to_dict(), created)
    directory = _run_root(options.runs_root, request.language, request.version, run_id)
    manifest = {
        "schemaVersion": 1,
        "phase": "PIPELINE",
        "pipelineRunId": run_id,
        "request": request.to_dict(),
        "createdAt": created,
        "updatedAt": created,
        "status": "RUNNING",
        "fromPhase": options.from_phase,
        "untilPhase": options.until_phase,
        "dryRun": options.dry_run,
        "maxQuestionRounds": options.max_question_rounds,
        "indexMode": options.index_mode,
        "timing": {
            "startedAt": created,
            "finishedAt": None,
            "elapsedSeconds": 0.0,
            "phases": {},
            "attempts": [],
        },
        "phase1": None,
        "planRunId": None,
        "planDirectory": None,
        "units": {},
        "error": None,
    }
    return directory, manifest


def _persist(directory: Path, manifest: dict[str, Any], options: PipelineOptions) -> None:
    manifest["updatedAt"] = utc_now()
    if not options.dry_run:
        _write_json_atomic(directory / "run.json", manifest)


def _unit_stage(manifest: dict[str, Any], unit: dict[str, Any]) -> dict[str, Any]:
    return manifest["units"].setdefault(unit["unitId"], {
        "name": unit["name"],
        "status": "PENDING",
        "stages": {},
    })


def _phase_selected(options: PipelineOptions, phase: str) -> bool:
    return PHASES.index(options.from_phase) <= PHASES.index(phase) <= PHASES.index(options.until_phase)


def run_pipeline(
    request: PlanningRequest,
    options: PipelineOptions,
    *,
    services: PipelineServices | None = None,
    progress: Callable[[str], None] | None = None,
) -> tuple[Path | None, dict[str, Any]]:
    with retrieval_selection(options.index_mode):
        return _run_pipeline(request, options, services=services, progress=progress)


def _run_pipeline(
    request: PlanningRequest,
    options: PipelineOptions,
    *,
    services: PipelineServices | None = None,
    progress: Callable[[str], None] | None = None,
) -> tuple[Path | None, dict[str, Any]]:
    services = services or PipelineServices()
    progress = progress or (lambda _message: None)
    if options.resume == "latest":
        resume_id = _latest_compatible_run(options.runs_root, request, options.index_mode)
    else:
        resume_id = options.resume
    if resume_id:
        directory, manifest = load_pipeline_run(options.runs_root, resume_id)
        if manifest.get("indexMode", "lexical") != options.index_mode:
            raise ValueError("--resume index mode does not match the stored run; start a new run")
        if manifest.get("request") != request.to_dict():
            raise ValueError("--resume request does not match the stored pipeline request")
        manifest["status"] = "RUNNING"
        manifest["fromPhase"] = options.from_phase
        manifest["untilPhase"] = options.until_phase
        manifest["dryRun"] = options.dry_run
        manifest["maxQuestionRounds"] = options.max_question_rounds
        manifest["indexMode"] = options.index_mode
        manifest["error"] = None
    else:
        directory, manifest = _new_manifest(request, options)

    def report(message: str) -> None:
        progress(f"{manifest['pipelineRunId']} {message}")

    timing = manifest.get("timing")
    if not isinstance(timing, dict):
        timing = {
            "startedAt": manifest.get("createdAt", utc_now()),
            "finishedAt": None,
            "elapsedSeconds": 0.0,
            "phases": {},
            "attempts": [],
        }
        manifest["timing"] = timing
    timing["finishedAt"] = None
    attempt = {
        "startedAt": utc_now(),
        "finishedAt": None,
        "elapsedSeconds": None,
        "status": "RUNNING",
        "phases": {},
    }
    timing.setdefault("attempts", []).append(attempt)
    attempt_started = perf_counter()
    active_phase: str | None = None
    active_phase_started = 0.0

    def start_phase(phase: str) -> None:
        nonlocal active_phase, active_phase_started
        if active_phase is not None:
            raise RuntimeError(f"cannot start pipeline phase {phase} while {active_phase} is active")
        active_phase = phase
        active_phase_started = perf_counter()
        attempt["phases"][phase] = {
            "startedAt": utc_now(),
            "finishedAt": None,
            "elapsedSeconds": None,
            "status": "RUNNING",
        }

    def finish_phase(status: str = "COMPLETE") -> None:
        nonlocal active_phase, active_phase_started
        if active_phase is None:
            return
        phase = active_phase
        elapsed = round(max(0.0, perf_counter() - active_phase_started), 6)
        phase_timing = attempt["phases"][phase]
        phase_timing.update({
            "finishedAt": utc_now(),
            "elapsedSeconds": elapsed,
            "status": status,
        })
        aggregate = timing.setdefault("phases", {}).setdefault(
            phase, {"elapsedSeconds": 0.0, "executions": 0}
        )
        aggregate["elapsedSeconds"] = round(float(aggregate["elapsedSeconds"]) + elapsed, 6)
        aggregate["executions"] = int(aggregate["executions"]) + 1
        verb = "finished" if status == "COMPLETE" else status.casefold()
        report(f"phase {PHASES.index(phase) + 1}/7 {phase}: {verb} after {_format_duration(elapsed)}")
        active_phase = None
        active_phase_started = 0.0

    def finish_timing(status: str) -> None:
        phase_status = "COMPLETE" if status in {"COMPLETE", "DRY_RUN", "NEEDS_ROUTING"} else status
        finish_phase(phase_status)
        elapsed = round(max(0.0, perf_counter() - attempt_started), 6)
        attempt.update({
            "finishedAt": utc_now(),
            "elapsedSeconds": elapsed,
            "status": status,
        })
        timing["elapsedSeconds"] = round(float(timing.get("elapsedSeconds", 0.0)) + elapsed, 6)
        timing["finishedAt"] = attempt["finishedAt"]
        report(f"total active pipeline time: {_format_duration(elapsed)}")

    try:
        start_phase("index")
        phase1 = prepare_index(request, options, progress=report)
        manifest["phase1"] = phase1
        finish_phase()
        _persist(directory, manifest, options)
        if PHASES.index(options.until_phase) == 0:
            manifest["status"] = "DRY_RUN" if options.dry_run else "COMPLETE"
            finish_timing(manifest["status"])
            _persist(directory, manifest, options)
            report(f"finished with status {manifest['status']}")
            return None if options.dry_run else directory, manifest
        if not phase1.get("ok") and options.dry_run:
            manifest["status"] = "DRY_RUN"
            finish_timing(manifest["status"])
            report("dry run stopped because Phase 1 would need rebuilding")
            return None, manifest

        start_phase("plan")
        database = _database_for(options, request)
        digest = phase1["sourceDatabaseDigest"]
        plan_pair: tuple[Path, dict[str, Any]] | None = None
        if resume_id and manifest.get("planRunId"):
            plan_pair = _plan_for_manifest(options, manifest)
            if plan_pair[1].get("sourceDatabaseDigest") != digest:
                raise RuntimeError("resumed Phase-2 plan is stale relative to the current Phase-1 index")
            if plan_pair[1].get("schemaVersion") != PLAN_SCHEMA_VERSION:
                if not _phase_selected(options, "plan"):
                    raise RuntimeError(
                        "resumed Phase-2 plan predates specification-derived translation groups; "
                        "rerun with --from plan"
                    )
                report("phase 2/7 plan: legacy grouping plan cannot be reused; replanning")
                plan_pair = None
            elif plan_pair[1].get("graphStatus") == "CYCLIC" and "executionSchedule" not in plan_pair[1]:
                if not _phase_selected(options, "plan"):
                    raise RuntimeError("resumed cyclic plan has no execution schedule; rerun with --from plan")
                report("phase 2/7 plan: legacy cyclic plan needs an execution schedule; replanning")
                plan_pair = None
        if plan_pair is None:
            plan_pair = _matching_plan(options.plans_root, request, digest)
        if plan_pair is None:
            if not _phase_selected(options, "plan"):
                raise FileNotFoundError("no reusable Phase-2 plan exists and Phase 2 is before --from")
            if options.dry_run:
                manifest["plan"] = {"disposition": "WOULD_BUILD"}
                manifest["status"] = "DRY_RUN"
                report("phase 2/7 plan: would build; dry run cannot derive a unit schedule")
                finish_timing(manifest["status"])
                return None, manifest
            report("phase 2/7 plan: starting bounded Planner session")
            plan_directory = services.plan_builder(
                database, options.plans_root, request, timeout_seconds=options.timeout_seconds
            )
            plan = json.loads((plan_directory / "plan.json").read_text(encoding="utf-8"))
            plan_disposition = "BUILT"
        else:
            plan_directory, plan = plan_pair
            plan_disposition = "REUSED"
        report(f"phase 2/7 plan: {plan_disposition.lower()} {plan['planRunId']}")
        manifest["planRunId"] = plan["planRunId"]
        manifest["planDirectory"] = str(plan_directory)
        manifest["plan"] = {"disposition": plan_disposition, "sourceDatabaseDigest": digest}
        units = _ordered_units(plan)
        if "executionSchedule" in plan:
            joint = sum(len(item["plannedGroupNames"]) > 1 for item in plan["executionSchedule"]["groupComponents"])
            report(f"phase 2/7 plan: validated execution schedule; {len(units)} units, "
                   f"{len(plan['translationGroups'])} translation groups, {joint} joint groups; "
                   f"{len(plan['cycles'])} source dependency cycles preserved")
        for unit in units:
            _unit_stage(manifest, unit)
        finish_phase()
        _persist(directory, manifest, options)
        if PHASES.index(options.until_phase) == 1:
            manifest["status"] = "DRY_RUN" if options.dry_run else "COMPLETE"
            finish_timing(manifest["status"])
            _persist(directory, manifest, options)
            report(f"finished with status {manifest['status']}")
            return None if options.dry_run else directory, manifest

        unit_positions = {
            str(unit["unitId"]): f"unit {index}/{len(units)} {unit['name']}"
            for index, unit in enumerate(units, start=1)
        }

        # Phases 3 and 4 remain instruction-scoped, but every semantic artifact must be
        # ready before the first group-scoped Translator session starts.
        start_phase("evidence")
        for unit in units:
            unit_id = str(unit["unitId"])
            unit_label = unit_positions[unit_id]
            state = _unit_stage(manifest, unit)
            state["status"] = "RUNNING"
            reusable = _evidence_reusable(options, plan, unit_id, database)
            disposition = "REUSED" if reusable else "WOULD_BUILD"
            if not reusable and not _phase_selected(options, "evidence"):
                raise FileNotFoundError(f"no fresh Phase-3 evidence exists for {unit_id}")
            if not reusable and not options.dry_run:
                path = evidence_run_root(options.evidence_root, plan) / unit_directory_name(unit)
                if path.exists():
                    report(f"{unit_label} phase 3/7 evidence: archiving incomplete or stale artifact")
                _archive_directory(path, directory, "evidence", unit_id)
                report(f"{unit_label} phase 3/7 evidence: starting bounded Retriever session")
                services.evidence_builder(
                    database, plan, options.evidence_root, unit_ids=[unit_id], jobs=1,
                    timeout_seconds=options.timeout_seconds,
                )
                reusable, disposition = True, "BUILT"
            state["stages"]["evidence"] = disposition
            if options.until_phase == "evidence":
                state["status"] = "PASS" if reusable else "PLANNED"
            report(f"{unit_label} phase 3/7 evidence: {disposition.lower().replace('_', ' ')}")
            _persist(directory, manifest, options)
        finish_phase()

        if options.until_phase != "evidence":
            start_phase("semantics")
            for unit in units:
                unit_id = str(unit["unitId"])
                unit_label = unit_positions[unit_id]
                state = _unit_stage(manifest, unit)
                reusable = _semantics_reusable(options, plan, unit_id)
                disposition = "REUSED" if reusable else "WOULD_BUILD"
                if not reusable and not _phase_selected(options, "semantics"):
                    raise FileNotFoundError(f"no fresh Phase-4 semantics exists for {unit_id}")
                if not reusable and not options.dry_run:
                    semantic_path = semantics_unit_directory(options.semantics_root, plan, unit)
                    if semantic_path.exists():
                        report(f"{unit_label} phase 4/7 semantics: archiving incomplete or stale artifact")
                    _archive_directory(semantic_path, directory, "semantics", unit_id)
                    report(f"{unit_label} phase 4/7 semantics: starting bounded Extractor session")
                    services.semantics_builder(
                        plan, options.evidence_root, options.semantics_root,
                        unit_ids=[unit_id], timeout_seconds=options.timeout_seconds,
                        database=database, max_question_rounds=options.max_question_rounds,
                        progress=lambda message, label=unit_label: report(
                            f"{label} phase 4/7 semantics: {message}"
                        ),
                    )
                    reusable, disposition = True, "BUILT"
                state["stages"]["semantics"] = disposition
                if options.until_phase == "semantics":
                    state["status"] = "PASS" if reusable else "PLANNED"
                report(f"{unit_label} phase 4/7 semantics: {disposition.lower().replace('_', ' ')}")
                _persist(directory, manifest, options)
            finish_phase()

        groups = grouped_units(plan)
        translation_fresh_by_group: dict[str, bool] = {}
        if PHASES.index(options.until_phase) >= PHASES.index("translate"):
            start_phase("translate")
            for group, group_units in groups.items():
                group_label = f"group {group} ({len(group_units)} instruction(s))"
                reusable = _translation_reusable(options, plan, group)
                disposition = "REUSED" if reusable else "WOULD_BUILD"
                if not reusable and not _phase_selected(options, "translate"):
                    raise FileNotFoundError(f"no fresh Phase-5 translation exists for group {group}")
                if not reusable and not options.dry_run:
                    translation_path = translation_group_directory(
                        options.translations_root, plan, group
                    )
                    if translation_path.exists():
                        report(f"{group_label} phase 5/7 translate: archiving incomplete or stale artifact")
                    _archive_directory(translation_path, directory, "translate", group)
                    for member in group_units:
                        legacy_path = legacy_translation_unit_directory(
                            options.translations_root, plan, member
                        )
                        if legacy_path.exists():
                            report(
                                f"{group_label} phase 5/7 translate: archiving legacy per-unit artifact "
                                f"for {member['name']}"
                            )
                        _archive_directory(
                            legacy_path, directory, "translate-legacy", str(member["unitId"])
                        )
                    report(f"{group_label} phase 5/7 translate: starting one bounded Translator session")
                    services.translation_builder(
                        plan, options.semantics_root, options.translations_root,
                        group=group, timeout_seconds=options.timeout_seconds,
                    )
                    reusable, disposition = True, "BUILT"
                for unit in group_units:
                    state = _unit_stage(manifest, unit)
                    state["stages"]["translate"] = disposition
                    if options.until_phase == "translate":
                        state["status"] = "PASS" if reusable else "PLANNED"
                translation_fresh_by_group[group] = reusable
                report(f"{group_label} phase 5/7 translate: {disposition.lower().replace('_', ' ')}")
                _persist(directory, manifest, options)
            finish_phase()

        checks: dict[str, dict[str, Any] | None] = {}
        if PHASES.index(options.until_phase) >= PHASES.index("check"):
            start_phase("check")
            for group, group_units in groups.items():
                freshness = {
                    str(unit["unitId"]): (
                        _check_reusable(options, plan, str(unit["unitId"]))
                        if translation_fresh_by_group.get(group, False)
                        else (False, None)
                    )
                    for unit in group_units
                }
                stale = [unit_id for unit_id, (fresh, _check) in freshness.items() if not fresh]
                if stale and not _phase_selected(options, "check"):
                    raise FileNotFoundError(
                        f"no fresh Phase-6 check exists for group {group}: {', '.join(stale)}"
                    )
                ran_results: dict[str, tuple[Path, dict[str, Any]]] = {}
                if stale and not options.dry_run:
                    report(f"group {group} phase 6/7 check: running one BUILD plus group COVERAGE/TRACEABILITY")
                    raw_results = services.checker(
                        plan, evidence_root=options.evidence_root, semantics_root=options.semantics_root,
                        translations_root=options.translations_root, checks_root=options.checks_root,
                        database=database, group=group,
                    )
                    if isinstance(raw_results, tuple) and len(group_units) == 1:
                        ran_results = {str(group_units[0]["unitId"]): raw_results}
                    else:
                        ran_results = raw_results
                for unit in group_units:
                    unit_id = str(unit["unitId"])
                    fresh, check = freshness[unit_id]
                    disposition = "REUSED" if fresh else ("RAN" if ran_results else "WOULD_RUN")
                    if unit_id in ran_results:
                        check = ran_results[unit_id][1]
                    checks[unit_id] = check
                    state = _unit_stage(manifest, unit)
                    state["stages"]["check"] = {
                        "disposition": disposition,
                        "status": check.get("status") if check else None,
                    }
                    if options.until_phase == "check":
                        state["status"] = check.get("status", "PLANNED") if check else "PLANNED"
                    report(
                        f"{unit_positions[unit_id]} phase 6/7 check: "
                        f"{disposition.lower().replace('_', ' ')}"
                        f"{(' ' + check['status']) if check is not None else ''}"
                    )
                _persist(directory, manifest, options)
            finish_phase()

        if options.until_phase == "troubleshoot":
            start_phase("troubleshoot")
            for unit in units:
                unit_id = str(unit["unitId"])
                unit_label = unit_positions[unit_id]
                state = _unit_stage(manifest, unit)
                # An earlier group repair may have replaced this instruction's check.
                fresh, refreshed = _check_reusable(options, plan, unit_id)
                check = refreshed if fresh else checks.get(unit_id)
                if fresh and refreshed != checks.get(unit_id):
                    state["stages"]["check"] = {
                        "disposition": "RERAN_DURING_GROUP_ROUTING",
                        "status": refreshed.get("status") if refreshed else None,
                    }
                if check is None:
                    state["stages"]["troubleshoot"] = "WOULD_ROUTE_IF_REQUIRED"
                    state["status"] = "PLANNED"
                elif action_for(check) == NO_ACTION:
                    state["stages"]["troubleshoot"] = "NOT_REQUIRED"
                    state["status"] = "PASS"
                    report(f"{unit_label} phase 7/7 troubleshoot: not required")
                elif options.dry_run:
                    state["stages"]["troubleshoot"] = {
                        "disposition": "WOULD_ROUTE", "action": action_for(check)
                    }
                    state["status"] = "PLANNED"
                    report(f"{unit_label} phase 7/7 troubleshoot: would route {action_for(check)}")
                else:
                    report(f"{unit_label} phase 7/7 troubleshoot: routing {action_for(check)}")
                    output, resolution = services.resolver(
                        plan, evidence_root=options.evidence_root, semantics_root=options.semantics_root,
                        translations_root=options.translations_root, checks_root=options.checks_root,
                        troubleshooting_root=options.troubleshooting_root, database=database,
                        unit_id=unit_id, timeout_seconds=options.timeout_seconds,
                        max_dispatches=options.max_dispatches, repository_root=options.repository_root,
                    )
                    state["stages"]["troubleshoot"] = {
                        "disposition": "ROUTED", "directory": str(output),
                        "outcome": resolution["outcome"], "dispatches": resolution["dispatches"],
                        "stopReason": resolution["stopReason"],
                    }
                    final_check = resolution.get("checkResult")
                    if isinstance(final_check, dict):
                        state["stages"]["check"] = {
                            "disposition": "RERAN_DURING_ROUTING",
                            "status": final_check.get("status"),
                        }
                    if resolution["outcome"] != "COMPLETE":
                        raise RuntimeError(
                            f"Phase-7 routing stopped for {unit_id}: {resolution['stopReason']}"
                        )
                    state["status"] = "PASS"
                    report(
                        f"{unit_label} phase 7/7 troubleshoot: {resolution['outcome'].lower()} "
                        f"after {resolution['dispatches']} dispatch(es)"
                    )
                _persist(directory, manifest, options)
                report(f"{unit_label}: {state['status'].lower()}")
            finish_phase()

        if options.dry_run:
            manifest["status"] = "DRY_RUN"
        elif options.until_phase == "check" and any(item["status"] == "FAIL" for item in manifest["units"].values()):
            manifest["status"] = "NEEDS_ROUTING"
        else:
            manifest["status"] = "COMPLETE"
        finish_timing(manifest["status"])
        _persist(directory, manifest, options)
        report(f"finished with status {manifest['status']}")
        return None if options.dry_run else directory, manifest
    except KeyboardInterrupt:
        manifest["status"] = "INTERRUPTED"
        manifest["error"] = "interrupted by user"
        finish_timing(manifest["status"])
        _persist(directory, manifest, options)
        report(f"interrupted; resume with --resume {manifest['pipelineRunId']}")
        raise
    except Exception as exc:
        manifest["status"] = "FAILED"
        manifest["error"] = str(exc)
        finish_timing(manifest["status"])
        _persist(directory, manifest, options)
        report(f"failed: {exc}")
        raise
