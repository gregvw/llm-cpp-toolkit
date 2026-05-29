"""Init command - create or upgrade projects for LLM workflows."""

import argparse
import os
import pathlib
import shutil
from typing import Optional

from ..core.context import get_root, get_exports_dir
from ..core.utils import run, write_json
from ..services.manifest import load_tools_manifest
from ..services.scaffold import context_from_preset, render_scaffold


def cmd_init(args: argparse.Namespace) -> int:
    """Execute the init command."""
    if args.existing:
        return init_existing_project(args.path or pathlib.Path.cwd())
    elif args.project_name:
        return init_new_project(args.project_name, args)
    else:
        print("Error: Must specify either project name or --existing flag")
        return 1


def init_new_project(project_name: str, args: argparse.Namespace) -> int:
    """Initialize a new C++ project."""
    project_path = pathlib.Path(project_name)

    if project_path.exists():
        print(f"Error: Directory '{project_name}' already exists")
        return 1

    print(f"Creating new C++ project: {project_name}")

    try:
        # Create project directory structure
        project_path.mkdir(parents=True, exist_ok=True)
        (project_path / "src").mkdir(exist_ok=True)
        (project_path / "include").mkdir(exist_ok=True)
        (project_path / "tests").mkdir(exist_ok=True)
        (project_path / "exports").mkdir(exist_ok=True)

        # Render scaffold files (CMakeLists.txt, src/main.cpp, .gitignore,
        # CMakePresets.json) from Jinja2 templates.
        ctx = context_from_preset(
            project_name,
            preset=getattr(args, "preset", "executable"),
            cpp_standard=getattr(args, "std", "17"),
            cmake_minimum=getattr(args, "cmake_min", "3.20"),
        )
        render_scaffold(ctx, project_path)

        # Initialize git repository
        original_cwd = os.getcwd()
        try:
            os.chdir(project_path)
            run(["git", "init"])
            run(["git", "add", "."])
            run(["git", "commit", "-m", f"Initial commit: {project_name} project"])
        finally:
            os.chdir(original_cwd)

        # Generate capabilities.json
        generate_capabilities(project_path)

        print(f"✅ Successfully created project '{project_name}'")
        print(f"📁 Project created in: {project_path.absolute()}")
        print("\n🚀 Next steps:")
        print(f"   cd {project_name}")
        print("   cmake -S . -B build")
        print("   cmake --build build")
        if ctx.target_type == "executable":
            print(f"   ./build/{project_name}")

        return 0

    except Exception as e:
        print(f"Error creating project: {e}")
        # Clean up on failure
        if project_path.exists():
            shutil.rmtree(project_path)
        return 1


def init_existing_project(project_path: pathlib.Path) -> int:
    """Initialize an existing project for LLM workflows."""
    project_path = project_path.resolve()
    print(f"Upgrading existing project for LLM workflows: {project_path}")

    try:
        # Create exports directory
        exports_dir = project_path / "exports"
        exports_dir.mkdir(exist_ok=True)

        # Copy compile_commands.json if it exists
        build_compile_commands = project_path / "build" / "compile_commands.json"
        root_compile_commands = project_path / "compile_commands.json"

        if build_compile_commands.exists():
            shutil.copy2(build_compile_commands, exports_dir / "compile_commands.json")
            print("✅ Copied compile_commands.json from build/ to exports/")
        elif root_compile_commands.exists():
            shutil.copy2(root_compile_commands, exports_dir / "compile_commands.json")
            print("✅ Copied compile_commands.json to exports/")
        else:
            print("ℹ️  No compile_commands.json found - run CMake with CMAKE_EXPORT_COMPILE_COMMANDS=ON")

        # Generate capabilities.json
        generate_capabilities(project_path)

        print("✅ Successfully upgraded project for LLM workflows")
        print("📁 Exports directory created with capabilities.json")

        return 0

    except Exception as e:
        print(f"Error upgrading project: {e}")
        return 1


def generate_capabilities(project_path: pathlib.Path) -> None:
    """Generate capabilities.json for the project."""
    exports_dir = project_path / "exports"

    capabilities = {
        "_meta": {
            "generated_by": "llmtk init",
            "project_root": str(project_path),
            "exports_dir": str(exports_dir)
        },
        "build": {
            "system": "cmake",
            "compile_commands": str(exports_dir / "compile_commands.json") if (exports_dir / "compile_commands.json").exists() else None
        },
        "tools": {}
    }

    # Load available tools
    tools_manifest = load_tools_manifest()
    if tools_manifest and "tools" in tools_manifest:
        capabilities["tools"] = tools_manifest["tools"]

    write_json(exports_dir / "capabilities.json", capabilities)
    print("✅ Generated capabilities.json")


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the init command."""
    parser = subparsers.add_parser(
        "init",
        help="Create new projects or upgrade existing ones for LLM workflows"
    )

    # Mutually exclusive group for new vs existing
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "project_name",
        nargs="?",
        help="Name of the new project to create"
    )
    group.add_argument(
        "--existing",
        action="store_true",
        help="Upgrade an existing project for LLM workflows"
    )

    # Optional arguments for new projects
    parser.add_argument(
        "--path",
        type=pathlib.Path,
        help="Path to existing project (default: current directory)"
    )
    parser.add_argument(
        "--std",
        default="17",
        help="C++ standard version (default: 17)"
    )
    parser.add_argument(
        "--cmake-min",
        default="3.20",
        help="Minimum CMake version (default: 3.20)"
    )
    parser.add_argument(
        "--preset",
        choices=["executable", "library", "full", "minimal"],
        default="executable",
        help="Project template preset (default: executable)"
    )

    parser.set_defaults(func=cmd_init)