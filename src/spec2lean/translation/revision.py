from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ..semantics.store import load_semantics
from ..util import canonical_json, sha256_file, stable_id
from .groups import group_for_unit, grouped_units
from .models import (
    TRANSLATION_SCHEMA_VERSION,
    TRANSLATOR_AGENT,
    TRANSLATOR_MODEL,
    TRANSLATOR_REASONING,
    TranslationGroupScope,
)
from .revision_prompt import build_translation_revision_prompt
from .runner import _session_id, opencode_config, require_translator_model
from .store import load_group_translation
from .validation import validate_manifest, validate_published


SessionRunner = Callable[..., dict[str, Any]]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _hash_json(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _file_hash(path: Path) -> str:
    return "sha256:" + sha256_file(path)


def _write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def run_translation_revision_session(
    context: dict[str, Any], *, timeout_seconds: int = 1800,
    run_command: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    executable = shutil.which("opencode")
    if executable is None:
        raise RuntimeError("OpenCode executable is not installed or not on PATH")
    require_translator_model(executable)
    scope = TranslationGroupScope.from_dict(context["scope"])
    prompt = build_translation_revision_prompt(
        scope,
        context["semanticsByUnit"],
        context["leanSource"],
        context["translationManifest"],
        context["diagnostics"],
        context["reason"],
        context["triggeringUnitId"],
        context.get("sharedCoreSource"),
    )
    with tempfile.TemporaryDirectory(prefix="spec2lean-translation-revision-") as temporary_name:
        temporary = Path(temporary_name)
        scope_path = temporary / "translation-scope.json"
        semantics_path = temporary / "semantics-by-unit.json"
        submission_path = temporary / "submission.json"
        scope_path.write_text(json.dumps(scope.to_dict(), ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        semantics_path.write_text(json.dumps(context["semanticsByUnit"], ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        config = opencode_config(scope_path, semantics_path, submission_path)
        command = [
            executable, "run", "--pure", "--print-logs", "--log-level", "ERROR",
            "--format", "json", "--agent", TRANSLATOR_AGENT, "--model", TRANSLATOR_MODEL,
            "--variant", TRANSLATOR_REASONING, "--title",
            f"{scope.plan_run_id}:{scope.group}:revise-translation", prompt,
        ]
        environment = os.environ.copy()
        environment["OPENCODE_CONFIG_CONTENT"] = json.dumps(config, separators=(",", ":"))
        config_dir, home_dir = temporary / "opencode-config", temporary / "opencode-home"
        config_dir.mkdir()
        home_dir.mkdir()
        environment["OPENCODE_CONFIG_DIR"] = str(config_dir)
        environment["OPENCODE_TEST_HOME"] = str(home_dir)
        environment["OPENCODE_DISABLE_PROJECT_CONFIG"] = "1"
        environment["OPENCODE_DISABLE_EXTERNAL_SKILLS"] = "1"
        environment["OPENCODE_DISABLE_CLAUDE_CODE_SKILLS"] = "1"
        try:
            completed = run_command(
                command, cwd=context["translationDirectory"], env=environment, text=True,
                capture_output=True, timeout=timeout_seconds, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            completed = subprocess.CompletedProcess(command, 124, exc.stdout or "", exc.stderr or "")
        error = None
        if completed.returncode == 124:
            error = f"OpenCode Translation Revision session timed out after {timeout_seconds} seconds"
        elif completed.returncode != 0:
            error = f"OpenCode Translation Revision exited with status {completed.returncode}"
        elif not submission_path.is_file():
            error = "OpenCode Translation Revision finished without a valid submit_translation call"
        candidate = None
        if submission_path.is_file():
            try:
                candidate = json.loads(submission_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                error = error or "Translation Revision submission is invalid JSON"
        return {
            "candidate": candidate,
            "error": error,
            "session": {
                "provider": "opencode", "model": TRANSLATOR_MODEL,
                "reasoning": TRANSLATOR_REASONING, "singleSession": True,
                "automaticRetries": 0, "command": command[:-1] + ["<translation-revision-prompt>"],
                "exitCode": completed.returncode, "sessionId": _session_id(completed.stdout),
                "stdout": completed.stdout, "stderr": completed.stderr,
            },
        }


def revise_translation(
    plan: dict[str, Any], *, semantics_root: Path, translations_root: Path, unit_id: str,
    diagnostics: list[dict[str, Any]], reason: str = "COVERAGE_FAILURE",
    timeout_seconds: int = 1800, source_check_hash: str | None = None,
    session_runner: SessionRunner = run_translation_revision_session,
    now: Callable[[], str] = utc_now,
) -> tuple[Path, dict[str, Any]]:
    if reason not in {"COVERAGE_FAILURE", "SEMANTICS_REVISED"}:
        raise ValueError(f"unsupported translation revision reason: {reason}")
    if not diagnostics:
        raise ValueError("translation revision requires concrete upstream diagnostics")
    group = group_for_unit(plan, unit_id)
    semantics_by_unit: dict[str, dict[str, Any]] = {}
    semantic_directories: dict[str, Path] = {}
    for unit in grouped_units(plan)[group]:
        member_id = str(unit["unitId"])
        semantic_directory, semantics = load_semantics(semantics_root, plan, member_id)
        semantic_directories[member_id] = semantic_directory
        semantics_by_unit[member_id] = semantics
    directory, source, manifest, _ = load_group_translation(translations_root, plan, group)
    shared_core = None
    if isinstance(manifest.get("sharedCore"), dict):
        from .shared_core import load_core

        shared_core = load_core(
            translations_root, plan, str(manifest["sharedCore"]["coreRunId"])
        )
    if source_check_hash is not None:
        for path in directory.glob("revisions/*/translation-revision.json"):
            recorded = json.loads(path.read_text(encoding="utf-8"))
            if recorded.get("sourceCheckHash") == source_check_hash:
                raise FileExistsError(f"Phase-6 check was already consumed by translation revision: {path.parent}")

    started_at = now()
    scope = TranslationGroupScope.from_inputs(
        plan, group, semantics_by_unit, created_at=started_at, shared_core=shared_core
    )
    lean_name = str(manifest.get("leanFile", scope.lean_file))
    lean_path = directory / lean_name
    manifest_path = directory / "translation-manifest.json"
    run_path = directory / "translator-run.json"
    before = {
        lean_name: _file_hash(lean_path),
        "translation-manifest.json": _file_hash(manifest_path),
        "translator-run.json": _file_hash(run_path),
    }
    revision_id = stable_id(
        "translation-group-revision", plan["planRunId"], group, unit_id,
        before[lean_name], before["translation-manifest.json"], _hash_json(diagnostics), reason,
        source_check_hash or "UNBOUND",
    )
    revision_directory = directory / "revisions" / revision_id
    if revision_directory.exists():
        raise FileExistsError(f"translation revision was already recorded: {revision_directory}")
    context = {
        "scope": scope.to_dict(),
        "semanticsByUnit": semantics_by_unit,
        "leanSource": source,
        "translationManifest": manifest,
        "diagnostics": diagnostics,
        "reason": reason,
        "triggeringUnitId": unit_id,
        "translationDirectory": str(directory),
        "sharedCoreSource": (
            getattr(shared_core, "source", None)
            or (
                shared_core.source_path.read_text(encoding="utf-8")
                if shared_core is not None and hasattr(shared_core, "source_path") else None
            )
        ),
    }
    result = session_runner(context, timeout_seconds=timeout_seconds)
    if result.get("error"):
        raise RuntimeError(str(result["error"]))
    candidate = result.get("candidate")
    if not isinstance(candidate, dict):
        raise ValueError("translation revision did not submit a candidate")
    candidate_source = candidate.get("leanSource")
    candidate_manifest = candidate.get("manifest")
    core_manifest = getattr(shared_core, "manifest", None)
    validation = validate_manifest(
        plan, semantics_by_unit, candidate_source, candidate_manifest,
        core_manifest=core_manifest,
    )
    if validation:
        raise ValueError(
            "translation revision failed deterministic validation: "
            + "; ".join(item["message"] for item in validation)
        )
    if (
        str(candidate_source).rstrip() == source.rstrip()
        and candidate_manifest == manifest
    ):
        raise ValueError("translation revision made no artifact change")

    new_source = str(candidate_source).rstrip() + "\n"
    new_manifest = json.dumps(candidate_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    session = result.get("session") or {}
    run_metadata = {
        "schemaVersion": TRANSLATION_SCHEMA_VERSION,
        "phase": "LLM_GROUP_TRANSLATOR",
        "planRunId": scope.plan_run_id,
        "group": {"name": group, "unitIds": list(scope.unit_ids)},
        "translationRunId": scope.translation_run_id,
        "translator": "opencode",
        "model": TRANSLATOR_MODEL,
        "reasoning": TRANSLATOR_REASONING,
        "singleSession": True,
        "automaticRetries": 0,
        "startedAt": started_at,
        "finishedAt": now(),
        "semanticsArtifactPaths": [
            str(semantic_directories[member_id] / "semantics.json") for member_id in scope.unit_ids
        ],
        "semanticsArtifacts": [
            {"unitId": member_id, "runId": dict(scope.semantics_run_ids)[member_id], "artifactHash": artifact_hash}
            for member_id, artifact_hash in scope.semantics_artifact_hashes
        ],
        "inputBoundary": (
            "PHASE_4_AND_FROZEN_SHARED_CORE"
            if scope.shared_core is not None
            else "PHASE_4_SEMANTIC_ARTIFACTS_ONLY"
        ),
        "sharedCore": manifest.get("sharedCore"),
        "targetLanguage": "Lean",
        "targetVersion": "4",
        "command": session.get("command", []),
        "exitCode": 0,
        "sessionId": session.get("sessionId"),
        "outcome": "SUCCESS",
        "error": None,
        "stdout": session.get("stdout", ""),
        "stderr": session.get("stderr", ""),
        "revisionRunId": revision_id,
        "revisionReason": reason,
        "revisionStartedAt": started_at,
        "triggeringUnitId": unit_id,
    }
    old_text = {
        lean_name: lean_path.read_text(encoding="utf-8"),
        "translation-manifest.json": manifest_path.read_text(encoding="utf-8"),
        "translator-run.json": run_path.read_text(encoding="utf-8"),
    }
    revision_directory.mkdir(parents=True)
    for name, content in old_text.items():
        _write_atomic(revision_directory / f"before-{name}", content)
    try:
        _write_atomic(lean_path, new_source)
        _write_atomic(manifest_path, new_manifest)
        _write_atomic(run_path, json.dumps(run_metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        published = validate_published(
            plan, semantics_by_unit, directory, core_manifest=core_manifest
        )
        if published:
            raise ValueError(
                "stored translation revision failed validation: "
                + "; ".join(item["message"] for item in published)
            )
    except Exception:
        for name, content in old_text.items():
            _write_atomic(directory / name, content)
        raise
    after = {name: _file_hash(directory / name) for name in before}
    changed = [name for name in before if before[name] != after[name]]
    metadata = {
        "schemaVersion": 2,
        "phase": "LLM_GROUP_TRANSLATOR_REVISION",
        "revisionRunId": revision_id,
        "planRunId": plan["planRunId"],
        "group": {"name": group, "unitIds": list(scope.unit_ids)},
        "triggeringUnitId": unit_id,
        "reason": reason,
        "diagnostics": diagnostics,
        "hashes": {"before": before, "after": after},
        "sourceCheckHash": source_check_hash,
        "changedFiles": changed,
        "model": {"provider": "opencode", "model": TRANSLATOR_MODEL, "reasoning": TRANSLATOR_REASONING},
        "singleSession": True,
        "automaticRetries": 0,
        "startedAt": started_at,
        "finishedAt": run_metadata["finishedAt"],
        "session": session,
        "recheckRequired": True,
    }
    _write_atomic(
        revision_directory / "translation-revision.json",
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return revision_directory, metadata
