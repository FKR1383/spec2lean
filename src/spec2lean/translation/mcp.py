from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from ..util import canonical_json
from .models import DECLARATION_ROLES, TranslationScope
from .validation import validate_submission


def _object(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def submission_schema() -> dict[str, Any]:
    mapping = _object({
        "declaration": {
            "type": "string",
            "pattern": "^[A-Za-z_][A-Za-z0-9_']*(\\.[A-Za-z_][A-Za-z0-9_']*)*$",
        },
        "role": {"type": "string", "enum": list(DECLARATION_ROLES)},
        "semanticClaimIds": {
            "type": "array",
            "items": {"type": "string", "pattern": "^claim:"},
        },
        "supportsDeclarations": {
            "type": "array",
            "items": {
                "type": "string",
                "pattern": "^[A-Za-z_][A-Za-z0-9_']*(\\.[A-Za-z_][A-Za-z0-9_']*)*$",
            },
        },
    }, ["declaration", "role", "semanticClaimIds"])
    return _object({
        "leanSource": {"type": "string", "minLength": 1},
        "declarations": {"type": "array", "items": mapping, "minItems": 1},
    }, ["leanSource", "declarations"])


def tool_definitions() -> list[dict[str, Any]]:
    return [{
        "name": "submit_translation",
        "description": "Submit one Lean 4 source candidate and its declaration-to-semantic-claim mappings for deterministic structural validation.",
        "inputSchema": submission_schema(),
    }]


class TranslationMcpServer:
    def __init__(
        self, scope: TranslationScope, semantics: dict[str, Any], submission_path: Path
    ):
        self.scope = scope
        self.semantics = semantics
        self.submission_path = submission_path

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name != "submit_translation":
            raise KeyError(f"unknown tool: {name}")
        candidate, diagnostics = validate_submission(self.scope, self.semantics, arguments)
        if diagnostics:
            value = {"accepted": False, "diagnostics": diagnostics}
        else:
            assert candidate is not None
            temporary = self.submission_path.with_suffix(".tmp")
            temporary.write_text(canonical_json(candidate) + "\n", encoding="utf-8")
            os.replace(temporary, self.submission_path)
            value = {
                "accepted": True,
                "translationRunId": self.scope.translation_run_id,
                "message": "Translation submission accepted.",
            }
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
                    "serverInfo": {"name": "spec2lean-translation", "version": "1"},
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
        except Exception as exc:  # Keep MCP protocol failures structured for the one session.
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32000, "message": str(exc)}}


def serve(scope_path: Path, semantics_path: Path, submission_path: Path) -> None:
    scope = TranslationScope.from_dict(json.loads(scope_path.read_text(encoding="utf-8")))
    semantics = json.loads(semantics_path.read_text(encoding="utf-8"))
    server = TranslationMcpServer(scope, semantics, submission_path)
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
    parser.add_argument("--scope", type=Path, required=True)
    parser.add_argument("--semantics", type=Path, required=True)
    parser.add_argument("--submission", type=Path, required=True)
    args = parser.parse_args()
    serve(args.scope, args.semantics, args.submission)


if __name__ == "__main__":
    main()
