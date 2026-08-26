from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..evidence.runner import unit_directory_name


def checks_run_root(root: Path, plan: dict[str, Any]) -> Path:
    return (
        root.resolve()
        / str(plan["language"]).casefold()
        / str(plan["version"])
        / str(plan["planRunId"])
    )


def unit_directory(root: Path, plan: dict[str, Any], unit: dict[str, Any]) -> Path:
    return checks_run_root(root, plan) / unit_directory_name(unit)


def load_check(root: Path, plan: dict[str, Any], unit_id: str) -> tuple[Path, dict[str, Any]]:
    units = [item for item in plan.get("requestedUnits", []) if item.get("unitId") == unit_id]
    if len(units) != 1:
        raise KeyError(f"unit is not uniquely present in plan: {unit_id}")
    directory = unit_directory(root, plan, units[0])
    path = directory / "check.json"
    if not path.is_file():
        raise FileNotFoundError(f"check artifact does not exist for unit: {unit_id}")
    return directory, json.loads(path.read_text(encoding="utf-8"))
