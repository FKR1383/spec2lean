from __future__ import annotations

from collections import Counter
from pathlib import Path
import json

import pymupdf as fitz

from spec2lean.database import build_database, connect
from spec2lean.cli import main
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
