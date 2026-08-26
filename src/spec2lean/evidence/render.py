from __future__ import annotations

from typing import Any

from .models import EVIDENCE_TIERS


def _provenance_line(item: dict[str, Any]) -> str:
    parts = [f"Section: {item['sectionNumber'] or 'n/a'} — {item['sectionTitle'] or 'n/a'}"]
    if item.get("htmlAnchor"):
        parts.append(f"HTML anchor: #{item['htmlAnchor']}")
    if item.get("pdfPage"):
        parts.append(f"PDF page: {item['pdfPage']}")
    parts.append(f"Document SHA-256: {item['documentSha256']}")
    return " | ".join(parts)


def render_markdown(bundle: dict[str, Any]) -> str:
    unit = bundle["unit"]
    lines = [
        f"# Evidence for {unit['name']}",
        "",
        f"Unit: `{unit['unitId']}`",
        "",
        f"Plan run: `{bundle['planRunId']}`",
        "",
    ]
    for tier in EVIDENCE_TIERS:
        lines.extend([f"## {tier.title()} evidence", ""])
        selected = [item for item in bundle["evidence"] if item["tier"] == tier]
        if not selected:
            lines.extend(["None.", ""])
            continue
        for item in selected:
            lines.extend([
                f"### [{item['evidenceId']}] {item['role']}",
                "",
                _provenance_line(item),
                "",
                "Source nodes: " + ", ".join(f"`{node}`" for node in item["sourceNodeIds"]),
                "",
                f"Relevance: {item['rationale']}",
                "",
                "Exact text:",
                "",
                "```text",
                item["exactText"],
                "```",
                "",
            ])
    return "\n".join(lines).rstrip() + "\n"
