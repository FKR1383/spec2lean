from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from spec2lean.cli import main
from spec2lean.evidence.runner import unit_directory_name
from spec2lean.translation.models import TranslationGroupScope
from spec2lean.translation.validation import validate_manifest
from spec2lean.troubleshooting.models import (
    NO_ACTION,
    REPAIR_BUILD,
    RETURN_TO_SEMANTIC_EXTRACTOR,
    RETURN_TO_TRANSLATOR,
    TROUBLESHOOTER_MODEL,
    TROUBLESHOOTER_REASONING,
    action_for,
)
from spec2lean.troubleshooting.mcp import TroubleshootingMcpServer, tool_definitions
from spec2lean.troubleshooting.opencode import opencode_config, run_opencode_repair
from spec2lean.troubleshooting.prompt import build_troubleshooter_prompt
from spec2lean.troubleshooting.resolver import resolve_check_failure
from spec2lean.troubleshooting.runner import run_troubleshooter
from spec2lean.troubleshooting.validation import validate_repair_submission


UNIT = {"unitId": "unit:repair", "name": "repair.unit", "sourceNodeIds": ["node:repair"]}
GROUP = "InstructionSemantics"
SOURCE = """namespace Spec2Lean.Repair

def operation (a b : Nat) : Nat := a + b

end Spec2Lean.Repair
"""
REPAIRED_SOURCE = SOURCE.replace("a + b", "Nat.add a b")


def _plan() -> dict:
    return {
        "schemaVersion": 2,
        "planRunId": "plan:troubleshooting-test",
        "language": "synthetic",
        "version": "1.0",
        "requestedUnits": [dict(UNIT)],
        "translationGroups": [{
            "name": GROUP,
            "unitIds": [UNIT["unitId"]],
            "reason": "Derived from the indexed synthetic instruction section.",
            "supportingNodeIds": ["node:repair"],
            "origin": "INFERRED",
        }],
    }


def _check(build: str, coverage: str, traceability: str) -> dict:
    return {
        "schemaVersion": 1,
        "phase": "CHECK",
        "planRunId": "plan:troubleshooting-test",
        "language": "synthetic",
        "version": "1.0",
        "unit": dict(UNIT),
        "translationRunId": "translation-run:placeholder",
        "status": "PASS" if (build, coverage, traceability) == ("PASS", "PASS", "PASS") else "FAIL",
        "build": {
            "status": build,
            "exitCode": 0 if build == "PASS" else 1,
            "leanVersion": "Lean (version 4.test)",
            "durationMs": 1,
            "diagnostics": [] if build == "PASS" else [{
                "stream": "stderr",
                "severity": "ERROR",
                "message": "type mismatch",
                "file": "Unit.lean",
                "line": 3,
                "column": 1,
            }],
        },
        "coverage": {
            "status": coverage,
            "covered": [],
            "uncovered": [] if coverage == "PASS" else [{
                "itemType": "SEMANTIC_CLAIM",
                "itemId": "claim:operation",
                "declarations": [],
            }],
        },
        "traceability": {
            "status": traceability,
            "validMappings": [],
            "brokenMappings": [] if traceability == "PASS" else [{
                "code": "MISSING_EVIDENCE",
                "message": "claim references absent evidence",
                "semanticClaimId": "claim:operation",
            }],
        },
        "routing": {"next": []},
    }


def _write_plan_and_check(tmp_path: Path, check: dict) -> tuple[dict, dict[str, Path]]:
    plan = _plan()
    roots = {name: tmp_path / name for name in (
        "plans", "semantics", "translations", "checks", "troubleshooting"
    )}
    plan_directory = roots["plans"] / "synthetic" / "1.0" / plan["planRunId"]
    plan_directory.mkdir(parents=True)
    (plan_directory / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    slug = unit_directory_name(UNIT)
    check_directory = roots["checks"] / "synthetic" / "1.0" / plan["planRunId"] / slug
    check_directory.mkdir(parents=True)
    (check_directory / "check.json").write_text(json.dumps(check), encoding="utf-8")
    return plan, roots


def _write_build_inputs(tmp_path: Path) -> tuple[dict, dict[str, Path], dict, dict]:
    check = _check("FAIL", "PASS", "PASS")
    plan, roots = _write_plan_and_check(tmp_path, check)
    semantics = {
        "schemaVersion": 1,
        "phase": "SEMANTIC_EXTRACTOR",
        "planRunId": plan["planRunId"],
        "language": plan["language"],
        "version": plan["version"],
        "unit": dict(UNIT),
        "runId": "semantic-run:repair",
        "outcome": "SUCCESS",
        "semantics": {"claims": [{
            "claimId": "claim:operation",
            "kind": "SOURCE_FACT",
            "statement": "The operation adds two natural numbers.",
            "evidenceIds": ["evidence:operation"],
        }]},
    }
    scope = TranslationGroupScope.from_inputs(
        plan, GROUP, {UNIT["unitId"]: semantics}, created_at="2026-08-27T00:00:00Z"
    )
    declarations = [{
        "declaration": "Spec2Lean.Repair.operation",
        "role": "OPERATION",
        "claimRefs": [{"unitId": UNIT["unitId"], "claimId": "claim:operation"}],
    }]
    manifest = scope.manifest(declarations)
    check["translationRunId"] = manifest["translationRunId"]
    slug = unit_directory_name(UNIT)
    check_path = roots["checks"] / "synthetic" / "1.0" / plan["planRunId"] / slug / "check.json"
    check_path.write_text(json.dumps(check), encoding="utf-8")
    semantics_directory = roots["semantics"] / "synthetic" / "1.0" / plan["planRunId"] / slug
    semantics_directory.mkdir(parents=True)
    (semantics_directory / "semantics.json").write_text(json.dumps(semantics), encoding="utf-8")
    translation_directory = roots["translations"] / "synthetic" / "1.0" / plan["planRunId"] / GROUP
    translation_directory.mkdir(parents=True)
    (translation_directory / f"{GROUP}.lean").write_text(SOURCE, encoding="utf-8")
    (translation_directory / "translation-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (translation_directory / "translator-run.json").write_text("{}", encoding="utf-8")
    return plan, roots, semantics, manifest


def _run(plan: dict, roots: dict[str, Path], repair_runner):
    return run_troubleshooter(
        plan,
        semantics_root=roots["semantics"],
        translations_root=roots["translations"],
        checks_root=roots["checks"],
        troubleshooting_root=roots["troubleshooting"],
        unit_id=UNIT["unitId"],
        repair_runner=repair_runner,
        now=lambda: "2026-08-27T00:00:00Z",
        repository_root=roots["plans"],
    )


def _forbidden_repair(*args, **kwargs):
    raise AssertionError("OpenCode repair must not be invoked for this route")


def test_build_failure_routes_to_one_troubleshooter_repair_and_records_hashes(tmp_path):
    plan, roots, _, manifest = _write_build_inputs(tmp_path)
    calls = []

    def repair(context, *, timeout_seconds):
        calls.append((context, timeout_seconds))
        return {
            "submission": {
                "leanSource": REPAIRED_SOURCE,
                "declarations": manifest["declarations"],
                "changes": [{
                    "description": "Use the resolved Nat.add API spelling.",
                    "affectedDeclarations": ["Spec2Lean.Repair.operation"],
                }],
            },
            "error": None,
            "session": {
                "provider": "opencode",
                "model": TROUBLESHOOTER_MODEL,
                "reasoning": TROUBLESHOOTER_REASONING,
                "opencodeVersion": "1.test",
                "singleSession": True,
                "automaticRetries": 0,
            },
        }

    output, artifact = _run(plan, roots, repair)
    assert len(calls) == 1
    assert artifact["action"] == REPAIR_BUILD and artifact["outcome"] == "REPAIRED"
    assert artifact["repairRunId"].startswith("repair-run:")
    assert artifact["hashes"]["before"][f"{GROUP}.lean"] != artifact["hashes"]["after"][f"{GROUP}.lean"]
    assert artifact["changedFiles"] == [f"{GROUP}.lean"]
    assert artifact["singleSession"] is True and artifact["automaticRetries"] == 0
    assert json.loads((output / "troubleshoot.json").read_text()) == artifact


def test_build_repair_context_includes_toolchain_and_prior_attempts(tmp_path):
    plan, roots, _, _ = _write_build_inputs(tmp_path)
    attempts = [{
        "repairRunId": "repair-run:prior",
        "compilerDiagnostics": [{"message": "previous mismatch"}],
        "changes": [{"description": "Previous failed conversion."}],
        "leanSourceHashBefore": "sha256:before",
        "leanSourceHashAfter": "sha256:after",
    }]
    captured = {}

    def repair(context, *, timeout_seconds):
        captured.update(context)
        return {
            "submission": {
                "leanSource": REPAIRED_SOURCE,
                "declarations": captured["translationManifest"]["declarations"],
                "changes": [{
                    "description": "Use the compiler-required API type.",
                    "affectedDeclarations": ["Spec2Lean.Repair.operation"],
                }],
            },
            "error": None,
            "session": {"opencodeVersion": "1.test"},
        }

    run_troubleshooter(
        plan,
        semantics_root=roots["semantics"],
        translations_root=roots["translations"],
        checks_root=roots["checks"],
        troubleshooting_root=roots["troubleshooting"],
        unit_id=UNIT["unitId"],
        repair_runner=repair,
        prior_repair_attempts=attempts,
        now=lambda: "2026-08-27T00:00:00Z",
        repository_root=roots["plans"],
    )

    assert captured["leanVersion"] == "Lean (version 4.test)"
    assert captured["priorRepairAttempts"] == attempts
    prompt = build_troubleshooter_prompt()
    assert "diagnostics and Lean version as authoritative" in prompt
    assert "Do not repeat" in prompt
    assert "correct the submission and call it again" in prompt


def test_file_level_import_repair_needs_no_affected_declaration(tmp_path):
    plan, _, semantics, manifest = _write_build_inputs(tmp_path)
    scope = TranslationGroupScope.from_inputs(
        plan, GROUP, {UNIT["unitId"]: semantics}, created_at=manifest["createdAt"]
    )
    candidate, diagnostics = validate_repair_submission(
        scope,
        {UNIT["unitId"]: semantics},
        SOURCE,
        manifest,
        {
            "leanSource": "import Std\n\n" + SOURCE,
            "declarations": manifest["declarations"],
            "changes": [{
                "description": "Replace a missing module with the installed root import.",
                "affectedDeclarations": [],
            }],
        },
    )
    assert diagnostics == []
    assert candidate is not None
    assert candidate["changes"][0]["affectedDeclarations"] == []


def test_coverage_failure_routes_to_translator_with_exact_uncovered_ids(tmp_path):
    check = _check("PASS", "FAIL", "PASS")
    plan, roots = _write_plan_and_check(tmp_path, check)
    _, artifact = _run(plan, roots, _forbidden_repair)
    assert artifact["action"] == RETURN_TO_TRANSLATOR
    assert artifact["handoff"] == {
        "phase": "LLM_TRANSLATOR", "diagnostics": check["coverage"]["uncovered"]
    }


def test_traceability_failure_routes_to_semantic_extractor_with_exact_diagnostics(tmp_path):
    check = _check("PASS", "PASS", "FAIL")
    plan, roots = _write_plan_and_check(tmp_path, check)
    _, artifact = _run(plan, roots, _forbidden_repair)
    assert artifact["action"] == RETURN_TO_SEMANTIC_EXTRACTOR
    assert artifact["handoff"] == {
        "phase": "SEMANTIC_EXTRACTOR", "diagnostics": check["traceability"]["brokenMappings"]
    }


def test_traceability_and_build_failure_routes_to_semantic_extractor_first(tmp_path):
    plan, roots = _write_plan_and_check(tmp_path, _check("FAIL", "PASS", "FAIL"))
    _, artifact = _run(plan, roots, _forbidden_repair)
    assert artifact["action"] == RETURN_TO_SEMANTIC_EXTRACTOR
    assert artifact["failures"] == {"build": True, "coverage": False, "traceability": True}


def test_coverage_and_build_failure_routes_to_translator_first(tmp_path):
    plan, roots = _write_plan_and_check(tmp_path, _check("FAIL", "FAIL", "PASS"))
    _, artifact = _run(plan, roots, _forbidden_repair)
    assert artifact["action"] == RETURN_TO_TRANSLATOR
    assert artifact["compilerDiagnostics"]


def test_successful_check_produces_no_repair_action(tmp_path):
    plan, roots = _write_plan_and_check(tmp_path, _check("PASS", "PASS", "PASS"))
    _, artifact = _run(plan, roots, _forbidden_repair)
    assert artifact["action"] == NO_ACTION
    assert artifact["outcome"] == "COMPLETE"
    assert artifact["recheck"]["required"] is False


def test_build_repair_preserves_valid_manifest_references_and_marks_all_checks(tmp_path):
    plan, roots, semantics, manifest = _write_build_inputs(tmp_path)

    def repair(context, *, timeout_seconds):
        return {
            "submission": {
                "leanSource": REPAIRED_SOURCE,
                "declarations": manifest["declarations"],
                "changes": [{
                    "description": "Repair a mechanical API reference.",
                    "affectedDeclarations": ["Spec2Lean.Repair.operation"],
                }],
            },
            "error": None,
            "session": {"opencodeVersion": "1.test"},
        }

    _, artifact = _run(plan, roots, repair)
    slug = unit_directory_name(UNIT)
    directory = roots["translations"] / "synthetic" / "1.0" / plan["planRunId"] / GROUP
    source = (directory / f"{GROUP}.lean").read_text()
    stored_manifest = json.loads((directory / "translation-manifest.json").read_text())
    assert validate_manifest(plan, {UNIT["unitId"]: semantics}, source, stored_manifest) == []
    assert stored_manifest["declarations"][0]["claimRefs"] == [
        {"unitId": UNIT["unitId"], "claimId": "claim:operation"}
    ]
    assert artifact["recheck"] == {
        "required": True,
        "phase": "CHECK",
        "checks": ["BUILD", "COVERAGE", "TRACEABILITY"],
        "automatic": False,
    }


def test_routing_is_deterministic_and_uses_earliest_failed_phase():
    matrix = {
        ("FAIL", "PASS", "PASS"): REPAIR_BUILD,
        ("FAIL", "FAIL", "PASS"): RETURN_TO_TRANSLATOR,
        ("FAIL", "FAIL", "FAIL"): RETURN_TO_SEMANTIC_EXTRACTOR,
        ("PASS", "FAIL", "FAIL"): RETURN_TO_SEMANTIC_EXTRACTOR,
        ("PASS", "PASS", "PASS"): NO_ACTION,
    }
    for statuses, expected in matrix.items():
        check = _check(*statuses)
        assert [action_for(check) for _ in range(10)] == [expected] * 10


def test_build_repair_cannot_change_semantic_mapping_responsibility(tmp_path):
    plan, roots, _, manifest = _write_build_inputs(tmp_path)
    changed_mapping = [dict(manifest["declarations"][0], role="EXECUTION")]

    def repair(context, *, timeout_seconds):
        return {
            "submission": {
                "leanSource": REPAIRED_SOURCE,
                "declarations": changed_mapping,
                "changes": [{
                    "description": "Improperly change the semantic role.",
                    "affectedDeclarations": ["Spec2Lean.Repair.operation"],
                }],
            },
            "error": None,
            "session": {"opencodeVersion": "1.test"},
        }

    with pytest.raises(RuntimeError, match="preserve declaration roles"):
        _run(plan, roots, repair)
    slug = unit_directory_name(UNIT)
    directory = roots["translations"] / "synthetic" / "1.0" / plan["planRunId"] / GROUP
    assert (directory / f"{GROUP}.lean").read_text() == SOURCE
    artifact = json.loads((
        roots["troubleshooting"] / "synthetic" / "1.0" / plan["planRunId"]
        / slug / "troubleshoot.json"
    ).read_text())
    assert artifact["outcome"] == "FAILED" and artifact["changedFiles"] == []


def test_opencode_configuration_uses_exact_model_and_restricted_troubleshooting_tools(tmp_path):
    config = opencode_config(tmp_path / "context.json", tmp_path / "submission.json")
    agent = config["agent"]["spec2lean-troubleshooter"]
    assert agent["model"] == TROUBLESHOOTER_MODEL == "openai/gpt-5.6-sol"
    assert agent["variant"] == TROUBLESHOOTER_REASONING == "medium"
    assert agent["permission"] == {"*": "deny", "troubleshooting_*": "allow"}
    assert agent["tools"]["bash"] is False and agent["tools"]["edit"] is False


def test_repair_context_must_be_fetched_through_read_only_mcp_tool(tmp_path):
    marker = "complete-repair-context"
    context = {
        "marker": marker,
        "leanSource": "def repaired := true",
        "translationManifest": {"schemaVersion": 2},
        "traceability": {"status": "PASS"},
        "semanticsByUnit": {"unit:one": {"claims": []}},
    }
    server = TroubleshootingMcpServer(context, tmp_path / "submission.json")

    assert [item["name"] for item in tool_definitions()] == ["get_context", "submit_repair"]
    rejected = json.loads(server.call_tool("submit_repair", {})["content"][0]["text"])
    assert rejected["diagnostics"][0]["code"] == "CONTEXT_NOT_READ"
    overview = json.loads(
        server.call_tool("get_context", {"component": "overview"})["content"][0]["text"]
    )
    assert overview["value"]["marker"] == marker
    assert overview["value"]["semanticUnitIds"] == ["unit:one"]
    assert "leanSource" not in overview["value"]
    for component in ("leanSource", "translationManifest", "traceability"):
        fetched = json.loads(
            server.call_tool("get_context", {"component": component})["content"][0]["text"]
        )
        assert fetched["transport"] == {"complete": True}
    semantic = json.loads(server.call_tool(
        "get_context", {"component": "semantics", "unitId": "unit:one"}
    )["content"][0]["text"])
    assert semantic["value"] == {"claims": []}
    assert server.context_reads == server._required_context_reads()


def test_large_repair_context_is_not_embedded_in_opencode_argument(
    tmp_path, monkeypatch
):
    marker = "large-repair-context-" + ("x" * 160_000)
    context = {
        "plan": {"planRunId": "plan:large-context"},
        "unit": {"unitId": "unit:large-context"},
        "translationDirectory": str(tmp_path),
        "marker": marker,
    }
    calls = []
    monkeypatch.setattr("spec2lean.troubleshooting.opencode.shutil.which", lambda _: "/usr/bin/opencode")
    monkeypatch.setattr(
        "spec2lean.troubleshooting.opencode.installed_openai_models",
        lambda _: {TROUBLESHOOTER_MODEL},
    )

    def fake_run(command, **kwargs):
        if command[1:] == ["--version"]:
            return subprocess.CompletedProcess(command, 0, "opencode test\n", "")
        calls.append((command, kwargs))
        config = json.loads(kwargs["env"]["OPENCODE_CONFIG_CONTENT"])
        mcp_command = config["mcp"]["troubleshooting"]["command"]
        context_path = Path(mcp_command[mcp_command.index("--context") + 1])
        assert json.loads(context_path.read_text())["marker"] == marker
        assert marker not in command[-1]
        assert len(command[-1].encode("utf-8")) < 32_000
        return subprocess.CompletedProcess(command, 0, '{"sessionID":"repair-session"}\n', "")

    result = run_opencode_repair(context, run_command=fake_run)
    assert len(calls) == 1
    assert result["error"] == "OpenCode Troubleshooter finished without a valid submit_repair call"


def test_inspection_cli_shows_artifact_and_changes_without_rerunning(tmp_path, capsys):
    check = _check("PASS", "FAIL", "PASS")
    plan, roots = _write_plan_and_check(tmp_path, check)
    _run(plan, roots, _forbidden_repair)
    common = [
        "--plan-run", plan["planRunId"], "--unit", UNIT["unitId"],
        "--plans-root", str(roots["plans"]),
        "--troubleshooting-root", str(roots["troubleshooting"]),
    ]
    assert main(["troubleshoot", "show", *common]) == 0
    assert json.loads(capsys.readouterr().out)["action"] == RETURN_TO_TRANSLATOR
    assert main(["troubleshoot", "changes", *common]) == 0
    assert json.loads(capsys.readouterr().out)["changedFiles"] == []


def test_resolver_dispatches_coverage_to_one_translation_revision_then_rechecks(tmp_path):
    check = _check("FAIL", "FAIL", "PASS")
    plan, roots = _write_plan_and_check(tmp_path, check)
    calls = []

    def translation_reviser(plan, **kwargs):
        calls.append(("translate", kwargs))
        return tmp_path / "translation-revision", {"revisionRunId": "translation-revision:test"}

    def checker(plan, **kwargs):
        calls.append(("check", kwargs))
        return roots["checks"], _check("PASS", "PASS", "PASS")

    _, resolution = resolve_check_failure(
        plan, evidence_root=tmp_path / "evidence", semantics_root=roots["semantics"],
        translations_root=roots["translations"], checks_root=roots["checks"],
        troubleshooting_root=roots["troubleshooting"], database=tmp_path / "db",
        unit_id=UNIT["unitId"], translation_reviser=translation_reviser,
        checker=checker, now=lambda: "2026-08-27T00:00:00Z",
        repository_root=roots["plans"],
    )
    assert [name for name, _ in calls] == ["translate", "check"]
    assert calls[0][1]["diagnostics"] == check["coverage"]["uncovered"]
    assert resolution["initialAction"] == RETURN_TO_TRANSLATOR
    assert resolution["nextAction"] == NO_ACTION and resolution["dispatches"] == 1


def test_resolver_dispatches_traceability_through_semantics_translation_and_one_recheck(tmp_path):
    check = _check("FAIL", "FAIL", "FAIL")
    plan, roots = _write_plan_and_check(tmp_path, check)
    calls = []

    def semantic_reviser(plan, **kwargs):
        calls.append(("semantics", kwargs))
        return tmp_path / "semantic-revision", {"revisionRunId": "semantic-revision:test"}

    def translation_reviser(plan, **kwargs):
        calls.append(("translate", kwargs))
        return tmp_path / "translation-revision", {"revisionRunId": "translation-revision:test"}

    def checker(plan, **kwargs):
        calls.append(("check", kwargs))
        return roots["checks"], _check("FAIL", "PASS", "PASS")

    _, resolution = resolve_check_failure(
        plan, evidence_root=tmp_path / "evidence", semantics_root=roots["semantics"],
        translations_root=roots["translations"], checks_root=roots["checks"],
        troubleshooting_root=roots["troubleshooting"], database=tmp_path / "db",
        unit_id=UNIT["unitId"], semantic_reviser=semantic_reviser,
        translation_reviser=translation_reviser, checker=checker,
        max_dispatches=1,
        now=lambda: "2026-08-27T00:00:00Z", repository_root=roots["plans"],
    )
    assert [name for name, _ in calls] == ["semantics", "translate", "check"]
    assert calls[0][1]["diagnostics"] == check["traceability"]["brokenMappings"]
    assert calls[1][1]["reason"] == "SEMANTICS_REVISED"
    assert resolution["nextAction"] == REPAIR_BUILD
    assert resolution["outcome"] == "DISPATCH_LIMIT"
    assert resolution["stopReason"] == "DISPATCH_LIMIT"
    assert resolution["automaticRetries"] == 0


def test_resolver_dispatches_build_to_syntax_handler_then_rechecks_once(tmp_path):
    plan, roots, _, manifest = _write_build_inputs(tmp_path)
    calls = []

    def repair(context, *, timeout_seconds):
        calls.append("repair")
        return {
            "submission": {
                "leanSource": REPAIRED_SOURCE,
                "declarations": manifest["declarations"],
                "changes": [{
                    "description": "Repair the syntax/API spelling.",
                    "affectedDeclarations": ["Spec2Lean.Repair.operation"],
                }],
            },
            "error": None,
            "session": {"opencodeVersion": "1.test"},
        }

    def checker(plan, **kwargs):
        calls.append("check")
        return roots["checks"], _check("PASS", "PASS", "PASS")

    _, resolution = resolve_check_failure(
        plan, evidence_root=tmp_path / "evidence", semantics_root=roots["semantics"],
        translations_root=roots["translations"], checks_root=roots["checks"],
        troubleshooting_root=roots["troubleshooting"], database=tmp_path / "db",
        unit_id=UNIT["unitId"], checker=checker, repair_runner=repair,
        now=lambda: "2026-08-27T00:00:00Z", repository_root=roots["plans"],
    )
    assert calls == ["repair", "check"]
    assert resolution["initialAction"] == REPAIR_BUILD
    assert resolution["outcome"] == "COMPLETE" and resolution["rechecked"] is True


def test_resolver_handles_coverage_then_fresh_build_failure_in_one_call(tmp_path):
    plan, roots, _, manifest = _write_build_inputs(tmp_path)
    initial = _check("FAIL", "FAIL", "PASS")
    initial["translationRunId"] = manifest["translationRunId"]
    slug = unit_directory_name(UNIT)
    check_path = roots["checks"] / "synthetic" / "1.0" / plan["planRunId"] / slug / "check.json"
    check_path.write_text(json.dumps(initial), encoding="utf-8")
    calls = []

    def translation_reviser(plan, **kwargs):
        calls.append("translate")
        return tmp_path / "translation-revision", {"revisionRunId": "translation-revision:test"}

    def repair(context, *, timeout_seconds):
        calls.append("repair")
        return {
            "submission": {
                "leanSource": REPAIRED_SOURCE,
                "declarations": manifest["declarations"],
                "changes": [{
                    "description": "Repair the remaining syntax/API error.",
                    "affectedDeclarations": ["Spec2Lean.Repair.operation"],
                }],
            },
            "error": None,
            "session": {"opencodeVersion": "1.test"},
        }

    check_results = [_check("FAIL", "PASS", "PASS"), _check("PASS", "PASS", "PASS")]
    for result in check_results:
        result["translationRunId"] = manifest["translationRunId"]

    def checker(plan, **kwargs):
        calls.append("check")
        result = check_results.pop(0)
        check_path.write_text(json.dumps(result), encoding="utf-8")
        return check_path.parent, result

    _, resolution = resolve_check_failure(
        plan, evidence_root=tmp_path / "evidence", semantics_root=roots["semantics"],
        translations_root=roots["translations"], checks_root=roots["checks"],
        troubleshooting_root=roots["troubleshooting"], database=tmp_path / "db",
        unit_id=UNIT["unitId"], translation_reviser=translation_reviser,
        checker=checker, repair_runner=repair,
        now=lambda: "2026-08-27T00:00:00Z", repository_root=roots["plans"],
    )
    assert calls == ["translate", "check", "repair", "check"]
    assert resolution["dispatches"] == 2
    assert resolution["stopReason"] == "ALL_CHECKS_PASS"
    assert resolution["outcome"] == "COMPLETE" and resolution["nextAction"] == NO_ACTION


def test_resolver_passes_failed_build_attempt_history_to_next_repair(tmp_path, monkeypatch):
    initial = _check("FAIL", "PASS", "PASS")
    plan, roots = _write_plan_and_check(tmp_path, initial)
    received_histories = []
    repair_number = 0

    def fake_troubleshooter(plan, **kwargs):
        nonlocal repair_number
        repair_number += 1
        received_histories.append(kwargs["prior_repair_attempts"])
        artifact = {
            "repairRunId": f"repair-run:{repair_number}",
            "compilerDiagnostics": kwargs["check_override"]["build"]["diagnostics"],
            "changes": [{"description": f"repair {repair_number}"}],
            "hashes": {
                "before": {"Unit.lean": f"sha256:before-{repair_number}"},
                "after": {"Unit.lean": f"sha256:after-{repair_number}"},
            },
        }
        return roots["troubleshooting"], artifact

    still_failing = _check("FAIL", "PASS", "PASS")
    still_failing["build"]["diagnostics"][0]["message"] = "new mismatch after repair 1"
    passed = _check("PASS", "PASS", "PASS")
    check_results = [still_failing, passed]

    def checker(plan, **kwargs):
        return roots["checks"], check_results.pop(0)

    monkeypatch.setattr(
        "spec2lean.troubleshooting.resolver.run_troubleshooter", fake_troubleshooter
    )
    _, resolution = resolve_check_failure(
        plan,
        evidence_root=tmp_path / "evidence",
        semantics_root=roots["semantics"],
        translations_root=roots["translations"],
        checks_root=roots["checks"],
        troubleshooting_root=roots["troubleshooting"],
        database=tmp_path / "db",
        unit_id=UNIT["unitId"],
        checker=checker,
        now=lambda: "2026-08-27T00:00:00Z",
        repository_root=roots["plans"],
    )

    assert received_histories[0] == []
    assert received_histories[1] == [{
        "repairRunId": "repair-run:1",
        "compilerDiagnostics": initial["build"]["diagnostics"],
        "changes": [{"description": "repair 1"}],
        "leanSourceHashBefore": "sha256:before-1",
        "leanSourceHashAfter": "sha256:after-1",
    }]
    assert resolution["dispatches"] == 2
    assert resolution["outcome"] == "COMPLETE"


def test_resolver_stops_on_repeated_actionable_state_instead_of_looping(tmp_path):
    check = _check("PASS", "FAIL", "PASS")
    plan, roots = _write_plan_and_check(tmp_path, check)
    calls = []

    def translation_reviser(plan, **kwargs):
        calls.append("translate")
        return tmp_path / "translation-revision", {"revisionRunId": "translation-revision:test"}

    def checker(plan, **kwargs):
        calls.append("check")
        return roots["checks"], check

    _, resolution = resolve_check_failure(
        plan, evidence_root=tmp_path / "evidence", semantics_root=roots["semantics"],
        translations_root=roots["translations"], checks_root=roots["checks"],
        troubleshooting_root=roots["troubleshooting"], database=tmp_path / "db",
        unit_id=UNIT["unitId"], translation_reviser=translation_reviser,
        checker=checker, now=lambda: "2026-08-27T00:00:00Z",
        repository_root=roots["plans"],
    )
    assert calls == ["translate", "check"]
    assert resolution["dispatches"] == 1
    assert resolution["stopReason"] == "NO_PROGRESS"
    assert resolution["outcome"] == "NO_PROGRESS"
