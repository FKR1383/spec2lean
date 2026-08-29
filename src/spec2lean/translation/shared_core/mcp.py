from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from ...util import canonical_json
from ..models import DECLARATION_ROLES
from .models import FrozenSharedCore, SharedRequirement, json_hash, text_hash
from .validation import normalize_core_submission


def _object(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def submission_schema() -> dict[str, Any]:
    lean_name = {
        "type": "string",
        "pattern": "^[A-Za-z_][A-Za-z0-9_']*(\\.[A-Za-z_][A-Za-z0-9_']*)*$",
    }
    claim_ref = _object({
        "unitId": {"type": "string", "pattern": "^unit:"},
        "claimId": {"type": "string", "pattern": "^claim:"},
    }, ["unitId", "claimId"])
    concept = _object({
        "dependencyId": {"type": "string", "pattern": "^shared:"},
        "leanDeclarations": {
            "type": "array", "minItems": 1, "uniqueItems": True,
            "items": lean_name,
        },
    }, ["dependencyId", "leanDeclarations"])
    declaration = _object({
        "declaration": lean_name,
        "role": {"enum": list(DECLARATION_ROLES)},
        "dependencyIds": {
            "type": "array", "minItems": 1, "uniqueItems": True,
            "items": {"type": "string", "pattern": "^shared:"},
        },
        "claimRefs": {"type": "array", "items": claim_ref, "uniqueItems": True},
        "supportsDeclarations": {
            "type": "array", "minItems": 1, "uniqueItems": True,
            "items": lean_name,
        },
    }, ["declaration", "role", "dependencyIds", "claimRefs"])
    return _object({
        "leanSource": {"type": "string", "minLength": 1},
        "concepts": {"type": "array", "items": concept},
        "declarations": {"type": "array", "items": declaration},
    }, ["leanSource", "concepts", "declarations"])


def tool_definitions() -> list[dict[str, Any]]:
    return [
        {
            "name": "get_context",
            "description": "Read the immutable shared semantic requirements and accepted parent core.",
            "inputSchema": _object({}, []),
        },
        {
            "name": "submit_core",
            "description": "Submit the complete shared Lean core and dependency/declaration registry.",
            "inputSchema": submission_schema(),
        },
    ]


def _parent(context: dict[str, Any]) -> FrozenSharedCore | None:
    value = context.get("parentCore")
    if not isinstance(value, dict):
        return None
    manifest, source = value.get("manifest"), value.get("leanSource")
    if not isinstance(manifest, dict) or not isinstance(source, str):
        raise ValueError("parentCore context is malformed")
    placeholder = Path("<immutable-parent-core>")
    return FrozenSharedCore(
        directory=placeholder,
        source_path=placeholder / str(manifest.get("leanFile", "Core.lean")),
        manifest_path=placeholder / "core-manifest.json",
        run_path=placeholder / "core-run.json",
        source=source,
        manifest=manifest,
        core_run_id=str(manifest["coreRunId"]),
        lean_module=str(manifest["leanModule"]),
        source_hash=text_hash(source),
        manifest_hash=json_hash(manifest),
        reused=True,
    )


class SharedCoreMcpServer:
    def __init__(self, context: dict[str, Any], submission_path: Path):
        self.context = context
        self.submission_path = submission_path
        self.requirements = tuple(
            SharedRequirement.from_dict(item) for item in context.get("requirements", [])
        )
        self.parent = _parent(context)

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "get_context":
            if arguments:
                value: dict[str, Any] = {
                    "accepted": False,
                    "diagnostics": [{
                        "code": "UNEXPECTED_ARGUMENT",
                        "message": "get_context accepts no arguments",
                        "path": "$",
                    }],
                }
            else:
                value = {"accepted": True, "context": self.context}
        elif name == "submit_core":
            candidate, diagnostics = normalize_core_submission(
                self.requirements, arguments, parent=self.parent,
                lean_namespace=(
                    str(self.context["leanNamespace"])
                    if self.parent is not None else None
                ),
            )
            if diagnostics:
                value = {"accepted": False, "diagnostics": diagnostics}
            else:
                assert candidate is not None
                temporary = self.submission_path.with_suffix(".tmp")
                temporary.write_text(canonical_json(candidate) + "\n", encoding="utf-8")
                os.replace(temporary, self.submission_path)
                value = {"accepted": True, "message": "Shared-core submission accepted."}
        else:
            raise KeyError(f"unknown tool: {name}")
        return {
            "content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False, sort_keys=True)}],
            "isError": False,
        }

    def handle(self, message: dict[str, Any]) -> dict[str, Any] | None:
        if "id" not in message:
            return None
        request_id = message["id"]
        try:
            method = message.get("method")
            if method == "initialize":
                result = {
                    "protocolVersion": message.get("params", {}).get("protocolVersion", "2024-11-05"),
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "spec2lean-shared-core", "version": "1"},
                }
            elif method == "tools/list":
                result = {"tools": tool_definitions()}
            elif method == "tools/call":
                params = message.get("params", {})
                result = self.call_tool(params.get("name", ""), params.get("arguments", {}))
            elif method == "ping":
                result = {}
            else:
                return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"unknown method: {method}"}}
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except Exception as exc:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32000, "message": str(exc)}}


def serve(context_path: Path, submission_path: Path) -> None:
    context = json.loads(context_path.read_text(encoding="utf-8"))
    server = SharedCoreMcpServer(context, submission_path)
    for line in sys.stdin:
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = server.handle(message)
        if response is not None:
            print(json.dumps(response, ensure_ascii=False, separators=(",", ":")), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--submission", type=Path, required=True)
    args = parser.parse_args()
    serve(args.context, args.submission)


if __name__ == "__main__":
    main()
