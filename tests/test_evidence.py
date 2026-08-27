from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pymupdf as fitz
import pytest

from spec2lean.database import build_database, connect
from spec2lean.cli import main
from spec2lean.evidence.mcp import EvidenceMcpServer, tool_definitions
from spec2lean.evidence.models import EvidenceScope
from spec2lean.evidence.query import EvidenceQuery, SessionQuery
from spec2lean.evidence.render import render_markdown
from spec2lean.evidence.runner import (
    RETRIEVER_MODEL,
    RETRIEVER_REASONING,
    build_evidence,
    opencode_config,
)
from spec2lean.evidence.validation import validate_bundle, validate_submission
from spec2lean.parsers.pdf import parse_pdf
from spec2lean.planning.models import PlanningRequest
from spec2lean.planning.scope import Phase1Query, ScopeResolver
from spec2lean.planning.validation import build_validated_plan


def _plan(planner_database: Path, names: list[str], *, shared_prerequisite: bool = False):
    with connect(planner_database, read_only=True) as connection:
        scope = ScopeResolver(connection).resolve(PlanningRequest.exact("synthetic", "1.0", names))
        submission = {
            "requestedUnitIds": [item["unitId"] for item in scope.candidate_units],
            "externalPrerequisites": [],
            "dependencies": [],
        }
        if shared_prerequisite:
            rules = connection.execute(
                "SELECT node_id FROM nodes WHERE html_anchor = 'integer-operand-rules'"
            ).fetchone()[0]
            submission["externalPrerequisites"] = [{
                "key": "integer-rules",
                "name": "Integer operand rules",
                "reason": "The requested units use integer operands.",
                "sourceNodeIds": [rules],
            }]
            submission["dependencies"] = [{
                "from": "integer-rules",
                "to": unit["unitId"],
                "reason": "Integer rules are shared supporting context.",
                "supportingNodeIds": [rules],
                "origin": "EXPLICIT",
            } for unit in scope.candidate_units]
        return build_validated_plan(
            Phase1Query(connection), scope, submission,
            language="synthetic", version="1.0", plan_run_id="plan:evidence-test",
            source_database_digest=EvidenceQuery(connection).source_database_digest(),
        )


def _selection(node_ids, *, role="OPERATION", tier="CORE", rationale="Relevant exact source.", spans=None):
    value = {
        "sourceNodeIds": list(node_ids),
        "role": role,
        "tier": tier,
        "rationale": rationale,
    }
    if spans is not None:
        value["sourceSpanIds"] = list(spans)
    return value


def _session_for(connection, plan, unit_id):
    scope = EvidenceScope.from_plan(plan, unit_id)
    query = EvidenceQuery(connection)
    return scope, query, SessionQuery(query, scope)


def test_valid_html_bundle_reconstructs_exact_text_provenance_and_rendering(planner_database):
    plan = _plan(planner_database, ["alpha.u32"])
    unit_id = plan["requestedUnits"][0]["unitId"]
    with connect(planner_database, read_only=True) as connection:
        scope, query, session = _session_for(connection, plan, unit_id)
        root = scope.unit["sourceNodeIds"][0]
        nodes = session.subtree(root, max_depth=1, limit=20)
        syntax = next(item for item in nodes if item["nodeType"] == "syntax_block")
        paragraph = next(item for item in nodes if item["nodeType"] == "paragraph")
        submission = {
            "unitId": unit_id,
            "selections": [_selection(
                [syntax["nodeId"], paragraph["nodeId"]], role="SYNTAX",
                rationale="The adjacent syntax and source description are core evidence.",
            )],
        }
        bundle, diagnostics = validate_submission(query, scope, session.ledger, submission)
        assert diagnostics == []
        assert bundle is not None
        item = bundle["evidence"][0]
        expected = connection.execute(
            "SELECT raw_text FROM nodes WHERE node_id IN (?, ?) ORDER BY ordinal",
            (syntax["nodeId"], paragraph["nodeId"]),
        ).fetchall()
        assert item["exactText"] == "\n".join(row[0] for row in expected)
        assert item["sourceType"] == "html"
        assert item["htmlAnchor"] == "instruction-alpha"
        assert item["documentSha256"]
        assert item["provenance"][0]["sourceSpans"][0]["domPath"]
        assert validate_bundle(query, plan, bundle, exposed_node_ids=session.ledger.nodes) == []
        assert render_markdown(bundle) == render_markdown(json.loads(json.dumps(bundle)))
        assert "Exact text:" in render_markdown(bundle)

        repeated, repeated_diagnostics = validate_submission(query, scope, session.ledger, submission)
        assert repeated_diagnostics == []
        assert repeated["evidence"][0]["evidenceId"] == item["evidenceId"]


def test_bundle_validator_detects_exact_text_sha_html_and_unit_tampering(planner_database):
    plan = _plan(planner_database, ["alpha.u32"])
    unit_id = plan["requestedUnits"][0]["unitId"]
    with connect(planner_database, read_only=True) as connection:
        scope, query, session = _session_for(connection, plan, unit_id)
        bundle, diagnostics = validate_submission(query, scope, session.ledger, {
            "unitId": unit_id,
            "selections": [_selection(scope.unit["sourceNodeIds"], role="OTHER")],
        })
        assert diagnostics == [] and bundle is not None
        mutations = (
            ("exactText", "paraphrased", "EXACT_TEXT_MISMATCH"),
            ("documentSha256", "0" * 64, "DOCUMENT_SHA_MISMATCH"),
            ("htmlAnchor", "invented", "HTML_PROVENANCE_MISMATCH"),
        )
        for field, value, code in mutations:
            changed = json.loads(json.dumps(bundle))
            changed["evidence"][0][field] = value
            assert code in {item["code"] for item in validate_bundle(query, plan, changed)}
        changed = json.loads(json.dumps(bundle))
        changed["unit"]["unitId"] = "unit:wrong"
        assert {item["code"] for item in validate_bundle(query, plan, changed)} == {"WRONG_UNIT"}
        changed = json.loads(json.dumps(bundle))
        changed["evidence"][0]["semanticClaim"] = "therefore Lean should..."
        assert "UNEXPECTED_FIELD" in {item["code"] for item in validate_bundle(query, plan, changed)}


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        ("nonexistent", "INVENTED_SOURCE_NODE"),
        ("not_exposed", "NODE_NOT_EXPOSED"),
        ("wrong_unit", "WRONG_UNIT"),
        ("invalid_role", "INVALID_ROLE"),
        ("invalid_tier", "INVALID_TIER"),
        ("duplicate", "DUPLICATE_EVIDENCE"),
    ],
)
def test_submission_rejects_invalid_or_out_of_session_choices(planner_database, kind, expected):
    plan = _plan(planner_database, ["alpha.u32", "beta.u32"])
    unit_id = plan["requestedUnits"][0]["unitId"]
    with connect(planner_database, read_only=True) as connection:
        scope, query, session = _session_for(connection, plan, unit_id)
        valid = _selection(scope.unit["sourceNodeIds"], role="OTHER")
        submission = {"unitId": unit_id, "selections": [valid]}
        if kind == "nonexistent":
            submission["selections"][0]["sourceNodeIds"] = ["node:invented"]
        elif kind == "not_exposed":
            other = plan["requestedUnits"][1]["sourceNodeIds"][0]
            submission["selections"][0]["sourceNodeIds"] = [other]
        elif kind == "wrong_unit":
            submission["unitId"] = plan["requestedUnits"][1]["unitId"]
        elif kind == "invalid_role":
            submission["selections"][0]["role"] = "SEMANTIC_CLAIM"
        elif kind == "invalid_tier":
            submission["selections"][0]["tier"] = "CONTEXT"
        else:
            submission["selections"].append(dict(valid, role="SYNTAX"))
        _, diagnostics = validate_submission(query, scope, session.ledger, submission)
        assert expected in {item["code"] for item in diagnostics}


def test_span_selection_must_be_exposed_and_is_reconstructed(planner_database):
    plan = _plan(planner_database, ["alpha.u32"])
    unit_id = plan["requestedUnits"][0]["unitId"]
    with connect(planner_database, read_only=True) as connection:
        scope, query, session = _session_for(connection, plan, unit_id)
        details = query.show(scope.unit["sourceNodeIds"][0])
        span = details["sourceSpans"][0]
        bundle, diagnostics = validate_submission(query, scope, session.ledger, {
            "unitId": unit_id,
            "selections": [_selection(
                scope.unit["sourceNodeIds"], role="OTHER", spans=[span["spanId"]]
            )],
        })
        assert diagnostics == []
        assert bundle["evidence"][0]["exactText"] == span["exactText"]
        _, bad = validate_submission(query, scope, session.ledger, {
            "unitId": unit_id,
            "selections": [_selection(
                scope.unit["sourceNodeIds"], role="OTHER", spans=["span:invented"]
            )],
        })
        assert {item["code"] for item in bad} >= {"SPAN_NOT_EXPOSED", "INVENTED_SOURCE_SPAN"}


def test_shared_supporting_source_has_stable_cross_bundle_evidence_id(planner_database):
    plan = _plan(planner_database, ["alpha.u32", "beta.u32"], shared_prerequisite=True)
    identifiers = []
    with connect(planner_database, read_only=True) as connection:
        query = EvidenceQuery(connection)
        for unit in plan["requestedUnits"]:
            scope = EvidenceScope.from_plan(plan, unit["unitId"])
            session = SessionQuery(query, scope)
            prerequisite_node = scope.prerequisites[0]["sourceNodeIds"][0]
            bundle, diagnostics = validate_submission(query, scope, session.ledger, {
                "unitId": unit["unitId"],
                "selections": [
                    _selection(scope.unit["sourceNodeIds"], role="OTHER"),
                    _selection(
                        [prerequisite_node], role="SUPPORTING_DEFINITION", tier="SUPPORTING",
                        rationale="Shared integer operand definition.",
                    ),
                ],
            })
            assert diagnostics == []
            identifiers.append(next(item["evidenceId"] for item in bundle["evidence"] if item["tier"] == "SUPPORTING"))
    assert identifiers[0] == identifiers[1]


def _make_evidence_pdf(path: Path) -> None:
    document = fitz.open()
    page = document.new_page(width=612, height=792)
    page.insert_text((72, 100), "1 Add instruction", fontsize=18, fontname="hebo")
    page.insert_textbox((72, 130, 540, 170), "add.u32 d, a, b;", fontsize=10, fontname="cour")
    page.insert_textbox((72, 190, 540, 230), "The operation adds two operands.", fontsize=10)
    document.save(path)
    document.close()


def test_pdf_page_and_bbox_provenance_are_deterministic(tmp_path):
    source = tmp_path / "evidence.pdf"
    _make_evidence_pdf(source)
    database = tmp_path / "pdf.sqlite"
    build_database(database, language="pdf", version="1", documents=[parse_pdf(source, "https://example.test/evidence.pdf")])
    with connect(database, read_only=True) as connection:
        query = EvidenceQuery(connection)
        root = connection.execute(
            "SELECT node_id FROM nodes WHERE section_number = '1'"
        ).fetchone()[0]
        digest = query.source_database_digest()
        plan = {
            "planRunId": "plan:pdf", "language": "pdf", "version": "1",
            "sourceDatabaseDigest": digest,
            "requestedUnits": [{"unitId": "unit:add", "name": "add.u32", "sourceNodeIds": [root]}],
            "externalPrerequisites": [], "dependencies": [],
        }
        scope = EvidenceScope.from_plan(plan, "unit:add")
        session = SessionQuery(query, scope)
        nodes = session.subtree(root, max_depth=1, limit=20)
        operation = next(item for item in nodes if "operation adds" in item["exactText"])
        bundle, diagnostics = validate_submission(query, scope, session.ledger, {
            "unitId": "unit:add",
            "selections": [_selection([operation["nodeId"]])],
        })
        assert diagnostics == []
        item = bundle["evidence"][0]
        assert item["sourceType"] == "pdf"
        assert item["pdfPage"] == 1
        assert len(item["bbox"]) == 4
        assert item["htmlAnchor"] is None
        assert validate_bundle(query, plan, bundle) == []
        changed = json.loads(json.dumps(bundle))
        changed["evidence"][0]["bbox"][0] += 1
        assert "PDF_PROVENANCE_MISMATCH" in {entry["code"] for entry in validate_bundle(query, plan, changed)}


def test_same_mcp_session_can_diagnose_then_accept(planner_database, tmp_path):
    plan = _plan(planner_database, ["alpha.u32"])
    scope = EvidenceScope.from_plan(plan, plan["requestedUnits"][0]["unitId"])
    submission = tmp_path / "submission.json"
    server = EvidenceMcpServer(planner_database, scope, submission, tmp_path / "trace.json")
    try:
        assert {item["name"] for item in tool_definitions()} == {
            "spec_show", "spec_children", "spec_ancestors", "spec_subtree", "spec_search",
            "spec_xrefs", "spec_definitions", "spec_correlated", "submit_evidence",
        }
        invalid = json.loads(server.call_tool("submit_evidence", {
            "unitId": "unit:wrong", "selections": [_selection(scope.unit["sourceNodeIds"], role="OTHER")],
        })["content"][0]["text"])
        assert invalid["accepted"] is False
        assert not submission.exists()
        valid = json.loads(server.call_tool("submit_evidence", {
            "unitId": scope.unit_id, "selections": [_selection(scope.unit["sourceNodeIds"], role="OTHER")],
        })["content"][0]["text"])
        assert valid["accepted"] is True
        assert submission.exists()
    finally:
        server.close()


def test_runner_pins_exact_model_and_writes_one_session_artifacts(planner_database, tmp_path, monkeypatch):
    plan = _plan(planner_database, ["alpha.u32"])
    monkeypatch.setattr("spec2lean.evidence.runner.shutil.which", lambda _: "/usr/bin/opencode")
    monkeypatch.setattr("spec2lean.evidence.runner.installed_openai_models", lambda _: {RETRIEVER_MODEL})
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        config = json.loads(kwargs["env"]["OPENCODE_CONFIG_CONTENT"])
        mcp_command = config["mcp"]["specdb"]["command"]
        def argument(name):
            return Path(mcp_command[mcp_command.index(name) + 1])
        scope = EvidenceScope.from_dict(json.loads(argument("--scope").read_text()))
        server = EvidenceMcpServer(
            planner_database, scope, argument("--submission"), argument("--trace")
        )
        try:
            server.call_tool("submit_evidence", {
                "unitId": scope.unit_id,
                "selections": [_selection(scope.unit["sourceNodeIds"], role="OTHER")],
            })
        finally:
            server.close()
        return subprocess.CompletedProcess(command, 0, '{"sessionID":"evidence-session"}\n', "")

    root = build_evidence(
        planner_database, plan, tmp_path / "evidence", run_command=fake_run
    )
    assert len(calls) == 1
    unit_dir = next(root.iterdir())
    assert {path.name for path in unit_dir.iterdir()} == {
        "evidence.json", "evidence.md", "retriever-run.json"
    }
    metadata = json.loads((unit_dir / "retriever-run.json").read_text())
    assert metadata["model"] == RETRIEVER_MODEL == "openai/gpt-5.6-sol"
    assert metadata["reasoning"] == RETRIEVER_REASONING == "medium"
    assert metadata["singleSession"] is True
    assert metadata["automaticRetries"] == 0
    assert metadata["sessionId"] == "evidence-session"
    assert metadata["command"][-1] == "<evidence-retriever-prompt>"
    assert calls[0][1]["env"]["OPENCODE_DISABLE_PROJECT_CONFIG"] == "1"


def test_opencode_config_disables_unbounded_capabilities(tmp_path):
    config = opencode_config(tmp_path / "db", tmp_path / "scope", tmp_path / "submission", tmp_path / "trace")
    agent = config["agent"]["spec2lean-evidence-retriever"]
    assert agent["model"] == RETRIEVER_MODEL
    assert agent["variant"] == RETRIEVER_REASONING == "medium"
    for forbidden in ("bash", "edit", "read", "task", "webfetch", "websearch", "skill"):
        assert agent["tools"][forbidden] is False


def test_evidence_inspection_cli_reads_artifacts_without_opencode(planner_database, tmp_path, capsys):
    plan = _plan(planner_database, ["alpha.u32"])
    unit_id = plan["requestedUnits"][0]["unitId"]
    with connect(planner_database, read_only=True) as connection:
        scope, query, session = _session_for(connection, plan, unit_id)
        bundle, diagnostics = validate_submission(query, scope, session.ledger, {
            "unitId": unit_id,
            "selections": [_selection(scope.unit["sourceNodeIds"], role="OTHER")],
        })
    assert diagnostics == [] and bundle is not None
    plans_root = tmp_path / "plans"
    plan_dir = plans_root / "synthetic" / "1.0" / plan["planRunId"]
    plan_dir.mkdir(parents=True)
    (plan_dir / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    evidence_root = tmp_path / "evidence"
    unit_dir = evidence_root / "synthetic" / "1.0" / plan["planRunId"] / "alpha"
    unit_dir.mkdir(parents=True)
    (unit_dir / "evidence.json").write_text(json.dumps(bundle), encoding="utf-8")
    (unit_dir / "retriever-run.json").write_text(json.dumps({
        "unitId": unit_id, "outcome": "VALID"
    }), encoding="utf-8")
    common = ["--plans-root", str(plans_root), "--evidence-root", str(evidence_root)]
    for command, extra in (
        ("units", []),
        ("show", ["--unit", unit_id]),
        ("core", ["--unit", unit_id]),
        ("supporting", ["--unit", unit_id]),
        ("stats", []),
    ):
        assert main(["evidence", command, "--plan-run", plan["planRunId"], *extra, *common]) == 0
        json.loads(capsys.readouterr().out)
    evidence_id = bundle["evidence"][0]["evidenceId"]
    assert main([
        "evidence", "provenance", "--evidence", evidence_id,
        "--evidence-root", str(evidence_root),
    ]) == 0
    provenance = json.loads(capsys.readouterr().out)
    assert provenance["documentSha256"] == bundle["evidence"][0]["documentSha256"]


def test_missing_exact_model_starts_no_session_or_artifact(planner_database, tmp_path, monkeypatch):
    plan = _plan(planner_database, ["alpha.u32"])
    monkeypatch.setattr("spec2lean.evidence.runner.shutil.which", lambda _: "/usr/bin/opencode")
    monkeypatch.setattr("spec2lean.evidence.runner.installed_openai_models", lambda _: {"openai/gpt-5.3-codex"})
    invoked = False

    def must_not_run(*args, **kwargs):
        nonlocal invoked
        invoked = True
        raise AssertionError("retriever must not start")

    with pytest.raises(RuntimeError, match="required OpenCode Evidence Retriever model is unavailable"):
        build_evidence(planner_database, plan, tmp_path / "evidence", run_command=must_not_run)
    assert invoked is False
    assert not (tmp_path / "evidence").exists()
