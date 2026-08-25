from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter
from typing import Any

from ..constants import (
    DEPENDENCY_ORIGINS,
    DEPENDENCY_TYPES,
    PLAN_SCHEMA_VERSION,
    UNIT_KINDS,
)
from .graph import derive_graph


UNIT_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
NODE_ID_PATTERN = re.compile(r"^node:[0-9a-f]{24}$")


def _issue(issues: list[dict[str, Any]], code: str, message: str, **context: Any) -> None:
    issues.append({"severity": "ERROR", "code": code, "message": message, "context": context})


def _strings(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item for item in value)


def _known_nodes(connection: sqlite3.Connection, node_ids: set[str]) -> set[str]:
    if not node_ids:
        return set()
    known: set[str] = set()
    ordered = sorted(node_ids)
    for start in range(0, len(ordered), 800):
        chunk = ordered[start : start + 800]
        placeholders = ",".join("?" for _ in chunk)
        known.update(
            row[0]
            for row in connection.execute(
                f"SELECT node_id FROM nodes WHERE node_id IN ({placeholders})", chunk
            )
        )
    return known


def _explicit_reference_pairs(connection: sqlite3.Connection) -> set[tuple[str, str]]:
    return {
        (row["source_node_id"], row["resolved_target_node_id"])
        for row in connection.execute(
            """SELECT source_node_id, resolved_target_node_id
               FROM cross_references
               WHERE resolution_status = 'RESOLVED' AND resolved_target_node_id IS NOT NULL"""
        )
    }


def validate_plan(
    plan: Any,
    connection: sqlite3.Connection,
    *,
    expected_language: str | None = None,
    expected_version: str | None = None,
    expected_digest: str | None = None,
    require_derived: bool = True,
    allowed_source_node_ids: set[str] | None = None,
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    checks: Counter[str] = Counter()
    if not isinstance(plan, dict):
        _issue(issues, "PLAN_TYPE", "plan must be a JSON object")
        return _report(issues, checks)

    checks["schema"] += 1
    if plan.get("schemaVersion") != PLAN_SCHEMA_VERSION:
        _issue(
            issues,
            "SCHEMA_VERSION",
            "unsupported or missing plan schema version",
            expected=PLAN_SCHEMA_VERSION,
            actual=plan.get("schemaVersion"),
        )

    specification = plan.get("specification")
    if not isinstance(specification, dict):
        _issue(issues, "SPECIFICATION", "specification metadata must be an object")
        specification = {}
    for field, expected in (
        ("language", expected_language),
        ("version", expected_version),
        ("indexSemanticDigest", expected_digest),
    ):
        checks["specification_identity"] += 1
        actual = specification.get(field)
        if not isinstance(actual, str) or not actual:
            _issue(issues, "SPECIFICATION_FIELD", f"specification.{field} must be a non-empty string")
        elif expected is not None and actual.casefold() != expected.casefold():
            _issue(
                issues,
                "SPECIFICATION_MISMATCH",
                f"specification.{field} does not match the selected index",
                field=field,
                expected=expected,
                actual=actual,
            )

    units = plan.get("units")
    if not isinstance(units, list):
        _issue(issues, "UNITS_TYPE", "units must be an array")
        units = []
    elif not units:
        _issue(issues, "UNITS_EMPTY", "plan must contain at least one formalization unit")
    dependencies = plan.get("dependencies")
    if not isinstance(dependencies, list):
        _issue(issues, "DEPENDENCIES_TYPE", "dependencies must be an array")
        dependencies = []

    unit_ids: list[str] = []
    unit_sources: dict[str, set[str]] = {}
    all_source_ids: set[str] = set()
    structurally_valid_units = True
    for ordinal, unit in enumerate(units):
        checks["units"] += 1
        if not isinstance(unit, dict):
            _issue(issues, "UNIT_TYPE", "unit must be an object", ordinal=ordinal)
            structurally_valid_units = False
            continue
        unit_id = unit.get("unitId")
        if not isinstance(unit_id, str) or not UNIT_ID_PATTERN.fullmatch(unit_id):
            _issue(issues, "UNIT_ID", "unitId has an invalid format", ordinal=ordinal, unitId=unit_id)
            structurally_valid_units = False
            continue
        unit_ids.append(unit_id)
        if not isinstance(unit.get("name"), str) or not unit["name"].strip():
            _issue(issues, "UNIT_NAME", "unit name must be non-empty", unitId=unit_id)
        if unit.get("kind") not in UNIT_KINDS:
            _issue(issues, "UNIT_KIND", "unit kind is invalid", unitId=unit_id, kind=unit.get("kind"))
        sources = unit.get("sourceNodeIds")
        if not _strings(sources) or not sources:
            _issue(issues, "UNIT_SOURCE_SUPPORT", "unit must have source node support", unitId=unit_id)
            sources = []
        if len(sources) != len(set(sources)):
            _issue(issues, "UNIT_SOURCE_DUPLICATE", "unit sourceNodeIds contain duplicates", unitId=unit_id)
        unit_sources[unit_id] = set(sources)
        all_source_ids.update(sources)
        instruction_names = unit.get("instructionNames", [])
        if not _strings(instruction_names):
            _issue(issues, "INSTRUCTION_NAMES", "instructionNames must be an array of non-empty strings", unitId=unit_id)
        elif len(instruction_names) != len(set(instruction_names)):
            _issue(issues, "INSTRUCTION_NAME_DUPLICATE", "instructionNames contain duplicates", unitId=unit_id)
        if unit.get("kind") in {"INSTRUCTION", "INSTRUCTION_FAMILY"} and not instruction_names:
            _issue(issues, "INSTRUCTION_MEMBERSHIP", "instruction units/families require instructionNames", unitId=unit_id)

    for duplicate, count in sorted(Counter(unit_ids).items()):
        if count > 1:
            _issue(issues, "DUPLICATE_UNIT", "unitId must be unique", unitId=duplicate, count=count)

    known_unit_ids = set(unit_ids)
    edge_keys: list[tuple[str, str, str]] = []
    structurally_valid_edges = True
    for ordinal, edge in enumerate(dependencies):
        checks["dependencies"] += 1
        if not isinstance(edge, dict):
            _issue(issues, "DEPENDENCY_TYPE", "dependency must be an object", ordinal=ordinal)
            structurally_valid_edges = False
            continue
        source = edge.get("fromUnitId")
        target = edge.get("toUnitId")
        dep_type = edge.get("type")
        if source not in known_unit_ids:
            _issue(issues, "DEPENDENCY_ENDPOINT", "fromUnitId does not exist", ordinal=ordinal, unitId=source)
            structurally_valid_edges = False
        if target not in known_unit_ids:
            _issue(issues, "DEPENDENCY_ENDPOINT", "toUnitId does not exist", ordinal=ordinal, unitId=target)
            structurally_valid_edges = False
        if source == target and source is not None:
            _issue(issues, "SELF_EDGE", "dependency self-edges are forbidden", ordinal=ordinal, unitId=source)
            structurally_valid_edges = False
        if dep_type not in DEPENDENCY_TYPES:
            _issue(issues, "DEPENDENCY_VOCABULARY", "dependency type is invalid", ordinal=ordinal, type=dep_type)
        if edge.get("origin") not in DEPENDENCY_ORIGINS:
            _issue(issues, "DEPENDENCY_ORIGIN", "origin must be EXPLICIT or INFERRED", ordinal=ordinal, origin=edge.get("origin"))
        if not isinstance(edge.get("reason"), str) or not edge["reason"].strip():
            _issue(issues, "DEPENDENCY_REASON", "dependency reason must be non-empty", ordinal=ordinal)
        sources = edge.get("sourceNodeIds")
        if not _strings(sources) or not sources:
            _issue(issues, "DEPENDENCY_SOURCE_SUPPORT", "dependency must have source node support", ordinal=ordinal)
            sources = []
        if len(sources) != len(set(sources)):
            _issue(issues, "DEPENDENCY_SOURCE_DUPLICATE", "dependency sourceNodeIds contain duplicates", ordinal=ordinal)
        all_source_ids.update(sources)
        if isinstance(source, str) and isinstance(target, str) and isinstance(dep_type, str):
            edge_keys.append((source, target, dep_type))

    for duplicate, count in sorted(Counter(edge_keys).items()):
        if count > 1:
            _issue(
                issues,
                "DUPLICATE_EDGE",
                "dependencies must be unique by endpoints and type",
                fromUnitId=duplicate[0],
                toUnitId=duplicate[1],
                type=duplicate[2],
                count=count,
            )

    malformed_nodes = {node_id for node_id in all_source_ids if not NODE_ID_PATTERN.fullmatch(node_id)}
    for node_id in sorted(malformed_nodes):
        _issue(
            issues,
            "SOURCE_NODE_FORMAT",
            "sourceNodeId must be a complete Phase-1 node ID",
            nodeId=node_id,
        )
    known_nodes = _known_nodes(connection, all_source_ids - malformed_nodes)
    checks["source_nodes"] += len(all_source_ids)
    for node_id in sorted(all_source_ids - malformed_nodes - known_nodes):
        _issue(issues, "SOURCE_NODE_MISSING", "sourceNodeId does not exist in the Phase-1 index", nodeId=node_id)
    if allowed_source_node_ids is not None:
        checks["observed_source_nodes"] += len(all_source_ids)
        for node_id in sorted(all_source_ids - allowed_source_node_ids):
            _issue(
                issues,
                "SOURCE_NODE_NOT_OBSERVED",
                "sourceNodeId was not returned by a specification query in this Planner session",
                nodeId=node_id,
            )

    explicit_pairs = _explicit_reference_pairs(connection)
    for ordinal, edge in enumerate(dependencies):
        if not isinstance(edge, dict) or edge.get("origin") != "EXPLICIT":
            continue
        source_unit = edge.get("fromUnitId")
        target_unit = edge.get("toUnitId")
        supporting = edge.get("sourceNodeIds") if _strings(edge.get("sourceNodeIds")) else []
        prerequisite_nodes = unit_sources.get(source_unit, set())
        dependent_nodes = unit_sources.get(target_unit, set())
        for node_id in supporting:
            checks["explicit_references"] += 1
            if node_id not in dependent_nodes:
                _issue(
                    issues,
                    "EXPLICIT_SUPPORT_MEMBERSHIP",
                    "an EXPLICIT edge support node must support the dependent unit",
                    ordinal=ordinal,
                    nodeId=node_id,
                    toUnitId=target_unit,
                )
            if not any((node_id, prerequisite) in explicit_pairs for prerequisite in prerequisite_nodes):
                _issue(
                    issues,
                    "EXPLICIT_REFERENCE_MISSING",
                    "no resolved indexed cross-reference connects the support node to the prerequisite unit",
                    ordinal=ordinal,
                    nodeId=node_id,
                    fromUnitId=source_unit,
                )

    if require_derived and structurally_valid_units and structurally_valid_edges and len(unit_ids) == len(set(unit_ids)):
        expected = derive_graph(units, dependencies)
        checks["sccs"] += len(expected["stronglyConnectedComponents"])
        checks["processing_layers"] += len(expected["processingLayers"])
        if plan.get("stronglyConnectedComponents") != expected["stronglyConnectedComponents"]:
            _issue(issues, "SCC_MISMATCH", "stronglyConnectedComponents do not match deterministic derivation")
        if plan.get("processingLayers") != expected["processingLayers"]:
            _issue(issues, "LAYER_MISMATCH", "processingLayers do not match deterministic SCC-DAG layering")

    return _report(issues, checks)


def _report(issues: list[dict[str, Any]], checks: Counter[str]) -> dict[str, Any]:
    return {
        "ok": not issues,
        "errors": len(issues),
        "checks": dict(sorted(checks.items())),
        "issues": issues,
    }


def normalize_candidate(candidate: Any) -> dict[str, Any]:
    """Return a deterministic representation without inventing planner content."""

    if not isinstance(candidate, dict):
        return candidate
    result = {
        "schemaVersion": candidate.get("schemaVersion"),
        "specification": candidate.get("specification"),
        "units": candidate.get("units"),
        "dependencies": candidate.get("dependencies"),
    }
    if isinstance(result["units"], list) and all(isinstance(item, dict) for item in result["units"]):
        normalized_units = []
        for unit in result["units"]:
            item = dict(unit)
            if isinstance(item.get("sourceNodeIds"), list) and all(
                isinstance(value, str) for value in item["sourceNodeIds"]
            ):
                item["sourceNodeIds"] = sorted(set(item["sourceNodeIds"]))
            if isinstance(item.get("instructionNames"), list) and all(
                isinstance(value, str) for value in item["instructionNames"]
            ):
                item["instructionNames"] = sorted(set(item["instructionNames"]))
            elif "instructionNames" not in item:
                item["instructionNames"] = []
            normalized_units.append(item)
        result["units"] = sorted(normalized_units, key=lambda item: str(item.get("unitId", "")))
    if isinstance(result["dependencies"], list) and all(isinstance(item, dict) for item in result["dependencies"]):
        normalized_edges = []
        for edge in result["dependencies"]:
            item = dict(edge)
            if isinstance(item.get("sourceNodeIds"), list) and all(
                isinstance(value, str) for value in item["sourceNodeIds"]
            ):
                item["sourceNodeIds"] = sorted(set(item["sourceNodeIds"]))
            normalized_edges.append(item)
        result["dependencies"] = sorted(
            normalized_edges,
            key=lambda item: (
                str(item.get("fromUnitId", "")),
                str(item.get("toUnitId", "")),
                str(item.get("type", "")),
                str(item.get("origin", "")),
            ),
        )
    return json.loads(json.dumps(result, ensure_ascii=False))
