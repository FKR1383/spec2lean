from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

from lxml import html

from .constants import INDEX_SCHEMA_VERSION, PARSER_VERSION
from .database import utc_now
from .page_text import page_text_path, render_pdf_page_text
from .util import normalize_text, sha256_file, stable_id


def statistics(connection: sqlite3.Connection) -> dict[str, Any]:
    database_file = next(
        (row["file"] for row in connection.execute("PRAGMA database_list") if row["name"] == "main"),
        "",
    )
    index_directory = Path(database_file).resolve().parent if database_file else Path.cwd()
    documents = [dict(row) for row in connection.execute(
        """SELECT document_id, source_type, title, local_path, sha256, byte_size,
                  page_count, source_text_chars, indexed_text_chars, parser_stats_json
           FROM documents ORDER BY source_type, document_id"""
    )]
    for document in documents:
        document["coverage_ratio"] = round(
            document["indexed_text_chars"] / max(document["source_text_chars"], 1), 6
        )
        document["parser_stats"] = json.loads(document.pop("parser_stats_json"))
        if document["source_type"] == "pdf":
            artifact = page_text_path(index_directory, document["local_path"], document["sha256"])
            document["page_text_path"] = str(artifact)
            document["page_text_exists"] = artifact.is_file()
            if artifact.is_file():
                document["page_text_bytes"] = artifact.stat().st_size
    node_types = {
        row["node_type"]: row["count"]
        for row in connection.execute(
            "SELECT node_type, count(*) AS count FROM nodes GROUP BY node_type ORDER BY node_type"
        )
    }
    references = {
        row["resolution_status"]: row["count"]
        for row in connection.execute(
            """SELECT resolution_status, count(*) AS count FROM cross_references
               GROUP BY resolution_status ORDER BY resolution_status"""
        )
    }
    return {
        "documents": documents,
        "totals": {
            "documents": len(documents),
            "pages": connection.execute("SELECT count(*) FROM pages").fetchone()[0],
            "nodes": connection.execute("SELECT count(*) FROM nodes").fetchone()[0],
            "source_spans": connection.execute("SELECT count(*) FROM source_spans").fetchone()[0],
            "definitions": connection.execute("SELECT count(*) FROM definitions").fetchone()[0],
            "terms": connection.execute("SELECT count(*) FROM terms").fetchone()[0],
            "cross_references": connection.execute("SELECT count(*) FROM cross_references").fetchone()[0],
            "correlations": connection.execute("SELECT count(*) FROM node_correlations").fetchone()[0],
        },
        "node_types": node_types,
        "cross_reference_statuses": references,
    }


def _issue(issues: list[dict[str, Any]], code: str, message: str, *, severity: str = "ERROR", **context: Any) -> None:
    issues.append({"severity": severity, "code": code, "message": message, "context": context})


def validate_database(connection: sqlite3.Connection) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    checks: Counter[str] = Counter()
    database_file = next(
        (row["file"] for row in connection.execute("PRAGMA database_list") if row["name"] == "main"),
        "",
    )
    index_directory = Path(database_file).resolve().parent if database_file else Path.cwd()

    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    checks["sqlite_integrity"] += 1
    if integrity != "ok":
        _issue(issues, "SQLITE_INTEGRITY", str(integrity))
    foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
    checks["foreign_keys"] += 1
    if foreign_keys:
        _issue(issues, "FOREIGN_KEYS", f"{len(foreign_keys)} foreign-key violations")

    build = connection.execute("SELECT * FROM builds ORDER BY created_at DESC LIMIT 1").fetchone()
    if not build:
        _issue(issues, "BUILD_MISSING", "database has no build record")
    else:
        checks["version_metadata"] += 1
        if build["schema_version"] != INDEX_SCHEMA_VERSION:
            _issue(issues, "STALE_SCHEMA", "index schema version differs from running code")
        if build["parser_version"] != PARSER_VERSION:
            _issue(issues, "STALE_PARSER", "parser version differs from running code")

    nodes = connection.execute(
        "SELECT node_id, document_id, parent_id, ordinal, depth FROM nodes ORDER BY node_id"
    ).fetchall()
    by_id = {row["node_id"]: row for row in nodes}
    checks["node_identity"] += len(nodes)
    roots: Counter[str] = Counter()
    siblings: dict[tuple[str, str | None], list[int]] = {}
    for row in nodes:
        if row["parent_id"] is None:
            roots[row["document_id"]] += 1
            if row["depth"] != 0:
                _issue(issues, "ROOT_DEPTH", "root depth is not zero", node_id=row["node_id"])
        else:
            parent = by_id.get(row["parent_id"])
            if parent is None:
                _issue(issues, "PARENT_MISSING", "node parent does not exist", node_id=row["node_id"])
            elif parent["document_id"] != row["document_id"]:
                _issue(issues, "CROSS_DOCUMENT_PARENT", "parent belongs to another document", node_id=row["node_id"])
            elif row["depth"] != parent["depth"] + 1:
                _issue(issues, "DEPTH_MISMATCH", "stored depth does not match parent", node_id=row["node_id"])
        siblings.setdefault((row["document_id"], row["parent_id"]), []).append(row["ordinal"])

        seen: set[str] = set()
        cursor = row
        while cursor["parent_id"] is not None:
            if cursor["node_id"] in seen:
                _issue(issues, "PARENT_CYCLE", "cycle detected", node_id=row["node_id"])
                break
            seen.add(cursor["node_id"])
            cursor = by_id.get(cursor["parent_id"])
            if cursor is None:
                break
    for key, ordinals in siblings.items():
        checks["sibling_order"] += 1
        if sorted(ordinals) != list(range(len(ordinals))):
            _issue(issues, "ORDINAL_GAP", "sibling ordinals are not contiguous", group=key, ordinals=ordinals)
    for document_id in [row["document_id"] for row in connection.execute("SELECT document_id FROM documents")]:
        if roots[document_id] != 1:
            _issue(issues, "ROOT_COUNT", "document must have exactly one root", document_id=document_id, count=roots[document_id])

    for document in connection.execute("SELECT * FROM documents ORDER BY document_id"):
        path = Path(document["local_path"])
        checks["source_identity"] += 1
        if not path.is_file():
            _issue(issues, "SOURCE_MISSING", "source file is unavailable", document_id=document["document_id"], path=str(path))
            continue
        actual_sha = sha256_file(path)
        if actual_sha != document["sha256"]:
            _issue(
                issues,
                "STALE_SOURCE_SHA",
                "source SHA-256 differs from indexed manifest",
                document_id=document["document_id"],
                expected=document["sha256"],
                actual=actual_sha,
            )
            continue

        if document["source_type"] == "pdf":
            pages = connection.execute(
                "SELECT page_number, width, height, raw_text FROM pages WHERE document_id = ? ORDER BY page_number",
                (document["document_id"],),
            ).fetchall()
            checks["pdf_pages"] += len(pages)
            expected = list(range(1, (document["page_count"] or 0) + 1))
            actual = [page["page_number"] for page in pages]
            if actual != expected:
                _issue(issues, "PDF_PAGE_COVERAGE", "stored page sequence is incomplete", document_id=document["document_id"])
            artifact = page_text_path(index_directory, document["local_path"], document["sha256"])
            checks["pdf_page_text_artifacts"] += 1
            if not artifact.is_file():
                _issue(
                    issues,
                    "PDF_PAGE_TEXT_MISSING",
                    "deterministic page-marked PDF text artifact is missing",
                    document_id=document["document_id"],
                    path=str(artifact),
                )
            else:
                expected_text = render_pdf_page_text(
                    source_filename=Path(document["local_path"]).name,
                    source_sha256=document["sha256"],
                    pages=pages,
                    parser_version=document["parser_version"],
                    schema_version=document["schema_version"],
                )
                actual_text = artifact.read_bytes()
                if actual_text != expected_text:
                    _issue(
                        issues,
                        "PDF_PAGE_TEXT_MISMATCH",
                        "page-marked PDF text artifact differs from indexed page text",
                        document_id=document["document_id"],
                        path=str(artifact),
                        expected_sha256=hashlib.sha256(expected_text).hexdigest(),
                        actual_sha256=hashlib.sha256(actual_text).hexdigest(),
                    )
            page_map = {page["page_number"]: page for page in pages}
            for span in connection.execute(
                """SELECT s.*, n.node_type
                   FROM source_spans s JOIN nodes n ON n.node_id = s.node_id
                   WHERE s.document_id = ? AND s.page_number IS NOT NULL""",
                (document["document_id"],),
            ):
                checks["pdf_spans"] += 1
                page = page_map.get(span["page_number"])
                if page is None:
                    _issue(issues, "SPAN_PAGE", "span references missing page", span_id=span["span_id"])
                    continue
                bbox = (span["bbox_x0"], span["bbox_y0"], span["bbox_x1"], span["bbox_y1"])
                if all(value is not None for value in bbox):
                    if not (0 <= bbox[0] <= bbox[2] <= page["width"] + 1 and 0 <= bbox[1] <= bbox[3] <= page["height"] + 1):
                        _issue(issues, "BBOX_RANGE", "span bounding box is outside page", span_id=span["span_id"], bbox=bbox)
                # Table spans are a deterministic TSV serialization returned by
                # PyMuPDF's geometric table extractor, not a literal substring
                # of the separately ordered page-text stream.
                if span["node_type"] == "table":
                    checks["pdf_table_spans"] += 1
                elif span["raw_text"] and span["raw_text"] not in page["raw_text"]:
                    _issue(
                        issues,
                        "PDF_TEXT_MISMATCH",
                        "span text is not a literal substring of stored page extraction",
                        severity="WARNING",
                        span_id=span["span_id"],
                    )
        elif document["source_type"] == "html":
            tree = html.parse(str(path))
            for node in connection.execute(
                "SELECT node_id, html_anchor FROM nodes WHERE document_id = ? AND html_anchor IS NOT NULL",
                (document["document_id"],),
            ):
                checks["html_anchors"] += 1
                matches = tree.xpath("//*[@id=$anchor or @name=$anchor]", anchor=node["html_anchor"])
                if not matches:
                    _issue(issues, "HTML_ANCHOR", "stored anchor does not resolve", node_id=node["node_id"], anchor=node["html_anchor"])
            for span in connection.execute(
                "SELECT * FROM source_spans WHERE document_id = ? AND dom_path IS NOT NULL",
                (document["document_id"],),
            ):
                checks["html_spans"] += 1
                matches = tree.xpath(span["dom_path"])
                if not matches:
                    _issue(issues, "DOM_PATH", "stored DOM path does not resolve", span_id=span["span_id"])
                elif span["raw_text"] != "".join(matches[0].itertext()):
                    _issue(issues, "HTML_TEXT_MISMATCH", "stored raw text differs from DOM text", span_id=span["span_id"])

        ratio = document["indexed_text_chars"] / max(document["source_text_chars"], 1)
        checks["text_coverage"] += 1
        if ratio < 0.75:
            _issue(issues, "LOW_TEXT_COVERAGE", "indexed text volume is suspiciously low", severity="WARNING", document_id=document["document_id"], ratio=round(ratio, 6))
        if ratio > 1.35:
            _issue(issues, "DUPLICATE_TEXT_COVERAGE", "indexed text volume suggests duplicated container text", severity="WARNING", document_id=document["document_id"], ratio=round(ratio, 6))
        parser_stats = json.loads(document["parser_stats_json"])
        if document["source_type"] == "html":
            discovered = parser_stats.get("html_sections_discovered", 0)
            indexed = parser_stats.get("html_sections_indexed", 0)
            checks["html_section_coverage"] += 1
            if discovered != indexed:
                _issue(
                    issues,
                    "HTML_SECTION_COVERAGE",
                    "not every discovered section container was indexed",
                    document_id=document["document_id"],
                    discovered=discovered,
                    indexed=indexed,
                )

    error_count = sum(issue["severity"] == "ERROR" for issue in issues)
    warning_count = sum(issue["severity"] == "WARNING" for issue in issues)
    report = {
        "ok": error_count == 0,
        "errors": error_count,
        "warnings": warning_count,
        "checks": dict(sorted(checks.items())),
        "issues": issues,
        "statistics": statistics(connection),
    }
    return report


def record_validation(connection: sqlite3.Connection, report: dict[str, Any]) -> str:
    build = connection.execute("SELECT build_id FROM builds ORDER BY created_at DESC LIMIT 1").fetchone()
    if not build:
        raise RuntimeError("cannot record validation without a build")
    created_at = utc_now()
    validation_id = stable_id("validation", build["build_id"], created_at)
    connection.execute(
        "INSERT INTO validation_runs VALUES (?, ?, ?, ?, ?)",
        (validation_id, build["build_id"], created_at, int(report["ok"]), json.dumps(report, ensure_ascii=False, sort_keys=True)),
    )
    connection.commit()
    return validation_id
