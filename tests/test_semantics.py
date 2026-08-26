from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

import pytest

from spec2lean.cli import main
from spec2lean.semantics.mcp import SemanticsMcpServer, tool_definitions
from spec2lean.semantics.models import (
    EXTRACTOR_MODEL, EXTRACTOR_REASONING, SemanticScope, evidence_bundle_hash,
)
from spec2lean.semantics.prompt import build_extractor_prompt
from spec2lean.semantics.render import render_markdown
from spec2lean.semantics.revision import revise_semantics
from spec2lean.semantics.runner import build_semantics, opencode_config
from spec2lean.semantics.store import unit_directory
from spec2lean.semantics.validation import validate_artifact, validate_submission


UNIT = {"unitId": "unit:alpha", "name": "alpha.u32", "sourceNodeIds": ["node:alpha"]}


def _record(evidence_id: str, role: str) -> dict:
    return {
        "evidenceId": evidence_id, "unitId": UNIT["unitId"], "role": role, "tier": "CORE",
        "documentId": "doc:spec", "documentSha256": "a" * 64, "sourceType": "html",
        "sourceNodeId": "node:alpha", "sourceNodeIds": ["node:alpha"], "sourceSpanIds": [],
        "exactText": f"Synthetic {role} specification text.",
    }


def _inputs() -> tuple[dict, dict]:
    plan = {
        "schemaVersion": 1, "planRunId": "plan:semantic-test", "language": "synthetic", "version": "1.0",
        "sourceDatabaseDigest": "digest:phase1", "request": {"scope": {"mode": "EXACT_INSTRUCTIONS"}},
        "requestedUnits": [copy.deepcopy(UNIT)],
    }
    bundle = {
        "schemaVersion": 1, "phase": "RETRIEVE_EVIDENCE", "planRunId": plan["planRunId"],
        "language": plan["language"], "version": plan["version"],
        "sourceDatabaseDigest": plan["sourceDatabaseDigest"], "unit": copy.deepcopy(UNIT),
        "evidence": [
            _record("evidence:operation", "OPERATION"), _record("evidence:algorithm", "ALGORITHM"),
            _record("evidence:syntax", "SYNTAX"), _record("evidence:operands", "OPERANDS"),
            _record("evidence:edge", "EDGE_CASE"), _record("evidence:state", "STATE_EFFECT"),
            _record("evidence:guard", "PREDICATION"), _record("evidence:version", "VERSION_OR_TARGET_RESTRICTION"),
        ],
    }
    return plan, bundle


def _scope(plan: dict, bundle: dict) -> SemanticScope:
    return SemanticScope.from_inputs(plan, bundle, UNIT["unitId"], created_at="2026-01-02T03:04:05.000000Z")


def _submission() -> dict:
    return {
        "outcome": "SUCCESS", "unitKind": "INSTRUCTION",
        "identity": {"name": "alpha.u32", "form": "alpha.u32 d, a", "description": "Synthetic instruction.", "evidenceIds": ["evidence:syntax"]},
        "syntaxForms": [{"form": "alpha.u32 d, a", "description": "One destination and source.", "evidenceIds": ["evidence:syntax"]}],
        "inputs": [{"name": "a", "role": "source", "description": "Input value.", "constraints": ["32-bit value"], "evidenceIds": ["evidence:operands"]}],
        "result": {"name": "r", "description": "Computed 32-bit result.", "constraints": ["32-bit value"], "evidenceIds": ["evidence:operation"]},
        "operation": {
            "description": "Computes the synthetic transformation of the source value.",
            "inputs": ["a"], "result": "The transformed value r.", "evidenceIds": ["evidence:operation"],
            "branches": [{"condition": "a is zero", "behavior": "produce zero", "evidenceIds": ["evidence:algorithm"]}],
        },
        "edgeCases": [{"condition": "a is maximal", "behavior": "use the stated bounded behavior", "evidenceIds": ["evidence:edge"]}],
        "stateEffects": [{"target": "destination d", "effect": "receives r", "evidenceIds": ["evidence:state"]}],
        "predication": {"guard": "predicate p", "whenTrue": "perform the instruction", "whenFalse": "leave destination unchanged", "evidenceIds": ["evidence:guard"]},
        "restrictions": [{"kind": "VERSION", "description": "Available since version 1.0.", "evidenceIds": ["evidence:version"]}],
        "dependencies": [{"concept": "finite-width values", "description": "Needs a reusable 32-bit value domain.", "evidenceIds": []}],
        "claims": [
            {"claimId": "claim:source", "kind": "SOURCE_FACT", "statement": "The instruction computes a transformed result.", "evidenceIds": ["evidence:operation"]},
            {"claimId": "claim:derived", "kind": "DERIVED_INTERPRETATION", "statement": "The algorithm is a piecewise operation.", "evidenceIds": ["evidence:algorithm"]},
            {"claimId": "claim:design", "kind": "DESIGN_DEPENDENCY", "statement": "A finite-width value model is needed.", "evidenceIds": []},
            {"claimId": "claim:assumption", "kind": "ASSUMPTION", "statement": "The surrounding state supplies valid operands.", "evidenceIds": []},
        ],
    }


def _codes(diagnostics: list[dict]) -> set[str]:
    return {item["code"] for item in diagnostics}


def test_valid_semantics_covers_operation_branches_edges_state_claims_metadata_and_rendering():
    plan, bundle = _inputs()
    scope = _scope(plan, bundle)
    artifact, diagnostics = validate_submission(scope, bundle, _submission())
    assert diagnostics == [] and artifact is not None
    assert artifact["evidenceBundleHash"] == evidence_bundle_hash(bundle)
    assert artifact["extractor"] == {"provider": "opencode", "model": EXTRACTOR_MODEL, "reasoning": "low"}
    assert validate_artifact(plan, bundle, artifact) == []
    rendered = render_markdown(artifact)
    for text in ("CORE OPERATION", "Branches", "SOURCE FACTS", "DERIVED INTERPRETATIONS", "STATE EFFECTS", "EDGE CASES", "ASSUMPTIONS"):
        assert text in rendered
    assert "Lean" not in rendered


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (lambda value: value["claims"][0].update(evidenceIds=[]), "MISSING_EVIDENCE"),
        (lambda value: value["claims"][1].update(evidenceIds=[]), "MISSING_EVIDENCE"),
        (lambda value: value["claims"][0].update(evidenceIds=["evidence:unknown"]), "UNKNOWN_EVIDENCE_ID"),
        (lambda value: value["claims"][1].update(claimId="claim:source"), "DUPLICATE_CLAIM_ID"),
        (lambda value: value["claims"][1].update(kind="OPEN_QUESTION"), "INVALID_CLAIM_KIND"),
    ],
)
def test_claim_validation_failures(mutate, code):
    plan, bundle = _inputs()
    value = _submission()
    mutate(value)
    _, diagnostics = validate_submission(_scope(plan, bundle), bundle, value)
    assert code in _codes(diagnostics)


def test_instruction_missing_operation_and_guard_only_operation_are_rejected():
    plan, bundle = _inputs()
    missing = _submission()
    del missing["operation"]
    _, diagnostics = validate_submission(_scope(plan, bundle), bundle, missing)
    assert "MISSING_OPERATION" in _codes(diagnostics)
    guard_only = _submission()
    guard_only["operation"]["evidenceIds"] = ["evidence:guard"]
    _, diagnostics = validate_submission(_scope(plan, bundle), bundle, guard_only)
    assert "NONFUNCTIONAL_OPERATION" in _codes(diagnostics)


def test_unknown_branch_and_state_evidence_and_unsupported_fields_are_rejected():
    plan, bundle = _inputs()
    value = _submission()
    value["operation"]["branches"][0]["evidenceIds"] = ["evidence:nope"]
    value["stateEffects"][0]["evidenceIds"] = ["evidence:nope"]
    value["leanType"] = "Nat"
    _, diagnostics = validate_submission(_scope(plan, bundle), bundle, value)
    assert _codes(diagnostics) >= {"UNKNOWN_EVIDENCE_ID", "UNEXPECTED_FIELD"}


def test_insufficient_evidence_is_a_structured_accepted_failure():
    plan, bundle = _inputs()
    artifact, diagnostics = validate_submission(_scope(plan, bundle), bundle, {
        "outcome": "INSUFFICIENT_EVIDENCE", "missingAspects": ["Result behavior for maximal input"],
        "explanation": "The supplied evidence states syntax but not this result case.",
        "evidenceIds": ["evidence:syntax"],
    })
    assert diagnostics == []
    assert artifact["outcome"] == "INSUFFICIENT_EVIDENCE"
    assert "INSUFFICIENT EVIDENCE" in render_markdown(artifact)


def test_tool_and_opencode_config_expose_submission_only(tmp_path):
    assert [item["name"] for item in tool_definitions()] == ["submit_semantics"]
    schema = tool_definitions()[0]["inputSchema"]
    assert schema["type"] == "object"
    assert "oneOf" not in schema
    assert schema["required"] == ["outcome"]
    config = opencode_config(tmp_path / "scope", tmp_path / "evidence", tmp_path / "submission")
    agent = config["agent"]["spec2lean-semantic-extractor"]
    assert agent["model"] == EXTRACTOR_MODEL == "openai/gpt-5.3-codex-spark"
    assert agent["variant"] == EXTRACTOR_REASONING == "low"
    for forbidden in ("bash", "edit", "read", "task", "webfetch", "websearch", "skill"):
        assert agent["tools"][forbidden] is False


def _write_inputs(tmp_path: Path) -> tuple[dict, dict, Path, Path]:
    plan, bundle = _inputs()
    plans_root, evidence_root = tmp_path / "plans", tmp_path / "evidence"
    plan_dir = plans_root / "synthetic" / "1.0" / plan["planRunId"]
    plan_dir.mkdir(parents=True)
    (plan_dir / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    evidence_dir = evidence_root / "synthetic" / "1.0" / plan["planRunId"] / "alpha"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "evidence.json").write_text(json.dumps(bundle), encoding="utf-8")
    (evidence_dir / "retriever-run.json").write_text(json.dumps({"unitId": UNIT["unitId"], "outcome": "VALID"}), encoding="utf-8")
    return plan, bundle, plans_root, evidence_root


def test_runner_uses_one_fake_session_and_records_deterministic_configuration(tmp_path, monkeypatch):
    plan, _, _, evidence_root = _write_inputs(tmp_path)
    calls = []
    monkeypatch.setattr("spec2lean.semantics.runner.shutil.which", lambda _: "/usr/bin/opencode")
    monkeypatch.setattr("spec2lean.semantics.runner.installed_openai_models", lambda _: {EXTRACTOR_MODEL})

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        config = json.loads(kwargs["env"]["OPENCODE_CONFIG_CONTENT"])
        mcp_command = config["mcp"]["semantics"]["command"]
        def argument(name):
            return Path(mcp_command[mcp_command.index(name) + 1])
        scope = SemanticScope.from_dict(json.loads(argument("--scope").read_text()))
        bundle = json.loads(argument("--evidence").read_text())
        server = SemanticsMcpServer(scope, bundle, argument("--submission"))
        response = server.call_tool("submit_semantics", _submission())
        assert json.loads(response["content"][0]["text"])["accepted"] is True
        return subprocess.CompletedProcess(command, 0, '{"sessionID":"semantic-session"}\n', "")

    root = build_semantics(plan, evidence_root, tmp_path / "semantics", unit_ids=[UNIT["unitId"]], run_command=fake_run)
    assert len(calls) == 1
    unit_dir = next(root.iterdir())
    assert {path.name for path in unit_dir.iterdir()} == {"semantics.json", "semantics.md", "extractor-run.json"}
    metadata = json.loads((unit_dir / "extractor-run.json").read_text())
    assert metadata["model"] == EXTRACTOR_MODEL
    assert metadata["reasoning"] == EXTRACTOR_REASONING
    assert metadata["singleSession"] is True and metadata["automaticRetries"] == 0
    assert metadata["inputBoundary"] == "PHASE_3_UNIT_EVIDENCE_BUNDLE_ONLY"
    assert metadata["sessionId"] == "semantic-session"


def test_semantics_inspection_cli_is_deterministic_and_does_not_run_opencode(tmp_path, capsys):
    plan, bundle, plans_root, evidence_root = _write_inputs(tmp_path)
    scope = _scope(plan, bundle)
    artifact, diagnostics = validate_submission(scope, bundle, _submission())
    assert diagnostics == []
    semantics_root = tmp_path / "semantics"
    directory = unit_directory(semantics_root, plan, UNIT)
    directory.mkdir(parents=True)
    (directory / "semantics.json").write_text(json.dumps(artifact), encoding="utf-8")
    (directory / "extractor-run.json").write_text(json.dumps({"outcome": "SUCCESS"}), encoding="utf-8")
    common = ["--plans-root", str(plans_root), "--semantics-root", str(semantics_root)]
    for command in ("show", "claims", "operation"):
        assert main(["semantics", command, "--plan-run", plan["planRunId"], "--unit", UNIT["unitId"], *common]) == 0
        json.loads(capsys.readouterr().out)
    assert main(["semantics", "stats", "--plan-run", plan["planRunId"], *common]) == 0
    assert json.loads(capsys.readouterr().out)["successfulArtifacts"] == 1
    assert main([
        "semantics", "evidence", "--claim", "claim:source", "--semantics-root", str(semantics_root),
        "--evidence-root", str(evidence_root),
    ]) == 0
    resolved = json.loads(capsys.readouterr().out)
    assert resolved["evidence"][0]["evidenceId"] == "evidence:operation"


def test_missing_exact_model_starts_no_session_and_creates_no_artifact(tmp_path, monkeypatch):
    plan, _, _, evidence_root = _write_inputs(tmp_path)
    monkeypatch.setattr("spec2lean.semantics.runner.shutil.which", lambda _: "/usr/bin/opencode")
    monkeypatch.setattr("spec2lean.semantics.runner.installed_openai_models", lambda _: {"openai/gpt-5.3-codex"})
    invoked = False
    def must_not_run(*args, **kwargs):
        nonlocal invoked
        invoked = True
        raise AssertionError
    output = tmp_path / "semantics"
    with pytest.raises(RuntimeError, match="required OpenCode Semantic Extractor model is unavailable"):
        build_semantics(plan, evidence_root, output, unit_ids=[UNIT["unitId"]], run_command=must_not_run)
    assert invoked is False and not output.exists()


def test_bounded_semantic_revision_uses_trace_diagnostics_and_preserves_original_prompt(tmp_path):
    plan, bundle, _, evidence_root = _write_inputs(tmp_path)
    semantics_root = tmp_path / "semantics"
    directory = unit_directory(semantics_root, plan, UNIT)
    directory.mkdir(parents=True)
    original_scope = _scope(plan, bundle)
    original, diagnostics = validate_submission(original_scope, bundle, _submission())
    assert diagnostics == [] and original is not None
    (directory / "semantics.json").write_text(json.dumps(original), encoding="utf-8")
    (directory / "semantics.md").write_text(render_markdown(original), encoding="utf-8")
    (directory / "extractor-run.json").write_text("{}", encoding="utf-8")
    broken = [{"code": "MISSING_EVIDENCE", "message": "claim evidence must be revalidated"}]
    calls = []

    def fake_session(context, *, timeout_seconds):
        calls.append(context)
        scope = SemanticScope.from_dict(context["scope"])
        artifact, inner = validate_submission(scope, context["evidence"], _submission())
        assert inner == []
        return {"artifact": artifact, "error": None, "session": {"sessionId": "semantic-revision"}}

    revision_directory, metadata = revise_semantics(
        plan, evidence_root=evidence_root, semantics_root=semantics_root,
        unit_id=UNIT["unitId"], diagnostics=broken, session_runner=fake_session,
        now=lambda: "2026-08-27T00:00:00Z",
    )
    assert len(calls) == 1 and calls[0]["diagnostics"] == broken
    assert metadata["singleSession"] is True and metadata["automaticRetries"] == 0
    assert (revision_directory / "before-semantics.json").is_file()
    assert json.loads((directory / "semantics.json").read_text())["createdAt"] == "2026-08-27T00:00:00Z"
    assert "bounded Spec2Lean Phase-4 semantic revision" not in build_extractor_prompt(original_scope, bundle)
