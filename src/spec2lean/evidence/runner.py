from __future__ import annotations

from ..runtime import is_rust, run_session, runtime_executable, runtime_name

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ..database import connect
from ..embeddings import index_mode
from ..planning.runner import installed_openai_models
from .models import EvidenceScope
from .prompt import build_retriever_prompt
from .query import EvidenceQuery
from .render import render_markdown
from .validation import validate_bundle


RETRIEVER_MODEL = "openai/gpt-5.6-sol"
RETRIEVER_REASONING = "medium"
RETRIEVER_AGENT = "spec2lean-evidence-retriever"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def require_retriever_model(executable: str) -> None:
    if is_rust(executable):
        return
    models = installed_openai_models(executable)
    if RETRIEVER_MODEL in models:
        return
    available = ", ".join(sorted(models)) or "<none>"
    raise RuntimeError(
        f"required OpenCode Evidence Retriever model is unavailable: {RETRIEVER_MODEL}; "
        f"installed OpenAI model IDs: {available}. No model was substituted and no retriever session was started"
    )


def opencode_config(
    database: Path, scope_path: Path, submission_path: Path, trace_path: Path
) -> dict[str, Any]:
    disabled = {
        name: False
        for name in (
            "bash", "edit", "write", "read", "glob", "grep", "list", "task",
            "webfetch", "websearch", "todowrite", "skill", "question", "lsp",
        )
    }
    return {
        "default_agent": RETRIEVER_AGENT,
        "share": "disabled",
        "autoupdate": False,
        "formatter": False,
        "lsp": False,
        "mcp": {
            "specdb": {
                "type": "local",
                "command": [
                    sys.executable, "-m", "spec2lean.evidence.mcp",
                    "--database", str(database),
                    "--scope", str(scope_path),
                    "--submission", str(submission_path),
                    "--trace", str(trace_path),
                ],
                "enabled": True,
                "timeout": 15_000,
            }
        },
        "agent": {
            RETRIEVER_AGENT: {
                "description": "Request-scoped exact specification evidence selector",
                "mode": "primary",
                "model": RETRIEVER_MODEL,
                "variant": RETRIEVER_REASONING,
                "steps": 100,
                "tools": disabled,
                "permission": {"*": "deny", "specdb_*": "allow"},
            }
        },
    }


def _session_id(stdout: str) -> str | None:
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        candidates = [event]
        if isinstance(event.get("part"), dict):
            candidates.append(event["part"])
        for candidate in candidates:
            for key in ("sessionID", "sessionId", "session_id"):
                if isinstance(candidate.get(key), str):
                    return candidate[key]
    return None


def unit_directory_name(unit: dict[str, Any]) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(unit["name"]).casefold()).strip("-") or "unit"
    return f"{slug}-{str(unit['unitId']).split(':', 1)[-1][:8]}"


def _run_unit(
    database: Path,
    plan: dict[str, Any],
    scope: EvidenceScope,
    run_root: Path,
    executable: str,
    *,
    timeout_seconds: int,
    run_command: Callable[..., subprocess.CompletedProcess[str]],
) -> Path:
    unit_directory = run_root / unit_directory_name(scope.unit)
    unit_directory.mkdir(parents=True, exist_ok=False)
    started_at = utc_now()
    with connect(database, read_only=True) as connection:
        prompt = build_retriever_prompt(EvidenceQuery(connection), scope)

    with tempfile.TemporaryDirectory(prefix="spec2lean-evidence-") as temporary_name:
        temporary = Path(temporary_name)
        scope_path = temporary / "evidence-scope.json"
        submission_path = temporary / "submission.json"
        trace_path = temporary / "exposure-trace.json"
        scope_path.write_text(json.dumps(scope.to_dict(), ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        config = opencode_config(database, scope_path, submission_path, trace_path)
        command = [
            executable, "run", "--pure", "--print-logs", "--log-level", "ERROR",
            "--format", "json", "--agent", RETRIEVER_AGENT,
            "--model", RETRIEVER_MODEL, "--variant", RETRIEVER_REASONING,
            "--title", f"{scope.plan_run_id}:{scope.unit_id}", prompt,
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
        error: str | None = None
        try:
            completed = run_session(
                command, run_command=run_command, cwd=str(unit_directory), env=environment, text=True,
                capture_output=True, timeout=timeout_seconds, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            completed = subprocess.CompletedProcess(command, 124, exc.stdout or "", exc.stderr or "")
            error = f"OpenCode Evidence Retriever session timed out after {timeout_seconds} seconds"
        if error is None and completed.returncode != 0:
            error = f"OpenCode Evidence Retriever exited with status {completed.returncode}"
        if error is None and not submission_path.is_file():
            error = "OpenCode Evidence Retriever session finished without a valid submit_evidence call"
        trace: dict[str, Any] = {}
        if trace_path.is_file():
            try:
                trace = json.loads(trace_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                error = error or "Evidence Retriever exposure trace is invalid"
        elif error is None:
            error = "Evidence Retriever did not produce its deterministic exposure trace"

        bundle: dict[str, Any] | None = None
        if error is None:
            bundle = json.loads(submission_path.read_text(encoding="utf-8"))
            exposed = [item["nodeId"] for item in trace.get("exposedNodes", [])]
            exposure_basis = {
                item["nodeId"]: item.get("basis", []) for item in trace.get("exposedNodes", [])
            }
            with connect(database, read_only=True) as connection:
                diagnostics = validate_bundle(
                    EvidenceQuery(connection), plan, bundle,
                    exposed_node_ids=exposed, exposure_basis=exposure_basis,
                )
            if diagnostics:
                error = "stored evidence failed deterministic validation: " + "; ".join(
                    item["message"] for item in diagnostics
                )
        outcome = "VALID" if error is None else "FAILED"
        if bundle is not None and error is None:
            (unit_directory / "evidence.json").write_text(
                json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            (unit_directory / "evidence.md").write_text(render_markdown(bundle), encoding="utf-8")
        metadata = {
            "schemaVersion": 1,
            "phase": "RETRIEVE_EVIDENCE",
            "planRunId": scope.plan_run_id,
            "unitId": scope.unit_id,
            "retriever": runtime_name(),
            "indexMode": index_mode(),
            "model": RETRIEVER_MODEL,
            "reasoning": RETRIEVER_REASONING,
            "singleSession": True,
            "automaticRetries": 0,
            "startedAt": started_at,
            "finishedAt": utc_now(),
            "sourceDatabase": str(database),
            "sourceDatabaseDigest": scope.source_database_digest,
            "retrievalScope": scope.to_dict(),
            "exploration": trace,
            "command": command[:-1] + ["<evidence-retriever-prompt>"],
            "exitCode": completed.returncode,
            "sessionId": _session_id(completed.stdout),
            "outcome": outcome,
            "error": error,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
        (unit_directory / "retriever-run.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        if error is not None:
            raise RuntimeError(f"{error}; run artifact: {unit_directory}")
    return unit_directory


def build_evidence(
    database: Path,
    plan: dict[str, Any],
    evidence_root: Path,
    *,
    unit_ids: list[str] | None = None,
    jobs: int = 1,
    timeout_seconds: int = 1800,
    run_command: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> Path:
    if jobs < 1:
        raise ValueError("evidence build jobs must be positive")
    database = database.resolve()
    with connect(database, read_only=True) as connection:
        digest = EvidenceQuery(connection).source_database_digest()
    if digest != plan.get("sourceDatabaseDigest"):
        raise ValueError("Phase-2 plan sourceDatabaseDigest does not match the Phase-1 database")
    all_ids = [item["unitId"] for item in plan.get("requestedUnits", [])]
    selected_ids = unit_ids or all_ids
    if not selected_ids:
        raise ValueError("Phase-2 plan has no requested units")
    if len(set(selected_ids)) != len(selected_ids):
        raise ValueError("unit selection contains duplicates")
    unknown = sorted(set(selected_ids) - set(all_ids))
    if unknown:
        raise KeyError(f"units are not in Phase-2 plan: {unknown}")

    executable = runtime_executable()
    if executable is None:
        raise RuntimeError("OpenCode executable is not installed or not on PATH")
    require_retriever_model(executable)
    run_root = (
        evidence_root.resolve() / str(plan["language"]).casefold() /
        str(plan["version"]) / str(plan["planRunId"])
    )
    run_root.mkdir(parents=True, exist_ok=True)
    scopes = [EvidenceScope.from_plan(plan, unit_id) for unit_id in selected_ids]
    existing = [run_root / unit_directory_name(scope.unit) for scope in scopes]
    collisions = [path for path in existing if path.exists()]
    if collisions:
        raise FileExistsError(f"evidence unit artifact already exists: {collisions[0]}")

    failures: list[str] = []
    if jobs == 1:
        for scope in scopes:
            try:
                _run_unit(
                    database, plan, scope, run_root, executable,
                    timeout_seconds=timeout_seconds, run_command=run_command,
                )
            except RuntimeError as exc:
                failures.append(str(exc))
                break
    else:
        with ThreadPoolExecutor(max_workers=jobs, thread_name_prefix="evidence-unit") as executor:
            futures = {
                executor.submit(
                    _run_unit, database, plan, scope, run_root, executable,
                    timeout_seconds=timeout_seconds, run_command=run_command,
                ): scope.unit_id
                for scope in scopes
            }
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as exc:
                    failures.append(f"{futures[future]}: {exc}")
    if failures:
        raise RuntimeError("one or more unit retrievals failed: " + " | ".join(failures))
    return run_root
