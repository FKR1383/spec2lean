from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..evidence.runner import unit_directory_name
from .groups import group_for_unit


def translations_run_root(root: Path, plan: dict[str, Any]) -> Path:
    return root.resolve() / str(plan["language"]).casefold() / str(plan["version"]) / str(plan["planRunId"])


def group_directory(root: Path, plan: dict[str, Any], group: str) -> Path:
    return translations_run_root(root, plan) / group


def legacy_unit_directory(root: Path, plan: dict[str, Any], unit: dict[str, Any]) -> Path:
    """Locate a schema-v1 per-unit artifact without treating it as reusable Phase 5."""
    return translations_run_root(root, plan) / unit_directory_name(unit)


def unit_directory(root: Path, plan: dict[str, Any], unit: dict[str, Any]) -> Path:
    """Compatibility locator: grouped Phase-5 artifacts are addressed through any member unit."""
    return group_directory(root, plan, group_for_unit(plan, str(unit["unitId"])))


def load_group_translation(
    root: Path, plan: dict[str, Any], group: str
) -> tuple[Path, str, dict[str, Any], dict[str, Any]]:
    directory = group_directory(root, plan, group)
    manifest_path = directory / "translation-manifest.json"
    run_path = directory / "translator-run.json"
    if not manifest_path.is_file() or not run_path.is_file():
        raise FileNotFoundError(f"complete translation artifact does not exist for group: {group}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    lean_path = directory / str(manifest.get("leanFile", f"{group}.lean"))
    if not lean_path.is_file():
        raise FileNotFoundError(f"complete translation artifact does not exist for group: {group}")
    return (
        directory,
        lean_path.read_text(encoding="utf-8"),
        manifest,
        json.loads(run_path.read_text(encoding="utf-8")),
    )


def load_translation(
    root: Path, plan: dict[str, Any], unit_id: str
) -> tuple[Path, str, dict[str, Any], dict[str, Any]]:
    try:
        return load_group_translation(root, plan, group_for_unit(plan, unit_id))
    except FileNotFoundError as group_error:
        units = [unit for unit in plan.get("requestedUnits", []) if unit.get("unitId") == unit_id]
        if len(units) != 1:
            raise group_error
        directory = legacy_unit_directory(root, plan, units[0])
        manifest_path = directory / "translation-manifest.json"
        run_path = directory / "translator-run.json"
        if not manifest_path.is_file() or not run_path.is_file():
            raise group_error
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        lean_path = directory / str(manifest.get("leanFile", "Unit.lean"))
        if not lean_path.is_file():
            raise group_error
        return (
            directory,
            lean_path.read_text(encoding="utf-8"),
            manifest,
            json.loads(run_path.read_text(encoding="utf-8")),
        )


def find_declaration(root: Path, declaration: str) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    matches: list[tuple[Path, dict[str, Any], dict[str, Any]]] = []
    paths = list(root.resolve().glob("*/*/*/*/translation-manifest.json"))
    paths.extend(root.resolve().glob("*/*/shared/versions/*/core-manifest.json"))
    for path in paths:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        for mapping in manifest.get("declarations", []):
            if mapping.get("declaration") == declaration:
                matches.append((path, manifest, mapping))
    if not matches:
        raise FileNotFoundError(f"Lean declaration was not found in translation manifests: {declaration}")
    if len(matches) > 1:
        raise RuntimeError(f"Lean declaration is ambiguous across translation manifests: {declaration}")
    return matches[0]
