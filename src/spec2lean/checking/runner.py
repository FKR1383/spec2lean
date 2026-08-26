from __future__ import annotations

import json
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable

from ..evidence.store import load_unit_bundle
from ..semantics.store import load_semantics
from ..translation.store import load_translation
from .build import run_build_test
from .logical import logical_tests
from .models import check_result
from .render import render_markdown
from .store import unit_directory


BuildRunner = Callable[[Path], dict[str, Any]]


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
    )
    output = unit_directory(checks_root, plan, units[0])
    output.mkdir(parents=True, exist_ok=True)
    _write_atomic(
        output / "check.json",
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    _write_atomic(output / "check.md", render_markdown(result))
    return output, result
