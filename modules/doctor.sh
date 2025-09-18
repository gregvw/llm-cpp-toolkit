#!/bin/bash
# Check system health and tool availability

set -euo pipefail

EXPORTS_DIR="${PWD}/exports"
mkdir -p "$EXPORTS_DIR"

TIMESTAMP=$(date -u +"%Y%m%d_%H%M%S")
OUTPUT_FILE="$EXPORTS_DIR/doctor_${TIMESTAMP}.json"

# Health check functions
check_tool() {
    local tool="$1"
    local required_version="$2"
    
    if command -v "$tool" >/dev/null 2>&1; then
        local version=$(get_tool_version "$tool")
        echo "{\"tool\":\"$tool\",\"available\":true,\"version\":\"$version\",\"status\":\"ok\"}"
    else
        echo "{\"tool\":\"$tool\",\"available\":false,\"version\":null,\"status\":\"missing\"}"
    fi
}

get_tool_version() {
    case "$1" in
        "rg") rg --version | head -1 | cut -d' ' -f2 ;;
        "fd") fd --version | cut -d' ' -f2 ;;
        "fzf") fzf --version | cut -d' ' -f1 ;;
        "bear") bear --version 2>/dev/null | head -1 | cut -d' ' -f2 || echo "unknown" ;;
        "ninja") ninja --version ;;
        "cmake") cmake --version | head -1 | cut -d' ' -f3 ;;
        *) echo "unknown" ;;
    esac
}

check_project() {
    local has_cmake=$([ -f "CMakeLists.txt" ] && echo true || echo false)
    local has_compile_db=$([ -f "compile_commands.json" ] && echo true || echo false)
    local has_git=$([ -d ".git" ] && echo true || echo false)
    
    echo "{\"cmake_project\":$has_cmake,\"compile_database\":$has_compile_db,\"git_repo\":$has_git}"
}

# Main execution
{
    echo "{"
    echo "  \"timestamp\": \"$(date -u --iso-8601=seconds)\","
    echo "  \"tools\": ["
    
    tools=("rg" "fd" "fzf" "bear" "ninja" "cmake" "clang-query" "cppcheck")
    for i in "${!tools[@]}"; do
        check_tool "${tools[$i]}" ""
        if [[ $i -lt $((${#tools[@]} - 1)) ]]; then
            echo ","
        fi
    done
    
    echo "  ],"
    echo "  \"project\": $(check_project),"
    echo "  \"system\": {"
    echo "    \"os\": \"$(uname -s)\","
    echo "    \"arch\": \"$(uname -m)\","
    echo "    \"pwd\": \"$PWD\""
    echo "  }"
    echo "}"
} > "$OUTPUT_FILE"

# Single line stdout as promised
echo "$OUTPUT_FILE"
