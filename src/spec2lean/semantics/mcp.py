from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from ..util import canonical_json
from .models import CLAIM_KINDS, RESTRICTION_KINDS, UNIT_KINDS, SemanticScope
from .validation import validate_submission


def _object(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"type": "object", "properties": properties, "additionalProperties": False}
    if required:
        result["required"] = required
    return result


TEXT = {"type": "string", "minLength": 1}
EVIDENCE_IDS = {
    "type": "array",
    "items": {"type": "string", "pattern": "^(evidence|resolution):"},
}

SEMANTIC_EVIDENCE_FIELDS = (
    "evidenceId", "role", "tier", "rationale", "sourceType", "sectionNumber",
    "sectionTitle", "exactText", "sourceNodeIds", "htmlAnchor", "pdfPage",
)


def semantic_evidence_view(scope: Any, bundle: dict[str, Any]) -> dict[str, Any]:
    """Project out verbose GUI provenance while preserving every semantic source passage."""
    evidence = [
        {field: item.get(field) for field in SEMANTIC_EVIDENCE_FIELDS}
        for item in bundle.get("evidence", [])
        if isinstance(item, dict)
    ]
    return {
        "schemaVersion": 1,
        "unit": dict(bundle.get("unit", {})),
        "evidence": evidence,
        "resolutions": list(bundle.get("resolutions", [])),
        "transport": {
            "complete": True,
            "evidenceBundleHash": scope.evidence_bundle_hash,
            "evidenceCount": len(evidence),
        },
    }


def _component(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return _object({**properties, "evidenceIds": EVIDENCE_IDS}, [*required, "evidenceIds"])


def submission_schema() -> dict[str, Any]:
    syntax = _component({"form": TEXT, "description": TEXT}, ["form"])
    operand = _component({
        "name": TEXT, "role": TEXT, "description": TEXT,
        "constraints": {"type": "array", "items": TEXT},
    }, ["name", "role", "description", "constraints"])
    result = _component({
        "name": TEXT, "description": TEXT, "constraints": {"type": "array", "items": TEXT},
    }, ["name", "description", "constraints"])
    branch = _component({"condition": TEXT, "behavior": TEXT}, ["condition", "behavior"])
    operation = _component({
        "description": TEXT, "inputs": {"type": "array", "items": TEXT, "minItems": 1},
        "result": TEXT, "branches": {"type": "array", "items": branch},
    }, ["description", "inputs", "result", "branches"])
    edge = _component({"condition": TEXT, "behavior": TEXT}, ["condition", "behavior"])
    state = _component({"target": TEXT, "effect": TEXT}, ["target", "effect"])
    restriction = _component({"kind": {"type": "string", "enum": list(RESTRICTION_KINDS)}, "description": TEXT}, ["kind", "description"])
    dependency = _component({
        "dependencyId": {"type": "string", "pattern": "^shared:"},
        "concept": TEXT,
        "description": TEXT,
        "artifactId": TEXT,
        "semanticClaimIds": {
            "type": "array",
            "items": {"type": "string", "pattern": "^claim:"},
            "uniqueItems": True,
        },
    }, ["concept", "description"])
    claim = _component({
        "claimId": {"type": "string", "pattern": "^claim:"},
        "kind": {"type": "string", "enum": list(CLAIM_KINDS)}, "statement": TEXT,
    }, ["claimId", "kind", "statement"])
    identity = _component({"name": TEXT, "form": TEXT, "description": TEXT}, ["name"])
    predication = _component({"guard": TEXT, "whenTrue": TEXT, "whenFalse": TEXT}, ["guard", "whenTrue", "whenFalse"])
    # Keep the MCP tool root a plain object. Some OpenCode/provider tool-schema
    # adapters silently omit tools whose root is a oneOf union. Conditional
    # SUCCESS/failure requirements are enforced by validate_submission.
    return _object({
        "outcome": {"type": "string", "enum": ["SUCCESS", "INSUFFICIENT_EVIDENCE"]},
        "unitKind": {"type": "string", "enum": list(UNIT_KINDS)},
        "identity": identity, "syntaxForms": {"type": "array", "items": syntax},
        "inputs": {"type": "array", "items": operand}, "result": result, "operation": operation,
        "edgeCases": {"type": "array", "items": edge}, "stateEffects": {"type": "array", "items": state},
        "predication": predication, "restrictions": {"type": "array", "items": restriction},
        "dependencies": {"type": "array", "items": dependency}, "claims": {"type": "array", "items": claim, "minItems": 1},
        "missingAspects": {"type": "array", "items": TEXT, "minItems": 1},
        "explanation": TEXT, "evidenceIds": EVIDENCE_IDS,
    }, ["outcome"])


def tool_definitions() -> list[dict[str, Any]]:
    return [
        {
            "name": "get_evidence",
            "description": (
                "Read the complete, immutable Phase-3 evidence bundle for this one semantic unit."
            ),
            "inputSchema": _object({}),
        },
        {
            "name": "submit_semantics",
            "description": "Submit semantics or a precise insufficient-evidence failure for deterministic validation.",
            "inputSchema": submission_schema(),
        },
    ]


class SemanticsMcpServer:
    def __init__(self, scope: SemanticScope, bundle: dict[str, Any], submission_path: Path):
        self.scope = scope
        self.bundle = bundle
        self.submission_path = submission_path
        self.evidence_read = False

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "get_evidence":
            if arguments:
                raise ValueError("get_evidence accepts no arguments")
            self.evidence_read = True
            value = semantic_evidence_view(self.scope, self.bundle)
        elif name != "submit_semantics":
            raise KeyError(f"unknown tool: {name}")
        else:
            if not self.evidence_read:
                value = {
                    "accepted": False,
                    "diagnostics": [{
                        "code": "EVIDENCE_NOT_READ",
                        "message": "call semantics_get_evidence before submitting semantics",
                        "path": "$",
                    }],
                }
                return {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(value, ensure_ascii=False, sort_keys=True),
                    }],
                    "isError": False,
                }
            artifact, diagnostics = validate_submission(self.scope, self.bundle, arguments)
            if diagnostics:
                value = {"accepted": False, "diagnostics": diagnostics}
            else:
                assert artifact is not None
                temporary = self.submission_path.with_suffix(".tmp")
                temporary.write_text(canonical_json(artifact) + "\n", encoding="utf-8")
                os.replace(temporary, self.submission_path)
                value = {"accepted": True, "outcome": artifact["outcome"], "message": "Semantic submission accepted."}
        return {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False, sort_keys=True)}], "isError": False}

    def handle(self, message: dict[str, Any]) -> dict[str, Any] | None:
        if "id" not in message:
            return None
        request_id = message["id"]
        try:
            method = message.get("method")
            if method == "initialize":
                result = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {"listChanged": False}}, "serverInfo": {"name": "spec2lean-phase4", "version": "1"}}
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
            return {"jsonrpc": "2.0", "id": request_id, "result": {"content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"}], "isError": True}}


def serve(scope_path: Path, evidence_path: Path, submission_path: Path) -> int:
    scope = SemanticScope.from_dict(json.loads(scope_path.read_text(encoding="utf-8")))
    bundle = json.loads(evidence_path.read_text(encoding="utf-8"))
    server = SemanticsMcpServer(scope, bundle, submission_path)
    for line in sys.stdin:
        if line.strip():
            response = server.handle(json.loads(line))
            if response is not None:
                sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
                sys.stdout.flush()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--submission", type=Path, required=True)
    args = parser.parse_args(argv)
    return serve(args.scope.resolve(), args.evidence.resolve(), args.submission.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
