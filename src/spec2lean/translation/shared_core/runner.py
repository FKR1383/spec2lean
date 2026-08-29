from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ...checking.build import run_build_test
from ...planning.runner import installed_openai_models
from ..runner import _session_id
from .models import (
    CORE_GENERATOR_AGENT,
    CORE_GENERATOR_MODEL,
    CORE_GENERATOR_REASONING,
    CORE_SCHEMA_VERSION,
    GENERATOR_POLICY_VERSION,
    REPRESENTATION_SCHEMA_VERSION,
    FrozenSharedCore,
    SharedRequirement,
    core_namespace_for,
    core_run_id_for,
    json_hash,
    text_hash,
)
from .prompt import build_core_prompt
from .requirements import collect_shared_requirements
from .store import (
    activate_core,
    core_lock,
    load_core,
    load_current_core,
    publish_core,
    versions_root,
)
from .validation import normalize_core_submission, validate_core_artifact


BuildRunner = Callable[[Path], dict[str, Any]]
RunCommand = Callable[..., subprocess.CompletedProcess[str]]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _module_location(lean_namespace: str, source_hash: str) -> tuple[str, str]:
    token = "C" + source_hash.removeprefix("sha256:")[:16]
    module = ".".join((lean_namespace, token, "Core"))
    return module, "modules/" + "/".join(module.split(".")) + ".lean"


def _empty_source() -> str:
    return "-- This specification has no shared semantic declarations.\n"


def _wrap_root_source(source: str, lean_namespace: str) -> str:
    """Nest declarations under the lineage namespace, keeping Lean imports first."""
    lines = source.rstrip().splitlines()
    header_end = 0
    for index, line in enumerate(lines):
        if line.strip() == "prelude" or line.lstrip().startswith("import "):
            header_end = index + 1
    header, body = lines[:header_end], lines[header_end:]
    wrapped: list[str] = list(header)
    if wrapped and wrapped[-1].strip():
        wrapped.append("")
    wrapped.extend((f"namespace {lean_namespace}", ""))
    wrapped.extend(body)
    if wrapped and wrapped[-1].strip():
        wrapped.append("")
    wrapped.append(f"end {lean_namespace}")
    return "\n".join(wrapped).rstrip() + "\n"


def _isolate_root_candidate(
    plan: dict[str, Any], candidate: dict[str, Any]
) -> tuple[dict[str, Any], str]:
    """Place a new root representation in its content-derived Lean namespace."""
    lean_namespace = core_namespace_for(plan, candidate)

    def qualified(name: str) -> str:
        return f"{lean_namespace}.{name}"

    concepts = []
    for item in candidate["concepts"]:
        value = dict(item)
        value["leanDeclarations"] = [
            qualified(name) for name in item["leanDeclarations"]
        ]
        concepts.append(value)
    declarations = []
    for item in candidate["declarations"]:
        value = dict(item)
        value["declaration"] = qualified(item["declaration"])
        if "supportsDeclarations" in item:
            value["supportsDeclarations"] = [
                qualified(name) for name in item["supportsDeclarations"]
            ]
        declarations.append(value)
    return {
        "leanSource": _wrap_root_source(candidate["leanSource"], lean_namespace),
        "concepts": concepts,
        "declarations": declarations,
    }, lean_namespace


def _core_context(
    plan: dict[str, Any], requirements: tuple[SharedRequirement, ...],
    parent: FrozenSharedCore | None,
) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "specification": {
            "language": plan["language"],
            "version": plan["version"],
            "sourceDatabaseDigest": plan["sourceDatabaseDigest"],
        },
        "requirements": [item.to_dict() for item in requirements],
        "leanNamespace": (
            parent.manifest.get("leanNamespace") if parent is not None else None
        ),
        "parentCore": (
            {"manifest": parent.manifest, "leanSource": parent.source}
            if parent is not None else None
        ),
    }


def _opencode_config(context_path: Path, submission_path: Path) -> dict[str, Any]:
    disabled = {
        name: False for name in (
            "bash", "edit", "write", "read", "glob", "grep", "list", "task",
            "webfetch", "websearch", "todowrite", "skill", "question", "lsp",
        )
    }
    return {
        "default_agent": CORE_GENERATOR_AGENT,
        "share": "disabled",
        "autoupdate": False,
        "formatter": False,
        "lsp": False,
        "mcp": {"shared_core": {
            "type": "local",
            "command": [
                sys.executable, "-m", "spec2lean.translation.shared_core.mcp",
                "--context", str(context_path), "--submission", str(submission_path),
            ],
            "enabled": True,
            "timeout": 15_000,
        }},
        "agent": {CORE_GENERATOR_AGENT: {
            "description": "Phase-4-bounded generic shared Lean core materializer",
            "mode": "primary",
            "model": CORE_GENERATOR_MODEL,
            "variant": CORE_GENERATOR_REASONING,
            "steps": 40,
            "tools": disabled,
            "permission": {"*": "deny", "shared_core_*": "allow"},
        }},
    }


def _require_model(executable: str) -> None:
    models = installed_openai_models(executable)
    if CORE_GENERATOR_MODEL in models:
        return
    available = ", ".join(sorted(models)) or "<none>"
    raise RuntimeError(
        f"required OpenCode shared-core model is unavailable: {CORE_GENERATOR_MODEL}; "
        f"installed OpenAI model IDs: {available}"
    )


def _run_materializer(
    plan: dict[str, Any], requirements: tuple[SharedRequirement, ...],
    parent: FrozenSharedCore | None, *, timeout_seconds: int, run_command: RunCommand,
) -> tuple[dict[str, Any], dict[str, Any]]:
    executable = shutil.which("opencode")
    if executable is None:
        raise RuntimeError("OpenCode executable is not installed or not on PATH")
    _require_model(executable)
    context = _core_context(plan, requirements, parent)
    started_at = utc_now()
    with tempfile.TemporaryDirectory(prefix="spec2lean-shared-core-") as temporary_name:
        temporary = Path(temporary_name)
        context_path = temporary / "context.json"
        submission_path = temporary / "submission.json"
        context_path.write_text(
            json.dumps(context, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
        )
        config = _opencode_config(context_path, submission_path)
        prompt = build_core_prompt(
            plan, requirements, parent.manifest if parent is not None else None
        )
        command = [
            executable, "run", "--pure", "--print-logs", "--log-level", "ERROR",
            "--format", "json", "--agent", CORE_GENERATOR_AGENT,
            "--model", CORE_GENERATOR_MODEL, "--variant", CORE_GENERATOR_REASONING,
            "--title", f"{plan['language']}:{plan['version']}:shared-core", prompt,
        ]
        environment = os.environ.copy()
        environment["OPENCODE_CONFIG_CONTENT"] = json.dumps(config, separators=(",", ":"))
        config_dir, home_dir = temporary / "opencode-config", temporary / "opencode-home"
        config_dir.mkdir()
        home_dir.mkdir()
        environment["OPENCODE_CONFIG_DIR"] = str(config_dir)
        environment["OPENCODE_TEST_HOME"] = str(home_dir)
        environment["OPENCODE_DISABLE_PROJECT_CONFIG"] = "1"
        environment["OPENCODE_DISABLE_EXTERNAL_SKILLS"] = "1"
        environment["OPENCODE_DISABLE_CLAUDE_CODE_SKILLS"] = "1"
        try:
            completed = run_command(
                command, cwd=str(temporary), env=environment, text=True,
                capture_output=True, timeout=timeout_seconds, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            completed = subprocess.CompletedProcess(
                command, 124, exc.stdout or "", exc.stderr or ""
            )
        if completed.returncode == 124:
            raise RuntimeError(f"OpenCode Shared-Core session timed out after {timeout_seconds} seconds")
        if completed.returncode != 0:
            raise RuntimeError(f"OpenCode Shared-Core session exited with status {completed.returncode}")
        if not submission_path.is_file():
            raise RuntimeError("OpenCode Shared-Core session finished without submit_core")
        try:
            raw_candidate = json.loads(submission_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError("OpenCode Shared-Core submission is invalid JSON") from exc

        # The MCP boundary persists the fully normalized candidate rather than the
        # model-facing submission.  Reconstruct the narrow submission here before
        # independently normalizing it, then require byte-meaningful equality with
        # what the MCP accepted.  This keeps the file handoff tamper-evident without
        # asking the input validator to accept its own deterministic output shape.
        concepts = raw_candidate.get("concepts")
        if not isinstance(concepts, list):
            raise RuntimeError("accepted Shared-Core submission has malformed concepts")
        reconstructed = {
            "leanSource": raw_candidate.get("leanSource"),
            "concepts": [
                {
                    "dependencyId": item.get("dependencyId"),
                    "leanDeclarations": item.get("leanDeclarations"),
                }
                if isinstance(item, dict) else item
                for item in concepts
            ],
            "declarations": raw_candidate.get("declarations"),
        }
        candidate, diagnostics = normalize_core_submission(
            requirements, reconstructed, parent=parent,
            lean_namespace=(
                str(parent.manifest["leanNamespace"]) if parent is not None else None
            ),
        )
        if diagnostics or candidate is None:
            raise RuntimeError(
                "accepted Shared-Core submission failed deterministic reconstruction: "
                + "; ".join(item["message"] for item in diagnostics)
            )
        if candidate != raw_candidate:
            raise RuntimeError(
                "accepted Shared-Core submission differs from deterministic reconstruction"
            )
        return candidate, {
            "invoked": True,
            "startedAt": started_at,
            "finishedAt": utc_now(),
            "command": command[:-1] + ["<shared-core-prompt>"],
            "exitCode": completed.returncode,
            "sessionId": _session_id(completed.stdout),
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }


def _semantic_artifacts(
    requirements: tuple[SharedRequirement, ...], parent: FrozenSharedCore | None
) -> list[dict[str, str]]:
    records = [
        dict(item)
        for item in (parent.manifest.get("semanticArtifacts", []) if parent else [])
        if isinstance(item, dict)
    ]
    records.extend(dict(record) for item in requirements for record in item.semantic_artifacts)
    unique = {
        (
            str(item.get("planRunId")), str(item.get("unitId")),
            str(item.get("runId")), str(item.get("artifactHash")),
        ): item
        for item in records
    }
    return [unique[key] for key in sorted(unique)]


def _provisional_core(
    source: str, manifest: dict[str, Any], *, reused: bool = False
) -> FrozenSharedCore:
    placeholder = Path("<candidate-shared-core>")
    return FrozenSharedCore(
        directory=placeholder,
        source_path=placeholder / manifest["leanFile"],
        manifest_path=placeholder / "core-manifest.json",
        run_path=placeholder / "core-run.json",
        source=source,
        manifest=manifest,
        core_run_id=manifest["coreRunId"],
        lean_module=manifest["leanModule"],
        source_hash=manifest["sourceHash"],
        manifest_hash=json_hash(manifest),
        reused=reused,
    )


def _extension_parent(
    plan: dict[str, Any], semantics_by_unit: dict[str, dict[str, Any]],
    current: FrozenSharedCore | None,
) -> FrozenSharedCore | None:
    """Use an immutable parent only for a pure missing-concept extension.

    A changed semantic fingerprint or generator/representation policy starts a new lineage so the
    canonical representation is free to change. The prior snapshot remains immutable and usable by
    translations already bound to it.
    """
    if current is None:
        return None
    diagnostics = validate_core_artifact(plan, semantics_by_unit, current)
    if diagnostics and {item["code"] for item in diagnostics} == {"MISSING_SHARED_CONCEPT"}:
        return current
    return None


def _stored_cores(
    translations_root: Path, plan: dict[str, Any]
) -> tuple[FrozenSharedCore, ...]:
    """Return validly stored snapshots newest-first for pointer recovery."""
    root = versions_root(translations_root, plan)
    if not root.is_dir():
        return ()
    candidates: list[FrozenSharedCore] = []
    for entry in root.iterdir():
        if not entry.is_dir():
            continue
        try:
            candidates.append(load_core(translations_root, plan, entry.name))
        except (FileNotFoundError, KeyError, RuntimeError, ValueError):
            continue
    return tuple(sorted(
        candidates,
        key=lambda core: (
            str(core.manifest.get("createdAt", "")), core.core_run_id
        ),
        reverse=True,
    ))


def ensure_shared_core(
    plan: dict[str, Any],
    semantics_by_unit: dict[str, dict[str, Any]],
    translations_root: Path,
    *,
    timeout_seconds: int = 1800,
    run_command: RunCommand = subprocess.run,
    build_runner: BuildRunner = run_build_test,
) -> FrozenSharedCore:
    """Return one immutable core snapshot, serializing materialization per specification."""
    requirements = collect_shared_requirements(plan, semantics_by_unit)
    with core_lock(translations_root, plan):
        try:
            current = load_current_core(translations_root, plan)
        except (FileNotFoundError, KeyError, RuntimeError, ValueError):
            # A current pointer is only a replaceable index.  A missing, malformed,
            # or internally inconsistent target must not make its immutable sibling
            # versions mutable, and must not prevent a clean rematerialization.
            current = None
        current_diagnostics = (
            validate_core_artifact(plan, semantics_by_unit, current)
            if current is not None else []
        )
        if current is not None and not current_diagnostics:
            return current.with_reused(True)

        stored = _stored_cores(translations_root, plan)
        diagnostics_by_id: dict[str, list[dict[str, str]]] = {}
        for candidate in stored:
            if current is not None and candidate.core_run_id == current.core_run_id:
                diagnostics = current_diagnostics
            else:
                diagnostics = validate_core_artifact(
                    plan, semantics_by_unit, candidate
                )
            diagnostics_by_id[candidate.core_run_id] = diagnostics
            if not diagnostics:
                return activate_core(
                    translations_root, plan, candidate
                ).with_reused(True)

        parent = _extension_parent(plan, semantics_by_unit, current)
        if parent is None:
            for candidate in stored:
                diagnostics = diagnostics_by_id[candidate.core_run_id]
                if diagnostics and {
                    item["code"] for item in diagnostics
                } == {"MISSING_SHARED_CONCEPT"}:
                    parent = candidate
                    break

        if not requirements and parent is None:
            raw_candidate: dict[str, Any] = {
                "leanSource": _empty_source(), "concepts": [], "declarations": [],
            }
            candidate, diagnostics = normalize_core_submission(requirements, raw_candidate)
            if diagnostics or candidate is None:
                raise RuntimeError("deterministic empty shared core failed validation")
            session = {
                "invoked": False, "startedAt": utc_now(), "finishedAt": utc_now(),
                "command": [], "exitCode": 0, "sessionId": None, "stdout": "", "stderr": "",
            }
        else:
            candidate, session = _run_materializer(
                plan, requirements, parent,
                timeout_seconds=timeout_seconds, run_command=run_command,
            )

        if parent is None:
            candidate, lean_namespace = _isolate_root_candidate(plan, candidate)
        else:
            lean_namespace = str(parent.manifest["leanNamespace"])
        source = str(candidate["leanSource"]).rstrip() + "\n"
        source_hash = text_hash(source)
        lean_module, lean_file = _module_location(lean_namespace, source_hash)
        concepts = [dict(item) for item in candidate["concepts"]]
        declarations = [dict(item) for item in candidate["declarations"]]
        core_run_id = core_run_id_for(
            plan, source_hash, concepts, declarations
        )
        created_at = str(session["startedAt"])
        manifest = {
            "schemaVersion": CORE_SCHEMA_VERSION,
            "phase": "SHARED_CORE",
            "language": plan["language"],
            "version": plan["version"],
            "sourceDatabaseDigest": plan["sourceDatabaseDigest"],
            "coreRunId": core_run_id,
            "parentCoreRunId": parent.core_run_id if parent is not None else None,
            "representationSchemaVersion": REPRESENTATION_SCHEMA_VERSION,
            "generator": {
                "provider": "opencode",
                "model": CORE_GENERATOR_MODEL,
                "reasoning": CORE_GENERATOR_REASONING,
                "policyVersion": GENERATOR_POLICY_VERSION,
                "invoked": bool(concepts),
            },
            "target": {"language": "Lean", "version": "4"},
            "leanFile": lean_file,
            "leanModule": lean_module,
            "leanNamespace": lean_namespace,
            "createdAt": created_at,
            "sourceHash": source_hash,
            "concepts": concepts,
            "declarations": declarations,
            "semanticArtifacts": _semantic_artifacts(requirements, parent),
        }
        provisional = _provisional_core(source, manifest)
        diagnostics = validate_core_artifact(
            plan, semantics_by_unit, provisional, parent=parent
        )
        if diagnostics:
            raise RuntimeError(
                "shared core failed deterministic validation: "
                + "; ".join(item["message"] for item in diagnostics)
            )

        with tempfile.TemporaryDirectory(prefix="spec2lean-core-build-") as build_name:
            build_path = Path(build_name) / lean_file
            build_path.parent.mkdir(parents=True, exist_ok=True)
            build_path.write_text(source, encoding="utf-8")
            build = build_runner(build_path)
        if not isinstance(build, dict) or build.get("status") != "PASS":
            diagnostics = build.get("diagnostics", []) if isinstance(build, dict) else []
            raise RuntimeError(
                "shared core failed Lean build validation"
                + (": " + "; ".join(str(item.get("message", item)) for item in diagnostics) if diagnostics else "")
            )

        run_metadata = {
            "schemaVersion": 1,
            "phase": "SHARED_CORE_MATERIALIZER",
            "coreRunId": core_run_id,
            "parentCoreRunId": manifest["parentCoreRunId"],
            "language": plan["language"],
            "version": plan["version"],
            "sourceDatabaseDigest": plan["sourceDatabaseDigest"],
            "representationSchemaVersion": REPRESENTATION_SCHEMA_VERSION,
            "generatorPolicyVersion": GENERATOR_POLICY_VERSION,
            "model": CORE_GENERATOR_MODEL,
            "reasoning": CORE_GENERATOR_REASONING,
            "materializerInvoked": bool(session["invoked"]),
            "semanticInputHashes": {
                item.dependency_id: item.semantic_input_hash for item in requirements
            },
            "startedAt": session["startedAt"],
            "finishedAt": session["finishedAt"],
            "command": session["command"],
            "exitCode": session["exitCode"],
            "sessionId": session["sessionId"],
            "stdout": session["stdout"],
            "stderr": session["stderr"],
            "build": build,
            "outcome": "SUCCESS",
        }
        try:
            existing = load_core(translations_root, plan, core_run_id)
        except FileNotFoundError:
            existing = None
        if existing is not None:
            existing_diagnostics = validate_core_artifact(
                plan, semantics_by_unit, existing
            )
            if existing_diagnostics:
                raise RuntimeError(
                    "existing content-addressed shared core is invalid: "
                    + "; ".join(
                        item["message"] for item in existing_diagnostics
                    )
                )
        return publish_core(
            translations_root, plan, source, manifest, run_metadata
        ).with_reused(False)
