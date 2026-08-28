from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from ..database import connect
from ..evidence.models import EVIDENCE_ROLES, EvidenceScope
from ..evidence.query import EvidenceQuery, SessionQuery
from ..evidence.validation import (
    EvidenceValidationError,
    build_evidence_record,
    required_official_renditions,
)
from ..util import canonical_json, normalize_text, stable_id
from .questions import (
    QUESTION_MODEL,
    QUESTION_REASONING,
    QUESTION_SOURCES,
    OpenQuestionScope,
    resolution_record,
)


def _object(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    value: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        value["required"] = required
    return value


TEXT = {"type": "string", "minLength": 1}
NODE_ID = {"type": "string", "pattern": "^node:"}
SPAN_ID = {"type": "string", "pattern": "^span:"}
QUESTION_ID = {"type": "string", "pattern": "^question:"}
LIMIT = {"type": "integer", "minimum": 1, "maximum": 100, "default": 20}


def tool_definitions(*, runtime_available: bool) -> list[dict[str, Any]]:
    question_query = {
        "questionId": QUESTION_ID,
        "query": TEXT,
        "justification": TEXT,
        "limit": LIMIT,
    }
    tools = [
        {
            "name": "spec_search",
            "description": "Search the canonical Phase-1 database for one missing semantic aspect.",
            "inputSchema": _object(question_query, ["questionId", "query", "justification"]),
        },
        {
            "name": "spec_definitions",
            "description": "Search canonical Phase-1 structural definitions for one missing aspect.",
            "inputSchema": _object(
                {"questionId": QUESTION_ID, "query": TEXT, "limit": LIMIT},
                ["questionId", "query"],
            ),
        },
        {
            "name": "spec_show",
            "description": "Read exact text and provenance for a discovered Phase-1 node.",
            "inputSchema": _object({"nodeId": NODE_ID}, ["nodeId"]),
        },
        {
            "name": "spec_children",
            "description": "Discover direct children of an exposed Phase-1 node.",
            "inputSchema": _object({"nodeId": NODE_ID, "limit": LIMIT}, ["nodeId"]),
        },
        {
            "name": "spec_subtree",
            "description": "Read a bounded Phase-1 subtree rooted at an exposed node.",
            "inputSchema": _object(
                {
                    "nodeId": NODE_ID,
                    "maxDepth": {"type": "integer", "minimum": 0, "maximum": 8, "default": 3},
                    "limit": LIMIT,
                },
                ["nodeId"],
            ),
        },
        {
            "name": "spec_correlated",
            "description": "Find the correlated HTML/PDF representation of an exposed Phase-1 node.",
            "inputSchema": _object({"nodeId": NODE_ID}, ["nodeId"]),
        },
    ]
    if runtime_available:
        tools.append({
            "name": "execute_probe",
            "description": (
                "Execute the configured trusted runtime-probe adapter for one unresolved case. "
                "The adapter receives JSON on stdin; arbitrary shell commands are not accepted."
            ),
            "inputSchema": _object(
                {"questionId": QUESTION_ID, "input": {}}, ["questionId", "input"]
            ),
        })
    resolution = _object(
        {
            "questionId": QUESTION_ID,
            "source": {"type": "string", "enum": list(QUESTION_SOURCES)},
            "role": {"type": "string", "enum": list(EVIDENCE_ROLES)},
            "answer": TEXT,
            "rationale": TEXT,
            "sourceNodeIds": {"type": "array", "items": NODE_ID},
            "sourceSpanIds": {"type": "array", "items": SPAN_ID},
            "counterpartSourceNodeIds": {"type": "array", "items": NODE_ID},
            "counterpartSourceSpanIds": {"type": "array", "items": SPAN_ID},
            "url": TEXT,
            "excerpt": TEXT,
            "probeId": {"type": "string", "pattern": "^probe:"},
        },
        ["questionId", "source", "role", "rationale"],
    )
    tools.append({
        "name": "submit_questions",
        "description": (
            "Submit exactly one disposition for every open question. Database evidence is rebuilt "
            "from Phase 1; all other answers are retained as explicitly non-normative resolutions."
        ),
        "inputSchema": _object(
            {"resolutions": {"type": "array", "items": resolution, "minItems": 1}},
            ["resolutions"],
        ),
    })
    return tools


class OpenQuestionMcpServer:
    def __init__(
        self,
        database: Path,
        scope: OpenQuestionScope,
        bundle: dict[str, Any],
        submission_path: Path,
        trace_path: Path,
        runtime_command: tuple[str, ...] = (),
        *,
        runtime_timeout_seconds: int = 60,
    ):
        self.connection = connect(database, read_only=True)
        self.query = EvidenceQuery(self.connection)
        evidence_scope = EvidenceScope(
            plan_run_id=scope.plan_run_id,
            language=scope.language,
            version=scope.version,
            source_database_digest=scope.source_database_digest,
            unit=dict(scope.unit),
            prerequisites=(),
            dependencies=(),
            seed_nodes=tuple((node, "UNIT_SOURCE") for node in scope.unit.get("sourceNodeIds", [])),
        )
        self.session = SessionQuery(self.query, evidence_scope)
        for record in bundle.get("evidence", []):
            for node_id in record.get("sourceNodeIds", []):
                details = self.query.show(node_id)
                self.session.ledger.expose(
                    node_id,
                    "CURRENT_EVIDENCE",
                    selectable=True,
                    spans=[item["spanId"] for item in details["sourceSpans"]],
                )
        self.scope = scope
        self.bundle = bundle
        self.evidence_scope = evidence_scope
        self.submission_path = submission_path
        self.trace_path = trace_path
        self.runtime_command = runtime_command
        self.runtime_timeout_seconds = runtime_timeout_seconds
        self.probes: dict[str, dict[str, Any]] = {}
        self._write_trace()

    def close(self) -> None:
        self._write_trace()
        self.connection.close()

    def _write_trace(self) -> None:
        value = self.session.ledger.to_dict()
        value["runtimeProbes"] = [self.probes[key] for key in sorted(self.probes)]
        temporary = self.trace_path.with_suffix(".tmp")
        temporary.write_text(canonical_json(value) + "\n", encoding="utf-8")
        os.replace(temporary, self.trace_path)

    def _known_question(self, question_id: str) -> None:
        if question_id not in {item["questionId"] for item in self.scope.questions}:
            raise ValueError(f"unknown open question: {question_id}")

    def _execute_probe(self, question_id: str, value: Any) -> dict[str, Any]:
        self._known_question(question_id)
        if not self.runtime_command:
            raise RuntimeError("no trusted runtime-probe adapter is configured")
        if not self._database_checked(question_id):
            raise RuntimeError(
                "the canonical database must be searched for this question before a runtime probe"
            )
        request = {"questionId": question_id, "input": value}
        completed = subprocess.run(
            list(self.runtime_command),
            input=canonical_json(request) + "\n",
            text=True,
            capture_output=True,
            timeout=self.runtime_timeout_seconds,
            check=False,
        )
        probe_id = stable_id(
            "probe", question_id, canonical_json(value), completed.returncode,
            completed.stdout, completed.stderr, length=32,
        )
        record = {
            "probeId": probe_id,
            "questionId": question_id,
            "adapter": list(self.runtime_command),
            "request": value,
            "exitCode": completed.returncode,
            "stdout": completed.stdout[-24_000:],
            "stderr": completed.stderr[-24_000:],
        }
        self.probes[probe_id] = record
        return record

    def _database_checked(self, question_id: str) -> bool:
        return any(
            call.get("tool") in {"spec_search", "spec_definitions"}
            and call.get("arguments", {}).get("questionId") == question_id
            for call in self.session.ledger.calls
        )

    def _validate_submission(
        self, submission: Any
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None, list[dict[str, str]]]:
        diagnostics: list[dict[str, str]] = []
        if not isinstance(submission, dict) or set(submission) != {"resolutions"}:
            return None, None, [{"code": "INVALID_SUBMISSION", "message": "submission must contain only resolutions", "path": "$"}]
        raw_items = submission.get("resolutions")
        if not isinstance(raw_items, list):
            return None, None, [{"code": "EXPECTED_ARRAY", "message": "resolutions must be an array", "path": "$.resolutions"}]
        expected = {item["questionId"]: item for item in self.scope.questions}
        seen: set[str] = set()
        official_additions: list[dict[str, Any]] = []
        supplemental: list[dict[str, Any]] = []
        question_results: list[dict[str, Any]] = []
        original_evidence = {item.get("evidenceId") for item in self.bundle.get("evidence", [])}
        added_evidence: dict[str, dict[str, Any]] = {}
        existing_resolutions = {item.get("resolutionId") for item in self.bundle.get("resolutions", [])}
        required_renditions = required_official_renditions(self.query, self.evidence_scope)
        allowed_fields = {
            "questionId", "source", "role", "answer", "rationale", "sourceNodeIds",
            "sourceSpanIds", "counterpartSourceNodeIds", "counterpartSourceSpanIds",
            "url", "excerpt", "probeId",
        }
        for index, raw in enumerate(raw_items):
            path = f"$.resolutions[{index}]"
            if not isinstance(raw, dict):
                diagnostics.append({"code": "EXPECTED_OBJECT", "message": "resolution must be an object", "path": path})
                continue
            for field in sorted(set(raw) - allowed_fields):
                diagnostics.append({"code": "UNEXPECTED_FIELD", "message": f"unsupported field: {field}", "path": f"{path}.{field}"})
            question_id = raw.get("questionId")
            if question_id not in expected:
                diagnostics.append({"code": "UNKNOWN_QUESTION", "message": f"unknown question: {question_id}", "path": f"{path}.questionId"})
                continue
            if question_id in seen:
                diagnostics.append({"code": "DUPLICATE_QUESTION", "message": f"duplicate question: {question_id}", "path": f"{path}.questionId"})
                continue
            seen.add(question_id)
            source, role = raw.get("source"), raw.get("role")
            rationale = normalize_text(raw.get("rationale", "")) if isinstance(raw.get("rationale"), str) else ""
            answer = normalize_text(raw.get("answer", "")) if isinstance(raw.get("answer"), str) else ""
            if source not in QUESTION_SOURCES:
                diagnostics.append({"code": "INVALID_SOURCE", "message": f"invalid resolution source: {source}", "path": f"{path}.source"})
                continue
            if role not in EVIDENCE_ROLES:
                diagnostics.append({"code": "INVALID_ROLE", "message": f"invalid semantic role: {role}", "path": f"{path}.role"})
            if not rationale:
                diagnostics.append({"code": "EMPTY_RATIONALE", "message": "rationale must be non-empty", "path": f"{path}.rationale"})
            if source != "UNRESOLVED" and not answer:
                diagnostics.append({"code": "EMPTY_ANSWER", "message": "resolved questions require an answer", "path": f"{path}.answer"})
            if source != "DATABASE" and not self._database_checked(question_id):
                diagnostics.append({"code": "DATABASE_NOT_CHECKED", "message": "the canonical database must be searched before using a fallback", "path": path})
            references: list[str] = []
            provenance: dict[str, Any] = {}
            if source == "DATABASE":
                fields = [("sourceNodeIds", "sourceSpanIds")]
                if required_renditions:
                    fields.append(("counterpartSourceNodeIds", "counterpartSourceSpanIds"))
                records: list[dict[str, Any]] = []
                initial_diagnostic_count = len(diagnostics)
                for node_field, span_field in fields:
                    node_ids, span_ids = raw.get(node_field), raw.get(span_field, [])
                    if not isinstance(node_ids, list) or not node_ids or not all(isinstance(item, str) for item in node_ids):
                        diagnostics.append({"code": "INVALID_SOURCE_NODES", "message": f"database resolution requires {node_field}", "path": f"{path}.{node_field}"})
                        continue
                    if not isinstance(span_ids, list) or not all(isinstance(item, str) for item in span_ids):
                        diagnostics.append({"code": "INVALID_SOURCE_SPANS", "message": f"{span_field} must be an array", "path": f"{path}.{span_field}"})
                        continue
                    if len(node_ids) != len(set(node_ids)):
                        diagnostics.append({"code": "DUPLICATE_SOURCE_NODE", "message": f"{node_field} contains a duplicate", "path": f"{path}.{node_field}"})
                    if len(span_ids) != len(set(span_ids)):
                        diagnostics.append({"code": "DUPLICATE_SOURCE_SPAN", "message": f"{span_field} contains a duplicate", "path": f"{path}.{span_field}"})
                    for node_id in node_ids:
                        if node_id not in self.session.ledger.selectable_nodes:
                            diagnostics.append({"code": "NODE_NOT_EXPOSED", "message": f"node was not read with exact text: {node_id}", "path": f"{path}.{node_field}"})
                    for span_id in span_ids:
                        if span_id not in self.session.ledger.spans:
                            diagnostics.append({"code": "SPAN_NOT_EXPOSED", "message": f"span was not read with exact text: {span_id}", "path": f"{path}.{span_field}"})
                    try:
                        records.append(build_evidence_record(
                            self.query,
                            self.evidence_scope,
                            node_ids=node_ids,
                            span_ids=span_ids,
                            role=role,
                            tier="SUPPORTING",
                            rationale=rationale,
                            selection_basis={node: sorted(self.session.ledger.nodes.get(node, ())) for node in node_ids},
                        ))
                    except (EvidenceValidationError, KeyError) as exc:
                        if isinstance(exc, EvidenceValidationError):
                            diagnostics.extend(exc.diagnostics)
                        else:
                            diagnostics.append({"code": "INVALID_DATABASE_EVIDENCE", "message": str(exc), "path": path})
                if len(diagnostics) != initial_diagnostic_count:
                    continue
                if required_renditions and {record["sourceType"] for record in records} != required_renditions:
                    diagnostics.append({
                        "code": "UNPAIRED_SOURCE_RENDITION",
                        "message": "database evidence must select corresponding HTML and PDF passages",
                        "path": path,
                    })
                    continue
                if any(record["evidenceId"] in original_evidence for record in records):
                    diagnostics.append({"code": "DUPLICATE_EXISTING_EVIDENCE", "message": "selected database evidence is already in the bundle", "path": path})
                    continue
                # A paired canonical selection may answer more than one missing aspect.
                for record in records:
                    if record["evidenceId"] not in added_evidence:
                        added_evidence[record["evidenceId"]] = record
                        official_additions.append(record)
                    references.append(record["evidenceId"])
                provenance = {
                    "sourceNodeIds": records[0]["sourceNodeIds"],
                    "sourceSpanIds": records[0]["sourceSpanIds"],
                }
                if len(records) == 2:
                    provenance.update({
                        "counterpartSourceNodeIds": records[1]["sourceNodeIds"],
                        "counterpartSourceSpanIds": records[1]["sourceSpanIds"],
                    })
            elif source == "INTERNET":
                url, excerpt = raw.get("url"), raw.get("excerpt")
                if not isinstance(url, str) or not url.startswith(("https://", "http://")):
                    diagnostics.append({"code": "INVALID_URL", "message": "internet resolution requires an HTTP(S) URL", "path": f"{path}.url"})
                    continue
                if not isinstance(excerpt, str) or not normalize_text(excerpt):
                    diagnostics.append({"code": "EMPTY_EXCERPT", "message": "internet resolution requires a source excerpt", "path": f"{path}.excerpt"})
                    continue
                provenance = {"url": url, "excerpt": normalize_text(excerpt)}
            elif source == "RUNTIME":
                probe_id = raw.get("probeId")
                if probe_id not in self.probes:
                    diagnostics.append({"code": "UNKNOWN_PROBE", "message": f"runtime probe was not executed in this session: {probe_id}", "path": f"{path}.probeId"})
                    continue
                provenance = dict(self.probes[probe_id])
            elif source == "LLM_REASONING":
                provenance = {"model": QUESTION_MODEL, "reasoning": QUESTION_REASONING}

            if source in {"INTERNET", "RUNTIME", "LLM_REASONING"}:
                record = resolution_record(
                    self.scope,
                    question_id=question_id,
                    source_kind=source,
                    role=role,
                    statement=answer,
                    rationale=rationale,
                    provenance=provenance,
                )
                if record["resolutionId"] in existing_resolutions:
                    diagnostics.append({"code": "DUPLICATE_RESOLUTION", "message": "resolution already exists in the bundle", "path": path})
                    continue
                existing_resolutions.add(record["resolutionId"])
                supplemental.append(record)
                references.append(record["resolutionId"])
            question_results.append({
                **expected[question_id],
                "status": "OPEN" if source == "UNRESOLVED" else "RESOLVED",
                "resolutionSource": source,
                "answer": answer or None,
                "rationale": rationale,
                "references": references,
                "provenance": provenance,
            })
        missing = sorted(set(expected) - seen)
        for question_id in missing:
            diagnostics.append({"code": "MISSING_QUESTION", "message": f"question has no disposition: {question_id}", "path": "$.resolutions"})
        if diagnostics:
            return None, None, diagnostics
        question_results.sort(key=lambda item: item["questionId"])
        open_count = sum(item["status"] == "OPEN" for item in question_results)
        outcome = "UNRESOLVED" if open_count == len(question_results) else ("PARTIALLY_RESOLVED" if open_count else "RESOLVED")
        artifact = {
            "schemaVersion": 1,
            "phase": "OPEN_QUESTION_HANDLER",
            "planRunId": self.scope.plan_run_id,
            "language": self.scope.language,
            "version": self.scope.version,
            "unit": dict(self.scope.unit),
            "sourceDatabaseDigest": self.scope.source_database_digest,
            "inputEvidenceBundleHash": self.scope.evidence_bundle_hash,
            "inputSemanticRunId": self.scope.semantic_run_id,
            "handler": {"provider": "opencode", "model": QUESTION_MODEL, "reasoning": QUESTION_REASONING},
            "runId": self.scope.run_id,
            "createdAt": self.scope.created_at,
            "outcome": outcome,
            "questions": question_results,
            "databaseEvidenceAdded": [item["evidenceId"] for item in official_additions],
            "supplementalResolutionsAdded": [item["resolutionId"] for item in supplemental],
        }
        augmented = dict(self.bundle)
        augmented["evidence"] = sorted(
            [*self.bundle.get("evidence", []), *official_additions],
            key=lambda item: (0 if item.get("tier") == "CORE" else 1, item["evidenceId"]),
        )
        if self.bundle.get("resolutions") or supplemental:
            augmented["resolutions"] = sorted(
                [*self.bundle.get("resolutions", []), *supplemental],
                key=lambda item: item["resolutionId"],
            )
        return artifact, augmented, []

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.session.ledger.record_call(name, dict(arguments))
        if name == "spec_search":
            self._known_question(arguments["questionId"])
            value = self.session.search(
                arguments["query"], arguments["justification"], limit=arguments.get("limit", 20)
            )
        elif name == "spec_definitions":
            self._known_question(arguments["questionId"])
            value = self.session.definitions(arguments["query"], limit=arguments.get("limit", 20))
        elif name == "spec_show":
            value = self.session.show(arguments["nodeId"])
        elif name == "spec_children":
            value = self.session.children(arguments["nodeId"], limit=arguments.get("limit", 20))
        elif name == "spec_subtree":
            value = self.session.subtree(
                arguments["nodeId"], max_depth=arguments.get("maxDepth", 3), limit=arguments.get("limit", 20)
            )
        elif name == "spec_correlated":
            value = self.session.correlated(arguments["nodeId"])
        elif name == "execute_probe":
            value = self._execute_probe(arguments["questionId"], arguments.get("input"))
        elif name == "submit_questions":
            artifact, augmented, diagnostics = self._validate_submission(arguments)
            if diagnostics:
                value = {"accepted": False, "diagnostics": diagnostics}
            else:
                assert artifact is not None and augmented is not None
                temporary = self.submission_path.with_suffix(".tmp")
                temporary.write_text(
                    canonical_json({"artifact": artifact, "augmentedBundle": augmented}) + "\n",
                    encoding="utf-8",
                )
                os.replace(temporary, self.submission_path)
                value = {"accepted": True, "outcome": artifact["outcome"]}
        else:
            raise KeyError(f"unknown tool: {name}")
        self._write_trace()
        return {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False, sort_keys=True)}], "isError": False}

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
                    "serverInfo": {"name": "spec2lean-open-questions", "version": "1"},
                }
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": tool_definitions(runtime_available=bool(self.runtime_command))}
            elif method == "tools/call":
                params = message.get("params", {})
                result = self.call_tool(params.get("name", ""), params.get("arguments", {}))
            else:
                return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"method not found: {method}"}}
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except Exception as exc:
            self._write_trace()
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"}], "isError": True},
            }


def serve(
    database: Path,
    scope_path: Path,
    evidence_path: Path,
    submission_path: Path,
    trace_path: Path,
    runtime_command: tuple[str, ...],
) -> int:
    scope = OpenQuestionScope.from_dict(json.loads(scope_path.read_text(encoding="utf-8")))
    bundle = json.loads(evidence_path.read_text(encoding="utf-8"))
    server = OpenQuestionMcpServer(
        database, scope, bundle, submission_path, trace_path, runtime_command
    )
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
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--submission", type=Path, required=True)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--runtime-command-json", default="[]")
    args = parser.parse_args(argv)
    command = json.loads(args.runtime_command_json)
    if not isinstance(command, list) or not all(isinstance(item, str) for item in command):
        raise ValueError("runtime command must be a JSON array of strings")
    return serve(
        args.database.resolve(), args.scope.resolve(), args.evidence.resolve(),
        args.submission.resolve(), args.trace.resolve(), tuple(command),
    )


if __name__ == "__main__":
    raise SystemExit(main())
