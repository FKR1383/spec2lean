from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Callable


LEAN_DIAGNOSTIC = re.compile(
    r"^(?P<file>.*?):(?P<line>\d+):(?P<column>\d+):\s*"
    r"(?:(?:error|warning)(?:\([^)]*\))?:\s*)?(?P<message>.*)$"
)

LEAN_MODULE_SEGMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_']*$")


def _diagnostics(stdout: str, stderr: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for stream, content in (("stdout", stdout), ("stderr", stderr)):
        current: dict[str, Any] | None = None
        for text in content.splitlines():
            item: dict[str, Any] = {"stream": stream, "message": text}
            match = LEAN_DIAGNOSTIC.match(text)
            if match:
                if current is not None:
                    result.append(current)
                item.update({
                    "file": match.group("file"),
                    "line": int(match.group("line")),
                    "column": int(match.group("column")),
                    "message": match.group("message"),
                })
            lowered = text.casefold()
            if "error" in lowered:
                item["severity"] = "ERROR"
            elif "warning" in lowered:
                item["severity"] = "WARNING"
            else:
                item["severity"] = "INFO"
            if match:
                current = item
            elif current is not None:
                current["message"] += "\n" + text
            else:
                result.append(item)
        if current is not None:
            result.append(current)
    return result


def run_build_test(
    lean_file: Path,
    *,
    dependency_modules: list[tuple[str, Path]] | None = None,
    lean_executable: str = "lean",
    run_command: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    executable = shutil.which(lean_executable) if not Path(lean_executable).is_absolute() else lean_executable
    if executable and Path(executable).is_absolute() and not Path(executable).is_file():
        executable = None
    if not executable:
        return {
            "status": "FAIL",
            "exitCode": 127,
            "leanVersion": None,
            "durationMs": 0,
            "diagnostics": [{
                "stream": "stderr",
                "severity": "ERROR",
                "message": f"Lean executable was not found: {lean_executable}",
            }],
        }

    version_run = run_command(
        [executable, "--version"], text=True, capture_output=True, check=False
    )
    version_output = (version_run.stdout or version_run.stderr).strip()
    lean_version = version_output.splitlines()[0] if version_output else None
    environment = os.environ.copy()
    started = monotonic()

    # Preserve the historical one-file command exactly when there are no
    # imported generated modules. Besides compatibility, this keeps ordinary
    # Phase-6 diagnostics located in the published translation directory.
    if not dependency_modules:
        completed = run_command(
            [executable, lean_file.name],
            cwd=str(lean_file.parent),
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )
        duration_ms = max(0, round((monotonic() - started) * 1000))
        return {
            "status": "PASS" if completed.returncode == 0 else "FAIL",
            "exitCode": completed.returncode,
            "leanVersion": lean_version,
            "durationMs": duration_ms,
            "diagnostics": _diagnostics(completed.stdout, completed.stderr),
        }

    diagnostics: list[dict[str, Any]] = []
    seen_modules: set[str] = set()
    with tempfile.TemporaryDirectory(prefix="spec2lean-check-build-") as temporary_name:
        temporary = Path(temporary_name)
        existing_lean_path = environment.get("LEAN_PATH")
        environment["LEAN_PATH"] = (
            str(temporary)
            if not existing_lean_path
            else str(temporary) + os.pathsep + existing_lean_path
        )
        staged_dependencies: list[tuple[Path, Path]] = []
        for module_name, source_path in dependency_modules:
            segments = module_name.split(".")
            if (
                not segments
                or any(not LEAN_MODULE_SEGMENT.fullmatch(segment) for segment in segments)
                or module_name in seen_modules
            ):
                duration_ms = max(0, round((monotonic() - started) * 1000))
                return {
                    "status": "FAIL",
                    "exitCode": 2,
                    "leanVersion": lean_version,
                    "durationMs": duration_ms,
                    "diagnostics": [{
                        "stream": "stderr",
                        "severity": "ERROR",
                        "message": f"invalid or duplicate Lean dependency module: {module_name}",
                    }],
                }
            if not source_path.is_file():
                duration_ms = max(0, round((monotonic() - started) * 1000))
                return {
                    "status": "FAIL",
                    "exitCode": 2,
                    "leanVersion": lean_version,
                    "durationMs": duration_ms,
                    "diagnostics": [{
                        "stream": "stderr",
                        "severity": "ERROR",
                        "message": f"Lean dependency source does not exist: {source_path}",
                    }],
                }
            seen_modules.add(module_name)
            relative_source = Path(*segments).with_suffix(".lean")
            staged_source = temporary / relative_source
            staged_source.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, staged_source)
            staged_dependencies.append((relative_source, relative_source.with_suffix(".olean")))

        staged_unit = temporary / lean_file.name
        shutil.copy2(lean_file, staged_unit)
        completed: subprocess.CompletedProcess[str] | None = None
        for relative_source, relative_olean in staged_dependencies:
            completed = run_command(
                [
                    executable,
                    "-R",
                    str(temporary),
                    "-o",
                    str(relative_olean),
                    str(relative_source),
                ],
                cwd=str(temporary),
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )
            diagnostics.extend(_diagnostics(completed.stdout, completed.stderr))
            if completed.returncode != 0:
                break
        else:
            completed = run_command(
                [executable, "-R", str(temporary), staged_unit.name],
                cwd=str(temporary),
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )
            diagnostics.extend(_diagnostics(completed.stdout, completed.stderr))

    assert completed is not None
    duration_ms = max(0, round((monotonic() - started) * 1000))
    return {
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "exitCode": completed.returncode,
        "leanVersion": lean_version,
        "durationMs": duration_ms,
        "diagnostics": diagnostics,
    }
