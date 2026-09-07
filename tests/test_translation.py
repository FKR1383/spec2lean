from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

import pytest

from spec2lean.cli import main
from spec2lean.translation.mcp import TranslationMcpServer, tool_definitions
from spec2lean.translation.groups import group_for_unit, grouped_units
from spec2lean.translation.models import (
    TRANSLATOR_MODEL,
    TRANSLATOR_REASONING,
    TranslationGroupScope,
    semantics_artifact_hash,
)
from spec2lean.translation.prompt import build_translator_prompt
from spec2lean.translation.runner import build_translation, opencode_config
from spec2lean.translation.revision import revise_translation
from spec2lean.translation.store import unit_directory
from spec2lean.translation.validation import (
    forbidden_constructs,
    validate_manifest,
    validate_run_metadata,
    validate_submission,
)


UNIT = {"unitId": "unit:alpha", "name": "alpha.u32", "sourceNodeIds": ["node:alpha"]}
GROUP = "InstructionSemantics"


def _inputs() -> tuple[dict, dict]:
    plan = {
        "schemaVersion": 2,
        "planRunId": "plan:translation-test",
        "language": "synthetic",
        "version": "1.0",
        "sourceDatabaseDigest": "digest:phase1",
        "request": {"scope": {"mode": "EXACT_INSTRUCTIONS"}},
        "requestedUnits": [copy.deepcopy(UNIT)],
        "translationGroups": [{
            "name": GROUP,
            "unitIds": [UNIT["unitId"]],
            "reason": "Derived from the indexed synthetic instruction section.",
            "supportingNodeIds": ["node:alpha"],
            "origin": "INFERRED",
        }],
    }
    semantics = {
        "schemaVersion": 1,
        "phase": "SEMANTIC_EXTRACTOR",
        "planRunId": plan["planRunId"],
        "language": plan["language"],
        "version": plan["version"],
        "unit": copy.deepcopy(UNIT),
        "evidenceBundleHash": "sha256:" + "a" * 64,
        "extractor": {
            "provider": "opencode", "model": TRANSLATOR_MODEL,
            "reasoning": TRANSLATOR_REASONING,
        },
        "runId": "semantic-run:synthetic",
        "createdAt": "2026-01-01T00:00:00.000000Z",
        "outcome": "SUCCESS",
        "semantics": {
            "unitKind": "INSTRUCTION",
            "identity": {"name": "alpha.u32", "evidenceIds": ["evidence:syntax"]},
            "syntaxForms": [],
            "inputs": [
                {"name": "a", "role": "source", "description": "left", "constraints": ["32 bit"], "evidenceIds": ["evidence:op"]},
                {"name": "b", "role": "source", "description": "right", "constraints": ["32 bit"], "evidenceIds": ["evidence:op"]},
            ],
            "result": {"name": "r", "description": "sum", "constraints": ["32 bit"], "evidenceIds": ["evidence:op"]},
            "operation": {"description": "Adds the two bounded inputs.", "inputs": ["a", "b"], "result": "r", "branches": [], "evidenceIds": ["evidence:op"]},
            "edgeCases": [],
            "stateEffects": [{"target": "destination", "effect": "receives r", "evidenceIds": ["evidence:state"]}],
            "predication": {"guard": "p", "whenTrue": "update", "whenFalse": "unchanged", "evidenceIds": ["evidence:guard"]},
            "restrictions": [],
            "dependencies": [],
            "claims": [
                {"claimId": "claim:type", "kind": "DESIGN_DEPENDENCY", "statement": "A minimal destination state is needed.", "evidenceIds": []},
                {"claimId": "claim:op", "kind": "DERIVED_INTERPRETATION", "statement": "The result is bounded addition.", "evidenceIds": ["evidence:op"]},
                {"claimId": "claim:state", "kind": "SOURCE_FACT", "statement": "A true guard writes the result.", "evidenceIds": ["evidence:state", "evidence:guard"]},
            ],
        },
    }
    return plan, semantics


def _scope(plan: dict, semantics: dict) -> TranslationGroupScope:
    return TranslationGroupScope.from_inputs(
        plan, GROUP, {UNIT["unitId"]: semantics},
        created_at="2026-01-02T03:04:05.000000Z"
    )


def _refs(*claim_ids: str) -> list[dict[str, str]]:
    return [{"unitId": UNIT["unitId"], "claimId": claim_id} for claim_id in claim_ids]


def _source() -> str:
    return """namespace Spec2Lean.Synthetic.AlphaU32

structure MachineState where
  destination : BitVec 32

def result (a b : BitVec 32) : BitVec 32 := a + b

def exec (state : MachineState) (guard : Bool) (a b : BitVec 32) : MachineState :=
  if guard then { destination := result a b } else state

end Spec2Lean.Synthetic.AlphaU32
"""


def _submission() -> dict:
    prefix = "Spec2Lean.Synthetic.AlphaU32"
    return {
        "leanSource": _source(),
        "declarations": [
            {"declaration": f"{prefix}.MachineState", "role": "PRIMARY_TYPE", "claimRefs": _refs("claim:type", "claim:state")},
            {"declaration": f"{prefix}.result", "role": "OPERATION", "claimRefs": _refs("claim:op")},
            {"declaration": f"{prefix}.exec", "role": "EXECUTION", "claimRefs": _refs("claim:state", "claim:op")},
        ],
    }


def _codes(diagnostics: list[dict]) -> set[str]:
    return {item["code"] for item in diagnostics}


def test_valid_translation_artifact_and_deterministic_metadata():
    plan, semantics = _inputs()
    scope = _scope(plan, semantics)
    semantics_by_unit = {UNIT["unitId"]: semantics}
    candidate, diagnostics = validate_submission(scope, semantics_by_unit, _submission())
    assert diagnostics == [] and candidate is not None
    manifest = candidate["manifest"]
    assert manifest["semanticsArtifacts"] == [{
        "unitId": UNIT["unitId"], "runId": semantics["runId"],
        "artifactHash": semantics_artifact_hash(semantics),
    }]
    assert manifest["translator"] == {
        "provider": "rust-harness", "model": TRANSLATOR_MODEL, "reasoning": TRANSLATOR_REASONING,
    }
    assert manifest["target"] == {"language": "Lean", "version": "4"}
    assert validate_manifest(plan, semantics_by_unit, candidate["leanSource"], manifest) == []

    metadata = {
        "schemaVersion": 2, "phase": "LLM_GROUP_TRANSLATOR", "planRunId": scope.plan_run_id,
        "group": {"name": GROUP, "unitIds": [UNIT["unitId"]]},
        "translationRunId": scope.translation_run_id,
        "translator": "opencode", "model": TRANSLATOR_MODEL, "reasoning": TRANSLATOR_REASONING,
        "singleSession": True, "automaticRetries": 0,
        "semanticsArtifacts": [{
            "unitId": UNIT["unitId"], "runId": semantics["runId"],
            "artifactHash": semantics_artifact_hash(semantics),
        }],
        "inputBoundary": "PHASE_4_SEMANTIC_ARTIFACTS_ONLY",
        "targetLanguage": "Lean", "targetVersion": "4",
        "startedAt": "start", "finishedAt": "finish", "command": [], "exitCode": 0,
        "outcome": "SUCCESS", "error": None,
        "semanticsArtifactPaths": ["/synthetic/semantics.json"], "sessionId": None,
        "stdout": "", "stderr": "",
    }
    assert validate_run_metadata(scope, metadata) == []

    for historical_model in ("openai/gpt-5.4-mini", "openai/gpt-5.3-codex-spark"):
        historical_manifest = copy.deepcopy(manifest)
        historical_manifest["translator"].update(model=historical_model, reasoning="low")
        assert validate_manifest(plan, semantics_by_unit, candidate["leanSource"], historical_manifest) == []
        historical_metadata = copy.deepcopy(metadata)
        historical_metadata.update(model=historical_model, reasoning="low")
        assert validate_run_metadata(scope, historical_metadata) == []


def test_stale_semantic_hash_is_rejected():
    plan, semantics = _inputs()
    semantics_by_unit = {UNIT["unitId"]: semantics}
    candidate, diagnostics = validate_submission(_scope(plan, semantics), semantics_by_unit, _submission())
    assert diagnostics == [] and candidate is not None
    candidate["manifest"]["semanticsArtifacts"][0]["artifactHash"] = "sha256:" + "0" * 64
    assert "DETERMINISTIC_MISMATCH" in _codes(
        validate_manifest(plan, semantics_by_unit, candidate["leanSource"], candidate["manifest"])
    )


def test_unknown_claim_and_operation_without_mapping_are_rejected():
    plan, semantics = _inputs()
    unknown = _submission()
    unknown["declarations"][1]["claimRefs"] = _refs("claim:invented")
    semantics_by_unit = {UNIT["unitId"]: semantics}
    _, diagnostics = validate_submission(_scope(plan, semantics), semantics_by_unit, unknown)
    assert "UNKNOWN_SEMANTIC_CLAIM" in _codes(diagnostics)
    missing_operation = _submission()
    del missing_operation["declarations"][1]
    _, diagnostics = validate_submission(_scope(plan, semantics), semantics_by_unit, missing_operation)
    assert _codes(diagnostics) >= {"MISSING_OPERATION_MAPPING", "UNMAPPED_LEAN_DECLARATION"}


def test_group_scope_supports_multiple_units_and_unit_scoped_claim_ids():
    plan, alpha_semantics = _inputs()
    beta_unit = {"unitId": "unit:beta", "name": "beta.u32", "sourceNodeIds": ["node:beta"]}
    beta_semantics = copy.deepcopy(alpha_semantics)
    beta_semantics["unit"] = copy.deepcopy(beta_unit)
    beta_semantics["runId"] = "semantic-run:beta"
    beta_semantics["semantics"]["identity"]["name"] = "beta.u32"
    plan["requestedUnits"].append(copy.deepcopy(beta_unit))
    plan["translationGroups"][0]["unitIds"].append(beta_unit["unitId"])
    plan["translationGroups"][0]["supportingNodeIds"].append("node:beta")
    semantics_by_unit = {
        UNIT["unitId"]: alpha_semantics,
        beta_unit["unitId"]: beta_semantics,
    }
    scope = TranslationGroupScope.from_inputs(
        plan, GROUP, semantics_by_unit, created_at="2026-01-02T03:04:05.000000Z"
    )
    source = """namespace Spec2Lean.Synthetic.Other

structure MachineState where
  destination : BitVec 32

def alphaResult (a b : BitVec 32) : BitVec 32 := a + b
def alphaExec (s : MachineState) (p : Bool) (a b : BitVec 32) : MachineState :=
  if p then { destination := alphaResult a b } else s
def betaResult (a b : BitVec 32) : BitVec 32 := a + b
def betaExec (s : MachineState) (p : Bool) (a b : BitVec 32) : MachineState :=
  if p then { destination := betaResult a b } else s

end Spec2Lean.Synthetic.Other
"""
    prefix = "Spec2Lean.Synthetic.Other"
    declarations = [
        {
            "declaration": f"{prefix}.MachineState", "role": "PRIMARY_TYPE",
            "claimRefs": [
                {"unitId": UNIT["unitId"], "claimId": "claim:type"},
                {"unitId": beta_unit["unitId"], "claimId": "claim:type"},
            ],
        },
        {"declaration": f"{prefix}.alphaResult", "role": "OPERATION", "claimRefs": _refs("claim:op")},
        {"declaration": f"{prefix}.alphaExec", "role": "EXECUTION", "claimRefs": _refs("claim:state", "claim:op")},
        {
            "declaration": f"{prefix}.betaResult", "role": "OPERATION",
            "claimRefs": [{"unitId": beta_unit["unitId"], "claimId": "claim:op"}],
        },
        {
            "declaration": f"{prefix}.betaExec", "role": "EXECUTION",
            "claimRefs": [
                {"unitId": beta_unit["unitId"], "claimId": "claim:state"},
                {"unitId": beta_unit["unitId"], "claimId": "claim:op"},
            ],
        },
    ]
    candidate, diagnostics = validate_submission(
        scope, semantics_by_unit, {"leanSource": source, "declarations": declarations}
    )
    assert diagnostics == [] and candidate is not None
    assert scope.lean_file == f"{GROUP}.lean"
    assert candidate["manifest"]["group"] == {
        "name": GROUP, "unitIds": [UNIT["unitId"], beta_unit["unitId"]]
    }
    assert len(candidate["manifest"]["semanticsArtifacts"]) == 2


def test_group_mapping_comes_only_from_the_phase2_plan():
    plan, _ = _inputs()
    assert group_for_unit(plan, UNIT["unitId"]) == GROUP
    assert grouped_units(plan) == {GROUP: [UNIT]}
    plan["requestedUnits"][0]["name"] = "completely.unknown.mnemonic"
    assert group_for_unit(plan, UNIT["unitId"]) == GROUP
    del plan["translationGroups"]
    with pytest.raises(ValueError, match="rerun from the plan phase"):
        grouped_units(plan)


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("def bad : Nat := sorry", "FORBIDDEN_SORRY"),
        ("theorem bad : True := by admit", "FORBIDDEN_ADMIT"),
        ("axiom bad : False", "FORBIDDEN_AXIOM"),
        ("constant bad : False", "FORBIDDEN_CONSTANT"),
        ("unsafe def bad : Nat := 0", "FORBIDDEN_UNSAFE"),
        ("partial def bad : Nat := bad", "FORBIDDEN_PARTIAL"),
    ],
)
def test_forbidden_construct_checks_ignore_comments_but_reject_code(text, code):
    assert code in _codes(forbidden_constructs(text))
    assert forbidden_constructs(f"-- {text}\n/- nested /- {text} -/ comment -/\ndef good := 0") == []


def test_structured_translator_submission_tool(tmp_path):
    plan, semantics = _inputs()
    scope = _scope(plan, semantics)
    path = tmp_path / "submission.json"
    server = TranslationMcpServer(scope, {UNIT["unitId"]: semantics}, path)
    response = server.call_tool("submit_translation", _submission())
    result = json.loads(response["content"][0]["text"])
    assert result["accepted"] is True and path.is_file()
    stored = json.loads(path.read_text())
    assert stored["manifest"]["translationRunId"] == scope.translation_run_id
    assert [item["name"] for item in tool_definitions()] == ["submit_translation"]
    assert tool_definitions()[0]["inputSchema"]["required"] == ["leanSource", "declarations"]


def test_implementation_helper_may_trace_through_supported_semantic_declaration():
    plan, semantics = _inputs()
    submission = _submission()
    submission["leanSource"] = submission["leanSource"].replace(
        "def result", "def addImpl (a b : BitVec 32) : BitVec 32 := a + b\n\ndef result"
    )
    operation = "Spec2Lean.Synthetic.AlphaU32.result"
    submission["declarations"].insert(1, {
        "declaration": "Spec2Lean.Synthetic.AlphaU32.addImpl",
        "role": "IMPLEMENTATION_HELPER",
        "claimRefs": [],
        "supportsDeclarations": [operation],
    })
    candidate, diagnostics = validate_submission(
        _scope(plan, semantics), {UNIT["unitId"]: semantics}, submission
    )
    assert diagnostics == [] and candidate is not None
    assert candidate["manifest"]["declarations"][1]["supportsDeclarations"] == [operation]


def _write_inputs(tmp_path: Path) -> tuple[dict, dict, Path, Path, Path]:
    plan, semantics = _inputs()
    plans_root, semantics_root, evidence_root = tmp_path / "plans", tmp_path / "semantics", tmp_path / "evidence"
    plan_dir = plans_root / "synthetic" / "1.0" / plan["planRunId"]
    plan_dir.mkdir(parents=True)
    (plan_dir / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    semantic_dir = semantics_root / "synthetic" / "1.0" / plan["planRunId"] / "alpha-u32-alpha"
    semantic_dir.mkdir(parents=True)
    (semantic_dir / "semantics.json").write_text(json.dumps(semantics), encoding="utf-8")
    return plan, semantics, plans_root, semantics_root, evidence_root


def test_missing_semantic_input_stops_before_session(tmp_path):
    plan, _ = _inputs()
    with pytest.raises(FileNotFoundError, match="semantic artifact does not exist"):
        build_translation(plan, tmp_path / "semantics", tmp_path / "translations", unit_id=UNIT["unitId"])


def test_runner_uses_one_session_exact_model_and_phase4_only_input(tmp_path, monkeypatch):
    plan, _, _, semantics_root, _ = _write_inputs(tmp_path)
    calls = []
    monkeypatch.setattr("spec2lean.translation.runner.shutil.which", lambda _: "/usr/bin/opencode")
    monkeypatch.setattr("spec2lean.translation.runner.installed_openai_models", lambda _: {TRANSLATOR_MODEL})

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        config = json.loads(kwargs["env"]["OPENCODE_CONFIG_CONTENT"])
        mcp_command = config["mcp"]["translation"]["command"]
        def argument(name):
            return Path(mcp_command[mcp_command.index(name) + 1])
        scope = TranslationGroupScope.from_dict(json.loads(argument("--scope").read_text()))
        semantics = json.loads(argument("--semantics").read_text())
        server = TranslationMcpServer(scope, semantics, argument("--submission"))
        result = server.call_tool("submit_translation", _submission())
        assert json.loads(result["content"][0]["text"])["accepted"] is True
        return subprocess.CompletedProcess(command, 0, '{"sessionID":"translator-session"}\n', "")

    output = build_translation(
        plan, semantics_root, tmp_path / "translations", unit_id=UNIT["unitId"], run_command=fake_run
    )
    assert len(calls) == 1
    assert {path.name for path in output.iterdir()} == {
        f"{GROUP}.lean", "translation-manifest.json", "translator-run.json",
    }
    metadata = json.loads((output / "translator-run.json").read_text())
    assert metadata["model"] == TRANSLATOR_MODEL == "openai/gpt-5.6-sol"
    assert metadata["reasoning"] == TRANSLATOR_REASONING == "medium"
    assert metadata["singleSession"] is True and metadata["automaticRetries"] == 0
    assert metadata["inputBoundary"] == "PHASE_4_SEMANTIC_ARTIFACTS_ONLY"
    assert metadata["sessionId"] == "translator-session"
    agent = json.loads(calls[0][1]["env"]["OPENCODE_CONFIG_CONTENT"])["agent"]["spec2lean-lean-translator"]
    assert agent["model"] == TRANSLATOR_MODEL and agent["variant"] == "medium"
    for forbidden in ("bash", "edit", "read", "task", "webfetch", "websearch", "skill"):
        assert agent["tools"][forbidden] is False


def test_missing_exact_model_starts_no_session_and_creates_no_artifact(tmp_path, monkeypatch):
    plan, _, _, semantics_root, _ = _write_inputs(tmp_path)
    monkeypatch.setattr("spec2lean.translation.runner.shutil.which", lambda _: "/usr/bin/opencode")
    monkeypatch.setattr(
        "spec2lean.translation.runner.installed_openai_models", lambda _: {"openai/gpt-5.3-codex"}
    )
    invoked = False
    def must_not_run(*args, **kwargs):
        nonlocal invoked
        invoked = True
        raise AssertionError
    output = tmp_path / "translations"
    with pytest.raises(RuntimeError, match="required OpenCode Lean Translator model is unavailable"):
        build_translation(
            plan, semantics_root, output, unit_id=UNIT["unitId"], run_command=must_not_run
        )
    assert invoked is False and not output.exists()


def test_traceability_chain_resolves_declaration_claim_evidence_and_source(tmp_path, capsys):
    plan, semantics, plans_root, semantics_root, evidence_root = _write_inputs(tmp_path)
    scope = _scope(plan, semantics)
    candidate, diagnostics = validate_submission(
        scope, {UNIT["unitId"]: semantics}, _submission()
    )
    assert diagnostics == [] and candidate is not None
    translations_root = tmp_path / "translations"
    output = unit_directory(translations_root, plan, UNIT)
    output.mkdir(parents=True)
    (output / f"{GROUP}.lean").write_text(candidate["leanSource"], encoding="utf-8")
    (output / "translation-manifest.json").write_text(json.dumps(candidate["manifest"]), encoding="utf-8")
    (output / "translator-run.json").write_text(json.dumps({"outcome": "SUCCESS"}), encoding="utf-8")
    evidence_dir = evidence_root / "synthetic" / "1.0" / plan["planRunId"] / "alpha"
    evidence_dir.mkdir(parents=True)
    records = []
    for evidence_id in ("evidence:op", "evidence:state", "evidence:guard"):
        records.append({
            "evidenceId": evidence_id, "unitId": UNIT["unitId"], "role": "OPERATION", "tier": "CORE",
            "sourceNodeId": "node:alpha", "sourceNodeIds": ["node:alpha"], "sourceSpanIds": ["span:alpha"],
            "sourceType": "html", "documentId": "doc:spec", "documentSha256": "a" * 64,
            "officialUrl": "https://example.test/spec", "exactText": "Synthetic source text.",
        })
    (evidence_dir / "evidence.json").write_text(json.dumps({"evidence": records}), encoding="utf-8")
    declaration = "Spec2Lean.Synthetic.AlphaU32.exec"
    assert main([
        "translate", "trace", "--declaration", declaration,
        "--translations-root", str(translations_root), "--semantics-root", str(semantics_root),
        "--evidence-root", str(evidence_root),
    ]) == 0
    trace = json.loads(capsys.readouterr().out)
    assert trace["declaration"]["declaration"] == declaration
    assert trace["claims"][0]["claim"]["claimId"] == "claim:state"
    assert trace["claims"][0]["evidence"][0]["sourceNodeIds"] == ["node:alpha"]


def test_bounded_translation_revision_updates_existing_artifact_and_keeps_build_prompt(tmp_path):
    plan, semantics, _, semantics_root, _ = _write_inputs(tmp_path)
    scope = _scope(plan, semantics)
    original, diagnostics = validate_submission(
        scope, {UNIT["unitId"]: semantics}, _submission()
    )
    assert diagnostics == [] and original is not None
    translations_root = tmp_path / "translations"
    directory = unit_directory(translations_root, plan, UNIT)
    directory.mkdir(parents=True)
    (directory / f"{GROUP}.lean").write_text(original["leanSource"], encoding="utf-8")
    (directory / "translation-manifest.json").write_text(json.dumps(original["manifest"]), encoding="utf-8")
    (directory / "translator-run.json").write_text("{}", encoding="utf-8")
    uncovered = [{"itemType": "SEMANTIC_CLAIM", "itemId": "claim:op", "declarations": []}]
    calls = []

    def fake_session(context, *, timeout_seconds):
        calls.append(context)
        revised = _submission()
        revised["leanSource"] = revised["leanSource"].replace(
            "def result", "def operationMeaning (a b : BitVec 32) : BitVec 32 := a + b\n\ndef result"
        )
        revised["declarations"].append({
            "declaration": "Spec2Lean.Synthetic.AlphaU32.operationMeaning",
            "role": "SEMANTIC_HELPER", "claimRefs": _refs("claim:op"),
        })
        candidate, inner = validate_submission(
            TranslationGroupScope.from_dict(context["scope"]), context["semanticsByUnit"], revised
        )
        assert inner == []
        return {"candidate": candidate, "error": None, "session": {"sessionId": "translation-revision"}}

    revision_directory, metadata = revise_translation(
        plan, semantics_root=semantics_root, translations_root=translations_root,
        unit_id=UNIT["unitId"], diagnostics=uncovered, session_runner=fake_session,
        source_check_hash="sha256:" + "1" * 64,
        now=lambda: "2026-08-27T00:00:00Z",
    )
    assert len(calls) == 1 and calls[0]["diagnostics"] == uncovered
    assert metadata["singleSession"] is True and metadata["automaticRetries"] == 0
    assert (revision_directory / f"before-{GROUP}.lean").is_file()
    source = (directory / f"{GROUP}.lean").read_text()
    manifest = json.loads((directory / "translation-manifest.json").read_text())
    assert "operationMeaning" in source and validate_manifest(
        plan, {UNIT["unitId"]: semantics}, source, manifest
    ) == []
    assert "bounded Spec2Lean Phase-5 Lean translation revision" not in build_translator_prompt(
        scope, {UNIT["unitId"]: semantics}
    )
    with pytest.raises(FileExistsError, match="already consumed"):
        revise_translation(
            plan, semantics_root=semantics_root, translations_root=translations_root,
            unit_id=UNIT["unitId"], diagnostics=uncovered, session_runner=fake_session,
            source_check_hash="sha256:" + "1" * 64,
        )
    assert len(calls) == 1
