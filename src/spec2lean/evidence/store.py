from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def evidence_run_root(evidence_root: Path, plan: dict[str, Any]) -> Path:
    return (
        evidence_root.resolve() / str(plan["language"]).casefold() /
        str(plan["version"]) / str(plan["planRunId"])
    )


def unit_artifacts(evidence_root: Path, plan: dict[str, Any]) -> list[dict[str, Any]]:
    root = evidence_run_root(evidence_root, plan)
    result = []
    if not root.is_dir():
        return result
    for directory in sorted(path for path in root.iterdir() if path.is_dir()):
        metadata_path = directory / "retriever-run.json"
        bundle_path = directory / "evidence.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.is_file() else {}
        bundle = json.loads(bundle_path.read_text(encoding="utf-8")) if bundle_path.is_file() else None
        result.append({"directory": directory, "metadata": metadata, "bundle": bundle})
    return result


def load_unit_bundle(evidence_root: Path, plan: dict[str, Any], unit_id: str) -> tuple[Path, dict[str, Any]]:
    matches = [
        item for item in unit_artifacts(evidence_root, plan)
        if (item["bundle"] or {}).get("unit", {}).get("unitId") == unit_id
        or item["metadata"].get("unitId") == unit_id
    ]
    if not matches:
        raise FileNotFoundError(f"evidence bundle does not exist for unit: {unit_id}")
    if len(matches) > 1:
        raise RuntimeError(f"multiple evidence artifacts exist for unit: {unit_id}")
    if matches[0]["bundle"] is None:
        raise RuntimeError(f"unit retrieval did not produce a valid bundle: {unit_id}")
    return matches[0]["directory"], matches[0]["bundle"]


def find_evidence(evidence_root: Path, evidence_id: str) -> tuple[Path, dict[str, Any]]:
    matches: list[tuple[Path, dict[str, Any]]] = []
    for path in evidence_root.resolve().glob("*/*/*/*/evidence.json"):
        bundle = json.loads(path.read_text(encoding="utf-8"))
        for item in [*bundle.get("evidence", []), *bundle.get("resolutions", [])]:
            item_id = item.get("evidenceId") or item.get("resolutionId")
            if item_id == evidence_id:
                matches.append((path, item))
    if not matches:
        raise FileNotFoundError(f"evidence ID was not found: {evidence_id}")
    if evidence_id.startswith("resolution:"):
        identities = {json.dumps(item, sort_keys=True) for _, item in matches}
        if len(identities) > 1:
            raise RuntimeError(f"resolution ID resolves to conflicting records: {evidence_id}")
        return matches[0]
    provenance_fields = (
        "evidenceId", "role", "tier", "sourceNodeId", "sourceNodeIds", "sourceSpanIds",
        "sourceType", "sectionNumber", "sectionTitle", "exactText", "documentId",
        "documentSha256", "sourcePath", "officialUrl", "htmlAnchor", "pdfPage", "bbox",
        "provenance",
    )
    identities = {
        json.dumps({key: item.get(key) for key in provenance_fields}, sort_keys=True)
        for _, item in matches
    }
    if len(identities) > 1:
        raise RuntimeError(f"evidence ID resolves to conflicting records: {evidence_id}")
    return matches[0]
