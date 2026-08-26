from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from typing import Any, Iterable

from ..util import normalize_text, stable_id
from .models import PlanningRequest, ScopeMode


MAX_FAMILY_CANDIDATES = 200
MAX_TOOL_ROWS = 100
MAX_TOOL_TEXT_CHARS = 24_000


def _title_mnemonics(title: str | None) -> list[str]:
    if not title:
        return []
    tail = title.rsplit(":", 1)[-1].strip() if ":" in title else title.strip()
    return [item.casefold() for item in re.findall(r"[@A-Za-z_{}][@A-Za-z0-9_.{}]*", tail)]


def _syntax_accepts(instruction: str, mnemonic: str, syntax_text: str) -> bool:
    """Match an exact spelling against syntax forms and their finite alternatives."""
    definitions: dict[str, set[str]] = {}
    for match in re.finditer(r"\.([A-Za-z][A-Za-z0-9_]*)\s*=\s*\{([^}]*)\}", syntax_text):
        definitions[match.group(1).casefold()] = {
            item.casefold() for item in re.findall(r"\.[A-Za-z0-9_]+", match.group(2))
        }
    form_pattern = re.compile(
        rf"(?<![A-Za-z0-9_.]){re.escape(mnemonic)}"
        r"((?:(?:\{\.[A-Za-z0-9_]+\})|(?:\.[A-Za-z0-9_]+))+)",
        re.I,
    )
    wanted = instruction.casefold()
    for match in form_pattern.finditer(syntax_text):
        suffix_terms = re.findall(r"\{\.[A-Za-z0-9_]+\}|\.[A-Za-z0-9_]+", match.group(1))
        expansions = [mnemonic.casefold()]
        for term in suffix_terms:
            optional = term.startswith("{")
            name = term.strip("{}")[1:].casefold()
            choices = sorted(definitions.get(name, {f".{name}"}))
            if optional:
                choices = [""] + choices
            expansions = [prefix + choice for prefix in expansions for choice in choices]
        if wanted in expansions:
            return True
    return False


def _node_summary(row: sqlite3.Row | dict[str, Any], *, include_text: bool = False) -> dict[str, Any]:
    result = {
        "nodeId": row["node_id"],
        "nodeType": row["node_type"],
        "title": row["title"],
        "sectionNumber": row["section_number"],
        "htmlAnchor": row["html_anchor"],
        "pageStart": row["page_start"],
    }
    if "source_type" in row.keys():
        result["sourceType"] = row["source_type"]
    if include_text:
        result["text"] = row["raw_text"][:MAX_TOOL_TEXT_CHARS]
        result["textTruncated"] = len(row["raw_text"]) > MAX_TOOL_TEXT_CHARS
    return result


def _section_order(section: str | None) -> tuple[Any, ...]:
    if section and all(part.isdigit() for part in section.split(".")):
        return (0, *(int(part) for part in section.split(".")))
    return (1, section or "")


@dataclass(frozen=True, slots=True)
class ResolvedScope:
    request: PlanningRequest
    candidate_units: tuple[dict[str, Any], ...]
    context_node_ids: tuple[str, ...]
    root_node_ids: tuple[str, ...]
    exact_unit_ids: tuple[str, ...] = ()

    @property
    def candidate_by_id(self) -> dict[str, dict[str, Any]]:
        return {item["unitId"]: item for item in self.candidate_units}

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": 1,
            "request": self.request.to_dict(),
            "candidateUnits": [dict(item) for item in self.candidate_units],
            "contextNodeIds": list(self.context_node_ids),
            "rootNodeIds": list(self.root_node_ids),
            "exactUnitIds": list(self.exact_unit_ids),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ResolvedScope:
        return cls(
            request=PlanningRequest.from_dict(value["request"]),
            candidate_units=tuple(value.get("candidateUnits", ())),
            context_node_ids=tuple(value.get("contextNodeIds", ())),
            root_node_ids=tuple(value.get("rootNodeIds", ())),
            exact_unit_ids=tuple(value.get("exactUnitIds", ())),
        )


class Phase1Query:
    """Bounded, read-only query interface over a Phase 1 SQLite connection."""

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def node_exists(self, node_id: str) -> bool:
        return self.connection.execute(
            "SELECT 1 FROM nodes WHERE node_id = ?", (node_id,)
        ).fetchone() is not None

    def show(self, node_id: str) -> dict[str, Any]:
        row = self.connection.execute(
            """SELECT n.*, d.source_type FROM nodes n
               JOIN documents d ON d.document_id = n.document_id WHERE n.node_id = ?""",
            (node_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown node: {node_id}")
        result = _node_summary(row, include_text=True)
        result["metadata"] = json.loads(row["metadata_json"])
        return result

    def children(self, node_id: str, *, limit: int = MAX_TOOL_ROWS) -> list[dict[str, Any]]:
        self._bounded_limit(limit)
        return [
            _node_summary(row)
            for row in self.connection.execute(
                """SELECT n.*, d.source_type FROM nodes n JOIN documents d USING(document_id)
                   WHERE n.parent_id = ? ORDER BY n.ordinal, n.node_id LIMIT ?""",
                (node_id, limit),
            )
        ]

    def ancestors(self, node_id: str, *, limit: int = 30) -> list[dict[str, Any]]:
        self._bounded_limit(limit)
        rows = self.connection.execute(
            """WITH RECURSIVE ancestors(node_id, parent_id, distance) AS (
                   SELECT node_id, parent_id, 0 FROM nodes WHERE node_id = ?
                   UNION ALL
                   SELECT n.node_id, n.parent_id, a.distance + 1
                   FROM nodes n JOIN ancestors a ON n.node_id = a.parent_id
               )
               SELECT n.*, d.source_type, a.distance FROM ancestors a
               JOIN nodes n ON n.node_id = a.node_id JOIN documents d USING(document_id)
               ORDER BY a.distance DESC LIMIT ?""",
            (node_id, limit),
        ).fetchall()
        return [_node_summary(row) for row in rows]

    def subtree(
        self, node_id: str, *, max_depth: int = 3, limit: int = MAX_TOOL_ROWS
    ) -> list[dict[str, Any]]:
        if max_depth < 0 or max_depth > 8:
            raise ValueError("max_depth must be between 0 and 8")
        self._bounded_limit(limit)
        rows = self.connection.execute(
            """WITH RECURSIVE tree(node_id, distance, path) AS (
                   SELECT node_id, 0, printf('%08d', ordinal) FROM nodes WHERE node_id = ?
                   UNION ALL
                   SELECT n.node_id, t.distance + 1, t.path || '/' || printf('%08d', n.ordinal)
                   FROM nodes n JOIN tree t ON n.parent_id = t.node_id WHERE t.distance < ?
               )
               SELECT n.*, d.source_type, t.distance FROM tree t JOIN nodes n USING(node_id)
               JOIN documents d USING(document_id) ORDER BY t.path, n.node_id LIMIT ?""",
            (node_id, max_depth, limit),
        ).fetchall()
        return [_node_summary(row, include_text=True) for row in rows]

    def search(self, query: str, *, limit: int = 20) -> list[dict[str, Any]]:
        self._bounded_limit(limit)
        tokens = [token.replace('"', '""') for token in query.split() if token]
        if not tokens:
            raise ValueError("search query must be non-empty")
        fts = " AND ".join(f'"{token}"' for token in tokens)
        rows = self.connection.execute(
            """SELECT n.*, d.source_type,
                      snippet(nodes_fts, 2, '[', ']', ' … ', 32) AS snippet,
                      bm25(nodes_fts, 8.0, 1.0, 0.5) AS rank
               FROM nodes_fts JOIN nodes n ON n.node_id = nodes_fts.node_id
               JOIN documents d USING(document_id) WHERE nodes_fts MATCH ?
               ORDER BY rank, n.node_id LIMIT ?""",
            (fts, limit),
        ).fetchall()
        result = [_node_summary(row) for row in rows]
        for item, row in zip(result, rows, strict=True):
            item["snippet"] = row["snippet"]
        return result

    def xrefs(self, node_id: str, *, include_incoming: bool = True) -> list[dict[str, Any]]:
        clauses = "r.source_node_id = ?"
        params: list[Any] = [node_id]
        if include_incoming:
            clauses += " OR r.resolved_target_node_id = ?"
            params.append(node_id)
        rows = self.connection.execute(
            f"""SELECT r.* FROM cross_references r WHERE {clauses}
                ORDER BY r.source_node_id, r.ordinal LIMIT ?""",
            (*params, MAX_TOOL_ROWS),
        ).fetchall()
        return [dict(row) for row in rows]

    def definitions(self, query: str | None = None, *, limit: int = 40) -> list[dict[str, Any]]:
        self._bounded_limit(limit)
        sql = """SELECT t.term, d.definition_text, d.structural_basis, d.node_id
                 FROM definitions d JOIN terms t USING(term_id)"""
        params: list[Any] = []
        if query:
            sql += " WHERE t.normalized_term LIKE ?"
            params.append(f"%{normalize_text(query).casefold()}%")
        sql += " ORDER BY t.normalized_term, d.node_id LIMIT ?"
        params.append(limit)
        return [dict(row) for row in self.connection.execute(sql, params)]

    @staticmethod
    def _bounded_limit(limit: int) -> None:
        if limit < 1 or limit > MAX_TOOL_ROWS:
            raise ValueError(f"limit must be between 1 and {MAX_TOOL_ROWS}")


class ScopeResolver:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self.query = Phase1Query(connection)

    def resolve(self, request: PlanningRequest) -> ResolvedScope:
        self._validate_database_identity(request)
        if request.mode == ScopeMode.EXACT_INSTRUCTIONS:
            return self._resolve_exact(request)
        if request.mode == ScopeMode.INSTRUCTION_FAMILY:
            return self._resolve_family(request)
        if request.mode == ScopeMode.SOURCE_SUBTREE:
            return self._resolve_subtree(request)
        return self._resolve_full(request)

    def _validate_database_identity(self, request: PlanningRequest) -> None:
        row = self.connection.execute(
            "SELECT language, version FROM specifications LIMIT 1"
        ).fetchone()
        if row is None:
            raise ValueError("Phase 1 database has no specification identity")
        if row["language"].casefold() != request.language.casefold() or row["version"] != request.version:
            raise ValueError(
                f"database contains {row['language']} {row['version']}, not "
                f"{request.language} {request.version}"
            )

    def _resolve_exact(self, request: PlanningRequest) -> ResolvedScope:
        units: list[dict[str, Any]] = []
        roots: list[str] = []
        for instruction in request.instructions:
            node_ids = self._exact_instruction_nodes(instruction)
            if not node_ids:
                raise ValueError(f"exact instruction could not be resolved: {instruction}")
            unit = self._unit(instruction, node_ids)
            units.append(unit)
            roots.extend(node_ids)
        context = self._context_nodes(roots)
        return ResolvedScope(
            request,
            tuple(units),
            tuple(context),
            tuple(dict.fromkeys(roots)),
            tuple(item["unitId"] for item in units),
        )

    def _exact_instruction_nodes(self, instruction: str) -> list[str]:
        wanted = instruction.casefold()
        rows = self.connection.execute(
            """SELECT n.*, d.source_type FROM nodes n JOIN documents d USING(document_id)
               WHERE n.node_type IN ('chapter', 'section', 'subsection')
               ORDER BY CASE d.source_type WHEN 'html' THEN 0 ELSE 1 END,
                        n.depth, n.node_id"""
        ).fetchall()
        heading_matches: list[tuple[int, str, sqlite3.Row]] = []
        for row in rows:
            for mnemonic in _title_mnemonics(row["title"]):
                if wanted == mnemonic or wanted.startswith(mnemonic + "."):
                    heading_matches.append((len(mnemonic), mnemonic, row))
        if not heading_matches:
            return []
        longest_mnemonic = max(length for length, _, _ in heading_matches)
        headings = [
            (mnemonic, row)
            for length, mnemonic, row in heading_matches
            if length == longest_mnemonic
        ]
        exact_pattern = re.compile(rf"(?<![A-Za-z0-9_.]){re.escape(instruction)}(?![A-Za-z0-9_.])", re.I)
        matches: list[sqlite3.Row] = []
        for mnemonic, row in headings:
            descendants = self.connection.execute(
                """WITH RECURSIVE tree(node_id) AS (
                       SELECT node_id FROM nodes WHERE node_id = ?
                       UNION ALL SELECT n.node_id FROM nodes n JOIN tree t ON n.parent_id = t.node_id
                   ) SELECT node_type, raw_text FROM nodes JOIN tree USING(node_id)""",
                (row["node_id"],),
            ).fetchall()
            literal = any(exact_pattern.search(item["raw_text"]) for item in descendants)
            syntax = any(item["node_type"] == "syntax_block" for item in descendants) and _syntax_accepts(
                instruction,
                mnemonic,
                "\n".join(item["raw_text"] for item in descendants),
            )
            if literal or syntax:
                matches.append(row)
        if not matches:
            return []
        # Keep corresponding source representations of the most specific logical section.
        best_depth = max(row["depth"] for row in matches)
        matches = [row for row in matches if row["depth"] == best_depth]
        best_section = matches[0]["section_number"]
        best_tail = tuple(_title_mnemonics(matches[0]["title"]))
        selected = [
            row["node_id"]
            for row in matches
            if row["section_number"] == best_section
            and tuple(_title_mnemonics(row["title"])) == best_tail
        ]
        return sorted(set(selected))

    def _resolve_family(self, request: PlanningRequest) -> ResolvedScope:
        assert request.family is not None
        roots = self._family_roots(request.family)
        if not roots:
            raise ValueError(f"instruction family could not be resolved: {request.family}")
        units = self._child_units(roots)
        if not units:
            units = [self._unit(request.family, roots)]
        if len(units) > MAX_FAMILY_CANDIDATES:
            raise ValueError(
                f"family scope produced {len(units)} candidates; maximum is {MAX_FAMILY_CANDIDATES}"
            )
        return ResolvedScope(
            request,
            tuple(units),
            tuple(self._context_nodes([node for unit in units for node in unit["sourceNodeIds"]])),
            tuple(roots),
        )

    def _family_roots(self, family: str) -> list[str]:
        wanted = normalize_text(family).casefold()
        significant = [word for word in re.findall(r"[a-z0-9]+", wanted) if word not in {"the", "a", "an"}]
        rows = self.connection.execute(
            """SELECT n.*, d.source_type FROM nodes n JOIN documents d USING(document_id)
               WHERE n.node_type IN ('chapter', 'section', 'subsection') AND n.title IS NOT NULL
               ORDER BY CASE d.source_type WHEN 'html' THEN 0 ELSE 1 END, n.depth, n.node_id"""
        ).fetchall()
        scored: list[tuple[int, sqlite3.Row]] = []
        for row in rows:
            title = normalize_text(row["title"]).casefold()
            if not all(word in title for word in significant):
                continue
            score = (1000 if title == wanted else 0) + len(significant) * 10 - abs(len(title) - len(wanted))
            scored.append((score, row))
        if not scored:
            return []
        best = max(score for score, _ in scored)
        winners = [row for score, row in scored if score == best]
        key = (winners[0]["section_number"], normalize_text(winners[0]["title"]).casefold())
        return sorted(
            row["node_id"]
            for _, row in scored
            if (row["section_number"], normalize_text(row["title"]).casefold()) == key
        )

    def _resolve_subtree(self, request: PlanningRequest) -> ResolvedScope:
        assert request.source_node_id is not None
        if not self.query.node_exists(request.source_node_id):
            raise ValueError(f"source subtree node does not exist: {request.source_node_id}")
        roots = self._correlated_nodes(request.source_node_id)
        units = self._child_units(roots)
        if not units:
            title = self.query.show(request.source_node_id)["title"] or request.source_node_id
            units = [self._unit(title, roots)]
        return ResolvedScope(
            request,
            tuple(units),
            tuple(self._context_nodes([node for unit in units for node in unit["sourceNodeIds"]])),
            tuple(roots),
            tuple(item["unitId"] for item in units),
        )

    def _resolve_full(self, request: PlanningRequest) -> ResolvedScope:
        roots = [
            row["node_id"]
            for row in self.connection.execute(
                "SELECT node_id FROM nodes WHERE parent_id IS NULL ORDER BY document_id, node_id"
            )
        ]
        units = self._child_units(roots)
        if not units:
            units = [self._unit("full specification", roots)]
        return ResolvedScope(
            request,
            tuple(units),
            tuple(self._context_nodes([node for unit in units for node in unit["sourceNodeIds"]])),
            tuple(roots),
            tuple(item["unitId"] for item in units),
        )

    def _child_units(self, roots: Iterable[str]) -> list[dict[str, Any]]:
        rows: list[sqlite3.Row] = []
        for root in roots:
            rows.extend(
                self.connection.execute(
                    """SELECT n.*, d.source_type FROM nodes n JOIN documents d USING(document_id)
                       WHERE n.parent_id = ? AND n.node_type IN ('chapter', 'section', 'subsection')
                       ORDER BY n.ordinal, n.node_id""",
                    (root,),
                ).fetchall()
            )
        grouped: dict[tuple[str | None, str], list[sqlite3.Row]] = {}
        for row in rows:
            key = (row["section_number"], normalize_text(row["title"] or row["node_id"]).casefold())
            grouped.setdefault(key, []).append(row)
        units = []
        for key in sorted(grouped, key=lambda item: (_section_order(item[0]), item[1])):
            group = grouped[key]
            title = group[0]["title"] or group[0]["node_id"]
            names = _title_mnemonics(title)
            name = ", ".join(names) if ":" in title and names else title
            units.append(self._unit(name, [row["node_id"] for row in group]))
        return units

    def _correlated_nodes(self, node_id: str) -> list[str]:
        related = {node_id}
        rows = self.connection.execute(
            """SELECT left_node_id, right_node_id FROM node_correlations
               WHERE left_node_id = ? OR right_node_id = ?""",
            (node_id, node_id),
        )
        for row in rows:
            related.update((row["left_node_id"], row["right_node_id"]))
        return sorted(related)

    def _context_nodes(self, roots: Iterable[str]) -> list[str]:
        result: set[str] = set()
        for node_id in roots:
            result.add(node_id)
            for item in self.query.ancestors(node_id):
                result.add(item["nodeId"])
            for ref in self.query.xrefs(node_id):
                result.add(ref["source_node_id"])
                if ref["resolved_target_node_id"]:
                    result.add(ref["resolved_target_node_id"])
            for related in self._correlated_nodes(node_id):
                result.add(related)
        return sorted(result)

    @staticmethod
    def _unit(name: str, node_ids: Iterable[str]) -> dict[str, Any]:
        sources = sorted(set(node_ids))
        return {
            "unitId": stable_id("unit", name.casefold(), *sources),
            "name": name,
            "sourceNodeIds": sources,
        }
