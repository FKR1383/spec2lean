from __future__ import annotations

from typing import Any

from .models import CLAIM_KINDS


def _evidence(item: dict[str, Any]) -> str:
    values = item.get("evidenceIds", [])
    return ", ".join(values) if values else "None (modeling dependency/assumption)"


def render_markdown(artifact: dict[str, Any]) -> str:
    unit = artifact["unit"]
    lines = [f"# Unit: {unit['name']}", "", f"Outcome: {artifact['outcome']}", ""]
    if artifact["outcome"] == "INSUFFICIENT_EVIDENCE":
        failure = artifact["failure"]
        lines.extend(["## INSUFFICIENT EVIDENCE", "", failure["explanation"], "", "Missing semantic aspects:", ""])
        lines.extend(f"- {item}" for item in failure["missingAspects"])
        lines.extend(["", f"Evidence inspected: {_evidence(failure)}", ""])
        return "\n".join(lines)
    semantics = artifact["semantics"]
    operation = semantics.get("operation")
    lines.extend(["## CORE OPERATION", ""])
    if operation:
        lines.extend([operation["description"], "", f"Inputs: {', '.join(operation['inputs'])}", f"Result: {operation['result']}", f"Evidence: {_evidence(operation)}", ""])
        if operation.get("branches"):
            lines.extend(["### Branches", ""])
            for item in operation["branches"]:
                lines.extend([f"- If {item['condition']}: {item['behavior']}", f"  Evidence: {_evidence(item)}"])
            lines.append("")
    else:
        lines.extend(["None", ""])
    lines.extend(["## INPUTS / OUTPUT", ""])
    for item in semantics.get("inputs", []):
        constraints = "; ".join(item.get("constraints", [])) or "None stated"
        lines.extend([f"- {item['name']} ({item['role']}): {item['description']}", f"  Constraints: {constraints}", f"  Evidence: {_evidence(item)}"])
    result = semantics.get("result")
    if result:
        lines.extend([f"- Result {result['name']}: {result['description']}", f"  Constraints: {'; '.join(result.get('constraints', [])) or 'None stated'}", f"  Evidence: {_evidence(result)}"])
    lines.append("")
    by_kind = {kind: [item for item in semantics["claims"] if item["kind"] == kind] for kind in CLAIM_KINDS}
    headings = {
        "SOURCE_FACT": "SOURCE FACTS", "DERIVED_INTERPRETATION": "DERIVED INTERPRETATIONS",
        "DESIGN_DEPENDENCY": "DESIGN DEPENDENCIES", "ASSUMPTION": "ASSUMPTIONS",
    }
    for kind in CLAIM_KINDS:
        lines.extend([f"## {headings[kind]}", ""])
        if not by_kind[kind]:
            lines.extend(["None", ""])
        for item in by_kind[kind]:
            lines.extend([f"- [{item['claimId']}] {item['statement']}", f"  Evidence: {_evidence(item)}", ""])
    for field, heading, format_item in (
        ("stateEffects", "STATE EFFECTS", lambda item: f"{item['target']}: {item['effect']}"),
        ("edgeCases", "EDGE CASES", lambda item: f"If {item['condition']}: {item['behavior']}"),
        ("restrictions", "VERSION / TARGET / OTHER RESTRICTIONS", lambda item: f"{item['kind']}: {item['description']}"),
        ("dependencies", "SHARED SEMANTIC DEPENDENCIES", lambda item: f"{item['concept']}: {item['description']}"),
    ):
        lines.extend([f"## {heading}", ""])
        items = semantics.get(field, [])
        if not items:
            lines.extend(["None", ""])
        for item in items:
            lines.extend([f"- {format_item(item)}", f"  Evidence: {_evidence(item)}", ""])
    if semantics.get("predication"):
        item = semantics["predication"]
        lines.extend(["## PREDICATION", "", f"Guard: {item['guard']}", f"When true: {item['whenTrue']}", f"When false: {item['whenFalse']}", f"Evidence: {_evidence(item)}", ""])
    return "\n".join(lines)
