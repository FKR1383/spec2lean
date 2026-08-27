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


def _check_state_hash(check: dict[str, Any]) -> str:
    """Hash actionable state while ignoring compiler duration and similar noise."""
    return artifact_hash({
        "translationRunId": check.get("translationRunId"),
        "inputHashes": check.get("inputHashes"),
        "build": {
            "status": (check.get("build") or {}).get("status"),
            "diagnostics": (check.get("build") or {}).get("diagnostics", []),
        },
        "coverage": {
            "status": (check.get("coverage") or {}).get("status"),
            "uncovered": (check.get("coverage") or {}).get("uncovered", []),
        },
        "traceability": {
            "status": (check.get("traceability") or {}).get("status"),
            "brokenMappings": (check.get("traceability") or {}).get("brokenMappings", []),
        },
    })


def resolve_check_failure(
    plan: dict[str, Any], *, evidence_root: Path, semantics_root: Path,
    translations_root: Path, checks_root: Path, troubleshooting_root: Path,
    database: Path, unit_id: str, timeout_seconds: int = 1800,
    semantic_reviser: Callable[..., tuple[Path, dict[str, Any]]] = revise_semantics,
    translation_reviser: Callable[..., tuple[Path, dict[str, Any]]] = revise_translation,
    checker: Callable[..., tuple[Path, dict[str, Any]]] = run_checks,
    repair_runner: Callable[..., dict[str, Any]] | None = None,
    max_dispatches: int = 8,
    now: Callable[[], str] = utc_now,
    repository_root: Path | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Resolve a bounded chain where every dispatch follows a concrete Phase-6 result."""
    if max_dispatches < 1:
        raise ValueError("max_dispatches must be positive")
    _, initial_check = load_check(checks_root, plan, unit_id)
    current_check = initial_check
    initial_action = action_for(initial_check)
    started_at = now()
    stages: list[dict[str, Any]] = []
    repair_history: list[dict[str, Any]] = []
    seen_states: set[str] = set()
    dispatch_count = 0
    stop_reason = "ALL_CHECKS_PASS"
    while action_for(current_check) != NO_ACTION:
        action = action_for(current_check)
        if dispatch_count >= max_dispatches:
            stop_reason = "DISPATCH_LIMIT"
            break
        state_hash = _check_state_hash(current_check)
        if state_hash in seen_states:
            stop_reason = "NO_PROGRESS"
            break
        seen_states.add(state_hash)
        source_check_hash = artifact_hash(current_check)
        route_kwargs: dict[str, Any] = {}
        if repair_runner is not None:
            route_kwargs["repair_runner"] = repair_runner
        if action == REPAIR_BUILD:
            route_kwargs["prior_repair_attempts"] = list(repair_history)
        _, route = run_troubleshooter(
            plan, semantics_root=semantics_root, translations_root=translations_root,
            checks_root=checks_root, troubleshooting_root=troubleshooting_root,
            unit_id=unit_id, timeout_seconds=timeout_seconds, repository_root=repository_root,
            check_override=current_check,
            **route_kwargs,
        )
        dispatch_count += 1
        if action == RETURN_TO_SEMANTIC_EXTRACTOR:
            broken = current_check["traceability"]["brokenMappings"]
            planned_ids = {
                str(unit["unitId"]) for unit in plan.get("requestedUnits", [])
            }
            diagnostic_unit_ids = sorted({
                str(item["unitId"])
                for item in broken
                if isinstance(item, dict) and item.get("unitId") in planned_ids
            })
            semantic_targets = diagnostic_unit_ids or [unit_id]
            for semantic_unit_id in semantic_targets:
                targeted = [
                    item for item in broken
                    if not isinstance(item, dict)
                    or item.get("unitId") in {None, semantic_unit_id}
                ]
                semantic_path, semantic_revision = semantic_reviser(
                    plan, evidence_root=evidence_root, semantics_root=semantics_root,
                    unit_id=semantic_unit_id, diagnostics=targeted,
                    timeout_seconds=timeout_seconds, source_check_hash=source_check_hash,
                )
                stages.append({
                    "dispatch": dispatch_count,
                    "phase": "SEMANTIC_EXTRACTOR_REVISION",
                    "unitId": semantic_unit_id,
                    "directory": str(semantic_path),
                    "runId": semantic_revision["revisionRunId"],
                })
            translation_path, translation_revision = translation_reviser(
                plan, semantics_root=semantics_root, translations_root=translations_root,
                unit_id=unit_id, diagnostics=broken,
                reason="SEMANTICS_REVISED", timeout_seconds=timeout_seconds,
                source_check_hash=source_check_hash,
            )
            stages.append({"dispatch": dispatch_count, "phase": "LLM_TRANSLATOR_REVISION", "directory": str(translation_path), "runId": translation_revision["revisionRunId"]})
        elif action == RETURN_TO_TRANSLATOR:
            translation_path, translation_revision = translation_reviser(
                plan, semantics_root=semantics_root, translations_root=translations_root,
                unit_id=unit_id, diagnostics=current_check["coverage"]["uncovered"],
                reason="COVERAGE_FAILURE", timeout_seconds=timeout_seconds,
                source_check_hash=source_check_hash,
            )
            stages.append({"dispatch": dispatch_count, "phase": "LLM_TRANSLATOR_REVISION", "directory": str(translation_path), "runId": translation_revision["revisionRunId"]})
        elif action == REPAIR_BUILD:
            stages.append({"dispatch": dispatch_count, "phase": "TROUBLESHOOTER_BUILD_REPAIR", "directory": str(unit_directory(troubleshooting_root, plan, current_check["unit"])), "runId": route["repairRunId"]})
            hashes = route.get("hashes") or {}
            lean_hash_keys = [
                key for key in (hashes.get("before") or {})
                if isinstance(key, str) and key.endswith(".lean")
            ]
            lean_hash_key = lean_hash_keys[0] if len(lean_hash_keys) == 1 else None
            repair_history.append({
                "repairRunId": route.get("repairRunId"),
                "compilerDiagnostics": route.get("compilerDiagnostics", []),
                "changes": route.get("changes", []),
                "leanSourceHashBefore": (hashes.get("before") or {}).get(lean_hash_key),
                "leanSourceHashAfter": (hashes.get("after") or {}).get(lean_hash_key),
            })

        check_path, after_check = checker(
            plan, evidence_root=evidence_root, semantics_root=semantics_root,
            translations_root=translations_root, checks_root=checks_root,
            database=database, unit_id=unit_id,
        )
        stages.append({"dispatch": dispatch_count, "phase": "CHECK", "directory": str(check_path), "status": after_check["status"], "nextAction": action_for(after_check)})
        current_check = after_check

    next_action = action_for(current_check)
    outcome = "COMPLETE" if next_action == NO_ACTION else (
        "NO_PROGRESS" if stop_reason == "NO_PROGRESS" else "DISPATCH_LIMIT"
    )
    result = {
        "schemaVersion": 1, "phase": "TROUBLESHOOTER_RESOLUTION",
        "resolutionRunId": stable_id(
            "resolution-run", artifact_hash(initial_check), artifact_hash(current_check), dispatch_count
        ),
        "planRunId": plan["planRunId"], "unitId": unit_id,
        "initialAction": initial_action, "stages": stages,
        "rechecked": dispatch_count > 0, "checkBeforeHash": artifact_hash(initial_check),
        "checkAfterHash": artifact_hash(current_check), "checkResult": current_check,
        "nextAction": next_action, "automaticRetries": 0,
        "dispatches": dispatch_count, "maxDispatches": max_dispatches,
        "stopReason": stop_reason, "startedAt": started_at, "finishedAt": now(),
        "outcome": outcome,
    }
    output = unit_directory(troubleshooting_root, plan, initial_check["unit"])
    _write_atomic(output / "resolution.json", json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return output, result
