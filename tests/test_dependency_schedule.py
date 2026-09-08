from copy import deepcopy
from itertools import permutations

import pytest

from spec2lean.pipeline.runner import _ordered_units
from spec2lean.planning.validation import (
    derive_execution_schedule, derive_processing_order, validate_execution_schedule,
)
from spec2lean.translation.groups import grouped_units


def scheduled_plan(groups, pairs):
    originals = [{"name": name, "unitIds": members, "reason": "Source grouping",
                  "origin": "EXPLICIT", "supportingNodeIds": ["node:" + name]}
                 for name, members in groups]
    ids = [unit for _, members in groups for unit in members]
    dependencies = [{"from": a, "to": b, "reason": "Required definition",
                     "origin": "EXPLICIT", "supportingNodeIds": ["node:edge"]}
                    for a, b in pairs]
    effective, schedule = derive_execution_schedule(ids, dependencies, originals)
    layers, cycles, blocked = derive_processing_order(ids, dependencies)
    return {"requestedUnits": [{"unitId": unit, "name": unit} for unit in ids],
            "plannedTranslationGroups": originals, "translationGroups": effective,
            "dependencies": dependencies, "externalPrerequisites": [{"prerequisiteId": "external"}],
            "executionSchedule": schedule, "processingLayers": layers,
            "cycles": cycles, "blockedUnitIds": blocked,
            "graphStatus": "CYCLIC" if cycles else "ACYCLIC"}


def test_cycle_merges_groups_without_losing_units_edges_or_downstream_order():
    groups = [("ZFirst", ["a"]), ("Second", ["b"]), ("ADownstream", ["c"]), ("Independent", ["d"])]
    pairs = [("a", "b"), ("b", "a"), ("b", "c"), ("external", "a")]
    plan = scheduled_plan(groups, pairs)
    before = deepcopy(plan)
    validate_execution_schedule(plan)
    assert plan == before
    assert plan["graphStatus"] == "CYCLIC"
    assert plan["cycles"] == [{"unitIds": ["a", "b"]}]
    assert plan["processingLayers"] == [{"layer": 0, "unitIds": ["a", "b", "d"]}, {"layer": 1, "unitIds": ["c"]}]
    assert [unit["unitId"] for unit in _ordered_units(plan)] == ["a", "b", "d", "c"]
    effective = grouped_units(plan)
    joint = next(name for name, units in effective.items() if len(units) == 2)
    assert list(effective).index(joint) < list(effective).index("ADownstream")
    schedule = plan["executionSchedule"]
    assert schedule["internalDependencyIndices"][joint] == [0, 1]
    assert schedule["dependencies"] == [{"from": joint, "to": "ADownstream", "dependencyIndices": [2]}]
    assert schedule["externalPrerequisiteDependencyIndices"] == [3]
    assert [(e["from"], e["to"]) for e in plan["dependencies"]] == pairs
    for reordered in permutations(groups):
        other = scheduled_plan(list(reordered), pairs)
        assert other["executionSchedule"] == schedule
        assert other["translationGroups"] == plan["translationGroups"]


def test_grouping_can_require_joint_translation_even_when_unit_graph_is_acyclic():
    plan = scheduled_plan([("Syntax", ["a", "d"]), ("Framing", ["b", "c"]), ("Tail", ["e"])],
                          [("a", "b"), ("c", "d"), ("d", "e")])
    validate_execution_schedule(plan)
    assert plan["graphStatus"] == "ACYCLIC"
    assert plan["cycles"] == []
    assert [group["unitIds"] for group in plan["translationGroups"]] == [["a", "b", "c", "d"], ["e"]]
    assert list(grouped_units(plan)) == ["FramingAndSyntax", "Tail"]


def test_multiple_components_and_long_or_colliding_group_names_are_safe():
    groups = [("A", ["a"]), ("B", ["b"]), ("AAndB", ["c"]),
              ("X" * 64, ["x"]), ("Y" * 64, ["y"])]
    plan = scheduled_plan(groups, [("a", "b"), ("b", "a"), ("x", "y"), ("y", "x"), ("b", "x")])
    validate_execution_schedule(plan)
    names = [g["name"] for g in plan["translationGroups"]]
    assert len(names) == len(set(names)) == 3
    assert all(len(name) <= 64 for name in names)
    assert "AAndB" in names


@pytest.mark.parametrize("mutation", ["drop_unit", "drop_edge_mapping", "reverse_groups", "hide_cycle", "unknown_edge", "change_group"])
def test_schedule_tampering_is_rejected(mutation):
    plan = scheduled_plan([("A", ["a"]), ("B", ["b"]), ("C", ["c"])],
                          [("a", "b"), ("b", "a"), ("b", "c")])
    if mutation == "drop_unit":
        plan["processingLayers"][0]["unitIds"].pop()
    elif mutation == "drop_edge_mapping":
        plan["executionSchedule"]["dependencies"].clear()
    elif mutation == "reverse_groups":
        plan["executionSchedule"]["groupLayers"].reverse()
    elif mutation == "hide_cycle":
        plan["graphStatus"] = "ACYCLIC"
    elif mutation == "unknown_edge":
        plan["dependencies"][0]["from"] = "invented"
    else:
        plan["translationGroups"][0]["unitIds"].append("c")
    with pytest.raises(ValueError, match="execution schedule"):
        _ordered_units(plan)


def test_legacy_cycles_and_duplicate_layers_cannot_bypass_the_guard():
    plan = {"requestedUnits": [{"unitId": "a"}], "graphStatus": "CYCLIC",
            "processingLayers": [{"layer": 0, "unitIds": ["a"]}]}
    with pytest.raises(RuntimeError, match="--from plan"):
        _ordered_units(plan)
    plan["graphStatus"] = "ACYCLIC"
    assert _ordered_units(plan) == [{"unitId": "a"}]
    plan["processingLayers"][0]["unitIds"].append("a")
    with pytest.raises(RuntimeError, match="exactly once"):
        _ordered_units(plan)
