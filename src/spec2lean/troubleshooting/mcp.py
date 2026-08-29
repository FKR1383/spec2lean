from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from ..translation.models import TranslationGroupScope
from ..util import canonical_json
from .validation import validate_repair_submission


def _object(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


def submission_schema() -> dict[str, Any]:
    mapping = _object({
        "declaration": {"type": "string"},
        "role": {"type": "string"},
        "claimRefs": {"type": "array", "items": _object({
            "unitId": {"type": "string"},
            "claimId": {"type": "string"},
        }, ["unitId", "claimId"])},
        "supportsDeclarations": {"type": "array", "items": {"type": "string"}},
    }, ["declaration", "role", "claimRefs"])
    change = _object({
        "description": {"type": "string", "minLength": 1},
        "affectedDeclarations": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Mapped declarations affected by the change; empty for file-level import changes.",
        },
    }, ["description", "affectedDeclarations"])
    return _object({
        "leanSource": {"type": "string", "minLength": 1},
        "declarations": {"type": "array", "minItems": 1, "items": mapping},
        "changes": {"type": "array", "minItems": 1, "items": change},
    }, ["leanSource", "declarations", "changes"])


def tool_definitions() -> list[dict[str, Any]]:
    return [{
        "name": "submit_repair",
        "description": (
            "Submit a minimal compiler-directed Lean repair for deterministic validation. "
            "If rejected, correct the diagnostics and resubmit within the same session."
        ),
        "inputSchema": submission_schema(),
    }]


class TroubleshootingMcpServer:
    def __init__(self, context: dict[str, Any], submission_path: Path):
        self.context = context
        self.submission_path = submission_path

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name != "submit_repair":
            raise KeyError(f"unknown tool: {name}")
        scope = TranslationGroupScope.from_dict(self.context["translationScope"])
        candidate, diagnostics = validate_repair_submission(
            scope,
            self.context["semanticsByUnit"],
            self.context["leanSource"],
            self.context["translationManifest"],
            arguments,
        )
        if diagnostics:
            value = {"accepted": False, "diagnostics": diagnostics}
        else:
            assert candidate is not None
            temporary = self.submission_path.with_suffix(".tmp")
            temporary.write_text(canonical_json({
                "leanSource": candidate["leanSource"],
                # Source ranges are deterministic manifest metadata, not repair-tool
                # arguments.  The runner derives them again from the returned source.
                "declarations": [
                    {
                        key: value for key, value in item.items()
                        if key != "sourceRange"
                    }
                    for item in candidate["manifest"]["declarations"]
                ],
                "changes": candidate["changes"],
            }) + "\n", encoding="utf-8")
            os.replace(temporary, self.submission_path)
            value = {"accepted": True, "message": "Compiler-directed repair accepted."}
        return {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False, sort_keys=True)}], "isError": False}

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
                    "serverInfo": {"name": "spec2lean-troubleshooting", "version": "1"},
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
    server = TroubleshootingMcpServer(context, submission_path)
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
