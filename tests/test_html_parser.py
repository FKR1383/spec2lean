from __future__ import annotations

from collections import Counter

from spec2lean.parsers.html import parse_html
from spec2lean.util import walk_nodes


def test_semantic_html_hierarchy_and_content(html_source):
    parsed = parse_html(html_source)
    walked = list(walk_nodes(parsed.root))
    counts = Counter(node.node_type for node, _, _, _ in walked)
    introduction = next(node for node, _, _, _ in walked if node.html_anchor == "introduction")
    syntax = next(node for node, _, _, _ in walked if node.html_anchor == "syntax")

    assert introduction.node_type == "chapter"
    assert introduction.section_number == "1"
    assert syntax in introduction.children
    assert syntax.node_type == "section"
    assert syntax.section_number == "1.1"
    assert counts["paragraph"] >= 2
    assert counts["syntax_block"] == 1
    assert counts["table"] == 1
    assert counts["list"] == 1
    assert counts["definition"] == 1
    assert counts["note"] == 1
    assert counts["footnote"] == 1
    assert counts["example"] == 1
    assert "add.type d, a, b;" in next(node.raw_text for node, _, _, _ in walked if node.node_type == "syntax_block")


def test_html_anchor_references_and_definitions(html_source):
    parsed = parse_html(html_source)
    nodes = [node for node, _, _, _ in walk_nodes(parsed.root)]
    overview = next(node for node in nodes if node.html_anchor == "overview")
    definition = next(node for node in nodes if node.node_type == "definition")

    assert any(ref.href == "#syntax" and ref.target_text == "syntax" for ref in overview.references)
    assert any(ref.kind == "SECTION" and ref.target_text == "1.1" for ref in overview.references)
    assert definition.definitions[0].term == "predicate"
    assert definition.spans[0].dom_path
    assert definition.spans[0].source_line_start
