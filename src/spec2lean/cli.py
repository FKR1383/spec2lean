from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, Sequence

from .constants import INDEX_SCHEMA_VERSION, PARSER_VERSION, __version__
from .checking.runner import run_checks
from .checking.store import load_check
from .database import build_database, connect
from .evidence.runner import build_evidence
from .evidence.store import evidence_run_root, find_evidence, load_unit_bundle, unit_artifacts
from .parsers import parse_html, parse_pdf
from .planning.models import PlanningRequest
from .planning.render import render_dot
from .planning.runner import build_plan
from .semantics.runner import build_semantics
from .semantics.revision import revise_semantics
from .semantics.store import artifacts as semantic_artifacts
from .semantics.store import find_claim, load_semantics, semantics_run_root
from .translation.runner import build_translation
from .translation.revision import revise_translation
from .translation.models import semantics_artifact_hash
from .translation.store import find_declaration, load_translation
from .troubleshooting.runner import run_troubleshooter
from .troubleshooting.models import (
    RETURN_TO_SEMANTIC_EXTRACTOR,
    RETURN_TO_TRANSLATOR,
    action_for,
    artifact_hash,
)
from .troubleshooting.resolver import resolve_check_failure
from .troubleshooting.store import load_troubleshooting
from .util import canonical_json
from .validation import record_validation, statistics, validate_database


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INDEX_ROOT = REPOSITORY_ROOT / "indexes"
DEFAULT_PLANS_ROOT = REPOSITORY_ROOT / "plans"
DEFAULT_EVIDENCE_ROOT = REPOSITORY_ROOT / "evidence"
DEFAULT_SEMANTICS_ROOT = REPOSITORY_ROOT / "semantics"
DEFAULT_TRANSLATIONS_ROOT = REPOSITORY_ROOT / "translations"
DEFAULT_CHECKS_ROOT = REPOSITORY_ROOT / "checks"
DEFAULT_TROUBLESHOOTING_ROOT = REPOSITORY_ROOT / "troubleshooting"


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


def _planning_request(args: argparse.Namespace) -> PlanningRequest:
    if args.instructions is not None:
        instructions = [item.strip() for item in args.instructions.split(",")]
        if any(not item for item in instructions):
            raise ValueError("--instructions must be a comma-separated list without empty items")
        return PlanningRequest.exact(args.language, args.version, instructions)
    if args.family is not None:
        return PlanningRequest.family_request(args.language, args.version, args.family)
    if args.source_node is not None:
        return PlanningRequest.subtree(args.language, args.version, args.source_node)
    return PlanningRequest.full(args.language, args.version)


def _command_plan_build(args: argparse.Namespace) -> int:
    database = _resolve_database(args)
    run_directory = build_plan(
        database,
        Path(args.plans_root),
        _planning_request(args),
        timeout_seconds=args.timeout,
    )
    print(run_directory)
    return 0


def _find_plan_run(run_id: str, plans_root: str | Path) -> Path:
    root = Path(plans_root).resolve()
    matches = [path.parent for path in root.glob(f"*/*/{run_id}/plan.json")]
    if not matches:
        raise FileNotFoundError(f"plan run does not exist: {run_id}")
    if len(matches) > 1:
        raise RuntimeError(f"plan run ID is ambiguous under {root}: {run_id}")
    return matches[0]


def _load_plan(args: argparse.Namespace) -> tuple[Path, dict[str, Any]]:
    run = _find_plan_run(args.run, args.plans_root)
    return run, json.loads((run / "plan.json").read_text(encoding="utf-8"))


def _command_plan_show(args: argparse.Namespace) -> int:
    _, plan = _load_plan(args)
    _json(plan)
    return 0


def _command_plan_field(args: argparse.Namespace) -> int:
    _, plan = _load_plan(args)
    _json(plan[args.plan_field])
    return 0


def _command_plan_graph(args: argparse.Namespace) -> int:
    _, plan = _load_plan(args)
    rendered = render_dot(plan)
    if args.output:
        output = Path(args.output).resolve()
        output.write_text(rendered, encoding="utf-8")
        print(output)
    else:
        print(rendered, end="")
    return 0


def _load_evidence_plan(args: argparse.Namespace) -> tuple[Path, dict[str, Any]]:
    run = _find_plan_run(args.plan_run, args.plans_root)
    return run, json.loads((run / "plan.json").read_text(encoding="utf-8"))


def _command_evidence_build(args: argparse.Namespace) -> int:
    _, plan = _load_evidence_plan(args)
    database = Path(args.database).resolve() if args.database else _database_for(plan["language"], plan["version"])
    if not database.is_file():
        raise FileNotFoundError(f"database does not exist: {database}")
    root = build_evidence(
        database,
        plan,
        Path(args.evidence_root),
        unit_ids=args.unit,
        jobs=args.jobs,
        timeout_seconds=args.timeout,
    )
    print(root)
    return 0


def _command_evidence_units(args: argparse.Namespace) -> int:
    _, plan = _load_evidence_plan(args)
    artifacts = {
        item["metadata"].get("unitId") or (item["bundle"] or {}).get("unit", {}).get("unitId"): item
        for item in unit_artifacts(Path(args.evidence_root), plan)
    }
    result = []
    for unit in plan["requestedUnits"]:
        artifact = artifacts.get(unit["unitId"])
        result.append({
            "unitId": unit["unitId"],
            "name": unit["name"],
            "status": artifact["metadata"].get("outcome", "VALID") if artifact else "NOT_RUN",
            "evidenceCount": len((artifact["bundle"] or {}).get("evidence", [])) if artifact else 0,
            "directory": str(artifact["directory"]) if artifact else None,
        })
    _json(result)
    return 0


def _command_evidence_show(args: argparse.Namespace) -> int:
    _, plan = _load_evidence_plan(args)
    _, bundle = load_unit_bundle(Path(args.evidence_root), plan, args.unit)
    if getattr(args, "tier", None):
        _json([item for item in bundle["evidence"] if item["tier"] == args.tier])
    else:
        _json(bundle)
    return 0


def _command_evidence_provenance(args: argparse.Namespace) -> int:
    path, item = find_evidence(Path(args.evidence_root), args.evidence)
    _json({
        "evidenceId": item["evidenceId"],
        "bundle": str(path),
        "unitId": item["unitId"],
        "sourceNodeIds": item["sourceNodeIds"],
        "sourceSpanIds": item["sourceSpanIds"],
        "sourceType": item["sourceType"],
        "documentId": item["documentId"],
        "documentSha256": item["documentSha256"],
        "officialUrl": item["officialUrl"],
        "sectionNumber": item["sectionNumber"],
        "sectionTitle": item["sectionTitle"],
        "htmlAnchor": item["htmlAnchor"],
        "pdfPage": item["pdfPage"],
        "bbox": item["bbox"],
        "provenance": item["provenance"],
    })
    return 0


def _command_evidence_stats(args: argparse.Namespace) -> int:
    _, plan = _load_evidence_plan(args)
    artifacts = unit_artifacts(Path(args.evidence_root), plan)
    bundles = [item["bundle"] for item in artifacts if item["bundle"]]
    evidence = [record for bundle in bundles for record in bundle["evidence"]]
    result = {
        "planRunId": plan["planRunId"],
        "plannedUnits": len(plan["requestedUnits"]),
        "validBundles": len(bundles),
        "failedUnits": sum(item["metadata"].get("outcome") == "FAILED" for item in artifacts),
        "evidenceItems": len(evidence),
        "uniqueEvidenceIds": len({item["evidenceId"] for item in evidence}),
        "byTier": {tier: sum(item["tier"] == tier for item in evidence) for tier in ("CORE", "SUPPORTING")},
        "byRole": {
            role: sum(item["role"] == role for item in evidence)
            for role in sorted({item["role"] for item in evidence})
        },
        "directory": str(evidence_run_root(Path(args.evidence_root), plan)),
    }
    _json(result)
    return 0


def _load_semantics_plan(args: argparse.Namespace) -> tuple[Path, dict[str, Any]]:
    run = _find_plan_run(args.plan_run, args.plans_root)
    return run, json.loads((run / "plan.json").read_text(encoding="utf-8"))


def _command_semantics_build(args: argparse.Namespace) -> int:
    _, plan = _load_semantics_plan(args)
    root = build_semantics(
        plan, Path(args.evidence_root), Path(args.semantics_root),
        unit_ids=args.unit, timeout_seconds=args.timeout,
    )
    print(root)
    return 0


def _command_semantics_revise(args: argparse.Namespace) -> int:
    _, plan = _load_semantics_plan(args)
    _, check = load_check(Path(args.checks_root), plan, args.unit)
    if action_for(check) != RETURN_TO_SEMANTIC_EXTRACTOR:
        raise ValueError("semantic revision requires TRACEABILITY = FAIL as the earliest Phase-6 failure")
    output, revision = revise_semantics(
        plan, evidence_root=Path(args.evidence_root), semantics_root=Path(args.semantics_root),
        unit_id=args.unit, diagnostics=check["traceability"]["brokenMappings"],
        timeout_seconds=args.timeout, source_check_hash=artifact_hash(check),
    )
    _json({"directory": str(output), **revision})
    return 0


def _command_semantics_show(args: argparse.Namespace) -> int:
    _, plan = _load_semantics_plan(args)
    _, artifact = load_semantics(Path(args.semantics_root), plan, args.unit)
    _json(artifact)
    return 0


def _command_semantics_field(args: argparse.Namespace) -> int:
    _, plan = _load_semantics_plan(args)
    _, artifact = load_semantics(Path(args.semantics_root), plan, args.unit)
    semantics = artifact.get("semantics") or {}
    _json(semantics.get(args.semantic_field))
    return 0


def _command_semantics_evidence(args: argparse.Namespace) -> int:
    semantic_path, artifact, claim = find_claim(Path(args.semantics_root), args.claim)
    records = []
    evidence_root = Path(args.evidence_root).resolve()
    for evidence_id in claim.get("evidenceIds", []):
        path, item = find_evidence(evidence_root, evidence_id)
        records.append({"bundle": str(path), **item})
    _json({
        "claim": claim, "semanticArtifact": str(semantic_path),
        "unitId": artifact["unit"]["unitId"], "evidence": records,
    })
    return 0


def _command_semantics_stats(args: argparse.Namespace) -> int:
    _, plan = _load_semantics_plan(args)
    items = semantic_artifacts(Path(args.semantics_root), plan)
    valid = [item["artifact"] for item in items if item["artifact"] and item["artifact"].get("outcome") == "SUCCESS"]
    claims = [claim for artifact in valid for claim in artifact["semantics"]["claims"]]
    _json({
        "planRunId": plan["planRunId"], "plannedUnits": len(plan["requestedUnits"]),
        "successfulArtifacts": len(valid),
        "insufficientEvidence": sum((item["artifact"] or {}).get("outcome") == "INSUFFICIENT_EVIDENCE" for item in items),
        "failedUnits": sum(item["metadata"].get("outcome") == "FAILED" for item in items),
        "claims": len(claims),
        "byClassification": {kind: sum(claim["kind"] == kind for claim in claims) for kind in ("SOURCE_FACT", "DERIVED_INTERPRETATION", "DESIGN_DEPENDENCY", "ASSUMPTION")},
        "directory": str(semantics_run_root(Path(args.semantics_root), plan)),
    })
    return 0


def _command_translate_build(args: argparse.Namespace) -> int:
    _, plan = _load_semantics_plan(args)
    output = build_translation(
        plan,
        Path(args.semantics_root),
        Path(args.translations_root),
        unit_id=args.unit,
        timeout_seconds=args.timeout,
    )
    print(output)
    return 0


def _command_translate_revise(args: argparse.Namespace) -> int:
    _, plan = _load_semantics_plan(args)
    _, check = load_check(Path(args.checks_root), plan, args.unit)
    if action_for(check) != RETURN_TO_TRANSLATOR:
        raise ValueError("translation revision requires COVERAGE = FAIL as the earliest Phase-6 failure")
    output, revision = revise_translation(
        plan, semantics_root=Path(args.semantics_root),
        translations_root=Path(args.translations_root), unit_id=args.unit,
        diagnostics=check["coverage"]["uncovered"], reason="COVERAGE_FAILURE",
        timeout_seconds=args.timeout, source_check_hash=artifact_hash(check),
    )
    _json({"directory": str(output), **revision})
    return 0


def _command_translate_show(args: argparse.Namespace) -> int:
    _, plan = _load_semantics_plan(args)
    directory, source, manifest, run = load_translation(Path(args.translations_root), plan, args.unit)
    _json({"directory": str(directory), "leanSource": source, "manifest": manifest, "translatorRun": run})
    return 0


def _command_translate_manifest(args: argparse.Namespace) -> int:
    _, plan = _load_semantics_plan(args)
    _, _, manifest, _ = load_translation(Path(args.translations_root), plan, args.unit)
    _json(manifest)
    return 0


def _command_translate_trace(args: argparse.Namespace) -> int:
    manifest_path, manifest, mapping = find_declaration(Path(args.translations_root), args.declaration)
    semantic_path, semantic_artifact = load_semantics(
        Path(args.semantics_root),
        {
            "language": manifest["language"],
            "version": manifest["version"],
            "planRunId": manifest["planRunId"],
            "requestedUnits": [manifest["unit"]],
        },
        manifest["unit"]["unitId"],
    )
    claims_by_id = {
        claim["claimId"]: claim for claim in semantic_artifact["semantics"]["claims"]
    }
    if semantics_artifact_hash(semantic_artifact) != manifest["semanticsArtifactHash"]:
        raise RuntimeError("translation manifest references a stale Phase-4 semantic artifact hash")
    mappings_by_name = {
        item["declaration"]: item for item in manifest["declarations"]
    }

    def claim_ids_for(item: dict[str, Any], seen: set[str]) -> list[str]:
        name = item["declaration"]
        if name in seen:
            raise RuntimeError(f"translation manifest has a declaration support cycle: {name}")
        result = list(item.get("semanticClaimIds", []))
        for supported in item.get("supportsDeclarations", []):
            target = mappings_by_name.get(supported)
            if target is None:
                raise RuntimeError(f"translation manifest references missing supported declaration: {supported}")
            result.extend(claim_ids_for(target, {*seen, name}))
        return list(dict.fromkeys(result))

    claims = []
    for claim_id in claim_ids_for(mapping, set()):
        claim = claims_by_id.get(claim_id)
        if claim is None:
            raise RuntimeError(f"translation manifest references missing semantic claim: {claim_id}")
        evidence = []
        for evidence_id in claim.get("evidenceIds", []):
            path, record = find_evidence(Path(args.evidence_root), evidence_id)
            evidence.append({"bundle": str(path), **record})
        claims.append({"claim": claim, "evidence": evidence})
    _json({
        "declaration": mapping,
        "translationManifest": str(manifest_path),
        "semanticsArtifact": str(semantic_path / "semantics.json"),
        "semanticsArtifactHash": manifest["semanticsArtifactHash"],
        "claims": claims,
    })
    return 0


def _command_check_run(args: argparse.Namespace) -> int:
    _, plan = _load_semantics_plan(args)
    database = Path(args.database).resolve() if args.database else _database_for(
        plan["language"], plan["version"]
    )
    output, result = run_checks(
        plan,
        evidence_root=Path(args.evidence_root),
        semantics_root=Path(args.semantics_root),
        translations_root=Path(args.translations_root),
        checks_root=Path(args.checks_root),
        database=database,
        unit_id=args.unit,
    )
    _json({"directory": str(output), **result})
    return 0 if result["status"] == "PASS" else 1


def _load_check_result(args: argparse.Namespace) -> tuple[Path, dict[str, Any]]:
    _, plan = _load_semantics_plan(args)
    return load_check(Path(args.checks_root), plan, args.unit)


def _command_check_show(args: argparse.Namespace) -> int:
    directory, result = _load_check_result(args)
    _json({"directory": str(directory), **result})
    return 0


def _command_check_field(args: argparse.Namespace) -> int:
    _, result = _load_check_result(args)
    _json(result[args.check_field])
    return 0


def _command_troubleshoot_run(args: argparse.Namespace) -> int:
    _, plan = _load_semantics_plan(args)
    output, artifact = run_troubleshooter(
        plan,
        semantics_root=Path(args.semantics_root),
        translations_root=Path(args.translations_root),
        checks_root=Path(args.checks_root),
        troubleshooting_root=Path(args.troubleshooting_root),
        unit_id=args.unit,
        timeout_seconds=args.timeout,
        repository_root=REPOSITORY_ROOT,
    )
    _json({"directory": str(output), **artifact})
    return 0


def _load_troubleshooting_result(args: argparse.Namespace) -> tuple[Path, dict[str, Any]]:
    _, plan = _load_semantics_plan(args)
    return load_troubleshooting(Path(args.troubleshooting_root), plan, args.unit)


def _command_troubleshoot_show(args: argparse.Namespace) -> int:
    directory, artifact = _load_troubleshooting_result(args)
    _json({"directory": str(directory), **artifact})
    return 0


def _command_troubleshoot_changes(args: argparse.Namespace) -> int:
    directory, artifact = _load_troubleshooting_result(args)
    _json({
        "directory": str(directory),
        "runId": artifact["runId"],
        "action": artifact["action"],
        "changedFiles": artifact["changedFiles"],
        "changes": artifact["changes"],
        "hashes": artifact["hashes"],
        "recheck": artifact["recheck"],
    })
    return 0


def _command_troubleshoot_resolve(args: argparse.Namespace) -> int:
    _, plan = _load_semantics_plan(args)
    database = Path(args.database).resolve() if args.database else _database_for(
        plan["language"], plan["version"]
    )
    output, resolution = resolve_check_failure(
        plan, evidence_root=Path(args.evidence_root), semantics_root=Path(args.semantics_root),
        translations_root=Path(args.translations_root), checks_root=Path(args.checks_root),
        troubleshooting_root=Path(args.troubleshooting_root), database=database,
        unit_id=args.unit, timeout_seconds=args.timeout,
        max_dispatches=args.max_dispatches, repository_root=REPOSITORY_ROOT,
    )
    _json({"directory": str(output), **resolution})
    return 0 if resolution["outcome"] == "COMPLETE" else 1


def _command_troubleshoot_resolution(args: argparse.Namespace) -> int:
    directory, _ = _load_troubleshooting_result(args)
    path = directory / "resolution.json"
    if not path.is_file():
        raise FileNotFoundError(f"Phase-7 resolution artifact does not exist for unit: {args.unit}")
    _json({"directory": str(directory), **json.loads(path.read_text(encoding="utf-8"))})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="spec2lean", description="Spec2Lean specification index and request-scoped planner")
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

    plan = commands.add_parser("plan", help="build and inspect request-scoped Phase 2 plans")
    plan_sub = plan.add_subparsers(dest="plan_command", required=True)
    plan_build = plan_sub.add_parser("build", help="resolve scope and run one OpenCode Planner session")
    plan_build.add_argument("--language", required=True)
    plan_build.add_argument("--version", required=True)
    plan_build.add_argument("--database")
    selector = plan_build.add_mutually_exclusive_group(required=True)
    selector.add_argument("--instructions", help="comma-separated exact instruction names")
    selector.add_argument("--family", help="conceptual instruction family")
    selector.add_argument("--source-node", help="exact Phase-1 node:<id> subtree")
    selector.add_argument("--all", action="store_true", help="explicitly plan the full specification")
    plan_build.add_argument("--plans-root", default=str(DEFAULT_PLANS_ROOT), help=argparse.SUPPRESS)
    plan_build.add_argument("--timeout", type=int, default=1800, help="single Planner session timeout in seconds")
    plan_build.set_defaults(func=_command_plan_build)

    for name, help_text, field in (
        ("show", "show the complete plan", None),
        ("units", "show requested plan units", "requestedUnits"),
        ("deps", "show dependency edges", "dependencies"),
        ("layers", "show derived processing layers", "processingLayers"),
        ("prerequisites", "show external prerequisites", "externalPrerequisites"),
    ):
        command = plan_sub.add_parser(name, help=help_text)
        command.add_argument("--run", required=True)
        command.add_argument("--plans-root", default=str(DEFAULT_PLANS_ROOT), help=argparse.SUPPRESS)
        if field is None:
            command.set_defaults(func=_command_plan_show)
        else:
            command.set_defaults(func=_command_plan_field, plan_field=field)

    graph = plan_sub.add_parser("graph", help="export a plan dependency graph")
    graph.add_argument("--run", required=True)
    graph.add_argument("--format", choices=("dot",), required=True)
    graph.add_argument("--output")
    graph.add_argument("--plans-root", default=str(DEFAULT_PLANS_ROOT), help=argparse.SUPPRESS)
    graph.set_defaults(func=_command_plan_graph)

    evidence = commands.add_parser("evidence", help="build and inspect request-scoped Phase 3 evidence")
    evidence_sub = evidence.add_subparsers(dest="evidence_command", required=True)
    evidence_build = evidence_sub.add_parser("build", help="run one bounded Evidence Retriever session per selected unit")
    evidence_build.add_argument("--plan-run", required=True)
    evidence_build.add_argument("--unit", action="append", help="exact Phase-2 unit ID; repeat to select a small subset")
    evidence_build.add_argument("--database", help=argparse.SUPPRESS)
    evidence_build.add_argument("--plans-root", default=str(DEFAULT_PLANS_ROOT), help=argparse.SUPPRESS)
    evidence_build.add_argument("--evidence-root", default=str(DEFAULT_EVIDENCE_ROOT), help=argparse.SUPPRESS)
    evidence_build.add_argument("--jobs", type=int, default=1, help="maximum concurrent independent unit sessions")
    evidence_build.add_argument("--timeout", type=int, default=1800, help="timeout per single-unit session in seconds")
    evidence_build.set_defaults(func=_command_evidence_build)

    evidence_units = evidence_sub.add_parser("units", help="show Phase-3 status for every planned unit")
    evidence_units.add_argument("--plan-run", required=True)
    evidence_units.add_argument("--plans-root", default=str(DEFAULT_PLANS_ROOT), help=argparse.SUPPRESS)
    evidence_units.add_argument("--evidence-root", default=str(DEFAULT_EVIDENCE_ROOT), help=argparse.SUPPRESS)
    evidence_units.set_defaults(func=_command_evidence_units)

    for name, help_text, tier in (
        ("show", "show a complete unit evidence bundle", None),
        ("core", "show only CORE evidence for a unit", "CORE"),
        ("supporting", "show only SUPPORTING evidence for a unit", "SUPPORTING"),
    ):
        command = evidence_sub.add_parser(name, help=help_text)
        command.add_argument("--plan-run", required=True)
        command.add_argument("--unit", required=True)
        command.add_argument("--plans-root", default=str(DEFAULT_PLANS_ROOT), help=argparse.SUPPRESS)
        command.add_argument("--evidence-root", default=str(DEFAULT_EVIDENCE_ROOT), help=argparse.SUPPRESS)
        command.set_defaults(func=_command_evidence_show, tier=tier)

    provenance = evidence_sub.add_parser("provenance", help="resolve a stable evidence ID to Phase-1 provenance")
    provenance.add_argument("--evidence", required=True)
    provenance.add_argument("--evidence-root", default=str(DEFAULT_EVIDENCE_ROOT), help=argparse.SUPPRESS)
    provenance.set_defaults(func=_command_evidence_provenance)

    evidence_stats = evidence_sub.add_parser("stats", help="show per-plan evidence statistics")
    evidence_stats.add_argument("--plan-run", required=True)
    evidence_stats.add_argument("--plans-root", default=str(DEFAULT_PLANS_ROOT), help=argparse.SUPPRESS)
    evidence_stats.add_argument("--evidence-root", default=str(DEFAULT_EVIDENCE_ROOT), help=argparse.SUPPRESS)
    evidence_stats.set_defaults(func=_command_evidence_stats)

    semantics = commands.add_parser("semantics", help="build and inspect evidence-bounded Phase 4 semantics")
    semantics_sub = semantics.add_subparsers(dest="semantics_command", required=True)
    semantics_build = semantics_sub.add_parser("build", help="run one Semantic Extractor session per selected unit")
    semantics_build.add_argument("--plan-run", required=True)
    semantics_build.add_argument("--unit", action="append", help="exact evidence-backed Phase-2 unit ID; repeat to select units")
    semantics_build.add_argument("--plans-root", default=str(DEFAULT_PLANS_ROOT), help=argparse.SUPPRESS)
    semantics_build.add_argument("--evidence-root", default=str(DEFAULT_EVIDENCE_ROOT), help=argparse.SUPPRESS)
    semantics_build.add_argument("--semantics-root", default=str(DEFAULT_SEMANTICS_ROOT), help=argparse.SUPPRESS)
    semantics_build.add_argument("--timeout", type=int, default=1800, help="timeout per single-unit session in seconds")
    semantics_build.set_defaults(func=_command_semantics_build)

    semantics_revise = semantics_sub.add_parser("revise", help="revise semantics from stored traceability diagnostics")
    semantics_revise.add_argument("--plan-run", required=True)
    semantics_revise.add_argument("--unit", required=True)
    semantics_revise.add_argument("--plans-root", default=str(DEFAULT_PLANS_ROOT), help=argparse.SUPPRESS)
    semantics_revise.add_argument("--evidence-root", default=str(DEFAULT_EVIDENCE_ROOT), help=argparse.SUPPRESS)
    semantics_revise.add_argument("--semantics-root", default=str(DEFAULT_SEMANTICS_ROOT), help=argparse.SUPPRESS)
    semantics_revise.add_argument("--checks-root", default=str(DEFAULT_CHECKS_ROOT), help=argparse.SUPPRESS)
    semantics_revise.add_argument("--timeout", type=int, default=1800, help="timeout for the single revision session in seconds")
    semantics_revise.set_defaults(func=_command_semantics_revise)

    semantic_show = semantics_sub.add_parser("show", help="show a complete semantic artifact")
    semantic_show.add_argument("--plan-run", required=True)
    semantic_show.add_argument("--unit", required=True)
    semantic_show.add_argument("--plans-root", default=str(DEFAULT_PLANS_ROOT), help=argparse.SUPPRESS)
    semantic_show.add_argument("--semantics-root", default=str(DEFAULT_SEMANTICS_ROOT), help=argparse.SUPPRESS)
    semantic_show.set_defaults(func=_command_semantics_show)

    for name, help_text, field in (
        ("claims", "show structured claims for a unit", "claims"),
        ("operation", "show the core operation for a unit", "operation"),
    ):
        command = semantics_sub.add_parser(name, help=help_text)
        command.add_argument("--plan-run", required=True)
        command.add_argument("--unit", required=True)
        command.add_argument("--plans-root", default=str(DEFAULT_PLANS_ROOT), help=argparse.SUPPRESS)
        command.add_argument("--semantics-root", default=str(DEFAULT_SEMANTICS_ROOT), help=argparse.SUPPRESS)
        command.set_defaults(func=_command_semantics_field, semantic_field=field)

    semantic_evidence = semantics_sub.add_parser("evidence", help="resolve one semantic claim to Phase-3 evidence")
    semantic_evidence.add_argument("--claim", required=True)
    semantic_evidence.add_argument("--evidence-root", default=str(DEFAULT_EVIDENCE_ROOT), help=argparse.SUPPRESS)
    semantic_evidence.add_argument("--semantics-root", default=str(DEFAULT_SEMANTICS_ROOT), help=argparse.SUPPRESS)
    semantic_evidence.set_defaults(func=_command_semantics_evidence)

    semantic_stats = semantics_sub.add_parser("stats", help="show per-plan semantic statistics")
    semantic_stats.add_argument("--plan-run", required=True)
    semantic_stats.add_argument("--plans-root", default=str(DEFAULT_PLANS_ROOT), help=argparse.SUPPRESS)
    semantic_stats.add_argument("--semantics-root", default=str(DEFAULT_SEMANTICS_ROOT), help=argparse.SUPPRESS)
    semantic_stats.set_defaults(func=_command_semantics_stats)

    translate = commands.add_parser("translate", help="build and inspect Phase 5 Lean translations")
    translate_sub = translate.add_subparsers(dest="translate_command", required=True)
    translate_build = translate_sub.add_parser("build", help="run one bounded OpenCode Lean Translator session")
    translate_build.add_argument("--plan-run", required=True)
    translate_build.add_argument("--unit", required=True, help="exact Phase-4 semantic unit ID")
    translate_build.add_argument("--plans-root", default=str(DEFAULT_PLANS_ROOT), help=argparse.SUPPRESS)
    translate_build.add_argument("--semantics-root", default=str(DEFAULT_SEMANTICS_ROOT), help=argparse.SUPPRESS)
    translate_build.add_argument("--translations-root", default=str(DEFAULT_TRANSLATIONS_ROOT), help=argparse.SUPPRESS)
    translate_build.add_argument("--timeout", type=int, default=1800, help="timeout for the single-unit session in seconds")
    translate_build.set_defaults(func=_command_translate_build)

    translate_revise = translate_sub.add_parser("revise", help="revise an existing translation from coverage diagnostics")
    translate_revise.add_argument("--plan-run", required=True)
    translate_revise.add_argument("--unit", required=True)
    translate_revise.add_argument("--plans-root", default=str(DEFAULT_PLANS_ROOT), help=argparse.SUPPRESS)
    translate_revise.add_argument("--semantics-root", default=str(DEFAULT_SEMANTICS_ROOT), help=argparse.SUPPRESS)
    translate_revise.add_argument("--translations-root", default=str(DEFAULT_TRANSLATIONS_ROOT), help=argparse.SUPPRESS)
    translate_revise.add_argument("--checks-root", default=str(DEFAULT_CHECKS_ROOT), help=argparse.SUPPRESS)
    translate_revise.add_argument("--timeout", type=int, default=1800, help="timeout for the single revision session in seconds")
    translate_revise.set_defaults(func=_command_translate_revise)

    for name, help_text, function in (
        ("show", "show the complete Lean translation artifact", _command_translate_show),
        ("manifest", "show declaration traceability and deterministic translation metadata", _command_translate_manifest),
    ):
        command = translate_sub.add_parser(name, help=help_text)
        command.add_argument("--plan-run", required=True)
        command.add_argument("--unit", required=True)
        command.add_argument("--plans-root", default=str(DEFAULT_PLANS_ROOT), help=argparse.SUPPRESS)
        command.add_argument("--translations-root", default=str(DEFAULT_TRANSLATIONS_ROOT), help=argparse.SUPPRESS)
        command.set_defaults(func=function)

    translate_trace = translate_sub.add_parser("trace", help="resolve a Lean declaration through semantics to source provenance")
    translate_trace.add_argument("--declaration", required=True)
    translate_trace.add_argument("--translations-root", default=str(DEFAULT_TRANSLATIONS_ROOT), help=argparse.SUPPRESS)
    translate_trace.add_argument("--semantics-root", default=str(DEFAULT_SEMANTICS_ROOT), help=argparse.SUPPRESS)
    translate_trace.add_argument("--evidence-root", default=str(DEFAULT_EVIDENCE_ROOT), help=argparse.SUPPRESS)
    translate_trace.set_defaults(func=_command_translate_trace)

    check = commands.add_parser("check", help="run and inspect deterministic Phase 6 checks")
    check_sub = check.add_subparsers(dest="check_command", required=True)
    check_run = check_sub.add_parser("run", help="run build, coverage, and traceability for one translated unit")
    check_run.add_argument("--plan-run", required=True)
    check_run.add_argument("--unit", required=True)
    check_run.add_argument("--database", help=argparse.SUPPRESS)
    check_run.add_argument("--plans-root", default=str(DEFAULT_PLANS_ROOT), help=argparse.SUPPRESS)
    check_run.add_argument("--evidence-root", default=str(DEFAULT_EVIDENCE_ROOT), help=argparse.SUPPRESS)
    check_run.add_argument("--semantics-root", default=str(DEFAULT_SEMANTICS_ROOT), help=argparse.SUPPRESS)
    check_run.add_argument("--translations-root", default=str(DEFAULT_TRANSLATIONS_ROOT), help=argparse.SUPPRESS)
    check_run.add_argument("--checks-root", default=str(DEFAULT_CHECKS_ROOT), help=argparse.SUPPRESS)
    check_run.set_defaults(func=_command_check_run)

    check_recheck = check_sub.add_parser("recheck", help="rerun all Phase-6 checks after a bounded revision")
    check_recheck.add_argument("--plan-run", required=True)
    check_recheck.add_argument("--unit", required=True)
    check_recheck.add_argument("--database", help=argparse.SUPPRESS)
    check_recheck.add_argument("--plans-root", default=str(DEFAULT_PLANS_ROOT), help=argparse.SUPPRESS)
    check_recheck.add_argument("--evidence-root", default=str(DEFAULT_EVIDENCE_ROOT), help=argparse.SUPPRESS)
    check_recheck.add_argument("--semantics-root", default=str(DEFAULT_SEMANTICS_ROOT), help=argparse.SUPPRESS)
    check_recheck.add_argument("--translations-root", default=str(DEFAULT_TRANSLATIONS_ROOT), help=argparse.SUPPRESS)
    check_recheck.add_argument("--checks-root", default=str(DEFAULT_CHECKS_ROOT), help=argparse.SUPPRESS)
    check_recheck.set_defaults(func=_command_check_run)

    for name, help_text, field in (
        ("show", "show the complete Phase-6 check result", None),
        ("coverage", "show coverage details for a checked unit", "coverage"),
        ("traceability", "show traceability details for a checked unit", "traceability"),
    ):
        command = check_sub.add_parser(name, help=help_text)
        command.add_argument("--plan-run", required=True)
        command.add_argument("--unit", required=True)
        command.add_argument("--plans-root", default=str(DEFAULT_PLANS_ROOT), help=argparse.SUPPRESS)
        command.add_argument("--checks-root", default=str(DEFAULT_CHECKS_ROOT), help=argparse.SUPPRESS)
        if field is None:
            command.set_defaults(func=_command_check_show)
        else:
            command.set_defaults(func=_command_check_field, check_field=field)

    troubleshoot = commands.add_parser("troubleshoot", help="route and repair failed Phase-6 checks")
    troubleshoot_sub = troubleshoot.add_subparsers(dest="troubleshoot_command", required=True)
    troubleshoot_run = troubleshoot_sub.add_parser(
        "run", help="route one failed check or run one bounded build-repair session"
    )
    troubleshoot_run.add_argument("--plan-run", required=True)
    troubleshoot_run.add_argument("--unit", required=True)
    troubleshoot_run.add_argument("--plans-root", default=str(DEFAULT_PLANS_ROOT), help=argparse.SUPPRESS)
    troubleshoot_run.add_argument("--semantics-root", default=str(DEFAULT_SEMANTICS_ROOT), help=argparse.SUPPRESS)
    troubleshoot_run.add_argument("--translations-root", default=str(DEFAULT_TRANSLATIONS_ROOT), help=argparse.SUPPRESS)
    troubleshoot_run.add_argument("--checks-root", default=str(DEFAULT_CHECKS_ROOT), help=argparse.SUPPRESS)
    troubleshoot_run.add_argument("--troubleshooting-root", default=str(DEFAULT_TROUBLESHOOTING_ROOT), help=argparse.SUPPRESS)
    troubleshoot_run.add_argument("--timeout", type=int, default=1800, help="timeout for the single repair session in seconds")
    troubleshoot_run.set_defaults(func=_command_troubleshoot_run)

    troubleshoot_resolve = troubleshoot_sub.add_parser(
        "resolve", help="dispatch one failure to its owner and run Phase 6 once"
    )
    troubleshoot_resolve.add_argument("--plan-run", required=True)
    troubleshoot_resolve.add_argument("--unit", required=True)
    troubleshoot_resolve.add_argument("--database", help=argparse.SUPPRESS)
    troubleshoot_resolve.add_argument("--plans-root", default=str(DEFAULT_PLANS_ROOT), help=argparse.SUPPRESS)
    troubleshoot_resolve.add_argument("--evidence-root", default=str(DEFAULT_EVIDENCE_ROOT), help=argparse.SUPPRESS)
    troubleshoot_resolve.add_argument("--semantics-root", default=str(DEFAULT_SEMANTICS_ROOT), help=argparse.SUPPRESS)
    troubleshoot_resolve.add_argument("--translations-root", default=str(DEFAULT_TRANSLATIONS_ROOT), help=argparse.SUPPRESS)
    troubleshoot_resolve.add_argument("--checks-root", default=str(DEFAULT_CHECKS_ROOT), help=argparse.SUPPRESS)
    troubleshoot_resolve.add_argument("--troubleshooting-root", default=str(DEFAULT_TROUBLESHOOTING_ROOT), help=argparse.SUPPRESS)
    troubleshoot_resolve.add_argument("--timeout", type=int, default=1800, help="timeout for each bounded revision session")
    troubleshoot_resolve.add_argument(
        "--max-dispatches", type=int, default=8,
        help="maximum fresh-check actions handled in this invocation",
    )
    troubleshoot_resolve.set_defaults(func=_command_troubleshoot_resolve)

    for name, help_text, function in (
        ("show", "show the complete Phase-7 routing or repair artifact", _command_troubleshoot_show),
        ("changes", "show changed files, hashes, and recheck requirements", _command_troubleshoot_changes),
        ("resolution", "show the latest bounded dispatch and recheck result", _command_troubleshoot_resolution),
    ):
        command = troubleshoot_sub.add_parser(name, help=help_text)
        command.add_argument("--plan-run", required=True)
        command.add_argument("--unit", required=True)
        command.add_argument("--plans-root", default=str(DEFAULT_PLANS_ROOT), help=argparse.SUPPRESS)
        command.add_argument("--troubleshooting-root", default=str(DEFAULT_TROUBLESHOOTING_ROOT), help=argparse.SUPPRESS)
        command.set_defaults(func=function)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "index_command", None) == "build" and not (args.pdf or args.html):
        parser.error("index build requires --pdf and/or --html")
    if getattr(args, "plan_command", None) == "build" and args.timeout < 1:
        parser.error("plan build --timeout must be positive")
    if getattr(args, "evidence_command", None) == "build" and (args.timeout < 1 or args.jobs < 1):
        parser.error("evidence build --timeout and --jobs must be positive")
    if getattr(args, "semantics_command", None) == "build" and args.timeout < 1:
        parser.error("semantics build --timeout must be positive")
    if getattr(args, "semantics_command", None) == "revise" and args.timeout < 1:
        parser.error("semantics revise --timeout must be positive")
    if getattr(args, "translate_command", None) == "build" and args.timeout < 1:
        parser.error("translate build --timeout must be positive")
    if getattr(args, "translate_command", None) == "revise" and args.timeout < 1:
        parser.error("translate revise --timeout must be positive")
    if getattr(args, "troubleshoot_command", None) == "run" and args.timeout < 1:
        parser.error("troubleshoot run --timeout must be positive")
    if getattr(args, "troubleshoot_command", None) == "resolve" and (
        args.timeout < 1 or args.max_dispatches < 1
    ):
        parser.error("troubleshoot resolve --timeout and --max-dispatches must be positive")
    try:
        return int(args.func(args))
    except (FileNotFoundError, FileExistsError, KeyError, RuntimeError, ValueError, sqlite3.Error) as exc:
        print(f"spec2lean: error: {exc}", file=sys.stderr)
        return 2
