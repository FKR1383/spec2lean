#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
RAW_DIR="$SOURCE_DIR/raw"

PDF_URL="https://cdrdv2-public.intel.com/922480/253666-092-sdm-vol-2a.pdf"
PDF_PATH="$RAW_DIR/253666-092-sdm-vol-2a.pdf"

mkdir -p "$RAW_DIR"

echo "Downloading official Intel x86 instruction-set reference (SDM Volume 2A, revision 092)..."
curl \
  --fail \
  --location \
  --retry 3 \
  --retry-delay 2 \
  --connect-timeout 20 \
  "$PDF_URL" \
  --output "$PDF_PATH.tmp"

mv "$PDF_PATH.tmp" "$PDF_PATH"

python3 - "$SOURCE_DIR" <<'PY'
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

source_dir = Path(sys.argv[1])
pdf_path = source_dir / "raw" / "253666-092-sdm-vol-2a.pdf"
pdf_data = pdf_path.read_bytes()

if not pdf_data.startswith(b"%PDF-"):
    raise SystemExit("ERROR: downloaded file has no valid PDF header")

if len(pdf_data) < 1_000_000:
    raise SystemExit("ERROR: downloaded PDF is unexpectedly small")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


manifest = {
    "schema_version": 1,
    "publisher": "Intel Corporation",
    "document_title": (
        "Intel 64 and IA-32 Architectures Software Developer's Manual, "
        "Volume 2A: Instruction Set Reference, A-L"
    ),
    "language": "x86",
    "specification_version": "092",
    "source_classification": "official",
    "retrieved_at_utc": (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    ),
    "initial_formalization_unit": {
        "construct": "ADD",
        "instruction_family": "general-purpose integer arithmetic",
        "section_heading": "ADD-Add",
    },
    "sample_instructions": ["ADD", "AND", "CMP", "DEC", "INC"],
    "artifacts": [
        {
            "kind": "pdf",
            "url": "https://cdrdv2-public.intel.com/922480/253666-092-sdm-vol-2a.pdf",
            "local_path": "raw/253666-092-sdm-vol-2a.pdf",
            "sha256": sha256(pdf_path),
            "size_bytes": pdf_path.stat().st_size,
        }
    ],
    "semantic_status": "not_started",
    "notes": [
        "Downloaded directly from Intel's official SDM download service.",
        "Volume 2A is the A-L portion of the x86 instruction-set reference.",
        "The selected sample instructions are all fully covered by this volume.",
        "No semantic interpretation was produced during acquisition.",
        "The local raw file is identified by its SHA-256 hash.",
    ],
}

(source_dir / "source-manifest.json").write_text(
    json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)
(source_dir / "SHA256SUMS").write_text(
    f"{sha256(pdf_path)}  raw/{pdf_path.name}\n",
    encoding="utf-8",
)

print()
print("Intel x86 source acquisition succeeded")
print(f"PDF:      {pdf_path}")
print(f"Manifest: {source_dir / 'source-manifest.json'}")
PY

echo
echo "Verifying checksums..."
(
  cd "$SOURCE_DIR"
  sha256sum --check SHA256SUMS
)
