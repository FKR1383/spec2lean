from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ..evidence.store import load_unit_bundle
from ..util import canonical_json, stable_id
from .models import EXTRACTOR_AGENT, EXTRACTOR_MODEL, EXTRACTOR_REASONING, SemanticScope
from .render import render_markdown
from .revision_prompt import build_semantic_revision_prompt
from .runner import _session_id, opencode_config, require_extractor_model
from .store import load_semantics
from .validation import validate_artifact


SessionRunner = Callable[..., dict[str, Any]]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _hash_json(value: Any) -> str:
    import hashlib
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


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


def run_semantic_revision_session(
    context: dict[str, Any], *, timeout_seconds: int = 1800,
    run_command: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    executable = shutil.which("opencode")
    if executable is None:
        raise RuntimeError("OpenCode executable is not installed or not on PATH")
    require_extractor_model(executable)
    scope = SemanticScope.from_dict(context["scope"])
    prompt = build_semantic_revision_prompt(
        scope, context["evidence"], context["currentSemantics"], context["diagnostics"]
    )
    with tempfile.TemporaryDirectory(prefix="spec2lean-semantic-revision-") as temporary_name:
        temporary = Path(temporary_name)
        scope_path = temporary / "semantic-scope.json"
        evidence_path = temporary / "evidence.json"
        submission_path = temporary / "submission.json"
        scope_path.write_text(json.dumps(scope.to_dict(), ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        evidence_path.write_text(json.dumps(context["evidence"], ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        config = opencode_config(scope_path, evidence_path, submission_path)
        command = [
            executable, "run", "--pure", "--print-logs", "--log-level", "ERROR",
            "--format", "json", "--agent", EXTRACTOR_AGENT, "--model", EXTRACTOR_MODEL,
            "--variant", EXTRACTOR_REASONING, "--title",
            f"{scope.plan_run_id}:{scope.unit_id}:revise-semantics", prompt,
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
                command, cwd=context["semanticDirectory"], env=environment, text=True,
                capture_output=True, timeout=timeout_seconds, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            completed = subprocess.CompletedProcess(command, 124, exc.stdout or "", exc.stderr or "")
        error = None
        if completed.returncode == 124:
            error = f"OpenCode Semantic Revision session timed out after {timeout_seconds} seconds"
        elif completed.returncode != 0:
            error = f"OpenCode Semantic Revision exited with status {completed.returncode}"
        elif not submission_path.is_file():
            error = "OpenCode Semantic Revision finished without a valid submit_semantics call"
        artifact = None
        if submission_path.is_file():
            try:
                artifact = json.loads(submission_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                error = error or "Semantic Revision submission is invalid JSON"
        return {
            "artifact": artifact,
            "error": error,
            "session": {
                "provider": "opencode", "model": EXTRACTOR_MODEL,
                "reasoning": EXTRACTOR_REASONING, "singleSession": True,
                "automaticRetries": 0, "command": command[:-1] + ["<semantic-revision-prompt>"],
                "exitCode": completed.returncode, "sessionId": _session_id(completed.stdout),
                "stdout": completed.stdout, "stderr": completed.stderr,
            },
        }


def revise_semantics(
    plan: dict[str, Any], *, evidence_root: Path, semantics_root: Path, unit_id: str,
    diagnostics: list[dict[str, Any]], timeout_seconds: int = 1800,
    source_check_hash: str | None = None,
    session_runner: SessionRunner = run_semantic_revision_session,
    now: Callable[[], str] = utc_now,
) -> tuple[Path, dict[str, Any]]:
    if not diagnostics:
        raise ValueError("semantic revision requires concrete Phase-6 traceability diagnostics")
    _, bundle = load_unit_bundle(evidence_root, plan, unit_id)
    directory, current = load_semantics(semantics_root, plan, unit_id)
    if source_check_hash is not None:
        for path in directory.glob("revisions/*/semantic-revision.json"):
            recorded = json.loads(path.read_text(encoding="utf-8"))
            if recorded.get("sourceCheckHash") == source_check_hash:
                raise FileExistsError(f"Phase-6 check was already consumed by semantic revision: {path.parent}")
    started_at = now()
    scope = SemanticScope.from_inputs(plan, bundle, unit_id, created_at=started_at)
    before_hash = _hash_json(current)
    revision_id = stable_id(
        "semantic-revision", plan["planRunId"], unit_id, before_hash,
        _hash_json(diagnostics), source_check_hash or "UNBOUND",
    )
    revision_directory = directory / "revisions" / revision_id
    if revision_directory.exists():
        raise FileExistsError(f"semantic revision was already recorded: {revision_directory}")
    context = {
        "scope": scope.to_dict(), "evidence": bundle, "currentSemantics": current,
        "diagnostics": diagnostics, "semanticDirectory": str(directory),
    }
    result = session_runner(context, timeout_seconds=timeout_seconds)
    if result.get("error"):
        raise RuntimeError(str(result["error"]))
    artifact = result.get("artifact")
    validation = validate_artifact(plan, bundle, artifact)
    if validation:
        raise ValueError("semantic revision failed deterministic validation: " + "; ".join(item["message"] for item in validation))
    if not isinstance(artifact, dict) or artifact.get("outcome") != "SUCCESS":
        raise RuntimeError("semantic revision did not produce successful semantics")
    after_hash = _hash_json(artifact)
    revision_directory.mkdir(parents=True)
    _write_atomic(revision_directory / "before-semantics.json", json.dumps(current, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    _write_atomic(revision_directory / "after-semantics.json", json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    metadata = {
        "schemaVersion": 1, "phase": "SEMANTIC_EXTRACTOR_REVISION",
        "revisionRunId": revision_id, "planRunId": plan["planRunId"], "unitId": unit_id,
        "reason": "TRACEABILITY_FAILURE", "diagnostics": diagnostics,
        "sourceCheckHash": source_check_hash,
        "beforeHash": before_hash, "afterHash": after_hash,
        "model": {"provider": "opencode", "model": EXTRACTOR_MODEL, "reasoning": EXTRACTOR_REASONING},
        "singleSession": True, "automaticRetries": 0,
        "startedAt": started_at, "finishedAt": now(), "session": result.get("session"),
        "changedFiles": ["semantics.json", "semantics.md"], "recheckRequired": True,
    }
    _write_atomic(revision_directory / "semantic-revision.json", json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    semantics_path = directory / "semantics.json"
    markdown_path = directory / "semantics.md"
    old_semantics = semantics_path.read_text(encoding="utf-8")
    old_markdown = markdown_path.read_text(encoding="utf-8") if markdown_path.is_file() else None
    try:
        _write_atomic(semantics_path, json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        _write_atomic(markdown_path, render_markdown(artifact))
    except Exception:
        _write_atomic(semantics_path, old_semantics)
        if old_markdown is not None:
            _write_atomic(markdown_path, old_markdown)
        raise
    return revision_directory, metadata
