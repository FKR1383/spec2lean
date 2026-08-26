from __future__ import annotations

import shutil

from spec2lean.database import build_database, connect, semantic_digest
from spec2lean.parsers.html import parse_html
from spec2lean.validation import statistics, validate_database


def test_parent_depth_order_subtree_search_and_cross_references(html_database):
    with connect(html_database, read_only=True) as db:
        rows = db.execute("SELECT * FROM nodes ORDER BY depth, ordinal").fetchall()
        by_id = {row["node_id"]: row for row in rows}
        for row in rows:
            if row["parent_id"]:
                assert row["depth"] == by_id[row["parent_id"]]["depth"] + 1

        syntax = db.execute("SELECT * FROM nodes WHERE html_anchor = 'syntax'").fetchone()
        subtree = db.execute(
            """WITH RECURSIVE tree(node_id) AS (
                   SELECT node_id FROM nodes WHERE node_id = ?
                   UNION ALL SELECT n.node_id FROM nodes n JOIN tree t ON n.parent_id = t.node_id
               ) SELECT node_id FROM tree""",
            (syntax["node_id"],),
        ).fetchall()
        assert len(subtree) >= 6

        hits = db.execute(
            """SELECT n.node_type FROM nodes_fts f JOIN nodes n ON n.node_id = f.node_id
               WHERE nodes_fts MATCH 'add'"""
        ).fetchall()
        assert any(hit["node_type"] == "syntax_block" for hit in hits)

        statuses = {row[0] for row in db.execute("SELECT resolution_status FROM cross_references")}
        assert "RESOLVED" in statuses
        assert "UNRESOLVED" in statuses


def test_validation_and_statistics(html_database):
    with connect(html_database, read_only=True) as db:
        report = validate_database(db)
        stats = statistics(db)
    assert report["ok"], report["issues"]
    assert stats["totals"]["documents"] == 1
    assert stats["node_types"]["table"] == 1
    assert stats["totals"]["definitions"] == 1


def test_sha_invalidation_is_detected(tmp_path, html_source):
    copied = tmp_path / "copy.html"
    shutil.copyfile(html_source, copied)
    database = tmp_path / "stale.sqlite"
    build_database(database, language="synthetic", version="1.0", documents=[parse_html(copied)])
    copied.write_text(copied.read_text() + "\n<!-- changed -->\n")
    with connect(database, read_only=True) as db:
        report = validate_database(db)
    assert not report["ok"]
    assert any(issue["code"] == "STALE_SOURCE_SHA" for issue in report["issues"])


def test_rebuild_has_identical_semantic_digest(tmp_path, html_source):
    first = tmp_path / "first.sqlite"
    second = tmp_path / "second.sqlite"
    one = build_database(first, language="synthetic", version="1.0", documents=[parse_html(html_source)])
    two = build_database(second, language="synthetic", version="1.0", documents=[parse_html(html_source)])
    assert one["page_text_artifacts"] == []
    assert two["page_text_artifacts"] == []
    assert one["semantic_digest"] == two["semantic_digest"]
    with connect(first, read_only=True) as a, connect(second, read_only=True) as b:
        assert semantic_digest(a) == semantic_digest(b)
