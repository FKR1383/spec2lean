from __future__ import annotations

from typing import Any


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        f"# Phase 6 Check: {result['unit']['name']}",
        "",
        f"- Overall: `{result['status']}`",
        f"- Build: `{result['build']['status']}`",
        f"- Coverage: `{result['coverage']['status']}`",
        f"- Traceability: `{result['traceability']['status']}`",
        f"- Routing: `{', '.join(result['routing']['next'])}`",
        "",
        "## Build Test",
        "",
        f"Lean: `{result['build']['leanVersion'] or 'unavailable'}`  ",
        f"Exit code: `{result['build']['exitCode']}`  ",
        f"Duration: `{result['build']['durationMs']} ms`",
        "",
    ]
    diagnostics = result["build"]["diagnostics"]
    if diagnostics:
        lines.extend(f"- `{item['severity']}` {item['message']}" for item in diagnostics)
    else:
        lines.append("No compiler diagnostics.")

    lines.extend(["", "## Coverage Test", ""])
    for label in ("covered", "uncovered"):
        lines.append(f"### {label.title()}")
        lines.append("")
        items = result["coverage"][label]
        if items:
            lines.extend(
                f"- `{item['itemType']}` `{item['itemId']}`"
                for item in items
            )
        else:
            lines.append("None.")
        lines.append("")

    lines.extend(["## Traceability Test", ""])
    if result["traceability"]["validMappings"]:
        lines.append("### Valid mappings")
        lines.append("")
        lines.extend(
            f"- `{item['declaration']}` → {', '.join(f'`{claim}`' for claim in item['semanticClaimIds'])}"
            for item in result["traceability"]["validMappings"]
        )
        lines.append("")
    if result["traceability"]["brokenMappings"]:
        lines.append("### Broken mappings")
        lines.append("")
        lines.extend(
            f"- `{item['code']}` {item['message']}"
            for item in result["traceability"]["brokenMappings"]
        )
    else:
        lines.append("No broken mappings.")
    return "\n".join(lines).rstrip() + "\n"
