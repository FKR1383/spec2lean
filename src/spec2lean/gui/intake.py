"""Run GUI work in a separate process so requests stay responsive."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

from ..intake import intake_path, list_intakes, load_intake
from ..pipeline.runner import PHASES, _write_json_atomic, utc_now


class IntakeJobs:
    def __init__(self, workspace: Path):
        self.workspace = workspace.resolve()
        self._lock = threading.Lock()
        self._process: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._active_id: str | None = None
        self._closed = False

    def list(self) -> list[dict[str, Any]]:
        return [self.get(item["id"]) for item in list_intakes(self.workspace)]

    def get(self, intake_id: str) -> dict[str, Any]:
        record = load_intake(self.workspace, intake_id)
        log = intake_path(self.workspace, intake_id).with_name("progress.log")
        if log.is_file():
            with log.open("rb") as handle:
                handle.seek(max(0, log.stat().st_size - 24000))
                record["log"] = handle.read().decode("utf-8", errors="replace")
        if self._active_id == intake_id and self._process and self._process.poll() is None and record["status"] != "RUNNING":
            record["status"] = "QUEUED"
        if record["status"] == "RUNNING" and record.get("workerPid"):
            try:
                os.kill(record["workerPid"], 0)
            except ProcessLookupError:
                record.update(status="INTERRUPTED", error="The GUI worker stopped. Start again to continue from saved artifacts.")
            except PermissionError:
                pass
        return record

    def start(self, intake_id: str, *, until: str = "index", runtime: str = "rust-harness", mode: str = "lexical") -> dict[str, Any]:
        if until not in PHASES or runtime not in {"rust-harness", "opencode"} or mode not in {"lexical", "semantic"}:
            raise ValueError("invalid pipeline phase, runtime, or index mode")
        with self._lock:
            if self._closed:
                raise RuntimeError("The GUI server is shutting down")
            if self._active_id is not None:
                raise RuntimeError("A pipeline job is already running in this GUI. Wait for it to finish.")
            record = load_intake(self.workspace, intake_id)
            if self.get(intake_id)["status"] == "RUNNING":
                raise RuntimeError("This specification is already running")
            command = [sys.executable, "-m", "spec2lean", "start", intake_id, "--workspace", str(self.workspace),
                       "--until", until, "--runtime", runtime, "--index-mode", mode]
            directory = intake_path(self.workspace, intake_id).parent
            env = os.environ.copy()
            source_root = str(Path(__file__).resolve().parents[2])
            env["PYTHONPATH"] = source_root + os.pathsep + env.get("PYTHONPATH", "")
            with (directory / "progress.log").open("wb") as stderr, (directory / "result.json").open("wb") as stdout:
                process = subprocess.Popen(command, stdout=stdout, stderr=stderr, env=env, start_new_session=True)
            self._process = process
            self._active_id = intake_id
            self._thread = threading.Thread(target=self._finish, args=(intake_id, process), daemon=True)
            self._thread.start()
            # The child owns persistent state; report queued work until it writes RUNNING.
            return {**record, "status": "QUEUED"}

    def _finish(self, intake_id: str, process: subprocess.Popen) -> None:
        code = process.wait()
        with self._lock:
            record = load_intake(self.workspace, intake_id)
            if code != 0 and record["status"] not in {"FAILED", "INTERRUPTED"} and record.get("workerPid") in {None, process.pid}:
                record.update(status="FAILED", error=f"Pipeline process exited with code {code}. See the progress log.", updatedAt=utc_now())
                _write_json_atomic(intake_path(self.workspace, intake_id), record)
            self._active_id = None
            self._process = None

    def close(self) -> None:
        with self._lock:
            self._closed = True
            process = self._process
        if process and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=5)
            except ProcessLookupError:
                pass
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        if self._thread:
            self._thread.join(timeout=5)
