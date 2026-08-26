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
from .models import TRANSLATOR_AGENT, TRANSLATOR_MODEL, TRANSLATOR_REASONING, TranslationScope
from .revision_prompt import build_translation_revision_prompt
from .runner import _session_id, opencode_config, require_translator_model
from .store import load_translation, shared_lean_sources
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
    scope = TranslationScope.from_dict(context["scope"])
    prompt = build_translation_revision_prompt(
        scope, context["semantics"], context["leanSource"], context["translationManifest"],
        context["diagnostics"], context["reason"], context["sharedLeanSources"],
    )
    with tempfile.TemporaryDirectory(prefix="spec2lean-translation-revision-") as temporary_name:
        temporary = Path(temporary_name)
        scope_path, semantics_path = temporary / "translation-scope.json", temporary / "semantics.json"
        submission_path = temporary / "submission.json"
        scope_path.write_text(json.dumps(scope.to_dict(), ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        semantics_path.write_text(json.dumps(context["semantics"], ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        config = opencode_config(scope_path, semantics_path, submission_path)
        command = [
            executable, "run", "--pure", "--print-logs", "--log-level", "ERROR",
            "--format", "json", "--agent", TRANSLATOR_AGENT, "--model", TRANSLATOR_MODEL,
            "--variant", TRANSLATOR_REASONING, "--title",
            f"{scope.plan_run_id}:{scope.unit_id}:revise-translation", prompt,
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
            "candidate": candidate, "error": error,
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
    timeout_seconds: int = 1800,
    source_check_hash: str | None = None,
    session_runner: SessionRunner = run_translation_revision_session,
    now: Callable[[], str] = utc_now,
) -> tuple[Path, dict[str, Any]]:
    if reason not in {"COVERAGE_FAILURE", "SEMANTICS_REVISED"}:
        raise ValueError(f"unsupported translation revision reason: {reason}")
    if not diagnostics:
        raise ValueError("translation revision requires concrete upstream diagnostics")
    semantic_directory, semantics = load_semantics(semantics_root, plan, unit_id)
    directory, source, manifest, _ = load_translation(translations_root, plan, unit_id)
    if source_check_hash is not None:
        for path in directory.glob("revisions/*/translation-revision.json"):
            recorded = json.loads(path.read_text(encoding="utf-8"))
            if recorded.get("sourceCheckHash") == source_check_hash:
                raise FileExistsError(f"Phase-6 check was already consumed by translation revision: {path.parent}")
    started_at = now()
    scope = TranslationScope.from_inputs(
        plan, semantics, unit_id, created_at=str(manifest.get("createdAt") or started_at)
    )
    before = {
        "Unit.lean": _file_hash(directory / "Unit.lean"),
        "translation-manifest.json": _file_hash(directory / "translation-manifest.json"),
        "translator-run.json": _file_hash(directory / "translator-run.json"),
    }
    revision_id = stable_id(
        "translation-revision", plan["planRunId"], unit_id,
        before["Unit.lean"], before["translation-manifest.json"], _hash_json(diagnostics), reason,
        source_check_hash or "UNBOUND",
    )
    revision_directory = directory / "revisions" / revision_id
    if revision_directory.exists():
        raise FileExistsError(f"translation revision was already recorded: {revision_directory}")
    shared = shared_lean_sources(translations_root, plan)
    context = {
        "scope": scope.to_dict(), "semantics": semantics, "leanSource": source,
        "translationManifest": manifest, "diagnostics": diagnostics, "reason": reason,
        "sharedLeanSources": shared, "translationDirectory": str(directory),
    }
    result = session_runner(context, timeout_seconds=timeout_seconds)
    if result.get("error"):
        raise RuntimeError(str(result["error"]))
    candidate = result.get("candidate")
    if not isinstance(candidate, dict):
        raise ValueError("translation revision did not submit a candidate")
    candidate_source = candidate.get("leanSource")
    candidate_manifest = candidate.get("manifest")
    validation = validate_manifest(plan, semantics, candidate_source, candidate_manifest)
    if validation:
        raise ValueError("translation revision failed deterministic validation: " + "; ".join(item["message"] for item in validation))
    new_source = str(candidate_source).rstrip() + "\n"
    new_manifest = json.dumps(candidate_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    session = result.get("session") or {}
    run_metadata = {
        "schemaVersion": 1, "phase": "LLM_TRANSLATOR", "planRunId": scope.plan_run_id,
        "unitId": scope.unit_id, "translationRunId": scope.translation_run_id,
        "translator": "opencode", "model": TRANSLATOR_MODEL, "reasoning": TRANSLATOR_REASONING,
        "singleSession": True, "automaticRetries": 0, "startedAt": scope.created_at,
        "finishedAt": now(), "semanticsArtifact": str(semantic_directory / "semantics.json"),
        "semanticsArtifactHash": scope.semantics_artifact_hash,
        "inputBoundary": "PHASE_4_SEMANTIC_ARTIFACT_ONLY", "sharedLeanFiles": [item["path"] for item in shared],
        "targetLanguage": "Lean", "targetVersion": "4", "command": session.get("command", []),
        "exitCode": 0, "sessionId": session.get("sessionId"), "outcome": "SUCCESS", "error": None,
        "stdout": session.get("stdout", ""), "stderr": session.get("stderr", ""),
        "revisionRunId": revision_id, "revisionReason": reason, "revisionStartedAt": started_at,
    }
    old_text = {
        "Unit.lean": (directory / "Unit.lean").read_text(encoding="utf-8"),
        "translation-manifest.json": (directory / "translation-manifest.json").read_text(encoding="utf-8"),
        "translator-run.json": (directory / "translator-run.json").read_text(encoding="utf-8"),
    }
    revision_directory.mkdir(parents=True)
    for name, content in old_text.items():
        _write_atomic(revision_directory / f"before-{name}", content)
    try:
        _write_atomic(directory / "Unit.lean", new_source)
        _write_atomic(directory / "translation-manifest.json", new_manifest)
        _write_atomic(directory / "translator-run.json", json.dumps(run_metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        published = validate_published(plan, semantics, directory)
        if published:
            raise ValueError("stored translation revision failed validation: " + "; ".join(item["message"] for item in published))
    except Exception:
        for name, content in old_text.items():
            _write_atomic(directory / name, content)
        raise
    after = {name: _file_hash(directory / name) for name in before}
    changed = [name for name in before if before[name] != after[name]]
    if not any(name in changed for name in ("Unit.lean", "translation-manifest.json")):
        for name, content in old_text.items():
            _write_atomic(directory / name, content)
        raise ValueError("translation revision made no translation or manifest change")
    metadata = {
        "schemaVersion": 1, "phase": "LLM_TRANSLATOR_REVISION", "revisionRunId": revision_id,
        "planRunId": plan["planRunId"], "unitId": unit_id, "reason": reason,
        "diagnostics": diagnostics, "hashes": {"before": before, "after": after},
        "sourceCheckHash": source_check_hash,
        "changedFiles": changed, "model": {"provider": "opencode", "model": TRANSLATOR_MODEL, "reasoning": TRANSLATOR_REASONING},
        "singleSession": True, "automaticRetries": 0, "startedAt": started_at,
        "finishedAt": run_metadata["finishedAt"], "session": session, "recheckRequired": True,
    }
    _write_atomic(revision_directory / "translation-revision.json", json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return revision_directory, metadata
