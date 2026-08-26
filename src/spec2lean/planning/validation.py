from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable

from ..util import stable_id
from .models import ScopeMode
from .scope import Phase1Query, ResolvedScope


@dataclass(slots=True)
class PlanValidationError(ValueError):
    diagnostics: list[dict[str, str]]

    def __str__(self) -> str:
        return "; ".join(item["message"] for item in self.diagnostics)


def _diagnostic(code: str, message: str, path: str = "$") -> dict[str, str]:
    return {"code": code, "message": message, "path": path}


def _as_list(value: Any, path: str, diagnostics: list[dict[str, str]]) -> list[Any]:
    if not isinstance(value, list):
        diagnostics.append(_diagnostic("EXPECTED_ARRAY", f"{path} must be an array", path))
        return []
    return value


def validate_submission(
    query: Phase1Query,
    scope: ResolvedScope,
    submission: Any,
) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    """Validate and normalize model-owned semantic planning content."""
    diagnostics: list[dict[str, str]] = []
    if not isinstance(submission, dict):
        return None, [_diagnostic("EXPECTED_OBJECT", "submission must be an object")]

    candidates = scope.candidate_by_id
    raw_unit_ids = _as_list(submission.get("requestedUnitIds"), "$.requestedUnitIds", diagnostics)
    unit_ids: list[str] = []
    for index, value in enumerate(raw_unit_ids):
        path = f"$.requestedUnitIds[{index}]"
        if not isinstance(value, str):
            diagnostics.append(_diagnostic("INVALID_UNIT_ID", "requested unit ID must be a string", path))
        elif value not in candidates:
            diagnostics.append(_diagnostic("OUT_OF_SCOPE_UNIT", f"unit is not in resolved scope: {value}", path))
        elif value in unit_ids:
            diagnostics.append(_diagnostic("DUPLICATE_UNIT", f"requested unit is duplicated: {value}", path))
        else:
            unit_ids.append(value)

    required = set(scope.exact_unit_ids)
    selected = set(unit_ids)
    if required and selected != required:
        missing = sorted(required - selected)
        extra = sorted(selected - required)
        diagnostics.append(
            _diagnostic(
                "SCOPE_MISMATCH",
                f"exact scope must be preserved; missing={missing}, extra={extra}",
                "$.requestedUnitIds",
            )
        )
    if scope.request.mode == ScopeMode.INSTRUCTION_FAMILY and not selected:
        diagnostics.append(
            _diagnostic("EMPTY_FAMILY_SELECTION", "family planning must select at least one candidate unit", "$.requestedUnitIds")
        )

    raw_prerequisites = _as_list(
        submission.get("externalPrerequisites", []), "$.externalPrerequisites", diagnostics
    )
    prerequisites: list[dict[str, Any]] = []
    prerequisite_keys: dict[str, str] = {}
    for index, value in enumerate(raw_prerequisites):
        path = f"$.externalPrerequisites[{index}]"
        if not isinstance(value, dict):
            diagnostics.append(_diagnostic("INVALID_PREREQUISITE", "prerequisite must be an object", path))
            continue
        key, name, reason = value.get("key"), value.get("name"), value.get("reason")
        source_ids = value.get("sourceNodeIds")
        if not isinstance(key, str) or not key.strip():
            diagnostics.append(_diagnostic("INVALID_PREREQUISITE_KEY", "prerequisite key must be non-empty", f"{path}.key"))
            continue
        if key in prerequisite_keys:
            diagnostics.append(_diagnostic("DUPLICATE_PREREQUISITE_KEY", f"duplicate prerequisite key: {key}", f"{path}.key"))
            continue
        if key in candidates:
            diagnostics.append(_diagnostic("PREREQUISITE_KEY_COLLISION", f"prerequisite key collides with a unit ID: {key}", f"{path}.key"))
            continue
        if not isinstance(name, str) or not name.strip():
            diagnostics.append(_diagnostic("MISSING_PREREQUISITE_NAME", "prerequisite name must be non-empty", f"{path}.name"))
        if not isinstance(reason, str) or not reason.strip():
            diagnostics.append(_diagnostic("MISSING_PREREQUISITE_REASON", "prerequisite reason must be non-empty", f"{path}.reason"))
        if not isinstance(source_ids, list) or not source_ids:
            diagnostics.append(_diagnostic("MISSING_SOURCE_SUPPORT", "prerequisite requires source node IDs", f"{path}.sourceNodeIds"))
            source_ids = []
        checked_sources = _validate_node_ids(query, source_ids, f"{path}.sourceNodeIds", diagnostics)
        prerequisite_id = stable_id("prerequisite", key, name or "", *checked_sources)
        prerequisite_keys[key] = prerequisite_id
        prerequisites.append(
            {
                "prerequisiteId": prerequisite_id,
                "name": name.strip() if isinstance(name, str) else "",
                "sourceNodeIds": checked_sources,
                "reason": reason.strip() if isinstance(reason, str) else "",
            }
        )

    endpoints = selected | set(prerequisite_keys)
    raw_dependencies = _as_list(submission.get("dependencies", []), "$.dependencies", diagnostics)
    dependencies: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str]] = set()
    for index, value in enumerate(raw_dependencies):
        path = f"$.dependencies[{index}]"
        if not isinstance(value, dict):
            diagnostics.append(_diagnostic("INVALID_DEPENDENCY", "dependency must be an object", path))
            continue
        source, target = value.get("from"), value.get("to")
        reason, origin = value.get("reason"), value.get("origin")
        support = value.get("supportingNodeIds")
        if not isinstance(source, str) or source not in endpoints:
            diagnostics.append(_diagnostic("UNKNOWN_EDGE_ENDPOINT", f"unknown dependency source: {source!r}", f"{path}.from"))
            continue
        if not isinstance(target, str) or target not in endpoints:
            diagnostics.append(_diagnostic("UNKNOWN_EDGE_ENDPOINT", f"unknown dependency target: {target!r}", f"{path}.to"))
            continue
        if target not in selected:
            diagnostics.append(
                _diagnostic(
                    "EXTERNAL_PREREQUISITE_TARGET",
                    "an external prerequisite cannot be the dependent endpoint",
                    f"{path}.to",
                )
            )
            continue
        if source == target:
            diagnostics.append(_diagnostic("SELF_EDGE", f"dependency cannot point to itself: {source}", path))
            continue
        pair = (source, target)
        if pair in seen_edges:
            diagnostics.append(_diagnostic("DUPLICATE_EDGE", f"duplicate dependency: {source} -> {target}", path))
            continue
        seen_edges.add(pair)
        if not isinstance(reason, str) or not reason.strip():
            diagnostics.append(_diagnostic("MISSING_EDGE_REASON", "dependency reason must be non-empty", f"{path}.reason"))
        if origin not in {"EXPLICIT", "INFERRED"}:
            diagnostics.append(_diagnostic("INVALID_EDGE_ORIGIN", "origin must be EXPLICIT or INFERRED", f"{path}.origin"))
        if not isinstance(support, list) or not support:
            diagnostics.append(_diagnostic("MISSING_SOURCE_SUPPORT", "dependency requires supporting source node IDs", f"{path}.supportingNodeIds"))
            support = []
        checked_support = _validate_node_ids(query, support, f"{path}.supportingNodeIds", diagnostics)
        dependencies.append(
            {
                "from": prerequisite_keys.get(source, source),
                "to": prerequisite_keys.get(target, target),
                "reason": reason.strip() if isinstance(reason, str) else "",
                "supportingNodeIds": checked_support,
                "origin": origin,
            }
        )

    if diagnostics:
        return None, diagnostics
    normalized = {
        "requestedUnits": [dict(candidates[unit_id]) for unit_id in unit_ids],
        "externalPrerequisites": prerequisites,
        "dependencies": dependencies,
    }
    return normalized, []


def _validate_node_ids(
    query: Phase1Query,
    values: Iterable[Any],
    path: str,
    diagnostics: list[dict[str, str]],
) -> list[str]:
    result: list[str] = []
    for index, value in enumerate(values):
        item_path = f"{path}[{index}]"
        if not isinstance(value, str) or not value.startswith("node:"):
            diagnostics.append(_diagnostic("INVALID_SOURCE_NODE", f"invalid source node ID: {value!r}", item_path))
        elif not query.node_exists(value):
            diagnostics.append(_diagnostic("INVENTED_SOURCE_NODE", f"source node does not exist: {value}", item_path))
        elif value in result:
            diagnostics.append(_diagnostic("DUPLICATE_SOURCE_NODE", f"duplicate source node: {value}", item_path))
        else:
            result.append(value)
    return sorted(result)


def _strongly_connected_components(vertices: list[str], edges: list[tuple[str, str]]) -> list[list[str]]:
    outgoing: dict[str, list[str]] = defaultdict(list)
    for source, target in edges:
        outgoing[source].append(target)
    index = 0
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    result: list[list[str]] = []

    def visit(vertex: str) -> None:
        nonlocal index
        indices[vertex] = lowlinks[vertex] = index
        index += 1
        stack.append(vertex)
        on_stack.add(vertex)
        for target in sorted(outgoing[vertex]):
            if target not in indices:
                visit(target)
                lowlinks[vertex] = min(lowlinks[vertex], lowlinks[target])
            elif target in on_stack:
                lowlinks[vertex] = min(lowlinks[vertex], indices[target])
        if lowlinks[vertex] == indices[vertex]:
            component: list[str] = []
            while True:
                item = stack.pop()
                on_stack.remove(item)
                component.append(item)
                if item == vertex:
                    break
            result.append(sorted(component))

    for vertex in sorted(vertices):
        if vertex not in indices:
            visit(vertex)
    return sorted(result, key=lambda component: component[0])


def derive_processing_order(
    requested_unit_ids: list[str], dependencies: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    requested = set(requested_unit_ids)
    edges = [
        (edge["from"], edge["to"])
        for edge in dependencies
        if edge["from"] in requested and edge["to"] in requested
    ]
    components = _strongly_connected_components(requested_unit_ids, edges)
    cyclic = {item for component in components if len(component) > 1 for item in component}
    cycles = [
        {"unitIds": component}
        for component in components
        if len(component) > 1
    ]
    requested_outgoing: dict[str, set[str]] = defaultdict(set)
    for source, target in edges:
        requested_outgoing[source].add(target)
    blocked = set(cyclic)
    frontier = list(cyclic)
    while frontier:
        source = frontier.pop()
        for target in requested_outgoing[source]:
            if target not in blocked:
                blocked.add(target)
                frontier.append(target)
    # Self edges are rejected earlier, so every remaining singleton is acyclic.
    remaining = requested - blocked
    incoming = {unit_id: set() for unit_id in remaining}
    outgoing: dict[str, set[str]] = defaultdict(set)
    for source, target in edges:
        if source in remaining and target in remaining:
            incoming[target].add(source)
            outgoing[source].add(target)
    layers: list[dict[str, Any]] = []
    layer_index = 0
    while remaining:
        ready = sorted(unit_id for unit_id in remaining if not incoming[unit_id])
        if not ready:  # Defensive: SCC detection should have removed every cycle.
            break
        layers.append({"layer": layer_index, "unitIds": ready})
        layer_index += 1
        for source in ready:
            remaining.remove(source)
            for target in outgoing[source]:
                incoming[target].discard(source)
    return layers, cycles, sorted(blocked - cyclic)


def build_validated_plan(
    query: Phase1Query,
    scope: ResolvedScope,
    submission: Any,
    *,
    language: str,
    version: str,
    plan_run_id: str,
    source_database_digest: str,
) -> dict[str, Any]:
    normalized, diagnostics = validate_submission(query, scope, submission)
    if diagnostics or normalized is None:
        raise PlanValidationError(diagnostics)
    unit_ids = [item["unitId"] for item in normalized["requestedUnits"]]
    layers, cycles, blocked = derive_processing_order(unit_ids, normalized["dependencies"])
    return {
        "schemaVersion": 1,
        "language": language,
        "version": version,
        "planRunId": plan_run_id,
        "sourceDatabaseDigest": source_database_digest,
        "request": scope.request.to_dict(),
        **normalized,
        "processingLayers": layers,
        "cycles": cycles,
        "blockedUnitIds": blocked,
        "graphStatus": "CYCLIC" if cycles else "ACYCLIC",
    }
