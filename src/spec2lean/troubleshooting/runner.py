from __future__ import annotations

import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ..checking.store import load_check
from ..semantics.store import load_semantics
from ..translation.models import TranslationScope
from ..translation.store import load_translation
from ..translation.validation import validate_manifest
from ..util import sha256_file
from .models import (
    NO_ACTION,
    REPAIR_BUILD,
    RETURN_TO_SEMANTIC_EXTRACTOR,
    RETURN_TO_TRANSLATOR,
    TROUBLESHOOTER_MODEL,
    TROUBLESHOOTER_REASONING,
    TROUBLESHOOTING_SCHEMA_VERSION,
    action_for,
    artifact_hash,
    diagnostic_payload,
    run_id,
)
from .opencode import run_opencode_repair
from .store import unit_directory
from .validation import validate_repair_submission


RepairRunner = Callable[..., dict[str, Any]]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


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


def _repository_commit(repository_root: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository_root,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    value = completed.stdout.strip()
    return value if completed.returncode == 0 and value else "UNKNOWN"


def _file_hash(path: Path) -> str:
    return "sha256:" + sha256_file(path)


def _base_artifact(
    plan: dict[str, Any],
    check: dict[str, Any],
    action: str,
    *,
    started_at: str,
    repository_root: Path,
) -> dict[str, Any]:
    reasons = {
        RETURN_TO_SEMANTIC_EXTRACTOR: "TRACEABILITY_FAILURE",
        RETURN_TO_TRANSLATOR: "COVERAGE_FAILURE",
        REPAIR_BUILD: "BUILD_FAILURE",
        NO_ACTION: "ALL_CHECKS_PASS",
    }
    diagnostics = diagnostic_payload(check)
    handoff: dict[str, Any] | None = None
    if action == RETURN_TO_SEMANTIC_EXTRACTOR:
        handoff = {"phase": "SEMANTIC_EXTRACTOR", "diagnostics": diagnostics["traceability"]}
    elif action == RETURN_TO_TRANSLATOR:
        handoff = {"phase": "LLM_TRANSLATOR", "diagnostics": diagnostics["coverage"]}
    return {
        "schemaVersion": TROUBLESHOOTING_SCHEMA_VERSION,
        "phase": "TROUBLESHOOTER",
        "runId": run_id(check),
        "repairRunId": None,
        "planRunId": plan["planRunId"],
        "language": plan["language"],
        "version": plan["version"],
        "unit": dict(check["unit"]),
        "translationRunId": check.get("translationRunId"),
        "checkArtifactHash": artifact_hash(check),
        "action": action,
        "reason": reasons[action],
        "failures": {
            name: check[name]["status"] == "FAIL"
            for name in ("build", "coverage", "traceability")
        },
        "diagnostics": diagnostics,
        "compilerDiagnostics": diagnostics["build"],
        "handoff": handoff,
        "changedFiles": [],
        "changes": [],
        "hashes": None,
        "model": None,
        "opencodeVersion": None,
        "singleSession": False,
        "automaticRetries": 0,
        "recheck": {"required": False, "phase": "CHECK", "checks": [], "automatic": False},
        "spec2leanCommit": _repository_commit(repository_root),
        "startedAt": started_at,
        "finishedAt": started_at,
        "outcome": "COMPLETE" if action == NO_ACTION else "ROUTED",
        "error": None,
        "session": None,
    }


def _store(output: Path, artifact: dict[str, Any]) -> None:
    _write_atomic(
        output / "troubleshoot.json",
        json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def run_troubleshooter(
    plan: dict[str, Any],
    *,
    semantics_root: Path,
    translations_root: Path,
    checks_root: Path,
    troubleshooting_root: Path,
    unit_id: str,
    timeout_seconds: int = 1800,
    repair_runner: RepairRunner = run_opencode_repair,
    now: Callable[[], str] = utc_now,
    repository_root: Path | None = None,
    check_override: dict[str, Any] | None = None,
) -> tuple[Path, dict[str, Any]]:
    if check_override is None:
        _, check = load_check(checks_root, plan, unit_id)
    else:
        check = check_override
    units = [item for item in plan.get("requestedUnits", []) if item.get("unitId") == unit_id]
    if len(units) != 1 or check.get("unit") != units[0]:
        raise ValueError("Phase-6 check unit does not match the Phase-2 planned unit")
    if check.get("planRunId") != plan.get("planRunId"):
        raise ValueError("Phase-6 check planRunId does not match Phase 2")
    action = action_for(check)
    output = unit_directory(troubleshooting_root, plan, units[0])
    output.mkdir(parents=True, exist_ok=True)
    started_at = now()
    repo = (repository_root or Path(__file__).resolve().parents[3]).resolve()
    artifact = _base_artifact(plan, check, action, started_at=started_at, repository_root=repo)
    if action != REPAIR_BUILD:
        artifact["finishedAt"] = now()
        _store(output, artifact)
        return output, artifact

    translation_directory, source, manifest, _ = load_translation(
        translations_root, plan, unit_id
    )
    _, semantics = load_semantics(semantics_root, plan, unit_id)
    if manifest.get("translationRunId") != check.get("translationRunId"):
        raise ValueError("Phase-6 check does not refer to the current Phase-5 translation")
    manifest_diagnostics = validate_manifest(plan, semantics, source, manifest)
    if manifest_diagnostics:
        raise ValueError(
            "build repair requires a valid Phase-5 translation manifest: "
            + "; ".join(item["message"] for item in manifest_diagnostics)
        )
    scope = TranslationScope.from_inputs(
        plan, semantics, unit_id, created_at=str(manifest.get("createdAt", ""))
    )
    lean_path = translation_directory / str(manifest.get("leanFile", "Unit.lean"))
    manifest_path = translation_directory / "translation-manifest.json"
    before = {"Unit.lean": _file_hash(lean_path), "translation-manifest.json": _file_hash(manifest_path)}
    artifact["runId"] = run_id(check, before["Unit.lean"], before["translation-manifest.json"])
    artifact["repairRunId"] = artifact["runId"].replace("troubleshoot-run:", "repair-run:", 1)
    artifact["model"] = {
        "provider": "opencode", "model": TROUBLESHOOTER_MODEL, "reasoning": TROUBLESHOOTER_REASONING
    }
    artifact["singleSession"] = True
    artifact["hashes"] = {"before": before, "after": dict(before)}
    context = {
        "plan": {
            "planRunId": plan["planRunId"], "language": plan["language"], "version": plan["version"]
        },
        "unit": dict(units[0]),
        "translationDirectory": str(translation_directory),
        "translationScope": scope.to_dict(),
        "leanSource": source,
        "translationManifest": manifest,
        "compilerDiagnostics": list(check["build"].get("diagnostics", [])),
        "traceability": check["traceability"],
        "semantics": semantics,
    }
    try:
        result = repair_runner(context, timeout_seconds=timeout_seconds)
        session = result.get("session")
        artifact["session"] = session
        if isinstance(session, dict):
            artifact["opencodeVersion"] = session.get("opencodeVersion")
        if result.get("error"):
            raise RuntimeError(str(result["error"]))
        candidate, diagnostics = validate_repair_submission(
            scope, semantics, source, manifest, result.get("submission")
        )
        if diagnostics or candidate is None:
            raise ValueError(
                "Troubleshooter submission failed deterministic validation: "
                + "; ".join(item["message"] for item in diagnostics)
            )

        new_source = candidate["leanSource"].rstrip() + "\n"
        new_manifest_text = json.dumps(
            candidate["manifest"], ensure_ascii=False, indent=2, sort_keys=True
        ) + "\n"
        original_source_text = lean_path.read_text(encoding="utf-8")
        original_manifest_text = manifest_path.read_text(encoding="utf-8")
        try:
            if new_source != original_source_text:
                _write_atomic(lean_path, new_source)
            if candidate["manifest"] != manifest:
                _write_atomic(manifest_path, new_manifest_text)
        except Exception:
            _write_atomic(lean_path, original_source_text)
            _write_atomic(manifest_path, original_manifest_text)
            raise
        after = {"Unit.lean": _file_hash(lean_path), "translation-manifest.json": _file_hash(manifest_path)}
        changed = [name for name in ("Unit.lean", "translation-manifest.json") if before[name] != after[name]]
        if not changed:
            raise ValueError("validated Troubleshooter submission produced no file changes")
        artifact["changedFiles"] = changed
        artifact["changes"] = candidate["changes"]
        artifact["hashes"]["after"] = after
        artifact["recheck"] = {
            "required": True,
            "phase": "CHECK",
            "checks": ["BUILD", "COVERAGE", "TRACEABILITY"],
            "automatic": False,
        }
        artifact["outcome"] = "REPAIRED"
    except Exception as exc:
        artifact["outcome"] = "FAILED"
        artifact["error"] = str(exc)
        artifact["finishedAt"] = now()
        _store(output, artifact)
        raise RuntimeError(f"{exc}; Phase-7 artifact: {output}") from exc
    artifact["finishedAt"] = now()
    _store(output, artifact)
    return output, artifact
