from __future__ import annotations

import math
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
EMPHASIS_FONT_RE = re.compile(
    r"bold|demi|black|heavy|medium|semi[ -]?bold|bookbold", re.I
)
# Formal reference manuals commonly introduce one entry with a short label and
# a descriptive title separated by a typographic dash.  A spaced ASCII hyphen
# is accepted too, but an ordinary in-word hyphen is deliberately not.
ENTRY_TITLE_RE = re.compile(
    r"^(?P<label>\S(?:.{0,78}?\S)?)"
    r"(?:\s*[—–]\s*|\s+-\s+)"
    r"(?P<description>\S(?:.{0,158}?\S)?)$"
)


@dataclass(slots=True)
class PdfBlock:
    page: int
    index: int
    bbox: tuple[float, float, float, float] | None
    raw_text: str
    max_size: float
    bold_ratio: float
    mono_ratio: float
    spans: list[SourceSpan] = field(default_factory=list)
    font_size_weights: tuple[tuple[float, int], ...] = ()
    emphasis_ratio: float = 0.0
    block_type: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class HeadingMatch:
    level: int
    section_number: str | None
    title: str
    basis: str


def _overlap_ratio(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    area = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    own = max(1.0, (a[2] - a[0]) * (a[3] - a[1]))
    return area / own


def _bbox_on_page(
    bbox: tuple[float, float, float, float],
    page_width: float,
    page_height: float,
) -> bool:
    """Return whether a PDF bbox is finite, ordered, and within the page."""
    x0, y0, x1, y1 = bbox
    return (
        all(math.isfinite(value) for value in bbox)
        and 0 <= x0 <= x1 <= page_width + 1
        and 0 <= y0 <= y1 <= page_height + 1
    )


def _bbox_from_transform(transform: Any) -> tuple[float, float, float, float] | None:
    """Map the unit image rectangle through a six-value PDF transform."""
    try:
        a, b, c, d, e, f = (float(value) for value in transform)
    except (TypeError, ValueError):
        return None
    points = ((e, f), (a + e, b + f), (c + e, d + f), (a + c + e, b + d + f))
    return (
        min(point[0] for point in points),
        min(point[1] for point in points),
        max(point[0] for point in points),
        max(point[1] for point in points),
    )


def _extract_image_block(
    page_number: int,
    image_index: int,
    image: dict[str, Any],
    page_width: float,
    page_height: float,
) -> PdfBlock:
    """Create a non-text block from PyMuPDF's displayed-image inventory.

    ``get_text('dict')`` can return corrupt image-mask bboxes when media-box
    clipping is enabled. ``get_image_info()`` avoids loading image binaries and
    normally supplies the correct displayed bbox. The transform provides a
    deterministic fallback, and an untrustworthy bbox is never persisted.
    """
    try:
        reported_bbox = tuple(float(value) for value in image.get("bbox", ()))
    except (TypeError, ValueError):
        reported_bbox = ()
    bbox: tuple[float, float, float, float] | None = None
    bbox_source = "unavailable"
    if len(reported_bbox) == 4 and _bbox_on_page(reported_bbox, page_width, page_height):
        bbox = reported_bbox
        bbox_source = "get_image_info"
    else:
        transformed_bbox = _bbox_from_transform(image.get("transform"))
        if transformed_bbox is not None and _bbox_on_page(
            transformed_bbox, page_width, page_height
        ):
            bbox = transformed_bbox
            bbox_source = "transform_fallback"

    transform = image.get("transform")
    metadata: dict[str, Any] = {
        "pdf_block_type": 1,
        "pdf_image_index": image_index,
        "pdf_image_number": image.get("number"),
        "width": image.get("width"),
        "height": image.get("height"),
        "colorspace": image.get("colorspace"),
        "colorspace_name": image.get("cs-name"),
        "bits_per_component": image.get("bpc"),
        "x_resolution": image.get("xres"),
        "y_resolution": image.get("yres"),
        "encoded_size": image.get("size"),
        "has_mask": image.get("has-mask"),
        "bbox_source": bbox_source,
    }
    if transform is not None:
        try:
            metadata["transform"] = tuple(float(value) for value in transform)
        except (TypeError, ValueError):
            metadata["transform_invalid"] = True
    if len(reported_bbox) == 4 and bbox_source != "get_image_info":
        metadata["invalid_reported_bbox"] = reported_bbox
    return PdfBlock(
        page=page_number,
        index=image_index,
        bbox=bbox,
        raw_text="",
        max_size=0,
        bold_ratio=0,
        mono_ratio=0,
        block_type=1,
        metadata=metadata,
    )


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
        return PdfBlock(
            page=page_number,
            index=index,
            bbox=bbox,
            raw_text="",
            max_size=0,
            bold_ratio=0,
            mono_ratio=0,
            block_type=block_type,
            metadata=metadata,
        )

    line_texts: list[str] = []
    source_spans: list[SourceSpan] = []
    sizes: list[tuple[float, int]] = []
    bold_chars = 0
    emphasis_chars = 0
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
            if EMPHASIS_FONT_RE.search(font) or flags & 16:
                emphasis_chars += len(text)
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
    size_weights: Counter[float] = Counter()
    for size, count in sizes:
        if size > 0:
            size_weights[round(size, 2)] += count
    return PdfBlock(
        page=page_number,
        index=index,
        bbox=bbox,
        raw_text=raw,
        max_size=max_size,
        bold_ratio=bold_chars / max(total_chars, 1),
        mono_ratio=mono_chars / max(total_chars, 1),
        spans=source_spans,
        font_size_weights=tuple(sorted(size_weights.items())),
        emphasis_ratio=emphasis_chars / max(total_chars, 1),
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
        for size, characters in block.font_size_weights:
            if 5 <= size <= 30:
                weighted[size] += characters
    return weighted.most_common(1)[0][0] if weighted else 10.0


def _canonical_number(number: str) -> str:
    """A section number with trailing `.0` components removed.

    Chapter 6 and chapter "6.0" are the same chapter, so they must collide when
    checking that a number is only claimed once.
    """
    parts = number.split(".")
    while len(parts) > 1 and parts[-1] == "0":
        parts.pop()
    return ".".join(parts)


def _heading_level(number: str) -> int:
    """Depth implied by a section number.

    A trailing `.0` names a chapter, not a subsection: specifications that
    number their chapters "1.0", "6.0" would otherwise have every chapter read
    as one level too deep, leaving the document with no chapters at all.
    """
    return len(_canonical_number(number).split("."))


def _heading(
    block: PdfBlock,
    body_size: float,
    page_height: float,
    *,
    entry_level: int = 1,
) -> HeadingMatch | None:
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
        return HeadingMatch(1, chapter.group(1), chapter.group(2).strip(), "chapter_label")
    number, title = split_section_title(clean)
    if number and title and any(character.isalpha() for character in title):
        level = _heading_level(number)
        heading_style = (
            block.max_size >= body_size * 1.15 or block.emphasis_ratio >= 0.45
        )
        if level <= 7 and len(clean) <= 160 and heading_style:
            return HeadingMatch(level, number, title, "section_number")
    appendix = re.match(r"^(Appendix\s+[A-Z])(?:\s*[:.—–-]?\s*)(.*)$", clean, re.I)
    if appendix and (block.emphasis_ratio >= 0.4 or block.max_size >= body_size * 1.05):
        return HeadingMatch(
            1,
            appendix.group(1),
            appendix.group(2) or appendix.group(1),
            "appendix_label",
        )

    # Entry titles in formal specifications are often not numbered sections.
    # Require both their label-description grammar and document-relative
    # typographic prominence so prose containing a dash is not promoted.
    entry_title = ENTRY_TITLE_RE.fullmatch(clean)
    line_count = sum(bool(line.strip()) for line in block.raw_text.splitlines())
    entry_prominence = block.max_size >= body_size * 1.2 and (
        block.emphasis_ratio >= 0.45 or block.max_size >= body_size * 1.3
    )
    entry_description = entry_title.group("description") if entry_title else ""
    if (
        entry_title
        and any(character.isalpha() for character in entry_description)
        and line_count <= 2
        and entry_prominence
    ):
        return HeadingMatch(entry_level, None, clean, "label_description_entry")

    alphabetic_ratio = sum(character.isalpha() for character in clean) / max(len(clean), 1)
    if (
        block.max_size >= body_size * 1.45
        and block.emphasis_ratio >= 0.45
        and alphabetic_ratio >= 0.35
        and len(clean) <= 100
    ):
        return HeadingMatch(1, None, clean, "prominent_unnumbered")
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
        if heading and heading.section_number:
            return True
    return False


def _entry_heading_level(heading_stack: dict[int, Node]) -> int:
    """Place repeated unnumbered entries below the active structural heading."""
    for level in sorted(heading_stack, reverse=True):
        if heading_stack[level].metadata.get("heading_basis") == "label_description_entry":
            return level
    return min(max(heading_stack, default=0) + 1, 7)


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
        "emphasis_ratio": round(block.emphasis_ratio, 4),
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
        # Text and displayed images intentionally use separate APIs. PyMuPDF's
        # default dictionary flags preserve images and apply media-box clipping;
        # that combination can produce malformed bboxes for image masks.
        text_flags = fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_IMAGES
        page_dict = page.get_text("dict", flags=text_flags, sort=True)
        for block_index, block_data in enumerate(page_dict.get("blocks", [])):
            all_blocks.append(_extract_block(page_number, block_index, block_data))
        for image_index, image_info in enumerate(page.get_image_info()):
            image_block = _extract_image_block(
                page_number,
                image_index,
                image_info,
                float(page.rect.width),
                float(page.rect.height),
            )
            all_blocks.append(image_block)
            if image_block.bbox is None:
                stats["pdf_image_bbox_unavailable"] += 1
            elif image_block.metadata["bbox_source"] == "transform_fallback":
                stats["pdf_image_bbox_transform_fallback"] += 1

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

    # A cover can contain more large-title characters than a tiny document has
    # body text. Once a later page exists, let actual document pages establish
    # the font baseline instead of allowing cover typography to become "body".
    body_blocks = [block for block in all_blocks if block.page > 1] or all_blocks
    body_size = _body_font_size(body_blocks)
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
        metadata={
            "pdf_metadata": metadata,
            # Keep the original key for index compatibility; values are now
            # measured in actual PDF font points rather than bbox height.
            "body_font_height": body_size,
            "body_font_size": body_size,
        },
        page_start=1 if len(pdf) else None,
        page_end=len(pdf) or None,
    )
    heading_stack: dict[int, Node] = {}
    # A specification numbers each of its sections once. A later block claiming
    # a number already used is prose that happens to start with a numeral —
    # compliance-test steps such as "6. Verify: ..." are the common case, and
    # each one used to open a new chapter.
    claimed_numbers: set[str] = set()
    previous_label = ""
    page_heights = {page["page_number"]: page["height"] for page in pages}

    for page_number in range(1, len(pdf) + 1):
        blocks = [block for block in all_blocks if block.page == page_number]
        blocks.sort(
            key=lambda item: (
                round(item.bbox[1], 2) if item.bbox is not None else float("inf"),
                round(item.bbox[0], 2) if item.bbox is not None else float("inf"),
                item.block_type,
                item.index,
            )
        )
        tables = table_by_page.get(page_number, [])
        events: list[tuple[float, float, str, Any]] = []
        for table in tables:
            events.append((table["bbox"][1], table["bbox"][0], "table", table))
        for block in blocks:
            if block.bbox is not None and any(
                _overlap_ratio(block.bbox, table["bbox"]) >= 0.5 for table in tables
            ):
                continue
            event_y = block.bbox[1] if block.bbox is not None else float("inf")
            event_x = block.bbox[0] if block.bbox is not None else float("inf")
            events.append((event_y, event_x, "block", block))
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
                    source_key=f"page:{page_number}:image:{block.index}",
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
            heading = _heading(
                block,
                body_size,
                page_heights[page_number],
                entry_level=_entry_heading_level(heading_stack),
            )
            if heading and heading.section_number:
                canonical = _canonical_number(heading.section_number)
                if canonical in claimed_numbers:
                    heading = None
                else:
                    claimed_numbers.add(canonical)
            # A cover page repeats the document title in large bold type, which
            # is indistinguishable from a chapter heading by style alone. When
            # the document numbers its real headings, an unnumbered one on page
            # 1 is cover text: keep the words, drop the false hierarchy.
            if (
                heading
                and numbered_headings
                and page_number == 1
                and heading.level == 1
                and not heading.section_number
            ):
                heading = None
                cover_text = True
            else:
                cover_text = False
            if heading:
                level = heading.level
                for old_level in [item for item in heading_stack if item >= level]:
                    del heading_stack[old_level]
                parent = heading_stack[max(heading_stack)] if heading_stack else root
                node_type = "chapter" if level == 1 else "section" if level == 2 else "subsection"
                node = Node(
                    source_key=f"page:{page_number}:block:{block.index}:heading",
                    node_type=node_type,
                    raw_text=block.raw_text,
                    title=heading.title,
                    section_number=heading.section_number,
                    page_start=page_number,
                    page_end=page_number,
                    metadata={
                        "heading_level": level,
                        "heading_basis": heading.basis,
                        "font_size_max": round(block.max_size, 3),
                        "bold_ratio": round(block.bold_ratio, 4),
                        "emphasis_ratio": round(block.emphasis_ratio, 4),
                        "pdf_block_index": block.index,
                    },
                    spans=block.spans,
                    references=text_references(block.raw_text),
                )
                parent.add(node)
                heading_stack[level] = node
                stats[node_type] += 1
                previous_label = heading.title
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
