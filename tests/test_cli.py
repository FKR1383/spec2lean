from __future__ import annotations

import json
import subprocess
from pathlib import Path

from spec2lean.database import connect


CLI = Path(__file__).resolve().parents[1] / "spec2lean"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(CLI), "index", *args],
        text=True,
        capture_output=True,
        check=False,
    )


def test_inspection_commands_cover_hierarchy_provenance_and_export(html_database, tmp_path):
    database = str(html_database)
    with connect(html_database, read_only=True) as db:
        syntax = db.execute("SELECT node_id FROM nodes WHERE html_anchor = 'syntax'").fetchone()[0]
        paragraph = db.execute("SELECT node_id FROM nodes WHERE html_anchor = 'overview'").fetchone()[0]

    commands = [
        ("stats", "--database", database),
        ("tree", "--database", database),
        ("show", "--database", database, "--node", paragraph),
        ("children", "--database", database, "--node", syntax),
        ("ancestors", "--database", database, "--node", paragraph),
        ("subtree", "--database", database, "--node", syntax, "--all-nodes"),
        ("search", "--database", database, "--query", "add"),
        ("definitions", "--database", database, "--query", "predicate"),
        ("xrefs", "--database", database, "--status", "UNRESOLVED"),
        ("validate", "--database", database),
    ]
    for command in commands:
        result = _run(*command)
        assert result.returncode == 0, (command, result.stderr, result.stdout)
        assert result.stdout.strip()

    shown = json.loads(_run("show", "--database", database, "--node", paragraph).stdout)
    assert shown["raw_text"].startswith("This paragraph")
    assert shown["html_anchor"] == "overview"
    assert shown["source_spans"][0]["dom_path"]

    output = tmp_path / "dump.json"
    dumped = _run("dump", "--database", database, "--format", "json", "--output", str(output))
    assert dumped.returncode == 0, dumped.stderr
    data = json.loads(output.read_text())
    assert data["nodes"]
    assert "created_at" not in data["documents"][0]

