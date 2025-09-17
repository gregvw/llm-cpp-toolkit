#!/usr/bin/env bash
set -euo pipefail

BUILD_DIR=${1:-build}
ROOT_DIR=$(pwd)
EXPORTS_DIR="$ROOT_DIR/exports/cmake-file-api"
mkdir -p "$EXPORTS_DIR"

echo "[llmtk] Querying CMake File API codemodel" >&2
mkdir -p "$BUILD_DIR/.cmake/api/v1/query"
touch "$BUILD_DIR/.cmake/api/v1/query/codemodel-v2"

cmake --build "$BUILD_DIR" || true

REPLY_DIR="$BUILD_DIR/.cmake/api/v1/reply"
if [[ -d "$REPLY_DIR" ]]; then
  cp "$REPLY_DIR"/* "$EXPORTS_DIR"/ || true
  echo "$EXPORTS_DIR"
fi
