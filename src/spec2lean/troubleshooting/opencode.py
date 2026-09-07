from __future__ import annotations

from ..runtime import (
    is_rust, run_session, runtime_executable, runtime_name,
    runtime_label, session_command, session_error,
)

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

from ..planning.runner import installed_openai_models
from ..translation.runner import _session_id
from .models import TROUBLESHOOTER_AGENT, TROUBLESHOOTER_MODEL, TROUBLESHOOTER_REASONING
from .prompt import build_troubleshooter_prompt


def require_troubleshooter_model(executable: str) -> None:
    if is_rust(executable):
        return
    models = installed_openai_models(executable)
    if TROUBLESHOOTER_MODEL in models:
        return
    available = ", ".join(sorted(models)) or "<none>"
    raise RuntimeError(
        f"required OpenCode Troubleshooter model is unavailable: {TROUBLESHOOTER_MODEL}; "
        f"installed OpenAI model IDs: {available}. No model was substituted and no "
        "Troubleshooter session was started"
    )


def opencode_config(context_path: Path, submission_path: Path) -> dict[str, Any]:
    disabled = {
        name: False
        for name in (
            "bash", "edit", "write", "read", "glob", "grep", "list", "task",
            "webfetch", "websearch", "todowrite", "skill", "question", "lsp",
        )
    }
    return {
        "default_agent": TROUBLESHOOTER_AGENT,
        "share": "disabled",
        "autoupdate": False,
        "formatter": False,
        "lsp": False,
        "mcp": {"troubleshooting": {
            "type": "local",
            "command": [
                sys.executable,
                "-m",
                "spec2lean.troubleshooting.mcp",
                "--context",
                str(context_path),
                "--submission",
                str(submission_path),
            ],
            "enabled": True,
            "timeout": 15_000,
        }},
        "agent": {TROUBLESHOOTER_AGENT: {
            "description": "Compiler-diagnostic-bounded Lean 4 translation troubleshooter",
            "mode": "primary",
            "model": TROUBLESHOOTER_MODEL,
            "variant": TROUBLESHOOTER_REASONING,
            "steps": 20,
            "tools": disabled,
            "permission": {"*": "deny", "troubleshooting_*": "allow"},
        }},
    }


def _version(
    executable: str,
    run_command: Callable[..., subprocess.CompletedProcess[str]],
) -> str:
    completed = run_command(
        [executable, "--version"], text=True, capture_output=True, timeout=60, check=False
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or f"status {completed.returncode}"
        raise RuntimeError(f"could not query the OpenCode version: {detail}")
    output = (completed.stdout or completed.stderr).strip()
    if not output:
        raise RuntimeError("OpenCode version command returned no version")
    return output.splitlines()[0]


def run_opencode_repair(
    context: dict[str, Any],
    *,
    timeout_seconds: int = 1800,
    run_command: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    executable = runtime_executable()
    if executable is None:
        raise RuntimeError("OpenCode executable is not installed or not on PATH")
    require_troubleshooter_model(executable)
    version = _version(executable, run_command)
    prompt = build_troubleshooter_prompt()
    with tempfile.TemporaryDirectory(prefix="spec2lean-troubleshooting-") as temporary_name:
        temporary = Path(temporary_name)
        context_path = temporary / "repair-context.json"
        submission_path = temporary / "submission.json"
        context_path.write_text(
            json.dumps(context, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
        )
        config = opencode_config(context_path, submission_path)
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
            TROUBLESHOOTER_AGENT,
            "--model",
            TROUBLESHOOTER_MODEL,
            "--variant",
            TROUBLESHOOTER_REASONING,
            "--title",
            f"{context['plan']['planRunId']}:{context['unit']['unitId']}:troubleshoot",
            prompt,
        ]
        environment = os.environ.copy()
        environment["OPENCODE_CONFIG_CONTENT"] = json.dumps(config, separators=(",", ":"))
        config_dir = temporary / "opencode-config"
        home_dir = temporary / "opencode-home"
        config_dir.mkdir()
        home_dir.mkdir()
        environment["OPENCODE_CONFIG_DIR"] = str(config_dir)
        environment["OPENCODE_TEST_HOME"] = str(home_dir)
        environment["OPENCODE_DISABLE_PROJECT_CONFIG"] = "1"
        environment["OPENCODE_DISABLE_EXTERNAL_SKILLS"] = "1"
        environment["OPENCODE_DISABLE_CLAUDE_CODE_SKILLS"] = "1"
        try:
            completed = run_session(
                command, run_command=run_command,
                cwd=context["translationDirectory"],
                env=environment,
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            completed = subprocess.CompletedProcess(command, 124, exc.stdout or "", exc.stderr or "")
        error: str | None = None
        if completed.returncode == 124:
            error = f"{runtime_label(executable)} Troubleshooter session timed out after {timeout_seconds} seconds"
        elif completed.returncode != 0:
            error = session_error(executable, "Troubleshooter", completed)
        elif not submission_path.is_file():
            error = f"{runtime_label(executable)} Troubleshooter finished without a valid submit_repair call"
        submission: dict[str, Any] | None = None
        if submission_path.is_file():
            try:
                submission = json.loads(submission_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                error = error or f"{runtime_label(executable)} Troubleshooter submission is invalid JSON"
        return {
            "submission": submission,
            "error": error,
            "session": {
                "provider": runtime_name(),
                "model": TROUBLESHOOTER_MODEL,
                "reasoning": TROUBLESHOOTER_REASONING,
                "opencodeVersion": version,
                "singleSession": True,
                "automaticRetries": 0,
                "command": session_command(command, "<troubleshooter-prompt>"),
                "exitCode": completed.returncode,
                "sessionId": _session_id(completed.stdout),
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            },
        }
