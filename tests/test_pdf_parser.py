from __future__ import annotations

from collections import Counter
from pathlib import Path
import json

import pymupdf as fitz

from spec2lean.database import build_database, connect
from spec2lean.cli import main
from spec2lean.parsers.pdf import (
    PdfBlock,
    _body_font_size,
    _extract_image_block,
    _heading,
    parse_pdf,
)
from spec2lean.util import walk_nodes
from spec2lean.validation import validate_database


def _make_pdf(path):
    document = fitz.open()
    document.set_metadata({"title": "Synthetic PDF ISA"})
    page = document.new_page(width=612, height=792)
    page.insert_text((72, 72), "1 Introduction", fontsize=18, fontname="hebo")
    page.insert_textbox((72, 95, 540, 140), "This is the first exact PDF paragraph.", fontsize=10, fontname="helv")
    page.insert_text((72, 170), "1.1 Syntax", fontsize=14, fontname="hebo")
    page.insert_textbox((72, 190, 540, 230), "add.u32 d, a, b;", fontsize=10, fontname="cour")
    page.insert_textbox((72, 245, 540, 285), "Note: Operands have matching types.", fontsize=10, fontname="helv")

    # A ruled 2x2 table gives PyMuPDF deterministic geometric table signals.
    for x in (72, 180, 300):
        page.draw_line((x, 320), (x, 380))
    for y in (320, 350, 380):
        page.draw_line((72, y), (300, y))
    page.insert_text((80, 340), "Name", fontsize=9)
    page.insert_text((190, 340), "Width", fontsize=9)
    page.insert_text((80, 370), "u32", fontsize=9)
    page.insert_text((190, 370), "32", fontsize=9)

    page2 = document.new_page(width=612, height=792)
    page2.insert_text((72, 72), "2 Operations", fontsize=18, fontname="hebo")
    page2.insert_textbox((72, 95, 540, 145), "See Section 1.1 for syntax.", fontsize=10, fontname="helv")
    page2.insert_textbox((72, 160, 540, 220), "Definition predicate: a one-bit guard.", fontsize=10, fontname="helv")
    document.save(path)
    document.close()


def _make_image_pdf(path):
    document = fitz.open()
    page = document.new_page(width=100, height=100)
    pixmap = fitz.Pixmap(fitz.csGRAY, fitz.IRect(0, 0, 2, 2), False)
    pixmap.clear_with(127)
    page.insert_image(fitz.Rect(10, 20, 30, 40), pixmap=pixmap)
    document.save(path)
    document.close()


def test_pdf_hierarchy_page_bbox_tables_and_validation(tmp_path):
    source = tmp_path / "synthetic.pdf"
    _make_pdf(source)
    parsed = parse_pdf(source)
    nodes = [node for node, _, _, _ in walk_nodes(parsed.root)]
    counts = Counter(node.node_type for node in nodes)
    chapter = next(node for node in nodes if node.section_number == "1")
    syntax = next(node for node in nodes if node.section_number == "1.1")

    assert parsed.page_count == 2
    assert parsed.parser_stats["pdf_pages_indexed"] == 2
    assert syntax in chapter.children
    assert counts["code_block"] + counts["syntax_block"] >= 1
    assert counts["table"] >= 1
    assert any(span.page_number == 1 and span.bbox for node in nodes for span in node.spans)

    database = tmp_path / "pdf.sqlite"
    result = build_database(database, language="synthetic-pdf", version="1.0", documents=[parsed])
    assert len(result["page_text_artifacts"]) == 1
    page_text = Path(result["page_text_artifacts"][0]["path"])
    rendered = page_text.read_text(encoding="utf-8")
    assert "source_sha256: " + parsed.sha256 in rendered
    assert "===== PDF PAGE 1 OF 2 =====" in rendered
    assert "===== PDF PAGE 2 OF 2 =====" in rendered
    assert "This is the first exact PDF paragraph." in rendered
    assert rendered.index("PDF PAGE 1 OF 2") < rendered.index("PDF PAGE 2 OF 2")
    with connect(database, read_only=True) as db:
        report = validate_database(db)
        span = db.execute(
            "SELECT * FROM source_spans WHERE page_number = 1 AND bbox_x0 IS NOT NULL LIMIT 1"
        ).fetchone()
        resolved = db.execute(
            "SELECT count(*) FROM cross_references WHERE resolution_status = 'RESOLVED'"
        ).fetchone()[0]
    assert report["ok"], report["issues"]
    assert span["bbox_x1"] > span["bbox_x0"]
    assert resolved >= 1

    page_text.write_text(rendered + "tampered\n", encoding="utf-8")
    with connect(database, read_only=True) as db:
        stale_report = validate_database(db)
    assert not stale_report["ok"]
    assert any(issue["code"] == "PDF_PAGE_TEXT_MISMATCH" for issue in stale_report["issues"])


def test_cli_build_records_page_text_in_manifest(tmp_path, capsys):
    source = tmp_path / "synthetic.pdf"
    _make_pdf(source)
    database = tmp_path / "index" / "specification.sqlite"

    status = main(
        [
            "index",
            "build",
            "--language",
            "synthetic-pdf",
            "--version",
            "1.0",
            "--pdf",
            str(source),
            "--database",
            str(database),
            "--no-pdf-tables",
        ]
    )
    output = json.loads(capsys.readouterr().out)
    manifest = json.loads((database.parent / "index-manifest.json").read_text(encoding="utf-8"))

    assert status == 0
    assert output["page_text_artifacts"][0]["page_count"] == 2
    page_text = manifest["sources"][0]["page_text"]
    assert page_text["format_version"] == 1
    assert page_text["relative_path"].startswith("text/")
    assert Path(page_text["path"]).is_file()


def _make_furnished_pdf(path):
    """A document with a running header, page numbers, and a contents page.

    All three are what a real specification PDF looks like, and all three used
    to enter the index as ordinary content.
    """
    document = fitz.open()
    document.set_metadata({"title": "Furnished ISA"})

    contents = document.new_page(width=612, height=792)
    contents.insert_text((72, 40), "Furnished ISA, Revision 2.1", fontsize=8, fontname="helv")
    contents.insert_text((72, 120), "Contents", fontsize=18, fontname="hebo")
    contents.insert_text((72, 150), "1 INTRODUCTION ....................................... 2", fontsize=10)
    contents.insert_text((72, 170), "2 OPERATIONS ......................................... 3", fontsize=10)
    contents.insert_text((300, 760), "1", fontsize=9)

    for number, (heading, body) in enumerate(
        [("1 Introduction", "The first real paragraph."),
         ("2 Operations", "The second real paragraph.")],
        start=2,
    ):
        page = document.new_page(width=612, height=792)
        # The running header repeats verbatim; the page number varies.
        page.insert_text((72, 40), "Furnished ISA, Revision 2.1", fontsize=8, fontname="helv")
        page.insert_text((72, 120), heading, fontsize=18, fontname="hebo")
        page.insert_textbox((72, 150, 540, 200), body, fontsize=10, fontname="helv")
        page.insert_text((300, 760), str(number), fontsize=9)

    document.save(path)


def test_running_headers_and_page_numbers_are_typed_as_furniture(tmp_path):
    source = tmp_path / "furnished.pdf"
    _make_furnished_pdf(source)
    parsed = parse_pdf(source)
    by_type = Counter(node.node_type for node, _, _, _ in walk_nodes(parsed.root))

    # The header appears on all three pages and the page number on each.
    assert by_type["page_furniture"] >= 5, by_type

    furniture = [
        node.raw_text.strip()
        for node, _, _, _ in walk_nodes(parsed.root)
        if node.node_type == "page_furniture"
    ]
    assert any("Furnished ISA, Revision 2.1" in text for text in furniture), furniture
    assert any(text in {"1", "2", "3"} for text in furniture), furniture

    # The real body text is untouched.
    paragraphs = [
        node.raw_text.strip()
        for node, _, _, _ in walk_nodes(parsed.root)
        if node.node_type == "paragraph"
    ]
    assert any("The first real paragraph." in text for text in paragraphs), paragraphs
    assert not any("Revision 2.1" in text for text in paragraphs), paragraphs


def test_table_of_contents_lines_never_become_headings(tmp_path):
    source = tmp_path / "furnished.pdf"
    _make_furnished_pdf(source)
    parsed = parse_pdf(source)

    entries = [
        node.raw_text.strip()
        for node, _, _, _ in walk_nodes(parsed.root)
        if node.node_type == "toc_entry"
    ]
    assert len(entries) == 2, entries
    assert all("INTRODUCTION" in text or "OPERATIONS" in text for text in entries)

    # Exactly one heading per real chapter: the contents lines named them
    # without being them, and used to produce a second empty copy of each.
    headings = [
        node.title
        for node, _, _, _ in walk_nodes(parsed.root)
        if node.node_type in {"chapter", "section", "subsection"}
    ]
    assert headings.count("Introduction") == 1, headings
    assert headings.count("Operations") == 1, headings


def test_furniture_detection_needs_repetition_not_just_position(tmp_path):
    """A one-off block in a margin is content, not furniture."""
    source = tmp_path / "single.pdf"
    document = fitz.open()
    page = document.new_page(width=612, height=792)
    page.insert_textbox((72, 40, 540, 70), "A unique note that happens to sit high on the page.", fontsize=10)
    page.insert_text((72, 120), "1 Introduction", fontsize=18, fontname="hebo")
    page.insert_textbox((72, 150, 540, 200), "Body text.", fontsize=10)
    document.save(source)

    parsed = parse_pdf(source)
    texts = {
        node.node_type: node.raw_text
        for node, _, _, _ in walk_nodes(parsed.root)
        if "unique note" in node.raw_text
    }
    assert "page_furniture" not in texts, texts


def test_cover_page_title_lines_are_not_chapters(tmp_path):
    """A cover repeats the title in chapter-sized bold type.

    Style alone cannot tell the two apart, so the rule is conditional: when a
    document numbers its real headings, an unnumbered level-1 heading on page 1
    is cover text.
    """
    source = tmp_path / "covered.pdf"
    document = fitz.open()
    cover = document.new_page(width=612, height=792)
    cover.insert_text((72, 200), "Synthetic ISA", fontsize=24, fontname="hebo")
    cover.insert_text((72, 240), "Transport Specification", fontsize=24, fontname="hebo")
    body = document.new_page(width=612, height=792)
    body.insert_text((72, 100), "1 Introduction", fontsize=18, fontname="hebo")
    body.insert_textbox((72, 130, 540, 180), "Real body text.", fontsize=10)
    document.save(source)

    parsed = parse_pdf(source)
    chapters = [
        node.title
        for node, _, _, _ in walk_nodes(parsed.root)
        if node.node_type == "chapter"
    ]
    assert chapters == ["Introduction"], chapters

    # The cover words are still indexed, just not as hierarchy.
    cover_text = [
        node.raw_text.strip()
        for node, _, _, _ in walk_nodes(parsed.root)
        if node.node_type == "cover_text"
    ]
    assert any("Synthetic ISA" in text for text in cover_text), cover_text


def test_an_unnumbered_document_keeps_its_headings(tmp_path):
    """The rule is conditional for a reason: a document that never numbers its
    headings must keep the ones it has, wherever they are."""
    source = tmp_path / "unnumbered.pdf"
    document = fitz.open()
    page = document.new_page(width=612, height=792)
    page.insert_text((72, 100), "Overview", fontsize=20, fontname="hebo")
    page.insert_textbox((72, 130, 540, 180), "Body text under the overview.", fontsize=10)
    document.save(source)

    parsed = parse_pdf(source)
    headings = [
        node.title
        for node, _, _, _ in walk_nodes(parsed.root)
        if node.node_type in {"chapter", "section", "subsection"}
    ]
    assert "Overview" in headings, headings


def test_merged_cells_do_not_widen_a_table_with_padding():
    """PyMuPDF reports a grid, not a table.

    Merged and spanning cells pad the grid with `None` and split one logical
    column across two, so a register table arrives several times wider than it
    is. Both are recoverable without guessing: a column empty in every row
    carries nothing, and two adjacent columns never occupied in the same row are
    one column split by a merged header.
    """
    from spec2lean.parsers.pdf import _compact_table

    raw = [
        ["", "Start", "", "", "End", "", "", "Name", ""],
        ["00h", None, None, "3Fh", None, None, "PCI Header", None, None],
        ["PMCAP", None, None, "PMCAP+7h", None, None, "PCI Power Management", None, None],
    ]
    rows, dropped = _compact_table(raw)
    assert rows == [
        ["Start", "End", "Name"],
        ["00h", "3Fh", "PCI Header"],
        ["PMCAP", "PMCAP+7h", "PCI Power Management"],
    ], rows
    assert dropped == 6


def test_genuinely_distinct_columns_are_left_alone():
    """Two columns that are ever occupied together are two columns."""
    from spec2lean.parsers.pdf import _compact_table

    rows, dropped = _compact_table(
        [["Bits", "Type"], ["31:16", "RO"], ["15:00", "RW"]]
    )
    assert rows == [["Bits", "Type"], ["31:16", "RO"], ["15:00", "RW"]]
    assert dropped == 0


def test_a_table_of_only_empty_cells_does_not_crash():
    from spec2lean.parsers.pdf import _compact_table

    rows, _ = _compact_table([[None, None], ["", ""]])
    assert all(not any(cell.strip() for cell in row) for row in rows)


def test_chapters_numbered_with_a_trailing_zero_are_chapters():
    """Some specifications number their chapters "1.0", "6.0".

    Reading the dot as depth makes every chapter a section, and leaves the
    document with no chapters at all — which is what happened to CXL 2.0, whose
    fourteen chapters were entirely invisible to planning.
    """
    from spec2lean.parsers.pdf import _canonical_number, _heading_level

    assert _heading_level("1") == 1
    assert _heading_level("1.0") == 1
    assert _heading_level("14.0") == 1
    assert _heading_level("1.1") == 2
    assert _heading_level("9.7.1.1") == 4
    # A trailing zero deeper in the number collapses the same way.
    assert _heading_level("3.2.0") == 2

    # Chapter 6 and chapter 6.0 are the same chapter.
    assert _canonical_number("6.0") == "6"
    assert _canonical_number("6") == "6"
    assert _canonical_number("1.4.1") == "1.4.1"


def test_a_section_number_opens_at_most_one_heading(tmp_path):
    """Compliance-test prose such as "6. Verify: ..." reads as a numbered
    heading. In CXL 2.0 nine such steps each opened a new chapter 6."""
    source = tmp_path / "repeated.pdf"
    document = fitz.open()
    page = document.new_page(width=612, height=792)
    page.insert_text((72, 100), "6.0 Flex Bus Physical Layer", fontsize=18, fontname="hebo")
    page.insert_textbox((72, 140, 540, 190), "The real chapter body.", fontsize=10)
    later = document.new_page(width=612, height=792)
    later.insert_text((72, 100), "6. Verify: Variable Value Condition ID = 0", fontsize=12, fontname="hebo")
    later.insert_textbox((72, 140, 540, 190), "A compliance step.", fontsize=10)
    document.save(source)

    parsed = parse_pdf(source)
    headings = [
        (node.section_number, node.title)
        for node, _, _, _ in walk_nodes(parsed.root)
        if node.node_type in {"chapter", "section", "subsection"}
    ]
    assert headings == [("6.0", "Flex Bus Physical Layer")], headings
    # The compliance step is still indexed, just not as hierarchy.
    assert any(
        "Verify: Variable Value Condition" in node.raw_text
        for node, _, _, _ in walk_nodes(parsed.root)
    )
def test_pdf_images_use_displayed_image_inventory_deterministically(tmp_path):
    source = tmp_path / "image.pdf"
    _make_image_pdf(source)

    parsed = parse_pdf(source, detect_tables=False)
    repeated = parse_pdf(source, detect_tables=False)
    image_nodes = [
        node for node, _, _, _ in walk_nodes(parsed.root) if node.node_type == "generic"
    ]
    repeated_images = [
        node for node, _, _, _ in walk_nodes(repeated.root) if node.node_type == "generic"
    ]

    assert len(image_nodes) == 1
    assert image_nodes[0].source_key == "page:1:image:0"
    assert image_nodes[0].spans[0].bbox == (10.0, 20.0, 30.0, 40.0)
    assert image_nodes[0].metadata["bbox_source"] == "get_image_info"
    assert image_nodes[0].source_key == repeated_images[0].source_key
    assert image_nodes[0].spans[0].bbox == repeated_images[0].spans[0].bbox
    assert image_nodes[0].metadata == repeated_images[0].metadata

    database = tmp_path / "image.sqlite"
    build_database(database, language="synthetic-pdf", version="1.0", documents=[parsed])
    with connect(database, read_only=True) as db:
        report = validate_database(db)
    assert report["ok"], report["issues"]


def test_pdf_invalid_image_bbox_uses_transform_fallback():
    block = _extract_image_block(
        page_number=836,
        image_index=0,
        image={
            "number": 12,
            "bbox": (153, 594, 56.875, -507.25),
            "transform": (0.96, 0, 0, 0.96, 153, 594),
            "width": 8,
            "height": 8,
            "colorspace": 0,
            "bpc": 1,
        },
        page_width=612,
        page_height=792,
    )

    assert block.bbox == (153.0, 594.0, 153.96, 594.96)
    assert block.metadata["bbox_source"] == "transform_fallback"
    assert block.metadata["invalid_reported_bbox"] == (
        153.0,
        594.0,
        56.875,
        -507.25,
    )


def test_pdf_unrecoverable_image_bbox_is_omitted():
    block = _extract_image_block(
        page_number=1,
        image_index=0,
        image={
            "bbox": (-20, 10, -5, 20),
            "transform": (10, 0, 0, 10, -20, 10),
        },
        page_width=100,
        page_height=100,
    )

    assert block.bbox is None
    assert block.metadata["bbox_source"] == "unavailable"


def test_pdf_entry_title_uses_document_typography_not_instruction_names():
    title = "OPX—Operation X"
    entry = PdfBlock(
        page=4,
        index=2,
        bbox=(46, 80, 220, 96),
        raw_text=title,
        max_size=12,
        bold_ratio=0,
        mono_ratio=0,
        font_size_weights=((12, len(title)),),
        emphasis_ratio=1,
    )
    match = _heading(entry, body_size=9, page_height=792, entry_level=3)

    assert match is not None
    assert match.level == 3
    assert match.title == title
    assert match.basis == "label_description_entry"


def test_pdf_entry_title_rule_does_not_promote_body_prose():
    prose = "The result—after rounding—is written to the destination."
    block = PdfBlock(
        page=4,
        index=3,
        bbox=(46, 120, 500, 132),
        raw_text=prose,
        max_size=9,
        bold_ratio=0,
        mono_ratio=0,
        font_size_weights=((9, len(prose)),),
    )

    assert _heading(block, body_size=9, page_height=792, entry_level=3) is None


def test_pdf_numbered_bit_labels_are_not_sections():
    bit_labels = "15 14 13 12 11 10 9 8 7 6 5 4 3 2 1 0"
    block = PdfBlock(
        page=4,
        index=4,
        bbox=(46, 120, 500, 136),
        raw_text=bit_labels,
        max_size=14,
        bold_ratio=0,
        mono_ratio=0,
        font_size_weights=((14, len(bit_labels)),),
        emphasis_ratio=1,
    )

    assert _heading(block, body_size=9, page_height=792, entry_level=3) is None


def test_pdf_body_font_baseline_uses_font_points():
    body = PdfBlock(
        page=1,
        index=1,
        bbox=(46, 100, 500, 114),
        raw_text="body text" * 20,
        max_size=9,
        bold_ratio=0,
        mono_ratio=0,
        font_size_weights=((9, 180),),
    )
    heading = PdfBlock(
        page=1,
        index=0,
        bbox=(46, 70, 200, 86),
        raw_text="ENTRY—Description",
        max_size=12,
        bold_ratio=0,
        mono_ratio=0,
        font_size_weights=((12, 17),),
        emphasis_ratio=1,
    )

    assert _body_font_size([heading, body]) == 9
