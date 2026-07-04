#!/usr/bin/env bash
# Build the Lambda deployment package: pip-install pure-Python deps and copy the
# application source into a staging dir that archive_file zips. boto3 is provided
# by the Lambda runtime, so it is not installed here.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PACKAGE_DIR="$SCRIPT_DIR/build/package"

rm -rf "$PACKAGE_DIR"
mkdir -p "$PACKAGE_DIR"

python3 -m pip install \
  --no-cache-dir \
  --quiet \
  --requirement "$ROOT_DIR/requirements.txt" \
  --target "$PACKAGE_DIR"

cp -R "$ROOT_DIR/src" "$PACKAGE_DIR/src"

# Drop compiled caches so the zip is deterministic.
find "$PACKAGE_DIR" -type d -name "__pycache__" -prune -exec rm -rf {} +

echo "Built package at $PACKAGE_DIR"
