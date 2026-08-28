from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from spec2lean.database import connect
from spec2lean.evidence.runner import unit_directory_name
from spec2lean.evidence.models import EvidenceScope
from spec2lean.evidence.query import EvidenceQuery, SessionQuery
from spec2lean.evidence.validation import build_evidence_record, validate_bundle
from spec2lean.planning.models import PlanningRequest
from spec2lean.planning.scope import Phase1Query, ScopeResolver
from spec2lean.planning.validation import build_validated_plan
from spec2lean.semantics.models import SemanticScope
from spec2lean.semantics.mcp import SemanticsMcpServer
from spec2lean.semantics.question_mcp import OpenQuestionMcpServer, tool_definitions
from spec2lean.semantics.questions import OpenQuestionScope
from spec2lean.semantics.question_runner import opencode_config
from spec2lean.semantics.runner import build_semantics


def _inputs(database: Path) -> tuple[dict, dict, dict]:
    with connect(database, read_only=True) as connection:
        resolved = ScopeResolver(connection).resolve(
            PlanningRequest.exact("synthetic", "1.0", ["alpha.u32"])
        )
        plan = build_validated_plan(
            Phase1Query(connection),
            resolved,
            {
                "requestedUnitIds": [resolved.candidate_units[0]["unitId"]],
                "translationGroups": [{
                    "name": "InstructionSemantics",
                    "unitIds": [resolved.candidate_units[0]["unitId"]],
                    "reason": "The indexed synthetic source presents one instruction family.",
                    "supportingNodeIds": resolved.candidate_units[0]["sourceNodeIds"],
                    "origin": "INFERRED",
                }],
                "externalPrerequisites": [],
                "dependencies": [],
            },
            language="synthetic",
            version="1.0",
            plan_run_id="plan:questions",
            source_database_digest=EvidenceQuery(connection).source_database_digest(),
        )
        evidence_scope = EvidenceScope.from_plan(plan, plan["requestedUnits"][0]["unitId"])
        session = SessionQuery(EvidenceQuery(connection), evidence_scope)
        node_id = evidence_scope.unit["sourceNodeIds"][0]
        record = build_evidence_record(
            session.query,
            evidence_scope,
            node_ids=[node_id],
            span_ids=[],
            role="OPERATION",
            tier="CORE",
            rationale="Initial instruction evidence.",
            selection_basis={node_id: sorted(session.ledger.nodes[node_id])},
        )
    bundle = {
        "schemaVersion": 1,
        "phase": "RETRIEVE_EVIDENCE",
        "planRunId": plan["planRunId"],
        "language": plan["language"],
        "version": plan["version"],
        "sourceDatabaseDigest": plan["sourceDatabaseDigest"],
        "unit": plan["requestedUnits"][0],
        "evidence": [record],
    }
    semantic_scope = SemanticScope.from_inputs(
        plan, bundle, bundle["unit"]["unitId"], created_at="2026-01-01T00:00:00Z"
    )
    failure = semantic_scope.artifact({
        "outcome": "INSUFFICIENT_EVIDENCE",
        "missingAspects": ["The canonical definition of an integer operand."],
        "explanation": "The current bundle does not contain the shared definition.",
        "evidenceIds": [record["evidenceId"]],
    })
    return plan, bundle, failure


def _text(response: dict) -> dict:
    return json.loads(response["content"][0]["text"])


def test_database_resolution_augments_canonical_evidence(planner_database, tmp_path):
    plan, bundle, failure = _inputs(planner_database)
    scope = OpenQuestionScope.from_inputs(
        plan, bundle, failure, created_at="2026-01-01T00:00:01Z"
    )
    server = OpenQuestionMcpServer(
        planner_database,
        scope,
        bundle,
        tmp_path / "submission.json",
        tmp_path / "trace.json",
    )
    try:
        question_id = scope.questions[0]["questionId"]
        definitions = _text(server.call_tool("spec_definitions", {
            "questionId": question_id, "query": "integer operand", "limit": 20,
        }))
        node_id = definitions[0]["node_id"]
        server.call_tool("spec_show", {"nodeId": node_id})
        accepted = _text(server.call_tool("submit_questions", {"resolutions": [{
            "questionId": question_id,
            "source": "DATABASE",
            "role": "SUPPORTING_DEFINITION",
            "answer": "An integer operand is an operand whose declared type is integral.",
            "rationale": "The canonical Phase-1 definition supplies the missing term.",
            "sourceNodeIds": [node_id],
            "sourceSpanIds": [],
        }]}))
        assert accepted == {"accepted": True, "outcome": "RESOLVED"}
        payload = json.loads((tmp_path / "submission.json").read_text())
        artifact, augmented = payload["artifact"], payload["augmentedBundle"]
        assert artifact["databaseEvidenceAdded"]
        assert artifact["supplementalResolutionsAdded"] == []
        assert len(augmented["evidence"]) == len(bundle["evidence"]) + 1
        with connect(planner_database, read_only=True) as connection:
            assert validate_bundle(EvidenceQuery(connection), plan, augmented) == []
    finally:
        server.close()


def test_one_new_database_record_can_resolve_multiple_questions(planner_database, tmp_path):
    plan, bundle, failure = _inputs(planner_database)
    failure["failure"]["missingAspects"] = [
        "The canonical definition of an integer operand.",
        "The canonical classification of an integer operand.",
    ]
    scope = OpenQuestionScope.from_inputs(
        plan, bundle, failure, created_at="2026-01-01T00:00:01Z"
    )
    server = OpenQuestionMcpServer(
        planner_database,
        scope,
        bundle,
        tmp_path / "submission.json",
        tmp_path / "trace.json",
    )
    try:
        node_id = None
        resolutions = []
        for question in scope.questions:
            definitions = _text(server.call_tool("spec_definitions", {
                "questionId": question["questionId"],
                "query": "integer operand",
                "limit": 20,
            }))
            node_id = node_id or definitions[0]["node_id"]
            server.call_tool("spec_show", {"nodeId": node_id})
            resolutions.append({
                "questionId": question["questionId"],
                "source": "DATABASE",
                "role": "SUPPORTING_DEFINITION",
                "answer": "The canonical definition supplies this missing aspect.",
                "rationale": "Both questions are answered by the same exact source node.",
                "sourceNodeIds": [node_id],
                "sourceSpanIds": [],
            })
        accepted = _text(server.call_tool(
            "submit_questions", {"resolutions": resolutions}
        ))
        assert accepted == {"accepted": True, "outcome": "RESOLVED"}
        payload = json.loads((tmp_path / "submission.json").read_text())
        assert len(payload["artifact"]["databaseEvidenceAdded"]) == 1
        assert len(payload["augmentedBundle"]["evidence"]) == len(bundle["evidence"]) + 1
        references = [item["references"] for item in payload["artifact"]["questions"]]
        assert references[0] == references[1]
    finally:
        server.close()


def test_llm_fallback_requires_database_check_and_is_flagged(planner_database, tmp_path):
    plan, bundle, failure = _inputs(planner_database)
    scope = OpenQuestionScope.from_inputs(
        plan, bundle, failure, created_at="2026-01-01T00:00:01Z"
    )
    server = OpenQuestionMcpServer(
        planner_database,
        scope,
        bundle,
        tmp_path / "submission.json",
        tmp_path / "trace.json",
    )
    try:
        question_id = scope.questions[0]["questionId"]
        submission = {"resolutions": [{
            "questionId": question_id,
            "source": "LLM_REASONING",
            "role": "ALGORITHM",
            "answer": "Use the explicitly proposed bounded interpretation.",
            "rationale": "This is a transparent modeling assumption, not a source fact.",
        }]}
        rejected = _text(server.call_tool("submit_questions", submission))
        assert "DATABASE_NOT_CHECKED" in {item["code"] for item in rejected["diagnostics"]}
        server.call_tool("spec_search", {
            "questionId": question_id,
            "query": "missing bounded interpretation",
            "justification": "Verify whether the canonical source defines the disputed behavior.",
            "limit": 20,
        })
        accepted = _text(server.call_tool("submit_questions", submission))
        assert accepted == {"accepted": True, "outcome": "RESOLVED"}
        payload = json.loads((tmp_path / "submission.json").read_text())
        resolution = payload["augmentedBundle"]["resolutions"][0]
        assert resolution["sourceKind"] == "LLM_REASONING"
        assert resolution["nonNormative"] is True
        assert resolution["provenance"] == {
            "model": "openai/gpt-5.6-sol", "reasoning": "medium"
        }
        with connect(planner_database, read_only=True) as connection:
            assert validate_bundle(
                EvidenceQuery(connection), plan, payload["augmentedBundle"]
            ) == []
    finally:
        server.close()


def test_runtime_tool_is_exposed_only_with_a_configured_adapter():
    without = {item["name"] for item in tool_definitions(runtime_available=False)}
    with_runtime = {item["name"] for item in tool_definitions(runtime_available=True)}
    assert "execute_probe" not in without
    assert "execute_probe" in with_runtime


def test_handler_config_pins_model_and_denies_general_execution(tmp_path):
    config = opencode_config(
        tmp_path / "spec.sqlite", tmp_path / "scope.json", tmp_path / "evidence.json",
        tmp_path / "submission.json", tmp_path / "trace.json", (),
    )
    agent = config["agent"]["spec2lean-open-question-handler"]
    assert agent["model"] == "openai/gpt-5.6-sol"
    assert agent["variant"] == "medium"
    assert agent["tools"]["bash"] is False
    assert agent["tools"]["websearch"] is True
    assert agent["tools"]["webfetch"] is True
    assert config["mcp"]["open_questions"]["timeout"] > 60_000


def test_runtime_probe_is_database_first_and_records_execution(planner_database, tmp_path):
    plan, bundle, failure = _inputs(planner_database)
    scope = OpenQuestionScope.from_inputs(
        plan, bundle, failure, created_at="2026-01-01T00:00:01Z"
    )
    server = OpenQuestionMcpServer(
        planner_database, scope, bundle, tmp_path / "submission.json",
        tmp_path / "trace.json",
        (sys.executable, "-c", "import sys; print(sys.stdin.read(), end='')"),
    )
    try:
        question_id = scope.questions[0]["questionId"]
        with pytest.raises(RuntimeError, match="canonical database must be searched"):
            server.call_tool("execute_probe", {"questionId": question_id, "input": {"x": 1}})
        server.call_tool("spec_search", {
            "questionId": question_id, "query": "runtime-specific missing behavior",
            "justification": "Check the canonical specification before executing a probe.",
        })
        probe = _text(server.call_tool(
            "execute_probe", {"questionId": question_id, "input": {"x": 1}}
        ))
        assert probe["exitCode"] == 0
        assert probe["probeId"].startswith("probe:")
        assert '"questionId"' in probe["stdout"]
    finally:
        server.close()


def test_semantic_runner_resolves_questions_then_reextracts(
    planner_database, tmp_path, monkeypatch
):
    plan, bundle, _ = _inputs(planner_database)
    evidence_root = tmp_path / "evidence"
    evidence_dir = (
        evidence_root / plan["language"] / plan["version"] / plan["planRunId"]
        / unit_directory_name(bundle["unit"])
    )
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "evidence.json").write_text(json.dumps(bundle), encoding="utf-8")
    (evidence_dir / "evidence.md").write_text("initial\n", encoding="utf-8")
    (evidence_dir / "retriever-run.json").write_text(json.dumps({
        "unitId": bundle["unit"]["unitId"], "outcome": "VALID",
    }), encoding="utf-8")

    monkeypatch.setattr("spec2lean.semantics.runner.shutil.which", lambda _: "/usr/bin/opencode")
    monkeypatch.setattr("spec2lean.semantics.question_runner.shutil.which", lambda _: "/usr/bin/opencode")
    monkeypatch.setattr(
        "spec2lean.semantics.runner.installed_openai_models",
        lambda _: {"openai/gpt-5.6-sol"},
    )
    monkeypatch.setattr(
        "spec2lean.semantics.question_runner.installed_openai_models",
        lambda _: {"openai/gpt-5.6-sol"},
    )
    calls: list[str] = []
    extractor_attempt = 0

    def fake_run(command, **kwargs):
        nonlocal extractor_attempt
        agent = command[command.index("--agent") + 1]
        calls.append(agent)
        config = json.loads(kwargs["env"]["OPENCODE_CONFIG_CONTENT"])
        if agent == "spec2lean-semantic-extractor":
            extractor_attempt += 1
            if extractor_attempt == 2:
                # Handler additions stay tentative until this extraction succeeds.
                persisted = json.loads((evidence_dir / "evidence.json").read_text())
                assert len(persisted["evidence"]) == 1
            mcp = config["mcp"]["semantics"]["command"]

            def semantic_path(flag):
                return Path(mcp[mcp.index(flag) + 1])

            scope = SemanticScope.from_dict(json.loads(semantic_path("--scope").read_text()))
            current_bundle = json.loads(semantic_path("--evidence").read_text())
            server = SemanticsMcpServer(scope, current_bundle, semantic_path("--submission"))
            server.call_tool("get_evidence", {})
            if extractor_attempt == 1:
                submission = {
                    "outcome": "INSUFFICIENT_EVIDENCE",
                    "missingAspects": ["The canonical definition of an integer operand."],
                    "explanation": "The current bundle does not contain the shared definition.",
                    "evidenceIds": [current_bundle["evidence"][0]["evidenceId"]],
                }
            else:
                evidence_id = current_bundle["evidence"][0]["evidenceId"]
                submission = {
                    "outcome": "SUCCESS",
                    "unitKind": "INSTRUCTION",
                    "identity": {"name": "alpha.u32", "form": "alpha.u32 d, a", "description": "Synthetic instruction.", "evidenceIds": [evidence_id]},
                    "syntaxForms": [],
                    "inputs": [{"name": "a", "role": "source", "description": "Input value.", "constraints": [], "evidenceIds": [evidence_id]}],
                    "result": {"name": "d", "description": "Output value.", "constraints": [], "evidenceIds": [evidence_id]},
                    "operation": {"description": "Copies the synthetic input into the output value.", "inputs": ["a"], "result": "The output value d.", "branches": [], "evidenceIds": [evidence_id]},
                    "edgeCases": [], "stateEffects": [], "predication": None,
                    "restrictions": [], "dependencies": [],
                    "claims": [{"claimId": "claim:alpha", "kind": "SOURCE_FACT", "statement": "The instruction produces the stated output.", "evidenceIds": [evidence_id]}],
                }
            accepted = _text(server.call_tool("submit_semantics", submission))
            assert accepted["accepted"] is True
        else:
            mcp = config["mcp"]["open_questions"]["command"]

            def handler_path(flag):
                return Path(mcp[mcp.index(flag) + 1])

            question_scope = OpenQuestionScope.from_dict(
                json.loads(handler_path("--scope").read_text())
            )
            current_bundle = json.loads(handler_path("--evidence").read_text())
            server = OpenQuestionMcpServer(
                handler_path("--database"), question_scope, current_bundle,
                handler_path("--submission"), handler_path("--trace"),
            )
            try:
                question_id = question_scope.questions[0]["questionId"]
                definitions = _text(server.call_tool("spec_definitions", {
                    "questionId": question_id, "query": "integer operand", "limit": 20,
                }))
                node_id = definitions[0]["node_id"]
                server.call_tool("spec_show", {"nodeId": node_id})
                accepted = _text(server.call_tool("submit_questions", {"resolutions": [{
                    "questionId": question_id, "source": "DATABASE",
                    "role": "SUPPORTING_DEFINITION",
                    "answer": "The canonical definition supplies the missing term.",
                    "rationale": "Recovered from the canonical Phase-1 database.",
                    "sourceNodeIds": [node_id], "sourceSpanIds": [],
                }]}))
                assert accepted == {"accepted": True, "outcome": "RESOLVED"}
            finally:
                server.close()
        return subprocess.CompletedProcess(command, 0, '{"sessionID":"test"}\n', "")

    root = build_semantics(
        plan, evidence_root, tmp_path / "semantics",
        database=planner_database, run_command=fake_run,
    )
    assert calls == [
        "spec2lean-semantic-extractor",
        "spec2lean-open-question-handler",
        "spec2lean-semantic-extractor",
    ]
    output = next(root.iterdir())
    assert json.loads((output / "semantics.json").read_text())["outcome"] == "SUCCESS"
    assert (output / "open-question-attempts/attempt-1/handler/open-questions.json").is_file()
    assert (output / "open-question-attempts/attempt-1/extractor/semantics.json").is_file()
    augmented = json.loads((evidence_dir / "evidence.json").read_text())
    assert len(augmented["evidence"]) == 2
    metadata = json.loads((evidence_dir / "retriever-run.json").read_text())
    assert metadata["openQuestionAugmentations"][0]["outcome"] == "RESOLVED"
