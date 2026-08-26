from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

from .constants import INDEX_SCHEMA_VERSION, PAGE_TEXT_FORMAT_VERSION, PARSER_VERSION
from .model import ParsedDocument


def page_text_path(index_directory: str | Path, source_path: str | Path, source_sha256: str) -> Path:
    """Return the stable generated path for one PDF page-text representation."""
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(source_path).stem).strip(".-") or "specification"
    return Path(index_directory).resolve() / "text" / f"{stem}.{source_sha256[:12]}.pages.txt"


def render_pdf_page_text(
    *,
    source_filename: str,
    source_sha256: str,
    pages: Iterable[Mapping[str, Any]],
    parser_version: str = PARSER_VERSION,
    schema_version: int = INDEX_SCHEMA_VERSION,
) -> bytes:
    """Serialize exact stored page text with deterministic, LLM-readable page boundaries."""
    ordered = sorted(pages, key=lambda page: int(page["page_number"]))
    total = len(ordered)
    parts = [
        "# Spec2Lean deterministic PDF page text\n",
        f"format_version: {PAGE_TEXT_FORMAT_VERSION}\n",
        f"source_filename: {source_filename}\n",
        f"source_sha256: {source_sha256}\n",
        f"parser_version: {parser_version}\n",
        f"index_schema_version: {schema_version}\n",
        f"page_count: {total}\n",
        "\n",
    ]
    for expected_number, page in enumerate(ordered, start=1):
        number = int(page["page_number"])
        if number != expected_number:
            raise ValueError(f"PDF page sequence is not contiguous at page {number}")
        parts.append(f"===== PDF PAGE {number} OF {total} =====\n")
        raw_text = str(page["raw_text"])
        parts.append(raw_text)
        if raw_text and not raw_text.endswith("\n"):
            parts.append("\n")
        parts.append(f"===== END PDF PAGE {number} =====\n\n")
    return "".join(parts).encode("utf-8")


def write_pdf_page_text_artifacts(
    index_directory: str | Path,
    documents: Iterable[ParsedDocument],
) -> list[dict[str, Any]]:
    """Write page text as part of the Parse + Index build, atomically per PDF."""
    resolved_index_directory = Path(index_directory).resolve()
    output_directory = resolved_index_directory / "text"
    pdf_documents = sorted(
        (document for document in documents if document.source_type == "pdf"),
        key=lambda document: (document.path, document.sha256),
    )
    expected_paths: set[Path] = set()
    artifacts: list[dict[str, Any]] = []
    if pdf_documents:
        output_directory.mkdir(parents=True, exist_ok=True)
    for document in pdf_documents:
        target = page_text_path(index_directory, document.path, document.sha256)
        expected_paths.add(target)
        data = render_pdf_page_text(
            source_filename=Path(document.path).name,
            source_sha256=document.sha256,
            pages=document.pages,
        )
        temporary = target.with_name(target.name + ".building")
        temporary.write_bytes(data)
        os.replace(temporary, target)
        artifacts.append(
            {
                "source_sha256": document.sha256,
                "path": str(target),
                "relative_path": str(target.relative_to(resolved_index_directory)),
                "sha256": hashlib.sha256(data).hexdigest(),
                "byte_size": len(data),
                "page_count": len(document.pages),
                "format_version": PAGE_TEXT_FORMAT_VERSION,
            }
        )

    # This directory contains generated outputs only. Remove sidecars for PDFs
    # no longer present in the rebuilt database so stale text cannot be consumed.
    if output_directory.is_dir():
        for existing in output_directory.glob("*.pages.txt"):
            if existing.resolve() not in expected_paths:
                existing.unlink()
    return artifacts
