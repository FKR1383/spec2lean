from __future__ import annotations

import math
import re
from collections import Counter
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
CONTENTS_ENTRY_RE = re.compile(
    r"^\s*(\d+(?:\.\d+)*\.?)\s+(.+?)\s*\.{2,}\s*\d+\s*$"
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


def _body_font_size(blocks: list[PdfBlock]) -> float:
    weighted: Counter[float] = Counter()
    for block in blocks:
        if block.block_type != 0:
            continue
        for size, characters in block.font_size_weights:
            if 5 <= size <= 30:
                weighted[size] += characters
    return weighted.most_common(1)[0][0] if weighted else 10.0


def _text_left(block: PdfBlock) -> float:
    """Measure visible indentation, including spaces embedded in PDF spans."""
    positions = []
    for span in block.spans:
        if span.bbox and span.raw_text.strip():
            leading = len(span.raw_text) - len(span.raw_text.lstrip())
            positions.append(span.bbox[0] + leading / len(span.raw_text) * (span.bbox[2] - span.bbox[0]))
    return min(positions) if positions else block.bbox[0]


def _layout_headings(
    blocks: list[PdfBlock], body_size: float, page_heights: dict[int, float],
) -> dict[tuple[int, int], HeadingMatch]:
    """Recover plain numbered headings using document-wide structural evidence.

    Fonts alone cannot distinguish headings in plain-text PDFs. A contents
    entry can corroborate a title; otherwise require a consistently numbered,
    aligned sequence separated from body text by indentation or extra space.
    Keep the original blocks and spans so evidence locations remain exact.
    """
    contents = set()
    text_blocks = []
    for block in blocks:
        if block.block_type != 0 or not block.bbox or not block.raw_text.strip():
            continue
        entries = [CONTENTS_ENTRY_RE.fullmatch(line) for line in block.raw_text.splitlines()]
        contents.update(
            (entry.group(1).rstrip("."), normalize_text(entry.group(2)).casefold())
            for entry in entries if entry
        )
        if (not any(entries) and block.bbox[1] > page_heights[block.page] * 0.065
                and block.bbox[3] < page_heights[block.page] * 0.93):
            text_blocks.append(block)

    # Long blocks provide a more reliable body margin than short labels,
    # examples, or numbered list items. Bucket near-identical PDF coordinates.
    tolerance = max(body_size * 0.3, 1.0)
    margins: Counter[int] = Counter()
    by_page: dict[int, list[PdfBlock]] = {}
    for block in text_blocks:
        by_page.setdefault(block.page, []).append(block)
        if len(normalize_text(block.raw_text)) >= 100:
            margins[round(_text_left(block) / tolerance)] += len(block.raw_text)
    body_left = margins.most_common(1)[0][0] * tolerance if margins else None
    result = {}
    sequences: dict[tuple[int, float], list[tuple[PdfBlock, HeadingMatch]]] = {}
    for page_blocks in by_page.values():
        page_blocks.sort(key=lambda block: (block.bbox[1], block.bbox[0], block.index))
        for index, block in enumerate(page_blocks):
            clean = normalize_text(block.raw_text)
            number, title = split_section_title(clean)
            lines = [line for line in block.raw_text.splitlines() if line.strip()]
            if (not number or not title or len(clean) > 160 or len(lines) > 2
                    or number.count(".") >= 7 or not any(char.isalpha() for char in title)
                    or title.endswith((".", "!", "?", ";", ":"))
                    or re.search(r"[={}\[\]|;]|\.{2,}", title)
                    or any(split_section_title(line)[0] for line in lines[1:])):
                continue
            match = HeadingMatch(number.count(".") + 1, number, title, "section_number_contents")
            if (number, title.casefold()) in contents:
                result[(block.page, block.index)] = match
                continue
            if body_left is None:
                continue
            before = block.bbox[1] - page_blocks[index - 1].bbox[3] if index else body_size * 2
            after = page_blocks[index + 1].bbox[1] - block.bbox[3] if index + 1 < len(page_blocks) else body_size
            left = _text_left(block)
            outdented = left <= body_left - body_size * 0.75
            spaced = abs(left - body_left) <= tolerance and before >= body_size * 1.5
            if min(before, after) >= body_size * 0.5 and (outdented or spaced):
                key = (round(left / tolerance), round(block.max_size, 1))
                match = HeadingMatch(match.level, number, title, "section_number_layout")
                sequences.setdefault(key, []).append((block, match))
    for sequence in sequences.values():
        numbers = [tuple(int(part) for part in match.section_number.split(".")) for _, match in sequence]
        if len(numbers) >= 2 and numbers == sorted(set(numbers)):
            result.update(((block.page, block.index), match) for block, match in sequence)
    return result


def _heading(
    block: PdfBlock,
    body_size: float,
    page_height: float,
    *,
    entry_level: int = 1,
) -> HeadingMatch | None:
    clean = normalize_text(block.raw_text)
    if not clean or len(clean) > 240 or any(
        CONTENTS_ENTRY_RE.fullmatch(line) for line in block.raw_text.splitlines()
    ):
        return None
    # Running headers and footers often combine a page number with a bold
    # chapter title. They remain content/provenance, never hierarchy.
    if block.bbox[1] <= page_height * 0.065 or block.bbox[3] >= page_height * 0.93:
        return None
    chapter = re.match(r"^Chapter\s+(\d+)\.?\s+(.+)$", clean, re.I)
    if chapter and block.max_size >= body_size * 1.4:
        return HeadingMatch(1, chapter.group(1), chapter.group(2).strip(), "chapter_label")
    number, title = split_section_title(clean)
    if number and title and any(character.isalpha() for character in title):
        level = number.count(".") + 1
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


def _entry_heading_level(heading_stack: dict[int, Node]) -> int:
    """Place repeated unnumbered entries below the active structural heading."""
    for level in sorted(heading_stack, reverse=True):
        if heading_stack[level].metadata.get("heading_basis") == "label_description_entry":
            return level
    return min(max(heading_stack, default=0) + 1, 7)


def _classify_content(block: PdfBlock, previous_label: str, page_height: float) -> tuple[str, dict[str, Any], list[Definition]]:
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
                    rows = table.extract()
                    raw = "\n".join("\t".join(cell or "" for cell in row) for row in rows)
                    tables.append(
                        {
                            "index": table_index,
                            "bbox": tuple(float(value) for value in table.bbox),
                            "rows": rows,
                            "raw_text": raw,
                        }
                    )
            except Exception as exc:  # retain page content even when table inference fails
                stats["pdf_table_detection_errors"] += 1
                stats[f"pdf_table_error_{type(exc).__name__}"] += 1
        table_by_page[page_number] = tables
        stats["pdf_tables_discovered"] += len(tables)

    body_size = _body_font_size(all_blocks)
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
    page_heights = {page["page_number"]: page["height"] for page in pages}
    layout_headings = _layout_headings(all_blocks, body_size, page_heights)
    heading_stack: dict[int, Node] = {}
    previous_label = ""

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
                    metadata={"rows": table["rows"], "pdf_table_index": table["index"]},
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
            ) or layout_headings.get((block.page, block.index))
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
                block, previous_label, page_heights[page_number]
            )
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
