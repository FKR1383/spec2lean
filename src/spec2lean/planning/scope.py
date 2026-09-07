from __future__ import annotations

from ..embeddings import index_mode, search as semantic_search

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

_SUFFIX_NAME = r"[A-Za-z][A-Za-z0-9_]*(?:::[A-Za-z0-9_]+)*"
_SUFFIX_TOKEN = re.compile(rf"\.(?P<name>{_SUFFIX_NAME})")
_DEFINITION_HEAD = re.compile(
    rf"(?P<aliases>(?:\.{_SUFFIX_NAME}\s*=\s*)+)\{{",
    re.I,
)
_TITLE_IDENTIFIER = r"[@A-Za-z_{}][@A-Za-z0-9_.{}]*"
_TITLE_ALIAS_LIST = re.compile(
    rf"^{_TITLE_IDENTIFIER}(?:\s*(?:/|,|\bor\b)\s*{_TITLE_IDENTIFIER})*$",
    re.I,
)
_TITLE_ENTRY_SEPARATOR = re.compile(r"\s*[—–]\s*|\s+-\s+")


def _title_mnemonics(title: str | None) -> list[str]:
    if not title:
        return []
    tail = title.rsplit(":", 1)[-1].strip() if ":" in title else title.strip()
    return [item.casefold() for item in re.findall(r"[@A-Za-z_{}][@A-Za-z0-9_.{}]*", tail)]


def _title_identity_labels(title: str | None) -> tuple[str, ...]:
    """Extract aliases only from a heading's explicit instruction-identity zone."""
    if not title:
        return ()
    clean = normalize_text(title)
    separator = _TITLE_ENTRY_SEPARATOR.search(clean)
    if separator:
        identity = clean[: separator.start()].strip()
        # Support a category prefix such as ``Instructions: ADD—Add``.
        identity = identity.rsplit(":", 1)[-1].strip()
    elif ":" in clean:
        identity = clean.rsplit(":", 1)[-1].strip()
    elif re.fullmatch(_TITLE_IDENTIFIER, clean):
        identity = clean
    else:
        # A prose section heading has no explicit instruction identity.  Its
        # individual words must not be treated as mnemonic aliases.
        return ()
    if not _TITLE_ALIAS_LIST.fullmatch(identity):
        return ()
    return tuple(
        match.group(0).casefold()
        for match in re.finditer(_TITLE_IDENTIFIER, identity)
        if match.group(0).casefold() != "or"
    )


def _matching_brace(text: str, opening: int) -> int | None:
    depth = 0
    for position in range(opening, len(text)):
        if text[position] == "{":
            depth += 1
        elif text[position] == "}":
            depth -= 1
            if depth == 0:
                return position
    return None


def _definition_choices(body: str) -> set[str]:
    """Extract finite dotted alternatives, including nested namespace choices."""
    choices: set[str] = set()
    position = 0
    nested_choice = re.compile(rf"(?:::|\.){_SUFFIX_NAME}")
    while match := _SUFFIX_TOKEN.search(body, position):
        base = match.group(0).casefold()
        choices.add(base)
        position = match.end()
        if position >= len(body) or body[position] != "{":
            continue
        closing = _matching_brace(body, position)
        if closing is None:
            break
        for nested in nested_choice.finditer(body, position + 1, closing):
            choices.add(base + nested.group(0).casefold())
        position = closing + 1
    return choices


def _syntax_definitions(syntax_text: str) -> dict[str, set[str]]:
    """Parse finite suffix definitions and assign alias chains to every name."""
    definitions: dict[str, set[str]] = {}
    position = 0
    while match := _DEFINITION_HEAD.search(syntax_text, position):
        opening = match.end() - 1
        closing = _matching_brace(syntax_text, opening)
        if closing is None:
            break
        choices = _definition_choices(syntax_text[opening + 1 : closing])
        for alias in _SUFFIX_TOKEN.finditer(match.group("aliases")):
            definitions.setdefault(alias.group("name").casefold(), set()).update(choices)
        position = closing + 1
    return definitions


def _syntax_form_terms(syntax_text: str, position: int) -> list[tuple[bool, str]]:
    """Read adjacent required or braced-optional dotted suffix terms."""
    terms: list[tuple[bool, str]] = []
    while position < len(syntax_text):
        if syntax_text.startswith("{.", position):
            closing = _matching_brace(syntax_text, position)
            if closing is None:
                break
            token = _SUFFIX_TOKEN.fullmatch(syntax_text[position + 1 : closing].strip())
            if token is None:
                break
            terms.append((True, token.group("name").casefold()))
            position = closing + 1
            continue
        token = _SUFFIX_TOKEN.match(syntax_text, position)
        if token is None:
            break
        terms.append((False, token.group("name").casefold()))
        position = token.end()
    return terms


def _terms_accept(
    wanted_suffix: str,
    terms: list[tuple[bool, str]],
    definitions: dict[str, set[str]],
) -> bool:
    """Match without materializing the Cartesian product of all alternatives."""
    positions = {0}
    for optional, name in terms:
        choices = definitions.get(name, {f".{name}"})
        candidates = choices | ({""} if optional else set())
        positions = {
            position + len(candidate)
            for position in positions
            for candidate in candidates
            if wanted_suffix.startswith(candidate, position)
        }
        if not positions:
            return False
    return len(wanted_suffix) in positions


def _syntax_accepts(instruction: str, mnemonic: str, syntax_text: str) -> bool:
    """Match an exact spelling against source-defined finite syntax templates."""
    wanted = instruction.casefold()
    mnemonic = mnemonic.casefold()
    if not wanted.startswith(mnemonic):
        return False
    definitions = _syntax_definitions(syntax_text)
    form_start = re.compile(
        rf"(?<![A-Za-z0-9_.]){re.escape(mnemonic)}(?=\.|\{{\.)",
        re.I,
    )
    wanted_suffix = wanted[len(mnemonic) :]
    return any(
        terms and _terms_accept(wanted_suffix, terms, definitions)
        for match in form_start.finditer(syntax_text)
        if (terms := _syntax_form_terms(syntax_text, match.end()))
    )


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
        if index_mode() == "semantic":
            rows = semantic_search(self.connection, query, limit=limit)
            result = [_node_summary(row) for row in rows]
            for item, row in zip(result, rows, strict=True):
                item.update(snippet=row["snippet"], similarity=row["similarity"])
            return result
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
            for mnemonic in _title_identity_labels(row["title"]):
                if wanted == mnemonic or wanted.startswith(mnemonic + "."):
                    match_quality = 2 if wanted == mnemonic else 1
                    heading_matches.append((match_quality, mnemonic, row))
        if not heading_matches:
            return []
        exact_pattern = re.compile(rf"(?<![A-Za-z0-9_.]){re.escape(instruction)}(?![A-Za-z0-9_.])", re.I)
        matches: list[tuple[tuple[int, int], sqlite3.Row]] = []
        for match_quality, mnemonic, row in heading_matches:
            descendants = self.connection.execute(
                """WITH RECURSIVE tree(node_id) AS (
                       SELECT node_id FROM nodes WHERE node_id = ?
                       UNION ALL SELECT n.node_id FROM nodes n JOIN tree t ON n.parent_id = t.node_id
                   ) SELECT node_id, node_type, raw_text FROM nodes JOIN tree USING(node_id)""",
                (row["node_id"],),
            ).fetchall()
            literal = any(exact_pattern.search(item["raw_text"]) for item in descendants)
            literal_content = any(
                item["node_id"] != row["node_id"] and exact_pattern.search(item["raw_text"])
                for item in descendants
            )
            syntax = any(item["node_type"] == "syntax_block" for item in descendants) and _syntax_accepts(
                instruction,
                mnemonic,
                "\n".join(item["raw_text"] for item in descendants),
            )
            if literal or syntax:
                evidence_quality = 2 if syntax else 1 if literal_content else 0
                matches.append(((match_quality, evidence_quality), row))
        if not matches:
            return []
        # Semantic match and evidence quality determine precedence.  Document
        # depth and opaque node IDs never decide which instruction a heading
        # denotes; equally supported representations are intentionally kept.
        best_score = max(score for score, _ in matches)
        return sorted({row["node_id"] for score, row in matches if score == best_score})

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
