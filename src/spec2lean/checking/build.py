from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable


LEAN_DIAGNOSTIC = re.compile(
    r"^(?P<file>.*?):(?P<line>\d+):(?P<column>\d+):\s*"
    r"(?:(?:error|warning)(?:\([^)]*\))?:\s*)?(?P<message>.*)$"
)


def _diagnostics(stdout: str, stderr: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for stream, content in (("stdout", stdout), ("stderr", stderr)):
        for text in content.splitlines():
            item: dict[str, Any] = {"stream": stream, "message": text}
            match = LEAN_DIAGNOSTIC.match(text)
            if match:
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
            result.append(item)
    return result


def run_build_test(
    lean_file: Path,
    *,
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
    shared_root = lean_file.parents[2] / "shared"
    if shared_root.is_dir():
        prior_lean_path = environment.get("LEAN_PATH")
        environment["LEAN_PATH"] = os.pathsep.join(
            [str(shared_root), *([prior_lean_path] if prior_lean_path else [])]
        )
    started = monotonic()
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
