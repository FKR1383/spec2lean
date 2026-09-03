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
    return [
        {
            "name": "get_context",
            "description": (
                "Read one complete, immutable component of the Phase-7 repair context. Read the "
                "overview first, then every component and semantic unit it lists."
            ),
            "inputSchema": _object({
                "component": {
                    "type": "string",
                    "enum": [
                        "overview", "leanSource", "translationManifest", "traceability",
                        "semantics",
                    ],
                },
                "unitId": {"type": "string"},
            }, ["component"]),
        },
        {
            "name": "submit_repair",
            "description": (
                "Submit a minimal compiler-directed Lean repair for deterministic validation. "
                "If rejected, correct the diagnostics and resubmit within the same session."
            ),
            "inputSchema": submission_schema(),
        },
    ]


class TroubleshootingMcpServer:
    def __init__(self, context: dict[str, Any], submission_path: Path):
        self.context = context
        self.submission_path = submission_path
        self.context_reads: set[str] = set()

    def _required_context_reads(self) -> set[str]:
        semantics = self.context.get("semanticsByUnit", {})
        unit_ids = semantics if isinstance(semantics, dict) else {}
        return {
            "overview", "leanSource", "translationManifest", "traceability",
            *(f"semantics:{unit_id}" for unit_id in unit_ids),
        }

    def _context_component(self, component: str, unit_id: str | None) -> Any:
        if component == "overview":
            if unit_id is not None:
                raise ValueError("overview does not accept unitId")
            excluded = {"leanSource", "translationManifest", "traceability", "semanticsByUnit"}
            return {
                **{key: value for key, value in self.context.items() if key not in excluded},
                "availableComponents": [
                    "leanSource", "translationManifest", "traceability", "semantics",
                ],
                "semanticUnitIds": sorted(self.context.get("semanticsByUnit", {})),
            }
        if component == "semantics":
            if not unit_id:
                raise ValueError("semantics requires unitId")
            semantics = self.context.get("semanticsByUnit", {})
            if unit_id not in semantics:
                raise KeyError(f"unknown semantic unit: {unit_id}")
            return semantics[unit_id]
        if unit_id is not None:
            raise ValueError(f"{component} does not accept unitId")
        return self.context[component]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "get_context":
            unexpected = set(arguments) - {"component", "unitId"}
            if unexpected:
                raise ValueError(f"get_context received unexpected arguments: {sorted(unexpected)}")
            component = str(arguments.get("component", ""))
            if component not in {
                "overview", "leanSource", "translationManifest", "traceability", "semantics",
            }:
                raise ValueError(f"unknown context component: {component}")
            unit_id = arguments.get("unitId")
            if unit_id is not None and not isinstance(unit_id, str):
                raise ValueError("unitId must be a string")
            component_key = f"semantics:{unit_id}" if component == "semantics" else component
            component_value = self._context_component(component, unit_id)
            self.context_reads.add(component_key)
            value = {
                "component": component,
                "value": component_value,
                "transport": {"complete": True},
            }
            if unit_id is not None:
                value["unitId"] = unit_id
        elif name != "submit_repair":
            raise KeyError(f"unknown tool: {name}")
        else:
            missing = sorted(self._required_context_reads() - self.context_reads)
            if missing:
                value = {
                    "accepted": False,
                    "diagnostics": [{
                        "code": "CONTEXT_NOT_READ",
                        "message": (
                            "read every repair context component with troubleshooting_get_context "
                            f"before submitting; missing: {', '.join(missing)}"
                        ),
                        "path": "$",
                    }],
                }
            else:
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
                        "declarations": candidate["manifest"]["declarations"],
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
