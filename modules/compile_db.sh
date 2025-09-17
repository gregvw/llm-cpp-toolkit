#!/usr/bin/env bash
set -euo pipefail

BUILD_DIR=${1:-build}
ROOT_DIR=$(pwd)
EXPORTS_DIR="$ROOT_DIR/exports"
mkdir -p "$EXPORTS_DIR"

echo "[llmtk] Generating compile_commands.json into exports/" >&2
cmake -S . -B "$BUILD_DIR" -G Ninja -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
if [[ -f "$BUILD_DIR/compile_commands.json" ]]; then
  cp "$BUILD_DIR/compile_commands.json" "$EXPORTS_DIR/compile_commands.json"
  echo "$EXPORTS_DIR/compile_commands.json"
else
  echo "[llmtk] compile_commands.json not found in $BUILD_DIR" >&2
  exit 0
fi
