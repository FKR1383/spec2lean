from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any, Iterable

from ..util import canonical_json, normalize_text, stable_id
from .models import EVIDENCE_ROLES, EVIDENCE_TIERS, EvidenceScope
from .query import EvidenceQuery, ExposureLedger


@dataclass(slots=True)
class EvidenceValidationError(ValueError):
    diagnostics: list[dict[str, str]]

    def __str__(self) -> str:
        return "; ".join(item["message"] for item in self.diagnostics)


def _diagnostic(code: str, message: str, path: str = "$") -> dict[str, str]:
    return {"code": code, "message": message, "path": path}


def _node_rows(query: EvidenceQuery, node_ids: list[str]) -> list[sqlite3.Row]:
    return [query._row(node_id) for node_id in node_ids]


def _canonical_nodes(
    query: EvidenceQuery, node_ids: list[str], path: str, diagnostics: list[dict[str, str]]
) -> tuple[list[str], list[sqlite3.Row]]:
    rows = _node_rows(query, node_ids)
    if len(rows) <= 1:
        return node_ids, rows
    documents = {row["document_id"] for row in rows}
    parents = {row["parent_id"] for row in rows}
    if len(documents) != 1 or len(parents) != 1:
        diagnostics.append(_diagnostic(
            "NONCONTIGUOUS_NODES",
            "a grouped evidence item must use adjacent sibling nodes from one document",
            path,
        ))
        return node_ids, rows
    ordered = sorted(rows, key=lambda row: (row["ordinal"], row["node_id"]))
    ordinals = [row["ordinal"] for row in ordered]
    if ordinals != list(range(ordinals[0], ordinals[0] + len(ordinals))):
        diagnostics.append(_diagnostic(
            "NONCONTIGUOUS_NODES", "grouped source nodes must be contiguous", path
        ))
    return [row["node_id"] for row in ordered], ordered


def _span_rows(
    query: EvidenceQuery,
    node_ids: list[str],
    span_ids: list[str],
    path: str,
    diagnostics: list[dict[str, str]],
) -> list[sqlite3.Row]:
    if not span_ids:
        return []
    placeholders = ",".join("?" for _ in span_ids)
    rows = query.connection.execute(
        f"SELECT * FROM source_spans WHERE span_id IN ({placeholders})", span_ids
    ).fetchall()
    by_id = {row["span_id"]: row for row in rows}
    for index, span_id in enumerate(span_ids):
        if span_id not in by_id:
            diagnostics.append(_diagnostic(
                "INVENTED_SOURCE_SPAN", f"source span does not exist: {span_id}", f"{path}[{index}]"
            ))
    allowed = set(node_ids)
    for row in rows:
        if row["node_id"] not in allowed:
            diagnostics.append(_diagnostic(
                "SPAN_NODE_MISMATCH",
                f"span {row['span_id']} does not belong to the selected source nodes",
                path,
            ))
    node_order = {node_id: index for index, node_id in enumerate(node_ids)}
    ordered = sorted(
        (row for row in rows if row["node_id"] in allowed),
        key=lambda row: (node_order[row["node_id"]], row["ordinal"], row["span_id"]),
    )
    by_node: dict[str, list[int]] = {}
    for row in ordered:
        by_node.setdefault(row["node_id"], []).append(row["ordinal"])
    for node_id, ordinals in by_node.items():
        if ordinals != list(range(ordinals[0], ordinals[0] + len(ordinals))):
            diagnostics.append(_diagnostic(
                "NONCONTIGUOUS_SPANS", f"selected spans are not contiguous in {node_id}", path
            ))
    missing_nodes = [node_id for node_id in node_ids if node_id not in by_node]
    if missing_nodes:
        diagnostics.append(_diagnostic(
            "SPAN_NODE_COVERAGE",
            f"when sourceSpanIds are used, at least one span is required for every source node: {missing_nodes}",
            path,
        ))
    return ordered


def _section(query: EvidenceQuery, node_id: str) -> tuple[str | None, str | None]:
    row = query.connection.execute(
        """WITH RECURSIVE lineage(node_id, parent_id, distance) AS (
               SELECT node_id, parent_id, 0 FROM nodes WHERE node_id = ?
               UNION ALL SELECT n.node_id, n.parent_id, l.distance + 1
               FROM nodes n JOIN lineage l ON n.node_id = l.parent_id
           )
           SELECT n.section_number, n.title FROM lineage l JOIN nodes n USING(node_id)
           WHERE n.node_type IN ('chapter', 'section', 'subsection')
           ORDER BY l.distance LIMIT 1""",
        (node_id,),
    ).fetchone()
    return (row["section_number"], row["title"]) if row else (None, None)


def _nearest_anchor(query: EvidenceQuery, node_id: str) -> str | None:
    row = query.connection.execute(
        """WITH RECURSIVE lineage(node_id, parent_id, distance) AS (
               SELECT node_id, parent_id, 0 FROM nodes WHERE node_id = ?
               UNION ALL SELECT n.node_id, n.parent_id, l.distance + 1
               FROM nodes n JOIN lineage l ON n.node_id = l.parent_id
           ) SELECT n.html_anchor FROM lineage l JOIN nodes n USING(node_id)
             WHERE n.html_anchor IS NOT NULL ORDER BY l.distance LIMIT 1""",
        (node_id,),
    ).fetchone()
    return str(row[0]) if row else None


def _bbox(spans: list[sqlite3.Row]) -> list[float] | None:
    boxes = [
        (row["bbox_x0"], row["bbox_y0"], row["bbox_x1"], row["bbox_y1"])
        for row in spans if row["bbox_x0"] is not None
    ]
    pages = {row["page_number"] for row in spans if row["page_number"] is not None}
    if not boxes or len(pages) != 1:
        return None
    return [
        min(box[0] for box in boxes), min(box[1] for box in boxes),
        max(box[2] for box in boxes), max(box[3] for box in boxes),
    ]


def _span_text(spans: list[sqlite3.Row]) -> str:
    if not spans:
        return ""
    pieces: list[str] = []
    previous: sqlite3.Row | None = None
    for row in spans:
        if previous is not None:
            if row["node_id"] != previous["node_id"]:
                pieces.append("\n")
            elif row["line_index"] is not None and row["line_index"] != previous["line_index"]:
                pieces.append("\n")
        pieces.append(row["raw_text"])
        previous = row
    return "".join(pieces)


def _fragment(
    query: EvidenceQuery, row: sqlite3.Row, selected_spans: list[sqlite3.Row]
) -> dict[str, Any]:
    section_number, section_title = _section(query, row["node_id"])
    spans = selected_spans or query.connection.execute(
        "SELECT * FROM source_spans WHERE node_id = ? ORDER BY ordinal", (row["node_id"],)
    ).fetchall()
    return {
        "sourceNodeId": row["node_id"],
        "nodeType": row["node_type"],
        "sectionNumber": section_number,
        "sectionTitle": section_title,
        "htmlAnchor": _nearest_anchor(query, row["node_id"]) if row["source_type"] == "html" else None,
        "pageStart": row["page_start"],
        "pageEnd": row["page_end"],
        "sourceSpans": [query._span_public(span) for span in spans],
    }


def build_evidence_record(
    query: EvidenceQuery,
    scope: EvidenceScope,
    *,
    node_ids: list[str],
    span_ids: list[str],
    role: str,
    tier: str,
    rationale: str,
    selection_basis: dict[str, list[str]],
) -> dict[str, Any]:
    diagnostics: list[dict[str, str]] = []
    node_ids, rows = _canonical_nodes(query, node_ids, "$.sourceNodeIds", diagnostics)
    spans = _span_rows(query, node_ids, span_ids, "$.sourceSpanIds", diagnostics)
    if diagnostics:
        raise EvidenceValidationError(diagnostics)
    spans_by_node: dict[str, list[sqlite3.Row]] = {}
    for span in spans:
        spans_by_node.setdefault(span["node_id"], []).append(span)
    fragments = [_fragment(query, row, spans_by_node.get(row["node_id"], [])) for row in rows]
    exact_text = _span_text(spans) if spans else "\n".join(row["raw_text"] for row in rows)
    document = rows[0]
    all_provenance_spans = [
        span
        for fragment in fragments
        for span in query.connection.execute(
            "SELECT * FROM source_spans WHERE node_id = ? ORDER BY ordinal",
            (fragment["sourceNodeId"],),
        )
    ] if not spans else spans
    pages = sorted({row["page_number"] for row in all_provenance_spans if row["page_number"] is not None})
    sections = {(fragment["sectionNumber"], fragment["sectionTitle"]) for fragment in fragments}
    anchors = {fragment["htmlAnchor"] for fragment in fragments if fragment["htmlAnchor"] is not None}
    identity = {
        "sourceDatabaseDigest": scope.source_database_digest,
        "sourceNodeIds": node_ids,
        "sourceSpanIds": [row["span_id"] for row in spans],
        "role": role,
        "tier": tier,
    }
    return {
        "evidenceId": stable_id("evidence", canonical_json(identity), length=32),
        "unitId": scope.unit_id,
        "role": role,
        "tier": tier,
        "rationale": normalize_text(rationale),
        "sourceNodeId": node_ids[0],
        "sourceNodeIds": node_ids,
        "sourceSpanIds": [row["span_id"] for row in spans],
        "sourceType": document["source_type"],
        "sectionNumber": next(iter(sections))[0] if len(sections) == 1 else None,
        "sectionTitle": next(iter(sections))[1] if len(sections) == 1 else None,
        "exactText": exact_text,
        "documentId": document["document_id"],
        "documentSha256": document["sha256"],
        "sourcePath": document["local_path"],
        "officialUrl": document["official_url"],
        "htmlAnchor": next(iter(anchors)) if len(anchors) == 1 else None,
        "pdfPage": pages[0] if len(pages) == 1 else None,
        "bbox": _bbox(all_provenance_spans),
        "selectionBasis": [
            {"sourceNodeId": node_id, "basis": sorted(selection_basis.get(node_id, []))}
            for node_id in node_ids
        ],
        "provenance": fragments,
    }


def validate_submission(
    query: EvidenceQuery,
    scope: EvidenceScope,
    ledger: ExposureLedger,
    submission: Any,
) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    diagnostics: list[dict[str, str]] = []
    if not isinstance(submission, dict):
        return None, [_diagnostic("EXPECTED_OBJECT", "submission must be an object")]
    unexpected = sorted(set(submission) - {"unitId", "selections"})
    for key in unexpected:
        diagnostics.append(_diagnostic(
            "UNEXPECTED_FIELD", f"semantic or unsupported submission field is not allowed: {key}", f"$.{key}"
        ))
    if submission.get("unitId") != scope.unit_id:
        diagnostics.append(_diagnostic(
            "WRONG_UNIT", f"submission unit must be {scope.unit_id}", "$.unitId"
        ))
    raw_selections = submission.get("selections")
    if not isinstance(raw_selections, list):
        return None, diagnostics + [_diagnostic("EXPECTED_ARRAY", "$.selections must be an array", "$.selections")]
    if not raw_selections:
        diagnostics.append(_diagnostic("EMPTY_EVIDENCE", "at least one evidence selection is required", "$.selections"))

    records: list[dict[str, Any]] = []
    seen_selections: set[tuple[tuple[str, ...], tuple[str, ...]]] = set()
    for index, raw in enumerate(raw_selections):
        path = f"$.selections[{index}]"
        if not isinstance(raw, dict):
            diagnostics.append(_diagnostic("INVALID_SELECTION", "selection must be an object", path))
            continue
        unexpected = sorted(set(raw) - {"sourceNodeIds", "sourceSpanIds", "role", "tier", "rationale"})
        for key in unexpected:
            diagnostics.append(_diagnostic("UNEXPECTED_FIELD", f"unsupported selection field: {key}", f"{path}.{key}"))
        node_ids = raw.get("sourceNodeIds")
        span_ids = raw.get("sourceSpanIds", [])
        if not isinstance(node_ids, list) or not node_ids:
            diagnostics.append(_diagnostic("INVALID_SOURCE_NODES", "sourceNodeIds must be a non-empty array", f"{path}.sourceNodeIds"))
            continue
        if not all(isinstance(item, str) for item in node_ids):
            diagnostics.append(_diagnostic("INVALID_SOURCE_NODE", "every source node ID must be a string", f"{path}.sourceNodeIds"))
            continue
        if len(set(node_ids)) != len(node_ids):
            diagnostics.append(_diagnostic("DUPLICATE_SOURCE_NODE", "sourceNodeIds contains a duplicate", f"{path}.sourceNodeIds"))
        if not isinstance(span_ids, list) or not all(isinstance(item, str) for item in span_ids):
            diagnostics.append(_diagnostic("INVALID_SOURCE_SPANS", "sourceSpanIds must be an array of strings", f"{path}.sourceSpanIds"))
            continue
        if len(set(span_ids)) != len(span_ids):
            diagnostics.append(_diagnostic("DUPLICATE_SOURCE_SPAN", "sourceSpanIds contains a duplicate", f"{path}.sourceSpanIds"))
        missing_nodes = [item for item in node_ids if not query.node_exists(item)]
        for node_id in missing_nodes:
            diagnostics.append(_diagnostic("INVENTED_SOURCE_NODE", f"source node does not exist: {node_id}", f"{path}.sourceNodeIds"))
        for node_id in node_ids:
            if node_id not in ledger.selectable_nodes:
                diagnostics.append(_diagnostic(
                    "NODE_NOT_EXPOSED", f"source node was not exposed with exact text in this session: {node_id}",
                    f"{path}.sourceNodeIds",
                ))
        for span_id in span_ids:
            if span_id not in ledger.spans:
                diagnostics.append(_diagnostic(
                    "SPAN_NOT_EXPOSED", f"source span was not exposed in this session: {span_id}",
                    f"{path}.sourceSpanIds",
                ))
        role, tier, rationale = raw.get("role"), raw.get("tier"), raw.get("rationale")
        if role not in EVIDENCE_ROLES:
            diagnostics.append(_diagnostic("INVALID_ROLE", f"invalid evidence role: {role!r}", f"{path}.role"))
        if tier not in EVIDENCE_TIERS:
            diagnostics.append(_diagnostic("INVALID_TIER", f"invalid evidence tier: {tier!r}", f"{path}.tier"))
        if not isinstance(rationale, str) or not normalize_text(rationale):
            diagnostics.append(_diagnostic("EMPTY_RATIONALE", "relevance rationale must be non-empty", f"{path}.rationale"))
        if missing_nodes or role not in EVIDENCE_ROLES or tier not in EVIDENCE_TIERS or not isinstance(rationale, str):
            continue
        local_diagnostics: list[dict[str, str]] = []
        canonical_nodes, _ = _canonical_nodes(query, node_ids, f"{path}.sourceNodeIds", local_diagnostics)
        spans = _span_rows(query, canonical_nodes, span_ids, f"{path}.sourceSpanIds", local_diagnostics)
        diagnostics.extend(local_diagnostics)
        key = (tuple(canonical_nodes), tuple(row["span_id"] for row in spans))
        if key in seen_selections:
            diagnostics.append(_diagnostic("DUPLICATE_EVIDENCE", "identical source evidence was selected more than once", path))
            continue
        seen_selections.add(key)
        if local_diagnostics:
            continue
        try:
            record = build_evidence_record(
                query, scope,
                node_ids=canonical_nodes,
                span_ids=[row["span_id"] for row in spans],
                role=role,
                tier=tier,
                rationale=rationale,
                selection_basis={node: sorted(ledger.nodes.get(node, ())) for node in canonical_nodes},
            )
            if not record["exactText"]:
                diagnostics.append(_diagnostic(
                    "EMPTY_EVIDENCE_TEXT", "selected evidence resolves to empty Phase-1 text", path
                ))
            else:
                records.append(record)
        except EvidenceValidationError as exc:
            diagnostics.extend(exc.diagnostics)

    if records and not any(item["tier"] == "CORE" for item in records):
        diagnostics.append(_diagnostic("MISSING_CORE_EVIDENCE", "a valid bundle requires at least one CORE item", "$.selections"))
    evidence_ids = [item["evidenceId"] for item in records]
    if len(evidence_ids) != len(set(evidence_ids)):
        diagnostics.append(_diagnostic("DUPLICATE_EVIDENCE_ID", "evidence IDs must be unique", "$.selections"))
    if diagnostics:
        return None, diagnostics
    records.sort(key=lambda item: (EVIDENCE_TIERS.index(item["tier"]), item["evidenceId"]))
    bundle = {
        "schemaVersion": 1,
        "phase": "RETRIEVE_EVIDENCE",
        "planRunId": scope.plan_run_id,
        "language": scope.language,
        "version": scope.version,
        "sourceDatabaseDigest": scope.source_database_digest,
        "unit": dict(scope.unit),
        "evidence": records,
    }
    return bundle, []


def validate_bundle(
    query: EvidenceQuery,
    plan: dict[str, Any],
    bundle: Any,
    *,
    exposed_node_ids: Iterable[str] | None = None,
    exposure_basis: dict[str, list[str]] | None = None,
) -> list[dict[str, str]]:
    """Rebuild every deterministic field and compare a stored canonical bundle to Phase 1."""
    diagnostics: list[dict[str, str]] = []
    if not isinstance(bundle, dict):
        return [_diagnostic("EXPECTED_OBJECT", "evidence bundle must be an object")]
    bundle_fields = {
        "schemaVersion", "phase", "planRunId", "language", "version",
        "sourceDatabaseDigest", "unit", "evidence",
    }
    for key in sorted(set(bundle) - bundle_fields):
        diagnostics.append(_diagnostic(
            "UNEXPECTED_FIELD", f"unsupported or semantic bundle field is not allowed: {key}", f"$.{key}"
        ))
    unit = bundle.get("unit")
    unit_id = unit.get("unitId") if isinstance(unit, dict) else None
    try:
        scope = EvidenceScope.from_plan(plan, unit_id)
    except KeyError:
        return [_diagnostic("WRONG_UNIT", f"bundle unit is not in the Phase-2 plan: {unit_id}", "$.unit.unitId")]
    if bundle.get("planRunId") != plan.get("planRunId"):
        diagnostics.append(_diagnostic("PLAN_MISMATCH", "bundle planRunId does not match Phase 2", "$.planRunId"))
    if bundle.get("sourceDatabaseDigest") != query.source_database_digest():
        diagnostics.append(_diagnostic("DATABASE_DIGEST_MISMATCH", "bundle database digest does not match Phase 1", "$.sourceDatabaseDigest"))
    if plan.get("sourceDatabaseDigest") != query.source_database_digest():
        diagnostics.append(_diagnostic("PLAN_DATABASE_MISMATCH", "Phase-2 plan does not match this Phase-1 database", "$.sourceDatabaseDigest"))
    evidence = bundle.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        diagnostics.append(_diagnostic("EMPTY_EVIDENCE", "bundle evidence must be a non-empty array", "$.evidence"))
        return diagnostics
    exposed = set(exposed_node_ids) if exposed_node_ids is not None else None
    seen_ids: set[str] = set()
    seen_sources: set[tuple[tuple[str, ...], tuple[str, ...]]] = set()
    for index, item in enumerate(evidence):
        path = f"$.evidence[{index}]"
        if not isinstance(item, dict):
            diagnostics.append(_diagnostic("INVALID_EVIDENCE", "evidence item must be an object", path))
            continue
        record_fields = {
            "evidenceId", "unitId", "role", "tier", "rationale", "sourceNodeId",
            "sourceNodeIds", "sourceSpanIds", "sourceType", "sectionNumber", "sectionTitle",
            "exactText", "documentId", "documentSha256", "sourcePath", "officialUrl",
            "htmlAnchor", "pdfPage", "bbox", "selectionBasis", "provenance",
        }
        for key in sorted(set(item) - record_fields):
            diagnostics.append(_diagnostic(
                "UNEXPECTED_FIELD", f"unsupported or semantic evidence field is not allowed: {key}", f"{path}.{key}"
            ))
        node_ids = item.get("sourceNodeIds", [])
        span_ids = item.get("sourceSpanIds", [])
        if not isinstance(node_ids, list) or not node_ids or not all(isinstance(x, str) for x in node_ids):
            diagnostics.append(_diagnostic("INVALID_SOURCE_NODES", "invalid sourceNodeIds", f"{path}.sourceNodeIds"))
            continue
        if exposed is not None:
            for node_id in node_ids:
                if node_id not in exposed:
                    diagnostics.append(_diagnostic("NODE_NOT_EXPOSED", f"node was not exposed: {node_id}", f"{path}.sourceNodeIds"))
        if item.get("unitId") != unit_id:
            diagnostics.append(_diagnostic("WRONG_UNIT", "evidence item unit does not match bundle unit", f"{path}.unitId"))
        if item.get("role") not in EVIDENCE_ROLES:
            diagnostics.append(_diagnostic("INVALID_ROLE", f"invalid evidence role: {item.get('role')!r}", f"{path}.role"))
            continue
        if item.get("tier") not in EVIDENCE_TIERS:
            diagnostics.append(_diagnostic("INVALID_TIER", f"invalid evidence tier: {item.get('tier')!r}", f"{path}.tier"))
            continue
        if not isinstance(item.get("rationale"), str) or not normalize_text(item["rationale"]):
            diagnostics.append(_diagnostic("EMPTY_RATIONALE", "evidence rationale must be non-empty", f"{path}.rationale"))
        if not isinstance(item.get("exactText"), str) or not item["exactText"]:
            diagnostics.append(_diagnostic("EMPTY_EVIDENCE_TEXT", "evidence exact text must be non-empty", f"{path}.exactText"))
        try:
            rebuilt = build_evidence_record(
                query, scope,
                node_ids=node_ids,
                span_ids=span_ids if isinstance(span_ids, list) else [],
                role=item["role"], tier=item["tier"], rationale=item.get("rationale", ""),
                selection_basis=(
                    {node_id: exposure_basis.get(node_id, []) for node_id in node_ids}
                    if exposure_basis is not None else
                    {entry["sourceNodeId"]: entry.get("basis", []) for entry in item.get("selectionBasis", [])}
                ),
            )
        except (EvidenceValidationError, KeyError) as exc:
            if isinstance(exc, EvidenceValidationError):
                diagnostics.extend(exc.diagnostics)
            else:
                diagnostics.append(_diagnostic("INVENTED_SOURCE_NODE", str(exc), f"{path}.sourceNodeIds"))
            continue
        for field in (
            "evidenceId", "sourceNodeId", "sourceNodeIds", "sourceSpanIds", "sourceType",
            "sectionNumber", "sectionTitle", "exactText", "documentId", "documentSha256",
            "sourcePath", "officialUrl", "htmlAnchor", "pdfPage", "bbox", "provenance",
        ):
            if item.get(field) != rebuilt.get(field):
                code = {
                    "exactText": "EXACT_TEXT_MISMATCH",
                    "documentSha256": "DOCUMENT_SHA_MISMATCH",
                    "htmlAnchor": "HTML_PROVENANCE_MISMATCH",
                    "pdfPage": "PDF_PROVENANCE_MISMATCH",
                    "bbox": "PDF_PROVENANCE_MISMATCH",
                    "provenance": "SOURCE_PROVENANCE_MISMATCH",
                }.get(field, "DETERMINISTIC_FIELD_MISMATCH")
                diagnostics.append(_diagnostic(code, f"stored {field} does not match Phase 1", f"{path}.{field}"))
        if exposure_basis is not None and item.get("selectionBasis") != rebuilt.get("selectionBasis"):
            diagnostics.append(_diagnostic(
                "SELECTION_BASIS_MISMATCH",
                "stored selection basis does not match the deterministic session exposure trace",
                f"{path}.selectionBasis",
            ))
        evidence_id = item.get("evidenceId")
        if evidence_id in seen_ids:
            diagnostics.append(_diagnostic("DUPLICATE_EVIDENCE_ID", f"duplicate evidence ID: {evidence_id}", f"{path}.evidenceId"))
        seen_ids.add(evidence_id)
        source_key = (tuple(node_ids), tuple(span_ids) if isinstance(span_ids, list) else ())
        if source_key in seen_sources:
            diagnostics.append(_diagnostic("DUPLICATE_EVIDENCE", "duplicate identical source evidence", path))
        seen_sources.add(source_key)
    if not any(isinstance(item, dict) and item.get("tier") == "CORE" for item in evidence):
        diagnostics.append(_diagnostic("MISSING_CORE_EVIDENCE", "bundle has no CORE evidence", "$.evidence"))
    return diagnostics
