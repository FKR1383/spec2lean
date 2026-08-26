from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ..checking.runner import run_checks
from ..checking.store import load_check
from ..semantics.revision import revise_semantics
from ..translation.revision import revise_translation
from ..util import stable_id
from .models import (
    NO_ACTION,
    REPAIR_BUILD,
    RETURN_TO_SEMANTIC_EXTRACTOR,
    RETURN_TO_TRANSLATOR,
    action_for,
    artifact_hash,
)
from .runner import run_troubleshooter
from .store import unit_directory


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


def resolve_check_failure(
    plan: dict[str, Any], *, evidence_root: Path, semantics_root: Path,
    translations_root: Path, checks_root: Path, troubleshooting_root: Path,
    database: Path, unit_id: str, timeout_seconds: int = 1800,
    semantic_reviser: Callable[..., tuple[Path, dict[str, Any]]] = revise_semantics,
    translation_reviser: Callable[..., tuple[Path, dict[str, Any]]] = revise_translation,
    checker: Callable[..., tuple[Path, dict[str, Any]]] = run_checks,
    repair_runner: Callable[..., dict[str, Any]] | None = None,
    now: Callable[[], str] = utc_now,
    repository_root: Path | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Dispatch one stored check failure and run Phase 6 once; never recurse on the result."""
    _, check = load_check(checks_root, plan, unit_id)
    action = action_for(check)
    source_check_hash = artifact_hash(check)
    started_at = now()
    route_kwargs: dict[str, Any] = {}
    if repair_runner is not None:
        route_kwargs["repair_runner"] = repair_runner
    _, route = run_troubleshooter(
        plan, semantics_root=semantics_root, translations_root=translations_root,
        checks_root=checks_root, troubleshooting_root=troubleshooting_root,
        unit_id=unit_id, timeout_seconds=timeout_seconds, repository_root=repository_root,
        **route_kwargs,
    )
    stages: list[dict[str, Any]] = []
    if action == NO_ACTION:
        result = {
            "schemaVersion": 1, "phase": "TROUBLESHOOTER_RESOLUTION",
            "resolutionRunId": stable_id("resolution-run", route["runId"], "complete"),
            "planRunId": plan["planRunId"], "unitId": unit_id, "initialAction": action,
            "stages": [], "rechecked": False, "checkBeforeHash": artifact_hash(check),
            "checkAfterHash": artifact_hash(check), "checkResult": check,
            "nextAction": NO_ACTION, "automaticRetries": 0, "dispatches": 0,
            "startedAt": started_at, "finishedAt": now(), "outcome": "COMPLETE",
        }
    else:
        if action == RETURN_TO_SEMANTIC_EXTRACTOR:
            semantic_path, semantic_revision = semantic_reviser(
                plan, evidence_root=evidence_root, semantics_root=semantics_root,
                unit_id=unit_id, diagnostics=check["traceability"]["brokenMappings"],
                timeout_seconds=timeout_seconds, source_check_hash=source_check_hash,
            )
            stages.append({"phase": "SEMANTIC_EXTRACTOR_REVISION", "directory": str(semantic_path), "runId": semantic_revision["revisionRunId"]})
            translation_path, translation_revision = translation_reviser(
                plan, semantics_root=semantics_root, translations_root=translations_root,
                unit_id=unit_id, diagnostics=check["traceability"]["brokenMappings"],
                reason="SEMANTICS_REVISED", timeout_seconds=timeout_seconds,
                source_check_hash=source_check_hash,
            )
            stages.append({"phase": "LLM_TRANSLATOR_REVISION", "directory": str(translation_path), "runId": translation_revision["revisionRunId"]})
        elif action == RETURN_TO_TRANSLATOR:
            translation_path, translation_revision = translation_reviser(
                plan, semantics_root=semantics_root, translations_root=translations_root,
                unit_id=unit_id, diagnostics=check["coverage"]["uncovered"],
                reason="COVERAGE_FAILURE", timeout_seconds=timeout_seconds,
                source_check_hash=source_check_hash,
            )
            stages.append({"phase": "LLM_TRANSLATOR_REVISION", "directory": str(translation_path), "runId": translation_revision["revisionRunId"]})
        elif action == REPAIR_BUILD:
            stages.append({"phase": "TROUBLESHOOTER_BUILD_REPAIR", "directory": str(unit_directory(troubleshooting_root, plan, check["unit"])), "runId": route["repairRunId"]})

        check_path, after_check = checker(
            plan, evidence_root=evidence_root, semantics_root=semantics_root,
            translations_root=translations_root, checks_root=checks_root,
            database=database, unit_id=unit_id,
        )
        stages.append({"phase": "CHECK", "directory": str(check_path), "status": after_check["status"]})
        next_action = action_for(after_check)
        result = {
            "schemaVersion": 1, "phase": "TROUBLESHOOTER_RESOLUTION",
            "resolutionRunId": stable_id("resolution-run", route["runId"], artifact_hash(after_check)),
            "planRunId": plan["planRunId"], "unitId": unit_id, "initialAction": action,
            "stages": stages, "rechecked": True, "checkBeforeHash": artifact_hash(check),
            "checkAfterHash": artifact_hash(after_check), "checkResult": after_check,
            "nextAction": next_action, "automaticRetries": 0, "dispatches": 1,
            "startedAt": started_at, "finishedAt": now(),
            "outcome": "COMPLETE" if next_action == NO_ACTION else "RECHECK_FAILED",
        }
    output = unit_directory(troubleshooting_root, plan, check["unit"])
    _write_atomic(output / "resolution.json", json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return output, result
