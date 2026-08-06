#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
RAW_DIR="$SOURCE_DIR/raw"

PDF_URL="https://docs.nvidia.com/cuda/pdf/ptx_isa_9.3.pdf"
HTML_URL="https://docs.nvidia.com/cuda/parallel-thread-execution/index.html"

PDF_PATH="$RAW_DIR/ptx_isa_9.3.pdf"
HTML_PATH="$RAW_DIR/ptx_isa_9.3.html"

mkdir -p "$RAW_DIR"

echo "Downloading official NVIDIA PTX ISA 9.3 PDF..."
curl \
  --fail \
  --location \
  --retry 3 \
  --retry-delay 2 \
  --connect-timeout 20 \
  "$PDF_URL" \
  --output "$PDF_PATH.tmp"

mv "$PDF_PATH.tmp" "$PDF_PATH"

echo "Downloading official NVIDIA PTX ISA 9.3 HTML..."
curl \
  --fail \
  --location \
  --retry 3 \
  --retry-delay 2 \
  --connect-timeout 20 \
  "$HTML_URL" \
  --output "$HTML_PATH.tmp"

mv "$HTML_PATH.tmp" "$HTML_PATH"

python3 - "$SOURCE_DIR" <<'PY'
from __future__ import annotations

import hashlib
import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

source_dir = Path(sys.argv[1])
raw_dir = source_dir / "raw"

pdf_path = raw_dir / "ptx_isa_9.3.pdf"
html_path = raw_dir / "ptx_isa_9.3.html"

pdf_data = pdf_path.read_bytes()
html_data = html_path.read_bytes()

if not pdf_data.startswith(b"%PDF-"):
    raise SystemExit("ERROR: downloaded PDF has no valid PDF header")

if len(pdf_data) < 1_000_000:
    raise SystemExit("ERROR: downloaded PDF is unexpectedly small")

if len(html_data) < 100_000:
    raise SystemExit("ERROR: downloaded HTML is unexpectedly small")

html_source = html_data.decode("utf-8", errors="replace")
plain_text = re.sub(r"<[^>]+>", " ", html_source)
plain_text = html.unescape(plain_text)
plain_text = " ".join(plain_text.split())

required_markers = [
    "Parallel Thread Execution ISA Version 9.3",
    "Integer Arithmetic Instructions: add",
    "add.type1",
]

for marker in required_markers:
    if marker not in plain_text:
        raise SystemExit(
            f"ERROR: expected PTX marker not found: {marker!r}"
        )

anchor_match = re.search(
    r'id="([^"]*integer-arithmetic-instructions-add[^"]*)"',
    html_source,
)

add_anchor = anchor_match.group(1) if anchor_match else None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


manifest = {
    "schema_version": 1,
    "publisher": "NVIDIA Corporation",
    "document_title": "Parallel Thread Execution ISA",
    "language": "PTX",
    "specification_version": "9.3",
    "source_classification": "official",
    "retrieved_at_utc": (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    ),
    "initial_formalization_unit": {
        "construct": "add.u32",
        "instruction_family": "add",
        "section_number": "9.7.1.1",
        "section_heading": "Integer Arithmetic Instructions: add",
        "html_anchor": add_anchor,
    },
    "artifacts": [
        {
            "kind": "pdf",
            "url": "https://docs.nvidia.com/cuda/pdf/ptx_isa_9.3.pdf",
            "local_path": "raw/ptx_isa_9.3.pdf",
            "sha256": sha256(pdf_path),
            "size_bytes": pdf_path.stat().st_size,
        },
        {
            "kind": "html",
            "url": (
                "https://docs.nvidia.com/cuda/"
                "parallel-thread-execution/index.html"
            ),
            "local_path": "raw/ptx_isa_9.3.html",
            "sha256": sha256(html_path),
            "size_bytes": html_path.stat().st_size,
        },
    ],
    "semantic_status": "not_started",
    "notes": [
        "Documents were downloaded directly from official NVIDIA URLs.",
        "No semantic interpretation was produced during acquisition.",
        "Local raw files are identified by SHA-256 hashes.",
    ],
}

manifest_path = source_dir / "source-manifest.json"

manifest_path.write_text(
    json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)

checksums_path = source_dir / "SHA256SUMS"

checksums_path.write_text(
    f"{sha256(pdf_path)}  raw/{pdf_path.name}\n"
    f"{sha256(html_path)}  raw/{html_path.name}\n",
    encoding="utf-8",
)

print()
print("PTX source acquisition succeeded")
print(f"PDF:      {pdf_path}")
print(f"HTML:     {html_path}")
print(f"Manifest: {manifest_path}")
print(f"Anchor:   {add_anchor or 'not detected'}")
PY

echo
echo "Verifying checksums..."
(
  cd "$SOURCE_DIR"
  sha256sum --check SHA256SUMS
)
