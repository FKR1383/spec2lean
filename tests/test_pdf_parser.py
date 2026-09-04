from __future__ import annotations

from collections import Counter
from pathlib import Path
import json

import pymupdf as fitz

from spec2lean.database import build_database, connect
from spec2lean.cli import main
from spec2lean.parsers.pdf import PdfBlock, _body_font_size, _heading, parse_pdf
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
