from __future__ import annotations

import copy

from spec2lean.translation.models import TranslationGroupScope
from spec2lean.translation.prompt import build_translator_prompt
from spec2lean.translation.revision_prompt import build_translation_revision_prompt
from spec2lean.translation.validation import (
    has_genuine_execution_semantics,
    validate_submission,
)


UNIT = {
    "unitId": "unit:quality",
    "name": "quality.operation",
    "sourceNodeIds": ["node:quality"],
}
GROUP = "QualityOperations"
PREFIX = "Spec2Lean.Synthetic.Quality"


def _inputs(
    *, stateful: bool = False, predicated: bool = False
) -> tuple[dict, dict, TranslationGroupScope]:
    plan = {
        "schemaVersion": 3,
        "planRunId": "plan:phase5-quality",
        "language": "synthetic",
        "version": "1",
        "sourceDatabaseDigest": "digest:quality",
        "request": {"scope": {"mode": "EXACT_INSTRUCTIONS"}},
        "requestedUnits": [copy.deepcopy(UNIT)],
        "translationGroups": [{
            "name": GROUP,
            "unitIds": [UNIT["unitId"]],
            "reason": "Exercise the generic Phase-5 execution boundary.",
            "supportingNodeIds": ["node:quality"],
            "origin": "INFERRED",
        }],
        "sharedPrerequisites": [],
    }
    claims = [{
        "claimId": "claim:operation",
        "kind": "SOURCE_FACT",
        "statement": "The result is the sum of the two source values.",
        "evidenceIds": ["evidence:operation"],
    }]
    state_effects: list[dict] = []
    if stateful:
        state_effects.append({
            "target": "machine destination slot",
            "effect": "Replace the slot with the operation result.",
            "evidenceIds": ["evidence:state"],
        })
        claims.append({
            "claimId": "claim:state",
            "kind": "SOURCE_FACT",
            "statement": "Execution updates the machine destination slot.",
            "evidenceIds": ["evidence:state"],
        })
    predication = None
    if predicated:
        predication = {
            "guard": "guard",
            "whenTrue": "Produce the operation result.",
            "whenFalse": "Do not produce a result.",
            "evidenceIds": ["evidence:guard"],
        }
        claims.append({
            "claimId": "claim:guard",
            "kind": "SOURCE_FACT",
            "statement": "The guard controls whether the operation produces its result.",
            "evidenceIds": ["evidence:guard"],
        })
    semantics = {
        "schemaVersion": 2,
        "phase": "SEMANTIC_EXTRACTOR",
        "planRunId": plan["planRunId"],
        "language": plan["language"],
        "version": plan["version"],
        "unit": copy.deepcopy(UNIT),
        "evidenceBundleHash": "sha256:" + "a" * 64,
        "extractor": {
            "provider": "opencode",
            "model": "openai/gpt-5.6-sol",
            "reasoning": "medium",
        },
        "runId": "semantic-run:phase5-quality",
        "createdAt": "2026-08-29T00:00:00Z",
        "outcome": "SUCCESS",
        "semantics": {
            "unitKind": "INSTRUCTION",
            "identity": {"name": UNIT["name"], "evidenceIds": ["evidence:syntax"]},
            "syntaxForms": [{
                "form": "quality.operation destination, a, b",
                "evidenceIds": ["evidence:syntax"],
            }],
            "inputs": [
                {
                    "name": "destination",
                    "role": "destination syntax operand",
                    "description": "The syntactic result destination.",
                    "constraints": [],
                    "evidenceIds": ["evidence:syntax"],
                },
                {
                    "name": "a",
                    "role": "source",
                    "description": "The first source value.",
                    "constraints": [],
                    "evidenceIds": ["evidence:operation"],
                },
                {
                    "name": "b",
                    "role": "source",
                    "description": "The second source value.",
                    "constraints": [],
                    "evidenceIds": ["evidence:operation"],
                },
            ],
            "result": {
                "name": "result",
                "description": "The sum of a and b.",
                "constraints": [],
                "evidenceIds": ["evidence:operation"],
            },
            "operation": {
                "description": "Add the two source values and return their sum.",
                "inputs": ["a", "b"],
                "result": "result",
                "branches": [],
                "evidenceIds": ["evidence:operation"],
            },
            "edgeCases": [],
            "stateEffects": state_effects,
            **({"predication": predication} if predication is not None else {}),
            "restrictions": [],
            "dependencies": [],
            "claims": claims,
        },
    }
    semantics_by_unit = {UNIT["unitId"]: semantics}
    scope = TranslationGroupScope.from_inputs(
        plan,
        GROUP,
        semantics_by_unit,
        created_at="2026-08-29T00:00:01Z",
    )
    return plan, semantics, scope


def _operation_mapping() -> dict:
    return {
        "declaration": f"{PREFIX}.operation",
        "role": "OPERATION",
        "claimRefs": [{"unitId": UNIT["unitId"], "claimId": "claim:operation"}],
    }


def test_redundant_execute_wrapper_is_rejected_for_operation_only_semantics() -> None:
    _plan, semantics, scope = _inputs()
    source = f"""namespace {PREFIX}

def operation (a b : Nat) : Nat := a + b

def executeOperation (_destination a b : Nat) : Nat := operation a b

end {PREFIX}
"""
    submission = {
        "leanSource": source,
        "declarations": [
            _operation_mapping(),
            {
                "declaration": f"{PREFIX}.executeOperation",
                "role": "EXECUTION",
                "claimRefs": [{
                    "unitId": UNIT["unitId"],
                    "claimId": "claim:operation",
                }],
            },
        ],
        "sharedUses": [],
    }

    candidate, diagnostics = validate_submission(
        scope, {UNIT["unitId"]: semantics}, submission
    )

    assert candidate is None
    redundant = [
        item for item in diagnostics if item["code"] == "REDUNDANT_EXECUTION_MAPPING"
    ]
    assert redundant == [{
        "code": "REDUNDANT_EXECUTION_MAPPING",
        "message": (
            "EXECUTION is permitted only when Phase 4 records state effects or predication "
            "beyond the pure operation; destination-shaped syntax or results do not justify "
            "an execution wrapper: ['unit:quality']"
        ),
        "path": "$.declarations[1].role",
    }]


def test_destination_shaped_syntax_does_not_require_execution() -> None:
    _plan, semantics, _scope = _inputs()
    payload = semantics["semantics"]

    assert payload["inputs"][0]["role"] == "destination syntax operand"
    assert has_genuine_execution_semantics(payload) is False


def test_pure_operation_is_the_complete_primary_semantic_declaration() -> None:
    _plan, semantics, scope = _inputs()
    source = f"""namespace {PREFIX}

def operation (a b : Nat) : Nat := a + b

end {PREFIX}
"""
    candidate, diagnostics = validate_submission(
        scope,
        {UNIT["unitId"]: semantics},
        {
            "leanSource": source,
            "declarations": [_operation_mapping()],
            "sharedUses": [],
        },
    )

    assert diagnostics == []
    assert candidate is not None
    mappings = candidate["manifest"]["declarations"]
    assert len(mappings) == 1
    assert {
        key: value for key, value in mappings[0].items() if key != "sourceRange"
    } == _operation_mapping()
    assert mappings[0]["sourceRange"] == {
        "file": "QualityOperations.lean", "startLine": 3, "endLine": 5,
    }


def test_genuine_stateful_execution_remains_allowed_but_is_not_forced() -> None:
    _plan, semantics, scope = _inputs(stateful=True)
    source = f"""namespace {PREFIX}

structure MachineState where
  destination : Nat

def operation (a b : Nat) : Nat := a + b

def executeOperation (state : MachineState) (a b : Nat) : MachineState :=
  {{ state with destination := operation a b }}

end {PREFIX}
"""
    refs = lambda claim_id: [{"unitId": UNIT["unitId"], "claimId": claim_id}]
    submission = {
        "leanSource": source,
        "declarations": [
            {
                "declaration": f"{PREFIX}.MachineState",
                "role": "PRIMARY_TYPE",
                "claimRefs": refs("claim:state"),
            },
            _operation_mapping(),
            {
                "declaration": f"{PREFIX}.executeOperation",
                "role": "EXECUTION",
                "claimRefs": refs("claim:state"),
            },
        ],
        "sharedUses": [],
    }

    assert has_genuine_execution_semantics(semantics["semantics"]) is True
    candidate, diagnostics = validate_submission(
        scope, {UNIT["unitId"]: semantics}, submission
    )
    assert diagnostics == []
    assert candidate is not None
    assert candidate["manifest"]["declarations"][-1]["role"] == "EXECUTION"

    without_execution = copy.deepcopy(submission)
    without_execution["leanSource"] = source.replace(
        "\ndef executeOperation (state : MachineState) (a b : Nat) : MachineState :=\n"
        "  { state with destination := operation a b }\n",
        "",
    )
    without_execution["declarations"].pop()
    operation_only, missing = validate_submission(
        scope, {UNIT["unitId"]: semantics}, without_execution
    )
    assert missing == []
    assert operation_only is not None


def test_destination_write_does_not_save_a_trivial_execution_wrapper() -> None:
    _plan, semantics, scope = _inputs(stateful=True)
    source = f"""namespace {PREFIX}

def operation (a b : Nat) : Nat := a + b

def executeOperation (_destination a b : Nat) : Nat := operation a b

end {PREFIX}
"""
    _candidate, diagnostics = validate_submission(
        scope,
        {UNIT["unitId"]: semantics},
        {
            "leanSource": source,
            "declarations": [
                _operation_mapping(),
                {
                    "declaration": f"{PREFIX}.executeOperation",
                    "role": "EXECUTION",
                    "claimRefs": [{
                        "unitId": UNIT["unitId"], "claimId": "claim:state",
                    }],
                },
            ],
            "sharedUses": [],
        },
    )
    assert "REDUNDANT_EXECUTION_MAPPING" in {
        item["code"] for item in diagnostics
    }


def test_predicated_execution_remains_allowed_without_state_effects() -> None:
    _plan, semantics, scope = _inputs(predicated=True)
    source = f"""namespace {PREFIX}

def operation (a b : Nat) : Nat := a + b

def executeOperation (guard : Bool) (a b : Nat) : Option Nat :=
  if guard then some (operation a b) else none

end {PREFIX}
"""
    candidate, diagnostics = validate_submission(
        scope,
        {UNIT["unitId"]: semantics},
        {
            "leanSource": source,
            "declarations": [
                _operation_mapping(),
                {
                    "declaration": f"{PREFIX}.executeOperation",
                    "role": "EXECUTION",
                    "claimRefs": [{
                        "unitId": UNIT["unitId"],
                        "claimId": "claim:guard",
                    }],
                },
            ],
            "sharedUses": [],
        },
    )

    assert has_genuine_execution_semantics(semantics["semantics"]) is True
    assert diagnostics == []
    assert candidate is not None


def test_primary_and_revision_prompts_preserve_the_execution_boundary() -> None:
    plan, semantics, scope = _inputs()
    primary = build_translator_prompt(scope, {UNIT["unitId"]: semantics})
    revision = build_translation_revision_prompt(
        scope,
        {UNIT["unitId"]: semantics},
        "def operation (a b : Nat) := a + b",
        {},
        [],
        "SEMANTICS_REVISED",
        UNIT["unitId"],
    )

    for prompt in (primary, revision):
        normalized = prompt.casefold()
        assert "genuine behavior beyond the pure result" in normalized
        assert "destination-shaped syntax" in normalized
        assert "unused destination" in normalized
    assert "primary semantic declaration" in primary
    assert plan["planRunId"] in primary
