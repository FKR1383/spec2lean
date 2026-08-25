from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

import pytest

from spec2lean.database import connect
from spec2lean.planning.graph import derive_graph
from spec2lean.planning.render import render_dot, render_markdown
from spec2lean.planning.runner import build_plan
from spec2lean.planning.submission import (
    initialize_session_state,
    record_observed_nodes,
    session_status,
    submit_candidate,
)
from spec2lean.planning.validation import normalize_candidate, validate_plan


CLI = Path(__file__).resolve().parents[1] / "spec2lean"


def _nodes(database: Path) -> tuple[str, str, str]:
    with connect(database, read_only=True) as connection:
        syntax = connection.execute("SELECT node_id FROM nodes WHERE html_anchor = 'syntax'").fetchone()[0]
        overview = connection.execute("SELECT node_id FROM nodes WHERE html_anchor = 'overview'").fetchone()[0]
        examples = connection.execute("SELECT node_id FROM nodes WHERE html_anchor = 'examples'").fetchone()[0]
    return syntax, overview, examples


def _plan(database: Path, *, explicit: bool = True) -> dict:
    syntax, overview, examples = _nodes(database)
    units = [
        {
            "unitId": "synthetic.syntax",
            "name": "syntax",
            "kind": "TYPE_SYSTEM",
            "sourceNodeIds": [syntax],
            "instructionNames": [],
        },
        {
            "unitId": "synthetic.execution",
            "name": "execution",
            "kind": "EXECUTION_MODEL",
            "sourceNodeIds": [overview],
            "instructionNames": [],
        },
        {
            "unitId": "synthetic.instruction.add",
            "name": "add",
            "kind": "INSTRUCTION",
            "sourceNodeIds": [examples],
            "instructionNames": ["add.u32"],
        },
    ]
    dependencies = [
        {
            "fromUnitId": "synthetic.syntax",
            "toUnitId": "synthetic.execution",
            "type": "USES_TYPE_SYSTEM",
            "reason": "The overview directly references the syntax section.",
            "sourceNodeIds": [overview],
            "origin": "EXPLICIT" if explicit else "INFERRED",
        },
        {
            "fromUnitId": "synthetic.execution",
            "toUnitId": "synthetic.instruction.add",
            "type": "USES_EXECUTION_MODEL",
            "reason": "The instruction is interpreted by the execution model.",
            "sourceNodeIds": [examples],
            "origin": "INFERRED",
        },
    ]
    plan = {
        "schemaVersion": 1,
        "specification": {
            "language": "synthetic",
            "version": "1.0",
            "indexSemanticDigest": _digest(database),
        },
        "units": units,
        "dependencies": dependencies,
    }
    plan.update(derive_graph(units, dependencies))
    return plan


def _digest(database: Path) -> str:
    with connect(database, read_only=True) as connection:
        return connection.execute("SELECT semantic_digest FROM builds").fetchone()[0]


def _validate(plan: dict, database: Path) -> dict:
    with connect(database, read_only=True) as connection:
        return validate_plan(
            plan,
            connection,
            expected_language="synthetic",
            expected_version="1.0",
            expected_digest=_digest(database),
        )


def _codes(report: dict) -> set[str]:
    return {issue["code"] for issue in report["issues"]}


def test_valid_graph_explicit_reference_inferred_edge_and_layers(html_database):
    plan = _plan(html_database)
    report = _validate(plan, html_database)
    assert report["ok"], report
    assert [layer["unitIds"] for layer in plan["processingLayers"]] == [
        ["synthetic.syntax"],
        ["synthetic.execution"],
        ["synthetic.instruction.add"],
    ]
    assert len(plan["stronglyConnectedComponents"]) == 3
    assert not any(component["cyclic"] for component in plan["stronglyConnectedComponents"])


def test_invalid_source_node_is_rejected(html_database):
    plan = _plan(html_database)
    plan["units"][0]["sourceNodeIds"] = ["node:000000000000000000000000"]
    assert "SOURCE_NODE_MISSING" in _codes(_validate(plan, html_database))


@pytest.mark.parametrize("guessed", ["node:9?", "node:2f3?", "node:9...?"])
def test_guessed_or_partial_source_node_ids_are_rejected(html_database, guessed):
    plan = _plan(html_database)
    plan["units"][0]["sourceNodeIds"] = [guessed]
    assert "SOURCE_NODE_FORMAT" in _codes(_validate(plan, html_database))


def test_invalid_dependency_endpoint_is_rejected(html_database):
    plan = _plan(html_database)
    plan["dependencies"][0]["fromUnitId"] = "synthetic.missing"
    assert "DEPENDENCY_ENDPOINT" in _codes(_validate(plan, html_database))


def test_duplicate_and_self_edges_are_rejected(html_database):
    duplicate = _plan(html_database)
    duplicate["dependencies"].append(copy.deepcopy(duplicate["dependencies"][0]))
    assert "DUPLICATE_EDGE" in _codes(_validate(duplicate, html_database))

    self_edge = _plan(html_database)
    self_edge["dependencies"][0]["fromUnitId"] = self_edge["dependencies"][0]["toUnitId"]
    assert "SELF_EDGE" in _codes(_validate(self_edge, html_database))


def test_explicit_reference_must_match_indexed_resolved_reference(html_database):
    plan = _plan(html_database)
    plan["dependencies"][0]["sourceNodeIds"] = plan["units"][2]["sourceNodeIds"]
    report = _validate(plan, html_database)
    assert {"EXPLICIT_SUPPORT_MEMBERSHIP", "EXPLICIT_REFERENCE_MISSING"} <= _codes(report)


def test_inferred_dependency_needs_nodes_but_not_an_indexed_xref(html_database):
    plan = _plan(html_database, explicit=False)
    assert _validate(plan, html_database)["ok"]


def test_cycle_is_preserved_as_scc_and_layered_over_condensation_graph(html_database):
    plan = _plan(html_database, explicit=False)
    plan["dependencies"].append(
        {
            "fromUnitId": "synthetic.instruction.add",
            "toUnitId": "synthetic.execution",
            "type": "REQUIRES",
            "reason": "Synthetic mutual dependency for SCC coverage.",
            "sourceNodeIds": plan["units"][1]["sourceNodeIds"],
            "origin": "INFERRED",
        }
    )
    plan.update(derive_graph(plan["units"], plan["dependencies"]))
    report = _validate(plan, html_database)
    assert report["ok"], report
    cyclic = [item for item in plan["stronglyConnectedComponents"] if item["cyclic"]]
    assert cyclic == [{
        "sccId": cyclic[0]["sccId"],
        "unitIds": ["synthetic.execution", "synthetic.instruction.add"],
        "cyclic": True,
    }]
    assert [layer["unitIds"] for layer in plan["processingLayers"]] == [
        ["synthetic.syntax"],
        ["synthetic.execution", "synthetic.instruction.add"],
    ]


def test_stored_sccs_and_layers_must_equal_derivation(html_database):
    plan = _plan(html_database)
    plan["processingLayers"] = list(reversed(plan["processingLayers"]))
    plan["stronglyConnectedComponents"][0]["cyclic"] = True
    assert {"SCC_MISMATCH", "LAYER_MISMATCH"} <= _codes(_validate(plan, html_database))


def test_normalization_and_rendering_are_deterministic(html_database):
    plan = _plan(html_database)
    reversed_candidate = {
        "schemaVersion": 1,
        "specification": plan["specification"],
        "units": list(reversed(plan["units"])),
        "dependencies": list(reversed(plan["dependencies"])),
    }
    normalized = normalize_candidate(reversed_candidate)
    normalized.update(derive_graph(normalized["units"], normalized["dependencies"]))
    expected = normalize_candidate(plan)
    expected.update(derive_graph(expected["units"], expected["dependencies"]))
    assert normalized == expected
    assert render_markdown(plan) == render_markdown(copy.deepcopy(plan))
    assert render_dot(plan) == render_dot(copy.deepcopy(plan))


def test_duplicate_trivial_lists_are_canonicalized(html_database):
    plan = _plan(html_database)
    unit = plan["units"][0]
    unit["sourceNodeIds"] *= 2
    unit["instructionNames"] = ["synthetic", "synthetic"]
    edge = plan["dependencies"][0]
    edge["sourceNodeIds"] *= 2
    normalized = normalize_candidate(plan)
    normalized_unit = next(item for item in normalized["units"] if item["unitId"] == unit["unitId"])
    normalized_edge = next(
        item for item in normalized["dependencies"]
        if item["fromUnitId"] == edge["fromUnitId"] and item["toUnitId"] == edge["toUnitId"]
    )
    assert normalized_unit["sourceNodeIds"] == sorted(set(unit["sourceNodeIds"]))
    assert normalized_unit["instructionNames"] == ["synthetic"]
    assert normalized_edge["sourceNodeIds"] == sorted(set(edge["sourceNodeIds"]))


def test_instruction_without_instruction_names_is_rejected(html_database):
    plan = _plan(html_database)
    plan["units"][2]["instructionNames"] = []
    assert "INSTRUCTION_MEMBERSHIP" in _codes(_validate(plan, html_database))


def test_submission_rejects_real_but_unobserved_source_node(html_database, tmp_path):
    state = tmp_path / "session.sqlite"
    output = tmp_path / "submission.json"
    initialize_session_state(state)
    plan = _plan(html_database)
    syntax, _, _ = _nodes(html_database)
    record_observed_nodes(state, {"nodeId": syntax})
    result = submit_candidate(
        database=html_database,
        state_path=state,
        output_path=output,
        language="synthetic",
        version="1.0",
        digest=_digest(html_database),
        candidate=plan,
    )
    assert not result["accepted"]
    assert "SOURCE_NODE_NOT_OBSERVED" in {item["code"] for item in result["diagnostics"]}


def test_invalid_then_valid_submission_stays_in_one_simulated_session(html_database, tmp_path):
    state = tmp_path / "session.sqlite"
    output = tmp_path / "submission.json"
    initialize_session_state(state)
    plan = _plan(html_database)
    record_observed_nodes(state, plan)

    invalid = copy.deepcopy(plan)
    invalid["units"][2]["instructionNames"] = []
    first = submit_candidate(
        database=html_database,
        state_path=state,
        output_path=output,
        language="synthetic",
        version="1.0",
        digest=_digest(html_database),
        candidate=invalid,
    )
    assert not first["accepted"]
    assert "INSTRUCTION_MEMBERSHIP" in {item["code"] for item in first["diagnostics"]}
    assert not output.exists()

    valid = copy.deepcopy(plan)
    valid["units"][0]["sourceNodeIds"] *= 2
    second = submit_candidate(
        database=html_database,
        state_path=state,
        output_path=output,
        language="synthetic",
        version="1.0",
        digest=_digest(html_database),
        candidate=valid,
    )
    assert second["accepted"]
    assert output.is_file()
    assert session_status(state)["submitPlanAttempts"] == 2


def test_runner_uses_one_opencode_session_with_same_session_correction(
    html_database, tmp_path, monkeypatch
):
    import spec2lean.planning.runner as runner

    plan = _plan(html_database)
    run_commands: list[list[str]] = []

    def fake_run(command, **kwargs):
        if command[1:] == ["models"]:
            return subprocess.CompletedProcess(command, 0, "openai/gpt-5.3-codex-spark\n", "")
        if command[1:] == ["--version"]:
            return subprocess.CompletedProcess(command, 0, "1.18.15\n", "")
        assert command[1] == "run"
        run_commands.append(command)
        environment = kwargs["env"]
        state = Path(environment["SPEC2LEAN_PLANNER_SESSION_STATE"])
        output = Path(environment["SPEC2LEAN_PLANNER_SUBMISSION"])
        record_observed_nodes(state, plan)
        invalid = copy.deepcopy(plan)
        invalid["units"][2]["instructionNames"] = []
        first = submit_candidate(
            database=html_database,
            state_path=state,
            output_path=output,
            language="synthetic",
            version="1.0",
            digest=_digest(html_database),
            candidate=invalid,
        )
        assert not first["accepted"]
        second = submit_candidate(
            database=html_database,
            state_path=state,
            output_path=output,
            language="synthetic",
            version="1.0",
            digest=_digest(html_database),
            candidate=plan,
        )
        assert second["accepted"]
        return subprocess.CompletedProcess(command, 0, '{"type":"done"}\n', "")

    monkeypatch.setattr(runner.shutil, "which", lambda _: "/fake/opencode")
    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    result = build_plan(
        database=html_database,
        plan_directory=tmp_path / "plan",
        repository_root=tmp_path,
        expected_language="synthetic",
        expected_version="1.0",
    )
    assert result["status"] == "PASS"
    assert result["openCodeSessions"] == 1
    assert result["submitPlanAttempts"] == 2
    assert len(run_commands) == 1


def test_plan_cli_inspection_and_dot_rendering(html_database, tmp_path):
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(_plan(html_database)), encoding="utf-8")
    output = tmp_path / "plan.dot"
    commands = [
        ("stats", "--plan", str(plan_path)),
        ("units", "--plan", str(plan_path)),
        ("show", "--plan", str(plan_path), "--unit", "synthetic.execution"),
        ("deps", "--plan", str(plan_path), "--unit", "synthetic.execution"),
        ("dependents", "--plan", str(plan_path), "--unit", "synthetic.execution"),
        ("layers", "--plan", str(plan_path)),
        ("scc", "--plan", str(plan_path)),
        ("graph", "--plan", str(plan_path), "--format", "dot", "--output", str(output)),
        ("validate", "--plan", str(plan_path), "--database", str(html_database)),
    ]
    for command in commands:
        result = subprocess.run([str(CLI), "plan", *command], text=True, capture_output=True, check=False)
        assert result.returncode == 0, (command, result.stdout, result.stderr)
    assert output.read_text(encoding="utf-8").startswith("digraph specification_plan")


def test_planner_tools_are_bounded_and_read_only(html_database):
    result = subprocess.run(
        [
            str(CLI), "planner-tool", "tree", "--database", str(html_database),
            "--request", json.dumps({"maxDepth": 2, "limit": 2}),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert len(payload["items"]) == 2
    assert payload["truncated"]
