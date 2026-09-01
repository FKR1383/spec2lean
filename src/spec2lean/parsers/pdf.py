from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..model import Definition, Node, ParsedDocument, SourceSpan
from ..references import text_references
from ..util import normalize_text, sha256_file, split_section_title


LIST_RE = re.compile(r"^(?:[•●▪◦‣▶*-]|\(?[a-zA-Z0-9]+[.)])\s+")
DEFINITION_RE = re.compile(r"^(?:Definition|Term)\s+([^:—–-]{1,100})\s*[:—–-]", re.I)
NOTE_RE = re.compile(r"^(?:NOTE|Note|Warning|Important)\s*[:.—–-]?")
EXAMPLE_RE = re.compile(r"^Example(?:\s+\d+(?:\.\d+)*)?\s*[:.—–-]?")
CAPTION_RE = re.compile(r"^(?:Table|Figure)\s+[A-Z]?(?:\d+(?:\.\d+)*)", re.I)


@dataclass(slots=True)
class PdfBlock:
    page: int
    index: int
    bbox: tuple[float, float, float, float]
    raw_text: str
    max_size: float
    bold_ratio: float
    mono_ratio: float
    spans: list[SourceSpan] = field(default_factory=list)
    block_type: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


def _overlap_ratio(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    area = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    own = max(1.0, (a[2] - a[0]) * (a[3] - a[1]))
    return area / own


def _extract_block(page_number: int, index: int, block: dict[str, Any]) -> PdfBlock:
    bbox = tuple(float(value) for value in block.get("bbox", (0, 0, 0, 0)))
    block_type = int(block.get("type", 0))
    if block_type != 0:
        metadata = {
            "pdf_block_type": block_type,
            "width": block.get("width"),
            "height": block.get("height"),
            "extension": block.get("ext"),
        }
        return PdfBlock(page_number, index, bbox, "", 0, 0, 0, block_type=block_type, metadata=metadata)

    line_texts: list[str] = []
    source_spans: list[SourceSpan] = []
    sizes: list[tuple[float, int]] = []
    bold_chars = 0
    mono_chars = 0
    total_chars = 0
    for line_index, line in enumerate(block.get("lines", [])):
        pieces: list[str] = []
        for span_index, span in enumerate(line.get("spans", [])):
            text = span.get("text", "")
            pieces.append(text)
            count = max(len(text), 1)
            size = float(span.get("size", 0.0))
            sizes.append((size, count))
            font = str(span.get("font", ""))
            flags = int(span.get("flags", 0))
            if re.search(r"bold|demi|black|heavy", font, re.I) or flags & 16:
                bold_chars += len(text)
            if re.search(r"mono|courier|consolas|code", font, re.I):
                mono_chars += len(text)
            total_chars += len(text)
            source_spans.append(
                SourceSpan(
                    raw_text=text,
                    page_number=page_number,
                    bbox=tuple(float(value) for value in span.get("bbox", bbox)),
                    block_index=index,
                    line_index=line_index,
                    span_index=span_index,
                )
            )
        line_texts.append("".join(pieces))
    raw = "\n".join(line_texts)
    max_size = max((size for size, _ in sizes), default=0.0)
    return PdfBlock(
        page_number,
        index,
        bbox,
        raw,
        max_size,
        bold_chars / max(total_chars, 1),
        mono_chars / max(total_chars, 1),
        source_spans,
        block_type=block_type,
    )


# A table-of-contents line: a title, a run of dot leaders, then a page number.
TOC_RE = re.compile(r"\.{4,}\s*\d{1,4}\s*$")
# A block that is nothing but a page number.
PAGE_NUMBER_RE = re.compile(r"^\d{1,4}$")


def _furniture_key(text: str) -> str:
    """Collapse a running header or footer to what repeats across pages."""
    return re.sub(r"\d+", "#", normalize_text(text)).casefold()


def _page_furniture(
    blocks: list[PdfBlock], page_heights: dict[int, float], page_count: int
) -> set[tuple[int, int]]:
    """Identify running headers, footers and page numbers.

    Position alone is not enough — a real paragraph can begin at the top of a
    page — so the signal is repetition: the same text, digits masked, appearing
    in the same margin on several pages. A specification's running header is
    provenance, not content, and a retriever offered 73 page numbers among 229
    paragraphs is being asked to filter the index by hand.
    """
    threshold = max(3, page_count // 10)
    seen: dict[str, set[int]] = defaultdict(set)
    marginal: list[tuple[PdfBlock, str]] = []
    for block in blocks:
        if block.block_type != 0:
            continue
        height = page_heights.get(block.page)
        if not height:
            continue
        top, bottom = block.bbox[1] <= height * 0.08, block.bbox[3] >= height * 0.92
        if not (top or bottom):
            continue
        text = normalize_text(block.raw_text)
        if not text:
            continue
        key = ("HEAD" if top else "FOOT") + "|" + _furniture_key(text)
        seen[key].add(block.page)
        marginal.append((block, key))

    furniture: set[tuple[int, int]] = set()
    for block, key in marginal:
        text = normalize_text(block.raw_text)
        # A bare page number in a margin is furniture on its own; anything else
        # must actually repeat.
        if PAGE_NUMBER_RE.fullmatch(text) or len(seen[key]) >= threshold:
            furniture.add((block.page, block.index))
    return furniture


def _compact_table(rows: list[list[Any]]) -> tuple[list[list[str]], int]:
    """Drop columns that are empty in every row.

    Merged and spanning cells make PyMuPDF report a grid several times wider
    than the table really is, padded with `None`. In a specification's register
    tables two of every three columns can be padding, which is what an extractor
    then has to read past to find the bit fields.
    """
    width = max((len(row) for row in rows), default=0)
    normalized = [
        [("" if cell is None else str(cell)) for cell in row] + [""] * (width - len(row))
        for row in rows
    ]
    keep = [
        column
        for column in range(width)
        if any(normalized[row][column].strip() for row in range(len(normalized)))
    ]
    compacted = [[row[column] for column in keep] for row in normalized]

    # A merged header cell also splits one logical column across two grid
    # columns: the header lands in one, every data value in the other, and the
    # two are never occupied in the same row. Merging them puts each column
    # back under its own heading.
    merged = True
    while merged and compacted and len(compacted[0]) > 1:
        merged = False
        for column in range(len(compacted[0]) - 1):
            left = [row[column].strip() for row in compacted]
            right = [row[column + 1].strip() for row in compacted]
            if not any(left) or not any(right):
                continue
            if any(a and b for a, b in zip(left, right)):
                continue
            for row in compacted:
                combined = row[column] or row[column + 1]
                row[column : column + 2] = [combined]
            merged = True
            break
    return compacted, width - len(compacted[0] if compacted else [])


def _body_font_size(blocks: list[PdfBlock]) -> float:
    weighted: Counter[float] = Counter()
    for block in blocks:
        if block.block_type != 0:
            continue
        for span in block.spans:
            if span.raw_text.strip() and span.bbox:
                # Span height is a stable proxy if font details are absent here.
                height = round(span.bbox[3] - span.bbox[1], 1)
                if 5 <= height <= 30:
                    weighted[height] += len(span.raw_text)
    return weighted.most_common(1)[0][0] if weighted else 10.0


def _heading(
    block: PdfBlock, body_size: float, page_height: float
) -> tuple[int, str | None, str] | None:
    clean = normalize_text(block.raw_text)
    if not clean or len(clean) > 240 or block.mono_ratio > 0.6:
        return None
    # Running headers and footers often combine a page number with a bold
    # chapter title. They remain content/provenance, never hierarchy.
    if block.bbox[1] <= page_height * 0.065 or block.bbox[3] >= page_height * 0.93:
        return None
    # A table-of-contents line names a section without being one. Treating it as
    # a heading invents a second, empty copy of every chapter.
    if TOC_RE.search(clean):
        return None
    chapter = re.match(r"^Chapter\s+(\d+)\.?\s+(.+)$", clean, re.I)
    if chapter and block.max_size >= body_size * 1.4:
        return 1, chapter.group(1), chapter.group(2).strip()
    number, title = split_section_title(clean)
    if number and title:
        level = number.count(".") + 1
        heading_style = block.max_size >= body_size * 1.15 or block.bold_ratio >= 0.45
        if level <= 7 and len(clean) <= 160 and heading_style:
            return level, number, title
    appendix = re.match(r"^(Appendix\s+[A-Z])(?:\s*[:.—–-]?\s*)(.*)$", clean, re.I)
    if appendix and (block.bold_ratio >= 0.4 or block.max_size >= body_size * 1.05):
        return 1, appendix.group(1), appendix.group(2) or appendix.group(1)
    if block.max_size >= body_size * 1.45 and block.bold_ratio >= 0.45 and len(clean) <= 100:
        return 1, None, clean
    return None


def _uses_numbered_headings(
    blocks: list[PdfBlock], body_size: float, page_heights: dict[int, float]
) -> bool:
    """Whether this document numbers its headings at all."""
    for block in blocks:
        height = page_heights.get(block.page)
        if not height:
            continue
        heading = _heading(block, body_size, height)
        if heading and heading[1]:
            return True
    return False


def _classify_content(
    block: PdfBlock,
    previous_label: str,
    page_height: float,
    furniture: set[tuple[int, int]] = frozenset(),
) -> tuple[str, dict[str, Any], list[Definition]]:
    clean = normalize_text(block.raw_text)
    metadata: dict[str, Any] = {
        "font_size_max": round(block.max_size, 3),
        "bold_ratio": round(block.bold_ratio, 4),
        "monospace_ratio": round(block.mono_ratio, 4),
        "pdf_block_index": block.index,
    }
    if block.bbox[1] <= page_height * 0.07:
        metadata["layout_role"] = "page_header"
    elif block.bbox[3] >= page_height * 0.93:
        metadata["layout_role"] = "page_footer"

    definitions: list[Definition] = []
    # Both of these stay in the index with their exact text and provenance; they
    # are typed so that everything downstream can tell content from furniture.
    if (block.page, block.index) in furniture:
        return "page_furniture", metadata, definitions
    if TOC_RE.search(clean):
        return "toc_entry", metadata, definitions
    definition = DEFINITION_RE.match(clean)
    if definition:
        term = definition.group(1).strip()
        definitions.append(Definition(term, block.raw_text, "pdf-explicit-definition-label"))
        return "definition", metadata, definitions
    if NOTE_RE.match(clean):
        return "note", metadata, definitions
    if EXAMPLE_RE.match(clean):
        return "example", metadata, definitions
    if CAPTION_RE.match(clean):
        metadata["caption_kind"] = clean.split(None, 1)[0].casefold()
        return "caption", metadata, definitions
    if LIST_RE.match(clean):
        metadata["items"] = [normalize_text(line) for line in block.raw_text.splitlines() if normalize_text(line)]
        return "list", metadata, definitions
    if block.mono_ratio >= 0.55:
        if previous_label.casefold() == "syntax" or "::=" in block.raw_text:
            return "syntax_block", metadata, definitions
        return "code_block", metadata, definitions
    if clean:
        return "paragraph", metadata, definitions
    return "generic", metadata, definitions


def parse_pdf(path: str | Path, official_url: str | None = None, *, detect_tables: bool = True) -> ParsedDocument:
    try:
        import pymupdf as fitz
    except ImportError as exc:  # pragma: no cover - exercised by CLI installation diagnostics
        raise RuntimeError("PDF indexing requires PyMuPDF; install the project dependencies") from exc

    source = Path(path).resolve()
    fitz.TOOLS.mupdf_display_errors(False)
    pdf = fitz.open(source)
    metadata = pdf.metadata or {}
    title = normalize_text(metadata.get("title") or "") or source.name
    all_blocks: list[PdfBlock] = []
    pages: list[dict[str, Any]] = []
    table_by_page: dict[int, list[dict[str, Any]]] = {}
    stats: Counter[str] = Counter()
    source_chars = 0

    for page_index, page in enumerate(pdf):
        page_number = page_index + 1
        page_text = page.get_text("text", sort=True)
        source_chars += len(normalize_text(page_text))
        pages.append(
            {
                "page_number": page_number,
                "width": float(page.rect.width),
                "height": float(page.rect.height),
                "raw_text": page_text,
                "source_text_chars": len(normalize_text(page_text)),
            }
        )
        page_dict = page.get_text("dict", sort=True)
        for block_index, block_data in enumerate(page_dict.get("blocks", [])):
            all_blocks.append(_extract_block(page_number, block_index, block_data))

        tables: list[dict[str, Any]] = []
        if detect_tables and hasattr(page, "find_tables"):
            try:
                finder = page.find_tables()
                for table_index, table in enumerate(finder.tables):
                    rows, dropped = _compact_table(table.extract())
                    raw = "\n".join("\t".join(row) for row in rows)
                    tables.append(
                        {
                            "index": table_index,
                            "bbox": tuple(float(value) for value in table.bbox),
                            "rows": rows,
                            "raw_text": raw,
                            "empty_columns_dropped": dropped,
                        }
                    )
            except Exception as exc:  # retain page content even when table inference fails
                stats["pdf_table_detection_errors"] += 1
                stats[f"pdf_table_error_{type(exc).__name__}"] += 1
        table_by_page[page_number] = tables
        stats["pdf_tables_discovered"] += len(tables)

    body_size = _body_font_size(all_blocks)
    page_height_by_number = {page["page_number"]: page["height"] for page in pages}
    numbered_headings = _uses_numbered_headings(all_blocks, body_size, page_height_by_number)
    furniture = _page_furniture(
        all_blocks,
        page_height_by_number,
        len(pdf),
    )
    root = Node(
        source_key="root",
        node_type="document",
        title=title,
        metadata={"pdf_metadata": metadata, "body_font_height": body_size},
        page_start=1 if len(pdf) else None,
        page_end=len(pdf) or None,
    )
    heading_stack: dict[int, Node] = {}
    previous_label = ""
    page_heights = {page["page_number"]: page["height"] for page in pages}

    for page_number in range(1, len(pdf) + 1):
        blocks = [block for block in all_blocks if block.page == page_number]
        blocks.sort(key=lambda item: (round(item.bbox[1], 2), round(item.bbox[0], 2), item.index))
        tables = table_by_page.get(page_number, [])
        events: list[tuple[float, float, str, Any]] = []
        for table in tables:
            events.append((table["bbox"][1], table["bbox"][0], "table", table))
        for block in blocks:
            if any(_overlap_ratio(block.bbox, table["bbox"]) >= 0.5 for table in tables):
                continue
            events.append((block.bbox[1], block.bbox[0], "block", block))
        events.sort(key=lambda event: (round(event[0], 2), round(event[1], 2), event[2]))

        for _, _, kind, value in events:
            parent = heading_stack[max(heading_stack)] if heading_stack else root
            if kind == "table":
                table = value
                raw = table["raw_text"]
                node = Node(
                    source_key=f"page:{page_number}:table:{table['index']}",
                    node_type="table",
                    raw_text=raw,
                    page_start=page_number,
                    page_end=page_number,
                    metadata={
                        "rows": table["rows"],
                        "pdf_table_index": table["index"],
                        "empty_columns_dropped": table.get("empty_columns_dropped", 0),
                    },
                    spans=[SourceSpan(raw, page_number, table["bbox"])],
                    references=text_references(raw),
                )
                parent.add(node)
                stats["table"] += 1
                previous_label = "table"
                continue

            block: PdfBlock = value
            if block.block_type != 0:
                node = Node(
                    source_key=f"page:{page_number}:block:{block.index}",
                    node_type="generic",
                    raw_text="",
                    page_start=page_number,
                    page_end=page_number,
                    metadata=block.metadata,
                    spans=[SourceSpan("", page_number, block.bbox, block.index)],
                )
                parent.add(node)
                stats["generic"] += 1
                stats["pdf_nontext_blocks"] += 1
                continue

            if not normalize_text(block.raw_text):
                continue
            heading = _heading(block, body_size, page_heights[page_number])
            # A cover page repeats the document title in large bold type, which
            # is indistinguishable from a chapter heading by style alone. When
            # the document numbers its real headings, an unnumbered one on page
            # 1 is cover text: keep the words, drop the false hierarchy.
            if (
                heading
                and numbered_headings
                and page_number == 1
                and heading[0] == 1
                and not heading[1]
            ):
                heading = None
                cover_text = True
            else:
                cover_text = False
            if heading:
                level, section_number, heading_title = heading
                for old_level in [item for item in heading_stack if item >= level]:
                    del heading_stack[old_level]
                parent = heading_stack[max(heading_stack)] if heading_stack else root
                node_type = "chapter" if level == 1 else "section" if level == 2 else "subsection"
                node = Node(
                    source_key=f"page:{page_number}:block:{block.index}:heading",
                    node_type=node_type,
                    raw_text=block.raw_text,
                    title=heading_title,
                    section_number=section_number,
                    page_start=page_number,
                    page_end=page_number,
                    metadata={
                        "heading_level": level,
                        "font_size_max": round(block.max_size, 3),
                        "bold_ratio": round(block.bold_ratio, 4),
                        "pdf_block_index": block.index,
                    },
                    spans=block.spans,
                    references=text_references(block.raw_text),
                )
                parent.add(node)
                heading_stack[level] = node
                stats[node_type] += 1
                previous_label = heading_title
                continue

            parent = heading_stack[max(heading_stack)] if heading_stack else root
            node_type, node_metadata, definitions = _classify_content(
                block, previous_label, page_heights[page_number], furniture
            )
            if cover_text and node_type == "paragraph":
                node_type = "cover_text"
            node = Node(
                source_key=f"page:{page_number}:block:{block.index}",
                node_type=node_type,
                raw_text=block.raw_text,
                page_start=page_number,
                page_end=page_number,
                metadata=node_metadata,
                spans=block.spans,
                references=text_references(block.raw_text),
                definitions=definitions,
            )
            parent.add(node)
            stats[node_type] += 1
            previous_label = normalize_text(block.raw_text)

    stats["pdf_pages_discovered"] = len(pdf)
    stats["pdf_pages_indexed"] = len(pages)
    stats["pdf_text_blocks_discovered"] = sum(block.block_type == 0 for block in all_blocks)
    stats["pdf_blocks_indexed"] = sum(stats[node_type] for node_type in (
        "chapter", "section", "subsection", "paragraph", "definition", "table",
        "code_block", "syntax_block", "list", "note", "example", "caption", "generic"
    ))
    page_count = len(pdf)
    pdf.close()
    return ParsedDocument(
        source_type="pdf",
        path=str(source),
        sha256=sha256_file(source),
        byte_size=source.stat().st_size,
        title=title,
        root=root,
        official_url=official_url,
        page_count=page_count,
        pages=pages,
        source_text_chars=source_chars,
        parser_stats=dict(stats),
    )
