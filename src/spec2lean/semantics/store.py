from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..evidence.runner import unit_directory_name


def semantics_run_root(root: Path, plan: dict[str, Any]) -> Path:
    return root.resolve() / str(plan["language"]).casefold() / str(plan["version"]) / str(plan["planRunId"])


def unit_directory(root: Path, plan: dict[str, Any], unit: dict[str, Any]) -> Path:
    return semantics_run_root(root, plan) / unit_directory_name(unit)


def load_semantics(root: Path, plan: dict[str, Any], unit_id: str) -> tuple[Path, dict[str, Any]]:
    units = [item for item in plan.get("requestedUnits", []) if item.get("unitId") == unit_id]
    if len(units) != 1:
        raise KeyError(f"unit is not uniquely present in plan: {unit_id}")
    directory = unit_directory(root, plan, units[0])
    path = directory / "semantics.json"
    if not path.is_file():
        raise FileNotFoundError(f"semantic artifact does not exist for unit: {unit_id}")
    return directory, json.loads(path.read_text(encoding="utf-8"))


def artifacts(root: Path, plan: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    run_root = semantics_run_root(root, plan)
    if not run_root.is_dir():
        return result
    for directory in sorted(path for path in run_root.iterdir() if path.is_dir()):
        semantics_path, metadata_path = directory / "semantics.json", directory / "extractor-run.json"
        result.append({
            "directory": directory,
            "artifact": json.loads(semantics_path.read_text(encoding="utf-8")) if semantics_path.is_file() else None,
            "metadata": json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.is_file() else {},
        })
    return result


def find_claim(root: Path, claim_id: str) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    matches = []
    for path in root.resolve().glob("*/*/*/*/semantics.json"):
        artifact = json.loads(path.read_text(encoding="utf-8"))
        for claim in (artifact.get("semantics") or {}).get("claims", []):
            if claim.get("claimId") == claim_id:
                matches.append((path, artifact, claim))
    if not matches:
        raise FileNotFoundError(f"semantic claim was not found: {claim_id}")
    if len(matches) > 1:
        raise RuntimeError(f"semantic claim ID is ambiguous: {claim_id}")
    return matches[0]
