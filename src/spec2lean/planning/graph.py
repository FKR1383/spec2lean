from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable


def _strongly_connected_components(
    unit_ids: Iterable[str], edges: Iterable[tuple[str, str]]
) -> list[list[str]]:
    adjacency: dict[str, set[str]] = {unit_id: set() for unit_id in unit_ids}
    for source, target in edges:
        if source in adjacency and target in adjacency:
            adjacency[source].add(target)

    index = 0
    indexes: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[list[str]] = []

    def visit(unit_id: str) -> None:
        nonlocal index
        indexes[unit_id] = index
        lowlinks[unit_id] = index
        index += 1
        stack.append(unit_id)
        on_stack.add(unit_id)

        for successor in sorted(adjacency[unit_id]):
            if successor not in indexes:
                visit(successor)
                lowlinks[unit_id] = min(lowlinks[unit_id], lowlinks[successor])
            elif successor in on_stack:
                lowlinks[unit_id] = min(lowlinks[unit_id], indexes[successor])

        if lowlinks[unit_id] == indexes[unit_id]:
            component: list[str] = []
            while True:
                member = stack.pop()
                on_stack.remove(member)
                component.append(member)
                if member == unit_id:
                    break
            components.append(sorted(component))

    for unit_id in sorted(adjacency):
        if unit_id not in indexes:
            visit(unit_id)
    return sorted(components, key=lambda item: tuple(item))


def derive_graph(units: list[dict[str, Any]], dependencies: list[dict[str, Any]]) -> dict[str, Any]:
    """Derive deterministic SCCs and topological layers over the SCC DAG.

    Dependency edges point from prerequisite to dependent, so layer zero contains
    components with no prerequisites.
    """

    unit_ids = sorted({unit["unitId"] for unit in units})
    pairs = [(edge["fromUnitId"], edge["toUnitId"]) for edge in dependencies]
    components = _strongly_connected_components(unit_ids, pairs)
    component_id_by_unit: dict[str, str] = {}
    rendered_components: list[dict[str, Any]] = []
    for ordinal, members in enumerate(components, start=1):
        component_id = f"scc:{ordinal:03d}"
        for member in members:
            component_id_by_unit[member] = component_id
        rendered_components.append(
            {"sccId": component_id, "unitIds": members, "cyclic": len(members) > 1}
        )

    successors: dict[str, set[str]] = defaultdict(set)
    indegree = {item["sccId"]: 0 for item in rendered_components}
    for source, target in pairs:
        source_component = component_id_by_unit.get(source)
        target_component = component_id_by_unit.get(target)
        if not source_component or not target_component or source_component == target_component:
            continue
        if target_component not in successors[source_component]:
            successors[source_component].add(target_component)
            indegree[target_component] += 1

    components_by_id = {item["sccId"]: item for item in rendered_components}
    remaining = set(indegree)
    layers: list[dict[str, Any]] = []
    while remaining:
        current = sorted(component_id for component_id in remaining if indegree[component_id] == 0)
        if not current:  # The condensation graph is acyclic by construction.
            raise RuntimeError("internal error: SCC condensation graph contains a cycle")
        layers.append(
            {
                "layer": len(layers),
                "sccIds": current,
                "unitIds": sorted(
                    unit_id
                    for component_id in current
                    for unit_id in components_by_id[component_id]["unitIds"]
                ),
            }
        )
        for component_id in current:
            remaining.remove(component_id)
            for successor in successors[component_id]:
                indegree[successor] -= 1

    return {
        "stronglyConnectedComponents": rendered_components,
        "processingLayers": layers,
    }
