from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, Sequence

from .constants import INDEX_SCHEMA_VERSION, PARSER_VERSION, __version__
from .database import build_database, connect
from .parsers import parse_html, parse_pdf
from .util import canonical_json
from .validation import record_validation, statistics, validate_database


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INDEX_ROOT = REPOSITORY_ROOT / "indexes"


def _database_for(language: str, version: str) -> Path:
    return DEFAULT_INDEX_ROOT / language.casefold() / version / "specification.sqlite"


def _official_url(path: Path) -> str | None:
    resolved = path.resolve()
    for parent in [resolved.parent, *resolved.parents]:
        manifest_path = parent / "source-manifest.json"
        if not manifest_path.is_file():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for artifact in manifest.get("artifacts", []):
            local = (manifest_path.parent / artifact.get("local_path", "")).resolve()
            if local == resolved:
                return artifact.get("url")
    return None


def _resolve_database(args: argparse.Namespace, node_id: str | None = None) -> Path:
    if getattr(args, "database", None):
        path = Path(args.database).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"database does not exist: {path}")
        return path
    language = getattr(args, "language", None)
    version = getattr(args, "version", None)
    if language and version:
        path = _database_for(language, version)
        if not path.is_file():
            raise FileNotFoundError(f"database does not exist: {path}")
        return path
    if node_id:
        matches = []
        for path in DEFAULT_INDEX_ROOT.glob("*/*/specification.sqlite"):
            try:
                with connect(path, read_only=True) as connection:
                    if connection.execute("SELECT 1 FROM nodes WHERE node_id = ?", (node_id,)).fetchone():
                        matches.append(path)
            except sqlite3.Error:
                continue
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise FileNotFoundError(f"node {node_id!r} was not found in local indexes")
        raise RuntimeError(f"node {node_id!r} occurs in multiple databases; pass --database")
    raise ValueError("pass --database or both --language and --version")


def _json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def _node_details(connection: sqlite3.Connection, node_id: str) -> dict[str, Any]:
    row = connection.execute(
        """SELECT n.*, d.source_type, d.local_path, d.sha256, d.official_url
           FROM nodes n JOIN documents d ON d.document_id = n.document_id
           WHERE n.node_id = ?""",
        (node_id,),
    ).fetchone()
    if row is None:
        raise KeyError(f"unknown node: {node_id}")
    result = dict(row)
    result["metadata"] = json.loads(result.pop("metadata_json"))
    result["source_spans"] = [dict(item) for item in connection.execute(
        "SELECT * FROM source_spans WHERE node_id = ? ORDER BY ordinal", (node_id,)
    )]
    result["definitions"] = [dict(item) for item in connection.execute(
        """SELECT t.term, d.definition_text, d.structural_basis
           FROM definitions d JOIN terms t ON t.term_id = d.term_id
           WHERE d.node_id = ? ORDER BY d.ordinal""",
        (node_id,),
    )]
    result["cross_references"] = [dict(item) for item in connection.execute(
        "SELECT * FROM cross_references WHERE source_node_id = ? ORDER BY ordinal", (node_id,)
    )]
    result["correlations"] = [dict(item) for item in connection.execute(
        """SELECT * FROM node_correlations
           WHERE left_node_id = ? OR right_node_id = ? ORDER BY correlation_id""",
        (node_id, node_id),
    )]
    return result


def _summary(row: sqlite3.Row) -> str:
    label = row["title"] or row["section_number"] or row["normalized_text"][:100] or "<empty>"
    number = f"{row['section_number']} " if row["section_number"] else ""
    page = f" p.{row['page_start']}" if row["page_start"] else ""
    anchor = f" #{row['html_anchor']}" if row["html_anchor"] else ""
    return f"{row['node_id']} [{row['node_type']}] {number}{label}{page}{anchor}"


def _print_tree(
    connection: sqlite3.Connection,
    roots: list[str],
    *,
    headings_only: bool,
    max_depth: int | None,
) -> None:
    def visit(node_id: str, shown_depth: int, structural_depth: int) -> None:
        row = connection.execute("SELECT * FROM nodes WHERE node_id = ?", (node_id,)).fetchone()
        if row is None:
            return
        show = not headings_only or row["node_type"] in {"document", "chapter", "section", "subsection"}
        if show:
            print("  " * shown_depth + _summary(row))
            next_shown = shown_depth + 1
        else:
            next_shown = shown_depth
        if max_depth is not None and structural_depth >= max_depth:
            return
        for child in connection.execute(
            "SELECT node_id FROM nodes WHERE parent_id = ? ORDER BY ordinal", (node_id,)
        ):
            visit(child["node_id"], next_shown, structural_depth + 1)

    for root in roots:
        visit(root, 0, 0)


def _command_build(args: argparse.Namespace) -> int:
    parsed = []
    if args.pdf:
        source = Path(args.pdf)
        parsed.append(parse_pdf(source, _official_url(source), detect_tables=not args.no_pdf_tables))
    if args.html:
        source = Path(args.html)
        parsed.append(parse_html(source, _official_url(source)))
    database = Path(args.database).resolve() if args.database else _database_for(args.language, args.version)
    result = build_database(
        database,
        language=args.language,
        version=args.version,
        documents=parsed,
    )
    with connect(database) as connection:
        report = validate_database(connection)
        result["validation_id"] = record_validation(connection, report)
        result["validation"] = {key: report[key] for key in ("ok", "errors", "warnings")}
        result["statistics"] = report["statistics"]

    manifest = {
        "language": args.language,
        "specification_version": args.version,
        "database": str(database),
        "parser_version": PARSER_VERSION,
        "index_schema_version": INDEX_SCHEMA_VERSION,
        "creation_timestamp": result["created_at"],
        "semantic_digest": result["semantic_digest"],
        "sources": [],
    }
    page_text_by_source = {
        artifact["source_sha256"]: artifact for artifact in result["page_text_artifacts"]
    }
    for item in sorted(parsed, key=lambda item: item.source_type):
        source_entry = {
            "source_type": item.source_type,
            "official_url": item.official_url,
            "local_path": item.path,
            "sha256": item.sha256,
            "byte_size": item.byte_size,
        }
        if item.sha256 in page_text_by_source:
            source_entry["page_text"] = page_text_by_source[item.sha256]
        manifest["sources"].append(source_entry)
    manifest_path = database.with_name("index-manifest.json")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result["manifest"] = str(manifest_path)
    _json(result)
    return 0 if report["ok"] else 1


def _command_stats(args: argparse.Namespace) -> int:
    database = _resolve_database(args)
    with connect(database, read_only=True) as connection:
        result = statistics(connection)
        result["database"] = str(database)
        build = connection.execute("SELECT * FROM builds ORDER BY created_at DESC LIMIT 1").fetchone()
        result["build"] = dict(build) if build else None
    _json(result)
    return 0


def _command_tree(args: argparse.Namespace) -> int:
    database = _resolve_database(args, getattr(args, "node", None))
    with connect(database, read_only=True) as connection:
        if args.node:
            roots = [args.node]
        else:
            query = """SELECT n.node_id FROM nodes n JOIN documents d ON d.document_id = n.document_id
                       WHERE n.parent_id IS NULL"""
            params: list[Any] = []
            if args.source_type:
                query += " AND d.source_type = ?"
                params.append(args.source_type)
            query += " ORDER BY d.source_type, n.node_id"
            roots = [row["node_id"] for row in connection.execute(query, params)]
        _print_tree(connection, roots, headings_only=not args.all_nodes, max_depth=args.max_depth)
    return 0


def _command_show(args: argparse.Namespace) -> int:
    database = _resolve_database(args, args.node)
    with connect(database, read_only=True) as connection:
        _json(_node_details(connection, args.node))
    return 0


def _command_children(args: argparse.Namespace) -> int:
    database = _resolve_database(args, args.node)
    with connect(database, read_only=True) as connection:
        rows = connection.execute(
            "SELECT * FROM nodes WHERE parent_id = ? ORDER BY ordinal", (args.node,)
        ).fetchall()
        for row in rows:
            print(_summary(row))
    return 0


def _command_ancestors(args: argparse.Namespace) -> int:
    database = _resolve_database(args, args.node)
    with connect(database, read_only=True) as connection:
        rows = connection.execute(
            """WITH RECURSIVE ancestors(node_id, parent_id, distance) AS (
                   SELECT node_id, parent_id, 0 FROM nodes WHERE node_id = ?
                   UNION ALL
                   SELECT n.node_id, n.parent_id, a.distance + 1
                   FROM nodes n JOIN ancestors a ON n.node_id = a.parent_id
               )
               SELECT n.*, a.distance FROM ancestors a JOIN nodes n ON n.node_id = a.node_id
               ORDER BY a.distance DESC""",
            (args.node,),
        ).fetchall()
        for row in rows:
            print(_summary(row))
    return 0


def _command_subtree(args: argparse.Namespace) -> int:
    database = _resolve_database(args, args.node)
    with connect(database, read_only=True) as connection:
        _print_tree(connection, [args.node], headings_only=not args.all_nodes, max_depth=args.max_depth)
    return 0


def _fts_query(query: str) -> str:
    tokens = [token.replace('"', '""') for token in query.split() if token]
    return " AND ".join(f'"{token}"' for token in tokens)


def _command_search(args: argparse.Namespace) -> int:
    database = _resolve_database(args)
    with connect(database, read_only=True) as connection:
        sql = """SELECT n.node_id, n.node_type, n.title, n.section_number,
                        n.page_start, n.html_anchor, d.source_type,
                        snippet(nodes_fts, 2, '[', ']', ' … ', 24) AS snippet,
                        bm25(nodes_fts, 8.0, 1.0, 0.5) AS rank
                 FROM nodes_fts JOIN nodes n ON n.node_id = nodes_fts.node_id
                 JOIN documents d ON d.document_id = n.document_id
                 WHERE nodes_fts MATCH ?"""
        params: list[Any] = [_fts_query(args.query)]
        if args.source_type:
            sql += " AND d.source_type = ?"
            params.append(args.source_type)
        if args.node_type:
            sql += " AND n.node_type = ?"
            params.append(args.node_type)
        sql += " ORDER BY rank, n.node_id LIMIT ?"
        params.append(args.limit)
        rows = [dict(row) for row in connection.execute(sql, params)]
    _json(rows)
    return 0


def _command_definitions(args: argparse.Namespace) -> int:
    database = _resolve_database(args)
    with connect(database, read_only=True) as connection:
        sql = """SELECT t.term, t.normalized_term, d.definition_text, d.structural_basis,
                        n.node_id, n.page_start, n.html_anchor, src.source_type
                 FROM definitions d JOIN terms t ON t.term_id = d.term_id
                 JOIN nodes n ON n.node_id = d.node_id
                 JOIN documents src ON src.document_id = n.document_id"""
        params: list[Any] = []
        if args.query:
            sql += " WHERE t.normalized_term LIKE ?"
            params.append(f"%{args.query.casefold()}%")
        sql += " ORDER BY t.normalized_term, src.source_type, n.node_id LIMIT ?"
        params.append(args.limit)
        rows = [dict(row) for row in connection.execute(sql, params)]
    _json(rows)
    return 0


def _command_xrefs(args: argparse.Namespace) -> int:
    database = _resolve_database(args)
    with connect(database, read_only=True) as connection:
        sql = """SELECT r.*, n.page_start, n.html_anchor, d.source_type
                 FROM cross_references r JOIN nodes n ON n.node_id = r.source_node_id
                 JOIN documents d ON d.document_id = n.document_id"""
        params: list[Any] = []
        if args.status:
            sql += " WHERE r.resolution_status = ?"
            params.append(args.status)
        sql += " ORDER BY r.resolution_status, r.reference_id LIMIT ?"
        params.append(args.limit)
        rows = [dict(row) for row in connection.execute(sql, params)]
    _json(rows)
    return 0


def _command_validate(args: argparse.Namespace) -> int:
    database = _resolve_database(args)
    with connect(database, read_only=not args.record) as connection:
        report = validate_database(connection)
        if args.record:
            report["validation_id"] = record_validation(connection, report)
    _json(report)
    return 0 if report["ok"] else 1


def _dump_json(connection: sqlite3.Connection) -> dict[str, Any]:
    specifications = [dict(row) for row in connection.execute("SELECT * FROM specifications ORDER BY specification_id")]
    documents = [dict(row) for row in connection.execute("SELECT * FROM documents ORDER BY document_id")]
    for item in specifications + documents:
        item.pop("created_at", None)
    nodes = [dict(row) for row in connection.execute("SELECT * FROM nodes ORDER BY document_id, depth, parent_id, ordinal")]
    for node in nodes:
        node["metadata"] = json.loads(node.pop("metadata_json"))
    return {
        "schema_version": INDEX_SCHEMA_VERSION,
        "parser_version": PARSER_VERSION,
        "specifications": specifications,
        "documents": documents,
        "nodes": nodes,
        "source_spans": [dict(row) for row in connection.execute("SELECT * FROM source_spans ORDER BY node_id, ordinal")],
        "cross_references": [dict(row) for row in connection.execute("SELECT * FROM cross_references ORDER BY reference_id")],
        "terms": [dict(row) for row in connection.execute("SELECT * FROM terms ORDER BY term_id")],
        "definitions": [dict(row) for row in connection.execute("SELECT * FROM definitions ORDER BY definition_id")],
        "correlations": [dict(row) for row in connection.execute("SELECT * FROM node_correlations ORDER BY correlation_id")],
    }


def _command_dump(args: argparse.Namespace) -> int:
    database = _resolve_database(args)
    output = Path(args.output).resolve() if args.output else None
    with connect(database, read_only=True) as connection:
        if args.format == "json":
            rendered = json.dumps(_dump_json(connection), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            if output:
                output.write_text(rendered, encoding="utf-8")
            else:
                print(rendered, end="")
        else:
            if output:
                original = sys.stdout
                with output.open("w", encoding="utf-8") as handle:
                    sys.stdout = handle
                    try:
                        roots = [row[0] for row in connection.execute("SELECT node_id FROM nodes WHERE parent_id IS NULL ORDER BY document_id")]
                        _print_tree(connection, roots, headings_only=not args.all_nodes, max_depth=args.max_depth)
                    finally:
                        sys.stdout = original
            else:
                roots = [row[0] for row in connection.execute("SELECT node_id FROM nodes WHERE parent_id IS NULL ORDER BY document_id")]
                _print_tree(connection, roots, headings_only=not args.all_nodes, max_depth=args.max_depth)
    if output:
        print(output)
    return 0


def _add_database_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--language")
    parser.add_argument("--version")
    parser.add_argument("--database")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="spec2lean", description="Spec2Lean Phase 1 specification index")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    index = commands.add_parser("index", help="build and inspect specification indexes")
    sub = index.add_subparsers(dest="index_command", required=True)

    build = sub.add_parser("build", help="build a deterministic hierarchical SQLite index")
    build.add_argument("--language", required=True)
    build.add_argument("--version", required=True)
    build.add_argument("--pdf")
    build.add_argument("--html")
    build.add_argument("--database")
    build.add_argument("--no-pdf-tables", action="store_true", help="disable PDF table inference")
    build.set_defaults(func=_command_build)

    stats = sub.add_parser("stats", help="show extraction and completeness statistics")
    _add_database_arguments(stats)
    stats.set_defaults(func=_command_stats)

    tree = sub.add_parser("tree", help="show the document heading hierarchy")
    _add_database_arguments(tree)
    tree.add_argument("--node")
    tree.add_argument("--source-type", choices=("pdf", "html"))
    tree.add_argument("--all-nodes", action="store_true")
    tree.add_argument("--max-depth", type=int)
    tree.set_defaults(func=_command_tree)

    show = sub.add_parser("show", help="show a node, exact text, and provenance")
    _add_database_arguments(show)
    show.add_argument("--node", required=True)
    show.set_defaults(func=_command_show)

    children = sub.add_parser("children", help="list direct children of a node")
    _add_database_arguments(children)
    children.add_argument("--node", required=True)
    children.set_defaults(func=_command_children)

    ancestors = sub.add_parser("ancestors", help="list ancestors from root to node")
    _add_database_arguments(ancestors)
    ancestors.add_argument("--node", required=True)
    ancestors.set_defaults(func=_command_ancestors)

    subtree = sub.add_parser("subtree", help="show a complete node subtree")
    _add_database_arguments(subtree)
    subtree.add_argument("--node", required=True)
    subtree.add_argument("--all-nodes", action="store_true")
    subtree.add_argument("--max-depth", type=int)
    subtree.set_defaults(func=_command_subtree)

    search = sub.add_parser("search", help="full-text search raw and normalized source text")
    _add_database_arguments(search)
    search.add_argument("--query", required=True)
    search.add_argument("--source-type", choices=("pdf", "html"))
    search.add_argument("--node-type")
    search.add_argument("--limit", type=int, default=20)
    search.set_defaults(func=_command_search)

    definitions = sub.add_parser("definitions", help="list structurally identified definitions")
    _add_database_arguments(definitions)
    definitions.add_argument("--query")
    definitions.add_argument("--limit", type=int, default=100)
    definitions.set_defaults(func=_command_definitions)

    xrefs = sub.add_parser("xrefs", help="inspect explicit cross references")
    _add_database_arguments(xrefs)
    xrefs.add_argument("--status", choices=("RESOLVED", "AMBIGUOUS", "UNRESOLVED"))
    xrefs.add_argument("--limit", type=int, default=100)
    xrefs.set_defaults(func=_command_xrefs)

    validate = sub.add_parser("validate", help="validate structure, provenance, and completeness")
    _add_database_arguments(validate)
    validate.add_argument("--record", action="store_true")
    validate.set_defaults(func=_command_validate)

    dump = sub.add_parser("dump", help="read-only hierarchy export")
    _add_database_arguments(dump)
    dump.add_argument("--format", choices=("json", "tree"), required=True)
    dump.add_argument("--output")
    dump.add_argument("--all-nodes", action="store_true")
    dump.add_argument("--max-depth", type=int)
    dump.set_defaults(func=_command_dump)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.index_command == "build" and not (args.pdf or args.html):
        parser.error("index build requires --pdf and/or --html")
    try:
        return int(args.func(args))
    except (FileNotFoundError, KeyError, RuntimeError, ValueError, sqlite3.Error) as exc:
        print(f"spec2lean: error: {exc}", file=sys.stderr)
        return 2
