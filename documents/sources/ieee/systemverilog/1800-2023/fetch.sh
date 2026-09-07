#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
RAW_DIR="$SOURCE_DIR/raw"
PDF_PATH="$RAW_DIR/IEEE_Std_1800-2023.pdf"
PDF_URL="https://www.iccircle.com/static/upload/img20240319175450.pdf"

mkdir -p "$RAW_DIR"

echo "Downloading IEEE Std 1800-2023 SystemVerilog specification..."
curl \
  --fail \
  --location \
  --retry 3 \
  --retry-delay 2 \
  --connect-timeout 20 \
  "$PDF_URL" \
  --output "$PDF_PATH.tmp"

mv "$PDF_PATH.tmp" "$PDF_PATH"

if [[ "$(head -c 5 "$PDF_PATH")" != "%PDF-" ]]; then
  echo "ERROR: downloaded file has no valid PDF header" >&2
  exit 1
fi

echo
echo "Verifying checksum..."
(
  cd "$SOURCE_DIR"
  sha256sum --check SHA256SUMS
)

echo
echo "SystemVerilog source acquisition succeeded"
echo "PDF: $PDF_PATH"
