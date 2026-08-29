from __future__ import annotations

import hashlib
import json
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable

from ..evidence.store import load_unit_bundle
from ..semantics.store import load_semantics
from ..translation.groups import group_for_unit, grouped_units
from ..translation.store import load_group_translation, load_translation
from ..util import canonical_json
from .build import run_build_test
from .logical import group_coverage_test, group_traceability_test, logical_tests
from .models import check_result
from .render import render_markdown
from .store import unit_directory


BuildRunner = Callable[..., dict[str, Any]]


def _write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent, text=True
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _load_referenced_core(
    translations_root: Path, plan: dict[str, Any], manifest: dict[str, Any]
) -> Any | None:
    reference = manifest.get("sharedCore")
    if reference is None:
        if manifest.get("sharedUses"):
            raise ValueError("translation manifest has sharedUses without a sharedCore reference")
        return None
    if not isinstance(reference, dict):
        raise ValueError("translation manifest sharedCore reference must be an object")
    required = ("coreRunId", "sourceHash", "manifestHash", "leanModule")
    missing = [field for field in required if not isinstance(reference.get(field), str)]
    if missing:
        raise ValueError(f"translation manifest sharedCore reference is missing: {', '.join(missing)}")

    # Kept lazy so historical Phase-6 checks remain importable without loading
    # any Phase-5 shared-core implementation.
    from ..translation.shared_core import load_core

    core = load_core(translations_root, plan, str(reference["coreRunId"]))
    observed = {
        "coreRunId": getattr(core, "core_run_id", None),
        "sourceHash": getattr(core, "source_hash", None),
        "manifestHash": getattr(core, "manifest_hash", None),
        "leanModule": getattr(core, "lean_module", None),
    }
    mismatches = [
        field for field in required if observed[field] != reference[field]
    ]
    if mismatches:
        raise ValueError(
            "translation manifest sharedCore reference does not match the frozen core: "
            + ", ".join(mismatches)
        )
    return core


def run_checks(
    plan: dict[str, Any],
    *,
    evidence_root: Path,
    semantics_root: Path,
    translations_root: Path,
    checks_root: Path,
    database: Path,
    unit_id: str,
    build_runner: BuildRunner = run_build_test,
) -> tuple[Path, dict[str, Any]]:
    try:
        _, _, manifest, _ = load_translation(translations_root, plan, unit_id)
    except FileNotFoundError:
        raise
    if manifest.get("schemaVersion") in {2, 3, 4}:
        results = run_group_checks(
            plan,
            evidence_root=evidence_root,
            semantics_root=semantics_root,
            translations_root=translations_root,
            checks_root=checks_root,
            database=database,
            group=group_for_unit(plan, unit_id),
            build_runner=build_runner,
        )
        return results[unit_id]

    # Historical schema-v1 artifacts remain inspectable and checkable.
    units = [item for item in plan.get("requestedUnits", []) if item.get("unitId") == unit_id]
    if len(units) != 1:
        raise KeyError(f"unit is not uniquely present in plan: {unit_id}")
    _, bundle = load_unit_bundle(evidence_root, plan, unit_id)
    _, semantics = load_semantics(semantics_root, plan, unit_id)
    translation_directory, source, manifest, _ = load_translation(
        translations_root, plan, unit_id
    )
    lean_file = translation_directory / str(manifest.get("leanFile", "Unit.lean"))
    if not lean_file.is_file():
        raise FileNotFoundError(f"translated Lean file does not exist: {lean_file}")
    if not database.is_file():
        raise FileNotFoundError(f"Phase-1 source database does not exist: {database}")

    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="spec2lean-check") as executor:
        build_future = executor.submit(build_runner, lean_file)
        logical_future = executor.submit(
            logical_tests, plan, bundle, semantics, source, manifest, database
        )
        build = build_future.result()
        coverage, traceability = logical_future.result()

    result = check_result(
        plan=plan,
        unit=units[0],
        translation_run_id=str(manifest.get("translationRunId", "")),
        build=build,
        coverage=coverage,
        traceability=traceability,
        input_hashes={
            "semantics": "sha256:" + hashlib.sha256(canonical_json(semantics).encode("utf-8")).hexdigest(),
            "leanSource": "sha256:" + hashlib.sha256(source.encode("utf-8")).hexdigest(),
            "translationManifest": "sha256:" + hashlib.sha256(canonical_json(manifest).encode("utf-8")).hexdigest(),
        },
    )
    output = unit_directory(checks_root, plan, units[0])
    output.mkdir(parents=True, exist_ok=True)
    _write_atomic(
        output / "check.json",
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    _write_atomic(output / "check.md", render_markdown(result))
    return output, result


def run_group_checks(
    plan: dict[str, Any],
    *,
    evidence_root: Path,
    semantics_root: Path,
    translations_root: Path,
    checks_root: Path,
    database: Path,
    group: str,
    build_runner: BuildRunner = run_build_test,
) -> dict[str, tuple[Path, dict[str, Any]]]:
    units = grouped_units(plan).get(group, [])
    if not units:
        raise KeyError(f"translation group is not present in plan: {group}")
    translation_directory, source, manifest, _ = load_group_translation(
        translations_root, plan, group
    )
    if manifest.get("schemaVersion") not in {2, 3, 4}:
        raise ValueError(
            f"group checking requires a schema-v2, schema-v3, or schema-v4 translation manifest: {group}"
        )
    lean_file = translation_directory / str(manifest.get("leanFile", f"{group}.lean"))
    if not lean_file.is_file():
        raise FileNotFoundError(f"translated Lean file does not exist: {lean_file}")
    if not database.is_file():
        raise FileNotFoundError(f"Phase-1 source database does not exist: {database}")

    bundles_by_unit: dict[str, dict[str, Any]] = {}
    semantics_by_unit: dict[str, dict[str, Any]] = {}
    for unit in units:
        unit_id = str(unit["unitId"])
        _, bundles_by_unit[unit_id] = load_unit_bundle(evidence_root, plan, unit_id)
        _, semantics_by_unit[unit_id] = load_semantics(semantics_root, plan, unit_id)

    core = _load_referenced_core(translations_root, plan, manifest)
    build_dependencies = (
        [(str(core.lean_module), Path(core.source_path))] if core is not None else None
    )

    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="spec2lean-group-check") as executor:
        if build_dependencies is None:
            build_future = executor.submit(build_runner, lean_file)
        else:
            build_future = executor.submit(
                build_runner, lean_file, dependency_modules=build_dependencies
            )
        traceability_future = executor.submit(
            group_traceability_test,
            plan,
            bundles_by_unit,
            semantics_by_unit,
            source,
            manifest,
            database,
            core_source=core.source if core is not None else None,
            core_manifest=core.manifest if core is not None else None,
        )
        build = build_future.result()
        traceability = traceability_future.result()

    source_hash = "sha256:" + hashlib.sha256(source.encode("utf-8")).hexdigest()
    manifest_hash = "sha256:" + hashlib.sha256(
        canonical_json(manifest).encode("utf-8")
    ).hexdigest()
    shared_hashes = (
        {
            "sharedCoreSource": str(core.source_hash),
            "sharedCoreManifest": str(core.manifest_hash),
        }
        if core is not None else {}
    )
    results: dict[str, tuple[Path, dict[str, Any]]] = {}
    for unit in units:
        unit_id = str(unit["unitId"])
        semantics = semantics_by_unit[unit_id]
        coverage = group_coverage_test(
            unit_id,
            semantics,
            source,
            manifest,
            core_source=core.source if core is not None else None,
            core_manifest=core.manifest if core is not None else None,
        )
        result = check_result(
            plan=plan,
            unit=unit,
            translation_run_id=str(manifest.get("translationRunId", "")),
            build=build,
            coverage=coverage,
            traceability=traceability,
            input_hashes={
                "semantics": "sha256:" + hashlib.sha256(
                    canonical_json(semantics).encode("utf-8")
                ).hexdigest(),
                "leanSource": source_hash,
                "translationManifest": manifest_hash,
                **shared_hashes,
            },
        )
        output = unit_directory(checks_root, plan, unit)
        output.mkdir(parents=True, exist_ok=True)
        _write_atomic(
            output / "check.json",
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )
        _write_atomic(output / "check.md", render_markdown(result))
        results[unit_id] = (output, result)
    return results
