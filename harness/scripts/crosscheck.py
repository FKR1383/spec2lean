#!/usr/bin/env python3
"""Cross-check the Rust phases against the Python implementation.

Builds one Phase-1 index, runs the same scripted tool sequences through both
implementations, and diffs the resulting artifacts.

Phase 2 plans must be byte-identical: the plan is what every later phase keys
off, and its unit IDs, shared dependency IDs, and processing layers are all
derived, so a match proves the derivation agrees.

Phase 3 bundles must be byte-identical, including every `evidenceId` — those are
SHA-256 digests over the canonical JSON identity, so a match proves that text
normalisation, canonical JSON, the stable-ID construction, provenance
reconstruction, and the record layout all agree between the two languages.

Phase 4 artifacts must match except for the `extractor` block, which is a
deliberate divergence: the Python implementation hardcoded
`provider: "opencode"`, while the Rust one records the provider and model that
actually ran. Everything else, including the `runId` and `evidenceBundleHash`,
must agree.

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
                    "name": "predicate",
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

        # ---- Phase 2 -------------------------------------------------------
        # Both implementations resolve the same request and validate the same
        # planner submission; the resulting plans must be identical.
        from spec2lean.database import connect as _connect
        from spec2lean.planning.models import PlanningRequest
        from spec2lean.planning.scope import Phase1Query, ScopeResolver
        from spec2lean.planning.validation import build_validated_plan

        py_request = PlanningRequest.full("synthetic", "1.0")
        with _connect(database, read_only=True) as connection:
            py_scope = ScopeResolver(connection).resolve(py_request)
            planner_units = [item["unitId"] for item in py_scope.candidate_units]
            planner_submission = {
                "requestedUnitIds": planner_units,
                "translationGroups": [
                    {
                        "name": "Whole",
                        "unitIds": planner_units,
                        "reason": "the fixture specification has a single chapter",
                        "supportingNodeIds": sorted(
                            {
                                node
                                for unit in py_scope.candidate_units
                                for node in unit["sourceNodeIds"]
                            }
                        ),
                        "origin": "EXPLICIT",
                    }
                ],
                "externalPrerequisites": [],
                "sharedPrerequisites": [],
                "dependencies": [],
            }
            python_plan = build_validated_plan(
                Phase1Query(connection),
                py_scope,
                planner_submission,
                language="synthetic",
                version="1.0",
                plan_run_id="plan:crosscheck",
                source_database_digest=digest,
            )

        (work / "planner-calls.json").write_text(
            json.dumps([{"tool": "submit_plan", "input": planner_submission}], indent=2)
        )
        completed = subprocess.run(
            [
                str(BINARY), "plan", "replay",
                "--database", str(database),
                "--language", "synthetic", "--version", "1.0", "--full",
                "--plan-run-id", "plan:crosscheck",
                "--calls", str(work / "planner-calls.json"),
                "--out", str(work / "rust-plan"),
            ],
            capture_output=True, text=True, check=False,
        )
        if completed.returncode != 0:
            print(completed.stdout)
            print(completed.stderr, file=sys.stderr)
            return 1
        rust_plan = json.loads((work / "rust-plan" / "plan.json").read_text())
        if python_plan != rust_plan:
            print("PHASE 2 PLANS DIFFER", file=sys.stderr)
            print(json.dumps({"python": python_plan, "rust": rust_plan}, indent=2, sort_keys=True))
            return 1
        print(
            f"phase 2: plans are identical "
            f"({len(rust_plan['requestedUnits'])} unit(s), "
            f"{len(rust_plan['translationGroups'])} group(s), "
            f"{rust_plan['graphStatus']})"
        )
        for unit in rust_plan["requestedUnits"]:
            print(f"  {unit['unitId']}  {unit['name']}")

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

        if python != rust:
            print("PHASE 3 BUNDLES DIFFER", file=sys.stderr)
            print(json.dumps({"python": python, "rust": rust}, indent=2, sort_keys=True))
            return 1
        print(f"phase 3: bundles are identical ({len(rust['evidence'])} evidence items)")
        for item in rust["evidence"]:
            print(f"  {item['tier']:<10} {item['role']:<24} {item['evidenceId']}")

        # ---- Phase 4 -------------------------------------------------------
        bundle_path = work / "rust" / "evidence-bundle.json"
        created_at = "2026-01-01T00:00:00.000000Z"
        submission = {
            "outcome": "SUCCESS",
            "unitKind": "LANGUAGE_CONSTRUCT",
            "identity": {"name": "add", "evidenceIds": [rust["evidence"][0]["evidenceId"]]},
            "syntaxForms": [
                {
                    "form": "add.type d, a, b;",
                    "evidenceIds": [rust["evidence"][0]["evidenceId"]],
                }
            ],
            # A `result` is included only so both implementations accept the
            # same submission. The Rust validator treats it as optional for a
            # non-instruction unit; the Python one requires it unconditionally,
            # which is the known divergence documented in harness/README.md.
            "result": {
                "name": "d",
                "description": "the destination operand",
                "constraints": ["named by the syntax form"],
                "evidenceIds": [rust["evidence"][0]["evidenceId"]],
            },
            "dependencies": [
                {
                    "dependencyId": "shared:predicate",
                    "concept": "predicate",
                    "description": "a one-bit value used to guard execution",
                    "semanticClaimIds": ["claim:2"],
                    "evidenceIds": [],
                }
            ],
            "claims": [
                {
                    "claimId": "claim:1",
                    "kind": "SOURCE_FACT",
                    "statement": "add takes a destination and two source operands",
                    "evidenceIds": [rust["evidence"][0]["evidenceId"]],
                },
                {
                    "claimId": "claim:2",
                    "kind": "DERIVED_INTERPRETATION",
                    "statement": "execution of add may be guarded by a predicate",
                    "evidenceIds": [rust["evidence"][1]["evidenceId"]],
                },
            ],
        }
        semantic_calls = [
            {"tool": "get_evidence", "input": {}},
            {"tool": "submit_semantics", "input": submission},
        ]
        (work / "semantic-calls.json").write_text(json.dumps(semantic_calls, indent=2))

        completed = subprocess.run(
            [
                str(BINARY), "semantics", "replay",
                "--plan", str(work / "plan.json"),
                "--bundle", str(bundle_path),
                "--unit", "unit:add",
                "--created-at", created_at,
                "--calls", str(work / "semantic-calls.json"),
                "--out", str(work / "rust-semantics"),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            print(completed.stdout)
            print(completed.stderr, file=sys.stderr)
            return 1
        rust_artifact = json.loads(
            (work / "rust-semantics" / "semantic-artifact.json").read_text()
        )

        from spec2lean.semantics.models import SemanticScope
        from spec2lean.semantics.validation import validate_submission as validate_semantics

        semantic_scope = SemanticScope.from_inputs(
            plan, rust, "unit:add", created_at=created_at
        )
        python_artifact, semantic_diagnostics = validate_semantics(
            semantic_scope, rust, submission
        )
        if semantic_diagnostics:
            print("python extractor rejected the submission:", file=sys.stderr)
            print(json.dumps(semantic_diagnostics, indent=2), file=sys.stderr)
            return 1

    # The extractor block is an intentional divergence; normalise it away.
    for artifact in (python_artifact, rust_artifact):
        artifact["extractor"] = "<normalised>"

    if python_artifact != rust_artifact:
        print("PHASE 4 ARTIFACTS DIFFER", file=sys.stderr)
        print(
            json.dumps(
                {"python": python_artifact, "rust": rust_artifact}, indent=2, sort_keys=True
            )
        )
        return 1

    claims = rust_artifact["semantics"]["claims"]
    print(f"phase 4: artifacts are identical ({len(claims)} claims)")
    print(f"  runId  {rust_artifact['runId']}")
    print(f"  bundle {rust_artifact['evidenceBundleHash']}")
    for claim in claims:
        print(f"  {claim['kind']:<24} {claim['claimId']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
