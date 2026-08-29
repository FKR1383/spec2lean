from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from spec2lean.database import connect
from spec2lean.planning.models import PlanningRequest, ScopeMode
from spec2lean.planning.mcp import PlannerMcpServer, tool_definitions
from spec2lean.planning.prompt import build_planner_prompt
from spec2lean.planning.runner import PLANNER_MODEL, PLANNER_REASONING, build_plan, opencode_config
from spec2lean.planning.scope import Phase1Query, ScopeResolver
from spec2lean.planning.validation import build_validated_plan, validate_submission


def _resolved(planner_database: Path, names: list[str]):
    connection = connect(planner_database, read_only=True)
    request = PlanningRequest.exact("synthetic", "1.0", names)
    return connection, ScopeResolver(connection).resolve(request)


def _submission(
    scope, *, selected=None, prerequisites=None, shared_prerequisites=None, dependencies=None
):
    unit_ids = selected or [item["unitId"] for item in scope.candidate_units]
    selected_units = [item for item in scope.candidate_units if item["unitId"] in unit_ids]
    return {
        "requestedUnitIds": unit_ids,
        "translationGroups": [{
            "name": "InstructionSemantics",
            "unitIds": unit_ids,
            "reason": "The indexed specification places these units in one instruction family.",
            "supportingNodeIds": sorted({
                node_id for item in selected_units for node_id in item["sourceNodeIds"]
            }),
            "origin": "INFERRED",
        }],
        "externalPrerequisites": prerequisites or [],
        "sharedPrerequisites": shared_prerequisites or [],
        "dependencies": dependencies or [],
    }


def _edge(source: str, target: str, support: str, *, origin="INFERRED"):
    return {
        "from": source,
        "to": target,
        "reason": "The source must be processed first.",
        "supportingNodeIds": [support],
        "origin": origin,
    }


def test_typed_request_modes_are_unambiguous():
    requests = [
        PlanningRequest.exact("x", "1", ["alpha.u32"]),
        PlanningRequest.family_request("x", "1", "integer arithmetic instructions"),
        PlanningRequest.subtree("x", "1", "node:abc"),
        PlanningRequest.full("x", "1"),
    ]
    assert [item.mode for item in requests] == list(ScopeMode)
    for request in requests:
        assert PlanningRequest.from_dict(request.to_dict()) == request
    with pytest.raises(ValueError, match="exactly one"):
        PlanningRequest("x", "1", ScopeMode.EXACT_INSTRUCTIONS, ("alpha.u32",), family="also")


def test_exact_scope_resolves_every_instruction_and_cannot_expand(planner_database):
    connection, scope = _resolved(planner_database, ["alpha.u32", "beta.u32"])
    try:
        assert [item["name"] for item in scope.candidate_units] == ["alpha.u32", "beta.u32"]
        submission = _submission(scope, selected=[scope.candidate_units[0]["unitId"]])
        _, diagnostics = validate_submission(Phase1Query(connection), scope, submission)
        assert {item["code"] for item in diagnostics} == {"SCOPE_MISMATCH"}
    finally:
        connection.close()


def test_invalid_exact_instruction_fails_during_resolution(planner_database):
    with connect(planner_database, read_only=True) as connection:
        for invalid in ("invented.u32", "alpha.wrong"):
            with pytest.raises(ValueError, match="could not be resolved"):
                ScopeResolver(connection).resolve(
                    PlanningRequest.exact("synthetic", "1.0", [invalid])
                )


def test_family_and_source_subtree_build_bounded_candidates(planner_database):
    with connect(planner_database, read_only=True) as connection:
        family = ScopeResolver(connection).resolve(
            PlanningRequest.family_request("synthetic", "1.0", "integer arithmetic instructions")
        )
        assert {unit["name"] for unit in family.candidate_units} == {"alpha", "beta", "gamma"}
        root = connection.execute(
            "SELECT node_id FROM nodes WHERE html_anchor = 'integer-arithmetic-instructions'"
        ).fetchone()[0]
        subtree = ScopeResolver(connection).resolve(
            PlanningRequest.subtree("synthetic", "1.0", root)
        )
        assert {unit["name"] for unit in subtree.candidate_units} == {"alpha", "beta", "gamma"}
        assert set(subtree.exact_unit_ids) == {unit["unitId"] for unit in subtree.candidate_units}
        full = ScopeResolver(connection).resolve(PlanningRequest.full("synthetic", "1.0"))
        assert {unit["name"] for unit in full.candidate_units} == {
            "Integer Arithmetic Instructions", "Integer Operand Rules"
        }
        assert set(full.exact_unit_ids) == {unit["unitId"] for unit in full.candidate_units}


def test_two_independent_instructions_share_layer_zero(planner_database):
    connection, scope = _resolved(planner_database, ["alpha.u32", "beta.u32"])
    try:
        plan = build_validated_plan(
            Phase1Query(connection), scope, _submission(scope),
            language="synthetic", version="1.0", plan_run_id="plan:test",
            source_database_digest="a" * 64,
        )
        assert plan["processingLayers"] == [{
            "layer": 0,
            "unitIds": sorted(item["unitId"] for item in scope.candidate_units),
        }]
        assert plan["graphStatus"] == "ACYCLIC"
        assert plan["schemaVersion"] == 3
        assert plan["translationGroups"][0]["unitIds"] == [
            item["unitId"] for item in scope.candidate_units
        ]
    finally:
        connection.close()


def test_simple_dependency_and_independent_third_unit_derive_layers(planner_database):
    connection, scope = _resolved(planner_database, ["alpha.u32", "beta.u32", "gamma.u32"])
    try:
        alpha, beta, gamma = [item["unitId"] for item in scope.candidate_units]
        support = scope.candidate_units[0]["sourceNodeIds"][0]
        plan = build_validated_plan(
            Phase1Query(connection), scope,
            _submission(scope, dependencies=[_edge(alpha, beta, support)]),
            language="synthetic", version="1.0", plan_run_id="plan:test",
            source_database_digest="b" * 64,
        )
        assert plan["processingLayers"] == [
            {"layer": 0, "unitIds": sorted([alpha, gamma])},
            {"layer": 1, "unitIds": [beta]},
        ]
    finally:
        connection.close()


def test_external_prerequisite_is_recorded_but_not_scheduled(planner_database):
    connection, scope = _resolved(planner_database, ["beta.u32"])
    try:
        rules = connection.execute(
            "SELECT node_id FROM nodes WHERE html_anchor = 'integer-operand-rules'"
        ).fetchone()[0]
        unit = scope.candidate_units[0]["unitId"]
        prerequisite = {
            "key": "integer-rules",
            "name": "Integer operand rules",
            "reason": "Beta uses integral operands.",
            "sourceNodeIds": [rules],
        }
        plan = build_validated_plan(
            Phase1Query(connection), scope,
            _submission(scope, prerequisites=[prerequisite], dependencies=[_edge("integer-rules", unit, rules, origin="EXPLICIT")]),
            language="synthetic", version="1.0", plan_run_id="plan:test",
            source_database_digest="c" * 64,
        )
        assert len(plan["externalPrerequisites"]) == 1
        assert plan["processingLayers"] == [{"layer": 0, "unitIds": [unit]}]
        assert plan["dependencies"][0]["from"].startswith("prerequisite:")
    finally:
        connection.close()


def test_shared_prerequisite_has_stable_scoped_identity_and_is_not_scheduled(planner_database):
    connection, scope = _resolved(planner_database, ["alpha.u32", "beta.u32"])
    try:
        rules = connection.execute(
            "SELECT node_id FROM nodes WHERE html_anchor = 'integer-operand-rules'"
        ).fetchone()[0]
        unit_ids = [item["unitId"] for item in scope.candidate_units]
        shared = {
            "key": "integer-value-domain",
            "name": "Integer value domain",
            "kind": "value-domain",
            "reason": "Both requested units consume the same source-level integer domain.",
            "sourceNodeIds": [rules],
            "requiredBy": list(reversed(unit_ids)),
        }
        first = build_validated_plan(
            Phase1Query(connection), scope,
            _submission(scope, shared_prerequisites=[shared]),
            language="synthetic", version="1.0", plan_run_id="plan:shared-one",
            source_database_digest="e" * 64,
        )
        item = first["sharedPrerequisites"][0]
        assert item["dependencyId"].startswith("shared:")
        assert item["kind"] == "value-domain"
        assert item["requiredBy"] == sorted(unit_ids)
        assert all(
            item["dependencyId"] not in layer["unitIds"]
            for layer in first["processingLayers"]
        )

        changed_scope_only = dict(shared)
        changed_scope_only["reason"] = "Different planning rationale wording."
        changed_scope_only["requiredBy"] = unit_ids
        second = build_validated_plan(
            Phase1Query(connection), scope,
            _submission(scope, shared_prerequisites=[changed_scope_only]),
            language="synthetic", version="1.0", plan_run_id="plan:shared-two",
            source_database_digest="e" * 64,
        )
        assert second["sharedPrerequisites"][0]["dependencyId"] == item["dependencyId"]
    finally:
        connection.close()


@pytest.mark.parametrize(
    ("required_by", "expected"),
    [
        ([], "MISSING_SHARED_PREREQUISITE_CONSUMER"),
        (["unit:invented"], "UNKNOWN_SHARED_PREREQUISITE_CONSUMER"),
        (None, "DUPLICATE_SHARED_PREREQUISITE_CONSUMER"),
    ],
)
def test_shared_prerequisite_consumers_are_nonempty_selected_and_unique(
    planner_database, required_by, expected
):
    connection, scope = _resolved(planner_database, ["alpha.u32", "beta.u32"])
    try:
        rules = connection.execute(
            "SELECT node_id FROM nodes WHERE html_anchor = 'integer-operand-rules'"
        ).fetchone()[0]
        unit_id = scope.candidate_units[0]["unitId"]
        consumers = [unit_id, unit_id] if required_by is None else required_by
        shared = {
            "key": "integer-domain", "name": "Integer domain", "kind": "value-domain",
            "reason": "Requested units use it.", "sourceNodeIds": [rules],
            "requiredBy": consumers,
        }
        _, diagnostics = validate_submission(
            Phase1Query(connection), scope,
            _submission(scope, shared_prerequisites=[shared]),
        )
        assert expected in {item["code"] for item in diagnostics}
    finally:
        connection.close()


def test_planner_rejects_representation_fields_and_keeps_shared_kind_extensible(
    planner_database
):
    connection, scope = _resolved(planner_database, ["alpha.u32", "beta.u32"])
    try:
        rules = connection.execute(
            "SELECT node_id FROM nodes WHERE html_anchor = 'integer-operand-rules'"
        ).fetchone()[0]
        shared = {
            "key": "integer-domain", "name": "Integer domain",
            "kind": "arbitrary-specification-concept", "reason": "Shared by the request.",
            "sourceNodeIds": [rules],
            "requiredBy": [item["unitId"] for item in scope.candidate_units],
            "leanType": "BitVec",
        }
        submission = _submission(scope, shared_prerequisites=[shared])
        submission["representation"] = "Nat"
        _, diagnostics = validate_submission(Phase1Query(connection), scope, submission)
        assert {item["code"] for item in diagnostics} == {"UNEXPECTED_FIELD"}
        schema = next(item for item in tool_definitions() if item["name"] == "submit_plan")[
            "inputSchema"
        ]
        kind_schema = schema["properties"]["sharedPrerequisites"]["items"]["properties"]["kind"]
        assert "enum" not in kind_schema
        prompt = build_planner_prompt(Phase1Query(connection), scope)
        assert "Never choose or mention a Lean type" in prompt
        assert "do not add speculative concepts for the rest of the specification" in prompt
    finally:
        connection.close()


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ("invented", "INVENTED_SOURCE_NODE"),
        ("duplicate", "DUPLICATE_EDGE"),
        ("self", "SELF_EDGE"),
    ],
)
def test_structural_validation_rejects_bad_sources_and_edges(planner_database, mutation, expected):
    connection, scope = _resolved(planner_database, ["alpha.u32", "beta.u32"])
    try:
        alpha, beta = [item["unitId"] for item in scope.candidate_units]
        support = scope.candidate_units[0]["sourceNodeIds"][0]
        edge = _edge(alpha, beta, support)
        if mutation == "invented":
            edge["supportingNodeIds"] = ["node:invented"]
            dependencies = [edge]
        elif mutation == "duplicate":
            dependencies = [edge, dict(edge)]
        else:
            edge["to"] = alpha
            dependencies = [edge]
        _, diagnostics = validate_submission(
            Phase1Query(connection), scope, _submission(scope, dependencies=dependencies)
        )
        assert expected in {item["code"] for item in diagnostics}
    finally:
        connection.close()


def test_genuine_cycle_is_preserved_and_reported(planner_database):
    connection, scope = _resolved(planner_database, ["alpha.u32", "beta.u32", "gamma.u32"])
    try:
        alpha, beta, gamma = [item["unitId"] for item in scope.candidate_units]
        support = scope.candidate_units[0]["sourceNodeIds"][0]
        plan = build_validated_plan(
            Phase1Query(connection), scope,
            _submission(scope, dependencies=[
                _edge(alpha, beta, support),
                _edge(beta, alpha, support),
                _edge(beta, gamma, support),
            ]),
            language="synthetic", version="1.0", plan_run_id="plan:test",
            source_database_digest="d" * 64,
        )
        assert plan["graphStatus"] == "CYCLIC"
        assert plan["cycles"] == [{"unitIds": sorted([alpha, beta])}]
        assert plan["processingLayers"] == []
        assert plan["blockedUnitIds"] == [gamma]
        assert len(plan["dependencies"]) == 3
    finally:
        connection.close()


def test_one_session_runner_owns_metadata_and_does_not_call_real_opencode(planner_database, tmp_path, monkeypatch):
    monkeypatch.setattr("spec2lean.planning.runner.shutil.which", lambda _: "/usr/bin/opencode")
    monkeypatch.setattr(
        "spec2lean.planning.runner.installed_openai_models", lambda _: {PLANNER_MODEL}
    )
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        config = json.loads(kwargs["env"]["OPENCODE_CONFIG_CONTENT"])
        mcp_command = config["mcp"]["specdb"]["command"]
        scope_path = Path(mcp_command[mcp_command.index("--scope") + 1])
        submission_path = Path(mcp_command[mcp_command.index("--submission") + 1])
        scope = json.loads(scope_path.read_text())
        submission_path.write_text(json.dumps({
            "requestedUnitIds": scope["exactUnitIds"],
            "translationGroups": [{
                "name": "InstructionSemantics",
                "unitIds": scope["exactUnitIds"],
                "reason": "The indexed source presents these as one instruction family.",
                "supportingNodeIds": sorted({
                    node_id
                    for unit in scope["candidateUnits"]
                    if unit["unitId"] in scope["exactUnitIds"]
                    for node_id in unit["sourceNodeIds"]
                }),
                "origin": "INFERRED",
            }],
            "externalPrerequisites": [],
            "sharedPrerequisites": [],
            "dependencies": [],
        }))
        return subprocess.CompletedProcess(command, 0, '{"sessionID":"session-test"}\n', "")

    run = build_plan(
        planner_database,
        tmp_path / "plans",
        PlanningRequest.exact("synthetic", "1.0", ["alpha.u32", "gamma.u32"]),
        run_command=fake_run,
    )
    assert len(calls) == 1
    metadata = json.loads((run / "planner-run.json").read_text())
    plan = json.loads((run / "plan.json").read_text())
    assert metadata["model"] == PLANNER_MODEL
    assert metadata["reasoning"] == PLANNER_REASONING
    assert metadata["singleSession"] is True
    assert metadata["sessionId"] == "session-test"
    assert metadata["command"][-1] == "<planner-prompt>"
    assert "--print-logs" in metadata["command"]
    assert metadata["command"][metadata["command"].index("--log-level") + 1] == "ERROR"
    assert plan["language"] == "synthetic"
    assert plan["version"] == "1.0"
    assert plan["planRunId"] == run.name
    assert plan["sourceDatabaseDigest"] == metadata["sourceDatabaseDigest"]
    assert {path.name for path in run.iterdir()} == {
        "request.json", "plan.json", "plan.md", "planner-run.json"
    }
    run_env = calls[0][1]["env"]
    assert run_env["OPENCODE_DISABLE_PROJECT_CONFIG"] == "1"
    assert "OPENCODE_DISABLE_DEFAULT_PLUGINS" not in run_env
    assert Path(run_env["OPENCODE_CONFIG_DIR"]).name == "opencode-config"
    assert Path(run_env["OPENCODE_TEST_HOME"]).name == "opencode-home"


def test_opencode_config_disables_unbounded_capabilities(tmp_path):
    config = opencode_config(tmp_path / "db", tmp_path / "scope", tmp_path / "submission")
    agent = config["agent"]["spec2lean-planner"]
    assert agent["model"] == PLANNER_MODEL == "openai/gpt-5.6-sol"
    assert agent["variant"] == PLANNER_REASONING == "medium"
    for forbidden in ("bash", "edit", "read", "task", "webfetch", "websearch", "skill"):
        assert agent["tools"][forbidden] is False


def test_missing_exact_model_fails_before_starting_a_planner_session(
    planner_database, tmp_path, monkeypatch
):
    monkeypatch.setattr("spec2lean.planning.runner.shutil.which", lambda _: "/usr/bin/opencode")
    monkeypatch.setattr(
        "spec2lean.planning.runner.installed_openai_models",
        lambda _: {"openai/gpt-5.4"},
    )
    invoked = False

    def must_not_run(*args, **kwargs):
        nonlocal invoked
        invoked = True
        raise AssertionError("Planner session should not start")

    with pytest.raises(RuntimeError, match="required OpenCode Planner model is unavailable"):
        build_plan(
            planner_database,
            tmp_path / "plans",
            PlanningRequest.exact("synthetic", "1.0", ["alpha.u32"]),
            run_command=must_not_run,
        )
    assert invoked is False
    assert not (tmp_path / "plans").exists()


def test_submit_tool_can_diagnose_then_accept_in_the_same_server_session(planner_database, tmp_path):
    with connect(planner_database, read_only=True) as connection:
        scope = ScopeResolver(connection).resolve(
            PlanningRequest.exact("synthetic", "1.0", ["alpha.u32"])
        )
    submission_path = tmp_path / "submission.json"
    server = PlannerMcpServer(planner_database, scope, submission_path)
    try:
        names = {item["name"] for item in tool_definitions()}
        assert names == {
            "spec_search", "spec_show", "spec_children", "spec_ancestors",
            "spec_subtree", "spec_xrefs", "spec_definitions", "submit_plan",
        }
        invalid = json.loads(server.call_tool("submit_plan", {
            "requestedUnitIds": ["unit:invented"],
            "translationGroups": [],
            "externalPrerequisites": [],
            "sharedPrerequisites": [],
            "dependencies": [],
        })["content"][0]["text"])
        assert invalid["accepted"] is False
        assert not submission_path.exists()
        valid_submission = _submission(scope)
        accepted = json.loads(
            server.call_tool("submit_plan", valid_submission)["content"][0]["text"]
        )
        assert accepted["accepted"] is True
        assert json.loads(submission_path.read_text()) == valid_submission
    finally:
        server.close()


def test_translation_groups_are_general_exact_and_source_supported(planner_database):
    connection, scope = _resolved(planner_database, ["alpha.u32", "beta.u32"])
    try:
        alpha, beta = [item["unitId"] for item in scope.candidate_units]
        support = scope.candidate_units[0]["sourceNodeIds"][0]
        submission = _submission(scope)
        submission["translationGroups"] = [{
            "name": "IndexedFamily",
            "unitIds": [alpha],
            "reason": "The indexed section supports this family.",
            "supportingNodeIds": [support],
            "origin": "EXPLICIT",
        }]
        _, diagnostics = validate_submission(Phase1Query(connection), scope, submission)
        assert "UNGROUPED_REQUESTED_UNITS" in {item["code"] for item in diagnostics}

        submission = _submission(scope)
        submission["translationGroups"][0]["name"] = "hard-coded name"
        _, diagnostics = validate_submission(Phase1Query(connection), scope, submission)
        assert "INVALID_TRANSLATION_GROUP_NAME" in {item["code"] for item in diagnostics}

        submission = _submission(scope)
        submission["translationGroups"][0]["unitIds"] = [alpha, beta, alpha]
        _, diagnostics = validate_submission(Phase1Query(connection), scope, submission)
        assert "DUPLICATE_TRANSLATION_GROUP_UNIT" in {item["code"] for item in diagnostics}
    finally:
        connection.close()
