#!/usr/bin/env bash
# Dependency graph extraction wrapper for llmtk

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXPORTS_DIR="${PWD}/exports"
BUILD_DIR="${PWD}/build"

# Parse arguments
JSON_FLAG=""
GRAPHVIZ_FLAG=""
SYMBOLS_FLAG=""
BUILD_DIR_ARG=""
OUTPUT_DIR_ARG=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --json)
            JSON_FLAG="--json"
            shift
            ;;
        --graphviz)
            GRAPHVIZ_FLAG="--graphviz"
            shift
            ;;
        --symbols)
            SYMBOLS_FLAG="--symbols"
            shift
            ;;
        --build-dir)
            BUILD_DIR_ARG="--build-dir $2"
            BUILD_DIR="$2"
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR_ARG="--output-dir $2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: llmtk deps [options]"
            echo ""
            echo "Extract and export CMake target dependency graphs"
            echo ""
            echo "Options:"
            echo "  --json             Export JSON format (default)"
            echo "  --graphviz         Export Graphviz DOT format"
            echo "  --symbols          Include symbol-level analysis"
            echo "  --build-dir DIR    CMake build directory (default: build)"
            echo "  --output-dir DIR   Output directory (default: exports/dependency_graphs)"
            echo "  --help, -h         Show this help message"
            echo ""
            echo "Examples:"
            echo "  llmtk deps                      # Export JSON dependencies"
            echo "  llmtk deps --graphviz           # Export Graphviz format"
            echo "  llmtk deps --json --graphviz    # Export both formats"
            echo "  llmtk deps --symbols            # Include symbol analysis"
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

# Ensure CMake File API query exists
if [[ -d "$BUILD_DIR" ]]; then
    mkdir -p "$BUILD_DIR/.cmake/api/v1/query"
    touch "$BUILD_DIR/.cmake/api/v1/query/codemodel-v2"

    # Try to trigger CMake to generate the response
    if [[ -f "$BUILD_DIR/CMakeCache.txt" ]]; then
        cmake --build "$BUILD_DIR" --target help >/dev/null 2>&1 || true
    fi
fi

# Run the Python dependency analyzer
python3 "$SCRIPT_DIR/dependency_graph.py" \
    $BUILD_DIR_ARG \
    $OUTPUT_DIR_ARG \
    $JSON_FLAG \
    $GRAPHVIZ_FLAG \
    $SYMBOLS_FLAG