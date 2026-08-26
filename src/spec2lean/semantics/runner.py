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

from ..evidence.store import load_unit_bundle
from ..planning.runner import installed_openai_models
from .models import EXTRACTOR_AGENT, EXTRACTOR_MODEL, EXTRACTOR_REASONING, SemanticScope
from .prompt import build_extractor_prompt
from .render import render_markdown
from .store import semantics_run_root, unit_directory
from .validation import validate_artifact


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def require_extractor_model(executable: str) -> None:
    models = installed_openai_models(executable)
    if EXTRACTOR_MODEL in models:
        return
    available = ", ".join(sorted(models)) or "<none>"
    raise RuntimeError(
        f"required OpenCode Semantic Extractor model is unavailable: {EXTRACTOR_MODEL}; "
        f"installed OpenAI model IDs: {available}. No model was substituted and no extractor session was started"
    )


def opencode_config(scope_path: Path, evidence_path: Path, submission_path: Path) -> dict[str, Any]:
    disabled = {
        name: False for name in (
            "bash", "edit", "write", "read", "glob", "grep", "list", "task", "webfetch",
            "websearch", "todowrite", "skill", "question", "lsp",
        )
    }
    return {
        "default_agent": EXTRACTOR_AGENT,
        "share": "disabled", "autoupdate": False, "formatter": False, "lsp": False,
        "mcp": {"semantics": {
            "type": "local",
            "command": [
                sys.executable, "-m", "spec2lean.semantics.mcp", "--scope", str(scope_path),
                "--evidence", str(evidence_path), "--submission", str(submission_path),
            ],
            "enabled": True, "timeout": 15_000,
        }},
        "agent": {EXTRACTOR_AGENT: {
            "description": "Evidence-bounded structured language semantic extractor",
            "mode": "primary", "model": EXTRACTOR_MODEL, "variant": EXTRACTOR_REASONING,
            "steps": 40, "tools": disabled, "permission": {"*": "deny", "semantics_*": "allow"},
        }},
    }


def _session_id(stdout: str) -> str | None:
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        candidates = [event, event.get("part")]
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            for key in ("sessionID", "sessionId", "session_id"):
                if isinstance(candidate.get(key), str):
                    return candidate[key]
    return None


def _run_unit(
    plan: dict[str, Any], bundle: dict[str, Any], output: Path, executable: str, *,
    timeout_seconds: int, run_command: Callable[..., subprocess.CompletedProcess[str]],
) -> Path:
    output.mkdir(parents=True, exist_ok=False)
    started_at = utc_now()
    scope = SemanticScope.from_inputs(plan, bundle, bundle["unit"]["unitId"], created_at=started_at)
    prompt = build_extractor_prompt(scope, bundle)
    with tempfile.TemporaryDirectory(prefix="spec2lean-semantics-") as temporary_name:
        temporary = Path(temporary_name)
        scope_path, evidence_path = temporary / "semantic-scope.json", temporary / "evidence.json"
        submission_path = temporary / "submission.json"
        scope_path.write_text(json.dumps(scope.to_dict(), ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        evidence_path.write_text(json.dumps(bundle, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        config = opencode_config(scope_path, evidence_path, submission_path)
        command = [
            executable, "run", "--pure", "--print-logs", "--log-level", "ERROR", "--format", "json",
            "--agent", EXTRACTOR_AGENT, "--model", EXTRACTOR_MODEL, "--variant", EXTRACTOR_REASONING,
            "--title", f"{scope.plan_run_id}:{scope.unit_id}:semantics", prompt,
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
                command, cwd=str(output), env=environment, text=True, capture_output=True,
                timeout=timeout_seconds, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            completed = subprocess.CompletedProcess(command, 124, exc.stdout or "", exc.stderr or "")
            error = f"OpenCode Semantic Extractor session timed out after {timeout_seconds} seconds"
        if error is None and completed.returncode != 0:
            error = f"OpenCode Semantic Extractor exited with status {completed.returncode}"
        if error is None and not submission_path.is_file():
            error = "OpenCode Semantic Extractor session finished without a valid submit_semantics call"
        artifact: dict[str, Any] | None = None
        if submission_path.is_file():
            try:
                artifact = json.loads(submission_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                error = error or "Semantic Extractor submission is invalid JSON"
        if artifact is not None and error is None:
            diagnostics = validate_artifact(plan, bundle, artifact)
            if diagnostics:
                error = "stored semantics failed deterministic validation: " + "; ".join(item["message"] for item in diagnostics)
        outcome = artifact.get("outcome") if artifact is not None and error is None else "FAILED"
        if artifact is not None and error is None:
            (output / "semantics.json").write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            (output / "semantics.md").write_text(render_markdown(artifact), encoding="utf-8")
        metadata = {
            "schemaVersion": 1, "phase": "SEMANTIC_EXTRACTOR", "planRunId": scope.plan_run_id,
            "unitId": scope.unit_id, "runId": scope.run_id, "extractor": "opencode",
            "model": EXTRACTOR_MODEL, "reasoning": EXTRACTOR_REASONING,
            "singleSession": True, "automaticRetries": 0, "startedAt": started_at,
            "finishedAt": utc_now(), "evidenceBundleHash": scope.evidence_bundle_hash,
            "evidenceCount": len(bundle["evidence"]),
            "inputBoundary": "PHASE_3_UNIT_EVIDENCE_BUNDLE_ONLY",
            "command": command[:-1] + ["<semantic-extractor-prompt>"], "exitCode": completed.returncode,
            "sessionId": _session_id(completed.stdout), "outcome": outcome, "error": error,
            "stdout": completed.stdout, "stderr": completed.stderr,
        }
        (output / "extractor-run.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if error is not None:
            raise RuntimeError(f"{error}; run artifact: {output}")
        if outcome == "INSUFFICIENT_EVIDENCE":
            missing = "; ".join(artifact["failure"]["missingAspects"]) if artifact else "unspecified"
            raise RuntimeError(f"INSUFFICIENT_EVIDENCE: {missing}; run artifact: {output}")
    return output


def build_semantics(
    plan: dict[str, Any], evidence_root: Path, semantics_root: Path, *, unit_ids: list[str] | None = None,
    timeout_seconds: int = 1800,
    run_command: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> Path:
    all_ids = [item["unitId"] for item in plan.get("requestedUnits", [])]
    selected = unit_ids or all_ids
    if not selected:
        raise ValueError("Phase-2 plan has no requested units")
    if len(selected) != len(set(selected)):
        raise ValueError("unit selection contains duplicates")
    unknown = sorted(set(selected) - set(all_ids))
    if unknown:
        raise KeyError(f"units are not in Phase-2 plan: {unknown}")
    bundles: list[dict[str, Any]] = []
    outputs: list[Path] = []
    for unit_id in selected:
        _, bundle = load_unit_bundle(evidence_root, plan, unit_id)
        unit = next(item for item in plan["requestedUnits"] if item["unitId"] == unit_id)
        output = unit_directory(semantics_root, plan, unit)
        if output.exists():
            raise FileExistsError(f"semantic unit artifact already exists: {output}")
        SemanticScope.from_inputs(plan, bundle, unit_id, created_at="preflight")
        bundles.append(bundle)
        outputs.append(output)
    executable = shutil.which("opencode")
    if executable is None:
        raise RuntimeError("OpenCode executable is not installed or not on PATH")
    require_extractor_model(executable)
    root = semantics_run_root(semantics_root, plan)
    root.mkdir(parents=True, exist_ok=True)
    for bundle, output in zip(bundles, outputs, strict=True):
        _run_unit(plan, bundle, output, executable, timeout_seconds=timeout_seconds, run_command=run_command)
    return root
