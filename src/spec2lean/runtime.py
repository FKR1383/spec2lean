"""Runtime transport only; phase prompts, tools and artifact owners stay in Python."""
from __future__ import annotations

import json
import os
import signal
import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable


@contextmanager
def runtime_selection(name: str | None):
    previous = os.environ.get("SPEC2LEAN_RUNTIME")
    try:
        if name is not None:
            os.environ["SPEC2LEAN_RUNTIME"] = name
        runtime_name()
        yield
    finally:
        if previous is None:
            os.environ.pop("SPEC2LEAN_RUNTIME", None)
        else:
            os.environ["SPEC2LEAN_RUNTIME"] = previous


def runtime_name() -> str:
    name = os.environ.get("SPEC2LEAN_RUNTIME", "rust-harness")
    if name not in {"rust-harness", "opencode"}:
        raise ValueError("SPEC2LEAN_RUNTIME must be rust-harness or opencode")
    return name


def is_rust(executable: str) -> bool:
    return Path(executable).name == "spec2lean-harness"


def runtime_executable() -> str:
    if runtime_name() == "opencode":
        executable = shutil.which("opencode")
        if executable:
            return executable
        raise RuntimeError("OpenCode executable is not installed or not on PATH")
    executable = shutil.which("spec2lean-harness")
    if executable:
        return executable
    root = Path(__file__).resolve().parents[2] / "harness" / "target"
    for profile in ("release", "debug"):
        candidate = root / profile / "spec2lean-harness"
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    raise RuntimeError(
        "Rust harness is not built; run cargo build --release --manifest-path harness/Cargo.toml "
        "(or select SPEC2LEAN_RUNTIME=opencode for the legacy runtime)"
    )


def run_session(command: list[str], *, run_command: Callable[..., Any], **kwargs: Any):
    """Translate main's existing session configuration into the Rust protocol.

    Custom command runners receive the selected runtime's protocol. A real Rust
    session gets its own process group so timeout/interrupt also stops its MCP
    workers and provider, before temporary artifact inputs are removed.
    """
    if not is_rust(command[0]):
        return run_command(command, **kwargs)
    environment = kwargs["env"].copy()
    config = json.loads(environment.pop("OPENCODE_CONFIG_CONTENT"))
    agent = config["agent"][config["default_agent"]]
    servers = [s for s in config["mcp"].values() if s.get("enabled", True)]
    if len(servers) != 1:
        raise ValueError("a phase session must have exactly one bounded MCP server")
    request = {
        "prompt": command[-1],
        "model": agent["model"],
        "reasoning": agent["variant"],
        "max_steps": agent["steps"],
        "timeout_seconds": kwargs["timeout"],
        "tool_timeout_ms": servers[0].get("timeout", 15000),
        "mcp_command": servers[0]["command"],
    }
    environment["SPEC2LEAN_RUNTIME"] = "rust-harness"
    if run_command is not subprocess.run:
        return run_command([command[0]], input=json.dumps(request), **{**kwargs, "env": environment})
    process = subprocess.Popen(
        [command[0]], cwd=kwargs.get("cwd"), env=environment,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, start_new_session=True,
    )

    def stop() -> tuple[str, str]:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        return process.communicate()

    try:
        stdout, stderr = process.communicate(json.dumps(request), timeout=kwargs["timeout"])
    except subprocess.TimeoutExpired as exc:
        stdout, stderr = stop()
        # Popen's timeout exception can hold bytes even in text mode. Main's
        # session artifacts require strings, including on timeout.
        raise subprocess.TimeoutExpired(command, kwargs["timeout"], output=stdout, stderr=stderr) from exc
    except BaseException:
        stop()
        raise
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
