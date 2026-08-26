from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable

from ..database import connect
from ..util import canonical_json
from .models import EVIDENCE_ROLES, EVIDENCE_TIERS, EvidenceScope
from .query import EvidenceQuery, SessionQuery
from .validation import validate_submission


def _object(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"type": "object", "properties": properties, "additionalProperties": False}
    if required:
        result["required"] = required
    return result


NODE_ID = {"type": "string", "pattern": "^node:"}
SPAN_ID = {"type": "string", "pattern": "^span:"}
LIMIT = {"type": "integer", "minimum": 1, "maximum": 100, "default": 20}


def tool_definitions() -> list[dict[str, Any]]:
    selection = _object(
        {
            "sourceNodeIds": {"type": "array", "items": NODE_ID, "minItems": 1},
            "sourceSpanIds": {"type": "array", "items": SPAN_ID},
            "role": {"type": "string", "enum": list(EVIDENCE_ROLES)},
            "tier": {"type": "string", "enum": list(EVIDENCE_TIERS)},
            "rationale": {"type": "string", "minLength": 1},
        },
        ["sourceNodeIds", "role", "tier", "rationale"],
    )
    return [
        {
            "name": "spec_show",
            "description": "Show exact text, spans, and provenance for one already discovered Phase-1 node.",
            "inputSchema": _object({"nodeId": NODE_ID}, ["nodeId"]),
        },
        {
            "name": "spec_children",
            "description": "Discover bounded direct children of an exposed Phase-1 node.",
            "inputSchema": _object({"nodeId": NODE_ID, "limit": LIMIT}, ["nodeId"]),
        },
        {
            "name": "spec_ancestors",
            "description": "Discover relevant ancestors of an exposed Phase-1 node.",
            "inputSchema": _object({"nodeId": NODE_ID}, ["nodeId"]),
        },
        {
            "name": "spec_subtree",
            "description": "Read a depth- and row-bounded subtree rooted at an exposed Phase-1 node.",
            "inputSchema": _object({
                "nodeId": NODE_ID,
                "maxDepth": {"type": "integer", "minimum": 0, "maximum": 8, "default": 3},
                "limit": LIMIT,
            }, ["nodeId"]),
        },
        {
            "name": "spec_search",
            "description": "Last-resort bounded Phase-1 full-text search requiring a unit-specific justification.",
            "inputSchema": _object({
                "query": {"type": "string", "minLength": 1},
                "justification": {"type": "string", "minLength": 1},
                "limit": LIMIT,
            }, ["query", "justification"]),
        },
        {
            "name": "spec_xrefs",
            "description": "Discover explicit incoming/outgoing cross-references for an exposed node.",
            "inputSchema": _object({"nodeId": NODE_ID}, ["nodeId"]),
        },
        {
            "name": "spec_definitions",
            "description": "Discover bounded structurally indexed definitions relevant to a term.",
            "inputSchema": _object({"query": {"type": "string", "minLength": 1}, "limit": LIMIT}, ["query"]),
        },
        {
            "name": "spec_correlated",
            "description": "Discover Phase-1 correlated HTML/PDF nodes for an exposed node.",
            "inputSchema": _object({"nodeId": NODE_ID}, ["nodeId"]),
        },
        {
            "name": "submit_evidence",
            "description": (
                "Submit relevance selections only. Deterministic validation and provenance reconstruction "
                "run immediately; correct diagnostics and resubmit within this same session."
            ),
            "inputSchema": _object({
                "unitId": {"type": "string", "pattern": "^unit:"},
                "selections": {"type": "array", "items": selection, "minItems": 1},
            }, ["unitId", "selections"]),
        },
    ]


class EvidenceMcpServer:
    def __init__(self, database: Path, scope: EvidenceScope, submission_path: Path, trace_path: Path):
        self.connection = connect(database, read_only=True)
        self.query = EvidenceQuery(self.connection)
        self.session = SessionQuery(self.query, scope)
        self.scope = scope
        self.submission_path = submission_path
        self.trace_path = trace_path
        self._write_trace()

    def close(self) -> None:
        self._write_trace()
        self.connection.close()

    def _write_trace(self) -> None:
        temporary = self.trace_path.with_suffix(".tmp")
        temporary.write_text(canonical_json(self.session.ledger.to_dict()) + "\n", encoding="utf-8")
        os.replace(temporary, self.trace_path)

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.session.ledger.record_call(name, dict(arguments))
        handlers: dict[str, Callable[[], Any]] = {
            "spec_show": lambda: self.session.show(arguments["nodeId"]),
            "spec_children": lambda: self.session.children(arguments["nodeId"], limit=arguments.get("limit", 20)),
            "spec_ancestors": lambda: self.session.ancestors(arguments["nodeId"]),
            "spec_subtree": lambda: self.session.subtree(
                arguments["nodeId"], max_depth=arguments.get("maxDepth", 3), limit=arguments.get("limit", 20)
            ),
            "spec_search": lambda: self.session.search(
                arguments["query"], arguments["justification"], limit=arguments.get("limit", 20)
            ),
            "spec_xrefs": lambda: self.session.xrefs(arguments["nodeId"]),
            "spec_definitions": lambda: self.session.definitions(arguments["query"], limit=arguments.get("limit", 20)),
            "spec_correlated": lambda: self.session.correlated(arguments["nodeId"]),
        }
        if name == "submit_evidence":
            bundle, diagnostics = validate_submission(self.query, self.scope, self.session.ledger, arguments)
            if diagnostics:
                value = {"accepted": False, "diagnostics": diagnostics}
            else:
                assert bundle is not None
                temporary = self.submission_path.with_suffix(".tmp")
                temporary.write_text(canonical_json(bundle) + "\n", encoding="utf-8")
                os.replace(temporary, self.submission_path)
                value = {
                    "accepted": True,
                    "evidenceCount": len(bundle["evidence"]),
                    "message": "Evidence accepted; exact text and provenance were resolved from Phase 1.",
                }
        elif name in handlers:
            value = handlers[name]()
        else:
            raise KeyError(f"unknown tool: {name}")
        self._write_trace()
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
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "spec2lean-phase3", "version": "1"},
                }
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": tool_definitions()}
            elif method == "tools/call":
                params = message.get("params", {})
                result = self.call_tool(params.get("name", ""), params.get("arguments", {}))
            else:
                return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"method not found: {method}"}}
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except Exception as exc:
            self._write_trace()
            return {
                "jsonrpc": "2.0", "id": request_id,
                "result": {"content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"}], "isError": True},
            }


def serve(database: Path, scope_path: Path, submission_path: Path, trace_path: Path) -> int:
    scope = EvidenceScope.from_dict(json.loads(scope_path.read_text(encoding="utf-8")))
    server = EvidenceMcpServer(database, scope, submission_path, trace_path)
    try:
        for line in sys.stdin:
            if not line.strip():
                continue
            response = server.handle(json.loads(line))
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
    parser.add_argument("--trace", type=Path, required=True)
    args = parser.parse_args(argv)
    return serve(args.database.resolve(), args.scope.resolve(), args.submission.resolve(), args.trace.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
