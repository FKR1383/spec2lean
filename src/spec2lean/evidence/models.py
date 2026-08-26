from __future__ import annotations

from dataclasses import dataclass
from typing import Any


EVIDENCE_ROLES = (
    "SYNTAX",
    "OPERANDS",
    "TYPE_RULES",
    "OPERATION",
    "ALGORITHM",
    "EDGE_CASE",
    "STATE_EFFECT",
    "PREDICATION",
    "VERSION_OR_TARGET_RESTRICTION",
    "EXAMPLE",
    "SUPPORTING_DEFINITION",
    "OTHER",
)
EVIDENCE_TIERS = ("CORE", "SUPPORTING")


@dataclass(frozen=True, slots=True)
class EvidenceScope:
    """The deterministic Phase-2 boundary for one retriever session."""

    plan_run_id: str
    language: str
    version: str
    source_database_digest: str
    unit: dict[str, Any]
    prerequisites: tuple[dict[str, Any], ...]
    dependencies: tuple[dict[str, Any], ...]
    seed_nodes: tuple[tuple[str, str], ...]

    @property
    def unit_id(self) -> str:
        return str(self.unit["unitId"])

    @classmethod
    def from_plan(cls, plan: dict[str, Any], unit_id: str) -> EvidenceScope:
        matches = [item for item in plan.get("requestedUnits", []) if item.get("unitId") == unit_id]
        if len(matches) != 1:
            raise KeyError(f"unit is not uniquely present in plan {plan.get('planRunId')}: {unit_id}")
        unit = matches[0]
        dependencies = tuple(
            edge for edge in plan.get("dependencies", [])
            if edge.get("from") == unit_id or edge.get("to") == unit_id
        )
        prerequisite_ids = {
            endpoint
            for edge in dependencies
            for endpoint in (edge.get("from"), edge.get("to"))
            if isinstance(endpoint, str) and endpoint.startswith("prerequisite:")
        }
        prerequisites = tuple(
            item for item in plan.get("externalPrerequisites", [])
            if item.get("prerequisiteId") in prerequisite_ids
        )
        seeds: list[tuple[str, str]] = []
        for node_id in unit.get("sourceNodeIds", []):
            seeds.append((node_id, "UNIT_SOURCE"))
        for item in prerequisites:
            basis = f"PREREQUISITE:{item['prerequisiteId']}"
            for node_id in item.get("sourceNodeIds", []):
                seeds.append((node_id, basis))
        for index, edge in enumerate(dependencies):
            for node_id in edge.get("supportingNodeIds", []):
                seeds.append((node_id, f"PHASE2_DEPENDENCY:{index}"))
        return cls(
            plan_run_id=str(plan["planRunId"]),
            language=str(plan["language"]),
            version=str(plan["version"]),
            source_database_digest=str(plan["sourceDatabaseDigest"]),
            unit=dict(unit),
            prerequisites=tuple(dict(item) for item in prerequisites),
            dependencies=tuple(dict(item) for item in dependencies),
            seed_nodes=tuple(dict.fromkeys(seeds)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": 1,
            "planRunId": self.plan_run_id,
            "language": self.language,
            "version": self.version,
            "sourceDatabaseDigest": self.source_database_digest,
            "unit": dict(self.unit),
            "relevantExternalPrerequisites": [dict(item) for item in self.prerequisites],
            "relatedDependencies": [dict(item) for item in self.dependencies],
            "seedNodes": [{"nodeId": node, "basis": basis} for node, basis in self.seed_nodes],
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> EvidenceScope:
        return cls(
            plan_run_id=value["planRunId"],
            language=value["language"],
            version=value["version"],
            source_database_digest=value["sourceDatabaseDigest"],
            unit=dict(value["unit"]),
            prerequisites=tuple(value.get("relevantExternalPrerequisites", ())),
            dependencies=tuple(value.get("relatedDependencies", ())),
            seed_nodes=tuple((item["nodeId"], item["basis"]) for item in value.get("seedNodes", ())),
        )
