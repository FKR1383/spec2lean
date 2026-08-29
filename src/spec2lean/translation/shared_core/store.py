from __future__ import annotations

import fcntl
import json
import os
import re
import shutil
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Any, Iterator

from .models import FrozenSharedCore, json_hash, text_hash


CORE_RUN_ID = re.compile(r"^shared-core-run:[0-9a-f]{24}$")
ADDRESSED_MANIFEST_FIELDS = {
    "schemaVersion", "phase", "language", "version", "sourceDatabaseDigest",
    "representationSchemaVersion", "generator", "target", "leanFile",
    "leanModule", "leanNamespace", "sourceHash", "concepts", "declarations",
}
_LOCKS_GUARD = threading.Lock()
_THREAD_LOCKS: dict[str, threading.Lock] = {}


def shared_root(root: Path, plan: dict[str, Any]) -> Path:
    return (
        root.resolve()
        / str(plan["language"]).casefold()
        / str(plan["version"])
        / "shared"
    )


def versions_root(root: Path, plan: dict[str, Any]) -> Path:
    return shared_root(root, plan) / "versions"


def core_directory(root: Path, plan: dict[str, Any], core_run_id: str) -> Path:
    if not CORE_RUN_ID.fullmatch(core_run_id):
        raise ValueError(f"invalid shared-core run ID: {core_run_id!r}")
    return versions_root(root, plan) / core_run_id


def _safe_source_path(directory: Path, relative: Any) -> Path:
    if not isinstance(relative, str):
        raise ValueError("shared-core manifest leanFile must be text")
    value = PurePosixPath(relative)
    if value.is_absolute() or ".." in value.parts or not value.parts:
        raise ValueError("shared-core manifest leanFile must be a safe relative path")
    if value.suffix != ".lean" or value.parts[0] != "modules":
        raise ValueError("shared-core Lean source must live below modules/ and end in .lean")
    return directory.joinpath(*value.parts)


def _load_core(
    root: Path, plan: dict[str, Any], core_run_id: str, *, reused: bool,
    require_identity: bool,
) -> FrozenSharedCore:
    directory = core_directory(root, plan, core_run_id)
    manifest_path = directory / "core-manifest.json"
    run_path = directory / "core-run.json"
    if not manifest_path.is_file() or not run_path.is_file():
        raise FileNotFoundError(f"complete shared-core artifact does not exist: {core_run_id}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"shared-core manifest is invalid JSON: {manifest_path}") from exc
    if not isinstance(manifest, dict):
        raise ValueError(f"shared-core manifest must be a JSON object: {manifest_path}")
    if manifest.get("coreRunId") != core_run_id:
        raise ValueError("shared-core directory and manifest run IDs differ")
    if require_identity and (
        manifest.get("language") != plan.get("language")
        or manifest.get("version") != plan.get("version")
        or manifest.get("sourceDatabaseDigest") != plan.get("sourceDatabaseDigest")
    ):
        raise ValueError("shared-core artifact belongs to another specification identity")
    source_path = _safe_source_path(directory, manifest.get("leanFile"))
    if not source_path.is_file():
        raise FileNotFoundError(f"shared-core Lean source does not exist: {source_path}")
    source = source_path.read_text(encoding="utf-8")
    source_hash = text_hash(source)
    if source_hash != manifest.get("sourceHash"):
        raise ValueError("shared-core Lean source hash does not match its manifest")
    lean_module = manifest.get("leanModule")
    if not isinstance(lean_module, str) or not lean_module:
        raise ValueError("shared-core manifest has no Lean module name")
    module_path = "/".join(lean_module.split(".")) + ".lean"
    if str(PurePosixPath(str(manifest["leanFile"])).relative_to("modules")) != module_path:
        raise ValueError("shared-core leanFile does not match leanModule")
    return FrozenSharedCore(
        directory=directory,
        source_path=source_path,
        manifest_path=manifest_path,
        run_path=run_path,
        source=source,
        manifest=manifest,
        core_run_id=core_run_id,
        lean_module=lean_module,
        source_hash=source_hash,
        manifest_hash=json_hash(manifest),
        reused=reused,
    )


def load_core(
    root: Path, plan: dict[str, Any], core_run_id: str, *, reused: bool = True
) -> FrozenSharedCore:
    """Load an explicitly referenced snapshot for the exact specification identity."""
    return _load_core(
        root, plan, core_run_id, reused=reused, require_identity=True
    )


def load_current_core(
    root: Path, plan: dict[str, Any]
) -> FrozenSharedCore | None:
    pointer_path = shared_root(root, plan) / "current.json"
    if not pointer_path.is_file():
        return None
    try:
        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"shared-core current pointer is invalid JSON: {pointer_path}") from exc
    if not isinstance(pointer, dict):
        raise ValueError("shared-core current pointer must be a JSON object")
    if set(pointer) != {
        "schemaVersion", "coreRunId", "manifestHash", "sourceHash", "leanModule"
    } or pointer.get("schemaVersion") != 1:
        raise ValueError("shared-core current pointer is malformed")
    # The language/version pointer intentionally spans source-database revisions.
    # Load its immutable target before applying freshness checks so callers can
    # diagnose and replace a snapshot whose source identity is now stale.
    core = _load_core(
        root, plan, str(pointer.get("coreRunId")), reused=True,
        require_identity=False,
    )
    if pointer != {"schemaVersion": 1, **core.reference()}:
        raise ValueError("shared-core current pointer does not match its immutable snapshot")
    return core


def activate_core(
    root: Path, plan: dict[str, Any], core: FrozenSharedCore
) -> FrozenSharedCore:
    """Atomically point current.json at an already-published immutable snapshot."""
    loaded = load_core(root, plan, core.core_run_id, reused=True)
    if loaded.reference() != core.reference():
        raise ValueError("shared-core recovery candidate changed while being activated")
    pointer = {"schemaVersion": 1, **loaded.reference()}
    _write_atomic(
        shared_root(root, plan) / "current.json",
        json.dumps(pointer, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return loaded


def _write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


@contextmanager
def core_lock(root: Path, plan: dict[str, Any]) -> Iterator[None]:
    base = shared_root(root, plan)
    base.mkdir(parents=True, exist_ok=True)
    lock_path = base / ".core.lock"
    key = str(lock_path)
    with _LOCKS_GUARD:
        thread_lock = _THREAD_LOCKS.setdefault(key, threading.Lock())
    with thread_lock:
        with lock_path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def publish_core(
    root: Path,
    plan: dict[str, Any],
    source: str,
    manifest: dict[str, Any],
    run_metadata: dict[str, Any],
) -> FrozenSharedCore:
    """Publish under ``core_lock``; immutable destinations are never overwritten."""
    core_run_id = str(manifest["coreRunId"])
    destination = core_directory(root, plan, core_run_id)
    versions = versions_root(root, plan)
    versions.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".publishing-", dir=versions))
    try:
        source_path = _safe_source_path(temporary, manifest["leanFile"])
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text(source, encoding="utf-8")
        (temporary / "core-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (temporary / "core-run.json").write_text(
            json.dumps(run_metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if destination.exists():
            existing = load_core(root, plan, core_run_id)
            # Attempt timestamps, parent lineage, and historical Phase-4 artifact
            # records are provenance rather than representation identity.  A lost
            # pointer, or a later semantically equivalent Phase-4 run, may address
            # the same frozen source/registry. Reuse that snapshot and repair only
            # current.json; never rewrite its original provenance.
            existing_content = {
                field: existing.manifest.get(field)
                for field in ADDRESSED_MANIFEST_FIELDS
            }
            candidate_content = {
                field: manifest.get(field)
                for field in ADDRESSED_MANIFEST_FIELDS
            }
            if existing_content != candidate_content or existing.source != source:
                raise RuntimeError(f"content-addressed shared-core collision: {core_run_id}")
        else:
            os.replace(temporary, destination)
        core = load_core(root, plan, core_run_id, reused=False)
        pointer = {"schemaVersion": 1, **core.reference()}
        _write_atomic(
            shared_root(root, plan) / "current.json",
            json.dumps(pointer, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )
        return core
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
