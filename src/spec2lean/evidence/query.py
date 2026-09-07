from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from ..planning.scope import MAX_TOOL_ROWS, Phase1Query
from ..util import normalize_text
from .models import EvidenceScope


MAX_NODE_TEXT_CHARS = 24_000


def _node_summary(row: sqlite3.Row, *, include_text: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {
        "nodeId": row["node_id"],
        "nodeType": row["node_type"],
        "title": row["title"],
        "sectionNumber": row["section_number"],
        "sourceType": row["source_type"],
        "htmlAnchor": row["html_anchor"],
        "pageStart": row["page_start"],
        "pageEnd": row["page_end"],
    }
    if include_text:
        result["exactText"] = row["raw_text"][:MAX_NODE_TEXT_CHARS]
        result["textTruncated"] = len(row["raw_text"]) > MAX_NODE_TEXT_CHARS
    return result


class EvidenceQuery:
    """Read-only Phase-1 access and deterministic source reconstruction."""

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self.phase1 = Phase1Query(connection)

    def node_exists(self, node_id: str) -> bool:
        return self.phase1.node_exists(node_id)

    def span_exists(self, span_id: str) -> bool:
        return self.connection.execute(
            "SELECT 1 FROM source_spans WHERE span_id = ?", (span_id,)
        ).fetchone() is not None

    def _row(self, node_id: str) -> sqlite3.Row:
        row = self.connection.execute(
            """SELECT n.*, d.source_type, d.sha256, d.local_path, d.official_url
               FROM nodes n JOIN documents d USING(document_id) WHERE n.node_id = ?""",
            (node_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown node: {node_id}")
        return row

    def show(self, node_id: str) -> dict[str, Any]:
        row = self._row(node_id)
        result = _node_summary(row, include_text=True)
        result["metadata"] = json.loads(row["metadata_json"])
        result["sourceSpans"] = [self._span_public(item) for item in self.connection.execute(
            "SELECT * FROM source_spans WHERE node_id = ? ORDER BY ordinal", (node_id,)
        )]
        result["document"] = {
            "documentId": row["document_id"],
            "sha256": row["sha256"],
            "localPath": row["local_path"],
            "officialUrl": row["official_url"],
        }
        return result

    @staticmethod
    def _span_public(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "spanId": row["span_id"],
            "ordinal": row["ordinal"],
            "exactText": row["raw_text"],
            "page": row["page_number"],
            "bbox": (
                [row["bbox_x0"], row["bbox_y0"], row["bbox_x1"], row["bbox_y1"]]
                if row["bbox_x0"] is not None else None
            ),
            "blockIndex": row["block_index"],
            "lineIndex": row["line_index"],
            "spanIndex": row["span_index"],
            "domPath": row["dom_path"],
            "sourceLineStart": row["source_line_start"],
            "sourceLineEnd": row["source_line_end"],
        }

    def children(self, node_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
        Phase1Query._bounded_limit(limit)
        return [_node_summary(row) for row in self.connection.execute(
            """SELECT n.*, d.source_type FROM nodes n JOIN documents d USING(document_id)
               WHERE n.document_id = (SELECT document_id FROM nodes WHERE node_id = ?)
                 AND n.parent_id = ? ORDER BY n.ordinal, n.node_id LIMIT ?""",
            (node_id, node_id, limit),
        )]

    def ancestors(self, node_id: str, *, limit: int = 30) -> list[dict[str, Any]]:
        return self.phase1.ancestors(node_id, limit=limit)

    def subtree(self, node_id: str, *, max_depth: int = 3, limit: int = 20) -> list[dict[str, Any]]:
        if max_depth < 0 or max_depth > 8:
            raise ValueError("max_depth must be between 0 and 8")
        Phase1Query._bounded_limit(limit)
        rows = self.connection.execute(
            """WITH RECURSIVE tree(node_id, distance, path) AS (
                   SELECT node_id, 0, printf('%08d', ordinal) FROM nodes WHERE node_id = ?
                   UNION ALL
                   SELECT n.node_id, t.distance + 1, t.path || '/' || printf('%08d', n.ordinal)
                   FROM nodes n JOIN tree t ON n.parent_id = t.node_id WHERE t.distance < ?
               )
               SELECT n.*, d.source_type FROM tree t JOIN nodes n USING(node_id)
               JOIN documents d USING(document_id) ORDER BY t.path, n.node_id LIMIT ?""",
            (node_id, max_depth, limit),
        ).fetchall()
        return [_node_summary(row, include_text=True) | {
            "sourceSpanIds": [item[0] for item in self.connection.execute(
                "SELECT span_id FROM source_spans WHERE node_id = ? ORDER BY ordinal", (row["node_id"],)
            )]
        } for row in rows]

    def search(self, text: str, *, limit: int = 20) -> list[dict[str, Any]]:
        return self.phase1.search(text, limit=limit)

    def xrefs(self, node_id: str) -> list[dict[str, Any]]:
        values = self.phase1.xrefs(node_id)
        for value in values:
            target = value.get("resolved_target_node_id")
            if target:
                value["resolvedTarget"] = _node_summary(self._row(target))
        return values

    def definitions(self, text: str, *, limit: int = 20) -> list[dict[str, Any]]:
        if not normalize_text(text):
            raise ValueError("definition query must be non-empty")
        return self.phase1.definitions(text, limit=limit)

    def correlated(self, node_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """SELECT c.*, CASE WHEN c.left_node_id = ? THEN c.right_node_id ELSE c.left_node_id END AS other_node_id
               FROM node_correlations c WHERE c.left_node_id = ? OR c.right_node_id = ?
               ORDER BY c.correlation_id LIMIT ?""",
            (node_id, node_id, node_id, MAX_TOOL_ROWS),
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["correlatedNode"] = _node_summary(self._row(row["other_node_id"]))
            result.append(item)
        return result

    def source_database_digest(self) -> str:
        row = self.connection.execute(
            "SELECT semantic_digest FROM builds WHERE status = 'COMPLETE' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        if row is None or not row[0]:
            raise ValueError("Phase 1 database has no completed semantic digest")
        return str(row[0])


@dataclass(slots=True)
class ExposureLedger:
    """Records precisely which identifiers the current model session received."""

    nodes: dict[str, set[str]] = field(default_factory=dict)
    selectable_nodes: set[str] = field(default_factory=set)
    spans: set[str] = field(default_factory=set)
    calls: list[dict[str, Any]] = field(default_factory=list)

    def expose(self, node_id: str, basis: str, *, selectable: bool = False, spans: list[str] | None = None) -> None:
        self.nodes.setdefault(node_id, set()).add(basis)
        if selectable:
            self.selectable_nodes.add(node_id)
        self.spans.update(spans or ())

    def require_discovered(self, node_id: str) -> None:
        if node_id not in self.nodes:
            raise ValueError(f"node is outside the bounded session context: {node_id}")

    def record_call(self, name: str, arguments: dict[str, Any]) -> None:
        self.calls.append({"tool": name, "arguments": arguments})

    def to_dict(self) -> dict[str, Any]:
        return {
            "exposedNodes": [
                {"nodeId": node, "basis": sorted(bases), "selectable": node in self.selectable_nodes}
                for node, bases in sorted(self.nodes.items())
            ],
            "exposedSpanIds": sorted(self.spans),
            "toolCalls": list(self.calls),
        }


class SessionQuery:
    """Capability boundary around EvidenceQuery for one planned unit."""

    def __init__(self, query: EvidenceQuery, scope: EvidenceScope):
        self.query = query
        self.scope = scope
        self.ledger = ExposureLedger()
        for node_id, basis in scope.seed_nodes:
            if not query.node_exists(node_id):
                raise ValueError(f"Phase 2 references a nonexistent Phase-1 node: {node_id}")
            details = query.show(node_id)
            self.ledger.expose(
                node_id, basis, selectable=True,
                spans=[item["spanId"] for item in details["sourceSpans"]],
            )

    def show(self, node_id: str) -> dict[str, Any]:
        self.ledger.require_discovered(node_id)
        value = self.query.show(node_id)
        self.ledger.expose(
            node_id, "SHOW", selectable=True,
            spans=[item["spanId"] for item in value["sourceSpans"]],
        )
        return value

    def children(self, node_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
        self.ledger.require_discovered(node_id)
        values = self.query.children(node_id, limit=limit)
        for item in values:
            self.ledger.expose(item["nodeId"], f"CHILD_OF:{node_id}")
        return values

    def ancestors(self, node_id: str) -> list[dict[str, Any]]:
        self.ledger.require_discovered(node_id)
        values = self.query.ancestors(node_id)
        for item in values:
            self.ledger.expose(item["nodeId"], f"ANCESTOR_OF:{node_id}")
        return values

    def subtree(self, node_id: str, *, max_depth: int = 3, limit: int = 20) -> list[dict[str, Any]]:
        self.ledger.require_discovered(node_id)
        values = self.query.subtree(node_id, max_depth=max_depth, limit=limit)
        for item in values:
            self.ledger.expose(
                item["nodeId"], f"SUBTREE_OF:{node_id}", selectable=True,
                spans=item["sourceSpanIds"],
            )
        return values

    def search(self, text: str, justification: str, *, limit: int = 20) -> list[dict[str, Any]]:
        if not normalize_text(justification):
            raise ValueError("bounded search requires a relevance justification")
        values = self.query.search(text, limit=limit)
        for item in values:
            self.ledger.expose(item["nodeId"], f"SEARCH:{normalize_text(justification)}")
        return values

    def xrefs(self, node_id: str) -> list[dict[str, Any]]:
        self.ledger.require_discovered(node_id)
        values = self.query.xrefs(node_id)
        for item in values:
            for candidate in (item.get("source_node_id"), item.get("resolved_target_node_id")):
                if candidate:
                    self.ledger.expose(candidate, f"XREF_OF:{node_id}")
        return values

    def definitions(self, text: str, *, limit: int = 20) -> list[dict[str, Any]]:
        values = self.query.definitions(text, limit=limit)
        for item in values:
            self.ledger.expose(item["node_id"], f"DEFINITION:{normalize_text(text)}")
        return values

    def correlated(self, node_id: str) -> list[dict[str, Any]]:
        self.ledger.require_discovered(node_id)
        values = self.query.correlated(node_id)
        for item in values:
            self.ledger.expose(item["other_node_id"], f"CORRELATED_WITH:{node_id}")
        return values
