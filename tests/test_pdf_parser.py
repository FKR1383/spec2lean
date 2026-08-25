from __future__ import annotations

from collections import Counter

import pymupdf as fitz

from spec2lean.database import build_database, connect
from spec2lean.parsers.pdf import parse_pdf
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
    build_database(database, language="synthetic-pdf", version="1.0", documents=[parsed])
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
