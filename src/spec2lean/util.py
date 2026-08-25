from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_id(prefix: str, *parts: object, length: int = 24) -> str:
    material = "\0".join(str(part) for part in parts).encode("utf-8")
    return f"{prefix}:{hashlib.sha256(material).hexdigest()[:length]}"


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    value = value.replace("\uf0c1", " ")
    return re.sub(r"\s+", " ", value).strip()


def normalize_title(value: str | None) -> str | None:
    if value is None:
        return None
    return normalize_text(value).casefold()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def walk_nodes(root: Any) -> Iterable[tuple[Any, Any | None, int, int]]:
    """Yield node, parent, depth, sibling ordinal in deterministic preorder."""
    stack = [(root, None, 0, 0)]
    while stack:
        node, parent, depth, ordinal = stack.pop()
        yield node, parent, depth, ordinal
        for index in range(len(node.children) - 1, -1, -1):
            stack.append((node.children[index], node, depth + 1, index))


SECTION_NUMBER_RE = re.compile(r"^\s*(\d+(?:\.\d+)*\.?)(?:\s+|$)(.*)$", re.S)


def split_section_title(text: str) -> tuple[str | None, str]:
    clean = normalize_text(text)
    match = SECTION_NUMBER_RE.match(clean)
    if not match:
        return None, clean
    return match.group(1).rstrip("."), match.group(2).strip()
