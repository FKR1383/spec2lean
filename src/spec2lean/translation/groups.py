from __future__ import annotations

from typing import Any

from ..planning.validation import validate_execution_schedule


def grouped_units(plan: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Return Phase-2's validated, specification-derived unit partition."""
    units = {str(unit["unitId"]): dict(unit) for unit in plan.get("requestedUnits", [])}
    raw_groups = plan.get("translationGroups")
    if not isinstance(raw_groups, list) or not raw_groups:
        raise ValueError(
            "Phase-2 plan has no specification-derived translationGroups; rerun from the plan phase"
        )
    groups: dict[str, list[dict[str, Any]]] = {}
    seen: set[str] = set()
    for item in raw_groups:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise ValueError("Phase-2 plan contains a malformed translation group")
        name = str(item["name"])
        if name in groups:
            raise ValueError(f"Phase-2 plan contains a duplicate translation group: {name}")
        member_ids = item.get("unitIds")
        if not isinstance(member_ids, list) or not member_ids:
            raise ValueError(f"Phase-2 translation group is empty: {name}")
        members: list[dict[str, Any]] = []
        for unit_id in member_ids:
            if unit_id not in units:
                raise ValueError(f"Phase-2 translation group references an unknown unit: {unit_id}")
            if unit_id in seen:
                raise ValueError(f"Phase-2 unit appears in more than one translation group: {unit_id}")
            seen.add(unit_id)
            members.append(units[unit_id])
        groups[name] = members
    if seen != set(units):
        missing = sorted(set(units) - seen)
        raise ValueError(f"Phase-2 translation groups do not cover every requested unit: {missing}")
    if "executionSchedule" in plan:
        validate_execution_schedule(plan)
        order = [name for layer in plan["executionSchedule"]["groupLayers"] for name in layer["groupNames"]]
    else:
        order = sorted(groups)
    return {name: groups[name] for name in order}


def group_for_unit(plan: dict[str, Any], unit_id: str) -> str:
    matches = [
        group
        for group, units in grouped_units(plan).items()
        if any(unit.get("unitId") == unit_id for unit in units)
    ]
    if len(matches) != 1:
        raise KeyError(f"unit has no unique translation group: {unit_id}")
    return matches[0]
