from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Iterable

from lxml import etree, html

from ..model import Definition, Node, ParsedDocument, Reference, SourceSpan
from ..references import text_references
from ..util import normalize_text, sha256_file, split_section_title


SEMANTIC_TAGS = {"p", "pre", "table", "ul", "ol", "dl", "figure", "aside", "blockquote"}
SKIP_TAGS = {"script", "style", "noscript", "template", "nav"}


def _raw_text(element: etree._Element) -> str:
    return "".join(element.itertext())


def _classes(element: etree._Element) -> set[str]:
    return set((element.get("class") or "").split())


def _dom_path(element: etree._Element) -> str:
    return element.getroottree().getpath(element)


def _span(element: etree._Element, raw: str) -> SourceSpan:
    line = element.sourceline
    return SourceSpan(
        raw_text=raw,
        dom_path=_dom_path(element),
        source_line_start=line,
        source_line_end=line,
    )


def _references(element: etree._Element, raw: str) -> list[Reference]:
    refs = text_references(raw)
    seen = {(ref.kind, ref.target_text, ref.href) for ref in refs}
    for anchor in element.xpath(".//a[@href]"):
        href = anchor.get("href")
        if not href or not href.startswith("#") or len(href) == 1:
            continue
        label = normalize_text(_raw_text(anchor)) or href
        key = ("ANCHOR", href[1:], href)
        if key in seen:
            continue
        seen.add(key)
        refs.append(
            Reference(raw_text=label, target_text=href[1:], kind="ANCHOR", href=href)
        )
    return refs


def _anchor(element: etree._Element) -> str | None:
    if element.get("id"):
        return element.get("id")
    named = element.xpath(".//a[@id or @name][1]")
    if named:
        return named[0].get("id") or named[0].get("name")
    return None


def _node_for_element(element: etree._Element, *, previous_label: str = "") -> Node | None:
    tag = element.tag.lower() if isinstance(element.tag, str) else ""
    classes = _classes(element)
    raw = _raw_text(element)
    clean = normalize_text(raw)
    if not clean and tag not in {"figure", "table"}:
        return None

    node_type = "generic"
    metadata: dict[str, object] = {"html_tag": tag, "classes": sorted(classes)}
    definitions: list[Definition] = []

    if tag == "p":
        node_type = "paragraph"
        if "rubric" in classes and clean.casefold() in {"syntax", "semantics", "description"}:
            node_type = "generic"
        elif classes & {"admonition-title", "note"} or clean.casefold().startswith("note:"):
            node_type = "note"
        elif classes & {"example", "example-title"} or clean.casefold().startswith("example:"):
            node_type = "example"
        elif "caption" in classes:
            node_type = "caption"
        for dfn in element.xpath(".//dfn"):
            term = normalize_text(_raw_text(dfn))
            if term:
                definitions.append(Definition(term, raw, "html-dfn"))
    elif tag == "pre":
        syntax_signal = (
            "syntax" in classes
            or previous_label.casefold() == "syntax"
            or "::=" in raw
            or "grammar" in " ".join(classes).casefold()
        )
        node_type = "syntax_block" if syntax_signal else "code_block"
    elif tag == "table":
        node_type = "table"
        rows = []
        for row in element.xpath(".//tr"):
            rows.append([normalize_text(_raw_text(cell)) for cell in row.xpath("./th|./td")])
        metadata["rows"] = rows
        captions = element.xpath("./caption")
        if captions:
            metadata["caption"] = normalize_text(_raw_text(captions[0]))
    elif tag in {"ul", "ol"}:
        node_type = "list"
        metadata["ordered"] = tag == "ol"
        metadata["items"] = [normalize_text(_raw_text(item)) for item in element.xpath("./li")]
    elif tag == "blockquote":
        node_type = "note"
    elif tag == "figure":
        node_type = "generic"
        metadata["role"] = "figure"
        metadata["images"] = [
            {"src": image.get("src"), "alt": image.get("alt")}
            for image in element.xpath(".//img")
        ]
        captions = element.xpath(".//figcaption")
        if captions:
            metadata["caption"] = normalize_text(_raw_text(captions[0]))
    elif tag == "aside":
        node_type = "footnote" if "footnote" in classes else "note"
    elif tag == "dl":
        node_type = "definition"
        pairs = []
        current_terms: list[str] = []
        for child in element:
            child_tag = child.tag.lower() if isinstance(child.tag, str) else ""
            if child_tag == "dt":
                current_terms.append(normalize_text(_raw_text(child)))
            elif child_tag == "dd":
                body = _raw_text(child)
                for term in current_terms:
                    if term:
                        definitions.append(Definition(term, body, "html-definition-list"))
                        pairs.append({"term": term, "definition": normalize_text(body)})
                current_terms = []
        metadata["entries"] = pairs
    else:
        joined = " ".join(classes).casefold()
        if "admonition" in joined or "note" in classes:
            node_type = "note"
        elif "example" in joined:
            node_type = "example"
        elif "footnote" in joined:
            node_type = "footnote"

    node = Node(
        source_key=_dom_path(element),
        node_type=node_type,
        raw_text=raw,
        html_anchor=_anchor(element),
        metadata=metadata,
        spans=[_span(element, raw)],
        references=_references(element, raw),
        definitions=definitions,
    )
    return node


def _first_direct_heading(section: etree._Element) -> etree._Element | None:
    for child in section:
        if isinstance(child.tag, str) and child.tag.lower() in {f"h{i}" for i in range(1, 7)}:
            return child
    return None


def _heading_node(heading: etree._Element, section: etree._Element | None = None) -> Node:
    tag = heading.tag.lower()
    level = int(tag[1])
    raw = _raw_text(heading)
    number, title = split_section_title(raw)
    node_type = "chapter" if level == 1 else "section" if level == 2 else "subsection"
    owner = section if section is not None else heading
    anchor = owner.get("id") or _anchor(heading)
    return Node(
        source_key=_dom_path(owner) + "#heading",
        node_type=node_type,
        raw_text=raw,
        title=title or normalize_text(raw),
        section_number=number,
        html_anchor=anchor,
        metadata={"heading_level": level, "html_tag": tag},
        spans=[_span(heading, raw)],
        references=_references(heading, raw),
    )


def _parse_children(container: etree._Element, parent: Node, stats: Counter[str]) -> None:
    previous_label = ""
    direct_heading = _first_direct_heading(container) if container.tag.lower() == "section" else None
    for element in container:
        if not isinstance(element.tag, str):
            continue
        tag = element.tag.lower()
        if element is direct_heading or tag in SKIP_TAGS:
            continue
        if tag == "section":
            heading = _first_direct_heading(element)
            if heading is None:
                generic = Node(
                    source_key=_dom_path(element) + "#section-container",
                    node_type="generic",
                    raw_text="",
                    html_anchor=_anchor(element),
                    metadata={"html_tag": "section", "role": "headingless-section"},
                    spans=[],
                )
                parent.add(generic)
                stats[generic.node_type] += 1
                stats["html_sections_indexed"] += 1
                _parse_children(element, generic, stats)
                continue
            heading_node = parent.add(_heading_node(heading, element))
            stats[heading_node.node_type] += 1
            stats["html_sections_indexed"] += 1
            _parse_children(element, heading_node, stats)
            previous_label = heading_node.title or ""
            continue
        if tag in {f"h{i}" for i in range(1, 7)}:
            heading_node = parent.add(_heading_node(element))
            stats[heading_node.node_type] += 1
            stats["html_sections_indexed"] += 1
            previous_label = heading_node.title or ""
            continue
        if tag in SEMANTIC_TAGS:
            node = _node_for_element(element, previous_label=previous_label)
            if node:
                parent.add(node)
                stats[node.node_type] += 1
                previous_label = normalize_text(node.raw_text)
            continue

        classes = _classes(element)
        joined_classes = " ".join(classes).casefold()
        if classes & {"admonition", "note", "warning", "important", "example"}:
            node = _node_for_element(element, previous_label=previous_label)
            if node:
                if "example" in joined_classes:
                    node.node_type = "example"
                else:
                    node.node_type = "note"
                parent.add(node)
                stats[node.node_type] += 1
            continue

        if "highlight" in joined_classes:
            pre_blocks = element.xpath(".//pre")
            if pre_blocks:
                for pre in pre_blocks:
                    node = _node_for_element(pre, previous_label=previous_label)
                    if node:
                        parent.add(node)
                        stats[node.node_type] += 1
                        previous_label = normalize_text(node.raw_text)
                continue

        # Layout containers are transparent; their semantic descendants retain provenance.
        _parse_children(element, parent, stats)


def parse_html(path: str | Path, official_url: str | None = None) -> ParsedDocument:
    source = Path(path).resolve()
    raw_bytes = source.read_bytes()
    parser = html.HTMLParser(encoding=None, recover=True, remove_comments=False)
    document = html.document_fromstring(raw_bytes, parser=parser)
    title_nodes = document.xpath("//title")
    title = normalize_text(_raw_text(title_nodes[0])) if title_nodes else source.name

    candidates = document.xpath("//*[@itemprop='articleBody']")
    if not candidates:
        candidates = document.xpath("//*[@role='main']")
    if not candidates:
        candidates = document.xpath("//main")
    content = candidates[0] if candidates else document

    root = Node(
        source_key="root",
        node_type="document",
        title=title,
        html_anchor=_anchor(content),
        metadata={"content_dom_path": _dom_path(content)},
    )
    stats: Counter[str] = Counter()
    stats["html_sections_discovered"] = len(content.xpath(".//section"))

    if content.tag.lower() == "section" and _first_direct_heading(content) is not None:
        heading = _heading_node(_first_direct_heading(content), content)  # type: ignore[arg-type]
        root.add(heading)
        stats[heading.node_type] += 1
        stats["html_sections_indexed"] += 1
        _parse_children(content, heading, stats)
    else:
        _parse_children(content, root, stats)

    content_text = _raw_text(content)
    stats["html_elements_discovered"] = len(content.xpath(".//*"))
    return ParsedDocument(
        source_type="html",
        path=str(source),
        sha256=sha256_file(source),
        byte_size=len(raw_bytes),
        title=title,
        root=root,
        official_url=official_url,
        source_text_chars=len(normalize_text(content_text)),
        parser_stats=dict(stats),
    )
