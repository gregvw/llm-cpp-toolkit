#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "usage: modules/reduce.sh <input> <test_cmd>" >&2
  exit 2
fi

INPUT=$1
TEST_CMD=$2
ROOT_DIR=$(pwd)
REPRO_DIR="$ROOT_DIR/exports/repros"
mkdir -p "$REPRO_DIR"

REPORT="$REPRO_DIR/report.json"

if ! command -v cvise >/dev/null 2>&1; then
  echo "{\"cvise_available\": false, \"note\": \"cvise not found; skip\", \"input\": \"$INPUT\"}" > "$REPORT"
  echo "$REPORT"
  exit 0
fi

set +e
cvise "$INPUT" -- bash -lc "$TEST_CMD"
RC=$?
set -e

echo "{\"cvise_available\": true, \"exit_code\": $RC, \"input\": \"$INPUT\"}" > "$REPORT"
echo "$REPORT"

