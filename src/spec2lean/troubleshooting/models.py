from __future__ import annotations

import hashlib
from typing import Any

from ..util import canonical_json, stable_id


TROUBLESHOOTING_SCHEMA_VERSION = 1
TROUBLESHOOTER_MODEL = "openai/gpt-5.6-sol"
TROUBLESHOOTER_REASONING = "medium"
TROUBLESHOOTER_AGENT = "spec2lean-troubleshooter"

RETURN_TO_SEMANTIC_EXTRACTOR = "RETURN_TO_SEMANTIC_EXTRACTOR"
RETURN_TO_TRANSLATOR = "RETURN_TO_TRANSLATOR"
REPAIR_BUILD = "REPAIR_BUILD"
NO_ACTION = "NO_ACTION"


def artifact_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def action_for(check: dict[str, Any]) -> str:
    """Select exactly one owner, respecting the Phase 4 -> 5 -> 7 dependency order."""
    if check.get("phase") != "CHECK":
        raise ValueError("Phase 7 requires a Phase-6 check artifact")
    statuses = {
        name: (check.get(name) or {}).get("status")
        for name in ("build", "coverage", "traceability")
    }
    invalid = {name: status for name, status in statuses.items() if status not in {"PASS", "FAIL"}}
    if invalid:
        raise ValueError(f"Phase-6 check has invalid statuses: {invalid}")
    if statuses["traceability"] == "FAIL":
        return RETURN_TO_SEMANTIC_EXTRACTOR
    if statuses["coverage"] == "FAIL":
        return RETURN_TO_TRANSLATOR
    if statuses["build"] == "FAIL":
        return REPAIR_BUILD
    return NO_ACTION


def run_id(check: dict[str, Any], *translation_hashes: str) -> str:
    return stable_id(
        "troubleshoot-run",
        check.get("planRunId", ""),
        (check.get("unit") or {}).get("unitId", ""),
        artifact_hash(check),
        *translation_hashes,
    )


def diagnostic_payload(check: dict[str, Any]) -> dict[str, Any]:
    return {
        "build": list((check.get("build") or {}).get("diagnostics", [])),
        "coverage": list((check.get("coverage") or {}).get("uncovered", [])),
        "traceability": list((check.get("traceability") or {}).get("brokenMappings", [])),
    }
