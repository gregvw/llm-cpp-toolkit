"""Doctor command - system health check."""

import argparse
import datetime
import os
import shutil
from typing import List

from ..core.context import get_root, get_exports_dir
from ..core.utils import run, write_json
from ..services.manifest import load_tools_manifest
from ..services.cmake import validate_cmake_guidance

def cmd_doctor(args: argparse.Namespace) -> int:
    """Execute the doctor command."""
    # Load from manifest to get complete tool list
    tools_config = load_tools_manifest()

    if tools_config and "tools" in tools_config:
        # Get all tools from manifest, prioritizing core and recommended
        all_tools = tools_config["tools"]
        tools = []
        for name, config in all_tools.items():
            role = config.get("role", "optional")
            if role in ["core", "recommended"]:
                tools.append(name)
        # Add any remaining tools
        for name in all_tools.keys():
            if name not in tools:
                tools.append(name)
    else:
        # Fallback list
        tools = [
            "cmake", "ninja", "clangd", "clang-tidy", "clang-format",
            "include-what-you-use", "cppcheck", "rg", "fd", "jq", "yq", "bear", "ccache", "mold"
        ]

    report = {"_meta": {"generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()}}

    found_tools = []
    missing_core = []
    missing_recommended = []
    missing_optional = []

    # Add local bin to PATH for tool discovery
    local_bin = get_root() / ".llmtk" / "bin"
    old_path = os.environ.get("PATH", "")
    if local_bin.exists():
        os.environ["PATH"] = f"{local_bin}:{old_path}"

    try:
        for t in tools:
            # Get the actual command to check from the manifest
            actual_cmd = t
            if tools_config and "tools" in tools_config:
                tool_config = tools_config["tools"].get(t, {})
                check_config = tool_config.get("check", {})
                if isinstance(check_config, dict) and "cmd" in check_config:
                    actual_cmd = check_config["cmd"][0]  # First element is the command name

            path = shutil.which(actual_cmd)
            info = {"found": bool(path), "path": path or None}
            if path:
                try:
                    result = run([actual_cmd, "--version"], check=False)
                    out = result.stdout.splitlines() if result.stdout else []
                    info["version_line"] = out[0] if out else None
                except Exception:
                    info["version_line"] = None
                found_tools.append(t)
            else:
                # Categorize missing tools by role
                if tools_config and "tools" in tools_config:
                    tool_config = tools_config["tools"].get(t, {})
                    role = tool_config.get("role", "optional")
                    if role == "core":
                        missing_core.append(t)
                    elif role == "recommended":
                        missing_recommended.append(t)
                    else:
                        missing_optional.append(t)
                else:
                    missing_core.append(t)  # Default to core for fallback
            report[t] = info
    finally:
        # Restore original PATH
        os.environ["PATH"] = old_path

    # Add CMake validation to the report
    cmake_validation = validate_cmake_guidance()
    report["_cmake"] = cmake_validation

    # Add summary to report
    report["_summary"] = {
        "total_tools": len(tools),
        "found": len(found_tools),
        "missing": len(tools) - len(found_tools),
        "missing_core": missing_core,
        "missing_recommended": missing_recommended,
        "missing_optional": missing_optional,
        "cmake_compliance_score": cmake_validation["overall_score"]
    }

    out = get_exports_dir() / "doctor.json"
    write_json(out, report)

    # Print user-friendly summary if not being called from install
    if not hasattr(args, '_from_install'):
        _print_summary(found_tools, tools, missing_core, missing_recommended, cmake_validation, args)

    print(str(out))
    return 0

def _print_summary(found_tools: List[str], tools: List[str], missing_core: List[str],
                  missing_recommended: List[str], cmake_validation: dict, args: argparse.Namespace) -> None:
    """Print user-friendly summary."""
    # Check if this is CMake-focused or full health check
    cmake_only = hasattr(args, 'cmake') and args.cmake

    if cmake_only:
        print()
        print("🏗️ CMAKE COMPLIANCE CHECK")
        print("=" * 40)
    else:
        print()
        print("🏥 HEALTH CHECK SUMMARY")
        print("=" * 40)
        print(f"✅ Found: {len(found_tools)}/{len(tools)} tools")

    # Show different content based on mode
    if not cmake_only:
        if missing_core:
            print(f"\n❌ Missing core tools ({len(missing_core)}):")
            for tool in missing_core:
                print(f"   • {tool}")

        if missing_recommended:
            print(f"\n⚠️ Missing recommended tools ({len(missing_recommended)}):")
            for tool in missing_recommended:
                print(f"   • {tool}")

    # Show CMake compliance status (always shown)
    cmake_score = cmake_validation["overall_score"]
    if cmake_validation["cmake_file_exists"]:
        if cmake_score >= 80:
            print(f"\n🏗️ CMake setup: ✅ {cmake_score:.0f}% compliant with CMAKE_GUIDANCE.md")
        elif cmake_score >= 50:
            print(f"\n🏗️ CMake setup: ⚠️ {cmake_score:.0f}% compliant with CMAKE_GUIDANCE.md")
        else:
            print(f"\n🏗️ CMake setup: ❌ {cmake_score:.0f}% compliant with CMAKE_GUIDANCE.md")

        # Show detailed compliance breakdown in CMake-only mode
        if cmake_only:
            print(f"\n📋 Compliance Details:")
            for key, value in cmake_validation["compliance"].items():
                status = "✅" if value else "❌"
                readable_name = key.replace("_", " ").title()
                print(f"   {status} {readable_name}")

        if cmake_validation["suggestions"]:
            suggestions_to_show = cmake_validation["suggestions"] if cmake_only else cmake_validation["suggestions"][:3]
            print("   CMake improvements needed:")
            for suggestion in suggestions_to_show:
                print(f"   • {suggestion}")
    else:
        print(f"\n🏗️ CMake setup: ❌ No CMakeLists.txt found")
        print("   • Run 'llmtk init' to create LLM-optimized project structure")

    # Recommendations section
    needs_tools = missing_core or missing_recommended
    needs_cmake = cmake_score < 80

    if (not cmake_only and needs_tools) or needs_cmake:
        print(f"\n💡 RECOMMENDED ACTIONS:")
        if not cmake_only and needs_tools:
            print(f"   • Run 'llmtk install' to install missing tools")
            print(f"   • Use 'llmtk install --local' for non-sudo installation")
        if needs_cmake:
            print(f"   • Run 'llmtk init' to upgrade CMake setup for LLM workflows")
            print(f"   • See CMAKE_GUIDANCE.md for manual setup instructions")

def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the doctor command."""
    parser = subparsers.add_parser(
        "doctor",
        help="Check system dependencies and CMake configuration"
    )
    parser.add_argument(
        "--cmake",
        action="store_true",
        help="Focus on CMake compliance checking only"
    )
    parser.set_defaults(func=cmd_doctor)
