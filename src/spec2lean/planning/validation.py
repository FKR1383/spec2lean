from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import re
from typing import Any, Iterable

from ..util import normalize_text, stable_id
from .models import ScopeMode
from .scope import Phase1Query, ResolvedScope


PLAN_SCHEMA_VERSION = 3
GROUP_NAME = re.compile(r"^[A-Z][A-Za-z0-9]{0,63}$")
SUBMISSION_FIELDS = {
    "requestedUnitIds",
    "translationGroups",
    "externalPrerequisites",
    "sharedPrerequisites",
    "dependencies",
}


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


def _reject_unexpected_fields(
    value: dict[str, Any], allowed: set[str], path: str, diagnostics: list[dict[str, str]]
) -> None:
    for key in sorted(set(value) - allowed):
        diagnostics.append(
            _diagnostic("UNEXPECTED_FIELD", f"unsupported planning field: {key}", f"{path}.{key}")
        )


def validate_submission(
    query: Phase1Query,
    scope: ResolvedScope,
    submission: Any,
) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    """Validate and normalize model-owned semantic planning content."""
    diagnostics: list[dict[str, str]] = []
    if not isinstance(submission, dict):
        return None, [_diagnostic("EXPECTED_OBJECT", "submission must be an object")]
    _reject_unexpected_fields(submission, SUBMISSION_FIELDS, "$", diagnostics)

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

    translation_groups = _validate_translation_groups(
        query, candidates, unit_ids, submission.get("translationGroups"), diagnostics
    )

    raw_shared = _as_list(
        submission.get("sharedPrerequisites"), "$.sharedPrerequisites", diagnostics
    )
    shared_prerequisites: list[dict[str, Any]] = []
    shared_keys: set[str] = set()
    shared_ids: set[str] = set()
    for index, value in enumerate(raw_shared):
        path = f"$.sharedPrerequisites[{index}]"
        if not isinstance(value, dict):
            diagnostics.append(
                _diagnostic("INVALID_SHARED_PREREQUISITE", "shared prerequisite must be an object", path)
            )
            continue
        _reject_unexpected_fields(
            value,
            {"key", "name", "kind", "reason", "sourceNodeIds", "requiredBy"},
            path,
            diagnostics,
        )
        key, name, kind, reason = (
            value.get("key"), value.get("name"), value.get("kind"), value.get("reason")
        )
        normalized_key = normalize_text(key).casefold() if isinstance(key, str) else ""
        normalized_name = normalize_text(name) if isinstance(name, str) else ""
        normalized_kind = normalize_text(kind) if isinstance(kind, str) else ""
        normalized_reason = normalize_text(reason) if isinstance(reason, str) else ""
        if not normalized_key:
            diagnostics.append(_diagnostic(
                "INVALID_SHARED_PREREQUISITE_KEY",
                "shared prerequisite key must be non-empty",
                f"{path}.key",
            ))
        elif normalized_key in shared_keys:
            diagnostics.append(_diagnostic(
                "DUPLICATE_SHARED_PREREQUISITE_KEY",
                f"duplicate shared prerequisite key: {key}",
                f"{path}.key",
            ))
        else:
            shared_keys.add(normalized_key)
        if not normalized_name:
            diagnostics.append(_diagnostic(
                "MISSING_SHARED_PREREQUISITE_NAME",
                "shared prerequisite name must be non-empty",
                f"{path}.name",
            ))
        if not normalized_kind:
            diagnostics.append(_diagnostic(
                "MISSING_SHARED_PREREQUISITE_KIND",
                "shared prerequisite kind must be a non-empty extensible concept label",
                f"{path}.kind",
            ))
        if not normalized_reason:
            diagnostics.append(_diagnostic(
                "MISSING_SHARED_PREREQUISITE_REASON",
                "shared prerequisite reason must be non-empty",
                f"{path}.reason",
            ))

        raw_sources = value.get("sourceNodeIds")
        if not isinstance(raw_sources, list) or not raw_sources:
            diagnostics.append(_diagnostic(
                "MISSING_SOURCE_SUPPORT",
                "shared prerequisite requires source node IDs",
                f"{path}.sourceNodeIds",
            ))
            raw_sources = []
        checked_sources = _validate_node_ids(
            query, raw_sources, f"{path}.sourceNodeIds", diagnostics
        )

        raw_required_by = value.get("requiredBy")
        required_by: list[str] = []
        if not isinstance(raw_required_by, list) or not raw_required_by:
            diagnostics.append(_diagnostic(
                "MISSING_SHARED_PREREQUISITE_CONSUMER",
                "shared prerequisite requiredBy must contain at least one requested unit",
                f"{path}.requiredBy",
            ))
            raw_required_by = []
        for unit_index, unit_id in enumerate(raw_required_by):
            unit_path = f"{path}.requiredBy[{unit_index}]"
            if not isinstance(unit_id, str) or unit_id not in selected:
                diagnostics.append(_diagnostic(
                    "UNKNOWN_SHARED_PREREQUISITE_CONSUMER",
                    f"shared prerequisite references an unselected unit: {unit_id!r}",
                    unit_path,
                ))
            elif unit_id in required_by:
                diagnostics.append(_diagnostic(
                    "DUPLICATE_SHARED_PREREQUISITE_CONSUMER",
                    f"shared prerequisite repeats a required unit: {unit_id}",
                    unit_path,
                ))
            else:
                required_by.append(unit_id)

        dependency_id = stable_id(
            "shared",
            scope.request.language.casefold(),
            scope.request.version,
            normalized_key,
            normalized_name.casefold(),
            normalized_kind.casefold(),
            *checked_sources,
        )
        if dependency_id in shared_ids:
            diagnostics.append(_diagnostic(
                "DUPLICATE_SHARED_PREREQUISITE_ID",
                f"shared prerequisites resolve to the same dependency ID: {dependency_id}",
                path,
            ))
        shared_ids.add(dependency_id)
        shared_prerequisites.append({
            "dependencyId": dependency_id,
            "name": normalized_name,
            "kind": normalized_kind,
            "reason": normalized_reason,
            "sourceNodeIds": checked_sources,
            "requiredBy": sorted(required_by),
        })

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
        _reject_unexpected_fields(
            value, {"key", "name", "reason", "sourceNodeIds"}, path, diagnostics
        )
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
        _reject_unexpected_fields(
            value,
            {"from", "to", "reason", "supportingNodeIds", "origin"},
            path,
            diagnostics,
        )
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
        "translationGroups": translation_groups,
        "externalPrerequisites": prerequisites,
        "sharedPrerequisites": sorted(
            shared_prerequisites, key=lambda item: item["dependencyId"]
        ),
        "dependencies": dependencies,
    }
    return normalized, []


def _validate_translation_groups(
    query: Phase1Query,
    candidates: dict[str, dict[str, Any]],
    selected_unit_ids: list[str],
    raw_value: Any,
    diagnostics: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """Validate a specification-supported, exact partition of selected units."""
    raw_groups = _as_list(raw_value, "$.translationGroups", diagnostics)
    selected = set(selected_unit_ids)
    seen_units: set[str] = set()
    seen_names: set[str] = set()
    groups: list[dict[str, Any]] = []

    for index, value in enumerate(raw_groups):
        path = f"$.translationGroups[{index}]"
        if not isinstance(value, dict):
            diagnostics.append(_diagnostic("INVALID_TRANSLATION_GROUP", "translation group must be an object", path))
            continue
        _reject_unexpected_fields(
            value,
            {"name", "unitIds", "reason", "supportingNodeIds", "origin"},
            path,
            diagnostics,
        )
        name = value.get("name")
        reason = value.get("reason")
        origin = value.get("origin")
        raw_unit_ids = value.get("unitIds")
        raw_support = value.get("supportingNodeIds")

        if not isinstance(name, str) or not GROUP_NAME.fullmatch(name):
            diagnostics.append(_diagnostic(
                "INVALID_TRANSLATION_GROUP_NAME",
                "translation group name must be an UpperCamelCase Lean identifier of at most 64 characters",
                f"{path}.name",
            ))
            normalized_name = ""
        else:
            normalized_name = name
            folded = name.casefold()
            if folded in seen_names:
                diagnostics.append(_diagnostic(
                    "DUPLICATE_TRANSLATION_GROUP_NAME",
                    f"duplicate translation group name: {name}",
                    f"{path}.name",
                ))
            seen_names.add(folded)

        if not isinstance(reason, str) or not reason.strip():
            diagnostics.append(_diagnostic(
                "MISSING_TRANSLATION_GROUP_REASON",
                "translation group requires a non-empty specification-based reason",
                f"{path}.reason",
            ))
        if origin not in {"EXPLICIT", "INFERRED"}:
            diagnostics.append(_diagnostic(
                "INVALID_TRANSLATION_GROUP_ORIGIN",
                "translation group origin must be EXPLICIT or INFERRED",
                f"{path}.origin",
            ))

        group_unit_ids: list[str] = []
        for unit_index, unit_id in enumerate(_as_list(raw_unit_ids, f"{path}.unitIds", diagnostics)):
            unit_path = f"{path}.unitIds[{unit_index}]"
            if not isinstance(unit_id, str) or unit_id not in selected:
                diagnostics.append(_diagnostic(
                    "UNKNOWN_TRANSLATION_GROUP_UNIT",
                    f"translation group references an unselected unit: {unit_id!r}",
                    unit_path,
                ))
            elif unit_id in group_unit_ids or unit_id in seen_units:
                diagnostics.append(_diagnostic(
                    "DUPLICATE_TRANSLATION_GROUP_UNIT",
                    f"unit appears more than once in translation groups: {unit_id}",
                    unit_path,
                ))
            else:
                group_unit_ids.append(unit_id)
                seen_units.add(unit_id)
        if not group_unit_ids:
            diagnostics.append(_diagnostic(
                "EMPTY_TRANSLATION_GROUP",
                "translation group must contain at least one selected unit",
                f"{path}.unitIds",
            ))

        support_values = _as_list(raw_support, f"{path}.supportingNodeIds", diagnostics)
        support = _validate_node_ids(
            query,
            support_values,
            f"{path}.supportingNodeIds",
            diagnostics,
        )
        if not support_values:
            diagnostics.append(_diagnostic(
                "MISSING_TRANSLATION_GROUP_SUPPORT",
                "translation group requires existing Phase-1 source-node support",
                f"{path}.supportingNodeIds",
            ))
        support_set = set(support)
        for unit_id in group_unit_ids:
            unit = candidates[unit_id]
            structural_context: set[str] = set()
            for source_node_id in unit.get("sourceNodeIds", []):
                structural_context.add(str(source_node_id))
                structural_context.update(
                    str(item["nodeId"]) for item in query.ancestors(str(source_node_id))
                )
            if support_set.isdisjoint(structural_context):
                diagnostics.append(_diagnostic(
                    "UNSUPPORTED_TRANSLATION_GROUP_MEMBER",
                    f"group support is not in the indexed source ancestry of unit {unit_id}",
                    f"{path}.supportingNodeIds",
                ))

        groups.append({
            "name": normalized_name,
            "unitIds": group_unit_ids,
            "reason": reason.strip() if isinstance(reason, str) else "",
            "supportingNodeIds": support,
            "origin": origin,
        })

    missing = sorted(selected - seen_units)
    if missing:
        diagnostics.append(_diagnostic(
            "UNGROUPED_REQUESTED_UNITS",
            f"every requested unit must belong to exactly one translation group; missing={missing}",
            "$.translationGroups",
        ))
    return sorted(groups, key=lambda item: item["name"])


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
        "schemaVersion": PLAN_SCHEMA_VERSION,
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
