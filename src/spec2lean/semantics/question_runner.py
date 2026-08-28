from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ..database import connect
from ..evidence.query import EvidenceQuery
from ..evidence.validation import validate_bundle
from ..planning.runner import installed_openai_models
from .question_prompt import build_open_question_prompt
from .question_render import render_open_questions
from .questions import (
    QUESTION_AGENT,
    QUESTION_MODEL,
    QUESTION_REASONING,
    OpenQuestionScope,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _session_id(stdout: str) -> str | None:
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        for candidate in (event, event.get("part")):
            if not isinstance(candidate, dict):
                continue
            for key in ("sessionID", "sessionId", "session_id"):
                if isinstance(candidate.get(key), str):
                    return candidate[key]
    return None


def require_question_model(executable: str) -> None:
    models = installed_openai_models(executable)
    if QUESTION_MODEL in models:
        return
    available = ", ".join(sorted(models)) or "<none>"
    raise RuntimeError(
        f"required OpenCode Open Question Handler model is unavailable: {QUESTION_MODEL}; "
        f"installed OpenAI model IDs: {available}. No model was substituted"
    )


def opencode_config(
    database: Path,
    scope_path: Path,
    evidence_path: Path,
    submission_path: Path,
    trace_path: Path,
    runtime_command: tuple[str, ...],
) -> dict[str, Any]:
    tools = {
        name: False
        for name in (
            "bash", "edit", "write", "read", "glob", "grep", "list", "task",
            "todowrite", "skill", "question", "lsp",
        )
    }
    tools.update({"webfetch": True, "websearch": True})
    command = [
        sys.executable,
        "-m",
        "spec2lean.semantics.question_mcp",
        "--database",
        str(database),
        "--scope",
        str(scope_path),
        "--evidence",
        str(evidence_path),
        "--submission",
        str(submission_path),
        "--trace",
        str(trace_path),
        "--runtime-command-json",
        json.dumps(list(runtime_command), separators=(",", ":")),
    ]
    return {
        "default_agent": QUESTION_AGENT,
        "share": "disabled",
        "autoupdate": False,
        "formatter": False,
        "lsp": False,
        # Runtime probes are bounded to 60 seconds by the MCP server, so the
        # transport timeout must be longer than that bound.
        "mcp": {"open_questions": {"type": "local", "command": command, "enabled": True, "timeout": 75_000}},
        "agent": {
            QUESTION_AGENT: {
                "description": "Canonical-database-first semantic open-question handler",
                "mode": "primary",
                "model": QUESTION_MODEL,
                "variant": QUESTION_REASONING,
                "steps": 120,
                "tools": tools,
                "permission": {
                    "*": "deny",
                    "open_questions_*": "allow",
                    "websearch": "allow",
                    "webfetch": "allow",
                },
            }
        },
    }


def handle_open_questions(
    database: Path,
    plan: dict[str, Any],
    bundle: dict[str, Any],
    failure: dict[str, Any],
    output: Path,
    *,
    timeout_seconds: int = 1800,
    runtime_command: tuple[str, ...] = (),
    run_command: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[dict[str, Any], dict[str, Any]]:
    database = database.resolve()
    output.mkdir(parents=True, exist_ok=False)
    started_at = utc_now()
    scope = OpenQuestionScope.from_inputs(plan, bundle, failure, created_at=started_at)
    with connect(database, read_only=True) as connection:
        if EvidenceQuery(connection).source_database_digest() != scope.source_database_digest:
            raise ValueError("open-question handler database does not match the Phase-2 plan")
    executable = shutil.which("opencode")
    if executable is None:
        raise RuntimeError("OpenCode executable is not installed or not on PATH")
    require_question_model(executable)

    with tempfile.TemporaryDirectory(prefix="spec2lean-open-questions-") as temporary_name:
        temporary = Path(temporary_name)
        scope_path = temporary / "scope.json"
        evidence_path = temporary / "evidence.json"
        submission_path = temporary / "submission.json"
        trace_path = temporary / "trace.json"
        scope_path.write_text(json.dumps(scope.to_dict(), ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        evidence_path.write_text(json.dumps(bundle, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        config = opencode_config(
            database, scope_path, evidence_path, submission_path, trace_path, runtime_command
        )
        prompt = build_open_question_prompt(
            scope, bundle, failure, runtime_available=bool(runtime_command)
        )
        command = [
            executable,
            "run",
            "--pure",
            "--print-logs",
            "--log-level",
            "ERROR",
            "--format",
            "json",
            "--agent",
            QUESTION_AGENT,
            "--model",
            QUESTION_MODEL,
            "--variant",
            QUESTION_REASONING,
            "--title",
            f"{scope.plan_run_id}:{scope.unit_id}:open-questions",
            prompt,
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
        error: str | None = None
        try:
            completed = run_command(
                command,
                cwd=str(output),
                env=environment,
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            completed = subprocess.CompletedProcess(command, 124, exc.stdout or "", exc.stderr or "")
            error = f"OpenCode Open Question Handler timed out after {timeout_seconds} seconds"
        if error is None and completed.returncode != 0:
            error = f"OpenCode Open Question Handler exited with status {completed.returncode}"
        if error is None and not submission_path.is_file():
            error = "OpenCode Open Question Handler finished without a valid submit_questions call"

        payload: dict[str, Any] | None = None
        if submission_path.is_file():
            try:
                payload = json.loads(submission_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                error = error or "Open Question Handler submission is invalid JSON"
        artifact = payload.get("artifact") if isinstance(payload, dict) else None
        augmented = payload.get("augmentedBundle") if isinstance(payload, dict) else None
        if error is None and (not isinstance(artifact, dict) or not isinstance(augmented, dict)):
            error = "Open Question Handler submission is incomplete"
        if error is None:
            with connect(database, read_only=True) as connection:
                diagnostics = validate_bundle(EvidenceQuery(connection), plan, augmented)
            if diagnostics:
                error = "augmented evidence failed deterministic validation: " + "; ".join(
                    item["message"] for item in diagnostics
                )

        trace: dict[str, Any] = {}
        if trace_path.is_file():
            try:
                trace = json.loads(trace_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                error = error or "Open Question Handler trace is invalid"
        metadata = {
            "schemaVersion": 1,
            "phase": "OPEN_QUESTION_HANDLER",
            "planRunId": scope.plan_run_id,
            "unitId": scope.unit_id,
            "runId": scope.run_id,
            "model": QUESTION_MODEL,
            "reasoning": QUESTION_REASONING,
            "singleSession": True,
            "databaseFirst": True,
            "startedAt": started_at,
            "finishedAt": utc_now(),
            "sourceDatabase": str(database),
            "sourceDatabaseDigest": scope.source_database_digest,
            "inputEvidenceBundleHash": scope.evidence_bundle_hash,
            "inputSemanticRunId": scope.semantic_run_id,
            "runtimeProbeConfigured": bool(runtime_command),
            "command": command[:-1] + ["<open-question-prompt>"],
            "exitCode": completed.returncode,
            "sessionId": _session_id(completed.stdout),
            "outcome": artifact.get("outcome") if isinstance(artifact, dict) and error is None else "FAILED",
            "error": error,
            "trace": trace,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
        (output / "handler-run.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if isinstance(artifact, dict) and error is None:
            (output / "open-questions.json").write_text(
                json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            (output / "open-questions.md").write_text(
                render_open_questions(artifact), encoding="utf-8"
            )
            (output / "before-evidence.json").write_text(
                json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            (output / "after-evidence.json").write_text(
                json.dumps(augmented, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        if error is not None:
            raise RuntimeError(f"{error}; run artifact: {output}")
        assert isinstance(artifact, dict) and isinstance(augmented, dict)
        return artifact, augmented
