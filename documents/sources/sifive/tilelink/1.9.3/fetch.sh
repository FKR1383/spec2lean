#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
RAW_DIR="$SOURCE_DIR/raw"

LANDING_URL="https://www.sifive.com/document-file/tilelink-spec-1.9.3"
PDF_URL="https://sifive.cdn.prismic.io/sifive/928d6a82-77a9-4291-8b60-5e815429b1ab_tilelink_spec_1.9.3.pdf"
PDF_PATH="$RAW_DIR/tilelink_spec_1.9.3.pdf"

mkdir -p "$RAW_DIR"

echo "Downloading official SiFive TileLink Specification 1.9.3..."
curl \
  --fail \
  --location \
  --retry 3 \
  --retry-delay 2 \
  --connect-timeout 20 \
  "$PDF_URL" \
  --output "$PDF_PATH.tmp"

mv "$PDF_PATH.tmp" "$PDF_PATH"

python3 - "$SOURCE_DIR" "$LANDING_URL" "$PDF_URL" <<'PY'
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

source_dir = Path(sys.argv[1])
landing_url = sys.argv[2]
pdf_url = sys.argv[3]
pdf_path = source_dir / "raw" / "tilelink_spec_1.9.3.pdf"
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
    "publisher": "SiFive, Inc.",
    "document_title": "SiFive TileLink Specification",
    "language": "TileLink",
    "specification_version": "1.9.3",
    "source_classification": "official",
    "retrieved_at_utc": (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    ),
    "initial_formalization_unit": {
        "construct": "TL-UL messages",
        "instruction_family": "TileLink Uncached Lightweight messages",
        "section_number": "7.2",
        "section_heading": "TL-UL Messages",
    },
    "sample_instructions": [
        "Get",
        "PutFullData",
        "PutPartialData",
        "AccessAck",
        "AccessAckData",
    ],
    "artifacts": [
        {
            "kind": "pdf",
            "url": pdf_url,
            "landing_url": landing_url,
            "local_path": "raw/tilelink_spec_1.9.3.pdf",
            "sha256": sha256(pdf_path),
            "size_bytes": pdf_path.stat().st_size,
        }
    ],
    "semantic_status": "not_started",
    "notes": [
        "Downloaded from the PDF linked by SiFive's official documentation page.",
        "TileLink was designed for RISC-V but is not itself a RISC-V ISA specification.",
        "The initial bounded scope is the five TL-UL request/response messages in section 7.2.",
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
print("TileLink source acquisition succeeded")
print(f"PDF:      {pdf_path}")
print(f"Manifest: {source_dir / 'source-manifest.json'}")
PY

echo
echo "Verifying checksum..."
(
  cd "$SOURCE_DIR"
  sha256sum --check SHA256SUMS
)
