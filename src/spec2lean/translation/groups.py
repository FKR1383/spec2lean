from __future__ import annotations

from collections import defaultdict
from typing import Any


PTX_GROUPS: dict[str, frozenset[str]] = {
    "Arithmetic": frozenset({
        "abs", "add", "addc", "div", "dp2a", "dp4a", "fma", "mad", "mad24",
        "madc", "max", "min", "mma", "mul", "mul24", "neg", "rcp", "rem",
        "rsqrt", "sad", "sqrt", "sub", "subc", "wgmma", "wmma",
    }),
    "BitManip": frozenset({
        "bfe", "bfi", "bfind", "bmsk", "brev", "clz", "fns", "popc", "prmt",
        "shf", "shl", "shr",
    }),
    "Communication": frozenset({
        "activemask", "bar", "barrier", "clusterlaunchcontrol", "elect", "fence",
        "griddepcontrol", "membar", "redux", "shfl", "vote",
    }),
    "Comparison": frozenset({"isspacep", "match", "selp", "set", "setp", "slct", "testp"}),
    "Conversion": frozenset({"cvt", "cvta"}),
    "Logic": frozenset({"and", "cnot", "lop3", "not", "or", "xor"}),
    "Memory": frozenset({
        "applypriority", "atom", "cp", "createpolicy", "discard", "ld", "ldmatrix",
        "ldu", "prefetch", "prefetchu", "red", "st", "stmatrix", "suld", "sured",
        "sust", "tex", "tld4",
    }),
    "Move": frozenset({"mov", "movmatrix", "pack", "unpack"}),
}


def instruction_group(language: str, instruction: str) -> str:
    """Return the deterministic Phase-5 output group for an instruction spelling."""
    if language.casefold() != "ptx":
        return "Other"
    mnemonic = instruction.casefold().split(".", 1)[0]
    matches = [group for group, mnemonics in PTX_GROUPS.items() if mnemonic in mnemonics]
    if not matches:
        return "Other"
    if len(matches) != 1:
        raise ValueError(f"PTX instruction has no unique translation group: {instruction}")
    return matches[0]


def grouped_units(plan: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for unit in plan.get("requestedUnits", []):
        groups[instruction_group(str(plan["language"]), str(unit["name"]))].append(dict(unit))
    return {group: groups[group] for group in sorted(groups)}


def group_for_unit(plan: dict[str, Any], unit_id: str) -> str:
    matches = [
        group
        for group, units in grouped_units(plan).items()
        if any(unit.get("unitId") == unit_id for unit in units)
    ]
    if len(matches) != 1:
        raise KeyError(f"unit has no unique translation group: {unit_id}")
    return matches[0]
