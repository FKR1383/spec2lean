from __future__ import annotations

from typing import Any


CHECK_SCHEMA_VERSION = 1
CHECK_STATUSES = ("PASS", "FAIL")
ROUTING_TARGETS = ("COMPLETE", "TROUBLESHOOTER", "TRANSLATOR", "SEMANTIC_EXTRACTOR")


def routing_for(build: str, coverage: str, traceability: str) -> list[str]:
    """Return every required destination, earliest workflow phase first."""
    targets: list[str] = []
    if traceability == "FAIL":
        targets.append("SEMANTIC_EXTRACTOR")
    if coverage == "FAIL":
        targets.append("TRANSLATOR")
    if build == "FAIL":
        targets.append("TROUBLESHOOTER")
    return targets or ["COMPLETE"]


def check_result(
    *,
    plan: dict[str, Any],
    unit: dict[str, Any],
    translation_run_id: str,
    build: dict[str, Any],
    coverage: dict[str, Any],
    traceability: dict[str, Any],
    input_hashes: dict[str, str] | None = None,
) -> dict[str, Any]:
    statuses = (build["status"], coverage["status"], traceability["status"])
    result = {
        "schemaVersion": CHECK_SCHEMA_VERSION,
        "phase": "CHECK",
        "planRunId": plan["planRunId"],
        "language": plan["language"],
        "version": plan["version"],
        "unit": dict(unit),
        "translationRunId": translation_run_id,
        "status": "PASS" if all(status == "PASS" for status in statuses) else "FAIL",
        "build": build,
        "coverage": coverage,
        "traceability": traceability,
        "routing": {"next": routing_for(*statuses)},
    }
    if input_hashes is not None:
        result["inputHashes"] = dict(input_hashes)
    return result
