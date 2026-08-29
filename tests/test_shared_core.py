from __future__ import annotations

import copy
import json
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest

from spec2lean.checking.build import run_build_test
from spec2lean.translation.shared_core import (
    MissingSharedAbstraction,
    collect_shared_requirements,
    ensure_shared_core,
    load_core,
    load_current_core,
    relevant_dependency_ids,
    validate_core_artifact,
)
from spec2lean.translation.shared_core.mcp import SharedCoreMcpServer
from spec2lean.translation.shared_core.models import core_run_id_for, json_hash
from spec2lean.translation.shared_core.validation import normalize_core_submission


UNITS = (
    {"unitId": "unit:alpha", "name": "alpha", "sourceNodeIds": ["node:alpha"]},
    {"unitId": "unit:beta", "name": "beta", "sourceNodeIds": ["node:beta"]},
)


def _plan(*, dependencies=("value",)) -> dict:
    return {
        "schemaVersion": 3,
        "planRunId": "plan:shared-core-test",
        "language": "synthetic",
        "version": "1.0",
        "sourceDatabaseDigest": "digest:synthetic-source",
        "requestedUnits": [copy.deepcopy(item) for item in UNITS],
        "sharedPrerequisites": [
            {
                "dependencyId": f"shared:{name}",
                "name": f"Shared {name}",
                "kind": f"synthetic-{name}-domain",
                "reason": f"Both requested units use the same {name} semantics.",
                "sourceNodeIds": ["node:shared"],
                "requiredBy": [item["unitId"] for item in UNITS],
            }
            for name in dependencies
        ],
    }


def _semantics(plan: dict, unit: dict, *, revision: str = "initial") -> dict:
    names = [item["dependencyId"].split(":", 1)[1] for item in plan["sharedPrerequisites"]]
    return {
        "schemaVersion": 2,
        "phase": "SEMANTIC_EXTRACTOR",
        "planRunId": plan["planRunId"],
        "language": plan["language"],
        "version": plan["version"],
        "unit": copy.deepcopy(unit),
        "evidenceBundleHash": "sha256:" + "a" * 64,
        "runId": f"semantic-run:{unit['unitId'].split(':')[1]}-{revision}",
        "createdAt": "2026-01-01T00:00:00Z",
        "outcome": "SUCCESS",
        "semantics": {
            "unitKind": "LANGUAGE_CONSTRUCT",
            "identity": {"name": unit["name"], "evidenceIds": ["evidence:identity"]},
            "syntaxForms": [],
            "inputs": [],
            "edgeCases": [],
            "stateEffects": [],
            "restrictions": [],
            "dependencies": [
                {
                    "dependencyId": f"shared:{name}",
                    "concept": f"Shared {name}",
                    "description": f"The units use one {name} domain ({revision}).",
                    "semanticClaimIds": [f"claim:{name}"],
                    "evidenceIds": [f"evidence:{name}"],
                }
                for name in names
            ],
            "claims": [
                {
                    "claimId": f"claim:{name}",
                    "kind": "SOURCE_FACT",
                    "statement": f"The shared {name} has semantics {revision}.",
                    "evidenceIds": [f"evidence:{name}"],
                }
                for name in names
            ] + [{
                "claimId": "claim:unit-only",
                "kind": "DESIGN_DEPENDENCY",
                "statement": f"{unit['name']} has a private implementation detail.",
                "evidenceIds": [],
            }],
        },
    }


def _inputs(*, dependencies=("value",), revision="initial") -> tuple[dict, dict[str, dict]]:
    plan = _plan(dependencies=dependencies)
    return plan, {
        unit["unitId"]: _semantics(plan, unit, revision=revision) for unit in UNITS
    }


def _lean_component(value: str) -> str:
    return "".join(part.capitalize() for part in value.replace(":", "-").split("-") if part)


def _candidate(context: dict) -> dict:
    parent = context.get("parentCore")
    source = parent["leanSource"] if parent else ""
    declarations = copy.deepcopy(parent["manifest"]["declarations"] if parent else [])
    parent_concepts = {
        item["dependencyId"]: item for item in (parent["manifest"]["concepts"] if parent else [])
    }
    concepts = []
    existing_names = {item["declaration"] for item in declarations}
    additions = []
    requirements = {item["dependencyId"]: item for item in context["requirements"]}
    for dependency_id in sorted(set(parent_concepts) | set(requirements)):
        if dependency_id in parent_concepts:
            lean_names = list(parent_concepts[dependency_id]["leanDeclarations"])
        else:
            local = _lean_component(dependency_id.split(":", 1)[1])
            base_namespace = "Spec2Lean.Synthetic.Shared"
            lineage_namespace = context.get("leanNamespace")
            declaration_namespace = (
                f"{lineage_namespace}.{base_namespace}"
                if lineage_namespace else base_namespace
            )
            qualified = f"{declaration_namespace}.{local}"
            lean_names = [qualified]
            additions.append(
                f"namespace {declaration_namespace}\n\n"
                f"structure {local} where\n  payload : Nat\n\n"
                f"end {declaration_namespace}\n"
            )
            requirement = requirements[dependency_id]
            declarations.append({
                "declaration": qualified,
                "role": "PRIMARY_TYPE",
                "dependencyIds": [dependency_id],
                "claimRefs": copy.deepcopy(requirement["claimRefs"]),
            })
            existing_names.add(qualified)
        concepts.append({"dependencyId": dependency_id, "leanDeclarations": lean_names})
    if additions:
        source += ("\n" if source else "") + "\n".join(additions)
    return {"leanSource": source, "concepts": concepts, "declarations": declarations}


def _finite_width_candidate(width: int):
    def candidate(context: dict) -> dict:
        assert context.get("parentCore") is None
        requirement = context["requirements"][0]
        dependency_id = requirement["dependencyId"]
        claim_refs = copy.deepcopy(requirement["claimRefs"])
        namespace = "SharedBoundary"
        word = f"{namespace}.Word"
        width_name = f"{namespace}.width"
        clamp = f"{namespace}.clampAmount"
        return {
            "leanSource": (
                "import Std\n\n"
                f"namespace {namespace}\n\n"
                f"abbrev Word := BitVec {width}\n\n"
                f"def width : Nat := {width}\n\n"
                "def clampAmount (amount : Word) : Nat :=\n"
                "  min amount.toNat width\n\n"
                f"end {namespace}\n"
            ),
            "concepts": [{
                "dependencyId": dependency_id,
                "leanDeclarations": [word, width_name, clamp],
            }],
            "declarations": [
                {
                    "declaration": word,
                    "role": "PRIMARY_TYPE",
                    "dependencyIds": [dependency_id],
                    "claimRefs": claim_refs,
                },
                {
                    "declaration": width_name,
                    "role": "SEMANTIC_HELPER",
                    "dependencyIds": [dependency_id],
                    "claimRefs": claim_refs,
                },
                {
                    "declaration": clamp,
                    "role": "EDGE_CASE_HELPER",
                    "dependencyIds": [dependency_id],
                    "claimRefs": claim_refs,
                },
            ],
        }

    return candidate


def _fake_run(calls: list[dict], candidate_builder=_candidate):
    def run(command, **kwargs):
        config = json.loads(kwargs["env"]["OPENCODE_CONFIG_CONTENT"])
        mcp_command = config["mcp"]["shared_core"]["command"]

        def argument(name: str) -> Path:
            return Path(mcp_command[mcp_command.index(name) + 1])

        context = json.loads(argument("--context").read_text(encoding="utf-8"))
        calls.append(context)
        server = SharedCoreMcpServer(context, argument("--submission"))
        result = server.call_tool("submit_core", candidate_builder(context))
        accepted = json.loads(result["content"][0]["text"])
        assert accepted["accepted"] is True, accepted
        return subprocess.CompletedProcess(command, 0, '{"sessionID":"shared-core-session"}\n', "")

    return run


def _passing_build(path: Path) -> dict:
    assert path.is_file() and path.suffix == ".lean"
    return {
        "status": "PASS", "exitCode": 0, "leanVersion": "Lean 4.test",
        "durationMs": 1, "diagnostics": [],
    }


def _with_manifest(core, manifest: dict):
    return replace(core, manifest=manifest, manifest_hash=json_hash(manifest))


@pytest.fixture
def materializer(monkeypatch):
    real_which = shutil.which
    monkeypatch.setattr(
        "spec2lean.translation.shared_core.runner.shutil.which",
        lambda name: "/usr/bin/opencode" if name == "opencode" else real_which(name),
    )
    monkeypatch.setattr(
        "spec2lean.translation.shared_core.runner._require_model", lambda _: None
    )


def test_requirement_collection_is_explicit_generic_and_unit_scoped():
    plan, semantics = _inputs(dependencies=("value", "environment"))
    plan["externalPrerequisites"] = [{
        "dependencyId": "shared:not-a-planned-shared-prerequisite",
        "requiredBy": ["unit:alpha", "unit:beta"],
    }]
    requirements = collect_shared_requirements(plan, semantics)
    assert [item.dependency_id for item in requirements] == [
        "shared:environment", "shared:value"
    ]
    assert requirements[0].kind == "synthetic-environment-domain"
    assert requirements[0].claim_refs == (
        ("unit:alpha", "claim:environment"), ("unit:beta", "claim:environment")
    )
    assert relevant_dependency_ids(plan, ["unit:alpha"]) == (
        "shared:environment", "shared:value"
    )
    assert all("claim:unit-only" not in item.claim_refs for item in requirements)

    one_unit = copy.deepcopy(plan)
    next(
        item for item in one_unit["sharedPrerequisites"]
        if item["dependencyId"] == "shared:environment"
    )["requiredBy"] = ["unit:alpha"]
    scoped = collect_shared_requirements(one_unit, semantics)
    environment = next(
        item for item in scoped if item.dependency_id == "shared:environment"
    )
    assert environment.required_by == ("unit:alpha",)
    assert environment.claim_refs == (("unit:alpha", "claim:environment"),)

    missing = copy.deepcopy(semantics)
    del missing["unit:alpha"]["semantics"]["dependencies"][0]["semanticClaimIds"]
    with pytest.raises(MissingSharedAbstraction) as raised:
        collect_shared_requirements(plan, missing)
    condition = raised.value.to_dict()
    assert condition["code"] == "MISSING_SHARED_ABSTRACTION"
    assert condition["dependencyId"] == "shared:value"
    assert condition["semanticRequirement"]["unitId"] == "unit:alpha"


def test_manifest_registry_freshness_and_traceability_round_trip(
    tmp_path, materializer
):
    plan, semantics = _inputs()
    calls: list[dict] = []
    core = ensure_shared_core(
        plan, semantics, tmp_path, run_command=_fake_run(calls), build_runner=_passing_build
    )
    assert len(calls) == 1 and core.reused is False
    assert core.core_run_id.startswith("shared-core-run:")
    assert core.source_path.relative_to(core.directory).parts[0] == "modules"
    assert core.manifest["concepts"][0]["dependencyId"] == "shared:value"
    declaration = core.manifest["concepts"][0]["leanDeclarations"][0]
    mapping = core.manifest["declarations"][0]
    assert mapping["declaration"] == declaration
    assert mapping["dependencyIds"] == ["shared:value"]
    assert mapping["claimRefs"] == [
        {"unitId": "unit:alpha", "claimId": "claim:value"},
        {"unitId": "unit:beta", "claimId": "claim:value"},
    ]
    assert {item["unitId"] for item in core.manifest["semanticArtifacts"]} == {
        "unit:alpha", "unit:beta"
    }
    assert validate_core_artifact(plan, semantics, core) == []
    assert load_current_core(tmp_path, plan).core_run_id == core.core_run_id
    assert load_core(tmp_path, plan, core.core_run_id).reference() == core.reference()
    pointer = json.loads(
        (tmp_path / "synthetic" / "1.0" / "shared" / "current.json").read_text()
    )
    assert pointer == {"schemaVersion": 1, **core.reference()}

    registry_variant = copy.deepcopy(core.manifest["declarations"])
    registry_variant[0]["role"] = "OPERATION"
    assert core_run_id_for(
        plan, core.source_hash, core.manifest["concepts"], registry_variant
    ) != core.core_run_id

    missing_trace = copy.deepcopy(core.manifest)
    missing_trace["semanticArtifacts"] = []
    diagnostics = validate_core_artifact(
        plan, semantics, _with_manifest(core, missing_trace)
    )
    assert "MISSING_SEMANTIC_ARTIFACT" in {
        item["code"] for item in diagnostics
    }


def test_fresh_core_reuses_without_materializer_or_build(tmp_path, materializer):
    plan, semantics = _inputs()
    calls: list[dict] = []
    first = ensure_shared_core(
        plan, semantics, tmp_path, run_command=_fake_run(calls), build_runner=_passing_build
    )

    def forbidden(*_args, **_kwargs):
        raise AssertionError("fresh core must not invoke external work")

    second = ensure_shared_core(
        plan, semantics, tmp_path, run_command=forbidden, build_runner=forbidden
    )
    assert second.core_run_id == first.core_run_id
    assert second.reused is True

    next_plan = copy.deepcopy(plan)
    next_plan["planRunId"] = "plan:shared-core-test-next-run"
    next_semantics = {
        unit["unitId"]: _semantics(next_plan, unit) for unit in UNITS
    }
    for artifact in next_semantics.values():
        artifact["runId"] += "-next"
        next(
            claim for claim in artifact["semantics"]["claims"]
            if claim["claimId"] == "claim:unit-only"
        )["statement"] += " Unrelated revision."
    cross_run = ensure_shared_core(
        next_plan, next_semantics, tmp_path,
        run_command=forbidden, build_runner=forbidden,
    )
    assert cross_run.core_run_id == first.core_run_id
    assert cross_run.reused is True
    assert len(calls) == 1


def test_semantic_change_invalidates_without_freezing_the_old_representation(
    tmp_path, materializer
):
    plan, semantics = _inputs()
    calls: list[dict] = []
    first = ensure_shared_core(
        plan, semantics, tmp_path, run_command=_fake_run(calls), build_runner=_passing_build
    )
    revised = {
        unit["unitId"]: _semantics(plan, unit, revision="revised") for unit in UNITS
    }
    second = ensure_shared_core(
        plan, revised, tmp_path, run_command=_fake_run(calls), build_runner=_passing_build
    )
    assert len(calls) == 2
    assert second.core_run_id != first.core_run_id
    assert calls[1]["parentCore"] is None
    assert second.manifest["parentCoreRunId"] is None
    assert second.manifest["concepts"][0]["semanticInputHash"] != first.manifest["concepts"][0]["semanticInputHash"]
    assert validate_core_artifact(plan, revised, second) == []


def test_source_digest_change_rematerializes_and_malformed_pointer_is_repaired(
    tmp_path, materializer
):
    plan, semantics = _inputs()
    calls: list[dict] = []
    first = ensure_shared_core(
        plan, semantics, tmp_path,
        run_command=_fake_run(calls), build_runner=_passing_build,
    )
    pointer = tmp_path / "synthetic" / "1.0" / "shared" / "current.json"
    pointer.write_text("{malformed\n", encoding="utf-8")
    repaired = ensure_shared_core(
        plan, semantics, tmp_path,
        run_command=_fake_run(calls), build_runner=_passing_build,
    )
    assert repaired.core_run_id == first.core_run_id
    assert repaired.reused is True and len(calls) == 1
    assert json.loads(pointer.read_text())["coreRunId"] == first.core_run_id

    revised_plan = copy.deepcopy(plan)
    revised_plan["sourceDatabaseDigest"] = "digest:reindexed-source"
    revised = ensure_shared_core(
        revised_plan, semantics, tmp_path,
        run_command=_fake_run(calls), build_runner=_passing_build,
    )
    assert revised.core_run_id != first.core_run_id
    assert len(calls) == 2
    assert calls[-1]["parentCore"] is None
    assert first.directory.is_dir()
    assert json.loads(pointer.read_text())["coreRunId"] == revised.core_run_id


def test_controlled_extension_adds_concept_once_and_is_then_reused(
    tmp_path, materializer
):
    first_plan, first_semantics = _inputs()
    calls: list[dict] = []
    first = ensure_shared_core(
        first_plan, first_semantics, tmp_path,
        run_command=_fake_run(calls), build_runner=_passing_build,
    )
    extended_plan, extended_semantics = _inputs(dependencies=("value", "environment"))
    gamma = {
        "unitId": "unit:gamma", "name": "gamma", "sourceNodeIds": ["node:gamma"]
    }
    extended_plan["requestedUnits"].append(gamma)
    next(
        item for item in extended_plan["sharedPrerequisites"]
        if item["dependencyId"] == "shared:environment"
    )["requiredBy"] = [gamma["unitId"]]
    extended_semantics[gamma["unitId"]] = _semantics(extended_plan, gamma)
    extended = ensure_shared_core(
        extended_plan, extended_semantics, tmp_path,
        run_command=_fake_run(calls), build_runner=_passing_build,
    )
    assert extended.core_run_id != first.core_run_id
    assert extended.source.startswith(first.source)
    assert extended.manifest["parentCoreRunId"] == first.core_run_id
    assert extended.manifest["leanNamespace"] == first.manifest["leanNamespace"]
    assert extended.lean_module != first.lean_module
    assert [item["dependencyId"] for item in extended.manifest["concepts"]] == [
        "shared:environment", "shared:value"
    ]
    names = [item["declaration"] for item in extended.manifest["declarations"]]
    assert len(names) == len(set(names)) == 2
    assert all(
        name.startswith(first.manifest["leanNamespace"] + ".") for name in names
    )
    assert first.manifest["declarations"][0] in extended.manifest["declarations"]
    reused = ensure_shared_core(
        extended_plan, extended_semantics, tmp_path,
        run_command=lambda *_a, **_k: (_ for _ in ()).throw(AssertionError()),
        build_runner=lambda *_a, **_k: (_ for _ in ()).throw(AssertionError()),
    )
    assert reused.core_run_id == extended.core_run_id and reused.reused is True
    assert len(calls) == 2


def test_concurrent_materializers_publish_exactly_one_frozen_snapshot(
    tmp_path, materializer
):
    plan, semantics = _inputs()
    calls: list[dict] = []
    runner = _fake_run(calls)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                ensure_shared_core, plan, semantics, tmp_path,
                run_command=runner, build_runner=_passing_build,
            )
            for _ in range(2)
        ]
    cores = [future.result() for future in futures]
    assert len(calls) == 1
    assert len({core.core_run_id for core in cores}) == 1
    assert sorted(core.reused for core in cores) == [False, True]
    versions = list((tmp_path / "synthetic" / "1.0" / "shared" / "versions").iterdir())
    assert [path.name for path in versions] == [cores[0].core_run_id]


def test_extension_rejects_parent_source_or_registry_rewrite(tmp_path, materializer):
    plan, semantics = _inputs()
    core = ensure_shared_core(
        plan, semantics, tmp_path, run_command=_fake_run([]), build_runner=_passing_build
    )
    requirements = collect_shared_requirements(plan, semantics)
    changed_source = _candidate({
        "requirements": [item.to_dict() for item in requirements],
        "parentCore": {"manifest": core.manifest, "leanSource": core.source},
    })
    changed_source["leanSource"] = changed_source["leanSource"].replace("payload : Nat", "payload : Int", 1)
    _, diagnostics = normalize_core_submission(requirements, changed_source, parent=core)
    assert "CORE_PREFIX_CHANGED" in {item["code"] for item in diagnostics}

    changed_mapping = _candidate({
        "requirements": [item.to_dict() for item in requirements],
        "parentCore": {"manifest": core.manifest, "leanSource": core.source},
    })
    changed_mapping["declarations"][0]["role"] = "SEMANTIC_HELPER"
    _, diagnostics = normalize_core_submission(requirements, changed_mapping, parent=core)
    assert "CORE_MAPPING_CHANGED" in {item["code"] for item in diagnostics}

    extended_plan, extended_semantics = _inputs(
        dependencies=("value", "environment")
    )
    extended_requirements = collect_shared_requirements(
        extended_plan, extended_semantics
    )
    ownership_rewrite = _candidate({
        "requirements": [item.to_dict() for item in extended_requirements],
        "parentCore": {"manifest": core.manifest, "leanSource": core.source},
    })
    environment_name = next(
        item["declaration"] for item in ownership_rewrite["declarations"]
        if item["dependencyIds"] == ["shared:environment"]
    )
    next(
        item for item in ownership_rewrite["concepts"]
        if item["dependencyId"] == "shared:value"
    )["leanDeclarations"].append(environment_name)
    next(
        item for item in ownership_rewrite["declarations"]
        if item["declaration"] == environment_name
    )["dependencyIds"].append("shared:value")
    _, diagnostics = normalize_core_submission(
        extended_requirements, ownership_rewrite, parent=core
    )
    assert "CORE_MAPPING_CHANGED" in {item["code"] for item in diagnostics}

    malformed = copy.deepcopy(core.manifest)
    malformed["concepts"][0]["requiredBy"] = None
    malformed["concepts"][0]["claimRefs"] = None
    malformed["declarations"].append("not-an-object")
    assert validate_core_artifact(
        plan, semantics, _with_manifest(core, malformed)
    )


def test_unit_specific_semantics_do_not_enter_an_empty_core(tmp_path):
    plan = _plan(dependencies=())
    semantics = {
        unit["unitId"]: _semantics(plan, unit) for unit in UNITS
    }
    invoked = False

    def forbidden(*_args, **_kwargs):
        nonlocal invoked
        invoked = True
        raise AssertionError("an empty shared scope must not invoke OpenCode")

    core = ensure_shared_core(
        plan, semantics, tmp_path, run_command=forbidden, build_runner=_passing_build
    )
    assert invoked is False
    assert core.manifest["concepts"] == []
    assert core.manifest["declarations"] == []
    assert "unit-only" not in core.source
    assert validate_core_artifact(plan, semantics, core) == []


def test_one_helper_can_be_registered_once_for_multiple_generic_dependencies():
    plan, semantics = _inputs(dependencies=("value", "environment"))
    requirements = collect_shared_requirements(plan, semantics)
    refs = {
        item.dependency_id: [
            {"unitId": unit_id, "claimId": claim_id}
            for unit_id, claim_id in item.claim_refs
        ]
        for item in requirements
    }
    source = """namespace Spec2Lean.Synthetic.Shared

structure Environment where
  payload : Nat

structure Value where
  payload : Nat

def commonSize (value : Value) : Nat := value.payload

end Spec2Lean.Synthetic.Shared
"""
    helper = "Spec2Lean.Synthetic.Shared.commonSize"
    submission = {
        "leanSource": source,
        "concepts": [
            {"dependencyId": "shared:environment", "leanDeclarations": ["Spec2Lean.Synthetic.Shared.Environment", helper]},
            {"dependencyId": "shared:value", "leanDeclarations": ["Spec2Lean.Synthetic.Shared.Value", helper]},
        ],
        "declarations": [
            {"declaration": "Spec2Lean.Synthetic.Shared.Environment", "role": "PRIMARY_TYPE", "dependencyIds": ["shared:environment"], "claimRefs": refs["shared:environment"]},
            {"declaration": "Spec2Lean.Synthetic.Shared.Value", "role": "PRIMARY_TYPE", "dependencyIds": ["shared:value"], "claimRefs": refs["shared:value"]},
            {"declaration": helper, "role": "IMPLEMENTATION_HELPER", "dependencyIds": ["shared:environment", "shared:value"], "claimRefs": [], "supportsDeclarations": ["Spec2Lean.Synthetic.Shared.Value"]},
        ],
    }
    candidate, diagnostics = normalize_core_submission(requirements, submission)
    assert diagnostics == [] and candidate is not None
    assert [item["declaration"] for item in candidate["declarations"]].count(helper) == 1


@pytest.mark.skipif(shutil.which("lean") is None, reason="Lean toolchain is not installed")
def test_incompatible_root_cores_with_same_inner_names_coimport(
    tmp_path, materializer
):
    plan, semantics = _inputs()
    calls: list[dict] = []

    def incompatible_candidate(context: dict) -> dict:
        candidate = _candidate(context)
        revised = any(
            "revised" in str(claim.get("statement", ""))
            for requirement in context["requirements"]
            for claim in requirement["claims"]
        )
        if revised:
            assert context.get("parentCore") is None
            candidate["leanSource"] = candidate["leanSource"].replace(
                "payload : Nat", "payload : Int"
            )
        return candidate

    runner = _fake_run(calls, incompatible_candidate)
    first = ensure_shared_core(
        plan, semantics, tmp_path,
        run_command=runner, build_runner=run_build_test,
    )
    revised_semantics = {
        unit["unitId"]: _semantics(plan, unit, revision="revised")
        for unit in UNITS
    }
    second = ensure_shared_core(
        plan, revised_semantics, tmp_path,
        run_command=runner, build_runner=run_build_test,
    )

    first_namespace = first.manifest["leanNamespace"]
    second_namespace = second.manifest["leanNamespace"]
    first_declaration = first.manifest["concepts"][0]["leanDeclarations"][0]
    second_declaration = second.manifest["concepts"][0]["leanDeclarations"][0]
    assert calls[1]["parentCore"] is None
    assert first_namespace != second_namespace
    assert first.lean_module != second.lean_module
    assert first_declaration.removeprefix(first_namespace + ".") == (
        second_declaration.removeprefix(second_namespace + ".")
    ) == "Spec2Lean.Synthetic.Shared.Value"

    together = tmp_path / "Together.lean"
    together.write_text(
        f"import {first.lean_module}\n"
        f"import {second.lean_module}\n\n"
        f"#check {first_declaration}\n"
        f"#check {second_declaration}\n",
        encoding="utf-8",
    )
    result = run_build_test(together, dependency_modules=[
        (first.lean_module, first.source_path),
        (second.lean_module, second.source_path),
    ])
    assert result["status"] == "PASS", result["diagnostics"]


@pytest.mark.skipif(shutil.which("lean") is None, reason="Lean toolchain is not installed")
def test_generic_finite_width_helper_compiles_boundary_guards(
    tmp_path, materializer
):
    width = 8
    plan, semantics = _inputs()
    prerequisite = plan["sharedPrerequisites"][0]
    prerequisite.update({
        "name": "Finite-width amount domain",
        "kind": "finite-width-boundary-domain",
        "reason": "Both constructs use the same finite-width clamping boundary.",
    })
    for artifact in semantics.values():
        dependency = artifact["semantics"]["dependencies"][0]
        dependency["concept"] = prerequisite["name"]
        dependency["description"] = (
            f"Amounts inhabit width {width}; values above {width} clamp to {width}."
        )
        artifact["semantics"]["claims"][0]["statement"] = (
            f"The finite width is {width}, and amounts above it clamp to {width}."
        )

    core = ensure_shared_core(
        plan, semantics, tmp_path,
        run_command=_fake_run([], _finite_width_candidate(width)),
        build_runner=run_build_test,
    )
    mappings = {
        item["declaration"]: item for item in core.manifest["declarations"]
    }
    word = next(name for name in mappings if name.endswith(".SharedBoundary.Word"))
    clamp = next(
        name for name in mappings if name.endswith(".SharedBoundary.clampAmount")
    )
    assert mappings[clamp]["claimRefs"] == [
        {"unitId": "unit:alpha", "claimId": "claim:value"},
        {"unitId": "unit:beta", "claimId": "claim:value"},
    ]

    amounts = (0, width // 2, width - 1, width, width + 1)
    expected = (0, width // 2, width - 1, width, width)
    guards = "\n".join(
        f"#guard {clamp} ({amount} : {word}) == {result}"
        for amount, result in zip(amounts, expected)
    )
    boundary_file = tmp_path / "SharedBoundaryTests.lean"
    boundary_file.write_text(
        f"import {core.lean_module}\n\n{guards}\n", encoding="utf-8"
    )
    result = run_build_test(
        boundary_file,
        dependency_modules=[(core.lean_module, core.source_path)],
    )
    assert result["status"] == "PASS", result["diagnostics"]


@pytest.mark.skipif(shutil.which("lean") is None, reason="Lean toolchain is not installed")
def test_materialized_core_compiles_with_project_lean(tmp_path, materializer):
    plan, semantics = _inputs()
    core = ensure_shared_core(
        plan, semantics, tmp_path, run_command=_fake_run([]), build_runner=run_build_test
    )
    assert json.loads(core.run_path.read_text())["build"]["status"] == "PASS"
