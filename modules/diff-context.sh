#!/usr/bin/env bash
# Diff-oriented context wrapper for llmtk

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXPORTS_DIR="${PWD}/exports/diff_context"

# Parse arguments
COMMAND=""
ARGS=()

while [[ $# -gt 0 ]]; do
    case $1 in
        diff|incremental|bisect)
            COMMAND="$1"
            shift
            ;;
        --help|-h)
            echo "Usage: llmtk diff-context <command> [options]"
            echo ""
            echo "Commands:"
            echo "  diff         Export diff-based context between git references"
            echo "  incremental  Export incremental context focusing on recent changes"
            echo "  bisect       Set up automated bisect for regression hunting"
            echo ""
            echo "Examples:"
            echo "  llmtk diff-context diff --base=main --target=feature-branch"
            echo "  llmtk diff-context incremental --cache=.llmtk-cache"
            echo "  llmtk diff-context bisect --good=v1.0 --bad=HEAD --test-cmd='make test'"
            echo ""
            echo "For command-specific help:"
            echo "  python3 $SCRIPT_DIR/diff_context.py <command> --help"
            exit 0
            ;;
        *)
            ARGS+=("$1")
            shift
            ;;
    esac
done

if [[ -z "$COMMAND" ]]; then
    echo "Error: No command specified. Use --help for usage information." >&2
    exit 1
fi

# Ensure exports directory exists
mkdir -p "$EXPORTS_DIR"

# Run the Python diff context analyzer
python3 "$SCRIPT_DIR/diff_context.py" "$COMMAND" "${ARGS[@]}"