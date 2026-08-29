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

from ..planning.runner import installed_openai_models
from ..semantics.store import load_semantics
from .groups import group_for_unit, grouped_units
from .models import (
    TRANSLATION_SCHEMA_VERSION,
    TRANSLATOR_AGENT,
    TRANSLATOR_MODEL,
    TRANSLATOR_REASONING,
    TranslationGroupScope,
)
from .prompt import build_translator_prompt
from .store import group_directory
from .validation import validate_published


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def require_translator_model(executable: str) -> None:
    models = installed_openai_models(executable)
    if TRANSLATOR_MODEL in models:
        return
    available = ", ".join(sorted(models)) or "<none>"
    raise RuntimeError(
        f"required OpenCode Lean Translator model is unavailable: {TRANSLATOR_MODEL}; "
        f"installed OpenAI model IDs: {available}. No model was substituted and no Translator session was started"
    )


def opencode_config(scope_path: Path, semantics_path: Path, submission_path: Path) -> dict[str, Any]:
    disabled = {
        name: False for name in (
            "bash", "edit", "write", "read", "glob", "grep", "list", "task", "webfetch",
            "websearch", "todowrite", "skill", "question", "lsp",
        )
    }
    return {
        "default_agent": TRANSLATOR_AGENT,
        "share": "disabled",
        "autoupdate": False,
        "formatter": False,
        "lsp": False,
        "mcp": {"translation": {
            "type": "local",
            "command": [
                sys.executable, "-m", "spec2lean.translation.mcp",
                "--scope", str(scope_path),
                "--semantics", str(semantics_path),
                "--submission", str(submission_path),
            ],
            "enabled": True,
            "timeout": 15_000,
        }},
        "agent": {TRANSLATOR_AGENT: {
            "description": "Phase-4-artifact-bounded Lean 4 semantic translator",
            "mode": "primary",
            "model": TRANSLATOR_MODEL,
            "variant": TRANSLATOR_REASONING,
            "steps": 40,
            "tools": disabled,
            "permission": {"*": "deny", "translation_*": "allow"},
        }},
    }


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


def build_group_translation(
    plan: dict[str, Any], semantics_root: Path, translations_root: Path, *, group: str,
    timeout_seconds: int = 1800,
    run_command: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    shared_core: Any | None = None,
) -> Path:
    units = grouped_units(plan).get(group, [])
    if not units:
        raise KeyError(f"translation group is not present in plan: {group}")
    semantics_by_unit: dict[str, dict[str, Any]] = {}
    semantic_directories: dict[str, Path] = {}
    for unit in units:
        unit_id = str(unit["unitId"])
        semantic_directory, semantics = load_semantics(semantics_root, plan, unit_id)
        semantic_directories[unit_id] = semantic_directory
        semantics_by_unit[unit_id] = semantics
    if any(
        isinstance(item, dict)
        and set(item.get("requiredBy", [])) & {str(unit["unitId"]) for unit in units}
        for item in plan.get("sharedPrerequisites", [])
    ) and shared_core is None:
        from .shared_core import load_current_core, validate_core_artifact

        candidate = load_current_core(translations_root, plan)
        if candidate is not None:
            all_semantics = dict(semantics_by_unit)
            for planned_unit in plan.get("requestedUnits", []):
                planned_unit_id = str(planned_unit["unitId"])
                if planned_unit_id not in all_semantics:
                    all_semantics[planned_unit_id] = load_semantics(
                        semantics_root, plan, planned_unit_id
                    )[1]
            if not validate_core_artifact(plan, all_semantics, candidate):
                shared_core = candidate
    started_at = utc_now()
    scope = TranslationGroupScope.from_inputs(
        plan, group, semantics_by_unit, created_at=started_at, shared_core=shared_core
    )
    output = group_directory(translations_root, plan, group)
    if output.exists():
        raise FileExistsError(f"translation group artifact already exists: {output}")
    executable = shutil.which("opencode")
    if executable is None:
        raise RuntimeError("OpenCode executable is not installed or not on PATH")
    require_translator_model(executable)
    output.mkdir(parents=True, exist_ok=False)
    core_source: str | None = None
    if shared_core is not None:
        core_source = getattr(shared_core, "source", None)
        if core_source is None:
            source_path = getattr(shared_core, "source_path", None)
            if isinstance(source_path, Path):
                core_source = source_path.read_text(encoding="utf-8")
    prompt = build_translator_prompt(scope, semantics_by_unit, core_source)
    with tempfile.TemporaryDirectory(prefix="spec2lean-translation-") as temporary_name:
        temporary = Path(temporary_name)
        scope_path = temporary / "translation-scope.json"
        semantics_path = temporary / "semantics-by-unit.json"
        submission_path = temporary / "submission.json"
        scope_path.write_text(json.dumps(scope.to_dict(), ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        semantics_path.write_text(json.dumps(semantics_by_unit, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        config = opencode_config(scope_path, semantics_path, submission_path)
        command = [
            executable, "run", "--pure", "--print-logs", "--log-level", "ERROR", "--format", "json",
            "--agent", TRANSLATOR_AGENT, "--model", TRANSLATOR_MODEL, "--variant", TRANSLATOR_REASONING,
            "--title", f"{scope.plan_run_id}:{scope.group}:translate", prompt,
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
            error = f"OpenCode Lean Translator session timed out after {timeout_seconds} seconds"
        if error is None and completed.returncode != 0:
            error = f"OpenCode Lean Translator exited with status {completed.returncode}"
        if error is None and not submission_path.is_file():
            error = "OpenCode Lean Translator session finished without a valid submit_translation call"
        candidate: dict[str, Any] | None = None
        if submission_path.is_file():
            try:
                candidate = json.loads(submission_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                error = error or "Lean Translator submission is invalid JSON"
        if candidate is not None and error is None:
            (output / scope.lean_file).write_text(candidate["leanSource"].rstrip() + "\n", encoding="utf-8")
            (output / "translation-manifest.json").write_text(
                json.dumps(candidate["manifest"], ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        metadata = {
            "schemaVersion": TRANSLATION_SCHEMA_VERSION,
            "phase": "LLM_GROUP_TRANSLATOR",
            "planRunId": scope.plan_run_id,
            "group": {"name": scope.group, "unitIds": list(scope.unit_ids)},
            "translationRunId": scope.translation_run_id,
            "translator": "opencode",
            "model": TRANSLATOR_MODEL,
            "reasoning": TRANSLATOR_REASONING,
            "singleSession": True,
            "automaticRetries": 0,
            "startedAt": started_at,
            "finishedAt": utc_now(),
            "semanticsArtifactPaths": [
                str(semantic_directories[unit_id] / "semantics.json") for unit_id in scope.unit_ids
            ],
            "semanticsArtifacts": [
                {"unitId": unit_id, "runId": dict(scope.semantics_run_ids)[unit_id], "artifactHash": artifact_hash}
                for unit_id, artifact_hash in scope.semantics_artifact_hashes
            ],
            "inputBoundary": (
                "PHASE_4_AND_FROZEN_SHARED_CORE"
                if scope.shared_core is not None
                else "PHASE_4_SEMANTIC_ARTIFACTS_ONLY"
            ),
            "sharedCore": (
                {
                    key: scope.shared_core[key]
                    for key in ("coreRunId", "manifestHash", "sourceHash", "leanModule")
                }
                if scope.shared_core is not None else None
            ),
            "targetLanguage": "Lean",
            "targetVersion": "4",
            "command": command[:-1] + ["<lean-translator-prompt>"],
            "exitCode": completed.returncode,
            "sessionId": _session_id(completed.stdout),
            "outcome": "SUCCESS" if candidate is not None and error is None else "FAILED",
            "error": error,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
        run_path = output / "translator-run.json"
        run_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if error is None:
            core_manifest = getattr(shared_core, "manifest", shared_core)
            diagnostics = validate_published(
                plan, semantics_by_unit, output,
                core_manifest=core_manifest if isinstance(core_manifest, dict) else None,
            )
            if diagnostics:
                error = "stored translation failed deterministic validation: " + "; ".join(item["message"] for item in diagnostics)
                metadata["outcome"] = "FAILED"
                metadata["error"] = error
                run_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if error is not None:
            raise RuntimeError(f"{error}; run artifact: {output}")
    return output


def build_translation(
    plan: dict[str, Any], semantics_root: Path, translations_root: Path, *, unit_id: str,
    timeout_seconds: int = 1800,
    run_command: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    shared_core: Any | None = None,
) -> Path:
    """Compatibility command: translate the complete group containing ``unit_id``."""
    return build_group_translation(
        plan, semantics_root, translations_root,
        group=group_for_unit(plan, unit_id), timeout_seconds=timeout_seconds,
        run_command=run_command, shared_core=shared_core,
    )
