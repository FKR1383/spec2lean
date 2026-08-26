from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..evidence.runner import unit_directory_name


def translations_run_root(root: Path, plan: dict[str, Any]) -> Path:
    return root.resolve() / str(plan["language"]).casefold() / str(plan["version"]) / str(plan["planRunId"])


def unit_directory(root: Path, plan: dict[str, Any], unit: dict[str, Any]) -> Path:
    return translations_run_root(root, plan) / unit_directory_name(unit)


def load_translation(
    root: Path, plan: dict[str, Any], unit_id: str
) -> tuple[Path, str, dict[str, Any], dict[str, Any]]:
    units = [item for item in plan.get("requestedUnits", []) if item.get("unitId") == unit_id]
    if len(units) != 1:
        raise KeyError(f"unit is not uniquely present in plan: {unit_id}")
    directory = unit_directory(root, plan, units[0])
    lean_path = directory / "Unit.lean"
    manifest_path = directory / "translation-manifest.json"
    run_path = directory / "translator-run.json"
    if not lean_path.is_file() or not manifest_path.is_file() or not run_path.is_file():
        raise FileNotFoundError(f"complete translation artifact does not exist for unit: {unit_id}")
    return (
        directory,
        lean_path.read_text(encoding="utf-8"),
        json.loads(manifest_path.read_text(encoding="utf-8")),
        json.loads(run_path.read_text(encoding="utf-8")),
    )


def find_declaration(root: Path, declaration: str) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    matches: list[tuple[Path, dict[str, Any], dict[str, Any]]] = []
    for path in root.resolve().glob("*/*/*/*/translation-manifest.json"):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        for mapping in manifest.get("declarations", []):
            if mapping.get("declaration") == declaration:
                matches.append((path, manifest, mapping))
    if not matches:
        raise FileNotFoundError(f"Lean declaration was not found in translation manifests: {declaration}")
    if len(matches) > 1:
        raise RuntimeError(f"Lean declaration is ambiguous across translation manifests: {declaration}")
    return matches[0]


def shared_lean_sources(root: Path, plan: dict[str, Any]) -> list[dict[str, str]]:
    shared = root.resolve() / str(plan["language"]).casefold() / str(plan["version"]) / "shared"
    if not shared.is_dir():
        return []
    return [
        {"path": path.relative_to(shared).as_posix(), "source": path.read_text(encoding="utf-8")}
        for path in sorted(shared.rglob("*.lean"))
        if path.is_file()
    ]
