from __future__ import annotations

import re

from .model import Reference
from .util import normalize_text


EXPLICIT_REFERENCE_RE = re.compile(
    r"\b(?P<kind>Section|Chapter|Table|Figure|Appendix)\s+"
    r"(?P<target>[A-Z]?(?:\d+(?:\.\d+)*|\.[A-Za-z0-9_.:-]+))",
    re.IGNORECASE,
)


def text_references(text: str) -> list[Reference]:
    found: list[Reference] = []
    seen: set[tuple[str, str]] = set()
    for match in EXPLICIT_REFERENCE_RE.finditer(normalize_text(text)):
        raw = match.group(0)
        key = (match.group("kind").casefold(), match.group("target").casefold())
        if key in seen:
            continue
        seen.add(key)
        found.append(
            Reference(
                raw_text=raw,
                target_text=match.group("target").rstrip("."),
                kind=match.group("kind").upper(),
            )
        )
    return found

