from __future__ import annotations

import json
import sqlite3
from typing import Any, Callable


MAX_LIMIT = 500
MAX_TEXT_CHARS = 50_000


def _bounded(value: Any, default: int, maximum: int = MAX_LIMIT) -> int:
    if value is None:
        return default
    return max(0, min(int(value), maximum))


def _node(row: sqlite3.Row, *, include_text: bool = False, text_chars: int = 0) -> dict[str, Any]:
    item: dict[str, Any] = {
        "nodeId": row["node_id"],
        "parentId": row["parent_id"],
        "nodeType": row["node_type"],
        "depth": row["depth"],
        "ordinal": row["ordinal"],
        "sectionNumber": row["section_number"],
        "title": row["title"],
        "sourceType": row["source_type"],
        "pageStart": row["page_start"],
        "pageEnd": row["page_end"],
        "htmlAnchor": row["html_anchor"],
    }
    if include_text:
        raw = row["raw_text"]
        item["rawText"] = raw[:text_chars]
        item["rawTextTruncated"] = len(raw) > text_chars
    return item


def _page(items: list[dict[str, Any]], *, total: int, offset: int, limit: int) -> dict[str, Any]:
    return {
        "items": items,
        "total": total,
        "offset": offset,
        "limit": limit,
        "truncated": offset + len(items) < total,
    }


def spec_tree(connection: sqlite3.Connection, request: dict[str, Any]) -> dict[str, Any]:
    source_type = request.get("sourceType", "html")
    root_id = request.get("rootNodeId")
    max_depth = _bounded(request.get("maxDepth"), 2, 12)
    offset = _bounded(request.get("offset"), 0, 1_000_000)
    limit = _bounded(request.get("limit"), 100)
    headings_only = request.get("headingsOnly", True) is not False
    params: list[Any] = []
    if root_id:
        seed = "SELECT node_id, parent_id, 0 AS relative_depth, printf('%08d', ordinal) AS path FROM nodes WHERE node_id = ?"
        params.append(root_id)
    else:
        seed = """SELECT n.node_id, n.parent_id, 0 AS relative_depth,
                         d.source_type || ':' || printf('%08d', n.ordinal) AS path
                  FROM nodes n JOIN documents d ON d.document_id = n.document_id
                  WHERE n.parent_id IS NULL AND d.source_type = ?"""
        params.append(source_type)
    type_clause = "AND n.node_type IN ('document','chapter','section','subsection')" if headings_only else ""
    cte = f"""WITH RECURSIVE tree(node_id, parent_id, relative_depth, path) AS (
                  {seed}
                  UNION ALL
                  SELECT n.node_id, n.parent_id, tree.relative_depth + 1,
                         tree.path || '.' || printf('%08d', n.ordinal)
                  FROM nodes n JOIN tree ON n.parent_id = tree.node_id
                  WHERE tree.relative_depth < ?
              )"""
    params.append(max_depth)
    count = connection.execute(
        cte + f" SELECT count(*) FROM tree JOIN nodes n ON n.node_id = tree.node_id WHERE 1=1 {type_clause}",
        params,
    ).fetchone()[0]
    rows = connection.execute(
        cte
        + f""" SELECT n.*, d.source_type, tree.relative_depth
               FROM tree JOIN nodes n ON n.node_id = tree.node_id
               JOIN documents d ON d.document_id = n.document_id
               WHERE 1=1 {type_clause}
               ORDER BY tree.path LIMIT ? OFFSET ?""",
        [*params, limit, offset],
    ).fetchall()
    items = [_node(row) | {"relativeDepth": row["relative_depth"]} for row in rows]
    return _page(items, total=count, offset=offset, limit=limit)


def spec_search(connection: sqlite3.Connection, request: dict[str, Any]) -> dict[str, Any]:
    query = request.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string")
    tokens = [token.replace('"', '""') for token in query.split() if token]
    fts = " AND ".join(f'"{token}"' for token in tokens)
    source_type = request.get("sourceType", "html")
    node_type = request.get("nodeType")
    offset = _bounded(request.get("offset"), 0, 1_000_000)
    limit = _bounded(request.get("limit"), 20, 100)
    where = ["nodes_fts MATCH ?", "d.source_type = ?"]
    params: list[Any] = [fts, source_type]
    if node_type:
        where.append("n.node_type = ?")
        params.append(node_type)
    where_sql = " AND ".join(where)
    total = connection.execute(
        f"""SELECT count(*) FROM nodes_fts JOIN nodes n USING(node_id)
            JOIN documents d ON d.document_id = n.document_id WHERE {where_sql}""",
        params,
    ).fetchone()[0]
    rows = connection.execute(
        f"""SELECT n.*, d.source_type,
                   snippet(nodes_fts, 2, '[', ']', ' ... ', 40) AS snippet,
                   bm25(nodes_fts, 8.0, 1.0, 0.5) AS rank
            FROM nodes_fts JOIN nodes n USING(node_id)
            JOIN documents d ON d.document_id = n.document_id
            WHERE {where_sql} ORDER BY rank, n.node_id LIMIT ? OFFSET ?""",
        [*params, limit, offset],
    ).fetchall()
    items = [_node(row) | {"snippet": row["snippet"], "rank": row["rank"]} for row in rows]
    return _page(items, total=total, offset=offset, limit=limit)


def spec_show(connection: sqlite3.Connection, request: dict[str, Any]) -> dict[str, Any]:
    node_id = request.get("nodeId")
    text_chars = _bounded(request.get("textChars"), 12_000, MAX_TEXT_CHARS)
    row = connection.execute(
        """SELECT n.*, d.source_type FROM nodes n JOIN documents d USING(document_id)
           WHERE n.node_id = ?""",
        (node_id,),
    ).fetchone()
    if row is None:
        raise KeyError(f"unknown node: {node_id}")
    item = _node(row, include_text=True, text_chars=text_chars)
    item["metadata"] = json.loads(row["metadata_json"])
    item["childCount"] = connection.execute(
        "SELECT count(*) FROM nodes WHERE parent_id = ?", (node_id,)
    ).fetchone()[0]
    item["definitions"] = [
        dict(definition)
        for definition in connection.execute(
            """SELECT t.term, d.definition_text AS definitionText,
                      d.structural_basis AS structuralBasis
               FROM definitions d JOIN terms t USING(term_id)
               WHERE d.node_id = ? ORDER BY d.ordinal""",
            (node_id,),
        )
    ]
    item["crossReferences"] = [
        {
            "referenceId": ref["reference_id"],
            "kind": ref["kind"],
            "rawText": ref["raw_text"],
            "targetReferenceText": ref["target_reference_text"],
            "resolvedTargetNodeId": ref["resolved_target_node_id"],
            "resolutionStatus": ref["resolution_status"],
        }
        for ref in connection.execute(
            "SELECT * FROM cross_references WHERE source_node_id = ? ORDER BY ordinal", (node_id,)
        )
    ]
    return item


def spec_children(connection: sqlite3.Connection, request: dict[str, Any]) -> dict[str, Any]:
    node_id = request.get("nodeId")
    offset = _bounded(request.get("offset"), 0, 1_000_000)
    limit = _bounded(request.get("limit"), 100)
    headings_only = request.get("headingsOnly", False) is True
    type_clause = "AND n.node_type IN ('chapter','section','subsection')" if headings_only else ""
    total = connection.execute(
        f"SELECT count(*) FROM nodes n WHERE n.parent_id = ? {type_clause}", (node_id,)
    ).fetchone()[0]
    rows = connection.execute(
        f"""SELECT n.*, d.source_type FROM nodes n JOIN documents d USING(document_id)
            WHERE n.parent_id = ? {type_clause} ORDER BY n.ordinal LIMIT ? OFFSET ?""",
        (node_id, limit, offset),
    ).fetchall()
    return _page([_node(row) for row in rows], total=total, offset=offset, limit=limit)


def spec_ancestors(connection: sqlite3.Connection, request: dict[str, Any]) -> dict[str, Any]:
    node_id = request.get("nodeId")
    rows = connection.execute(
        """WITH RECURSIVE ancestors(node_id, parent_id, distance) AS (
               SELECT node_id, parent_id, 0 FROM nodes WHERE node_id = ?
               UNION ALL
               SELECT n.node_id, n.parent_id, ancestors.distance + 1
               FROM nodes n JOIN ancestors ON n.node_id = ancestors.parent_id
           )
           SELECT n.*, d.source_type, ancestors.distance
           FROM ancestors JOIN nodes n USING(node_id) JOIN documents d USING(document_id)
           ORDER BY ancestors.distance DESC""",
        (node_id,),
    ).fetchall()
    if not rows:
        raise KeyError(f"unknown node: {node_id}")
    return {"items": [_node(row) | {"distance": row["distance"]} for row in rows]}


def spec_subtree(connection: sqlite3.Connection, request: dict[str, Any]) -> dict[str, Any]:
    nested = dict(request)
    nested["rootNodeId"] = request.get("nodeId")
    nested.setdefault("maxDepth", 3)
    nested.setdefault("limit", 100)
    return spec_tree(connection, nested)


def spec_definitions(connection: sqlite3.Connection, request: dict[str, Any]) -> dict[str, Any]:
    query = request.get("query")
    source_type = request.get("sourceType", "html")
    offset = _bounded(request.get("offset"), 0, 1_000_000)
    limit = _bounded(request.get("limit"), 50, 100)
    where = ["src.source_type = ?"]
    params: list[Any] = [source_type]
    if query:
        where.append("t.normalized_term LIKE ?")
        params.append(f"%{str(query).casefold()}%")
    where_sql = " AND ".join(where)
    base = """FROM definitions d JOIN terms t USING(term_id)
              JOIN nodes n ON n.node_id = d.node_id
              JOIN documents src ON src.document_id = n.document_id"""
    total = connection.execute(f"SELECT count(*) {base} WHERE {where_sql}", params).fetchone()[0]
    rows = connection.execute(
        f"""SELECT t.term, d.definition_text, d.structural_basis,
                   n.node_id, n.section_number, n.title, src.source_type
            {base} WHERE {where_sql}
            ORDER BY t.normalized_term, n.node_id LIMIT ? OFFSET ?""",
        [*params, limit, offset],
    ).fetchall()
    items = [
        {
            "term": row["term"],
            "definitionText": row["definition_text"],
            "structuralBasis": row["structural_basis"],
            "nodeId": row["node_id"],
            "sectionNumber": row["section_number"],
            "title": row["title"],
            "sourceType": row["source_type"],
        }
        for row in rows
    ]
    return _page(items, total=total, offset=offset, limit=limit)


def spec_xrefs(connection: sqlite3.Connection, request: dict[str, Any]) -> dict[str, Any]:
    node_id = request.get("nodeId")
    status = request.get("status")
    direction = request.get("direction", "either")
    offset = _bounded(request.get("offset"), 0, 1_000_000)
    limit = _bounded(request.get("limit"), 50, 100)
    where: list[str] = []
    params: list[Any] = []
    if node_id:
        if direction == "source":
            where.append("r.source_node_id = ?")
            params.append(node_id)
        elif direction == "target":
            where.append("r.resolved_target_node_id = ?")
            params.append(node_id)
        else:
            where.append("(r.source_node_id = ? OR r.resolved_target_node_id = ?)")
            params.extend([node_id, node_id])
    if status:
        where.append("r.resolution_status = ?")
        params.append(status)
    where_sql = " WHERE " + " AND ".join(where) if where else ""
    total = connection.execute(
        f"SELECT count(*) FROM cross_references r{where_sql}", params
    ).fetchone()[0]
    rows = connection.execute(
        f"""SELECT r.*, n.section_number, n.title, d.source_type
            FROM cross_references r JOIN nodes n ON n.node_id = r.source_node_id
            JOIN documents d ON d.document_id = n.document_id
            {where_sql} ORDER BY r.reference_id LIMIT ? OFFSET ?""",
        [*params, limit, offset],
    ).fetchall()
    items = [
        {
            "referenceId": row["reference_id"],
            "sourceNodeId": row["source_node_id"],
            "sourceSectionNumber": row["section_number"],
            "sourceTitle": row["title"],
            "sourceType": row["source_type"],
            "kind": row["kind"],
            "rawText": row["raw_text"],
            "targetReferenceText": row["target_reference_text"],
            "resolvedTargetNodeId": row["resolved_target_node_id"],
            "resolutionStatus": row["resolution_status"],
        }
        for row in rows
    ]
    return _page(items, total=total, offset=offset, limit=limit)


TOOLS: dict[str, Callable[[sqlite3.Connection, dict[str, Any]], dict[str, Any]]] = {
    "tree": spec_tree,
    "search": spec_search,
    "show": spec_show,
    "children": spec_children,
    "ancestors": spec_ancestors,
    "subtree": spec_subtree,
    "definitions": spec_definitions,
    "xrefs": spec_xrefs,
}


def invoke_tool(connection: sqlite3.Connection, name: str, request: dict[str, Any]) -> dict[str, Any]:
    try:
        implementation = TOOLS[name]
    except KeyError as exc:
        raise ValueError(f"unknown planner tool: {name}") from exc
    if not isinstance(request, dict):
        raise ValueError("planner tool request must be a JSON object")
    return implementation(connection, request)
