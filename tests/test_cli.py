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


def _run_plan(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(CLI), "plan", *args],
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


def test_plan_inspection_commands_and_dot_export(tmp_path):
    plans_root = tmp_path / "plans"
    run_id = "plan:test-cli"
    run = plans_root / "synthetic" / "1.0" / run_id
    run.mkdir(parents=True)
    plan = {
        "schemaVersion": 2,
        "language": "synthetic",
        "version": "1.0",
        "planRunId": run_id,
        "sourceDatabaseDigest": "a" * 64,
        "request": {"scope": {"mode": "EXACT_INSTRUCTIONS"}},
        "requestedUnits": [
            {"unitId": "unit:a", "name": "alpha.u32", "sourceNodeIds": ["node:a"]},
            {"unitId": "unit:b", "name": "beta.u32", "sourceNodeIds": ["node:b"]},
        ],
        "translationGroups": [{
            "name": "InstructionSemantics",
            "unitIds": ["unit:a", "unit:b"],
            "reason": "The indexed synthetic source presents one instruction family.",
            "supportingNodeIds": ["node:a", "node:b"],
            "origin": "INFERRED",
        }],
        "externalPrerequisites": [],
        "dependencies": [{
            "from": "unit:a", "to": "unit:b", "reason": "alpha first",
            "supportingNodeIds": ["node:a"], "origin": "INFERRED",
        }],
        "processingLayers": [
            {"layer": 0, "unitIds": ["unit:a"]},
            {"layer": 1, "unitIds": ["unit:b"]},
        ],
        "cycles": [],
        "graphStatus": "ACYCLIC",
    }
    (run / "plan.json").write_text(json.dumps(plan))
    common = ("--run", run_id, "--plans-root", str(plans_root))
    for command in ("show", "units", "groups", "deps", "layers", "prerequisites"):
        result = _run_plan(command, *common)
        assert result.returncode == 0, (command, result.stderr)
        json.loads(result.stdout)
    output = tmp_path / "plan.dot"
    result = _run_plan("graph", *common, "--format", "dot", "--output", str(output))
    assert result.returncode == 0, result.stderr
    assert '"unit:a" -> "unit:b"' in output.read_text()
