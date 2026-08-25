from __future__ import annotations

import json
from collections import Counter
from typing import Any


def plan_statistics(plan: dict[str, Any]) -> dict[str, Any]:
    units = plan["units"]
    dependencies = plan["dependencies"]
    node_ids = {
        node_id
        for item in [*units, *dependencies]
        for node_id in item.get("sourceNodeIds", [])
    }
    kinds = Counter(unit["kind"] for unit in units)
    origins = Counter(edge["origin"] for edge in dependencies)
    cyclic = [item for item in plan["stronglyConnectedComponents"] if item["cyclic"]]
    return {
        "formalizationUnits": len(units),
        "instructionUnits": kinds["INSTRUCTION"],
        "instructionFamilyUnits": kinds["INSTRUCTION_FAMILY"],
        "dependencyEdges": len(dependencies),
        "explicitEdges": origins["EXPLICIT"],
        "inferredEdges": origins["INFERRED"],
        "stronglyConnectedComponents": len(plan["stronglyConnectedComponents"]),
        "cyclicStronglyConnectedComponents": len(cyclic),
        "processingLayers": len(plan["processingLayers"]),
        "sourceNodesReferenced": len(node_ids),
        "unitKinds": dict(sorted(kinds.items())),
    }


def render_markdown(plan: dict[str, Any]) -> str:
    stats = plan_statistics(plan)
    units = {unit["unitId"]: unit for unit in plan["units"]}
    lines = [
        f"# {plan['specification']['language'].upper()} {plan['specification']['version']} formalization plan",
        "",
        "Canonical data: `plan.json`.",
        "",
        "## Summary",
        "",
        f"- Formalization units: {stats['formalizationUnits']}",
        f"- Instruction units: {stats['instructionUnits']}",
        f"- Dependency edges: {stats['dependencyEdges']} ({stats['explicitEdges']} explicit, {stats['inferredEdges']} inferred)",
        f"- SCCs: {stats['stronglyConnectedComponents']} ({stats['cyclicStronglyConnectedComponents']} cyclic)",
        f"- Processing layers: {stats['processingLayers']}",
        f"- Source nodes referenced: {stats['sourceNodesReferenced']}",
        "",
        "## Processing layers",
        "",
    ]
    for layer in plan["processingLayers"]:
        lines.extend([f"### Layer {layer['layer']}", ""])
        for unit_id in layer["unitIds"]:
            unit = units[unit_id]
            lines.append(f"- `{unit_id}` — {unit['name']} ({unit['kind']})")
        lines.append("")
    lines.extend(["## Dependencies", ""])
    for edge in plan["dependencies"]:
        lines.append(
            f"- `{edge['fromUnitId']}` → `{edge['toUnitId']}` "
            f"({edge['type']}, {edge['origin']}): {edge['reason']}"
        )
    lines.append("")
    return "\n".join(lines)


def render_dot(plan: dict[str, Any]) -> str:
    lines = ["digraph specification_plan {", "  rankdir=LR;"]
    for unit in plan["units"]:
        label = f"{unit['name']}\\n{unit['kind']}".replace('"', '\\"')
        lines.append(f'  {json.dumps(unit["unitId"])} [label="{label}"];')
    for edge in plan["dependencies"]:
        label = f"{edge['type']} / {edge['origin']}".replace('"', '\\"')
        lines.append(
            f'  {json.dumps(edge["fromUnitId"])} -> {json.dumps(edge["toUnitId"])} [label="{label}"];'
        )
    lines.append("}")
    return "\n".join(lines) + "\n"
