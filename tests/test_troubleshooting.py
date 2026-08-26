from __future__ import annotations

import json
from pathlib import Path

import pytest

from spec2lean.cli import main
from spec2lean.evidence.runner import unit_directory_name
from spec2lean.translation.models import TranslationScope
from spec2lean.translation.validation import validate_manifest
from spec2lean.troubleshooting.models import (
    NO_ACTION,
    REPAIR_BUILD,
    RETURN_TO_SEMANTIC_EXTRACTOR,
    RETURN_TO_TRANSLATOR,
    action_for,
)
from spec2lean.troubleshooting.opencode import opencode_config
from spec2lean.troubleshooting.runner import run_troubleshooter


UNIT = {"unitId": "unit:repair", "name": "repair.unit", "sourceNodeIds": ["node:repair"]}
SOURCE = """namespace Spec2Lean.Repair

def operation (a b : Nat) : Nat := a + b

end Spec2Lean.Repair
"""
REPAIRED_SOURCE = SOURCE.replace("a + b", "Nat.add a b")


def _plan() -> dict:
    return {
        "schemaVersion": 1,
        "planRunId": "plan:troubleshooting-test",
        "language": "synthetic",
        "version": "1.0",
        "requestedUnits": [dict(UNIT)],
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
    scope = TranslationScope.from_inputs(
        plan, semantics, UNIT["unitId"], created_at="2026-08-27T00:00:00Z"
    )
    declarations = [{
        "declaration": "Spec2Lean.Repair.operation",
        "role": "OPERATION",
        "semanticClaimIds": ["claim:operation"],
    }]
    manifest = scope.manifest(declarations)
    check["translationRunId"] = manifest["translationRunId"]
    slug = unit_directory_name(UNIT)
    check_path = roots["checks"] / "synthetic" / "1.0" / plan["planRunId"] / slug / "check.json"
    check_path.write_text(json.dumps(check), encoding="utf-8")
    semantics_directory = roots["semantics"] / "synthetic" / "1.0" / plan["planRunId"] / slug
    semantics_directory.mkdir(parents=True)
    (semantics_directory / "semantics.json").write_text(json.dumps(semantics), encoding="utf-8")
    translation_directory = roots["translations"] / "synthetic" / "1.0" / plan["planRunId"] / slug
    translation_directory.mkdir(parents=True)
    (translation_directory / "Unit.lean").write_text(SOURCE, encoding="utf-8")
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
                "model": "openai/gpt-5.3-codex-spark",
                "reasoning": "low",
                "opencodeVersion": "1.test",
                "singleSession": True,
                "automaticRetries": 0,
            },
        }

    output, artifact = _run(plan, roots, repair)
    assert len(calls) == 1
    assert artifact["action"] == REPAIR_BUILD and artifact["outcome"] == "REPAIRED"
    assert artifact["repairRunId"].startswith("repair-run:")
    assert artifact["hashes"]["before"]["Unit.lean"] != artifact["hashes"]["after"]["Unit.lean"]
    assert artifact["changedFiles"] == ["Unit.lean"]
    assert artifact["singleSession"] is True and artifact["automaticRetries"] == 0
    assert json.loads((output / "troubleshoot.json").read_text()) == artifact


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
    directory = roots["translations"] / "synthetic" / "1.0" / plan["planRunId"] / slug
    source = (directory / "Unit.lean").read_text()
    stored_manifest = json.loads((directory / "translation-manifest.json").read_text())
    assert validate_manifest(plan, semantics, source, stored_manifest) == []
    assert stored_manifest["declarations"][0]["semanticClaimIds"] == ["claim:operation"]
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
    directory = roots["translations"] / "synthetic" / "1.0" / plan["planRunId"] / slug
    assert (directory / "Unit.lean").read_text() == SOURCE
    artifact = json.loads((
        roots["troubleshooting"] / "synthetic" / "1.0" / plan["planRunId"]
        / slug / "troubleshoot.json"
    ).read_text())
    assert artifact["outcome"] == "FAILED" and artifact["changedFiles"] == []


def test_opencode_configuration_uses_exact_model_low_reasoning_and_one_submit_tool(tmp_path):
    config = opencode_config(tmp_path / "context.json", tmp_path / "submission.json")
    agent = config["agent"]["spec2lean-troubleshooter"]
    assert agent["model"] == "openai/gpt-5.3-codex-spark"
    assert agent["variant"] == "low"
    assert agent["permission"] == {"*": "deny", "troubleshooting_*": "allow"}
    assert agent["tools"]["bash"] is False and agent["tools"]["edit"] is False


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
