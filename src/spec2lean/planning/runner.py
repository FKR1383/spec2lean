from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..constants import (
    PLAN_SCHEMA_VERSION,
    PLANNER_AGENT,
    PLANNER_MODEL_ID,
    PLANNER_REASONING_EFFORT,
)
from ..database import connect
from .graph import derive_graph
from .render import plan_statistics, render_markdown
from .submission import initialize_session_state, session_status
from .validation import normalize_candidate, validate_plan


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def _atomic_text(path: Path, value: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    os.replace(temporary, path)


def _index_identity(database: Path) -> tuple[str, str, str]:
    with connect(database, read_only=True) as connection:
        specification = connection.execute(
            "SELECT language, version FROM specifications"
        ).fetchone()
        build = connection.execute(
            "SELECT semantic_digest FROM builds WHERE status = 'COMPLETE' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    if specification is None or build is None or not build["semantic_digest"]:
        raise RuntimeError("Phase-1 database has no complete build identity")
    return specification["language"], specification["version"], build["semantic_digest"]


def _available_models(opencode: str, repository_root: Path) -> set[str]:
    result = subprocess.run(
        [opencode, "models"], cwd=repository_root, text=True, capture_output=True, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(f"cannot list OpenCode models: {result.stderr.strip() or result.stdout.strip()}")
    return {line.strip() for line in result.stdout.splitlines() if "/" in line}


def build_plan(
    *,
    database: Path,
    plan_directory: Path,
    repository_root: Path,
    opencode_executable: str = "opencode",
    expected_language: str | None = None,
    expected_version: str | None = None,
) -> dict[str, Any]:
    """Run exactly one Planner session; submission corrections stay inside it."""

    database = database.resolve()
    plan_directory = plan_directory.resolve()
    repository_root = repository_root.resolve()
    opencode = shutil.which(opencode_executable)
    if opencode is None:
        raise FileNotFoundError(f"OpenCode executable not found: {opencode_executable}")
    language, version, digest = _index_identity(database)
    if expected_language is not None and language.casefold() != expected_language.casefold():
        raise ValueError(
            f"selected database language {language!r} does not match {expected_language!r}"
        )
    if expected_version is not None and version != expected_version:
        raise ValueError(
            f"selected database version {version!r} does not match {expected_version!r}"
        )
    available = _available_models(opencode, repository_root)
    if PLANNER_MODEL_ID not in available:
        raise RuntimeError(
            f"required OpenCode model {PLANNER_MODEL_ID!r} is unavailable; no substitution was made"
        )

    version_result = subprocess.run(
        [opencode, "--version"], cwd=repository_root, text=True, capture_output=True, check=False
    )
    opencode_version = version_result.stdout.strip() if version_result.returncode == 0 else None
    plan_directory.mkdir(parents=True, exist_ok=True)
    session_nonce = uuid.uuid4().hex
    submission = plan_directory / f".planner-submission-{session_nonce}.json"
    session_state = plan_directory / f".planner-session-{session_nonce}.sqlite"
    initialize_session_state(session_state)
    started_at = _utc_now()
    started = time.monotonic()
    prompt = (
        f"Build the Phase-2 formalization plan for {language} {version}. "
        "Explore the authoritative Phase-1 index incrementally with the spec_* tools. "
        "Follow your role instructions and call submit_plan when the complete plan is ready. "
        "If submission validation returns diagnostics, correct them and resubmit within this same session."
    )
    command = [
        opencode,
        "run",
        "--agent",
        PLANNER_AGENT,
        "--model",
        PLANNER_MODEL_ID,
        "--variant",
        PLANNER_REASONING_EFFORT,
        "--format",
        "json",
        "--title",
        f"Spec2Lean plan {language} {version}",
        prompt,
    ]
    environment = os.environ.copy()
    environment.update(
        {
            "SPEC2LEAN_PLANNER_DATABASE": str(database),
            "SPEC2LEAN_PLANNER_SESSION_STATE": str(session_state),
            "SPEC2LEAN_PLANNER_SUBMISSION": str(submission),
            "SPEC2LEAN_PLANNER_LANGUAGE": language,
            "SPEC2LEAN_PLANNER_VERSION": version,
            "SPEC2LEAN_PLANNER_INDEX_DIGEST": digest,
        }
    )
    result = subprocess.run(
        command,
        cwd=repository_root,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    runtime = round(time.monotonic() - started, 3)
    finished_at = _utc_now()
    run: dict[str, Any] = {
        "runId": f"planner-run:{uuid.uuid4().hex}",
        "plannerAgent": PLANNER_AGENT,
        "opencodeVersion": opencode_version,
        "modelId": PLANNER_MODEL_ID,
        "reasoning": {
            "variant": PLANNER_REASONING_EFFORT,
            "reasoningEffort": PLANNER_REASONING_EFFORT,
        },
        "language": language,
        "version": version,
        "database": str(database),
        "indexSemanticDigest": digest,
        "startedAt": started_at,
        "finishedAt": finished_at,
        "runtimeSeconds": runtime,
        "opencodeExitCode": result.returncode,
        "opencodeOutputSha256": hashlib.sha256(result.stdout.encode("utf-8")).hexdigest(),
        "invocation": {
            "agent": PLANNER_AGENT,
            "model": PLANNER_MODEL_ID,
            "variant": PLANNER_REASONING_EFFORT,
            "format": "json",
        },
        "status": "FAIL",
        "openCodeSessions": 1,
    }

    try:
        current_session = session_status(session_state)
        run["submitPlanAttempts"] = current_session["submitPlanAttempts"]
        run["observedSourceNodes"] = current_session["observedSourceNodes"]
        if result.returncode != 0:
            diagnostic = result.stderr.strip() or result.stdout.strip()
            run["diagnostics"] = [
                {
                    "severity": "ERROR",
                    "code": "OPENCODE_FAILED",
                    "message": diagnostic[-20_000:] or "OpenCode exited unsuccessfully",
                    "context": {"exitCode": result.returncode},
                }
            ]
            _atomic_json(plan_directory / "planner-run.json", run)
            return run
        if not submission.is_file():
            run["diagnostics"] = current_session["lastDiagnostics"] or [
                {
                    "severity": "ERROR",
                    "code": "PLAN_NOT_ACCEPTED",
                    "message": "OpenCode Planner completed without an accepted submit_plan result",
                    "context": {"submitPlanAttempts": current_session["submitPlanAttempts"]},
                }
            ]
            _atomic_json(plan_directory / "planner-run.json", run)
            return run
        try:
            candidate = json.loads(submission.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            run["diagnostics"] = [
                {
                    "severity": "ERROR",
                    "code": "PLAN_JSON",
                    "message": f"submitted plan is not readable JSON: {exc}",
                    "context": {},
                }
            ]
            _atomic_json(plan_directory / "planner-run.json", run)
            return run

        plan = normalize_candidate(candidate)
        with connect(database, read_only=True) as connection:
            base_validation = validate_plan(
                plan,
                connection,
                expected_language=language,
                expected_version=version,
                expected_digest=digest,
                require_derived=False,
            )
            if base_validation["ok"]:
                plan.update(derive_graph(plan["units"], plan["dependencies"]))
                validation = validate_plan(
                    plan,
                    connection,
                    expected_language=language,
                    expected_version=version,
                    expected_digest=digest,
                    require_derived=True,
                )
            else:
                validation = base_validation
        run["validation"] = validation
        if not validation["ok"]:
            run["diagnostics"] = validation["issues"]
            _atomic_json(plan_directory / "planner-output.invalid.json", plan)
            _atomic_json(plan_directory / "planner-run.json", run)
            return run

        _atomic_json(plan_directory / "plan.json", plan)
        _atomic_text(plan_directory / "plan.md", render_markdown(plan))
        invalid_output = plan_directory / "planner-output.invalid.json"
        if invalid_output.exists():
            invalid_output.unlink()
        run["status"] = "PASS"
        run["planSchemaVersion"] = PLAN_SCHEMA_VERSION
        run["artifacts"] = {"plan": "plan.json", "rendering": "plan.md"}
        run["statistics"] = plan_statistics(plan)
        run["validation"] = validation
        _atomic_json(plan_directory / "planner-run.json", run)
        return run
    finally:
        if submission.exists():
            submission.unlink()
        for state_artifact in (
            session_state,
            session_state.with_name(session_state.name + "-wal"),
            session_state.with_name(session_state.name + "-shm"),
        ):
            if state_artifact.exists():
                state_artifact.unlink()
