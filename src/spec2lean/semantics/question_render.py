from __future__ import annotations

from typing import Any


def render_open_questions(artifact: dict[str, Any]) -> str:
    lines = [
        f"# Open questions for {artifact['unit']['name']}",
        "",
        f"Outcome: {artifact['outcome']}",
        "",
    ]
    for item in artifact.get("questions", []):
        lines.extend([
            f"## {item['questionId']}",
            "",
            f"Missing aspect: {item['aspect']}",
            "",
            f"Status: {item['status']}",
            "",
            f"Resolution source: {item['resolutionSource']}",
            "",
            f"Answer: {item.get('answer') or 'Unresolved'}",
            "",
            f"Rationale: {item['rationale']}",
            "",
            "References: " + (", ".join(item.get("references", [])) or "None"),
            "",
        ])
    return "\n".join(lines).rstrip() + "\n"
