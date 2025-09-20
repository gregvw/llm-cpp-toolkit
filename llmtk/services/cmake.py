"""CMake-related services and validation."""

import pathlib
from typing import Any, Dict

def validate_cmake_guidance(project_dir: pathlib.Path = None) -> Dict[str, Any]:
    """Validate CMakeLists.txt compliance with CMAKE_GUIDANCE.md patterns."""
    if project_dir is None:
        project_dir = pathlib.Path.cwd()
    else:
        project_dir = pathlib.Path(project_dir)

    cmake_file = project_dir / "CMakeLists.txt"

    result = {
        "cmake_file_exists": cmake_file.exists(),
        "compliance": {
            "compile_commands_export": False,
            "project_warnings_interface": False,
            "project_sanitizers_interface": False,
            "json_diagnostics": False,
            "cxx_standard_set": False,
            "lint_target": False
        },
        "suggestions": [],
        "overall_score": 0
    }

    if not cmake_file.exists():
        result["suggestions"].append("Create CMakeLists.txt with 'llmtk init'")
        return result

    try:
        cmake_content = cmake_file.read_text()

        # Check for required patterns from CMAKE_GUIDANCE.md
        patterns = {
            "compile_commands_export": "CMAKE_EXPORT_COMPILE_COMMANDS ON",
            "project_warnings_interface": "add_library(project_warnings INTERFACE)",
            "project_sanitizers_interface": "add_library(project_sanitizers INTERFACE)",
            "json_diagnostics": "fdiagnostics-format=json",
            "cxx_standard_set": "CMAKE_CXX_STANDARD",
            "lint_target": "add_custom_target(lint"
        }

        for key, pattern in patterns.items():
            if pattern in cmake_content:
                result["compliance"][key] = True
            else:
                # Add specific suggestions based on missing patterns
                if key == "compile_commands_export":
                    result["suggestions"].append("Add 'set(CMAKE_EXPORT_COMPILE_COMMANDS ON)' for clangd support")
                elif key == "project_warnings_interface":
                    result["suggestions"].append("Create project_warnings INTERFACE library for consistent warnings")
                elif key == "json_diagnostics":
                    result["suggestions"].append("Add JSON diagnostics support for LLM-friendly error output")
                elif key == "lint_target":
                    result["suggestions"].append("Add custom lint target for syntax-only checking")

        # Calculate overall compliance score
        compliant_count = sum(result["compliance"].values())
        total_checks = len(result["compliance"])
        result["overall_score"] = (compliant_count / total_checks) * 100

    except Exception as e:
        result["suggestions"].append(f"Error reading CMakeLists.txt: {e}")

    return result