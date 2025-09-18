#!/bin/bash
# Export comprehensive project context for LLM consumption

set -euo pipefail

EXPORTS_DIR="${PWD}/exports"
mkdir -p "$EXPORTS_DIR"

TIMESTAMP=$(date -u +"%Y%m%d_%H%M%S")
OUTPUT_FILE="$EXPORTS_DIR/context_${TIMESTAMP}.json"

# Export functions
export_file_tree() {
    if command -v fd >/dev/null 2>&1; then
        fd -t f -H | head -1000 | jq -R -s 'split("\n")[:-1] | map(select(length > 0))'
    else
        find . -type f | head -1000 | jq -R -s 'split("\n")[:-1] | map(select(length > 0))'
    fi
}

export_cpp_files() {
    if command -v fd >/dev/null 2>&1; then
        fd '\.(cpp|hpp|cc|h|cxx)$' | head -500 | jq -R -s 'split("\n")[:-1] | map(select(length > 0))'
    else
        find . -name '*.cpp' -o -name '*.hpp' -o -name '*.cc' -o -name '*.h' -o -name '*.cxx' | head -500 | jq -R -s 'split("\n")[:-1] | map(select(length > 0))'
    fi
}

export_cmake_files() {
    if command -v fd >/dev/null 2>&1; then
        fd 'CMakeLists\.txt|.*\.cmake$' | jq -R -s 'split("\n")[:-1] | map(select(length > 0))'
    else
        find . -name 'CMakeLists.txt' -o -name '*.cmake' | jq -R -s 'split("\n")[:-1] | map(select(length > 0))'
    fi
}

export_includes() {
    if command -v rg >/dev/null 2>&1; then
        rg '#include\s*[<"]([^>"]+)[>"]' --only-matching --replace '$1' --no-filename | sort -u | head -200 | jq -R -s 'split("\n")[:-1] | map(select(length > 0))'
    else
        grep -r '#include' . --include='*.cpp' --include='*.hpp' --include='*.cc' --include='*.h' | \
        sed 's/.*#include\s*[<"]\([^>"]*\)[>"].*/\1/' | sort -u | head -200 | jq -R -s 'split("\n")[:-1] | map(select(length > 0))'
    fi
}

export_functions() {
    if command -v rg >/dev/null 2>&1; then
        rg '^[^/]*\w+\s+\w+\s*\([^)]*\)\s*\{?' --only-matching --no-filename | head -300 | jq -R -s 'split("\n")[:-1] | map(select(length > 0))'
    else
        echo '[]'
    fi
}

# Main execution
{
    echo "{"
    echo "  \"timestamp\": \"$(date -u --iso-8601=seconds)\","
    echo "  \"project_root\": \"$PWD\","
    echo "  \"file_tree\": $(export_file_tree),"
    echo "  \"cpp_files\": $(export_cpp_files),"
    echo "  \"cmake_files\": $(export_cmake_files),"
    echo "  \"includes\": $(export_includes),"
    echo "  \"functions\": $(export_functions),"
    echo "  \"stats\": {"
    echo "    \"total_files\": $(find . -type f | wc -l),"
    echo "    \"cpp_files_count\": $(find . -name '*.cpp' -o -name '*.hpp' -o -name '*.cc' -o -name '*.h' | wc -l),"
    echo "    \"cmake_files_count\": $(find . -name 'CMakeLists.txt' -o -name '*.cmake' | wc -l)"
    echo "  }"
    echo "}"
} > "$OUTPUT_FILE"

echo "$OUTPUT_FILE"
