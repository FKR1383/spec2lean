from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable

from ..database import connect
from ..util import canonical_json
from .scope import Phase1Query, ResolvedScope
from .validation import validate_submission


def _schema_object(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"type": "object", "properties": properties, "additionalProperties": False}
    if required:
        result["required"] = required
    return result


NODE_ID = {"type": "string", "pattern": "^node:"}
LIMIT = {"type": "integer", "minimum": 1, "maximum": 100, "default": 20}


def tool_definitions() -> list[dict[str, Any]]:
    prerequisite = _schema_object(
        {
            "key": {"type": "string", "minLength": 1},
            "name": {"type": "string", "minLength": 1},
            "reason": {"type": "string", "minLength": 1},
            "sourceNodeIds": {"type": "array", "items": NODE_ID, "minItems": 1},
        },
        ["key", "name", "reason", "sourceNodeIds"],
    )
    dependency = _schema_object(
        {
            "from": {"type": "string", "minLength": 1},
            "to": {"type": "string", "minLength": 1},
            "reason": {"type": "string", "minLength": 1},
            "supportingNodeIds": {"type": "array", "items": NODE_ID, "minItems": 1},
            "origin": {"type": "string", "enum": ["EXPLICIT", "INFERRED"]},
        },
        ["from", "to", "reason", "supportingNodeIds", "origin"],
    )
    return [
        {
            "name": "spec_search",
            "description": "Bounded full-text search of the Phase-1 specification database.",
            "inputSchema": _schema_object(
                {"query": {"type": "string", "minLength": 1}, "limit": LIMIT}, ["query"]
            ),
        },
        {
            "name": "spec_show",
            "description": "Show one Phase-1 node with bounded source text and provenance.",
            "inputSchema": _schema_object({"nodeId": NODE_ID}, ["nodeId"]),
        },
        {
            "name": "spec_children",
            "description": "List bounded direct children of a Phase-1 node.",
            "inputSchema": _schema_object({"nodeId": NODE_ID, "limit": LIMIT}, ["nodeId"]),
        },
        {
            "name": "spec_ancestors",
            "description": "List ancestors of a Phase-1 node from root to the node.",
            "inputSchema": _schema_object({"nodeId": NODE_ID}, ["nodeId"]),
        },
        {
            "name": "spec_subtree",
            "description": "Read a depth- and row-bounded Phase-1 subtree.",
            "inputSchema": _schema_object(
                {
                    "nodeId": NODE_ID,
                    "maxDepth": {"type": "integer", "minimum": 0, "maximum": 8, "default": 3},
                    "limit": LIMIT,
                },
                ["nodeId"],
            ),
        },
        {
            "name": "spec_xrefs",
            "description": "List explicit incoming and outgoing cross-references for one node.",
            "inputSchema": _schema_object({"nodeId": NODE_ID}, ["nodeId"]),
        },
        {
            "name": "spec_definitions",
            "description": "Search structurally identified Phase-1 definitions.",
            "inputSchema": _schema_object(
                {"query": {"type": "string"}, "limit": LIMIT}
            ),
        },
        {
            "name": "submit_plan",
            "description": (
                "Submit semantic planning content for deterministic validation. Diagnostics are "
                "returned without ending the session; correct and resubmit until accepted."
            ),
            "inputSchema": _schema_object(
                {
                    "requestedUnitIds": {
                        "type": "array",
                        "items": {"type": "string", "pattern": "^unit:"},
                    },
                    "externalPrerequisites": {"type": "array", "items": prerequisite},
                    "dependencies": {"type": "array", "items": dependency},
                },
                ["requestedUnitIds", "externalPrerequisites", "dependencies"],
            ),
        },
    ]


class PlannerMcpServer:
    def __init__(self, database: Path, scope: ResolvedScope, submission_path: Path):
        self.connection = connect(database, read_only=True)
        self.query = Phase1Query(self.connection)
        self.scope = scope
        self.submission_path = submission_path

    def close(self) -> None:
        self.connection.close()

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        handlers: dict[str, Callable[[], Any]] = {
            "spec_search": lambda: self.query.search(arguments["query"], limit=arguments.get("limit", 20)),
            "spec_show": lambda: self.query.show(arguments["nodeId"]),
            "spec_children": lambda: self.query.children(arguments["nodeId"], limit=arguments.get("limit", 20)),
            "spec_ancestors": lambda: self.query.ancestors(arguments["nodeId"]),
            "spec_subtree": lambda: self.query.subtree(
                arguments["nodeId"],
                max_depth=arguments.get("maxDepth", 3),
                limit=arguments.get("limit", 20),
            ),
            "spec_xrefs": lambda: self.query.xrefs(arguments["nodeId"]),
            "spec_definitions": lambda: self.query.definitions(
                arguments.get("query"), limit=arguments.get("limit", 20)
            ),
        }
        if name == "submit_plan":
            normalized, diagnostics = validate_submission(self.query, self.scope, arguments)
            if diagnostics:
                value = {"accepted": False, "diagnostics": diagnostics}
            else:
                temporary = self.submission_path.with_suffix(".tmp")
                temporary.write_text(canonical_json(arguments) + "\n", encoding="utf-8")
                os.replace(temporary, self.submission_path)
                value = {"accepted": True, "message": "Plan accepted; deterministic layers will be derived."}
        elif name in handlers:
            value = handlers[name]()
        else:
            raise KeyError(f"unknown tool: {name}")
        return {
            "content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False, sort_keys=True)}],
            "isError": False,
        }

    def handle(self, message: dict[str, Any]) -> dict[str, Any] | None:
        method = message.get("method")
        if "id" not in message:
            return None
        request_id = message["id"]
        try:
            if method == "initialize":
                result = {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "spec2lean-phase2", "version": "1"},
                }
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": tool_definitions()}
            elif method == "tools/call":
                params = message.get("params", {})
                result = self.call_tool(params.get("name", ""), params.get("arguments", {}))
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": f"method not found: {method}"},
                }
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"}],
                    "isError": True,
                },
            }


def serve(database: Path, scope_path: Path, submission_path: Path) -> int:
    scope = ResolvedScope.from_dict(json.loads(scope_path.read_text(encoding="utf-8")))
    server = PlannerMcpServer(database, scope, submission_path)
    try:
        for line in sys.stdin:
            if not line.strip():
                continue
            message = json.loads(line)
            response = server.handle(message)
            if response is not None:
                sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
                sys.stdout.flush()
    finally:
        server.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--scope", type=Path, required=True)
    parser.add_argument("--submission", type=Path, required=True)
    args = parser.parse_args(argv)
    return serve(args.database.resolve(), args.scope.resolve(), args.submission.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
