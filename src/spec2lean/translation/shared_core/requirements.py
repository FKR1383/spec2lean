from __future__ import annotations

from typing import Any, Iterable

from ...util import canonical_json
from ..models import semantics_artifact_hash
from .models import MissingSharedAbstraction, SharedRequirement, json_hash


def _dependency_id(value: dict[str, Any]) -> str | None:
    candidate = value.get("dependencyId", value.get("id"))
    return candidate if isinstance(candidate, str) else None


def _shared_prerequisites(plan: dict[str, Any]) -> list[dict[str, Any]]:
    raw = plan.get("sharedPrerequisites", [])
    if not isinstance(raw, list):
        raise ValueError("Phase-2 sharedPrerequisites must be an array")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    requested = {
        str(item.get("unitId"))
        for item in plan.get("requestedUnits", [])
        if isinstance(item, dict) and isinstance(item.get("unitId"), str)
    }
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"sharedPrerequisites[{index}] must be an object")
        dependency_id = _dependency_id(item)
        if not dependency_id or not dependency_id.startswith("shared:"):
            raise ValueError(f"sharedPrerequisites[{index}] requires a shared:* dependencyId")
        if dependency_id in seen:
            raise ValueError(f"duplicate shared prerequisite: {dependency_id}")
        seen.add(dependency_id)
        name, kind = item.get("name"), item.get("kind")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"shared prerequisite {dependency_id} requires a name")
        if not isinstance(kind, str) or not kind.strip():
            raise ValueError(f"shared prerequisite {dependency_id} requires an extensible kind")
        source_ids = item.get("sourceNodeIds")
        if (
            not isinstance(source_ids, list)
            or not source_ids
            or not all(isinstance(value, str) and value.startswith("node:") for value in source_ids)
        ):
            raise ValueError(f"shared prerequisite {dependency_id} requires sourceNodeIds")
        required_by = item.get("requiredBy")
        if (
            not isinstance(required_by, list)
            or not required_by
            or not all(isinstance(value, str) and value in requested for value in required_by)
        ):
            raise ValueError(
                f"shared prerequisite {dependency_id} must be required by selected units"
            )
        if len(required_by) != len(set(required_by)):
            raise ValueError(f"shared prerequisite {dependency_id} has duplicate requiredBy entries")
        result.append({
            "dependencyId": dependency_id,
            "name": name.strip(),
            "kind": kind.strip(),
            "sourceNodeIds": sorted(set(source_ids)),
            "requiredBy": sorted(required_by),
        })
    return sorted(result, key=lambda item: item["dependencyId"])


def relevant_dependency_ids(
    plan: dict[str, Any], unit_ids: Iterable[str] | None = None
) -> tuple[str, ...]:
    selected = (
        {
            str(item.get("unitId"))
            for item in plan.get("requestedUnits", [])
            if isinstance(item, dict) and isinstance(item.get("unitId"), str)
        }
        if unit_ids is None
        else {str(item) for item in unit_ids}
    )
    return tuple(
        item["dependencyId"]
        for item in _shared_prerequisites(plan)
        if selected.intersection(item["requiredBy"])
    )


def _missing(
    prerequisite: dict[str, Any], unit_id: str, detail: str,
    claim_refs: list[dict[str, str]] | None = None,
) -> MissingSharedAbstraction:
    return MissingSharedAbstraction(
        dependency_id=prerequisite["dependencyId"],
        semantic_requirement={
            "name": prerequisite["name"],
            "kind": prerequisite["kind"],
            "requiredBy": list(prerequisite["requiredBy"]),
            "unitId": unit_id,
        },
        claim_refs=claim_refs or [],
        detail=detail,
    )


def collect_shared_requirements(
    plan: dict[str, Any], semantics_by_unit: dict[str, dict[str, Any]],
    unit_ids: Iterable[str] | None = None,
) -> tuple[SharedRequirement, ...]:
    selected = None if unit_ids is None else {str(item) for item in unit_ids}
    requirements: list[SharedRequirement] = []
    for prerequisite in _shared_prerequisites(plan):
        required_units = [
            unit_id for unit_id in prerequisite["requiredBy"]
            if selected is None or unit_id in selected
        ]
        if not required_units:
            continue
        semantic_dependencies: list[dict[str, Any]] = []
        claims: list[dict[str, Any]] = []
        claim_refs: list[tuple[str, str]] = []
        artifacts: list[dict[str, str]] = []
        for unit_id in required_units:
            artifact = semantics_by_unit.get(unit_id)
            if not isinstance(artifact, dict):
                raise _missing(prerequisite, unit_id, "the required Phase-4 artifact is absent")
            if artifact.get("phase") != "SEMANTIC_EXTRACTOR" or artifact.get("outcome") != "SUCCESS":
                raise _missing(prerequisite, unit_id, "the required Phase-4 artifact is not successful")
            if artifact.get("planRunId") != plan.get("planRunId"):
                raise _missing(prerequisite, unit_id, "the Phase-4 artifact belongs to another plan")
            if artifact.get("language") != plan.get("language") or artifact.get("version") != plan.get("version"):
                raise _missing(prerequisite, unit_id, "the Phase-4 artifact belongs to another specification")
            artifact_unit = artifact.get("unit")
            if not isinstance(artifact_unit, dict) or artifact_unit.get("unitId") != unit_id:
                raise _missing(prerequisite, unit_id, "the Phase-4 artifact belongs to another unit")
            payload = artifact.get("semantics")
            raw_dependencies = payload.get("dependencies") if isinstance(payload, dict) else None
            if not isinstance(raw_dependencies, list):
                raise _missing(prerequisite, unit_id, "Phase 4 has no semantic dependency array")
            matches = [
                item for item in raw_dependencies
                if isinstance(item, dict) and item.get("dependencyId") == prerequisite["dependencyId"]
            ]
            if len(matches) != 1:
                raise _missing(
                    prerequisite, unit_id,
                    "Phase 4 must contain exactly one dependency with this dependencyId",
                )
            dependency = matches[0]
            description = dependency.get("description")
            claim_ids = dependency.get("semanticClaimIds")
            if not isinstance(description, str) or not description.strip():
                raise _missing(prerequisite, unit_id, "the semantic dependency has no description")
            if (
                not isinstance(claim_ids, list)
                or not claim_ids
                or not all(isinstance(value, str) and value.startswith("claim:") for value in claim_ids)
                or len(claim_ids) != len(set(claim_ids))
            ):
                raise _missing(
                    prerequisite, unit_id,
                    "the semantic dependency requires unique, explicit semanticClaimIds",
                )
            raw_claims = payload.get("claims")
            if not isinstance(raw_claims, list):
                raise _missing(
                    prerequisite, unit_id,
                    "Phase 4 has no structured semantic claim array",
                )
            claims_by_id: dict[str, dict[str, Any]] = {}
            for claim in raw_claims:
                claim_id = claim.get("claimId") if isinstance(claim, dict) else None
                if not isinstance(claim_id, str):
                    raise _missing(
                        prerequisite, unit_id,
                        "Phase 4 contains a malformed semantic claim",
                    )
                if claim_id in claims_by_id:
                    raise _missing(
                        prerequisite, unit_id,
                        f"Phase 4 contains duplicate semantic claim ID {claim_id}",
                    )
                claims_by_id[claim_id] = claim
            current_refs = [
                {"unitId": unit_id, "claimId": claim_id} for claim_id in claim_ids
            ]
            missing_ids = [claim_id for claim_id in claim_ids if claim_id not in claims_by_id]
            if missing_ids:
                raise _missing(
                    prerequisite, unit_id,
                    "semanticClaimIds reference missing Phase-4 claims: " + ", ".join(missing_ids),
                    current_refs,
                )
            dependency_copy = dict(dependency)
            dependency_copy["unitId"] = unit_id
            semantic_dependencies.append(dependency_copy)
            for claim_id in claim_ids:
                claim_refs.append((unit_id, claim_id))
                claims.append({"unitId": unit_id, **dict(claims_by_id[claim_id])})
            run_id = artifact.get("runId")
            if not isinstance(run_id, str) or not run_id.startswith("semantic-run:"):
                raise _missing(prerequisite, unit_id, "the Phase-4 run ID is missing or malformed")
            artifacts.append({
                "planRunId": str(artifact["planRunId"]),
                "unitId": unit_id,
                "runId": run_id,
                "artifactHash": semantics_artifact_hash(artifact),
            })
        fingerprint = {
            "sourceDatabaseDigest": plan.get("sourceDatabaseDigest"),
            "prerequisite": {
                key: prerequisite[key]
                for key in ("dependencyId", "name", "kind", "sourceNodeIds")
            },
            "semanticDependencies": sorted(
                semantic_dependencies, key=lambda item: (item["unitId"], canonical_json(item))
            ),
            "claims": sorted(claims, key=lambda item: (item["unitId"], item["claimId"])),
        }
        requirements.append(SharedRequirement(
            dependency_id=prerequisite["dependencyId"],
            name=prerequisite["name"],
            kind=prerequisite["kind"],
            source_node_ids=tuple(prerequisite["sourceNodeIds"]),
            required_by=tuple(required_units),
            semantic_input_hash=json_hash(fingerprint),
            claim_refs=tuple(sorted(claim_refs)),
            semantic_dependencies=tuple(semantic_dependencies),
            claims=tuple(claims),
            semantic_artifacts=tuple(artifacts),
        ))
    return tuple(sorted(requirements, key=lambda item: item.dependency_id))
