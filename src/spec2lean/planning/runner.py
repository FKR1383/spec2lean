from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ..database import connect
from ..util import stable_id
from .models import PlanningRequest
from .prompt import build_planner_prompt
from .render import render_markdown
from .scope import Phase1Query, ScopeResolver
from .validation import build_validated_plan


PLANNER_MODEL = "openai/gpt-5.6-sol"
PLANNER_REASONING = "medium"
PLANNER_AGENT = "spec2lean-planner"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def source_database_digest(connection: Any) -> str:
    row = connection.execute(
        "SELECT semantic_digest FROM builds WHERE status = 'COMPLETE' ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    if row is None or not row["semantic_digest"]:
        raise ValueError("Phase 1 database has no completed semantic digest")
    return str(row["semantic_digest"])


def installed_openai_models(executable: str) -> set[str]:
    try:
        completed = subprocess.run(
            [executable, "models", "openai"],
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"could not query the OpenCode model catalog: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or f"status {completed.returncode}"
        raise RuntimeError(f"could not query the OpenCode model catalog: {detail}")
    ansi = re.compile(r"\x1b\[[0-9;]*m")
    return {
        ansi.sub("", line).strip()
        for line in completed.stdout.splitlines()
        if ansi.sub("", line).strip()
    }


def require_planner_model(executable: str) -> None:
    models = installed_openai_models(executable)
    if PLANNER_MODEL in models:
        return
    available = ", ".join(sorted(models)) or "<none>"
    raise RuntimeError(
        f"required OpenCode Planner model is unavailable: {PLANNER_MODEL}; "
        f"installed OpenAI model IDs: {available}. No model was substituted and no Planner session was started"
    )


def opencode_config(database: Path, scope_path: Path, submission_path: Path) -> dict[str, Any]:
    disabled = {
        name: False
        for name in (
            "bash", "edit", "write", "read", "glob", "grep", "list", "task",
            "webfetch", "websearch", "todowrite", "skill", "question", "lsp",
        )
    }
    return {
        "default_agent": PLANNER_AGENT,
        "share": "disabled",
        "autoupdate": False,
        "formatter": False,
        "lsp": False,
        "mcp": {
            "specdb": {
                "type": "local",
                "command": [
                    sys.executable,
                    "-m",
                    "spec2lean.planning.mcp",
                    "--database",
                    str(database),
                    "--scope",
                    str(scope_path),
                    "--submission",
                    str(submission_path),
                ],
                "enabled": True,
                "timeout": 15_000,
            }
        },
        "agent": {
            PLANNER_AGENT: {
                "description": "Request-scoped specification dependency planner",
                "mode": "primary",
                "model": PLANNER_MODEL,
                "variant": PLANNER_REASONING,
                "steps": 80,
                "tools": disabled,
                "permission": {"*": "deny", "specdb_*": "allow"},
            }
        },
    }


def _extract_session_id(stdout: str) -> str | None:
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        for key in ("sessionID", "sessionId", "session_id"):
            if isinstance(event.get(key), str):
                return event[key]
        part = event.get("part")
        if isinstance(part, dict):
            for key in ("sessionID", "sessionId", "session_id"):
                if isinstance(part.get(key), str):
                    return part[key]
    return None


def build_plan(
    database: Path,
    plans_root: Path,
    request: PlanningRequest,
    *,
    timeout_seconds: int = 1800,
    run_command: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> Path:
    database = database.resolve()
    with connect(database, read_only=True) as connection:
        query = Phase1Query(connection)
        scope = ScopeResolver(connection).resolve(request)
        digest = source_database_digest(connection)
        prompt = build_planner_prompt(query, scope)

    executable = shutil.which("opencode")
    if executable is None:
        raise RuntimeError("OpenCode executable is not installed or not on PATH")
    require_planner_model(executable)

    started_at = utc_now()
    plan_run_id = stable_id("plan", request.language.casefold(), request.version, digest, started_at)
    run_directory = plans_root.resolve() / request.language.casefold() / request.version / plan_run_id
    run_directory.mkdir(parents=True, exist_ok=False)
    (run_directory / "request.json").write_text(
        json.dumps(request.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with tempfile.TemporaryDirectory(prefix="spec2lean-plan-") as temporary_name:
        temporary = Path(temporary_name)
        scope_path = temporary / "resolved-scope.json"
        submission_path = temporary / "submission.json"
        scope_path.write_text(
            json.dumps(scope.to_dict(), ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
        )
        config = opencode_config(database, scope_path, submission_path)
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
            PLANNER_AGENT,
            "--model",
            PLANNER_MODEL,
            "--variant",
            PLANNER_REASONING,
            "--title",
            plan_run_id,
            prompt,
        ]
        environment = os.environ.copy()
        environment["OPENCODE_CONFIG_CONTENT"] = json.dumps(config, separators=(",", ":"))
        isolated_config = temporary / "opencode-config"
        isolated_config.mkdir()
        isolated_home = temporary / "opencode-home"
        isolated_home.mkdir()
        environment["OPENCODE_CONFIG_DIR"] = str(isolated_config)
        environment["OPENCODE_TEST_HOME"] = str(isolated_home)
        environment["OPENCODE_DISABLE_PROJECT_CONFIG"] = "1"
        environment["OPENCODE_DISABLE_EXTERNAL_SKILLS"] = "1"
        environment["OPENCODE_DISABLE_CLAUDE_CODE_SKILLS"] = "1"
        outcome = "FAILED"
        error: str | None = None
        try:
            completed = run_command(
                command,
                cwd=str(run_directory),
                env=environment,
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            completed = subprocess.CompletedProcess(command, 124, exc.stdout or "", exc.stderr or "")
            error = f"OpenCode Planner session timed out after {timeout_seconds} seconds"

        if error is None and completed.returncode != 0:
            error = f"OpenCode Planner exited with status {completed.returncode}"
        if error is None and not submission_path.is_file():
            error = "OpenCode Planner session finished without a valid submit_plan call"
        if error is None:
            submission = json.loads(submission_path.read_text(encoding="utf-8"))
            with connect(database, read_only=True) as connection:
                plan = build_validated_plan(
                    Phase1Query(connection),
                    scope,
                    submission,
                    language=request.language,
                    version=request.version,
                    plan_run_id=plan_run_id,
                    source_database_digest=digest,
                )
            (run_directory / "plan.json").write_text(
                json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            (run_directory / "plan.md").write_text(render_markdown(plan), encoding="utf-8")
            outcome = "VALID"

        metadata = {
            "schemaVersion": 1,
            "planRunId": plan_run_id,
            "planner": "opencode",
            "model": PLANNER_MODEL,
            "reasoning": PLANNER_REASONING,
            "singleSession": True,
            "startedAt": started_at,
            "finishedAt": utc_now(),
            "sourceDatabase": str(database),
            "sourceDatabaseDigest": digest,
            "command": command[:-1] + ["<planner-prompt>"],
            "exitCode": completed.returncode,
            "sessionId": _extract_session_id(completed.stdout),
            "outcome": outcome,
            "error": error,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
        (run_directory / "planner-run.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if error is not None:
            raise RuntimeError(f"{error}; run artifact: {run_directory}")
    return run_directory
