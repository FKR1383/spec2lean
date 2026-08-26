from __future__ import annotations

import json
import os
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .constants import INDEX_SCHEMA_VERSION, PARSER_VERSION
from .model import Node, ParsedDocument
from .page_text import write_pdf_page_text_artifacts
from .util import canonical_json, normalize_text, normalize_title, stable_id, walk_nodes


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = DELETE;

CREATE TABLE specifications (
    specification_id TEXT PRIMARY KEY,
    language TEXT NOT NULL COLLATE NOCASE,
    version TEXT NOT NULL,
    title TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(language, version)
);

CREATE TABLE builds (
    build_id TEXT PRIMARY KEY,
    specification_id TEXT NOT NULL REFERENCES specifications(specification_id),
    parser_version TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    semantic_digest TEXT,
    status TEXT NOT NULL
);

CREATE TABLE documents (
    document_id TEXT PRIMARY KEY,
    specification_id TEXT NOT NULL REFERENCES specifications(specification_id),
    source_type TEXT NOT NULL CHECK(source_type IN ('pdf', 'html')),
    title TEXT NOT NULL,
    official_url TEXT,
    local_path TEXT NOT NULL,
    sha256 TEXT NOT NULL CHECK(length(sha256) = 64),
    byte_size INTEGER NOT NULL,
    parser_version TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    page_count INTEGER,
    source_text_chars INTEGER NOT NULL,
    indexed_text_chars INTEGER NOT NULL DEFAULT 0,
    parser_stats_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    UNIQUE(specification_id, source_type, sha256)
);

CREATE TABLE pages (
    document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL CHECK(page_number >= 1),
    width REAL NOT NULL,
    height REAL NOT NULL,
    raw_text TEXT NOT NULL,
    source_text_chars INTEGER NOT NULL,
    PRIMARY KEY(document_id, page_number)
);

CREATE TABLE nodes (
    node_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    parent_id TEXT REFERENCES nodes(node_id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
    source_key TEXT NOT NULL,
    node_type TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK(ordinal >= 0),
    depth INTEGER NOT NULL CHECK(depth >= 0),
    title TEXT,
    normalized_title TEXT,
    section_number TEXT,
    raw_text TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    page_start INTEGER,
    page_end INTEGER,
    html_anchor TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(document_id, source_key),
    UNIQUE(document_id, parent_id, ordinal),
    CHECK((page_start IS NULL AND page_end IS NULL) OR
          (page_start >= 1 AND page_end >= page_start))
);

CREATE INDEX nodes_parent_order ON nodes(document_id, parent_id, ordinal);
CREATE INDEX nodes_section_number ON nodes(document_id, section_number);
CREATE INDEX nodes_anchor ON nodes(document_id, html_anchor);
CREATE INDEX nodes_type ON nodes(document_id, node_type);

CREATE TABLE source_spans (
    span_id TEXT PRIMARY KEY,
    node_id TEXT NOT NULL REFERENCES nodes(node_id) ON DELETE CASCADE,
    document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    page_number INTEGER,
    bbox_x0 REAL,
    bbox_y0 REAL,
    bbox_x1 REAL,
    bbox_y1 REAL,
    block_index INTEGER,
    line_index INTEGER,
    span_index INTEGER,
    dom_path TEXT,
    source_line_start INTEGER,
    source_line_end INTEGER,
    raw_text TEXT NOT NULL,
    UNIQUE(node_id, ordinal)
);

CREATE INDEX source_spans_page ON source_spans(document_id, page_number);
CREATE INDEX source_spans_dom ON source_spans(document_id, dom_path);

CREATE TABLE cross_references (
    reference_id TEXT PRIMARY KEY,
    source_node_id TEXT NOT NULL REFERENCES nodes(node_id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    kind TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    target_reference_text TEXT NOT NULL,
    href TEXT,
    resolved_target_node_id TEXT REFERENCES nodes(node_id),
    resolution_status TEXT NOT NULL CHECK(resolution_status IN ('RESOLVED', 'AMBIGUOUS', 'UNRESOLVED')),
    candidate_count INTEGER NOT NULL DEFAULT 0,
    UNIQUE(source_node_id, ordinal)
);

CREATE INDEX cross_references_status ON cross_references(resolution_status);

CREATE TABLE terms (
    term_id TEXT PRIMARY KEY,
    specification_id TEXT NOT NULL REFERENCES specifications(specification_id),
    term TEXT NOT NULL,
    normalized_term TEXT NOT NULL,
    UNIQUE(specification_id, normalized_term)
);

CREATE TABLE definitions (
    definition_id TEXT PRIMARY KEY,
    term_id TEXT NOT NULL REFERENCES terms(term_id),
    node_id TEXT NOT NULL REFERENCES nodes(node_id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    definition_text TEXT NOT NULL,
    structural_basis TEXT NOT NULL,
    UNIQUE(node_id, ordinal)
);

CREATE TABLE term_occurrences (
    term_id TEXT NOT NULL REFERENCES terms(term_id),
    node_id TEXT NOT NULL REFERENCES nodes(node_id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    PRIMARY KEY(term_id, node_id, role, ordinal)
);

CREATE TABLE node_correlations (
    correlation_id TEXT PRIMARY KEY,
    left_node_id TEXT NOT NULL REFERENCES nodes(node_id) ON DELETE CASCADE,
    right_node_id TEXT NOT NULL REFERENCES nodes(node_id) ON DELETE CASCADE,
    basis TEXT NOT NULL,
    confidence TEXT NOT NULL,
    UNIQUE(left_node_id, right_node_id)
);

CREATE TABLE validation_runs (
    validation_id TEXT PRIMARY KEY,
    build_id TEXT NOT NULL REFERENCES builds(build_id),
    created_at TEXT NOT NULL,
    ok INTEGER NOT NULL,
    report_json TEXT NOT NULL
);

CREATE VIRTUAL TABLE nodes_fts USING fts5(
    node_id UNINDEXED,
    title,
    raw_text,
    normalized_text,
    tokenize = 'unicode61 remove_diacritics 2'
);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def connect(path: str | Path, *, read_only: bool = False) -> sqlite3.Connection:
    target = Path(path).resolve()
    if read_only:
        connection = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
    else:
        connection = sqlite3.connect(target)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _node_id(document_id: str, node: Node) -> str:
    return stable_id("node", document_id, node.source_key)


def _insert_document(
    connection: sqlite3.Connection,
    specification_id: str,
    parsed: ParsedDocument,
    created_at: str,
) -> tuple[str, Counter[str]]:
    document_id = stable_id("doc", specification_id, parsed.source_type, parsed.sha256)
    connection.execute(
        """INSERT INTO documents(
               document_id, specification_id, source_type, title, official_url,
               local_path, sha256, byte_size, parser_version, schema_version,
               page_count, source_text_chars, parser_stats_json, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            document_id,
            specification_id,
            parsed.source_type,
            parsed.title,
            parsed.official_url,
            parsed.path,
            parsed.sha256,
            parsed.byte_size,
            PARSER_VERSION,
            INDEX_SCHEMA_VERSION,
            parsed.page_count,
            parsed.source_text_chars,
            canonical_json(parsed.parser_stats),
            created_at,
        ),
    )
    for page in parsed.pages:
        connection.execute(
            """INSERT INTO pages(document_id, page_number, width, height, raw_text, source_text_chars)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                document_id,
                page["page_number"],
                page["width"],
                page["height"],
                page["raw_text"],
                page["source_text_chars"],
            ),
        )

    ids = {id(node): _node_id(document_id, node) for node, _, _, _ in walk_nodes(parsed.root)}
    counts: Counter[str] = Counter()
    indexed_chars = 0
    for node, parent, depth, ordinal in walk_nodes(parsed.root):
        node_id = ids[id(node)]
        parent_id = ids[id(parent)] if parent is not None else None
        normalized = normalize_text(node.raw_text)
        if node.node_type != "document":
            indexed_chars += len(normalized)
        counts[node.node_type] += 1
        connection.execute(
            """INSERT INTO nodes(
                   node_id, document_id, parent_id, source_key, node_type, ordinal,
                   depth, title, normalized_title, section_number, raw_text,
                   normalized_text, page_start, page_end, html_anchor, metadata_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                node_id,
                document_id,
                parent_id,
                node.source_key,
                node.node_type,
                ordinal,
                depth,
                node.title,
                normalize_title(node.title),
                node.section_number,
                node.raw_text,
                normalized,
                node.page_start,
                node.page_end,
                node.html_anchor,
                canonical_json(node.metadata),
            ),
        )
        connection.execute(
            "INSERT INTO nodes_fts(node_id, title, raw_text, normalized_text) VALUES (?, ?, ?, ?)",
            (node_id, node.title or "", node.raw_text, normalized),
        )
        for span_ordinal, span in enumerate(node.spans):
            bbox = span.bbox or (None, None, None, None)
            span_id = stable_id("span", node_id, span_ordinal)
            connection.execute(
                """INSERT INTO source_spans(
                       span_id, node_id, document_id, ordinal, page_number,
                       bbox_x0, bbox_y0, bbox_x1, bbox_y1, block_index,
                       line_index, span_index, dom_path, source_line_start,
                       source_line_end, raw_text)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    span_id,
                    node_id,
                    document_id,
                    span_ordinal,
                    span.page_number,
                    *bbox,
                    span.block_index,
                    span.line_index,
                    span.span_index,
                    span.dom_path,
                    span.source_line_start,
                    span.source_line_end,
                    span.raw_text,
                ),
            )
        for ref_ordinal, ref in enumerate(node.references):
            reference_id = stable_id("ref", node_id, ref_ordinal)
            connection.execute(
                """INSERT INTO cross_references(
                       reference_id, source_node_id, ordinal, kind, raw_text,
                       target_reference_text, href, resolution_status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'UNRESOLVED')""",
                (
                    reference_id,
                    node_id,
                    ref_ordinal,
                    ref.kind,
                    ref.raw_text,
                    ref.target_text,
                    ref.href,
                ),
            )
        for definition_ordinal, definition in enumerate(node.definitions):
            normalized_term = normalize_text(definition.term).casefold()
            term_id = stable_id("term", specification_id, normalized_term)
            connection.execute(
                """INSERT INTO terms(term_id, specification_id, term, normalized_term)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(specification_id, normalized_term) DO NOTHING""",
                (term_id, specification_id, definition.term, normalized_term),
            )
            definition_id = stable_id("def", node_id, definition_ordinal)
            connection.execute(
                """INSERT INTO definitions(
                       definition_id, term_id, node_id, ordinal, definition_text, structural_basis)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    definition_id,
                    term_id,
                    node_id,
                    definition_ordinal,
                    definition.definition_text,
                    definition.basis,
                ),
            )
            connection.execute(
                "INSERT INTO term_occurrences(term_id, node_id, role, ordinal) VALUES (?, ?, 'DEFINITION', ?)",
                (term_id, node_id, definition_ordinal),
            )

    connection.execute(
        "UPDATE documents SET indexed_text_chars = ? WHERE document_id = ?",
        (indexed_chars, document_id),
    )
    return document_id, counts


def _resolve_references(connection: sqlite3.Connection) -> None:
    references = connection.execute(
        """SELECT r.*, n.document_id
           FROM cross_references r JOIN nodes n ON n.node_id = r.source_node_id
           ORDER BY r.reference_id"""
    ).fetchall()
    for ref in references:
        target = ref["target_reference_text"]
        kind = ref["kind"].upper()
        if kind == "ANCHOR":
            candidates = connection.execute(
                "SELECT node_id FROM nodes WHERE document_id = ? AND html_anchor = ? ORDER BY node_id",
                (ref["document_id"], target),
            ).fetchall()
        elif kind in {"SECTION", "CHAPTER", "APPENDIX"}:
            candidates = connection.execute(
                """SELECT node_id FROM nodes
                   WHERE document_id = ? AND section_number = ?
                   ORDER BY node_id""",
                (ref["document_id"], target),
            ).fetchall()
        elif kind in {"TABLE", "FIGURE"}:
            prefix = f"{kind.title()} {target}%"
            candidates = connection.execute(
                """SELECT node_id FROM nodes
                   WHERE document_id = ? AND normalized_text LIKE lower(?)
                     AND node_type IN ('caption', 'table', 'generic')
                   ORDER BY node_id""",
                (ref["document_id"], prefix),
            ).fetchall()
        else:
            candidates = []
        count = len(candidates)
        status = "RESOLVED" if count == 1 else "AMBIGUOUS" if count > 1 else "UNRESOLVED"
        resolved = candidates[0]["node_id"] if count == 1 else None
        connection.execute(
            """UPDATE cross_references
               SET resolved_target_node_id = ?, resolution_status = ?, candidate_count = ?
               WHERE reference_id = ?""",
            (resolved, status, count, ref["reference_id"]),
        )


def _correlate_documents(connection: sqlite3.Connection, specification_id: str) -> None:
    rows = connection.execute(
        """SELECT n.node_id, n.section_number, n.normalized_title, d.source_type
           FROM nodes n JOIN documents d ON d.document_id = n.document_id
           WHERE d.specification_id = ? AND n.section_number IS NOT NULL
             AND n.node_type IN ('chapter', 'section', 'subsection')
           ORDER BY n.node_id""",
        (specification_id,),
    ).fetchall()
    pdf = [row for row in rows if row["source_type"] == "pdf"]
    html_rows = [row for row in rows if row["source_type"] == "html"]
    for left in pdf:
        matches = [
            right
            for right in html_rows
            if right["section_number"] == left["section_number"]
            and right["normalized_title"] == left["normalized_title"]
        ]
        if len(matches) != 1:
            continue
        right = matches[0]
        correlation_id = stable_id("corr", left["node_id"], right["node_id"])
        connection.execute(
            """INSERT INTO node_correlations(
                   correlation_id, left_node_id, right_node_id, basis, confidence)
               VALUES (?, ?, ?, 'exact-section-number-and-normalized-title', 'HIGH')""",
            (correlation_id, left["node_id"], right["node_id"]),
        )


def semantic_digest(connection: sqlite3.Connection) -> str:
    import hashlib

    digest = hashlib.sha256()
    tables = [
        "specifications",
        "documents",
        "pages",
        "nodes",
        "source_spans",
        "cross_references",
        "terms",
        "definitions",
        "term_occurrences",
        "node_correlations",
    ]
    excluded = {"created_at"}
    stable_order = {
        "specifications": "specification_id",
        "documents": "document_id",
        "pages": "document_id, page_number",
        "nodes": "node_id",
        "source_spans": "span_id",
        "cross_references": "reference_id",
        "terms": "term_id",
        "definitions": "definition_id",
        "term_occurrences": "term_id, node_id, role, ordinal",
        "node_correlations": "correlation_id",
    }
    for table in tables:
        columns = [
            row["name"]
            for row in connection.execute(f"PRAGMA table_info({table})")
            if row["name"] not in excluded
        ]
        selection = ", ".join(columns)
        for row in connection.execute(
            f"SELECT {selection} FROM {table} ORDER BY {stable_order[table]}"
        ):
            digest.update(table.encode())
            digest.update(canonical_json(list(row)).encode("utf-8"))
    return digest.hexdigest()


def build_database(
    database_path: str | Path,
    *,
    language: str,
    version: str,
    documents: Iterable[ParsedDocument],
) -> dict[str, Any]:
    target = Path(database_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".building")
    if temporary.exists():
        temporary.unlink()
    created_at = utc_now()
    specification_id = stable_id("spec", language.casefold(), version)
    build_id = stable_id("build", specification_id, PARSER_VERSION, INDEX_SCHEMA_VERSION)
    parsed_documents = list(documents)
    if not parsed_documents:
        raise ValueError("at least one PDF or HTML source is required")
    title = parsed_documents[0].title

    connection = connect(temporary)
    try:
        connection.executescript(SCHEMA_SQL)
        connection.execute(
            "INSERT INTO specifications VALUES (?, ?, ?, ?, ?)",
            (specification_id, language, version, title, created_at),
        )
        connection.execute(
            "INSERT INTO builds VALUES (?, ?, ?, ?, ?, NULL, 'BUILDING')",
            (build_id, specification_id, PARSER_VERSION, INDEX_SCHEMA_VERSION, created_at),
        )
        document_ids = []
        aggregate_counts: Counter[str] = Counter()
        for parsed in sorted(parsed_documents, key=lambda item: (item.source_type, item.sha256)):
            document_id, counts = _insert_document(connection, specification_id, parsed, created_at)
            document_ids.append(document_id)
            aggregate_counts.update(counts)
        _resolve_references(connection)
        _correlate_documents(connection, specification_id)
        digest = semantic_digest(connection)
        connection.execute(
            "UPDATE builds SET semantic_digest = ?, status = 'COMPLETE' WHERE build_id = ?",
            (digest, build_id),
        )
        connection.commit()
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"SQLite integrity check failed: {integrity}")
    except Exception:
        connection.close()
        if temporary.exists():
            temporary.unlink()
        raise
    finally:
        try:
            connection.close()
        except Exception:
            pass
    os.replace(temporary, target)
    page_text_artifacts = write_pdf_page_text_artifacts(target.parent, parsed_documents)
    return {
        "database": str(target),
        "specification_id": specification_id,
        "build_id": build_id,
        "semantic_digest": digest,
        "documents": document_ids,
        "node_counts": dict(sorted(aggregate_counts.items())),
        "created_at": created_at,
        "page_text_artifacts": page_text_artifacts,
    }
