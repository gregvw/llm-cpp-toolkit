#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(pwd)
EXPORTS_DIR="$ROOT_DIR/exports/reports"
mkdir -p "$EXPORTS_DIR"

COMPILE_DB="$ROOT_DIR/exports/compile_commands.json"
PATHS=("${@:-src include .}")

have() { command -v "$1" >/dev/null 2>&1; }

# clang-tidy (placeholder – wire real invocation later)
{
  echo "{"
  echo "  \"note\": \"wire real clang-tidy invocation\"," 
       "\"available\": $(have clang-tidy && echo true || echo false),"
  echo "  \"compile_commands\": \"$COMPILE_DB\""
  echo "}"
} > "$EXPORTS_DIR/clang-tidy.json"

# IWYU (placeholder)
{
  echo "{\"note\": \"invoke IWYU via compile_commands\", \"available\": $(have include-what-you-use && echo true || echo false)}"
} > "$EXPORTS_DIR/iwyu.json"

# cppcheck (placeholder)
{
  echo "{\"note\": \"run cppcheck --project exports/compile_commands.json\", \"available\": $(have cppcheck && echo true || echo false)}"
} > "$EXPORTS_DIR/cppcheck.json"

echo "$EXPORTS_DIR"

