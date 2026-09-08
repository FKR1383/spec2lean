from __future__ import annotations

import json
from typing import Any


def render_markdown(plan: dict[str, Any]) -> str:
    units = {item["unitId"]: item["name"] for item in plan["requestedUnits"]}
    prerequisites = {
        item["prerequisiteId"]: item["name"] for item in plan["externalPrerequisites"]
    }
    names = units | prerequisites
    lines = [
        f"# Plan {plan['planRunId']}",
        "",
        f"Specification: `{plan['language']} {plan['version']}`",
        "",
        f"Graph status: **{plan['graphStatus']}**",
        "",
        "## Requested units",
        "",
    ]
    for unit in plan["requestedUnits"]:
        sources = ", ".join(f"`{item}`" for item in unit["sourceNodeIds"])
        lines.append(f"- **{unit['name']}** (`{unit['unitId']}`): {sources}")
    lines.extend(["", "## Translation groups", ""])
    for group in plan["translationGroups"]:
        members = ", ".join(names[unit_id] for unit_id in group["unitIds"])
        support = ", ".join(f"`{node}`" for node in group["supportingNodeIds"])
        lines.append(
            f"- **{group['name']}** ({group['origin']}): {members}. "
            f"{group['reason']} ({support})"
        )
    if "executionSchedule" in plan:
        lines.extend(["", "## Translation schedule", "",
                      "The execution graph is acyclic. Original dependencies and cycles remain recorded below; "
                      "mutually dependent groups are translated together. Evidence, semantics, and checks remain per unit.", ""])
        for layer in plan["executionSchedule"]["groupLayers"]:
            lines.append(f"- Layer {layer['layer']}: " + ", ".join(layer["groupNames"]))
    lines.extend(["", "## External prerequisites", ""])
    if plan["externalPrerequisites"]:
        for item in plan["externalPrerequisites"]:
            sources = ", ".join(f"`{node}`" for node in item["sourceNodeIds"])
            lines.append(f"- **{item['name']}**: {item['reason']} ({sources})")
    else:
        lines.append("None.")
    lines.extend(["", "## Dependencies", ""])
    if plan["dependencies"]:
        for edge in plan["dependencies"]:
            support = ", ".join(f"`{node}`" for node in edge["supportingNodeIds"])
            lines.append(
                f"- **{names[edge['from']]} → {names[edge['to']]}** "
                f"({edge['origin']}): {edge['reason']} ({support})"
            )
    else:
        lines.append("None; the requested units are independent.")
    lines.extend(["", "## Processing layers", ""])
    for layer in plan["processingLayers"]:
        lines.append(
            f"- Layer {layer['layer']}: " + ", ".join(names[unit] for unit in layer["unitIds"])
        )
    if plan["cycles"]:
        lines.extend(["", "## Cycles", ""])
        for cycle in plan["cycles"]:
            lines.append("- " + " ↔ ".join(names[unit] for unit in cycle["unitIds"]))
        if plan.get("blockedUnitIds"):
            lines.extend(["", "Units blocked downstream of cycles: " + ", ".join(
                names[unit] for unit in plan["blockedUnitIds"]
            )])
    return "\n".join(lines) + "\n"


def _dot_quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def render_dot(plan: dict[str, Any]) -> str:
    lines = ["digraph plan {", "  rankdir=LR;"]
    for unit in plan["requestedUnits"]:
        lines.append(
            f"  {_dot_quote(unit['unitId'])} [label={_dot_quote(unit['name'])}, shape=box];"
        )
    for item in plan["externalPrerequisites"]:
        lines.append(
            f"  {_dot_quote(item['prerequisiteId'])} "
            f"[label={_dot_quote(item['name'])}, shape=ellipse, style=dashed];"
        )
    for edge in plan["dependencies"]:
        label = f"{edge['origin']}: {edge['reason']}"
        lines.append(
            f"  {_dot_quote(edge['from'])} -> {_dot_quote(edge['to'])} "
            f"[label={_dot_quote(label)}];"
        )
    lines.append("}")
    return "\n".join(lines) + "\n"
