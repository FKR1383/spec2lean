#!/usr/bin/env python3
"""Cross-check the Rust evidence phase against the Python implementation.

Builds one Phase-1 index, runs the same scripted tool sequence through both
implementations, and diffs the resulting evidence bundles. The bundles must be
identical, including every `evidenceId` — those are SHA-256 digests over the
canonical JSON identity, so a match proves that text normalisation, canonical
JSON, the stable-ID construction, provenance reconstruction, and the record
layout all agree between the two languages.

Usage:  .venv/bin/python harness/scripts/crosscheck.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BINARY = REPO / "harness" / "target" / "debug" / "s2l"

def build_index(target: Path) -> None:
    from spec2lean.database import build_database
    from spec2lean.parsers.html import parse_html

    build_database(
        target,
        language="synthetic",
        version="1.0",
        documents=[
            parse_html(
                REPO / "tests" / "fixtures" / "specification.html",
                "https://example.test/spec",
            )
        ],
    )


def discover(database: Path) -> tuple[str, str, str, str]:
    """Pick the section unit, a child to select, and the definition node."""
    from spec2lean.database import connect

    with connect(database, read_only=True) as connection:
        digest = connection.execute(
            "SELECT semantic_digest FROM builds WHERE status = 'COMPLETE'"
        ).fetchone()[0]
        section = connection.execute(
            "SELECT node_id FROM nodes WHERE node_type = 'section' ORDER BY ordinal LIMIT 1"
        ).fetchone()[0]
        syntax = connection.execute(
            "SELECT node_id FROM nodes WHERE node_type = 'syntax_block' LIMIT 1"
        ).fetchone()[0]
        definition = connection.execute(
            "SELECT node_id FROM nodes WHERE node_type = 'definition' LIMIT 1"
        ).fetchone()[0]
    return digest, section, syntax, definition


def main() -> int:
    if not BINARY.is_file():
        print(f"build the harness first: cargo build --manifest-path {REPO}/harness/Cargo.toml")
        return 2

    with tempfile.TemporaryDirectory(prefix="spec2lean-crosscheck-") as name:
        work = Path(name)
        database = work / "spec.sqlite"
        build_index(database)
        digest, section, syntax, definition = discover(database)

        plan = {
            "schemaVersion": 1,
            "planRunId": "plan:crosscheck",
            "language": "synthetic",
            "version": "1.0",
            "sourceDatabaseDigest": digest,
            "requestedUnits": [
                {"unitId": "unit:add", "name": "add", "sourceNodeIds": [section]}
            ],
            "externalPrerequisites": [],
            "sharedPrerequisites": [
                {
                    "dependencyId": "shared:predicate",
                    "requiredBy": ["unit:add"],
                    "sourceNodeIds": [definition],
                }
            ],
            "dependencies": [],
        }
        submission = {
            "unitId": "unit:add",
            "selections": [
                {
                    "sourceNodeIds": [syntax],
                    "role": "SYNTAX",
                    "tier": "CORE",
                    "rationale": "the instruction syntax form",
                },
                {
                    "sourceNodeIds": [definition],
                    "role": "SUPPORTING_DEFINITION",
                    "tier": "SUPPORTING",
                    "rationale": "defines predicate used by the unit",
                },
            ],
        }
        calls = [
            {"tool": "spec_children", "input": {"nodeId": section}},
            {"tool": "spec_show", "input": {"nodeId": syntax}},
            {"tool": "spec_definitions", "input": {"query": "predicate"}},
            {"tool": "submit_evidence", "input": submission},
        ]

        (work / "plan.json").write_text(json.dumps(plan, indent=2))
        (work / "calls.json").write_text(json.dumps(calls, indent=2))

        completed = subprocess.run(
            [
                str(BINARY), "evidence", "replay",
                "--database", str(database),
                "--plan", str(work / "plan.json"),
                "--unit", "unit:add",
                "--calls", str(work / "calls.json"),
                "--out", str(work / "rust"),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            print(completed.stdout)
            print(completed.stderr, file=sys.stderr)
            return 1
        rust = json.loads((work / "rust" / "evidence-bundle.json").read_text())

        # The Python side: same index, same scope, same tool sequence.
        from spec2lean.database import connect
        from spec2lean.evidence.models import EvidenceScope
        from spec2lean.evidence.query import EvidenceQuery, SessionQuery
        from spec2lean.evidence.validation import validate_submission

        scope = EvidenceScope.from_plan(plan, "unit:add")
        with connect(database, read_only=True) as connection:
            query = EvidenceQuery(connection)
            session = SessionQuery(query, scope)
            session.children(section, limit=20)
            session.show(syntax)
            session.definitions("predicate", limit=20)
            python, diagnostics = validate_submission(
                query, scope, session.ledger, submission
            )
        if diagnostics:
            print("python validator rejected the submission:", diagnostics, file=sys.stderr)
            return 1

    if python == rust:
        print(f"bundles are identical ({len(rust['evidence'])} evidence items)")
        for item in rust["evidence"]:
            print(f"  {item['tier']:<10} {item['role']:<24} {item['evidenceId']}")
        return 0

    print("BUNDLES DIFFER", file=sys.stderr)
    print(json.dumps({"python": python, "rust": rust}, indent=2, sort_keys=True))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
