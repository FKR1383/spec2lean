from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class SourceSpan:
    raw_text: str
    page_number: int | None = None
    bbox: tuple[float, float, float, float] | None = None
    block_index: int | None = None
    line_index: int | None = None
    span_index: int | None = None
    dom_path: str | None = None
    source_line_start: int | None = None
    source_line_end: int | None = None


@dataclass(slots=True)
class Reference:
    raw_text: str
    target_text: str
    kind: str
    href: str | None = None


@dataclass(slots=True)
class Definition:
    term: str
    definition_text: str
    basis: str


@dataclass(slots=True)
class Node:
    source_key: str
    node_type: str
    raw_text: str = ""
    title: str | None = None
    section_number: str | None = None
    html_anchor: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    spans: list[SourceSpan] = field(default_factory=list)
    references: list[Reference] = field(default_factory=list)
    definitions: list[Definition] = field(default_factory=list)
    children: list[Node] = field(default_factory=list)

    def add(self, child: Node) -> Node:
        self.children.append(child)
        return child


@dataclass(slots=True)
class ParsedDocument:
    source_type: str
    path: str
    sha256: str
    byte_size: int
    title: str
    root: Node
    official_url: str | None = None
    page_count: int | None = None
    pages: list[dict[str, Any]] = field(default_factory=list)
    source_text_chars: int = 0
    parser_stats: dict[str, Any] = field(default_factory=dict)

