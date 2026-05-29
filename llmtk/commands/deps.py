"""Dependency graph command for llmtk."""

import argparse
import subprocess
import sys

from ..core.context import get_modules_dir, get_project_root
from ..core.dry_run import is_dry_run
from ..core.utils import write_json


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the deps command."""
    parser = subparsers.add_parser(
        "deps",
        help="Extract and export CMake target dependency graphs",
    )
    parser.add_argument("--build-dir", default="build", help="CMake build directory")
    parser.add_argument(
        "--output-dir",
        default="exports/dependency_graphs",
        help="Output directory",
    )
    parser.add_argument("--json", action="store_true", help="Export JSON format")
    parser.add_argument("--graphviz", action="store_true", help="Export Graphviz DOT format")
    parser.add_argument("--symbols", action="store_true", help="Include symbol-level analysis")
    parser.set_defaults(func=handle_deps)


def handle_deps(args: argparse.Namespace) -> int:
    """Handle the deps command."""
    cmd = build_deps_command(args)
    if is_dry_run():
        print("[DRY RUN] Would run dependency graph extraction:")
        print("  " + " ".join(cmd))
        return 0

    result = subprocess.run(
        cmd,
        cwd=get_project_root(),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip(), file=sys.stderr)
    output_json = get_project_root() / str(args.output_dir) / "dependencies.json"
    if result.returncode != 0 and not output_json.exists():
        write_json(
            output_json,
            {
                "_meta": {
                    "build_dir": str(args.build_dir),
                    "codemodel_available": False,
                    "targets_count": 0,
                    "symbol_analysis_available": False,
                },
                "error": result.stderr.strip() or result.stdout.strip() or "Dependency graph export failed",
                "targets": {},
                "symbol_dependencies": {},
                "package_managers": {},
                "dependency_matrix": [],
                "build_order": [],
            },
        )
    return result.returncode


def build_deps_command(args: argparse.Namespace) -> list[str]:
    """Build the dependency graph module command."""
    script = get_modules_dir() / "dependency_graph.py"
    cmd = [
        sys.executable,
        str(script),
        "--build-dir",
        str(args.build_dir),
        "--output-dir",
        str(args.output_dir),
    ]
    if args.json:
        cmd.append("--json")
    if args.graphviz:
        cmd.append("--graphviz")
    if args.symbols:
        cmd.append("--symbols")
    return cmd


def run_deps_for_agent(params: dict) -> int:
    """Run dependency graph extraction from structured agent/MCP parameters."""
    args = argparse.Namespace(
        build_dir=params.get("build_dir", "build"),
        output_dir=params.get("output_dir", "exports/dependency_graphs"),
        json=bool(params.get("json", True)),
        graphviz=bool(params.get("graphviz", False)),
        symbols=bool(params.get("symbols", False)),
    )
    return handle_deps(args)
